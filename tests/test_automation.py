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
from server.evidence import EvidenceList
from server.exceptions import ServerError
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
        self.name = "Test Hub"
        self.character_data = {}
        self.saved_paths = []
        self.abbreviation = "TH"
        self.subtheme = ""
        self.time_of_day = ""
        self.info = ""
        self.char_list_ref = ""
        self.music_ref = ""
        self.move_delay = 0
        self.can_gm = True
        self.single_cm = False
        self.arup_enabled = True
        self.hide_clients = False
        self.replace_music = False
        self.client_music = True
        self.max_areas = -1
        self.can_spectate = True
        self.can_getareas = True
        self.passing_msg = False
        self.autokick_to_latest_area = False
        self.timer = Timer(0, hub=self)

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
        return len(self.char_list) > char_id >= 0

    def get_area_by_id(self, area_id):
        return self.areas[area_id]

    def get_char_id_by_name(self, name):
        for i, ch in enumerate(self.char_list):
            if ch.lower() == name.lower():
                return i
        raise ServerError("Character not found.")

    def get_character_data(self, char, key, default=None):
        if isinstance(char, int) and self.is_valid_char_id(char):
            char = self.char_list[char]
        return self.character_data.get(char, {}).get(key, default)

    def set_character_data(self, char, key, value):
        if isinstance(char, int) and self.is_valid_char_id(char):
            char = self.char_list[char]
        self.character_data.setdefault(char, {})[key] = value

    def save_character_data(self, path=None):
        self.saved_paths.append(path)


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
        self.variables = {}
        self.afkers = []
        self._owners = set()
        self.area_manager = FakeAreaManager()
        self.timers = [Timer(x, area=self) for x in range(20)]
        self.evi_list = EvidenceList()
        self.links = {}

    def send_command(self, cmd, *args):
        self.sent.append((cmd,) + tuple(args))

    def broadcast_ooc(self, msg, exclude_list=None):
        self.ooc.append(msg)


class FakeScriptClient:
    """Minimal Client stand-in with the fields the live-source whitelist reads."""

    def __init__(self, user_id, showname, char_id=0, ipid=1, is_mod=False, hidden=False):
        self.id = user_id
        self.showname = showname
        self.char_name = showname
        self.name = showname
        self.char_id = char_id
        self.ipid = ipid
        self.is_mod = is_mod
        self.hidden = hidden
        self.pos = "wit"
        self.charid_pair = -1
        self.hdid = "hdid"
        self.sneaking = False
        self.frozen = False
        self.iniswap = ""
        self.last_move_time = 0
        self.remote_listen = 2
        self.subtheme = ""
        self.time_of_day = ""
        self.char_url = ""
        self.hidden_in = None
        self.listen_pos = None


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
    desc = "wait 1000%CT#narrator#hello%BN#bg1%"
    assert parse_demo_description(desc) == [
        ("wait", 1.0),
        ("packet", "CT", ("narrator", "hello")),
        ("packet", "BN", ("bg1",)),
    ]


def test_parse_demo_description_command():
    assert parse_demo_description("/ct hello world%") == [("command", "ct", "hello world")]


def test_parse_demo_description_chained_demo():
    assert parse_demo_description("/demo 2%") == [("command", "demo", "2")]


def test_parse_demo_description_unescapes():
    desc = "CT#a<num>b<and>c<percent>d<dollar>e%"
    assert parse_demo_description(desc) == [("packet", "CT", ("a", "b&c"))]


def test_parse_demo_description_num_percent_terminator():
    desc = "set count 0#%CT#COUNTER#Count: <!count>#1#%set count count+1#%if count gt 1 loop#%label loop#%return#%wait 500#%"
    assert parse_demo_description(desc) == [
        ("set", "count", "0"),
        ("packet", "CT", ("COUNTER", "Count: <!count>", "1")),
        ("set", "count", "count+1"),
        ("if", "count", "gt", "1", "loop"),
        ("label", "loop"),
        ("return",),
        ("wait", 0.5),
    ]


def test_parse_demo_description_symbol_if_operators():
    desc = "if total >= 5 done%if x == 2 next%if y != z other%if a < 3 small%if b <= 2 tiny%if c > 9 big%"
    assert parse_demo_description(desc) == [
        ("if", "total", ">=", "5", "done"),
        ("if", "x", "==", "2", "next"),
        ("if", "y", "!=", "z", "other"),
        ("if", "a", "<", "3", "small"),
        ("if", "b", "<=", "2", "tiny"),
        ("if", "c", ">", "9", "big"),
    ]


def test_parse_demo_description_rand():
    desc = "rand roll 1 6%rand dmg 2 total+1%"
    assert parse_demo_description(desc) == [
        ("rand", "roll", "1", "6"),
        ("rand", "dmg", "2", "total+1"),
    ]


def test_parse_demo_description_newline_separated_instructions():
    desc = "set count 5\nset count count-1\nif count gt 0 loop\nlabel loop"
    assert parse_demo_description(desc) == [
        ("set", "count", "5"),
        ("set", "count", "count-1"),
        ("if", "count", "gt", "0", "loop"),
        ("label", "loop"),
    ]


def test_parse_demo_description_newlines_and_percent_mixed():
    desc = "set count 5\nlabel loop\nset count count-1\nif count gt 0 loop%\nCT#narrator#go%\nwait 500"
    assert parse_demo_description(desc) == [
        ("set", "count", "5"),
        ("label", "loop"),
        ("set", "count", "count-1"),
        ("if", "count", "gt", "0", "loop"),
        ("packet", "CT", ("narrator", "go")),
        ("wait", 0.5),
    ]


