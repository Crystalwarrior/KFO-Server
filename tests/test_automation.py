"""Tests for the automation overhaul (triggers, timers, demo playback).

The roleplay automation systems all funnel through a shared executor client
(`Area.get_script_client`) and the `ScriptRunner` engine, so the tests below
assert on that indirection: triggers/timers/demos must never touch a real
player's state and must keep working with no owners present.
"""

import asyncio
from types import SimpleNamespace

import pytest

from server import commands
from server.area import Area
from server.script_runner import ScriptRunner, parse_demo_description
from server.timer import Timer


class FakeServer:
    command_aliases = {}
    char_list = []


class FakeHubManager:
    def __init__(self):
        self.server = FakeServer()
        self.hubs = []


class FakeAreaManager:
    def __init__(self):
        self.hub_manager = FakeHubManager()
        self.owners = set()
        self.areas = []
        self.char_list = ["Char0"]
        self.can_gm = True
        self.single_cm = False
        self.arup_enabled = False
        self.hide_clients = False

    @property
    def server(self):
        return self.hub_manager.server

    def broadcast_ooc(self, msg, exclude_list=None):
        pass

    def send_arup_players(self):
        pass

    def update_subtheme(self, client):
        pass

    def real_owners(self):
        from server.remote_client import RemoteClient

        return {o for o in self.owners if not isinstance(o, RemoteClient)}

    def is_valid_char_id(self, char_id):
        return char_id == 0

    def get_area_by_id(self, area_id):
        return self.areas[area_id]

    def get_character_data(self, char_id, key, default=""):
        return default


class FakeExecutor:
    """Mimics RemoteClient.execute: clears output, captures calls, errors."""

    def __init__(self):
        self.server = FakeServer()
        self.area = None
        self.output = []
        self.calls = []
        self.error = None
        self.broadcast_list = []

    def join_area(self, area):
        self.area = area

    def execute(self, cmd, arg=""):
        self.calls.append((cmd, arg))
        self.output = [f"[ERROR] {self.error}"] if self.error else []
        return self.output


class FakeTarget:
    hidden = False
    is_mod = False
    id = 42
    showname = "Showname"
    char_name = "Char"


class FakeBroadcastArea:
    """Minimal area stand-in for ScriptRunner tests (no real server needed)."""

    def __init__(self):
        self.id = 0
        self.clients = set()
        self.hp_def = 7
        self.hp_pro = 8
        self.background = "test-bg"
        self.pos_lock = ["wit"]
        self.last_ic_message = None
        self.sent = []
        self.ooc = []

    def send_command(self, cmd, *args):
        self.sent.append((cmd,) + tuple(args))

    def broadcast_ooc(self, msg, exclude_list=None):
        self.ooc.append(msg)


@pytest.fixture
def make_area():
    def _make_area():
        manager = FakeAreaManager()
        area = Area(manager, "Test Area")
        manager.areas.append(area)
        return area

    return _make_area


def _spy_ooc(area):
    messages = []
    area.broadcast_ooc = lambda msg, exclude_list=None: messages.append(msg)
    return messages


# --- parse_demo_description ---


def test_parse_demo_description_basic():
    desc = "wait#1000%CT#narrator#hello%BN#bg1%"
    assert parse_demo_description(desc) == [
        ("wait", 1.0),
        ("packet", "CT", ("narrator", "hello")),
        ("packet", "BN", ("bg1",)),
    ]


def test_parse_demo_description_command():
    assert parse_demo_description("/ct hello world%") == [
        ("command", "ct", "hello world")
    ]


def test_parse_demo_description_chained_demo():
    assert parse_demo_description("/demo 2%") == [("command", "demo", "2")]


def test_parse_demo_description_unescapes():
    desc = "CT#a<num>b<and>c<percent>d<dollar>e%"
    assert parse_demo_description(desc) == [("packet", "CT", ("a", "b&c"))]


def test_parse_demo_description_ignores_unknown_headers():
    desc = "FOO#bar%MS#x#y%"
    assert parse_demo_description(desc) == [("packet", "MS", ("x", "y"))]


def test_parse_demo_description_ignores_empty_lines():
    assert parse_demo_description("%%%") == []


