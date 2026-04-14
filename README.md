# MeshCore Bridge — Cross-Frequency Message Bridge
### No MQTT, no broker, no cloud. Just LoRa ↔ LoRa.
![Status](https://img.shields.io/badge/Status-Production-green.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux-orange.svg)
![Transport](https://img.shields.io/badge/Transport-Dual%20USB%20Serial-blueviolet.svg)
![Bridge](https://img.shields.io/badge/Bridge-Cross--Frequency%20LoRa%20↔%20LoRa-ff6600.svg)

A standalone daemon that connects two MeshCore devices operating on different radio frequencies. It forwards messages on one or more configurable bridge channels from one device to the other, effectively extending your mesh network across frequency boundaries.

## Table of Contents

- [1. Overview](#1-overview)
- [2. Features](#2-features)
- [3. Requirements](#3-requirements)
  - [3.1. Requirement Status](#31-requirement-status)
- [4. Installation](#4-installation)
  - [4.1. Quick Start](#41-quick-start)
  - [4.2. systemd Service](#42-systemd-service)
- [5. Configuration](#5-configuration)
  - [5.1. File Locations](#51-file-locations)
  - [5.2. config.json Structure](#52-configjson-structure)
  - [5.3. Command-Line Options](#53-command-line-options)
  - [5.4. Bridge Configuration GUI](#54-bridge-configuration-gui)
- [6. How It Works](#6-how-it-works)
  - [6.1. Message Flow](#61-message-flow)
  - [6.2. Loop Prevention](#62-loop-prevention)
  - [6.3. Private (Encrypted) Channels](#63-private-encrypted-channels)
- [7. Dashboard](#7-dashboard)
- [8. File Structure](#8-file-structure)
- [9. Assumptions](#9-assumptions)
- [10. Troubleshooting](#10-troubleshooting)
  - [10.1. Bridge Won't Start](#101-bridge-wont-start)
  - [10.2. Messages Not Forwarding](#102-messages-not-forwarding)
  - [10.3. Port Conflicts](#103-port-conflicts)
  - [10.4. Service Issues](#104-service-issues)
- [11. License](#11-license)
- [12. Author](#12-author)

---

## 1. Overview

The bridge runs as an independent process **on the same hardware** as two running [meshcore-gui](https://github.com/pe1hvh/meshcore-gui) service instances. It imports the existing meshcore_gui modules (SharedData, Worker, models, config) as a library and requires **zero modifications** to the meshcore_gui codebase.

> **⚠️ Prerequisite:** The bridge cannot function without two active meshcore-gui services running on the same host — one per MeshCore device. Install and configure meshcore-gui first: [github.com/pe1hvh/meshcore-gui](https://github.com/pe1hvh/meshcore-gui)

```
┌───────────────────────────────────────────────┐
│           meshcore_bridge daemon               │
│                                               │
│  ┌──────────────┐    ┌──────────────────────┐ │
│  │ SharedData A │    │    BridgeEngine       │ │
│  │ + Worker A   │◄──►│  - multi-pair forward │ │
│  │ (ttyUSB1)    │    │  - direction filter   │ │
│  └──────────────┘    │  - loop prevention    │ │
│  ┌──────────────┐    └──────────────────────┘ │
│  │ SharedData B │◄────────────────────────────┤ │
│  │ + Worker B   │                             │ │
│  │ (ttyUSB2)    │                             │ │
│  └──────────────┘                             │ │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  Bridge Dashboard (NiceGUI :9092)        │  │
│  │  - Device A & B status                  │  │
│  │  - Bridge configuration panel (3-panel) │  │
│  │  - Forwarded message log                │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

Key properties:

- **Separate process** — the bridge runs alongside the two meshcore-gui services on the same host, as an independent process
- **Multiple bridge pairs** — any number of channel pairs can be bridged simultaneously, each with its own direction setting
- **Per-pair direction** — each bridge can be `A→B`, `B→A` or bidirectional `A↔B`
- **Live reconfiguration** — bridges can be added, removed and saved from the dashboard without restarting the daemon
- **Loop prevention** — three mechanisms prevent message loops: direction filter, message hash tracking, and echo suppression
- **Private channels** — encrypted channels work transparently because the bridge operates at the plaintext level
- **DOMCA dashboard** — status page on its own port with device status, bridge configurator and forwarded message log
- **JSON configuration** — all settings in `~/.meshcore-gui/bridge/config.json`; device/channel list read automatically from existing meshcore-gui cache files

## 2. Features

- **Multiple channel bridges** — Configure any number of channel pairs between the two devices
- **Directional forwarding** — Per-pair direction: `A → B`, `B → A`, or `A ↔ B` (bidirectional)
- **Live bridge configurator** — 3-panel GUI: device A channels (left), device B channels (middle), bridge list (right); save without restart
- **Auto device discovery** — Device names and channel lists read from `~/.meshcore-gui/device_identity.json` and the per-device cache files
- **Loop prevention** — Direction filter, message hash tracking, and echo suppression prevent infinite loops
- **Private channel support** — Encrypted channels work transparently; bridge operates at the plaintext level
- **DOMCA dashboard** — Live status page with device connections, bridge statistics and forwarded message log
- **JSON configuration** — No YAML; pure JSON config; no extra dependencies
- **systemd integration** — Install as a background daemon with automatic restart
- **Zero meshcore_gui changes** — Imports existing modules as a library, 0 changed files

## 3. Requirements

- Python 3.10+
- meshcore_gui (installed or on PYTHONPATH)
- meshcore Python library (`pip install meshcore`)
- Two MeshCore devices connected via USB serial
- meshcore_gui must have been run at least once so the device cache files exist

> **Note:** `pyyaml` is no longer required.

### 3.1. Requirement Status

| ID | Requirement | Status |
|----|-------------|--------|
| M1 | Bridge as separate process, meshcore_gui unchanged | ✅ |
| M2 | Forward messages on configured channels A↔B within <2s | ✅ |
| M3 | JSON config for channels, ports, polling interval | ✅ |
| M4 | 0 changed files in meshcore_gui/ | ✅ |
| M5 | GUI identical to meshcore_gui (DOMCA theme) | ✅ |
| M6 | Configurable port (--port=9092) | ✅ |
| M7 | Loop prevention via forwarded-hash set | ✅ |
| M8 | Two devices on different frequencies | ✅ |
| M9 | Private (encrypted) channels fully supported | ✅ |
| M10 | Multiple bridge pairs with per-pair direction | ✅ |
| M11 | Live reconfiguration without daemon restart | ✅ |
| M12 | Device/channel list from meshcore-gui cache files | ✅ |

---

## 4. Installation

### 4.1. Quick Start

```bash
# 1. Run the bridge (no extra pip installs needed)
python meshcore_bridge.py

# 2. Open the dashboard at http://your-host:9092

# 3. Use the Bridge Configuration panel to add channel bridges and save
```

**Prerequisites:** Two meshcore-gui services must be running on this host — one per MeshCore device. See [meshcore-gui](https://github.com/pe1hvh/meshcore-gui) for installation. Both services must have completed at least one successful connection so their cache files exist at `~/.meschcore/cache/`.

### 4.2. systemd Service

Install the bridge as a systemd daemon for production use:

```bash
# Run the installer script
sudo bash install_bridge.sh

# Start the service
sudo systemctl start meshcore-bridge
sudo systemctl enable meshcore-bridge
```

**Useful service commands:**

| Command | Description |
|---------|-------------|
| `sudo systemctl status meshcore-bridge` | Check if the service is running |
| `sudo journalctl -u meshcore-bridge -f` | Follow the live log output |
| `sudo systemctl restart meshcore-bridge` | Restart after a configuration change |
| `sudo systemctl stop meshcore-bridge` | Stop the service |

**Uninstall:**

```bash
sudo bash install_bridge.sh --uninstall
```

---

## 5. Configuration

### 5.1. File Locations

| File | Purpose |
|------|---------|
| `~/.meshcore-gui/bridge/config.json` | Bridge configuration (devices, bridge pairs, runtime settings) |
| `~/.meshcore-gui/device_identity.json` | Device registry read by meshcore_gui — used to resolve device names |
| `~/.meschcore/cache/_dev_ttyUSBX.json` | Per-device cache read by meshcore_gui — provides channel names and radio info |

The bridge config directory and file are created automatically on first save via the dashboard.

### 5.2. config.json Structure

```json
{
  "device_a": {
    "port": "/dev/ttyUSB1",
    "baud": 115200,
    "label": "ZwolsBotje"
  },
  "device_b": {
    "port": "/dev/ttyUSB2",
    "baud": 115200,
    "label": "ZwolsBotje-CZ"
  },
  "bridges": [
    {
      "channel_a_key": "Public",
      "channel_b_key": "Public",
      "direction": "both",
      "enabled": true
    },
    {
      "channel_a_key": "Bridge",
      "channel_b_key": "Bridge",
      "direction": "a_to_b",
      "enabled": true
    }
  ],
  "poll_interval_ms": 200,
  "forward_prefix": true,
  "max_forwarded_cache": 500,
  "gui_port": 9092,
  "gui_title": "MeshCore Bridge"
}
```

**Direction values:**

| Value | Meaning |
|-------|---------|
| `"both"` | Forward in both directions (A↔B) |
| `"a_to_b"` | Forward only from device A to device B |
| `"b_to_a"` | Forward only from device B to device A |

**Bridge pair fields:**

| Field | Type | Description |
|-------|------|-------------|
| `channel_a_key` | string | Channel name on device A (stable identifier) |
| `channel_b_key` | string | Channel name on device B (stable identifier) |
| `direction` | string | Forwarding direction (see table above) |
| `enabled` | bool | Whether this bridge is active |

> **Note:** Bridges are stored by channel *name* (key), not by channel index. At startup the bridge resolves each key to the current channel index from the device cache. If a channel has been re-indexed since the last save, the index is corrected automatically and the config is written back to disk.

### 5.3. Command-Line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--config=PATH` | Path to JSON config file | `~/.meshcore-gui/bridge/config.json` |
| `--port=PORT` | Override GUI port | From config (9092) |
| `--debug-on` | Enable verbose debug logging | Off |
| `--help` | Show usage info | — |

### 5.4. Bridge Configuration GUI

The dashboard includes an interactive **Bridge Configuration** panel with three columns:

- **Left** — Channels available on device A (read from the meshcore-gui cache file)
- **Middle** — Channels available on device B (read from the meshcore-gui cache file)
- **Right** — Active bridge list, with per-bridge enable toggle, direction label and remove button; plus an "Add bridge" form and a "Save configuration" button

Clicking **Save configuration** writes `config.json` and hot-reloads the bridge engine immediately — no restart required.

---

## 6. How It Works

### 6.1. Message Flow

1. **Device A** receives a channel message on a bridge channel via LoRa
2. MeshCore firmware decrypts the message (if private channel) and passes plaintext to the Worker
3. The Worker's EventHandler stores the message in **SharedData A**
4. **BridgeEngine** polls SharedData A, detects the new message, matches it against active bridge pairs
5. If the message matches an enabled pair whose direction allows A→B, BridgeEngine injects a `send_message` command into **SharedData B**'s command queue
6. Worker B picks up the command and transmits the message on Device B's configured channel
7. MeshCore firmware on Device B encrypts (if private channel) and transmits via LoRa

The reverse direction (B→A) works identically and can run simultaneously for bidirectional pairs.

### 6.2. Loop Prevention

The bridge uses three mechanisms to prevent message loops:

1. **Direction filter** — Only incoming messages (`direction='in'`) are forwarded. Messages we transmitted (`direction='out'`) are never forwarded.

2. **Message hash tracking** — Each forwarded message's hash is stored in a bounded set (configurable via `max_forwarded_cache`). If the same hash appears again, it is blocked.

3. **Echo suppression** — When a message is forwarded, the hash of the forwarded text (including `[sender]` prefix) is also registered, preventing the forwarded message from being re-forwarded when it appears on the target device.

### 6.3. Private (Encrypted) Channels

The bridge works transparently with both public and private channels. Both devices must have the bridge channel configured with the same channel secret/password:

- **Inbound**: MeshCore firmware decrypts → Worker receives plaintext → BridgeEngine reads plaintext
- **Outbound**: BridgeEngine injects command → Worker sends via meshcore lib → Firmware encrypts → LoRa TX

> **Prerequisite:** Each bridged channel MUST be configured on both devices with **identical channel secret/password**. Only the frequency and channel index may differ.

---

## 7. Dashboard

The bridge dashboard is accessible at `http://your-host:9092` (or your configured port) and shows:

- **Configuration summary** — config file name, poll interval, prefix setting, number of active bridges
- **Device A status** — connection state, device name, radio frequency
- **Device B status** — connection state, device name, radio frequency
- **Bridge statistics** — messages forwarded (total, A→B, B→A), duplicates blocked, uptime
- **Bridge Configuration** — 3-panel live configurator (see [section 5.4](#54-bridge-configuration-gui))
- **Forwarded message log** — last 200 forwarded messages with timestamps and direction

The dashboard uses the same DOMCA theme as meshcore_gui with dark/light mode toggle.

---

## 8. File Structure

```
meshcore_bridge/
├── __init__.py                             # Package init
├── __main__.py                             # CLI, dual-worker setup, NiceGUI server
├── config.py                               # JSON config loading, BridgePair dataclass
├── bridge_engine.py                        # Core bridge logic, multi-pair, direction filter
├── device_reader.py                        # Reads device_identity.json + cache files
└── gui/
    ├── __init__.py                         # GUI package init
    ├── dashboard.py                        # Bridge dashboard page
    └── panels/
        ├── __init__.py                     # Panels package init
        ├── status_panel.py                 # Device connection status
        ├── log_panel.py                    # Forwarded message log
        └── bridge_config_panel.py          # 3-panel bridge configurator (new)

install_bridge.sh                           # systemd service installer
README.md                                   # This documentation
```

**Changed files in meshcore_gui/:** 0 (zero)

---

## 9. Assumptions

- Both MeshCore devices are connected via USB serial to the same host (Raspberry Pi / Linux server)
- meshcore_gui has connected to both devices at least once, so `~/.meschcore/cache/_dev_ttyUSBX.json` files exist
- Each bridged channel has identical channel secret/password on both devices
- The meshcore_gui package is importable (installed via `pip install -e .` or on PYTHONPATH)
- Sufficient CPU/RAM for two simultaneous MeshCore connections (~100MB)
- Messages are forwarded with a sender prefix `[original_sender]` for identification (configurable)

---

## 10. Troubleshooting

### 10.1. Bridge Won't Start

- Check that both serial ports exist: `ls -l /dev/ttyUSB*`
- Verify meshcore_gui is importable: `python -c "from meshcore_gui.core.shared_data import SharedData"`
- Check that the device cache files exist: `ls ~/.meschcore/cache/`

### 10.2. Messages Not Forwarding

- Open the dashboard and verify both devices show "Connected"
- Check the Bridge Configuration panel: is the relevant bridge pair enabled?
- Verify the channel secret is identical on both devices for that channel
- Enable debug mode: `python meshcore_bridge.py --debug-on`

### 10.3. Channel List Empty in Config Panel

- The channel list is read from `~/.meschcore/cache/_dev_ttyUSBX.json`
- Run meshcore_gui and connect to both devices at least once to populate these files
- Check the file exists: `ls ~/.meschcore/cache/`

### 10.4. Port Conflicts

| Daemon | Default Port |
|---|---|
| meshcore_gui | 8081 |
| **meshcore_bridge** | **9092** |
| meshcore_observer | 9093 |

Change via `--port=XXXX` or in `config.json`.

### 10.5. Service Issues

```bash
sudo systemctl status meshcore-bridge
journalctl -u meshcore-bridge -f
sudo systemctl restart meshcore-bridge
```

---

## 11. License

MIT License — Copyright (c) 2026 PE1HVH

## 12. Author

**PE1HVH** — [GitHub](https://github.com/pe1hvh) — DOMCA MeshCore Project