def test_parse_demo_description_multiline_packet_preserved():
    """A packet spans newlines until `%`; newlines stay in its fields."""
    desc = "CT#narrator#Hello\nthere\nguys!!!#%\nset count 5%"
    assert parse_demo_description(desc) == [
        ("packet", "CT", ("narrator", "Hello\nthere\nguys!!!")),
        ("set", "count", "5"),
    ]


def test_parse_demo_description_multiline_command_preserved():
    """A slash command spans newlines until `%`; newlines stay in its args."""
    desc = "/say line one\nline two%\nset count 5%"
    assert parse_demo_description(desc) == [
        ("command", "say", "line one\nline two"),
        ("set", "count", "5"),
    ]


def test_parse_demo_description_wait_hash_form():
    """Legacy `wait#<ms>#%` and space `wait <ms>` are equivalent."""
    assert parse_demo_description("wait#5000#%") == [("wait", 5.0)]
    assert parse_demo_description("wait 5000") == [("wait", 5.0)]


def test_parse_demo_description_concat():
    assert parse_demo_description('concat list s ", "%concat tag s%') == [
        ("concat", "list", "s", '", "'),
        ("concat", "tag", "s", ""),
    ]


def test_parse_demo_description_save():
    assert parse_demo_description('save "my folder" title "hello world"%save 0 lives 3%') == [
        ("save", '"my folder"', "title", '"hello world"'),
        ("save", "0", "lives", "3"),
    ]


def test_parse_demo_description_ignores_unknown_headers():
    desc = "FOO#bar%MS#x#y%"
    assert parse_demo_description(desc) == [("packet", "MS", ("x", "y"))]


def test_parse_demo_description_ignores_empty_lines():
    assert parse_demo_description("%%%") == []


def test_parse_demo_description_commands_with_newlines():
    """Multi-line evidence: newlines before % don't drop commands or packets."""
    desc = "/pos_lock day%\n/bg BOTC-TownSquare%\nMS#x#y%\n/timer 0 start%\nwait 1000#%"
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


def test_trigger_sets_script_context_variables(make_area):
    area = make_area()
    area.triggers["join"] = "ct <showname>"
    executor = FakeExecutor()
    area._script_client = executor

    area.trigger("join", FakeTarget())

    assert executor.calls == [("ct", "Showname")]
    assert area.variables["trigger_cid"] == 42
    assert area.variables["trigger_showname"] == "Showname"
    assert area.variables["trigger_char"] == "Char"


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

        good = SimpleNamespace(name="good", desc="MS#1#-#CM 1##lol#wit#0#1#0#0#0#0#0#0#3# #-1###%")
        area.play_demo(caller, good)
        assert calls == []
        area.stop_demo()

        bad = SimpleNamespace(
            name="bad",
            desc="wait 500%MS#1#-#CM 1##lol#wit#0#1#500#0#0#0#0#0#3# #-1###%",
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
            desc="wait 500%MS#1#-#CM 1##lol#wit#0#1#500#0#0#0#0#0#3# #-1###%",
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
            "CT#test#hello-from-demo%" "MS#1#-#CM 1##lol#wit#0#1#0#0#0#0#0#0#3# #-1###%",
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


# --- Demo scripting (set/get/labels/goto/if) ---


def test_parse_demo_scripting_instructions():
    from server.script_runner import parse_demo_description

    desc = (
        "set count 5%"
        "get need players+2%"
        "label loop%"
        "set count count-1%"
        "if count gt 0 loop%"
        "goto sub%"
        "goto done%"
        "label sub%"
        "return%"
        "label done%"
        "CT#narrator#go%"
    )
    instructions = parse_demo_description(desc)
    assert ("set", "count", "5") in instructions
    assert ("get", "need", "players+2") in instructions
    assert ("label", "loop") in instructions
    assert ("if", "count", "gt", "0", "loop") in instructions
    assert ("goto", "sub") in instructions
    assert ("goto", "done") in instructions
    assert ("return",) in instructions
    assert ("packet", "CT", ("narrator", "go")) in instructions


def test_script_runner_set_get(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("set", "count", "5"), ("set", "count", "count+3"), ("get", "need", "players")])
    area.clients = {"a", "b", "c"}

    fake_loop.pop_next()  # set count = 5
    assert area.variables["count"] == 5

    fake_loop.pop_next()  # set count = count + 3
    assert area.variables["count"] == 8

    fake_loop.pop_next()  # get need = live player count (3 clients)
    assert area.variables["need"] == 3

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_unknown_variable_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("set", "x", "missing+1")])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("[Demo] [ERROR] Unknown variable 'missing'" in m for m in area.ooc)


def test_script_runner_set_string_literal(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "name", '"Alice"'),
            ("set", "also", "'Bob'"),
            ("packet", "CT", ("narrator", "Hello <!name>, from <!also>")),
        ]
    )

    fake_loop.pop_next()  # set name = "Alice"
    assert area.variables["name"] == "Alice"

    fake_loop.pop_next()  # set also = "Bob"
    assert area.variables["also"] == "Bob"

    fake_loop.pop_next()  # broadcast CT with substituted getters
    assert area.sent[-1] == ("CT", "narrator", "Hello Alice, from Bob")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_set_copies_variable(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("set", "a", '"hello"'), ("set", "b", "a")])

    fake_loop.pop_next()  # set a = "hello"
    fake_loop.pop_next()  # set b = a (copy, not expression)

    assert area.variables["a"] == "hello"
    assert area.variables["b"] == "hello"

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_if_string_eq_branch(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "name", '"Alice"'),
            ("if", "name", "eq", '"Alice"', "yes"),
            ("packet", "CT", ("narrator", "not taken")),
            ("label", "yes"),
            ("packet", "CT", ("narrator", "taken")),
        ]
    )

    fake_loop.pop_next()  # set name = "Alice"
    fake_loop.pop_next()  # if name == "Alice" -> jump to yes
    fake_loop.pop_next()  # label yes
    fake_loop.pop_next()  # broadcast CT "taken"

    assert area.sent[-1] == ("CT", "narrator", "taken")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_if_mixed_compare_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("set", "n", "5"), ("if", "n", "lt", '"5"', "done")])

    fake_loop.pop_next()  # set n = 5
    fake_loop.pop_next()  # if 5 < "5" -> cannot compare

    assert runner.running is False
    assert any("Cannot compare a number and a string" in m for m in area.ooc)