def test_parse_demo_description_commands_with_newlines():
    """Multi-line evidence: newlines before % don't drop commands or packets."""
    desc = "/pos_lock day%\n/bg BOTC-TownSquare%\nMS#x#y%\n/timer 0 start%\nwait#1000#%"
    assert parse_demo_description(desc) == [
        ("command", "pos_lock", "day"),
        ("command", "bg", "BOTC-TownSquare"),
        ("packet", "MS", ("x", "y")),
        ("command", "timer", "0 start"),
        ("wait", 1.0),
    ]


# --- triggers ---


def test_join_trigger_runs_command_through_executor(make_area):
    area = make_area()
    area.triggers["join"] = "ct <cid> <showname> <char>"
    executor = FakeExecutor()
    area._script_client = executor

    area.trigger("join", FakeTarget())

    assert executor.calls == [("ct", "42 Showname Char")]


def test_trigger_skips_remote_and_hidden_targets(make_area, monkeypatch):
    area = make_area()
    area.triggers["join"] = "ct hello"
    executor = FakeExecutor()
    area._script_client = executor

    remote = _make_remote_client(monkeypatch)
    hidden = FakeTarget()
    hidden.hidden = True

    area.trigger("join", remote)
    area.trigger("join", hidden)

    assert executor.calls == []


def test_trigger_ignores_empty_command(make_area):
    area = make_area()
    executor = FakeExecutor()
    area._script_client = executor

    area.trigger("join", FakeTarget())

    assert executor.calls == []


def test_present_trigger_runs_command_through_executor(make_area):
    area = make_area()
    evidence = SimpleNamespace(triggers={"present": "ct <cid>"})
    executor = FakeExecutor()
    area._script_client = executor

    area.trigger_evidence(evidence, "present", FakeTarget())

    assert executor.calls == [("ct", "42")]


def test_trigger_broadcasts_errors(make_area):
    area = make_area()
    area.triggers["join"] = "ct hello"
    executor = FakeExecutor()
    executor.error = "boom"
    area._script_client = executor
    messages = _spy_ooc(area)

    area.trigger("join", FakeTarget())

    assert any("[ERROR] boom" in m for m in messages)


# --- timers ---


def test_timer_expired_runs_commands_through_executor(make_area):
    area = make_area()
    executor = FakeExecutor()
    area._script_client = executor
    messages = _spy_ooc(area)
    timer = Timer(0, area=area)
    timer.commands = ["ct hello", "mc test"]

    timer.timer_expired()

    assert executor.calls == [("ct", "hello"), ("mc", "test")]
    assert timer.commands == []
    assert any("expired" in m for m in messages)


def test_timer_expired_stops_and_clears_on_error(make_area):
    area = make_area()
    executor = FakeExecutor()
    executor.error = "boom"
    area._script_client = executor
    messages = _spy_ooc(area)
    timer = Timer(0, area=area)
    timer.commands = ["ct a", "ct b"]

    timer.timer_expired()

    assert executor.calls == [("ct", "a")]
    assert timer.commands == []
    assert any("[ERROR] boom" in m for m in messages)


# --- ScriptRunner ---


class FakeHandle:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeLoop:
    """Deterministic stand-in for asyncio loop.call_later."""

    def __init__(self):
        self.calls = []

    def call_later(self, delay, callback):
        handle = FakeHandle()
        self.calls.append((handle, delay, callback))
        return handle

    def pop_next(self):
        handle, delay, callback = self.calls.pop(0)
        assert not handle.cancelled, "cancelled handle fired"
        callback()


@pytest.fixture
def fake_loop(monkeypatch):
    loop = FakeLoop()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    return loop


