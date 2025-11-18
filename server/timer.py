import asyncio
import datetime
import logging
from typing import Any, List, Optional

import arrow

from server import commands
from server.client import Client
from server.exceptions import AreaError, ArgumentError, ClientError, ServerError

logger = logging.getLogger("areatimer")


class Timer:
    """Represents a single instance of a timer in the area."""

    def __init__(
        self,
        _id: int,
        set_: bool = False,
        started: bool = False,
        static: Optional[datetime.timedelta] = None,
        target: Optional[arrow.Arrow] = None,
        area: Optional[Any] = None,
        caller: Optional[Client] = None,
    ):
        self.id: int = _id
        self.set: bool = set_
        self.started: bool = started
        self.static: Optional[datetime.timedelta] = static
        self.target: Optional["arrow.Arrow"] = target
        self.area: Optional["Area"] = area
        self.caller: Optional["Client"] = caller
        self.schedule: Optional[asyncio.TimerHandle] = None
        self.commands: List[str] = []
        self.format: str = "hh:mm:ss.zzz"
        self.interval: int = 16

    def timer_expired(self) -> None:
        if self.schedule:
            self.schedule.cancel()
        # Either the area or the hub was destroyed at some point
        if self.area is None or self is None:
            return

        self.static = datetime.timedelta(0)
        self.started = False

        self.area.broadcast_ooc(f"Timer {self.id + 1} has expired.")
        self.call_commands()

    def call_commands(self) -> None:
        if self.caller is None:
            return
        if self.area is None or self is None:
            return
        if self.caller not in self.area.owners:
            return
        # We clear out the commands as we call them in order one by one
        while len(self.commands) > 0:
            # Take the first command in the list and run it
            cmd = self.commands.pop(0)
            args = cmd.split(" ")
            cmd = args.pop(0).lower()
            arg = ""
            if len(args) > 0:
                arg = " ".join(args)[:1024]
            try:
                old_area = self.caller.area
                old_hub = self.caller.area.area_manager
                self.caller.area = self.area
                commands.call(self.caller, cmd, arg)
                if old_area and old_area in old_hub.areas:
                    self.caller.area = old_area
            except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                self.caller.send_ooc(f"[Timer {self.id}] {ex}")
                # Command execution critically failed somewhere. Clear out all commands so the timer doesn't screw with us.
                self.commands.clear()
                # Even tho self.commands.clear() is going to break us out of the while loop, manually return anyway just to be safe.
                return
            except Exception as ex:
                self.caller.send_ooc(
                    f"[Timer {self.id}] An internal error occurred: {ex}. Please inform the staff of the server about the issue."
                )
                logger.error("Exception while running a command")
                # Command execution critically failed somewhere. Clear out all commands so the timer doesn't screw with us.
                self.commands.clear()
                # Even tho self.commands.clear() is going to break us out of the while loop, manually return anyway just to be safe.
                return
