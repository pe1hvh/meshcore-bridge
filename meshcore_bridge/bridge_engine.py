"""
Core bridge logic: message monitoring, forwarding and loop prevention.

BridgeEngine polls two SharedData stores and forwards messages across
all configured BridgePair instances. Each pair has its own direction
setting (a_to_b / b_to_a / both) and enabled flag.

Loop prevention is achieved via a bounded set of forwarded message
hashes and by filtering outbound (direction='out') messages.

Thread safety: all SharedData access goes through the existing lock
mechanism in SharedData. BridgeEngine itself is called from a single
polling thread (started in __main__).

                 Author: PE1HVH
                Version: 2.0.0
SPDX-License-Identifier: MIT
              Copyright: (c) 2026 PE1HVH
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from meshcore_gui.core.models import Message
from meshcore_gui.core.shared_data import SharedData

from meshcore_bridge.config import BridgeConfig, BridgePair


@dataclass
class ForwardedEntry:
    """Record of a forwarded message for the bridge log."""

    time: str
    direction: str          # "A→B" or "B→A"
    sender: str
    text: str
    channel: Optional[int]


class BridgeEngine:
    """Core bridge logic: poll, filter, forward and deduplicate.

    Monitors two SharedData instances for new incoming messages across
    all configured and enabled BridgePair instances. Forwards matching
    messages to the opposite device via put_command().

    Attributes:
        stats: Runtime statistics dict exposed to the GUI dashboard.
    """

    def __init__(
        self,
        shared_a: SharedData,
        shared_b: SharedData,
        config: BridgeConfig,
    ) -> None:
        self._a = shared_a
        self._b = shared_b
        self._cfg = config

        # Active bridge pairs — live-reloadable via reload_bridges()
        self._bridges: List[BridgePair] = list(config.bridges)

        # Loop prevention: bounded ordered dict of forwarded hashes
        self._forwarded_hashes: OrderedDict = OrderedDict()
        self._max_cache = config.max_forwarded_cache

        # Tracking last seen message count per side
        self._last_count_a: int = 0
        self._last_count_b: int = 0

        # Forwarded message log (for dashboard)
        self._log: List[ForwardedEntry] = []
        self._max_log: int = 200

        # Runtime statistics
        self.stats = {
            "forwarded_a_to_b": 0,
            "forwarded_b_to_a": 0,
            "duplicates_blocked": 0,
            "last_forward_time": "",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": 0,
        }
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload_bridges(self, bridges: List[BridgePair]) -> None:
        """Replace the active bridge list without restarting the engine.

        Called by the GUI configuration panel after the user saves a
        new bridge configuration.

        Args:
            bridges: New list of BridgePair instances.
        """
        self._bridges = list(bridges)

    def poll_and_forward(self) -> int:
        """Check both stores for new bridge-channel messages and forward.

        Takes a single snapshot of each SharedData per poll cycle to
        avoid repeated locking. Iterates over all enabled bridge pairs.

        Returns:
            Number of messages forwarded in this poll cycle.
        """
        self.stats["uptime_seconds"] = int(time.time() - self._start_time)

        # Snapshot both sides once per poll cycle
        snap_a = self._a.get_snapshot()
        snap_b = self._b.get_snapshot()
        msgs_a = snap_a["messages"]
        msgs_b = snap_b["messages"]

        # Handle list shrinkage after reconnect / reload
        if len(msgs_a) < self._last_count_a:
            self._last_count_a = 0
        if len(msgs_b) < self._last_count_b:
            self._last_count_b = 0

        new_msgs_a = msgs_a[self._last_count_a:]
        new_msgs_b = msgs_b[self._last_count_b:]

        self._last_count_a = len(msgs_a)
        self._last_count_b = len(msgs_b)

        active_bridges = [b for b in self._bridges if b.enabled]
        count = 0

        for bridge in active_bridges:
            # A → B
            if bridge.direction in ("a_to_b", "both"):
                for msg in new_msgs_a:
                    if self._should_forward(msg, bridge.channel_a):
                        self._forward(msg, self._b, bridge.channel_b, "A→B")
                        self.stats["forwarded_a_to_b"] += 1
                        count += 1

            # B → A
            if bridge.direction in ("b_to_a", "both"):
                for msg in new_msgs_b:
                    if self._should_forward(msg, bridge.channel_b):
                        self._forward(msg, self._a, bridge.channel_a, "B→A")
                        self.stats["forwarded_b_to_a"] += 1
                        count += 1

        return count

    def get_log(self) -> List[ForwardedEntry]:
        """Return a copy of the forwarded message log (newest first)."""
        return list(reversed(self._log))

    def get_total_forwarded(self) -> int:
        """Total number of messages forwarded since start."""
        return (
            self.stats["forwarded_a_to_b"]
            + self.stats["forwarded_b_to_a"]
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _should_forward(self, msg: Message, expected_channel: int) -> bool:
        """Determine whether a message should be forwarded.

        Filtering rules:
        1. Channel must match the bridge channel for this pair.
        2. Outbound messages (direction='out') are never forwarded
           — they are our own transmissions (including previous forwards).
        3. Messages whose hash is already in the forwarded set are
           duplicates (loop prevention).

        Args:
            msg:              Message to evaluate.
            expected_channel: Bridge channel index to match.

        Returns:
            True if the message should be forwarded.
        """
        # Rule 1: channel filter
        if msg.channel != expected_channel:
            return False

        # Rule 2: never forward our own transmissions
        if msg.direction == "out":
            return False

        # Rule 3: loop prevention via hash set
        msg_hash = self._compute_hash(msg)
        if msg_hash in self._forwarded_hashes:
            self.stats["duplicates_blocked"] += 1
            return False

        return True

    def _forward(
        self,
        msg: Message,
        target: SharedData,
        target_ch: int,
        direction_label: str,
    ) -> None:
        """Forward a message to the target SharedData via put_command().

        Args:
            msg:             Message to forward.
            target:          Target SharedData instance.
            target_ch:       Channel index on the target device.
            direction_label: "A→B" or "B→A" for logging.
        """
        msg_hash = self._compute_hash(msg)

        # Register hash for loop prevention
        self._forwarded_hashes[msg_hash] = True
        if len(self._forwarded_hashes) > self._max_cache:
            self._forwarded_hashes.popitem(last=False)

        # Also register the echo hash so the forwarded message isn't
        # re-forwarded when it appears on the target device.
        forward_text = self._build_forward_text(msg)
        echo_hash = self._text_hash(forward_text)
        self._forwarded_hashes[echo_hash] = True
        if len(self._forwarded_hashes) > self._max_cache:
            self._forwarded_hashes.popitem(last=False)

        # Inject send command into the target's command queue
        target.put_command({
            "action": "send_message",
            "channel": target_ch,
            "text": forward_text,
            "_bot": True,
        })

        now = datetime.now().strftime("%H:%M:%S")
        self.stats["last_forward_time"] = now

        entry = ForwardedEntry(
            time=now,
            direction=direction_label,
            sender=msg.sender,
            text=msg.text,
            channel=msg.channel,
        )
        self._log.append(entry)
        if len(self._log) > self._max_log:
            self._log.pop(0)

    def _build_forward_text(self, msg: Message) -> str:
        """Build the text to transmit on the target device.

        When forward_prefix is enabled, the original sender name is
        prepended so recipients can identify the origin.

        Args:
            msg: Original message.

        Returns:
            Text string to send.
        """
        if self._cfg.forward_prefix:
            return f"[{msg.sender}] {msg.text}"
        return msg.text

    @staticmethod
    def _compute_hash(msg: Message) -> str:
        """Compute a deduplication hash for a message.

        Uses the message_hash field when available (deterministic
        packet ID from MeshCore firmware). Falls back to a SHA-256
        digest of channel + sender + text.

        Args:
            msg: Message to hash.

        Returns:
            Hash string.
        """
        if msg.message_hash:
            return f"mh:{msg.message_hash}"
        raw = f"{msg.channel}:{msg.sender}:{msg.text}"
        return f"ct:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    @staticmethod
    def _text_hash(text: str) -> str:
        """Hash a plain text string for echo suppression.

        Args:
            text: Text to hash.

        Returns:
            Hash string.
        """
        return f"tx:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
