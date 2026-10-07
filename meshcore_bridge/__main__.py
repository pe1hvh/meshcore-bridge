#!/usr/bin/env python3
"""
MeshCore Bridge — Entry Point
==============================

Parses command-line arguments, loads JSON configuration from
~/.meshcore-gui/bridge/config.json (with device identities from
~/.meshcore-gui/device_identity.json), creates two SharedData/Worker
pairs (one per device), initialises the BridgeEngine, registers the
NiceGUI dashboard page and starts the server.

Usage:
    python meshcore_bridge.py
    python meshcore_bridge.py --config=~/.meshcore-gui/bridge/config.json
    python meshcore_bridge.py --port=9092
    python meshcore_bridge.py --debug-on

                   Author: PE1HVH
                  Version: 2.0.2
  SPDX-License-Identifier: MIT
                Copyright: (c) 2026 PE1HVH
"""

import sys
import threading
import time
from pathlib import Path

from nicegui import ui

import meshcore_gui.config as gui_config

try:
    from meshcore import MeshCore, EventType  # noqa: F401
except ImportError:
    print("ERROR: meshcore library not found")
    print("Install with: pip install meshcore")
    sys.exit(1)

from meshcore_gui.ble.worker import create_worker
from meshcore_gui.core.shared_data import SharedData

from meshcore_bridge.config import BridgeConfig, DEFAULT_CONFIG_PATH, resolve_bridge_indices
from meshcore_bridge.bridge_engine import BridgeEngine
from meshcore_bridge.device_reader import (
    CACHE_DIR,
    cache_mtime,
    read_device_identity,
    read_device_channels,
)
from meshcore_bridge.gui.dashboard import BridgeDashboard


# Global dashboard instance (needed by NiceGUI page decorator)
_dashboard: BridgeDashboard | None = None


@ui.page('/')
def _page_dashboard():
    """NiceGUI page handler — bridge dashboard."""
    if _dashboard:
        _dashboard.render()


def _print_usage():
    """Show usage information."""
    print("MeshCore Bridge — Cross-Frequency Message Bridge Daemon")
    print("=" * 58)
    print()
    print("Usage: python meshcore_bridge.py [OPTIONS]")
    print()
    print("Options:")
    print("  --config=PATH     Path to bridge config JSON")
    print(f"                    (default: {DEFAULT_CONFIG_PATH})")
    print("  --port=PORT       Override GUI port from config (default: 9092)")
    print("  --debug-on        Enable verbose debug logging")
    print("  --help            Show this help message")
    print()
    print("Configuration:")
    print(f"  Device identities : ~/.meshcore-gui/device_identity.json")
    print(f"  Bridge config     : {DEFAULT_CONFIG_PATH}")
    print(f"  Channel cache     : {CACHE_DIR}/_dev_ttyUSBX.json")
    print()
    print("Examples:")
    print("  python meshcore_bridge.py")
    print("  python meshcore_bridge.py --config=/etc/meshcore/bridge.json")
    print("  python meshcore_bridge.py --port=9092 --debug-on")


def _parse_flags(argv):
    """Parse CLI arguments into a flag dict.

    Handles ``--flag=value`` and boolean ``--flag`` forms.
    """
    flags = {}
    for a in argv:
        if '=' in a and a.startswith('--'):
            key, value = a.split('=', 1)
            flags[key] = value
        elif a.startswith('--'):
            flags[a] = True
    return flags


# Interval for checking the cache files while bridge pairs are unresolved (s)
_RESOLVE_CHECK_S: float = 5.0


def _resolve_bridges(cfg: BridgeConfig, config_path: Path) -> None:
    """Resolve bridge channel keys to runtime indices from the cache files.

    Mutates the BridgePair instances in ``cfg.bridges`` in place and
    writes the config back to disk when an index was corrected.

    Args:
        cfg:         BridgeConfig with device ports and bridge pairs.
        config_path: Path of the config file to persist corrections to.
    """
    if not cfg.bridges:
        return
    channels_a = read_device_channels(cfg.device_a.port)
    channels_b = read_device_channels(cfg.device_b.port)
    ch_map_a = channels_a.channels if channels_a else {}
    ch_map_b = channels_b.channels if channels_b else {}

    _, indices_changed = resolve_bridge_indices(cfg.bridges, ch_map_a, ch_map_b)
    if indices_changed:
        print("Bridge indices corrected — saving updated config.")
        cfg.to_json(config_path)


def _bridge_poll_loop(
    engine: BridgeEngine,
    cfg: BridgeConfig,
    config_path: Path,
):
    """Background thread that runs the bridge polling loop.

    While enabled bridge pairs are unresolved (e.g. no cache file existed
    at startup), the cache files are checked every ``_RESOLVE_CHECK_S``
    seconds and resolution is retried whenever one of them has changed.
    The Workers write the cache files on their first successful
    connection, so pairs become active without a restart.

    Args:
        engine:      BridgeEngine instance.
        cfg:         BridgeConfig (bridge pairs are resolved in place).
        config_path: Path of the config file.
    """
    interval_s = cfg.poll_interval_ms / 1000.0
    last_check = time.monotonic()
    last_mtimes = (cache_mtime(cfg.device_a.port), cache_mtime(cfg.device_b.port))
    while True:
        try:
            now = time.monotonic()
            pending = [b for b in cfg.bridges if b.enabled and not b.resolved]
            if pending and now - last_check >= _RESOLVE_CHECK_S:
                last_check = now
                mtimes = (cache_mtime(cfg.device_a.port),
                          cache_mtime(cfg.device_b.port))
                if mtimes != last_mtimes:
                    last_mtimes = mtimes
                    _resolve_bridges(cfg, config_path)
                    resolved = sum(1 for b in pending if b.resolved)
                    if resolved:
                        print(f"Bridge pairs resolved: {resolved}/{len(pending)}")
                    engine.reload_bridges(cfg.bridges)
            engine.poll_and_forward()
        except Exception as e:
            gui_config.debug_print(f"Bridge poll error: {e}")
        time.sleep(interval_s)


