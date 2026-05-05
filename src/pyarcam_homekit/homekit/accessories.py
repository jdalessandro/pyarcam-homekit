"""
HomeKit bridge and Television-shaped accessory for Arcam SA10/SA20.

Characteristic mapping uses pyarcam over TCP (port 50000). Linked services
(TelevisionSpeaker, InputSource) follow HAP-python's requirement to assign
``broker`` and IIDs before serializing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from pyhap.accessory import Accessory, Bridge
from pyhap.const import CATEGORY_BRIDGE, CATEGORY_TELEVISION
from pyhap.service import Service
from pyarcam.client import ArcamClient
from pyarcam.constants import (
    ZONE_1,
    ZONE_2,
    InputSource,
    PowerState,
)
from pyarcam.exceptions import ArcamError

from pyarcam_homekit.arcam.config import ArcamConfig

logger = logging.getLogger(__name__)

# pyarcam maps some failures to Arcam*; connect() can still raise plain TimeoutError / OSError.
_RECOVERABLE_AMP: tuple[type[BaseException], ...] = (
    ArcamError,
    TimeoutError,
    ConnectionError,
    OSError,
)

# All discrete inputs defined for SA10/SA20 (protocol order).
INPUT_SOURCES: tuple[InputSource, ...] = tuple(InputSource)


def _amp_volume_to_hap(level: int) -> int:
    level = max(0, min(99, int(level)))
    return int(round(level * 100 / 99))


def _hap_volume_to_amp(level: int) -> int:
    level = max(0, min(100, int(level)))
    return min(99, int(round(level * 99 / 100)))


class ArcamAmpAccessory(Accessory):
    """Television primary service + linked speaker + one InputSource per input."""

    category = CATEGORY_TELEVISION

    def __init__(
        self,
        driver: Any,
        cfg: ArcamConfig,
        client: ArcamClient,
    ) -> None:
        super().__init__(driver, cfg.display_name, aid=cfg.hap_aid)
        self._client = client

        loader = self.driver.loader

        tv = loader.get_service("Television")
        tv.configure_char("ConfiguredName", value=cfg.display_name)
        tv.configure_char("SleepDiscoveryMode", value=1)
        tv.configure_char("Active", setter_callback=self._set_active)
        tv.configure_char("ActiveIdentifier", setter_callback=self._set_active_identifier)

        sp = loader.get_service("TelevisionSpeaker")
        sp.unique_id = "arcam-tv-speaker"
        sp.add_characteristic(loader.get_char("Volume"))
        sp.configure_char("Mute", setter_callback=self._set_mute)
        sp.configure_char("Volume", setter_callback=self._set_volume)

        self.add_service(tv)
        self._register_linked(tv, sp)

        for src in INPUT_SOURCES:
            inp = loader.get_service("InputSource")
            inp.unique_id = f"arcam-input-{src.name.lower()}"
            inp.add_characteristic(loader.get_char("Identifier"))
            label = src.name.replace("_", " ").title()
            inp.configure_char("ConfiguredName", value=label)
            inp.configure_char("InputSourceType", value=0)
            inp.configure_char("IsConfigured", value=1)
            inp.configure_char("CurrentVisibilityState", value=0)
            inp.configure_char("Identifier", value=int(src.value))
            self._register_linked(tv, inp)

        # HAP accessory JSON must list every service object, not only Television's
        # "linked" IIDs — otherwise HomeKit often exposes Active (power) only.
        for child in tv.linked_services:
            self.add_service(child)

        self.set_primary_service(tv)
        self._serv_tv = tv
        self._serv_sp = sp

        self.set_info_service(
            manufacturer="Arcam",
            model="SA10/SA20",
            serial_number=f"{cfg.host}:{cfg.port}",
            firmware_revision="1.0.0",
        )

    def _register_linked(self, parent: Service, child: Service) -> None:
        child.broker = self
        self.iid_manager.assign(child)
        for ch in child.characteristics:
            ch.broker = self
            self.iid_manager.assign(ch)
        parent.add_linked_service(child)

    def _close_client_safely(self) -> None:
        try:
            self._client.close()
        except OSError:
            pass

    def _set_active(self, value: int) -> None:
        try:
            if int(value) == 1:
                self._client.power_on()
            else:
                self._client.power_off()
        except _RECOVERABLE_AMP as e:
            logger.warning("power command failed (%s:%s): %s", self._client.host, self._client.port, e)
            self._close_client_safely()

    def _set_active_identifier(self, value: int) -> None:
        vid = int(value)
        try:
            src = InputSource(vid)
        except ValueError:
            logger.warning("unknown input identifier %s", vid)
            return
        try:
            self._client.set_input(src, processor_mode=False)
        except _RECOVERABLE_AMP as e:
            logger.warning("set_input failed (%s:%s): %s", self._client.host, self._client.port, e)
            self._close_client_safely()

    def _set_mute(self, value: bool) -> None:
        try:
            if value:
                self._client.mute()
            else:
                self._client.unmute()
        except _RECOVERABLE_AMP as e:
            logger.warning("mute command failed (%s:%s): %s", self._client.host, self._client.port, e)
            self._close_client_safely()

    def _set_volume(self, value: int) -> None:
        try:
            self._client.set_volume(_hap_volume_to_amp(int(value)))
        except _RECOVERABLE_AMP as e:
            logger.warning("volume command failed (%s:%s): %s", self._client.host, self._client.port, e)
            self._close_client_safely()

    def apply_amp_state(self) -> None:
        """Sync HAP characteristics from the amplifier (call holds TCP lock inside pyarcam)."""
        tv = self._serv_tv
        sp = self._serv_sp

        try:
            power = self._client.get_power_state()
            active = 1 if power == PowerState.ON else 0
            tv.get_characteristic("Active").set_value(active, should_notify=True)

            vol = self._client.get_volume()
            muted = self._client.get_mute()
            sp.get_characteristic("Mute").set_value(bool(muted), should_notify=True)
            sp.get_characteristic("Volume").set_value(
                _amp_volume_to_hap(vol), should_notify=True
            )

            current, _proc = self._client.get_input()
            if current is not None:
                tv.get_characteristic("ActiveIdentifier").set_value(
                    int(current.value), should_notify=True
                )
        except _RECOVERABLE_AMP as e:
            logger.warning(
                "Arcam unreachable (%s:%s): %s — check IP, LAN, and amp network standby",
                self._client.host,
                self._client.port,
                e,
            )
            self._close_client_safely()


class ArcamBridge(Bridge):
    """HAP bridge that owns an Arcam client and polls state like smartrent-devices-homekit."""

    category = CATEGORY_BRIDGE

    def __init__(
        self,
        driver: Any,
        display_name: str,
        cfg: ArcamConfig,
        client: ArcamClient,
    ) -> None:
        super().__init__(driver, display_name)
        self._cfg = cfg
        self._amp = ArcamAmpAccessory(driver, cfg, client)
        self.add_accessory(self._amp)
        self._poll_task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        await super().run()
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._amp.apply_amp_state)
        except Exception:
            logger.exception("initial Arcam state sync failed (unexpected)")
        self._poll_task = asyncio.create_task(self._poll_loop(), name="arcam-poll")

    async def _poll_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            await asyncio.sleep(self._cfg.poll_interval_seconds)
            try:
                await loop.run_in_executor(None, self._amp.apply_amp_state)
            except Exception:
                logger.exception("Arcam poll failed (unexpected)")

    async def stop(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        await super().stop()


def zone_constant(zone: int) -> int:
    """Map config zone (1 or 2) to pyarcam zone bytes."""
    return ZONE_1 if zone == 1 else ZONE_2