def test_script_runner_if_symbol_operators(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "n", "3"),
            ("if", "n", ">=", "5", "done"),
            ("packet", "CT", ("narrator", "n < 5")),
            ("set", "n", "n+2"),
            ("if", "n", ">=", "5", "done"),
            ("packet", "CT", ("narrator", "unreachable")),
            ("label", "done"),
            ("packet", "CT", ("narrator", "n is 5")),
        ]
    )

    fake_loop.pop_next()  # set n = 3
    fake_loop.pop_next()  # if 3 >= 5 -> no jump
    fake_loop.pop_next()  # broadcast "n < 5"
    fake_loop.pop_next()  # set n = 5
    fake_loop.pop_next()  # if 5 >= 5 -> jump to done
    fake_loop.pop_next()  # label done
    fake_loop.pop_next()  # broadcast "n is 5"

    assert area.sent[-1] == ("CT", "narrator", "n is 5")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_if_symbol_ne_branch(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "name", '"Alice"'),
            ("if", "name", "!=", '"Bob"', "yes"),
            ("packet", "CT", ("narrator", "not taken")),
            ("label", "yes"),
            ("packet", "CT", ("narrator", "taken")),
        ]
    )

    fake_loop.pop_next()  # set name = "Alice"
    fake_loop.pop_next()  # if "Alice" != "Bob" -> jump to yes
    fake_loop.pop_next()  # label yes
    fake_loop.pop_next()  # broadcast "taken"

    assert area.sent[-1] == ("CT", "narrator", "taken")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_inline_getter_in_packet(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "count", "5"),
            ("packet", "CT", ("narrator", "I counted <!count>")),
        ]
    )

    fake_loop.pop_next()  # set count = 5
    fake_loop.pop_next()  # broadcast CT with substituted getter

    assert area.variables["count"] == 5
    assert area.sent[-1] == ("CT", "narrator", "I counted 5")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_inline_getter_in_command(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "score", "10"),
            ("command", "h", "Score: <!score>"),
        ]
    )

    fake_loop.pop_next()  # set score = 10
    fake_loop.pop_next()  # run command with substituted arg

    assert executor.calls == [("h", "Score: 10")]

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_inline_getter_unknown_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("packet", "CT", ("narrator", "I counted <!count>"))])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("Unknown variable 'count' in inline getter" in m for m in area.ooc)


def test_script_runner_inline_getter_live_source(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("packet", "CT", ("narrator", "<!players> people here"))])
    area.clients = {"a", "b", "c"}

    fake_loop.pop_next()

    assert area.sent[-1] == ("CT", "narrator", "3 people here")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_inline_getter_live_path(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("packet", "CT", ("narrator", "<!client[0].showname> leads"))])
    area.clients = {FakeScriptClient(2, "Apollo"), FakeScriptClient(1, "Miles")}

    fake_loop.pop_next()

    assert area.sent[-1] == ("CT", "narrator", "Apollo leads")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_get_client_showname(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "i", "0"),
            ("get", "showname", "client[i].showname"),
            ("packet", "CT", ("narrator", "<!showname> is here")),
        ]
    )
    area.clients = {FakeScriptClient(2, "Apollo"), FakeScriptClient(1, "Miles")}

    fake_loop.pop_next()  # set i = 0
    fake_loop.pop_next()  # get showname = client[0].showname (Apollo, alphabetical)
    assert area.variables["showname"] == "Apollo"
    fake_loop.pop_next()  # broadcast CT with getter

    assert area.sent[-1] == ("CT", "narrator", "Apollo is here")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_get_client_index_out_of_range_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("get", "x", "client[5].showname")])
    area.clients = {FakeScriptClient(1, "Miles")}

    fake_loop.pop_next()

    assert runner.running is False
    assert any("Client index 5 out of range" in m for m in area.ooc)


