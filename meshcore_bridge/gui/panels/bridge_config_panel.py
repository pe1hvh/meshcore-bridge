"""
Bridge configuration panel — 3-panel channel bridge configurator.

Displays device A channels (left panel), device B channels (middle panel)
and the current bridge list (right panel). Users can add bridges with a
configurable direction, toggle individual bridges on/off, remove bridges
and save the configuration to disk — all without restarting the daemon.

Layout mirrors the conventions of FilterPanel (checkbox style) and
ActionsPanel (button style) from the existing meshcore_gui codebase.

                 Author: PE1HVH
                Version: 1.0.1
SPDX-License-Identifier: MIT
              Copyright: (c) 2026 PE1HVH
"""

from pathlib import Path
from typing import Callable, List, Optional

from nicegui import ui

from meshcore_bridge.config import BridgeConfig, BridgePair, DEFAULT_CONFIG_PATH
from meshcore_bridge.device_reader import DeviceChannels


_DIRECTION_LABELS = {
    "a_to_b": "A → B",
    "b_to_a": "B → A",
    "both":   "A ↔ B",
}

_DIRECTION_OPTIONS = [
    {"label": "A ↔ B  (bidirectional)", "value": "both"},
    {"label": "A → B  (one-way)", "value": "a_to_b"},
    {"label": "B → A  (one-way)", "value": "b_to_a"},
]


