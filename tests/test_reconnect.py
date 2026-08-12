"""Tests for graceful reconnect / ghost session resumption."""

import asyncio

from server.client_manager import ClientManager


class FakeTransport:
    """Minimal asyncio-transport stand-in that records written bytes."""

    def __init__(self, ipid="1"):
        self.written = b""
        self.closed = False
        self._ipid = ipid

    def get_extra_info(self, key):
        if key == "peername":
            return (self._ipid, 0)
        return None

    def write(self, data: bytes):
        self.written += data

    def close(self):
        self.closed = True


class FakeProtocol:
    def __init__(self, client):
        self.client = client


class FakeAreaManager:
    def __init__(self):
        self.owners = set()
        self.char_list = ["Char0"]
        self.id = 0
        self.name = "Hub"
        self.music_ref = ""
        self.music_list = []
        self.replace_music = False
        self.client_music = True


class FakeArea:
    """Minimal area stand-in used only for the ghost path checks."""

    def __init__(self, area_manager):
        self.clients = set()
        self.area_manager = area_manager
        self._owners = set()
        self.invite_list = set()
        self.music_ref = ""
        self.music_list = []
        self.music_autoplay = False
        self.music = ""
        self.music_looping = 0
        self.music_effects = 0
        self.ambience = ""
        self.background = ""
        self.overlay = ""
        self.hp_def = 0
        self.hp_pro = 0
        self.pos_lock = []
        self.dark = False

    def broadcast_ooc(self, msg, exclude_list=None):
        for c in list(self.clients):
            c.send_ooc(msg)

    def remove_client(self, client):
        self.clients.discard(client)


class FakeHubManager:
    def __init__(self):
        self.hubs = []

    def default_hub(self):
        hub = type("Hub", (), {})()
        hub.default_area = lambda: None
        return hub


class FakePlayerStateObserver:
    def unregister_client(self, client):
        pass

    def register_client(self, client):
        pass

    def notify_character_changed(self, client):
        pass


class FakeServer:
    """Minimal server façade exposing what Client/ClientManager touch."""

    def __init__(self):
        self.config = {
            "multiclient_limit": 16,
            "reconnect_grace_time": 5,
            "music_change_floodguard": {
                "interval_length": 1,
                "times_per_interval": 1,
                "mute_length": 1,
            },
            "wtce_floodguard": {
                "interval_length": 1,
                "times_per_interval": 1,
                "mute_length": 1,
            },
            "ooc_floodguard": {
                "interval_length": 1,
                "times_per_interval": 1,
                "mute_length": 1,
            },
            "packet_size": 1024,
            "hostname": "test",
            "playerlimit": 100,
        }
        self.music_list = []
        self.music_whitelist = []
        self.hub_manager = FakeHubManager()
        self.client_manager = ClientManager(self)
        self.player_state_observer = FakePlayerStateObserver()
        self.area = FakeArea(FakeAreaManager())
        # Wire the area into the server's hub list so ClientManager.remove_client
        # hub iteration is safe.
        hub = type("Hub", (), {})()
        hub.areas = [self.area]
        hub.clients = set()
        self.hub_manager.hubs = [hub]

    @property
    def player_count(self):
        return sum(1 for c in self.client_manager.clients if c.char_id != -1)

    def remove_client(self, client):
        client.area.remove_client(client)
        self.player_state_observer.unregister_client(client)
        self.client_manager.remove_client(client)


_ID_COUNTER = [0]


def _next_id():
    _ID_COUNTER[0] += 1
    return _ID_COUNTER[0]


def _joined_client(server, ipid=1, hdid="h1", user_id=None):
    """Create a fully-joined, connected client with a unique id."""
    cm = server.client_manager
    transport = FakeTransport(str(ipid))
    if user_id is None:
        user_id = _next_id()
    c = cm.Client(server, transport, user_id, ipid)
    c.hdid = hdid
    c.char_id = 0
    c.name = "Tester"
    c.joined = True
    c.is_checked = True
    c.area = server.area
    server.area.clients.add(c)
    cm.clients.add(c)
    return c