def test_script_runner_concat(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "list", '""'),
            ("set", "a", '"Miles"'),
            ("set", "b", '"Apollo"'),
            ("concat", "list", "a", '", "'),
            ("concat", "list", "b", '", "'),
            ("packet", "CT", ("narrator", "Players: <!list>")),
        ]
    )

    fake_loop.pop_next()  # set list = ""
    fake_loop.pop_next()  # set a = "Miles"
    fake_loop.pop_next()  # set b = "Apollo"
    fake_loop.pop_next()  # concat list += "Miles"
    fake_loop.pop_next()  # concat list += ", Apollo"
    assert area.variables["list"] == "Miles, Apollo"

    fake_loop.pop_next()  # broadcast CT
    assert area.sent[-1] == ("CT", "narrator", "Players: Miles, Apollo")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_concat_no_separator(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "tag", '"A"'),
            ("concat", "tag", '"B"'),
            ("concat", "tag", '"C"'),
        ]
    )

    fake_loop.pop_next()  # set tag = "A"
    fake_loop.pop_next()  # concat tag += "B"
    fake_loop.pop_next()  # concat tag += "C"

    assert area.variables["tag"] == "ABC"

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_rand_inclusive_range(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("rand", "roll", "1", "6"),
            ("packet", "CT", ("narrator", "You rolled <!roll>")),
        ]
    )

    fake_loop.pop_next()  # rand roll in [1, 6]
    roll = area.variables["roll"]
    assert isinstance(roll, int)
    assert 1 <= roll <= 6

    fake_loop.pop_next()  # broadcast CT
    assert area.sent[-1] == ("CT", "narrator", f"You rolled {roll}")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_rand_operand_bounds(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "min", "1"),
            ("set", "max", "3"),
            ("rand", "roll", "min", "max"),
            ("packet", "CT", ("narrator", "<!roll>")),
        ]
    )

    fake_loop.pop_next()  # set min = 1
    fake_loop.pop_next()  # set max = 3
    fake_loop.pop_next()  # rand roll = random.randint(1, 3)
    assert 1 <= area.variables["roll"] <= 3

    fake_loop.pop_next()  # broadcast CT
    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_rand_bounds_reversed_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("rand", "roll", "6", "1")])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("rand min 6 is greater than max 1" in m for m in area.ooc)


def test_script_runner_rand_non_number_bounds_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("rand", "roll", '"a"', "6")])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("rand bounds must be numbers" in m for m in area.ooc)


def test_script_runner_if_live_path_and_list_visible(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    hidden = FakeScriptClient(2, "Ghost", hidden=True)
    visible = FakeScriptClient(1, "Miles")
    area.clients = {hidden, visible}
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "i", "0"),
            ("get", "total", "clients.count"),
            ("set", "list", '""'),
            ("label", "loop"),
            ("if", "i", "ge", "total", "done"),
            ("if", "client[i].hidden", "eq", "1", "continue"),
            ("get", "showname", "client[i].showname"),
            ("concat", "list", "showname", '", "'),
            ("label", "continue"),
            ("set", "i", "i+1"),
            ("goto", "loop"),
            ("label", "done"),
            ("packet", "CT", ("narrator", "Players here: <!list>")),
        ]
    )

    for _ in range(30):
        if not runner.running:
            break
        fake_loop.pop_next()

    assert area.variables["list"] == "Miles"
    assert area.sent[-1] == ("CT", "narrator", "Players here: Miles")
    assert runner.running is False


def test_script_runner_goto_loop(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("set", "count", "3"),
            ("label", "loop"),
            ("set", "count", "count-1"),
            ("if", "count", "gt", "0", "loop"),
            ("packet", "CT", ("narrator", "done")),
        ]
    )

    fake_loop.pop_next()  # set count = 3
    fake_loop.pop_next()  # label loop (no-op)
    fake_loop.pop_next()  # set count = 2
    fake_loop.pop_next()  # if count > 0 -> jump to loop
    fake_loop.pop_next()  # label loop
    fake_loop.pop_next()  # set count = 1
    fake_loop.pop_next()  # if count > 0 -> jump to loop
    fake_loop.pop_next()  # label loop
    fake_loop.pop_next()  # set count = 0
    fake_loop.pop_next()  # if count > 0 -> false, fall through
    fake_loop.pop_next()  # broadcast CT

    assert area.variables["count"] == 0
    assert area.sent[-1] == ("CT", "narrator", "done")
    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_goto_unknown_label_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("goto", "nope")])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("Unknown label 'nope'" in m for m in area.ooc)


def test_script_runner_goto_return(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("packet", "CT", ("a", "before")),
            ("goto", "sub"),
            ("goto", "done"),
            ("label", "sub"),
            ("packet", "CT", ("a", "in-sub")),
            ("return",),
            ("label", "done"),
            ("packet", "CT", ("a", "after")),
        ]
    )

    fake_loop.pop_next()  # broadcast "before"
    fake_loop.pop_next()  # goto sub -> push return, jump to sub
    fake_loop.pop_next()  # label sub (no-op)
    fake_loop.pop_next()  # broadcast "in-sub"
    fake_loop.pop_next()  # return -> pop to the goto, which jumps to done
    fake_loop.pop_next()  # goto done
    fake_loop.pop_next()  # label done (no-op)
    fake_loop.pop_next()  # broadcast "after"

    assert [s[2] for s in area.sent] == ["before", "in-sub", "after"]
    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_return_without_target_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("packet", "CT", ("a", "say")), ("return",)])

    fake_loop.pop_next()  # broadcast "say"
    fake_loop.pop_next()  # return with empty stack -> script just ends

    assert runner.running is False
    assert [s[2] for s in area.sent] == ["say"]
    assert not area.ooc


def test_script_runner_if_unknown_op_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("if", "a", "zzz", "1", "loop")])

    fake_loop.pop_next()

    assert runner.running is False
    assert any("Unknown comparison 'zzz'" in m for m in area.ooc)


def test_script_runner_max_steps_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.max_steps = 5
    runner.start(
        [
            ("label", "loop"),
            ("goto", "loop"),
        ]
    )

    for _ in range(6):
        fake_loop.pop_next()

    assert runner.running is False
    assert any("Max steps exceeded" in m for m in area.ooc)


def test_evaluate_expression_arithmetic():
    from server.scripting import evaluate_expression, ScriptingError

    assert evaluate_expression("5", {}) == 5
    assert evaluate_expression("2+3*4", {}) == 14
    assert evaluate_expression("x+1", {"x": 5}) == 6
    assert evaluate_expression("x*y-2", {"x": 3, "y": 4}) == 10
    with pytest.raises(ScriptingError):
        evaluate_expression("x**2", {})
    with pytest.raises(ScriptingError):
        evaluate_expression("unknown_var+1", {})
    with pytest.raises(ScriptingError):
        evaluate_expression("1/0", {})
    with pytest.raises(ScriptingError):
        evaluate_expression("2 + __import__('os')", {})