def test_script_runner_steps_instructions(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    instructions = [
        ("packet", "CT", ("narrator", "hello")),
        ("wait", 0.01),
        ("command", "h", "world"),
    ]
    assert runner.start(instructions) is True

    fake_loop.pop_next()  # step: broadcast the CT packet
    assert area.sent[-1] == ("CT", "narrator", "hello")
    assert len(fake_loop.calls) == 1

    fake_loop.pop_next()  # step: consume the wait, schedule the delayed step
    assert len(fake_loop.calls) == 1
    assert fake_loop.calls[0][1] == 0.01

    fake_loop.pop_next()  # step: run the command
    assert executor.calls == [("h", "world")]

    fake_loop.pop_next()  # step: queue exhausted, finish playback
    assert runner.running is False
    assert not fake_loop.calls


def test_script_runner_stops_on_error(fake_loop, monkeypatch):
    monkeypatch.setattr(
        commands,
        "resolve_command",
        lambda server, cmd: (lambda: None),
    )
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    executor.error = "something broke"
    runner = ScriptRunner(area, executor)

    runner.start([("command", "ct", "hi")])
    fake_loop.pop_next()  # step: command fails -> stop playback

    assert runner.running is False
    assert any("[ERROR] something broke" in m for m in area.ooc)
    assert not fake_loop.calls


def test_script_runner_chained_demo_replaces_queue(fake_loop, monkeypatch):
    monkeypatch.setattr(
        commands,
        "resolve_command",
        lambda server, cmd: commands.ooc_cmd_demo if cmd == "demo" else (lambda: None),
    )
    area = FakeBroadcastArea()
    executor = FakeExecutor()

    def _execute(cmd, arg=""):
        executor.calls.append((cmd, arg))
        if cmd == "demo":
            runner.start([("packet", "CT", ("narrator", "chained"))])
        executor.output = []
        return executor.output

    executor.execute = _execute
    runner = ScriptRunner(area, executor)

    runner.start([("command", "demo", "2")])
    fake_loop.pop_next()  # step: chained /demo replaces the queue

    assert executor.calls == [("demo", "2")]
    assert runner.running is True
    assert len(fake_loop.calls) == 1

    fake_loop.pop_next()  # step: play the chained packet
    assert area.sent[-1] == ("CT", "narrator", "chained")

    fake_loop.pop_next()  # step: queue exhausted, finish playback
    assert runner.running is False
    assert not fake_loop.calls


def test_script_runner_resets_modified_packets_on_finish():
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)

    runner.send_packet("HP", (1, "5"))
    runner.send_packet("BN", ("some-bg",))
    runner.finish()

    assert ("HP", 1, area.hp_def) in area.sent
    assert ("HP", 2, area.hp_pro) in area.sent
    assert ("BN", area.background) in area.sent
    assert runner.modified_packets == set()


# --- Area.play_demo / stop_demo ---


def test_play_demo_and_stop_demo(make_area):
    async def _run():
        area = make_area()
        executor = FakeExecutor()
        area._script_client = executor
        evidence = SimpleNamespace(desc="CT#narrator#hi%")

        area.play_demo(None, evidence)
        assert area.demo_runner is not None

        area.stop_demo()
        assert area.demo_runner.running is False

    asyncio.run(_run())


def test_play_demo_warns_out_of_range_char_id(make_area):
    """MS packets with an out-of-range char id warn the human caller."""

    async def _run():
        area = make_area()
        area._script_client = FakeExecutor()
        calls = []
        caller = SimpleNamespace(send_ooc=calls.append)

        good = SimpleNamespace(
            name="good", desc="MS#1#-#CM 1##lol#wit#0#1#0#0#0#0#0#0#3# #-1###%"
        )
        area.play_demo(caller, good)
        assert calls == []
        area.stop_demo()

        bad = SimpleNamespace(
            name="bad",
            desc="wait#500%MS#1#-#CM 1##lol#wit#0#1#500#0#0#0#0#0#3# #-1###%",
        )
        area.play_demo(caller, bad)
        assert any("char id 500" in msg for msg in calls)
        area.stop_demo()

    asyncio.run(_run())


def test_play_demo_no_instructions_warns_executor_caller(make_area):
    """Executor-triggered demos (present/join triggers) with no parseable
    lines broadcast a warning to the area instead of failing silently."""

    async def _run():
        area = make_area()
        area._script_client = FakeExecutor()
        ooc = _spy_ooc(area)
        evidence = SimpleNamespace(
            name="Nominate",
            desc="(👀Discovered in pos: wit)\njust some stray text with no % lines",
        )
        area.play_demo(None, evidence)
        assert area.demo_runner is None
        assert any("has no demo instructions" in msg for msg in ooc)
        assert any("Nominate" in msg for msg in ooc)

    asyncio.run(_run())


