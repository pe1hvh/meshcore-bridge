"""
Bridge-specific configuration — JSON-based.

Loads settings from ~/.meshcore-gui/bridge/config.json.
Provides typed access to device connections, bridge pairs and runtime
parameters. Falls back to sensible defaults when keys are missing.

Replaces the previous YAML-based configuration entirely; no pyyaml
dependency is required.

                 Author: PE1HVH
                Version: 2.0.0
SPDX-License-Identifier: MIT
              Copyright: (c) 2026 PE1HVH
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


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

    Attributes:
        channel_a:  Channel index on device A.
        channel_b:  Channel index on device B.
        direction:  Forwarding direction — 'a_to_b', 'b_to_a', or 'both'.
        enabled:    Whether this bridge is active.
    """

    channel_a: int = 0
    channel_b: int = 0
    direction: str = "both"   # 'a_to_b' | 'b_to_a' | 'both'
    enabled: bool = True

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON persistence."""
        return {
            "channel_a": self.channel_a,
            "channel_b": self.channel_b,
            "direction": self.direction,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BridgePair":
        """Deserialise from a plain dict.

        Args:
            d: Dict with optional keys channel_a, channel_b,
               direction, enabled.

        Returns:
            Populated BridgePair instance.
        """
        return cls(
            channel_a=int(d.get("channel_a", 0)),
            channel_b=int(d.get("channel_b", 0)),
            direction=str(d.get("direction", "both")),
            enabled=bool(d.get("enabled", True)),
        )


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
