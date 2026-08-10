"""
Unified countdown timer used by both areas and hubs.

Timer 0 (hub-wide) lives on an `AreaManager`; timers 1-20 are per-area. On
expiry the queued commands run through the area's system executor client
(see `Area.get_script_client`) so automation no longer depends on a real
player staying online or keeping CM/GM status.
"""

import asyncio
import datetime
import logging

logger = logging.getLogger("timer")


class Timer:
    """Represents a single countdown timer with attached expiry commands."""

    def __init__(self, _id, area=None, hub=None):
        self.id = _id
        self.area = area
        self.hub = hub
        self.set = False
        self.started = False
        self.static = None
        self.target = None
        self.schedule = None
        self.commands = []
        self.format = "hh:mm:ss.zzz"
        self.interval = 16

    @property
    def scope(self):
        """The hub or area this timer is bound to."""
        return self.hub if self.hub is not None else self.area

    @property
    def label(self):
        """User-facing timer ID string ('0' for the hub timer, else 1-20)."""
        return "0" if self.hub is not None else str(self.id + 1)

    def timer_expired(self):
        if self.schedule:
            self.schedule.cancel()
            self.schedule = None
        scope = self.scope
        # The area or hub this timer belonged to was destroyed at some point
        if scope is None:
            return

        self.static = datetime.timedelta(0)
        self.started = False

        scope.broadcast_ooc(f"Timer {self.label} has expired.")
        self.call_commands()

    def call_commands(self):
        if self.area is None:
            return
        executor = self.area.get_script_client()
        # We clear out the commands as we call them in order one by one
        while len(self.commands) > 0:
            # Take the first command in the list and run it
            cmd_string = self.commands.pop(0)
            parts = cmd_string.split(" ")
            cmd = parts.pop(0).lower()
            arg = ""
            if len(parts) > 0:
                arg = " ".join(parts)[:1024]
            executor.execute(cmd, arg)
            errors = [msg for msg in executor.output if msg.startswith("[ERROR]")]
            if errors:
                for msg in errors:
                    self.area.broadcast_ooc(f"[Timer {self.label}] {msg}")
                # Command execution critically failed somewhere. Clear out all
                # commands so the timer doesn't keep fighting us.
                self.commands.clear()
                return


def start_schedule(timer):
    """
    (Re)arm the timer's expiry callback if it's currently running.
    """
    if timer.schedule:
        timer.schedule.cancel()
    if timer.started:
        timer.schedule = asyncio.get_running_loop().call_later(int(timer.static.total_seconds()), timer.timer_expired)
