# Changelog

All notable changes to MeshCore Bridge are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

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
