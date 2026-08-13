"""Tests for GM-panel remote-login hub binding.

Covers the ``gm_panel.users`` ``hubs`` config option, the occupancy predicate
("any hub GM at all, including in-game ``real_owners()``"), the two-phase
``gm`` login (``login`` -> hub options -> ``complete_hub_login``), and the
"one account, one hub" guard.
"""

from server.web_view.gm_panel import sessions
from server.web_view.gm_panel.sessions import GMSessionManager


class FakeHub:
    def __init__(self, hub_id, name="Hub", owners=None):
        self.id = hub_id
        self.name = name
        self.areas = [object()]  # non-empty so the hub is resolvable/bindable
        self._owners = set(owners or [])

    def real_owners(self):
        return self._owners

    def default_area(self):
        return self.areas[0]


class FakeHubManager:
    def __init__(self, hubs):
        self.hubs = hubs


class FakeServer:
    def __init__(self, hubs):
        self.hub_manager = FakeHubManager(hubs)


class FakeSession:
    """Stands in for a live ``RemoteSession`` in ``_remote_sessions``."""

    def __init__(self, user, hub, role="gm", valid=True):
        self._user = user
        self._hub = hub
        self._role = role
        self._valid = valid

    @property
    def user(self):
        return self._user

    @property
    def role(self):
        return self._role

    def is_valid(self):
        return self._valid

    def current_hub(self):
        return self._hub


def _make_manager(hubs, users):
    return GMSessionManager(FakeServer(hubs), {"users": users})


def _inject_session(manager, token, session):
    manager._remote_sessions[token] = session


# --- _parse_users ----------------------------------------------------------

def test_parse_users_hubs_list():
    users = GMSessionManager._parse_users({
        "alice": {"password": "pw", "role": "gm", "hubs": [0, 2, 2]},
    })
    assert users["alice"]["role"] == "gm"
    assert users["alice"]["hubs"] == frozenset({0, 2})


def test_parse_users_hubs_omitted_is_unrestricted():
    users = GMSessionManager._parse_users({
        "alice": {"password": "pw", "role": "gm"},
    })
    assert users["alice"]["hubs"] is None


def test_parse_users_hubs_ignores_non_numeric():
    users = GMSessionManager._parse_users({
        "alice": {"password": "pw", "role": "gm", "hubs": [0, "x", -1, "1"]},
    })
    assert users["alice"]["hubs"] == frozenset({0, 1})


def test_parse_users_admin_ignores_hubs():
    users = GMSessionManager._parse_users({
        "root": {"password": "pw", "role": "admin", "hubs": [0, 1]},
    })
    assert users["root"]["role"] == "admin"
    assert users["root"]["hubs"] is None


def test_parse_users_legacy_scalar_entry_defaults_admin():
    users = GMSessionManager._parse_users({"root": "pw"})
    assert users["root"]["password"] == "pw"
    assert users["root"]["role"] == "admin"
    assert users["root"]["hubs"] is None


# --- occupancy / claim -----------------------------------------------------

def test_hub_has_gm_in_game_owner():
    hub0 = FakeHub(0, owners=[object()])
    manager = _make_manager([hub0], {})
    assert manager.hub_has_gm(hub0) is True


def test_hub_has_gm_remote_session():
    hub0 = FakeHub(0)
    hub1 = FakeHub(1)
    manager = _make_manager([hub0, hub1], {})
    _inject_session(manager, "t", FakeSession("alice", hub0))
    assert manager.hub_has_gm(hub0) is True
    assert manager.hub_has_gm(hub1) is False


def test_hub_claim_error_in_game_owner():
    hub = FakeHub(0, owners=[object()])
    manager = _make_manager([hub], {})
    assert manager._hub_claim_error(hub, "alice") == "hub_occupied"


def test_hub_claim_error_occupied_by_other_account():
    hub = FakeHub(0)
    manager = _make_manager([hub], {})
    _inject_session(manager, "t", FakeSession("bob", hub))
    assert manager._hub_claim_error(hub, "alice") == "hub_occupied"


