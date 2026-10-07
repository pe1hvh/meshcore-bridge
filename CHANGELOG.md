# Changelog

All notable changes to MeshCore Bridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.3] — 2026-10-07

### FIXED
- `device_reader.py`: Channel cache was read from `~/.meschcore/cache/`, while
  meshcore_gui writes it to `~/.meshcore-gui/cache/`. `CACHE_DIR` is now
  imported from `meshcore_gui.services.cache` (single source of truth). With
  the wrong path every channel map was empty, all bridge pairs ran on
  channel index 0 and the configuration panel showed no channels.
- `config.py` / `bridge_engine.py`: A bridge pair whose channel key cannot be
  resolved no longer falls back to channel index 0. `BridgePair` has a new
  runtime attribute `resolved`; `BridgeEngine` skips unresolved pairs.
- `__main__.py`: Bridge indices were resolved only once, before the Workers
  connected. While pairs are unresolved, the poll loop now checks the device
  cache files every 5 s and re-resolves when one has changed, so pairs become
  active after the first connection without a restart.
- `README.md`: Reverted the 1.0.2 change of the cache path to
  `~/.meschcore/cache/`; the correct path is `~/.meshcore-gui/cache/`.
- `README.md`: meshcore-gui only needs to be installed, not running. The bridge
  opens both serial ports through its own Workers; the prerequisite is replaced
  by a warning not to run meshcore-gui on the same serial ports.
- `README.md`: Table of contents for section 10 matched to the section headings.
- `meshcore_bridge.py`, `__init__.py`: Docstrings no longer describe the bridge
  as connecting two meshcore_gui instances; stale `bridge_config.yaml` usage
  example replaced by the JSON config path.

### CHANGED
- `bridge_config_panel.py`: Pairs added via the GUI are marked resolved when
  both channel keys are known.
- `config.py`: Warning for an unknown channel key now states that the bridge
  pair is inactive until resolved.

### ADDED
- `device_reader.py`: `cache_mtime(port)` helper.
- `README.md`: Section 1.1 "Scope: A Simple Channel Bridge" — channel messages
  only; DMs, adverts and routing are not bridged, with rationale; radio
  settings (frequency, bandwidth, SF, CR) are independent per side; companion
  firmware required.
- `docs/architecture.svg`: Architecture diagram, replacing the ASCII diagram
  in the README.

---

## [1.0.2] — 2026-04-14

### FIXED
- `config.py`: Removed stale YAML/pyyaml reference from module docstring; the
  configuration format has been JSON-only since 1.0.0.
- `__init__.py`: Corrected `__version__` from `1.0.1` to `1.0.2`; updated
  package description from "a configurable bridge channel" (singular, old
  single-pair design) to "one or more configurable bridge channels".
- `bridge_config.yaml`: Replaced with `bridge_config.json` — an example
  configuration file in the current JSON multi-pair format. The YAML file
  was a leftover from an earlier design and no longer matched the config
  schema or file format used by the daemon.
- `README.md`: Corrected five occurrences of `~/.meshcore-gui/cache/` to
  `~/.meschcore/cache/` (the actual path used by `device_reader.py`);
  corrected `BRIDGE.md` reference in the file structure section to `README.md`.

---

## [1.0.1] — 2026-04-13

### CHANGED
- `BridgePair` now stores bridges by channel **key** (channel name) instead of
  channel index. The fields `channel_a` / `channel_b` (integer index) are no
  longer persisted to `config.json`; they are runtime-only attributes populated
  at startup by `resolve_bridge_indices()`.
- `config.json` bridge entries now use `channel_a_key` / `channel_b_key`
  (string channel names) instead of `channel_a` / `channel_b` (integer indices).
- `BridgeConfigPanel._on_add_bridge()` sets `channel_a_key` / `channel_b_key`
  from the channel name lookup when the user adds a bridge via the GUI.

### ADDED
- `resolve_bridge_indices(bridges, channels_a, channels_b)` in `config.py`:
  resolves each bridge pair's runtime channel indices from the current device
  channel maps. If an index has drifted (channel re-ordered after firmware
  update), it is corrected in place and the caller is notified via the return
  value so the updated config can be written back to disk.
- Startup step in `__main__.py`: after resolving device ports, device channel
  maps are read and `resolve_bridge_indices()` is called. When indices are
  corrected, `config.json` is saved automatically before the engine starts.

### IMPACT
- **Breaking:** existing `config.json` files that use the old `channel_a` /
  `channel_b` integer format must be manually updated to use
  `channel_a_key` / `channel_b_key` string values, or be deleted so a new
  config can be created via the GUI.

### RATIONALE
- Channel indices can change after firmware updates or channel list edits.
  Storing the channel name (key) provides a stable reference that survives
  index drift. The startup resolution step ensures the engine always forwards
  on the correct channel regardless of index changes since the last save.

---

## [1.0.0] — 2026-04-11

### ADDED
- Initial release of MeshCore Bridge.
- Dual-device bridge daemon with multi-pair channel forwarding.
- Per-pair direction control (`a_to_b`, `b_to_a`, `both`).
- Loop prevention via message hash tracking and echo suppression.
- NiceGUI dashboard with status panel, bridge configurator and forwarded message log.
- JSON-based configuration (`~/.meshcore-gui/bridge/config.json`).
- Live bridge reconfiguration without daemon restart.
