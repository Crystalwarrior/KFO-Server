"""
Script runner: the shared automation engine for demo playback.

A `ScriptRunner` executes an ordered list of instructions -- `wait` delays,
AO packets, and OOC commands -- through the area's system executor client
(`Area.get_script_client`). Playback is non-recursive: each instruction is
processed in its own event-loop tick, so scripts are safe to chain (`/demo`
inside `/demo`) and can be arbitrarily long.

Instruction tuples: `("wait", seconds)`, `("packet", header, args)`,
`("command", cmd, arg)`.
"""

import asyncio
import logging

from collections import deque

from server import commands

logger = logging.getLogger("script")

# Server->client packet headers a demo is allowed to broadcast.
PACKET_HEADERS = ("MS", "CT", "MC", "BN", "HP", "RT", "JD", "GM", "ST")


def parse_demo_description(desc):
    """
    Parse an evidence description into script instructions.

    Lines are terminated by `%`. A line is either an AO packet (optionally
    multiline, closed with `%`), a `wait#<ms>` delay, or a command starting
    with `/`. Escaped characters (`<num>`, `<and>`, `<percent>`, `<dollar>`)
    are unescaped before splitting.
    """
    desc = desc.replace("<num>", "#").replace("<and>", "&").replace("<percent>", "%").replace("<dollar>", "$")
    instructions = []
    for line in desc.split("%"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("/"):
            parts = stripped.split(" ")
            cmd = parts.pop(0).lstrip("/").lower()
            arg = " ".join(parts)[:1024] if parts else ""
            instructions.append(("command", cmd, arg))
            continue
        fields = line.split("#")
        header = fields[0].strip()
        if header == "wait":
            try:
                seconds = float(fields[1]) / 1000 if len(fields) > 1 else 0
            except (ValueError, IndexError):
                seconds = 0
            instructions.append(("wait", seconds))
        elif header in PACKET_HEADERS:
            instructions.append(("packet", header, tuple(fields[1:])))
        # Unknown headers are ignored so stray text in a description can't
        # crash playback.
    return instructions


class ScriptRunner:
    """Runs a sequence of demo instructions through an executor client."""

    def __init__(self, area, executor):
        self.area = area
        self.executor = executor
        self.queue = deque()
        self.schedule = None
        self.running = False
        self.modified_packets = set()

    # --- Lifecycle ---

    def start(self, instructions):
        """Replace the current queue and begin (or restart) playback."""
        self._replace(instructions)
        if not self.queue:
            self.finish()
            return False
        self.running = True
        logger.info(
            "Demo started in area %s (%d instructions)", self.area.id, len(instructions)
        )
        self._schedule_next(0)
        return True

    def stop(self):
        """Stop playback and clean up."""
        logger.info("Demo stopped in area %s", self.area.id)
        self.finish()

    def finish(self):
        """Cancel any pending step, reset script state and modified packets."""
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        self.running = False
        self.queue.clear()
        self._reset_modified_packets()

    def _replace(self, instructions):
        """Swap in a new instruction queue (used by chained `/demo` calls)."""
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        self.queue = deque(instructions)

    def _schedule_next(self, delay):
        loop = asyncio.get_running_loop()
        if delay > 0:
            self.schedule = loop.call_later(delay, self.step)
        else:
            self.schedule = loop.call_later(0, self.step)

    # --- Stepping ---

    def step(self):
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        if not self.running or not self.queue:
            self.finish()
            return
        instruction = self.queue.popleft()
        kind = instruction[0]
        if kind == "wait":
            logger.info("Demo wait %s in area %s", instruction[1], self.area.id)
            self._schedule_next(instruction[1])
            return
        if kind == "packet":
            logger.info("Demo packet %s in area %s", instruction[1], self.area.id)
            self.send_packet(instruction[1], instruction[2])
        elif kind == "command":
            # If a chained /demo took over the queue, don't schedule another
            # step on top of the new script. If playback was stopped by an
            # error, don't keep stepping either.
            if self.run_command(instruction[1], instruction[2]):
                return
            if not self.running:
                return
        self._schedule_next(0)

    def send_packet(self, header, args):
        """Broadcast an AO packet, honouring the executor's broadcast list."""
        area_list = [self.area]
        if len(self.executor.broadcast_list) > 0:
            area_list = self.executor.broadcast_list
        for area in area_list:
            packet_args = list(args)
            if header == "MS":
                # If we're on narration pos, keep the same position as the
                # last IC message, falling back to the area's first pos-lock.
                if len(packet_args) > 5 and packet_args[5] == "":
                    if area.last_ic_message is not None:
                        packet_args[5] = area.last_ic_message[5]
                    elif len(self.area.pos_lock) > 0:
                        packet_args[5] = self.area.pos_lock[0]
            area.send_command(header, *packet_args)
            logger.info(
                "Demo broadcast %s to area %s (%d clients)",
                header,
                area.id,
                len(area.clients),
            )
        self.modified_packets.add(header)

    def run_command(self, cmd, arg):
        """
        Run a command through the executor.

        Returns True if the script was replaced by a chained `/demo` call.
        Broadcasts errors to the area and stops playback on failure.
        """
        resolved = commands.resolve_command(self.executor.server, cmd)
        if resolved is None:
            self.area.broadcast_ooc(f"[Demo] Invalid command: {cmd}. Use /help to find up-to-date commands.")
            self.finish()
            return False
        is_demo = resolved is getattr(commands, "ooc_cmd_demo", None)
        self.executor.execute(cmd, arg)
        for msg in self.executor.output:
            if msg.startswith("[ERROR]"):
                self.area.broadcast_ooc(f"[Demo] {msg}")
                self.finish()
                return False
        return is_demo

    # --- Cleanup ---

    def _reset_modified_packets(self):
        """Restore area state for packets the script actually modified."""
        area = self.area
        if area is None:
            return
        if "HP" in self.modified_packets:
            area.send_command("HP", 1, area.hp_def)
            area.send_command("HP", 2, area.hp_pro)
        if "BN" in self.modified_packets:
            area.send_command("BN", area.background)
        self.modified_packets.clear()