def test_resolve_value():
    from server.scripting import resolve_value, ScriptingError

    assert resolve_value('"hello"', {}) == "hello"
    assert resolve_value("'hello'", {}) == "hello"
    assert resolve_value('""', {}) == ""
    assert resolve_value("5", {}) == 5
    assert resolve_value("2+3", {}) == 5
    assert resolve_value("x", {"x": "hello"}) == "hello"
    assert resolve_value("x", {"x": 7}) == 7
    assert resolve_value("players", {}, {"players": 3}) == 3
    with pytest.raises(ScriptingError):
        resolve_value("missing", {})


def test_live_sources(make_area):
    from server.scripting import live_sources

    area = make_area()
    area.clients = {"a", "b"}
    area.max_players = 10
    area.hp_def = 7
    area.hp_pro = 8
    sources = live_sources(area)
    assert sources["players"] == 2
    assert sources["max_players"] == 10
    assert sources["hp_def"] == 7
    assert sources["hp_pro"] == 8
    assert sources["char_count"] == 1
    assert "timer0_remaining_ms" not in sources


def _filled_area():
    area = FakeBroadcastArea()
    area.clients = {
        FakeScriptClient(3, "Zulu", is_mod=True),
        FakeScriptClient(1, "Miles"),
        FakeScriptClient(2, "Apollo", char_id=0),
    }
    return area


def test_live_get_clients_count_excludes_system():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    area.clients = {
        FakeScriptClient(1, "Miles"),
        FakeScriptClient(2, "System", ipid=0),
    }
    assert live_get("clients.count", area) == 1


def test_live_get_client_snapshot_matches_getarea_order():
    from server.scripting import live_get

    area = _filled_area()
    area._owners = {next(iter(area.clients))}

    cm = next(c for c in area.clients if c.showname == "Apollo")
    area._owners = {cm}
    mod = next(c for c in area.clients if c.showname == "Zulu")

    # /getarea order: normal first (by showname), then CM, then mod.
    assert live_get("client[0].showname", area) == "Miles"
    assert live_get("client[1].showname", area) == "Apollo"
    assert live_get("client[2].showname", area) == "Zulu"


def test_live_get_client_fields():
    from server.scripting import live_get

    area = _filled_area()
    # /getarea order: Apollo, Miles (normals, alphabetical), then Zulu (mod).
    assert live_get("client[0].showname", area) == "Apollo"
    assert live_get("client[0].id", area) == 2
    assert live_get("client[0].char_id", area) == 0
    assert live_get("client[0].char_folder", area) == "Char0"
    assert live_get("client[0].is_cm", area) == 0
    assert live_get("client[0].iniswap", area) == ""
    assert live_get("client[0].last_move_time", area) == 0
    assert live_get("client[0].remote_listen", area) == 2
    assert live_get("client[0].subtheme", area) == ""
    assert live_get("client[0].time_of_day", area) == ""
    assert live_get("client[0].char_url", area) == ""
    assert live_get("client[0].sneaking", area) == 0
    assert live_get("client[0].frozen", area) == 0
    assert live_get("client[2].showname", area) == "Zulu"


def test_live_get_index_expression():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    area.clients = {FakeScriptClient(1, "Miles"), FakeScriptClient(2, "Apollo")}
    # Snapshot order: [Apollo, Miles].
    assert live_get("client[i].showname", area, {"i": 1}) == "Miles"
    assert live_get("client[i+1].showname", area, {"i": 0}) == "Miles"


def test_live_get_area_and_hub_fields(make_area):
    from server.scripting import live_get

    area = make_area()
    area.name = "Courtroom"
    area.max_players = 10
    area.hp_def = 7
    area.hp_pro = 8
    area.desc = "A room"
    area.pos_lock = ["wit", "stand"]
    area.music_ref = "court"
    area.evidence_mod = "FFA"
    area.area_manager.name = "Test Hub"

    assert live_get("area.name", area) == "Courtroom"
    assert live_get("area.max_players", area) == 10
    assert live_get("area.hp_def", area) == 7
    assert live_get("area.hp_pro", area) == 8
    assert live_get("area.desc", area) == "A room"
    assert live_get("area.pos_lock", area) == "wit stand"
    assert live_get("area.music_ref", area) == "court"
    assert live_get("area.evidence_mod", area) == "FFA"
    assert live_get("area.bg_lock", area) == 0
    assert live_get("area.can_cm", area) == 0
    assert live_get("area.locked", area) == 0
    assert live_get("area.music_autoplay", area) == 0
    hub = area.area_manager
    hub.music_ref = "court_hub"
    hub.move_delay = 3
    hub.char_list_ref = "characters.yaml"
    hub.info = "A hub description"
    assert live_get("hub.name", area) == "Test Hub"
    assert live_get("hub.char_count", area) == 1
    assert live_get("hub.music_ref", area) == "court_hub"
    assert live_get("hub.move_delay", area) == 3
    assert live_get("hub.char_list_ref", area) == "characters.yaml"
    assert live_get("hub.doc", area) == "A hub description"
    assert live_get("hub.current_areas", area) == 1


def test_live_get_hub_fields_all_readable(make_area):
    from server.scripting import live_get

    area = make_area()
    fields = [
        "name",
        "abbreviation",
        "move_delay",
        "arup_enabled",
        "hide_clients",
        "info",
        "can_gm",
        "music_ref",
        "replace_music",
        "client_music",
        "max_areas",
        "single_cm",
        "can_spectate",
        "can_getareas",
        "passing_msg",
        "autokick_to_latest_area",
        "char_list_ref",
        "doc",
        "char_count",
        "subtheme",
        "time_of_day",
        "current_areas",
    ]
    for field in fields:
        assert live_get(f"hub.{field}", area) is not None, field


