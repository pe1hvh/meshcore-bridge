"""
Device reader — reads device identity and channel info from meshcore-gui cache files.

Provides typed access to device names and channel lists from:
  ~/.meshcore-gui/device_identity.json   — device registry
  ~/.meschcore/cache/_dev_ttyUSBX.json   — per-device channel and radio info

Note: The cache directory uses the spelling 'meschcore' (with 'ch') as found
in the actual application file layout.

                 Author: PE1HVH
                Version: 1.0.0
SPDX-License-Identifier: MIT
              Copyright: (c) 2026 PE1HVH
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


IDENTITY_PATH: Path = Path.home() / ".meshcore-gui" / "device_identity.json"
CACHE_DIR: Path = Path.home() / ".meschcore" / "cache"


@dataclass
class DeviceChannels:
    """Channel and radio information for a single MeshCore device.

    Attributes:
        port:        Serial port path, e.g. '/dev/ttyUSB1'.
        device_name: Human-readable device name from firmware.
        radio_freq:  Radio frequency in MHz (0.0 if unknown).
        channels:    Mapping of channel index -> channel name.
    """

    port: str
    device_name: str
    radio_freq: float
    channels: Dict[int, str] = field(default_factory=dict)


def _port_to_cache_filename(port: str) -> str:
    """Convert a port path to its cache filename.

    Example: ``/dev/ttyUSB1`` → ``_dev_ttyUSB1.json``

    Args:
        port: Serial port path.

    Returns:
        Cache filename string.
    """
    return port.replace("/", "_") + ".json"


def read_device_identity() -> Dict[str, dict]:
    """Read all device entries from device_identity.json.

    Returns:
        Dict mapping port path -> identity dict.
        Empty dict if the file does not exist or cannot be parsed.
    """
    if not IDENTITY_PATH.exists():
        return {}
    try:
        with open(IDENTITY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def read_device_channels(port: str) -> Optional[DeviceChannels]:
    """Read channel and radio info from the per-device cache file.

    Args:
        port: Serial port path, e.g. '/dev/ttyUSB1'.

    Returns:
        Populated DeviceChannels if the cache file exists and is valid,
        None otherwise.
    """
    cache_file = CACHE_DIR / _port_to_cache_filename(port)
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None

    device_section = data.get("device", {})
    channel_names = data.get("channel_names", {})

    channels: Dict[int, str] = {}
    for idx_str, name in channel_names.items():
        try:
            channels[int(idx_str)] = name
        except ValueError:
            pass

    return DeviceChannels(
        port=port,
        device_name=device_section.get("name", port),
        radio_freq=float(device_section.get("radio_freq", 0.0)),
        channels=channels,
    )


def read_all_devices() -> Dict[str, DeviceChannels]:
    """Read all known devices from identity file, enriched with cache data.

    Returns:
        Dict mapping port path -> DeviceChannels for all known devices.
        Devices without a cache file get an empty channel list.
    """
    identity = read_device_identity()
    result: Dict[str, DeviceChannels] = {}

    for port, info in identity.items():
        cached = read_device_channels(port)
        if cached:
            result[port] = cached
        else:
            result[port] = DeviceChannels(
                port=port,
                device_name=info.get("device_name", port),
                radio_freq=0.0,
                channels={},
            )

    return result
