"""CLI entry: load arcam.json, pair HAP bridge, poll amplifier state."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pyhap.accessory_driver import AccessoryDriver

from pyarcam.client import ArcamClient

from pyarcam_homekit.arcam.config import load_config
from pyarcam_homekit.homekit.accessories import ArcamBridge, zone_constant


def _pincode_from_env() -> bytes:
    raw = os.environ.get("ARCAM_HAP_PINCODE", "031-45-154")
    return raw.encode("ascii")


def main() -> None:
    level_name = os.environ.get("ARCAM_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("pyarcam_homekit")

    config_path = Path(os.environ.get("ARCAM_CONFIG", "arcam.json")).expanduser()
    if not config_path.is_file():
        log.error("Config not found: %s (set ARCAM_CONFIG or create arcam.json)", config_path)
        sys.exit(1)

    cfg = load_config(config_path)

    port = int(os.environ.get("ARCAM_HAP_PORT", "51827"))
    persist = os.path.expanduser(
        os.environ.get("ARCAM_HAP_PERSIST", "~/.pyarcam_homekit.state")
    )

    client = ArcamClient(
        cfg.host,
        port=cfg.port,
        zone=zone_constant(cfg.zone),
        timeout=cfg.timeout_sec,
    )

    driver = AccessoryDriver(
        port=port,
        persist_file=persist,
        pincode=_pincode_from_env(),
    )
    bridge = ArcamBridge(driver, "Arcam Bridge", cfg, client)
    driver.add_accessory(bridge)

    log.info(
        "Starting HAP on port %s (persist %s); polling Arcam at %s:%s every %ss",
        port,
        persist,
        cfg.host,
        cfg.port,
        cfg.poll_interval_seconds,
    )
    try:
        driver.start()
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
