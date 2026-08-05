import asyncio

import websockets

from server.constants import decode_ao_packet


class MockClient:
    """Async WebSocket client that speaks the AO protocol for testing.

    Connects to a real KFOServer over WebSocket, performs the handshake,
    and provides high-level helpers for every protocol command.

    Usage::

        async with MockClient(host, port) as client:
            await client.handshake()
            await client.select_character(0)
            await client.send_ic_message("Hello!")
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._ws = None
        self._buffer = ""

        # State tracked across the session
        self.player_id = None
        self.char_id = None
        self.char_list = []
        self.features = []

    # --- Connection lifecycle ---

    async def connect(self):
        """Connect to the server and wait for the decryptor handshake packet.

        The server may send other packets (GM, MC, etc.) before decryptor
        due to area.new_client() running first in the WS handler.
        """
        uri = f"ws://{self.host}:{self.port}"
        self._ws = await websockets.connect(uri)
        return await self.recv_until("decryptor")

    async def close(self):
        """Close the connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # --- Low-level I/O ---

    async def send(self, command: str, *args):
        """Encode and send an AO protocol packet over WebSocket.

        Joins *command* and *args* with ``#`` and appends ``#%``.
        """
        parts = [command] + [str(a) for a in args]
        msg = "#".join(parts) + "#%"
        await self._ws.send(msg)

    async def recv(self, timeout: float = 2.0) -> tuple[str, list[str]]:
        """Read and return the next complete packet as ``(command, [args])``."""
        while "#%" not in self._buffer:
            data = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            self._buffer += data

        packet, self._buffer = self._buffer.split("#%", 1)
        parts = packet.split("#")
        cmd = parts[0]
        args = [decode_ao_packet(a) for a in parts[1:]]
        return cmd, args

    async def recv_until(self, target_cmd: str, timeout: float = 2.0) -> tuple[str, list[str]]:
        """Read packets until *target_cmd* is seen, then return it."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {target_cmd}")
            cmd, args = await self.recv(timeout=remaining)
            if cmd == target_cmd:
                return cmd, args

    async def recv_all(self, timeout: float = 0.2) -> list[tuple[str, list[str]]]:
        """Drain all available packets within *timeout*."""
        packets = []
        try:
            while True:
                packets.append(await self.recv(timeout=timeout))
        except (TimeoutError, asyncio.TimeoutError):
            pass
        return packets

    async def recv_ooc(self, timeout: float = 2.0) -> str:
        """Read until a CT (OOC) packet arrives and return the message text."""
        _, args = await self.recv_until("CT", timeout=timeout)
        # CT#<server_name>#<message>#<is_server>#%
        return args[1] if len(args) > 1 else ""

    # --- Handshake (full join sequence) ---

    async def handshake(self, hdid="test-hdid", software="AO2", version="2.10.0"):
        """Perform the full AO join sequence.

        Sends: HI -> ID -> askchaa -> RC -> RM -> RD

        Uses ``recv_until`` for each expected response so optional
        packets (ASS, GM, MC, etc.) are silently consumed.

        Returns a summary dict with player_id, features, and char_list.
        """
        # HI -> server responds with ID (+ PN)
        await self.send("HI", hdid)
        _, args = await self.recv_until("ID")
        self.player_id = int(args[0])

        # ID -> server responds with FL (+ optionally ASS)
        await self.send("ID", software, version)
        _, args = await self.recv_until("FL")
        self.features = args

        # askchaa -> SI
        await self.send("askchaa")
        await self.recv_until("SI")

        # RC -> SC (character list)
        await self.send("RC")
        _, args = await self.recv_until("SC")
        self.char_list = args

        # RM -> SM (music/area list)
        await self.send("RM")
        await self.recv_until("SM")

        # RD -> many packets... -> DONE, then MOTD/hub info follow
        await self.send("RD")
        await self.recv_until("DONE")
        # Drain remaining post-DONE packets (MOTD, hub info, etc.)
        await self.recv_all(timeout=0.1)

        return {
            "player_id": self.player_id,
            "features": self.features,
            "char_list": self.char_list,
        }

    # --- Character selection ---

    async def select_character(self, char_id: int):
        """Select a character by ID. Sends CC, receives PV."""
        await self.send("CC", 0, char_id, "test-hdid")
        cmd, args = await self.recv_until("PV")
        self.char_id = char_id
        return cmd, args

    # --- IC message (MS packet) ---

    async def send_ic_message(self, text: str, **kwargs):
        """Send an IC message (v2.8 MS packet, 26 fields) with sensible defaults.

        Keyword arguments override any field. ``folder`` defaults to the
        selected character name, ``cid`` to ``self.char_id``.
        """
        folder = kwargs.get("folder") or (
            self.char_list[self.char_id] if self.char_id is not None and self.char_id >= 0 else ""
        )
        cid = kwargs.get("cid", self.char_id if self.char_id is not None else 0)

        fields = [
            kwargs.get("msg_type", "1"),
            kwargs.get("pre", ""),
            folder,
            kwargs.get("anim", "normal"),
            text,
            kwargs.get("pos", "def"),
            kwargs.get("sfx", "1"),
            str(kwargs.get("emote_mod", 0)),
            str(cid),
            str(kwargs.get("sfx_delay", 0)),
            str(kwargs.get("button", 0)),
            str(kwargs.get("evidence", 0)),
            str(kwargs.get("flip", 0)),
            str(kwargs.get("ding", 0)),
            str(kwargs.get("color", 0)),
            kwargs.get("showname", ""),
            str(kwargs.get("charid_pair", "-1")),
            str(kwargs.get("offset_pair", "0")),
            str(kwargs.get("nonint_pre", 0)),
            kwargs.get("sfx_looping", "0"),
            str(kwargs.get("screenshake", 0)),
            kwargs.get("frames_shake", "0"),
            kwargs.get("frames_realization", "0"),
            kwargs.get("frames_sfx", "0"),
            str(kwargs.get("additive", 0)),
            kwargs.get("effect", "0"),
        ]
        await self.send("MS", *fields)

    # --- OOC message ---

    async def send_ooc_message(self, message: str, name: str = "TestUser"):
        """Send an OOC message (CT packet)."""
        await self.send("CT", name, message)

    # --- Music ---

    async def play_music(self, song: str, *, cid=None, showname="", effects=0, loop=True):
        """Play a music track (MC packet)."""
        await self.send("MC", song, cid if cid is not None else (self.char_id or 0), showname, effects, int(loop))

    # --- Judge buttons ---

    async def send_wtce(self, sign: str = "testimony1"):
        """Send a WT/CE animation (RT packet)."""
        await self.send("RT", sign)

    # --- Penalty bars ---

    async def set_penalty(self, bar_type: int, value: int):
        """Set a penalty bar (HP packet)."""
        await self.send("HP", bar_type, value)

    # --- Evidence ---

    async def add_evidence(self, name: str, desc: str, image: str):
        """Add a piece of evidence (PE packet)."""
        await self.send("PE", name, desc, image)

    async def delete_evidence(self, evi_id: int):
        """Delete a piece of evidence (DE packet)."""
        await self.send("DE", evi_id)

    async def edit_evidence(self, evi_id: int, name: str, desc: str, image: str):
        """Edit a piece of evidence (EE packet)."""
        await self.send("EE", evi_id, name, desc, image)

    # --- Keepalive ---

    async def keepalive(self):
        """Send a keepalive (CH packet)."""
        await self.send("CH")

    # --- Mod call ---

    async def mod_call(self, reason: str = ""):
        """Send a mod call (ZZ packet)."""
        await self.send("ZZ", reason)