def test_live_get_area_fields_all_readable(make_area):
    from server.scripting import live_get

    area = make_area()
    fields = [
        "background",
        "background_suffix",
        "overlay",
        "pos_lock",
        "bg_lock",
        "overlay_lock",
        "evidence_mod",
        "can_cm",
        "locking_allowed",
        "iniswap_allowed",
        "showname_changes_allowed",
        "shouts_allowed",
        "jukebox",
        "abbreviation",
        "non_int_pres_only",
        "locked",
        "muted",
        "blankposting_allowed",
        "blankposting_forced",
        "hp_def",
        "hp_pro",
        "doc",
        "status",
        "move_delay",
        "hide_clients",
        "music_autoplay",
        "max_players",
        "desc",
        "music_ref",
        "replace_music",
        "client_music",
        "music",
        "music_effects",
        "music_looping",
        "ambience",
        "can_dj",
        "music_locked",
        "hidden",
        "can_whisper",
        "can_wtce",
        "can_change_status",
        "use_backgrounds_yaml",
        "can_spectate",
        "can_getarea",
        "can_cross_swords",
        "can_scrum_debate",
        "can_panic_talk_action",
        "cross_swords_song_start",
        "cross_swords_song_end",
        "cross_swords_song_concede",
        "scrum_debate_song_start",
        "scrum_debate_song_end",
        "scrum_debate_song_concede",
        "panic_talk_action_song_start",
        "panic_talk_action_song_end",
        "panic_talk_action_song_concede",
        "force_sneak",
        "password",
        "dark",
        "background_dark",
        "pos_dark",
        "desc_dark",
        "passing_msg",
        "msg_delay",
        "present_reveals_evidence",
        "ooc_actions_enabled",
        "can_battle",
        "auto_pair",
        "auto_pair_max",
        "auto_pair_cycle",
    ]
    for field in fields:
        assert live_get(f"area.{field}", area) is not None, field


def test_live_get_timer_fields():
    import arrow
    import datetime

    from server.scripting import live_get

    area = FakeBroadcastArea()
    # Hub timer 0: running with 30s left.
    hub_timer = area.area_manager.timer
    hub_timer.set = True
    hub_timer.started = True
    hub_timer.target = arrow.get() + datetime.timedelta(seconds=30)
    # Area timer 1: set but paused with 90s on it.
    area.timers[0].set = True
    area.timers[0].static = datetime.timedelta(seconds=90)

    assert 29000 <= live_get("timer[0].remaining_ms", area) <= 30000
    assert live_get("timer[0].started", area) == 1
    assert live_get("timer[0].set", area) == 1
    assert live_get("timer[1].remaining_ms", area) == 90000
    assert live_get("timer[1].started", area) == 0
    assert live_get("timer[1].static_ms", area) == 90000
    # Unset timers read as zeros.
    assert live_get("timer[5].set", area) == 0
    assert live_get("timer[5].remaining_ms", area) == 0


def test_live_get_timer_index_expression():
    import datetime

    from server.scripting import live_get

    area = FakeBroadcastArea()
    # timer[4] is the 4th area timer, i.e. area.timers[3].
    area.timers[3].set = True
    area.timers[3].static = datetime.timedelta(seconds=7)

    assert live_get("timer[n].remaining_ms", area, {"n": 4}) == 7000


def test_live_get_timer_errors():
    from server.scripting import live_get, ScriptingError

    area = FakeBroadcastArea()
    with pytest.raises(ScriptingError, match="Timer index 21"):
        live_get("timer[21].remaining_ms", area)
    with pytest.raises(ScriptingError, match="Unknown timer field"):
        live_get("timer[0].bogus_field", area)
    with pytest.raises(ScriptingError):
        live_get("timer[1.5].remaining_ms", area)


def test_script_runner_get_timer_path(fake_loop):
    import datetime

    area = FakeBroadcastArea()
    area.timers[1].set = True
    area.timers[1].static = datetime.timedelta(seconds=45)
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("get", "left", "timer[2].remaining_ms"),
            ("packet", "CT", ("narrator", "<!left> ms left")),
        ]
    )

    fake_loop.pop_next()  # get left = timer[2].remaining_ms
    assert area.variables["left"] == 45000
    fake_loop.pop_next()  # broadcast CT with getter
    assert area.sent[-1] == ("CT", "narrator", "45000 ms left")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_live_get_errors():
    from server.scripting import live_get, ScriptingError

    area = _filled_area()
    with pytest.raises(ScriptingError):
        live_get("client[9].showname", area)
    with pytest.raises(ScriptingError):
        live_get("client[0].bogus_field", area)
    for field in ("ipid", "hdid", "is_mod"):
        with pytest.raises(ScriptingError):
            live_get(f"client[0].{field}", area)
    for field in ("music_player", "music_player_ipid"):
        with pytest.raises(ScriptingError):
            live_get(f"area.{field}", area)
    with pytest.raises(ScriptingError):
        live_get("area.bogus_field", area)
    with pytest.raises(ScriptingError):
        live_get("hub.bogus_field", area)
    with pytest.raises(ScriptingError):
        live_get("bogus.path", area)
    with pytest.raises(ScriptingError):
        live_get("client[1.5].showname", area)


