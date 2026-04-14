"""
Bridge-specific configuration — JSON-based.

Loads settings from ~/.meshcore-gui/bridge/config.json.
Provides typed access to device connections, bridge pairs and runtime
parameters. Falls back to sensible defaults when keys are missing.

No external dependencies beyond the Python standard library are required.

Bridge pairs are stored by channel key (channel name) rather than by
channel index. On startup, call resolve_bridge_indices() to populate the
runtime channel_a / channel_b integer fields from the current device
channel maps. If a key-to-index mapping has drifted, the index is
corrected automatically and the updated config is written back to disk.

                 Author: PE1HVH
                Version: 1.0.2
SPDX-License-Identifier: MIT
              Copyright: (c) 2026 PE1HVH
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_CONFIG_PATH: Path = (
    Path.home() / ".meshcore-gui" / "bridge" / "config.json"
)


@dataclass
class DeviceConfig:
    """Configuration for a single MeshCore device connection."""

    port: str = "/dev/ttyUSB0"
    baud: int = 115200
    label: str = ""


@dataclass
class BridgePair:
    """A single channel bridge between device A and device B.

    Bridge pairs are stored by channel *key* (channel name) for
    stability across device reconnects or firmware channel re-indexes.

    Persistent attributes (written to / read from JSON):
        channel_a_key:  Channel name on device A (stable identifier).
        channel_b_key:  Channel name on device B (stable identifier).
        direction:      Forwarding direction — 'a_to_b', 'b_to_a', or 'both'.
        enabled:        Whether this bridge is active.

    Runtime attributes (not persisted; populated by resolve_bridge_indices()):
        channel_a:  Current channel index on device A.
        channel_b:  Current channel index on device B.
    """

    # Persistent — stored in config.json
    channel_a_key: str = ""
    channel_b_key: str = ""
    direction: str = "both"   # 'a_to_b' | 'b_to_a' | 'both'
    enabled: bool = True

    # Runtime only — resolved from device channel map at startup
    channel_a: int = field(default=0, compare=False, repr=False)
    channel_b: int = field(default=0, compare=False, repr=False)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON persistence.

        Only the key-based fields are written; runtime indices are omitted.
        """
        return {
            "channel_a_key": self.channel_a_key,
            "channel_b_key": self.channel_b_key,
            "direction": self.direction,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BridgePair":
        """Deserialise from a plain dict.

        Args:
            d: Dict with optional keys channel_a_key, channel_b_key,
               direction, enabled.

        Returns:
            Populated BridgePair instance (channel_a/channel_b default to 0
            until resolve_bridge_indices() is called).
        """
        return cls(
            channel_a_key=str(d.get("channel_a_key", "")),
            channel_b_key=str(d.get("channel_b_key", "")),
            direction=str(d.get("direction", "both")),
            enabled=bool(d.get("enabled", True)),
        )


def resolve_bridge_indices(
    bridges: List[BridgePair],
    channels_a: Dict[int, str],
    channels_b: Dict[int, str],
) -> Tuple[List[BridgePair], bool]:
    """Populate and verify runtime channel indices from channel key maps.

    For each BridgePair, the stored channel_a_key / channel_b_key (channel
    names) are looked up in the current device channel maps to obtain the
    runtime channel_a / channel_b integer indices required by BridgeEngine.

    If the index for a key has changed since the config was last written
    (e.g. after a firmware update or channel re-order), the runtime index is
    corrected in-place and ``changed`` is returned as True — the caller
    should then persist the updated config back to disk.

    Keys that are not found in the current channel map are left at index 0
    and a warning is logged; this can happen when a device is unreachable at
    startup.

    Args:
        bridges:    List of BridgePair instances to resolve (mutated in place).
        channels_a: Index → name map for device A.
        channels_b: Index → name map for device B.

    Returns:
        Tuple of (bridges, changed) where changed is True when at least one
        runtime index was corrected.
    """
    log = logging.getLogger(__name__)

    # Build reverse maps: name → index
    name_to_idx_a: Dict[str, int] = {name: idx for idx, name in channels_a.items()}
    name_to_idx_b: Dict[str, int] = {name: idx for idx, name in channels_b.items()}

    changed = False

    for bridge in bridges:
        # ── Side A ──────────────────────────────────────────────────
        idx_a = name_to_idx_a.get(bridge.channel_a_key)
        if idx_a is None:
            log.warning(
                "Bridge key %r not found in device A channel map; "
                "keeping runtime index %d",
                bridge.channel_a_key,
                bridge.channel_a,
            )
        elif idx_a != bridge.channel_a:
            log.info(
                "Bridge key %r: device A index corrected %d → %d",
                bridge.channel_a_key,
                bridge.channel_a,
                idx_a,
            )
            bridge.channel_a = idx_a
            changed = True
        else:
            bridge.channel_a = idx_a

        # ── Side B ──────────────────────────────────────────────────
        idx_b = name_to_idx_b.get(bridge.channel_b_key)
        if idx_b is None:
            log.warning(
                "Bridge key %r not found in device B channel map; "
                "keeping runtime index %d",
                bridge.channel_b_key,
                bridge.channel_b,
            )
        elif idx_b != bridge.channel_b:
            log.info(
                "Bridge key %r: device B index corrected %d → %d",
                bridge.channel_b_key,
                bridge.channel_b,
                idx_b,
            )
            bridge.channel_b = idx_b
            changed = True
        else:
            bridge.channel_b = idx_b

    return bridges, changed


@dataclass
class BridgeConfig:
    """Complete bridge daemon configuration."""

    # Device connections
    device_a: DeviceConfig = field(default_factory=lambda: DeviceConfig(
        port="/dev/ttyUSB1", label="Device A",
    ))
    device_b: DeviceConfig = field(default_factory=lambda: DeviceConfig(
        port="/dev/ttyUSB2", label="Device B",
    ))

    # Bridge pairs (zero or more)
    bridges: List[BridgePair] = field(default_factory=list)

    # Shared runtime settings
    poll_interval_ms: int = 200
    forward_prefix: bool = True
    max_forwarded_cache: int = 500

    # GUI settings
    gui_port: int = 9092
    gui_title: str = "MeshCore Bridge"

    # Runtime flags — set from CLI, not persisted to JSON
    debug: bool = False
    config_path: str = ""

    @classmethod
    def from_json(cls, path: Path) -> "BridgeConfig":
        """Load configuration from a JSON file.

        Missing keys fall back to dataclass defaults.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            Populated BridgeConfig instance.

        Raises:
            json.JSONDecodeError: If the file contains invalid JSON.
            OSError: If the file cannot be opened.
        """
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh) or {}

        device_a_section = raw.get("device_a", {})
        device_b_section = raw.get("device_b", {})
        bridges_raw = raw.get("bridges", [])

        dev_a = DeviceConfig(
            port=device_a_section.get("port", "/dev/ttyUSB1"),
            baud=int(device_a_section.get("baud", 115200)),
            label=device_a_section.get("label", "Device A"),
        )
        dev_b = DeviceConfig(
            port=device_b_section.get("port", "/dev/ttyUSB2"),
            baud=int(device_b_section.get("baud", 115200)),
            label=device_b_section.get("label", "Device B"),
        )

        bridges = [BridgePair.from_dict(b) for b in bridges_raw if isinstance(b, dict)]

        return cls(
            device_a=dev_a,
            device_b=dev_b,
            bridges=bridges,
            poll_interval_ms=int(raw.get("poll_interval_ms", 200)),
            forward_prefix=bool(raw.get("forward_prefix", True)),
            max_forwarded_cache=int(raw.get("max_forwarded_cache", 500)),
            gui_port=int(raw.get("gui_port", 9092)),
            gui_title=str(raw.get("gui_title", "MeshCore Bridge")),
        )

    def to_json(self, path: Path) -> None:
        """Write the current configuration to a JSON file.

        Parent directories are created if they do not exist.

        Args:
            path: Destination file path.
        """
        data = {
            "device_a": {
                "port": self.device_a.port,
                "baud": self.device_a.baud,
                "label": self.device_a.label,
            },
            "device_b": {
                "port": self.device_b.port,
                "baud": self.device_b.baud,
                "label": self.device_b.label,
            },
            "bridges": [b.to_dict() for b in self.bridges],
            "poll_interval_ms": self.poll_interval_ms,
            "forward_prefix": self.forward_prefix,
            "max_forwarded_cache": self.max_forwarded_cache,
            "gui_port": self.gui_port,
            "gui_title": self.gui_title,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