def test_play_demo_warns_out_of_range_char_id_for_executor(make_area):
    """OOR MS packets in an executor-triggered demo warn the area owners."""

    async def _run():
        area = make_area()
        area._script_client = FakeExecutor()
        ooc = _spy_ooc(area)
        bad = SimpleNamespace(
            name="bad",
            desc="wait#500%MS#1#-#CM 1##lol#wit#0#1#500#0#0#0#0#0#3# #-1###%",
        )
        area.play_demo(None, bad)
        assert any("char id 500" in msg for msg in ooc)
        area.stop_demo()

    asyncio.run(_run())


def test_demo_broadcasts_to_real_clients(monkeypatch):
    """End-to-end: playback on the real executor reaches real players in the area."""
    import asyncio

    import server.remote_client as remote_client
    from server.client_manager import ClientManager
    from server.evidence import EvidenceList
    from server.remote_client import RemoteClient

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    class RecordingTransport:
        def __init__(self):
            self.writes = []

        def write(self, data):
            self.writes.append(data)

    server = SimpleNamespace(
        hub_manager=FakeHubManager(),
        config={
            "playerlimit": 64,
            "hostname": "test",
            "music_change_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "ooc_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "wtce_floodguard": {"interval_length": 1, "times_per_interval": 1},
        },
        command_aliases={},
    )
    server.client_manager = ClientManager(server)

    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    transport = RecordingTransport()
    player = ClientManager.Client(server, transport, 1, 1)
    player.char_id = 0
    player.area = area
    area.clients.add(player)

    area.evi_list.evidences.append(
        EvidenceList.Evidence(
            "demo",
            "CT#test#hello-from-demo%"
            "MS#1#-#CM 1##lol#wit#0#1#0#0#0#0#0#0#3# #-1###%",
            "image",
            "all",
        )
    )

    async def _run():
        area.play_demo(None, area.evi_list.evidences[0])
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert isinstance(area._script_client, RemoteClient)
    payload = b"".join(transport.writes).decode("utf-8", "replace")
    assert "hello-from-demo" in payload
    assert "lol" in payload
    assert "MS#" in payload


# --- Executor robustness regressions (live-server crashes) ---


class FakeTransport:
    pass


class FakeHub:
    def default_area(self):
        return None


class FakeHubManager:
    def __init__(self):
        self.server = FakeServer()
        self.hubs = []

    def default_hub(self):
        return FakeHub()


def _make_server():
    return SimpleNamespace(
        hub_manager=FakeHubManager(),
        config={
            "music_change_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "ooc_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "wtce_floodguard": {"interval_length": 1, "times_per_interval": 1},
        },
    )


def _make_remote_client(monkeypatch):
    import server.remote_client as remote_client
    from server.remote_client import RemoteClient

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)
    return RemoteClient(_make_server(), is_mod=True)


def test_remote_client_excluded_from_player_list(make_area, monkeypatch):
    """System executor must not appear in player-list broadcasts (/gm crash)."""
    import json as json_module

    from server.client_manager import ClientManager

    server = _make_server()
    real = ClientManager.Client(server, FakeTransport(), 1, 1)
    real.char_id = 0
    remote = _make_remote_client(monkeypatch)
    remote.char_id = 0  # would pass every filter if not excluded by type

    area = make_area()
    area.clients = {real, remote}
    real.area = area

    sent = []
    target = FakeTarget()
    target.send_command = lambda cmd, *args: sent.append((cmd, args))

    area.broadcast_player_list_to_target(target)

    jsn = json_module.loads(sent[0][1][0])
    assert [str(c["id"]) for c in jsn["data"]] == ["1"]


def test_remote_client_ms_interception_tolerates_string_cid(monkeypatch):
    """Demo MS packets carry a string cid; interception must not raise."""
    rc = _make_remote_client(monkeypatch)
    rc.area = SimpleNamespace(
        id=0,
        name="x",
        clients=set(),
        area_manager=SimpleNamespace(char_list=["Char0"]),
    )

    args = [str(i) for i in range(17)]
    args[8] = "-1"
    rc.send_command("MS", *args)  # must not raise TypeError

    assert rc.area.area_manager.char_list == ["Char0"]