def _fresh_client(server, ipid=1, hdid="h1"):
    """Create a brand-new, not-yet-joined client (a reconnect stand-in)."""
    cm = server.client_manager
    transport = FakeTransport(str(ipid))
    c = cm.Client(server, transport, _next_id(), ipid)
    c.hdid = hdid
    c.joined = False
    c.area = server.area
    server.area.clients.add(c)
    cm.clients.add(c)
    return c



def test_joined_client_becomes_ghost():
    """A disconnected joined client should ghost and suppress outgoing writes."""

    async def _run():
        server = FakeServer()
        cm = server.client_manager
        c = _joined_client(server, ipid=1, hdid="h1")

        c.mark_ghost(grace_time=0.1)

        assert c.is_ghost
        assert c.joined

        # Writes are suppressed while ghosted.
        c.send_command("KA", "hello")
        assert c.transport.written == b""

        c._finalize_ghost()
        assert not c.is_ghost
        assert c not in server.area.clients
        assert c not in cm.clients

    asyncio.run(_run())


def test_ghost_without_character_is_removed_immediately():
    """Clients that never chose a character aren't kept as ghosts."""

    async def _run():
        server = FakeServer()
        c = _joined_client(server, ipid=1, hdid="h1")
        c.char_id = None
        c.joined = False

        c.mark_ghost(grace_time=5)
        assert not c.is_ghost
        assert c not in server.client_manager.clients

    asyncio.run(_run())


def test_find_ghost_matches_ipid_and_hdid():
    server = FakeServer()
    cm = server.client_manager

    ghost = _joined_client(server, ipid=1, hdid="h1")
    _joined_client(server, ipid=2, hdid="h2")
    ghost.is_ghost = True

    by_id = _joined_client(server, ipid=1, hdid="h1")
    assert cm.find_ghost(by_id) is ghost

    wrong_hdid = _joined_client(server, ipid=1, hdid="h9")
    assert cm.find_ghost(wrong_hdid) is None


def test_try_resume_discards_fresh_client_and_uses_ghost():
    async def _run():
        server = FakeServer()
        cm = server.client_manager

        ghost = _joined_client(server, ipid=1, hdid="h1")
        ghost.is_ghost = True

        # A brand-new connection with the same identity, not yet joined.
        fresh = _fresh_client(server, ipid=1, hdid="h1")

        protocol = FakeProtocol(fresh)

        # Isolate the state re-push (real resync needs full area methods).
        original_resync = ghost.resync_session
        ghost.resync_session = lambda: None
        try:
            resumed = cm.try_resume(fresh, protocol, "h1")
        finally:
            ghost.resync_session = original_resync

        assert resumed is ghost
        assert protocol.client is ghost
        assert not ghost.is_ghost
        assert ghost.transport is fresh.transport
        assert ghost in cm.clients
        assert fresh not in cm.clients

    asyncio.run(_run())


def test_disconnect_then_reconnect_resumes_same_session():
    async def _run():
        server = FakeServer()
        cm = server.client_manager

        # Original client joins and becomes a ghost on disconnect.
        original = _joined_client(server, ipid=1, hdid="h1")
        original.mark_ghost(grace_time=5)
        assert original.is_ghost

        # The same client reconnects with a fresh connection.
        fresh = _fresh_client(server, ipid=1, hdid="h1")

        protocol = FakeProtocol(fresh)
        original.resync_session = lambda: None
        resumed = cm.try_resume(fresh, protocol, "h1")

        assert resumed is original
        assert not original.is_ghost
        assert protocol.client is original
        assert original.transport is fresh.transport
        assert fresh not in cm.clients
        assert original in cm.clients

    asyncio.run(_run())
