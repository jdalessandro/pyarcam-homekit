"""Load ``arcam.json`` for host, timing, and HAP bridge settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArcamConfig:
    """Validated settings for the amplifier connection and bridge."""

    host: str
    port: int = 50000
    timeout_sec: float = 5.0
    poll_interval_seconds: float = 3.0
    display_name: str = "Arcam SA20"
    hap_aid: int | None = 2
    zone: int = 1


def load_config(path: Path) -> ArcamConfig:
    """Parse and validate a JSON config file."""
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    host = str(raw.get("host") or "").strip()
    if not host:
        raise ValueError("config: 'host' is required")

    port = int(raw.get("port", 50000))
    timeout_sec = float(raw.get("timeout_sec", 5.0))
    poll_interval_seconds = float(raw.get("poll_interval_seconds", 3.0))
    display_name = str(raw.get("display_name") or "Arcam SA20")

    hap_raw = raw.get("hap_aid")
    hap_aid = int(hap_raw) if hap_raw is not None else None

    zone = int(raw.get("zone", 1))
    if zone not in (1, 2):
        raise ValueError("config: 'zone' must be 1 or 2")

    return ArcamConfig(
        host=host,
        port=port,
        timeout_sec=timeout_sec,
        poll_interval_seconds=poll_interval_seconds,
        display_name=display_name,
        hap_aid=hap_aid,
        zone=zone,
    )