def test_executor_is_gm_never_mod(monkeypatch):
    """The system executor holds GM authority, never mod power."""
    import server.remote_client as remote_client
    from server.remote_client import RemoteClient

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)
    executor = RemoteClient(_make_server(), is_mod=False, name="[SCRIPT]", is_gm=True)
    assert executor.is_mod is False
    assert executor.is_gm is True

    admin = RemoteClient(_make_server(), is_mod=True, name="[ADMIN]", is_gm=False)
    assert admin.is_mod is True
    assert admin.is_gm is False


def test_executor_permissions_gm_only(monkeypatch):
    """Executor can run GM/CM commands but is denied pure-mod ones."""
    import server.remote_client as remote_client
    from server.client_manager import ClientManager
    from server.remote_client import RemoteClient
    from server.exceptions import ClientError

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = SimpleNamespace(
        hub_manager=FakeHubManager(),
        config={
            "playerlimit": 64,
            "hostname": "test",
            "music_change_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "ooc_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "wtce_floodguard": {"interval_length": 1, "times_per_interval": 1},
        },
        command_aliases={},
    )
    server.client_manager = ClientManager(server)

    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    executor = area.get_script_client()
    assert isinstance(executor, RemoteClient)
    assert executor.is_mod is False
    assert executor.is_gm is True

    # The executor holds GM authority: it's in the owner sets command bodies
    # check directly (e.g. /kick), but is invisible to real-GM lifecycle logic.
    assert executor in area.owners
    assert executor in area.area_manager.owners
    assert executor not in area._owners
    assert executor not in area.area_manager.real_owners()

    # GM/CM-gated command (/demo) still runs through the executor.
    out = executor.execute("demo", "")
    assert any("Stopping demo playback" in msg for msg in out)

    # Pure-mod command (/announce) is refused, even from the executor.
    out = executor.execute("announce", "hi")
    assert any("must be authorized" in msg for msg in out)

    # A regular client with no privileges is still denied both gates.
    player = ClientManager.Client(server, FakeTransport(), 1, 1)
    player.char_id = 0
    player.area = area
    area.clients.add(player)
    with pytest.raises(ClientError):
        commands.call(player, "announce", "hi")
    with pytest.raises(ClientError):
        commands.call(player, "demo", "")


def test_executor_invisible_to_gm_lifecycle(monkeypatch):
    """The phantom GM never blocks hub-name reset or shows in GM listings."""
    import server.remote_client as remote_client
    from server.area_manager import AreaManager
    from server.client_manager import ClientManager

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = SimpleNamespace(
        hub_manager=FakeHubManager(),
        config={
            "playerlimit": 64,
            "hostname": "test",
            "music_change_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "ooc_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "wtce_floodguard": {"interval_length": 1, "times_per_interval": 1},
        },
        command_aliases={},
    )
    server.client_manager = ClientManager(server)

    manager = AreaManager(server.hub_manager, "Original Hub")
    manager.hub_manager.server = server
    manager.can_gm = True
    manager.broadcast_ooc = lambda *a, **k: None
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    area.get_script_client()  # creates the phantom GM
    assert len(manager.owners) == 1
    assert len(manager.real_owners()) == 0
    assert manager.get_gms() == ""

    gm = ClientManager.Client(server, FakeTransport(), 1, 1)
    gm.area = area
    gm.broadcast_list = []
    gm.hide = lambda *a, **k: None
    area.broadcast_area_list = lambda *a, **k: None
    area.broadcast_evidence_list = lambda *a, **k: None
    manager.owners.add(gm)

    assert len(manager.real_owners()) == 1
    assert manager.get_gms() == "[SYSTEM]".replace("[SYSTEM]", gm.name)

    manager.name = "Meme Name"
    manager.remove_owner(gm)
    # Only the phantom GM remains, so the hub name must still reset.
    assert manager.name == "Original Hub"


# --- Executor authority: CM in claim-only hubs ---