def _resolve_device_ports(cfg: BridgeConfig) -> tuple[str, str]:
    """Resolve device A and B ports from device_identity.json if not yet set.

    When device_a.port / device_b.port are still at their defaults and
    device_identity.json exists, pick the first two known ports in order.

    Args:
        cfg: BridgeConfig (mutated in-place when ports are resolved).

    Returns:
        Tuple (port_a, port_b).
    """
    identity = read_device_identity()
    if not identity:
        return cfg.device_a.port, cfg.device_b.port

    ports = list(identity.keys())

    # Only auto-assign when ports are still at default values
    defaults = {"/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"}
    if cfg.device_a.port in defaults and len(ports) >= 1:
        port_a = ports[0]
        info_a = identity[port_a]
        cfg.device_a.port = port_a
        cfg.device_a.label = info_a.get("device_name", port_a)

    if cfg.device_b.port in defaults and len(ports) >= 2:
        port_b = ports[1]
        info_b = identity[port_b]
        cfg.device_b.port = port_b
        cfg.device_b.label = info_b.get("device_name", port_b)

    return cfg.device_a.port, cfg.device_b.port


def main():
    """Main entry point.

    Loads configuration, resolves device ports from device_identity.json,
    creates dual workers, starts the bridge engine and the NiceGUI dashboard.
    """
    global _dashboard

    flags = _parse_flags(sys.argv[1:])

    if '--help' in flags:
        _print_usage()
        sys.exit(0)

    # ── Load configuration ──
    config_path = Path(
        flags.get('--config', str(DEFAULT_CONFIG_PATH))
    ).expanduser()

    if config_path.exists():
        print(f"Loading config from: {config_path}")
        cfg = BridgeConfig.from_json(config_path)
    else:
        print(f"Config not found at {config_path}, using defaults.")
        print("Run with --help for usage information.")
        cfg = BridgeConfig()

    cfg.config_path = str(config_path)

    # ── CLI overrides ──
    if '--debug-on' in flags:
        cfg.debug = True
        gui_config.DEBUG = True

    if '--port' in flags:
        try:
            cfg.gui_port = int(flags['--port'])
        except ValueError:
            print(f"ERROR: Invalid port: {flags['--port']}")
            sys.exit(1)

    # ── Resolve device ports from device_identity.json ──
    port_a, port_b = _resolve_device_ports(cfg)

    # ── Resolve bridge channel indices from channel key maps ──
    # Unresolved pairs (no cache yet) are retried by the poll loop.
    _resolve_bridges(cfg, config_path)

    # ── Startup banner ──
    print("=" * 58)
    print("MeshCore Bridge — Cross-Frequency Message Bridge Daemon")
    print("=" * 58)
    print(f"Config:         {config_path}")
    print(f"Device A:       {port_a} ({cfg.device_a.label})")
    print(f"Device B:       {port_b} ({cfg.device_b.label})")
    print(f"Bridges:        {len(cfg.bridges)} configured")
    print(f"Poll interval:  {cfg.poll_interval_ms}ms")
    print(f"GUI port:       {cfg.gui_port}")
    print(f"Forward prefix: {'ON' if cfg.forward_prefix else 'OFF'}")
    print(f"Debug mode:     {'ON' if cfg.debug else 'OFF'}")
    print("=" * 58)

    # ── Create dual SharedData instances ──
    shared_a = SharedData(f"bridge_a_{port_a.replace('/', '_')}")
    shared_b = SharedData(f"bridge_b_{port_b.replace('/', '_')}")

    # ── Create BridgeEngine ──
    engine = BridgeEngine(shared_a, shared_b, cfg)

    # ── Create and start workers (one per device) ──
    gui_config.SERIAL_BAUDRATE = cfg.device_a.baud
    worker_a = create_worker(port_a, shared_a, baudrate=cfg.device_a.baud)

    gui_config.SERIAL_BAUDRATE = cfg.device_b.baud
    worker_b = create_worker(port_b, shared_b, baudrate=cfg.device_b.baud)

    print(f"Starting worker A ({port_a})...")
    worker_a.start()

    print(f"Starting worker B ({port_b})...")
    worker_b.start()

    # ── Start bridge polling thread ──
    print(f"Starting bridge engine (poll every {cfg.poll_interval_ms}ms)...")
    poll_thread = threading.Thread(
        target=_bridge_poll_loop,
        args=(engine, cfg, config_path),
        daemon=True,
    )
    poll_thread.start()

    # ── Create dashboard ──
    _dashboard = BridgeDashboard(shared_a, shared_b, engine, cfg)

    # ── Start NiceGUI server (blocks) ──
    print(f"Starting GUI on port {cfg.gui_port}...")
    ui.run(
        show=False,
        host='0.0.0.0',
        title=cfg.gui_title,
        port=cfg.gui_port,
        reload=False,
        storage_secret='meshcore-bridge-secret',
    )


if __name__ == "__main__":
    main()