def test_live_get_evidence_fields():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    area.evi_list.evidences.append(EvidenceList.Evidence("Letter", "A clue", "letter.png", "all", True, 2, True, False))
    assert live_get("evidence.count", area) == 1
    assert live_get("evidence[0].name", area) == "Letter"
    assert live_get("evidence[0].desc", area) == "A clue"
    assert live_get("evidence[0].image", area) == "letter.png"
    assert live_get("evidence[0].pos", area) == "all"
    assert live_get("evidence[0].can_hide_in", area) == 1
    assert live_get("evidence[0].show_in_dark", area) == 2
    assert live_get("evidence[0].can_take", area) == 1
    assert live_get("evidence[0].editable", area) == 0


def test_live_get_evidence_index_expression():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    area.evi_list.evidences.append(EvidenceList.Evidence("A", "1", "", "all"))
    area.evi_list.evidences.append(EvidenceList.Evidence("B", "2", "", "all"))
    assert live_get("evidence[i].name", area, {"i": 1}) == "B"
    assert live_get("evidence[0].name", area, {"i": 1}) == "A"


def test_live_get_link_fields():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    area.links = {
        "3": {
            "locked": True,
            "hidden": False,
            "target_pos": "stand",
            "can_peek": True,
            "evidence": [1, 2],
            "password": "abc",
        },
        "5": {"locked": False, "hidden": True, "target_pos": "", "can_peek": False, "evidence": [], "password": ""},
    }
    assert live_get("links.count", area) == 2
    assert live_get("links[0].target", area) == "3"
    assert live_get("links[0].locked", area) == 1
    assert live_get("links[0].hidden", area) == 0
    assert live_get("links[0].target_pos", area) == "stand"
    assert live_get("links[0].can_peek", area) == 1
    assert live_get("links[0].evidence", area) == "1 2"
    assert live_get("links[0].password", area) == "abc"
    assert live_get("links[1].target", area) == "5"
    assert live_get("links[1].locked", area) == 0


def test_live_get_evidence_and_link_errors():
    from server.scripting import live_get, ScriptingError

    area = FakeBroadcastArea()
    area.evi_list.evidences.append(EvidenceList.Evidence("A", "1", "", "all"))
    area.links = {
        "3": {"locked": False, "hidden": False, "target_pos": "", "can_peek": True, "evidence": [], "password": ""}
    }
    with pytest.raises(ScriptingError, match="Evidence index"):
        live_get("evidence[5].name", area)
    with pytest.raises(ScriptingError, match="Unknown evidence field"):
        live_get("evidence[0].bogus", area)
    for field in ("hiding_client", "triggers"):
        with pytest.raises(ScriptingError):
            live_get(f"evidence[0].{field}", area)
    with pytest.raises(ScriptingError, match="Link index"):
        live_get("links[2].locked", area)
    with pytest.raises(ScriptingError, match="Unknown link field"):
        live_get("links[0].bogus", area)
    with pytest.raises(ScriptingError):
        live_get("links[1.5].locked", area)


def test_script_runner_iterates_evidence(fake_loop):
    area = FakeBroadcastArea()
    area.evi_list.evidences.append(EvidenceList.Evidence("Letter", "A", "", "all"))
    area.evi_list.evidences.append(EvidenceList.Evidence("Badge", "B", "", "all"))
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("get", "count", "evidence.count"),
            ("set", "i", "0"),
            ("set", "list", '""'),
            ("label", "loop"),
            ("if", "i", "ge", "count", "done"),
            ("get", "item", "evidence[i].name"),
            ("concat", "list", "item", '", "'),
            ("set", "i", "i+1"),
            ("goto", "loop"),
            ("label", "done"),
            ("packet", "CT", ("narrator", "<!list>")),
        ]
    )
    # get count -> set i -> set list -> label -> if (false) -> get -> concat
    # -> set i -> goto -> label -> if (false) -> get -> concat -> set i -> goto
    # -> label -> if (true, jump to done) -> label done -> packet -> finish.
    for _ in range(20):
        fake_loop.pop_next()

    assert area.variables["count"] == 2
    assert area.sent[-1] == ("CT", "narrator", "Letter, Badge")
    assert runner.running is False


def test_script_runner_iterates_links(fake_loop):
    area = FakeBroadcastArea()
    area.links = {
        "3": {"locked": True, "hidden": False, "target_pos": "", "can_peek": True, "evidence": [], "password": "abc"},
        "5": {"locked": False, "hidden": False, "target_pos": "", "can_peek": True, "evidence": [], "password": ""},
    }
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("get", "count", "links.count"),
            ("set", "i", "0"),
            ("set", "list", '""'),
            ("label", "loop"),
            ("if", "i", "ge", "count", "done"),
            ("get", "target", "links[i].target"),
            ("get", "locked", "links[i].locked"),
            ("concat", "list", "target", '", "'),
            ("set", "i", "i+1"),
            ("goto", "loop"),
            ("label", "done"),
            ("packet", "CT", ("narrator", "<!list>")),
        ]
    )
    # Same shape as the evidence loop with two iterations: the loop body now
    # has two `get` instructions, so 20 + 2 = 22 steps total.
    for _ in range(22):
        fake_loop.pop_next()

    assert area.sent[-1] == ("CT", "narrator", "3, 5")
    assert runner.running is False


def test_script_runner_get_excludes_system_client(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("get", "total", "clients.count")])
    area.clients = {
        FakeScriptClient(1, "Miles"),
        FakeScriptClient(2, "System", ipid=0),
    }

    fake_loop.pop_next()

    assert area.variables["total"] == 1

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_live_get_client_hidden_and_listen_fields():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    client = FakeScriptClient(1, "Miles")
    area.clients = {client}
    assert live_get("client[0].hidden_in", area) == ""
    assert live_get("client[0].listen_pos", area) == ""
    client.hidden_in = 3
    client.listen_pos = ["wit", "stand"]
    assert live_get("client[0].hidden_in", area) == 3
    assert live_get("client[0].listen_pos", area) == "wit stand"