def _server_with_client_manager():
    from server.client_manager import ClientManager

    server = SimpleNamespace(
        hub_manager=FakeHubManager(),
        config={
            "playerlimit": 64,
            "hostname": "test",
            "music_change_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "ooc_floodguard": {"interval_length": 1, "times_per_interval": 1},
            "wtce_floodguard": {"interval_length": 1, "times_per_interval": 1},
        },
        command_aliases={},
        player_state_observer=SimpleNamespace(
            notify_hub_changed=lambda *a, **k: None,
            notify_area_id_changed=lambda *a, **k: None,
        ),
    )
    server.client_manager = ClientManager(server)
    return server


def test_executor_is_cm_in_claim_only_hub(monkeypatch):
    """In a hub where GMs can't be claimed (e.g. KFO Hub 0), the executor is
    an area owner (CM), never a hub owner (GM), so CM automation can't
    escalate to GM power through a demo."""
    import server.remote_client as remote_client
    from server.remote_client import RemoteClient

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.can_gm = False
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)
    manager.timer = Timer(0, area=area, hub=manager)

    executor = area.get_script_client()
    assert isinstance(executor, RemoteClient)
    assert executor.is_mod is False
    assert executor.is_gm is False
    assert executor in area._owners
    assert executor in area.owners
    assert executor not in area.area_manager.owners
    assert area.real_cms() == set()
    assert area.get_owners() == ""

    # CM-gated commands still run through the executor (/demo, area timers).
    out = executor.execute("demo", "")
    assert any("Stopping demo playback" in msg for msg in out)
    out = executor.execute("timer", "1 5m")
    assert any("Timer 1" in msg for msg in out)

    # GM-only commands are denied, so a CM can't escalate via a demo.
    out = executor.execute("timer", "0 5m")
    assert any("Only GMs can set hub-wide timer ID 0" in msg for msg in out)
    out = executor.execute("stop_demo", "")
    assert any("must be authorized" in msg for msg in out)

    # Pure-mod commands stay denied too.
    out = executor.execute("announce", "hi")
    assert any("must be authorized" in msg for msg in out)


def test_get_owners_excludes_executor(monkeypatch):
    """The phantom CM never shows up in CM listings (get_owners/ARUP)."""
    import server.remote_client as remote_client
    from server.client_manager import ClientManager

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.can_gm = False
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    executor = area.get_script_client()
    assert executor in area._owners
    assert area.get_owners() == ""

    cm = ClientManager.Client(server, FakeTransport(), 1, 1)
    cm.showname = "RealCM"
    cm.char_id = 0
    cm.area = area
    area._owners.add(cm)

    assert area.real_cms() == {cm}
    assert "RealCM" in area.get_owners()
    assert "[SCRIPT]" not in area.get_owners()


def test_executor_cannot_change_hubs(monkeypatch):
    """The automation executor can't escape its hub/area via change_area."""
    import server.remote_client as remote_client
    from server.exceptions import ClientError

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    other = FakeAreaManager()
    other.hub_manager.server = server
    other_area = Area(other, "Other Area")
    other.areas.append(other_area)

    executor = area.get_script_client()
    assert getattr(executor, "is_automation", False) is True
    assert executor.area == area
    with pytest.raises(ClientError):
        executor.change_area(other_area)
    assert executor.area == area


# --- Executor movement: GM crawl vs CM pinning ---


def test_cm_executor_cannot_leave_area(monkeypatch):
    """A CM-level executor in a claim-only hub is pinned to its home area:
    any set_area attempt (e.g. via /area_kick **) raises and leaves it put."""
    import server.remote_client as remote_client
    from server.exceptions import ClientError

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.can_gm = False
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    other = Area(manager, "Other Area")
    manager.areas.extend([area, other])

    executor = area.get_script_client()
    assert executor.is_gm is False
    with pytest.raises(ClientError):
        executor.set_area(other)
    assert executor.area is area
    assert executor in area.clients
    assert executor in server.client_manager.clients
    assert executor in area._owners