class BridgeConfigPanel:
    """Three-panel bridge configurator.

    Left  — Device A channel list (read from cache)
    Middle — Device B channel list (read from cache)
    Right — Active bridge list with add / remove / direction / save

    Args:
        config:       Active BridgeConfig instance (mutated on save).
        channels_a:   Channel info for device A from DeviceReader.
        channels_b:   Channel info for device B from DeviceReader.
        on_save:      Callback invoked with the updated bridge list after
                      a successful save. Used to hot-reload the engine.
        config_path:  Path where config.json is written.
    """

    def __init__(
        self,
        config: BridgeConfig,
        channels_a: Optional[DeviceChannels],
        channels_b: Optional[DeviceChannels],
        on_save: Callable[[List[BridgePair]], None],
        config_path: Path = DEFAULT_CONFIG_PATH,
    ) -> None:
        self._cfg = config
        self._channels_a = channels_a
        self._channels_b = channels_b
        self._on_save = on_save
        self._config_path = config_path

        # Working copy of the bridge list (mutable; committed on save)
        self._bridges: List[BridgePair] = list(config.bridges)

        # UI element references
        self._bridge_list_container: Optional[ui.column] = None
        self._status_label: Optional[ui.label] = None

        # Form state — current selections in the "Add bridge" sub-form
        self._sel_channel_a: int = self._first_channel(channels_a)
        self._sel_channel_b: int = self._first_channel(channels_b)
        self._sel_direction: str = "both"

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _first_channel(dev: Optional[DeviceChannels]) -> int:
        """Return the lowest channel index available, or 0."""
        if dev and dev.channels:
            return min(dev.channels.keys())
        return 0

    @staticmethod
    def _channel_options(dev: Optional[DeviceChannels]) -> List[dict]:
        """Build select options from a DeviceChannels object."""
        if not dev or not dev.channels:
            return [{"label": "No channels found", "value": 0}]
        return [
            {"label": f"[{idx}]  {name}", "value": idx}
            for idx, name in sorted(dev.channels.items())
        ]

    @staticmethod
    def _channel_label(dev: Optional[DeviceChannels], idx: int) -> str:
        """Human-readable channel label, e.g. '[0] Public'."""
        if dev and idx in dev.channels:
            return f"[{idx}] {dev.channels[idx]}"
        return f"[{idx}]"

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Build the complete 3-panel bridge configuration card."""
        with ui.card().classes("w-full"):
            # Card header
            with ui.row().classes("items-center gap-2 mb-3"):
                ui.icon("cable", color="primary").classes("text-lg")
                ui.label("Bridge Configuration").classes(
                    "text-sm font-bold"
                ).style("font-family: 'JetBrains Mono', monospace")

            with ui.row().classes("w-full gap-4 items-start"):

                # ── Left panel: Device A channels ────────────────────
                with ui.column().classes("flex-1 min-w-[180px] gap-1"):
                    self._render_channel_list(
                        heading=f"Device A — {self._cfg.device_a.port}",
                        device=self._channels_a,
                    )

                # ── Middle panel: Device B channels ──────────────────
                with ui.column().classes("flex-1 min-w-[180px] gap-1"):
                    self._render_channel_list(
                        heading=f"Device B — {self._cfg.device_b.port}",
                        device=self._channels_b,
                    )

                # ── Right panel: Bridge list + add form ───────────────
                with ui.column().classes("flex-1 min-w-[280px] gap-2"):

                    ui.label("Bridges").classes(
                        "text-xs font-bold opacity-60"
                    ).style("font-family: 'JetBrains Mono', monospace")

                    self._bridge_list_container = ui.column().classes("w-full gap-1")
                    self._render_bridge_list()

                    ui.separator().classes("my-1")

                    # ── Add bridge sub-form ───────────────────────────
                    ui.label("Add bridge").classes(
                        "text-xs font-bold opacity-60"
                    ).style("font-family: 'JetBrains Mono', monospace")

                    # Channel A selector
                    sel_a = ui.select(
                        options=self._channel_options(self._channels_a),
                        value=self._sel_channel_a,
                        label="Channel A",
                    ).classes("w-full text-xs")
                    sel_a.on(
                        "update:model-value",
                        lambda e: self._set_sel_a(e.args),
                    )

                    # Direction selector
                    sel_dir = ui.select(
                        options=_DIRECTION_OPTIONS,
                        value=self._sel_direction,
                        label="Direction",
                    ).classes("w-full text-xs")
                    sel_dir.on(
                        "update:model-value",
                        lambda e: self._set_sel_dir(e.args),
                    )

                    # Channel B selector
                    sel_b = ui.select(
                        options=self._channel_options(self._channels_b),
                        value=self._sel_channel_b,
                        label="Channel B",
                    ).classes("w-full text-xs")
                    sel_b.on(
                        "update:model-value",
                        lambda e: self._set_sel_b(e.args),
                    )

                    ui.button(
                        "Add bridge",
                        icon="add",
                        on_click=self._on_add_bridge,
                    ).classes("w-full text-xs").props("color=primary size=sm")

                    ui.separator().classes("my-1")

                    ui.button(
                        "Save configuration",
                        icon="save",
                        on_click=self._on_save_config,
                    ).classes("w-full text-xs").props("color=positive size=sm")

                    self._status_label = ui.label("").classes(
                        "text-xs opacity-70 mt-1"
                    ).style("font-family: 'JetBrains Mono', monospace")

    # ------------------------------------------------------------------
    # Sub-renderers
    # ------------------------------------------------------------------

    def _render_channel_list(
        self,
        heading: str,
        device: Optional[DeviceChannels],
    ) -> None:
        """Render the channel list for one device side."""
        ui.label(heading).classes(
            "text-xs font-bold opacity-60"
        ).style("font-family: 'JetBrains Mono', monospace")

        if not device:
            ui.label("Cache file not found").classes(
                "text-xs opacity-40 italic"
            )
            return

        if device.radio_freq:
            ui.label(
                f"{device.device_name} · {device.radio_freq:.3f} MHz"
            ).classes("text-xs opacity-50").style(
                "font-family: 'JetBrains Mono', monospace"
            )

        if not device.channels:
            ui.label("No channels in cache").classes("text-xs opacity-40 italic")
            return

        for idx, name in sorted(device.channels.items()):
            with ui.row().classes("items-center gap-1 py-0.5"):
                ui.icon("router", size="xs").classes("opacity-30 shrink-0")
                ui.label(f"[{idx}]").classes(
                    "text-xs opacity-50 w-8 shrink-0"
                ).style("font-family: 'JetBrains Mono', monospace")
                ui.label(name).classes("text-xs").style(
                    "font-family: 'JetBrains Mono', monospace"
                )

    def _render_bridge_list(self) -> None:
        """Repopulate the bridge list container from self._bridges."""
        if not self._bridge_list_container:
            return
        self._bridge_list_container.clear()
        with self._bridge_list_container:
            if not self._bridges:
                ui.label("No bridges configured").classes(
                    "text-xs opacity-40 italic py-1"
                )
                return
            for i, bridge in enumerate(self._bridges):
                self._render_bridge_row(i, bridge)

    def _render_bridge_row(self, idx: int, bridge: BridgePair) -> None:
        """Render one bridge row: enabled toggle + labels + remove button."""
        ch_a = self._channel_label(self._channels_a, bridge.channel_a)
        ch_b = self._channel_label(self._channels_b, bridge.channel_b)
        dir_lbl = _DIRECTION_LABELS.get(bridge.direction, bridge.direction)

        with ui.row().classes("w-full items-center gap-1 py-0.5"):
            # Enabled toggle — style matches BOT-checkbox in FilterPanel
            chk = ui.checkbox(value=bridge.enabled).props("dense size=xs")
            chk.tooltip("Enable / disable this bridge")
            chk.on(
                "update:model-value",
                lambda e, i=idx: self._toggle_bridge(i, e.args),
            )

            ui.label(ch_a).classes(
                "text-xs opacity-70 truncate"
            ).style(
                "font-family: 'JetBrains Mono', monospace; max-width:80px"
            )
            ui.label(dir_lbl).classes(
                "text-xs font-bold"
            ).style("font-family: 'JetBrains Mono', monospace")
            ui.label(ch_b).classes(
                "text-xs opacity-70 truncate"
            ).style(
                "font-family: 'JetBrains Mono', monospace; max-width:80px"
            )

            ui.space()

            # Remove button — style matches ActionsPanel buttons
            ui.button(
                icon="delete",
                on_click=lambda _, i=idx: self._on_remove_bridge(i),
            ).props("flat round dense size=xs color=negative").tooltip(
                "Remove bridge"
            )

    # ------------------------------------------------------------------
    # Form state
    # ------------------------------------------------------------------

    def _set_sel_a(self, value) -> None:
        try:
            self._sel_channel_a = int(value)
        except (TypeError, ValueError):
            pass

    def _set_sel_b(self, value) -> None:
        try:
            self._sel_channel_b = int(value)
        except (TypeError, ValueError):
            pass

    def _set_sel_dir(self, value) -> None:
        if value in ("a_to_b", "b_to_a", "both"):
            self._sel_direction = value

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _toggle_bridge(self, idx: int, enabled: bool) -> None:
        """Toggle the enabled flag of bridge at index idx."""
        if 0 <= idx < len(self._bridges):
            self._bridges[idx].enabled = bool(enabled)

    def _on_add_bridge(self) -> None:
        """Append a new BridgePair from the current form selections.

        Stores the channel name as the stable key and sets the runtime
        index immediately so the engine can forward without a restart.
        """
        key_a = ""
        key_b = ""
        if self._channels_a and self._sel_channel_a in self._channels_a.channels:
            key_a = self._channels_a.channels[self._sel_channel_a]
        if self._channels_b and self._sel_channel_b in self._channels_b.channels:
            key_b = self._channels_b.channels[self._sel_channel_b]

        pair = BridgePair(
            channel_a_key=key_a,
            channel_b_key=key_b,
            direction=self._sel_direction,
            enabled=True,
        )
        # Populate runtime indices immediately (no restart needed)
        pair.channel_a = self._sel_channel_a
        pair.channel_b = self._sel_channel_b

        self._bridges.append(pair)
        self._render_bridge_list()
        self._set_status("Bridge added — click Save to apply.")

    def _on_remove_bridge(self, idx: int) -> None:
        """Remove the bridge at index idx."""
        if 0 <= idx < len(self._bridges):
            self._bridges.pop(idx)
            self._render_bridge_list()
            self._set_status("Bridge removed — click Save to apply.")

    def _on_save_config(self) -> None:
        """Write bridges to config.json and hot-reload the engine."""
        try:
            self._cfg.bridges = list(self._bridges)
            self._cfg.to_json(self._config_path)
            self._on_save(list(self._bridges))
            self._set_status(f"Saved → {self._config_path}")
        except OSError as exc:
            self._set_status(f"Save failed: {exc}")

    def _set_status(self, msg: str) -> None:
        """Update the status label below the Save button."""
        if self._status_label:
            self._status_label.set_text(msg)