def test_live_get_evidence_hiding_field():
    from server.scripting import live_get

    area = FakeBroadcastArea()
    evi = EvidenceList.Evidence("Letter", "A", "", "all")
    area.evi_list.evidences.append(evi)
    assert live_get("evidence[0].hiding", area) == ""
    evi.hiding_client = FakeScriptClient(1, "Miles")
    assert live_get("evidence[0].hiding", area) == "Miles"


def test_live_get_afk_source():
    from server.scripting import live_get, ScriptingError

    area = FakeBroadcastArea()
    area.afkers = [FakeScriptClient(1, "Miles"), FakeScriptClient(2, "Apollo")]
    assert live_get("afk.count", area) == 2
    assert live_get("afk[0].showname", area) == "Miles"
    assert live_get("afk[0].pos", area) == "wit"
    # System clients are hidden from the AFK list too.
    area.afkers.append(FakeScriptClient(3, "System", ipid=0))
    assert live_get("afk.count", area) == 2
    with pytest.raises(ScriptingError, match="AFK index"):
        live_get("afk[2].showname", area)
    with pytest.raises(ScriptingError):
        live_get("afk[0].bogus_field", area)


def test_live_get_char_source(make_area):
    from server.scripting import live_get, ScriptingError

    area = make_area()
    hub = area.area_manager
    hub.char_list = ["Phoenix", "Edgeworth"]
    hub.character_data = {
        "Phoenix": {"title": "Attorney", "points": 3, "tags": ["a", "b"]},
        "Edgeworth": {"title": "Prosecutor"},
    }
    assert live_get("char[0].title", area) == "Attorney"
    assert live_get('char["Phoenix"].title', area) == "Attorney"
    assert live_get('char["Phoenix"].points', area) == 3
    assert live_get('char["Phoenix"].tags', area) == "a b"
    assert live_get('char["Phoenix"].missing', area) == ""
    assert live_get('char["Phoenix"].count', area) == 3
    assert live_get('char["Phoenix"].fields', area) == "title points tags"
    assert live_get("char[1].title", area) == "Prosecutor"
    assert live_get('char["Bogus"].anything', area) == ""
    with pytest.raises(ScriptingError, match="Unknown source"):
        live_get("char.count", area)
    with pytest.raises(ScriptingError, match="Unknown source"):
        live_get("bogus.count", area)
    with pytest.raises(ScriptingError, match="Unknown source"):
        live_get("bogus[0].x", area)
    with pytest.raises(ScriptingError):
        live_get("char[Edgeworth].title", area)


def test_script_runner_save_char_data(fake_loop):
    area = FakeBroadcastArea()
    area.area_manager.char_list = ["Phoenix", "Edgeworth"]
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start(
        [
            ("save", '"Phoenix"', "title", '"Attorney"'),
            ("save", "0", "points", "5"),
            ("get", "got", 'char["Phoenix"].title'),
            ("packet", "CT", ("narrator", "<!got>")),
        ]
    )
    fake_loop.pop_next()  # save title
    fake_loop.pop_next()  # save points
    fake_loop.pop_next()  # get title from saved data
    fake_loop.pop_next()  # broadcast CT with getter

    assert area.area_manager.character_data["Phoenix"]["title"] == "Attorney"
    assert area.area_manager.character_data["Phoenix"]["points"] == 5
    assert area.area_manager.saved_paths == [None, None]
    assert area.sent[-1] == ("CT", "narrator", "Attorney")

    fake_loop.pop_next()  # queue exhausted
    assert runner.running is False


def test_script_runner_save_unknown_char_stops(fake_loop):
    area = FakeBroadcastArea()
    executor = FakeExecutor()
    runner = ScriptRunner(area, executor)
    runner.start([("save", "999", "title", '"x"')])

    fake_loop.pop_next()

    assert any("Unknown character id 999" in m for m in area.ooc)
    assert runner.running is False


def test_ooc_get_set_char_data():
    from server.commands.character import ooc_cmd_get_char_data, ooc_cmd_set_char_data

    area = FakeBroadcastArea()
    area.area_manager.char_list = ["Phoenix", "Edgeworth"]
    out = []
    client = SimpleNamespace(area=area, is_mod=True, send_ooc=out.append)

    ooc_cmd_set_char_data(client, "0 title Attorney")
    assert area.area_manager.character_data["Phoenix"]["title"] == "Attorney"
    assert area.area_manager.saved_paths == [None]

    ooc_cmd_get_char_data(client, "phoenix title")
    assert any("title = Attorney" in m for m in out)

    out.clear()
    ooc_cmd_get_char_data(client, "phoenix")
    assert any("Phoenix.title = Attorney" in m for m in out)

    ooc_cmd_set_char_data(client, "phoenix title")
    assert "title" not in area.area_manager.character_data["Phoenix"]
    assert len(area.area_manager.saved_paths) == 2


def test_ooc_set_char_data_unknown_char():
    from server.commands.character import ooc_cmd_set_char_data
    from server.exceptions import ArgumentError

    area = FakeBroadcastArea()
    area.area_manager.char_list = ["Phoenix"]
    client = SimpleNamespace(area=area, is_mod=True, send_ooc=lambda m: None)
    with pytest.raises(ArgumentError, match="Unknown character id"):
        ooc_cmd_set_char_data(client, "999 title x")
    with pytest.raises(ArgumentError, match="Unknown character"):
        ooc_cmd_set_char_data(client, "Bogus title x")