def test_gm_executor_can_crawl_within_hub(monkeypatch):
    """A GM-level executor may move between areas of its own hub (e.g. a GM
    /area_kick), but never leaves the hub."""
    import server.remote_client as remote_client
    from server.client_manager import ClientManager

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)
    # set_area triggers area join/leave + music bookkeeping that isn't under test.
    monkeypatch.setattr(Area, "new_client", lambda self, client: self.clients.add(client))
    monkeypatch.setattr(Area, "remove_client", lambda self, client: self.clients.discard(client))
    monkeypatch.setattr(Area, "broadcast_area_list", lambda *a, **k: None)
    monkeypatch.setattr(Area, "broadcast_player_list", lambda *a, **k: None)
    monkeypatch.setattr(Area, "broadcast_player_list_to_target", lambda *a, **k: None)
    monkeypatch.setattr(ClientManager.Client, "refresh_music", lambda self, reload=False: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area1 = Area(manager, "Area 1")
    area2 = Area(manager, "Area 2")
    manager.areas.extend([area1, area2])

    executor = area1.get_script_client()
    assert executor.is_gm is True
    executor.set_area(area2)
    assert executor.area is area2
    assert executor in area2.clients
    assert executor not in area1.clients
    assert executor in server.client_manager.clients


def test_gm_executor_cannot_change_hubs(monkeypatch):
    """Even a GM-level executor cannot move to another hub via set_area."""
    import server.remote_client as remote_client
    from server.exceptions import ClientError

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area1 = Area(manager, "Area 1")
    manager.areas.append(area1)

    other = FakeAreaManager()
    other.hub_manager.server = server
    other_area = Area(other, "Other Hub Area")
    other.areas.append(other_area)

    executor = area1.get_script_client()
    with pytest.raises(ClientError):
        executor.set_area(other_area)
    assert executor.area is area1
    assert executor in area1.clients


def test_get_script_client_reanchors_parked_executor(monkeypatch):
    """Reusing a cached executor that was parked in another area (e.g. via a
    GM area_kick) pulls it back to its home area before the demo/trigger runs."""
    import server.remote_client as remote_client

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area1 = Area(manager, "Area 1")
    area2 = Area(manager, "Area 2")
    manager.areas.extend([area1, area2])

    executor = area1.get_script_client()
    assert executor in server.client_manager.clients

    # GM executor crawled to another area in the same hub.
    area1.clients.discard(executor)
    executor.area = area2
    area2.clients.add(executor)

    assert area1.get_script_client() is executor
    assert executor.area is area1
    assert executor in area1.clients
    assert executor not in area2.clients
    assert executor in server.client_manager.clients


# --- /stop_demo ---


def test_stop_demo_stops_area_and_all_hub_demos(monkeypatch):
    """GMs/mods can stop the current area demo and all hub demos via /stop_demo."""
    import server.remote_client as remote_client
    from server.client_manager import ClientManager

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area1 = Area(manager, "Area 1")
    area2 = Area(manager, "Area 2")
    manager.areas.extend([area1, area2])
    area1._script_client = FakeExecutor()
    area2._script_client = FakeExecutor()

    gm = ClientManager.Client(server, FakeTransport(), 1, 1)
    gm.showname = "GM"
    gm.char_id = 0
    gm.area = area1
    gm.send_command = lambda *a, **k: None
    area1.clients.add(gm)
    manager.owners.add(gm)

    evidence = SimpleNamespace(desc="CT#narrator#hi%")

    async def _run():
        area1.play_demo(None, evidence)
        area2.play_demo(None, evidence)
        assert area1.demo_runner.running and area2.demo_runner.running

        commands.call(gm, "stop_demo", "")
        assert area1.demo_runner.running is False
        assert area2.demo_runner.running is True

        commands.call(gm, "stop_demo", "all")
        assert area1.demo_runner.running is False
        assert area2.demo_runner.running is False

    asyncio.run(_run())


def test_stop_demo_denied_for_cm(monkeypatch):
    """CMs (area owners) can't use /stop_demo; only GMs and mods."""
    import server.remote_client as remote_client
    from server.client_manager import ClientManager
    from server.exceptions import ClientError

    monkeypatch.setattr(remote_client, "_ensure_system_ipid", lambda db: None)

    server = _server_with_client_manager()
    manager = FakeAreaManager()
    manager.hub_manager.server = server
    area = Area(manager, "Test Area")
    manager.areas.append(area)

    cm = ClientManager.Client(server, FakeTransport(), 1, 1)
    cm.showname = "CM"
    cm.area = area
    area._owners.add(cm)

    with pytest.raises(ClientError):
        commands.call(cm, "stop_demo", "")