def test_hub_claim_error_already_bound_different_hub():
    hub0 = FakeHub(0)
    hub1 = FakeHub(1)
    manager = _make_manager([hub0, hub1], {})
    _inject_session(manager, "t", FakeSession("alice", hub0))
    assert manager._hub_claim_error(hub1, "alice") == "already_bound_hub"


def test_hub_claim_error_own_same_hub_allowed():
    hub0 = FakeHub(0)
    manager = _make_manager([hub0], {})
    _inject_session(manager, "t", FakeSession("alice", hub0))
    assert manager._hub_claim_error(hub0, "alice") is None


def test_hub_claim_error_free_hub_allowed():
    hub0 = FakeHub(0)
    manager = _make_manager([hub0], {})
    assert manager._hub_claim_error(hub0, "alice") is None


def test_hub_options_flags():
    hub0 = FakeHub(0, "Free")
    hub1 = FakeHub(1, "Taken", owners=[object()])
    manager = _make_manager([hub0, hub1], {})
    _inject_session(manager, "t", FakeSession("alice", hub0))

    options = manager.hub_options_for("alice", {"hubs": None})
    by_id = {o["id"]: o for o in options}

    # Own current hub: selectable, flagged self_bound, not occupied.
    assert by_id[0] == {
        "id": 0, "name": "Free", "occupied": False, "self_bound": True, "blocked": False,
    }
    # In-game-GM hub: occupied, blocked (account already bound elsewhere).
    assert by_id[1]["occupied"] is True
    assert by_id[1]["blocked"] is True
    assert by_id[1]["self_bound"] is False


def test_resolve_allowed_hubs_skips_unknown_and_empty():
    hub0 = FakeHub(0)
    hub1 = FakeHub(1)
    empty = FakeHub(2)
    empty.areas = []
    manager = _make_manager([hub0, hub1, empty], {})
    resolved = manager._resolve_allowed_hubs({"hubs": frozenset({1, 2, 99})})
    assert [h.id for h in resolved] == [1]


# --- two-phase gm login ----------------------------------------------------

def test_login_gm_returns_hub_options():
    hub0 = FakeHub(0, "Hub 0")
    hub1 = FakeHub(1, "Hub 1")
    manager = _make_manager([hub0, hub1], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0, 1]},
    })

    result, error = manager.login("gmuser", "pw", "1.2.3.4")
    assert error is None
    assert result["pre_auth"]
    assert [o["id"] for o in result["hubs"]] == [0, 1]
    assert result["ttl"] > 0
    # No session minted yet.
    assert manager._remote_sessions == {}


def test_login_gm_no_hubs_config_means_all_hubs():
    hubs = [FakeHub(0), FakeHub(1), FakeHub(2)]
    manager = _make_manager(hubs, {"gmuser": {"password": "pw", "role": "gm"}})

    result, error = manager.login("gmuser", "pw", "1.2.3.4")
    assert error is None
    assert [o["id"] for o in result["hubs"]] == [0, 1, 2]


def test_login_gm_all_hubs_occupied():
    hub0 = FakeHub(0, owners=[object()])
    hub1 = FakeHub(1)
    manager = _make_manager([hub0, hub1], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0, 1]},
    })
    _inject_session(manager, "t", FakeSession("bob", hub1))

    result, error = manager.login("gmuser", "pw", "1.2.3.4")
    assert result is None
    assert error == "all_hubs_occupied"


def test_login_gm_bad_credentials():
    manager = _make_manager([FakeHub(0)], {
        "gmuser": {"password": "pw", "role": "gm"},
    })
    result, error = manager.login("gmuser", "wrong", "1.2.3.4")
    assert result is None
    assert error == "invalid_credentials"


def test_login_admin_returns_session(monkeypatch):
    manager = _make_manager([FakeHub(0)], {
        "root": {"password": "pw", "role": "admin"},
    })
    made = {}

    class FakeClient:
        def __init__(self, server, is_mod=True, is_gm=False, name="[SYSTEM]"):
            self.server = server
            self.is_mod = is_mod
            self.is_gm = is_gm
            self.name = name
            self.area = None

        def join_area(self, area=None):
            self.area = area

    class FakeAdminSession:
        def __init__(self, server, client, user, ttl):
            self.server = server
            self.client = client
            self.user = user
            self.ttl = ttl

        @property
        def role(self):
            return "admin"

    def make_client(*a, **k):
        made["client"] = FakeClient(*a, **k)
        return made["client"]

    def make_session(*a, **k):
        made["session"] = FakeAdminSession(*a, **k)
        return made["session"]

    monkeypatch.setattr(sessions, "RemoteClient", make_client)
    monkeypatch.setattr(sessions, "AdminSession", make_session)

    result, error = manager.login("root", "pw", "1.2.3.4")
    assert error is None
    assert result["token"] in manager._remote_sessions
    assert result["session"] is made["session"]
    assert result["session"].user == "root"


# --- complete_hub_login ----------------------------------------------------

def test_complete_hub_login_binds_chosen_hub(monkeypatch):
    hub0 = FakeHub(0, "Hub 0")
    hub1 = FakeHub(1, "Hub 1")
    manager = _make_manager([hub0, hub1], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0, 1]},
    })
    result, _ = manager.login("gmuser", "pw", "1.2.3.4")

    made = {}

    class FakeClient:
        def __init__(self, server, is_mod=True, is_gm=False, name="[SYSTEM]"):
            self.server = server
            self.is_mod = is_mod
            self.is_gm = is_gm
            self.name = name
            self.area = None

        def join_area(self, area=None):
            self.area = area

    class FakeRemoteSession:
        def __init__(self, server, client, user, ttl):
            self.server = server
            self.client = client
            self.user = user
            self.ttl = ttl

    def make_client(*a, **k):
        made["client"] = FakeClient(*a, **k)
        return made["client"]

    def make_session(*a, **k):
        made["session"] = FakeRemoteSession(*a, **k)
        return made["session"]

    monkeypatch.setattr(sessions, "RemoteClient", make_client)
    monkeypatch.setattr(sessions, "RemoteSession", make_session)

    res, error = manager.complete_hub_login(result["pre_auth"], 1)
    assert error is None
    assert made["client"].is_gm is True
    assert made["client"].area is hub1.default_area()
    assert made["session"].user == "gmuser"
    assert res["token"] in manager._remote_sessions
    # Pre-auth is single-use.
    assert manager._pending_hub_auths == {}


def test_complete_hub_login_rejects_occupied(monkeypatch):
    hub0 = FakeHub(0, owners=[object()])
    manager = _make_manager([hub0], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0]},
    })
    # In-game owner occupies hub 0 -> login phase A rejects outright.
    _, error = manager.login("gmuser", "pw", "1.2.3.4")
    assert error == "all_hubs_occupied"


def test_complete_hub_login_rejects_invalid_hub(monkeypatch):
    hub0 = FakeHub(0)
    manager = _make_manager([hub0], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0]},
    })
    result, _ = manager.login("gmuser", "pw", "1.2.3.4")

    res, error = manager.complete_hub_login(result["pre_auth"], 99)
    assert res is None
    assert error == "invalid_hub"


def test_complete_hub_login_rejects_expired_pre_auth():
    hub0 = FakeHub(0)
    manager = _make_manager([hub0], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0]},
    })
    res, error = manager.complete_hub_login("bogus", 0)
    assert res is None
    assert error == "invalid_or_expired_token"


def test_complete_hub_login_rejects_already_bound_hub(monkeypatch):
    hub0 = FakeHub(0, "Hub 0")
    hub1 = FakeHub(1, "Hub 1")
    manager = _make_manager([hub0, hub1], {
        "gmuser": {"password": "pw", "role": "gm", "hubs": [0, 1]},
    })
    # Account already holds hub 0 via an existing remote session.
    _inject_session(manager, "t", FakeSession("gmuser", hub0))
    result, _ = manager.login("gmuser", "pw", "1.2.3.4")

    class FakeClient:
        def __init__(self, server, is_mod=True, is_gm=False, name="[SYSTEM]"):
            self.area = None

        def join_area(self, area=None):
            self.area = area

    monkeypatch.setattr(sessions, "RemoteClient", FakeClient)

    res, error = manager.complete_hub_login(result["pre_auth"], 1)
    assert res is None
    assert error == "already_bound_hub"
