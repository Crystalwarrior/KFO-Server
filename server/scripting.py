"""
Safe arithmetic expression evaluation for demo scripting.

Standardizes the math engine behind `/roll` modifiers and the demo `set`/`get`
instructions: one whitelist, one set of error messages, one security posture.

Expressions support numbers, `+ - * / ( )`, and bare identifiers that are
substituted from the caller's variable/source dictionaries. Everything else is
rejected before evaluation, and `eval` runs with no builtins available.

`resolve_value` is the general operand resolver: quoted strings become string
literals, bare identifiers copy their stored value (number or string), and
anything else is evaluated as an arithmetic expression.

`live_get` is the structured live-state resolver used by `get` and inline
getters: `clients.count`, `client[i].<field>`, `area.<field>`, `hub.<field>`,
`timer[i].<field>`. Every field is read through an explicit whitelist, never
raw `getattr`, and `client[i]` indexes a deterministic `/getarea`-ordered
snapshot.
"""

import re

from server.constants import _SYSTEM_IPID
from server.exceptions import ArgumentError

# Characters allowed in an expression after identifier substitution.
ALLOWED_CHARS = "0123456789+-*/(). "

# A bare identifier: a variable or source name to substitute with its value.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# An inline getter: `<!name>` (or `<!path>`) substituted with a value.
_PLACEHOLDER = re.compile(r"<!([^>]+)>")

# A quoted string literal, either single- or double-quoted.
_QUOTED = re.compile(r'^(?:"([^"]*)"|\'([^\']*)\')$')

# A structured live source path (see `live_get`).
_LIVE_PATH = re.compile(
    r"^(clients\.count"
    r"|client\[[^\]]+\]\.[A-Za-z_][A-Za-z0-9_]*"
    r"|timer\[[^\]]+\]\.[A-Za-z_][A-Za-z0-9_]*"
    r"|area\.[A-Za-z_][A-Za-z0-9_]*"
    r"|hub\.[A-Za-z_][A-Za-z0-9_]*)$"
)

# Client field access: `client[i].<field>`.
_CLIENT_INDEX = re.compile(r"^client\[([^\]]+)\]\.([A-Za-z_][A-Za-z0-9_]*)$")
# Timer field access: `timer[i].<field>`.
_TIMER_INDEX = re.compile(r"^timer\[([^\]]+)\]\.([A-Za-z_][A-Za-z0-9_]*)$")
# Area/hub field access: `area.<field>` / `hub.<field>`.
_SCOPE_FIELD = re.compile(r"^(area|hub)\.([A-Za-z_][A-Za-z0-9_]*)$")

# Maximum magnitude of any single numeric term, mirroring the `/roll` lag guard.
MAX_TERM = 10**6


class ScriptingError(ArgumentError):
    """Raised when a scripting expression cannot be evaluated."""


class DivisionByZeroError(ScriptingError):
    """Raised when an expression divides by zero (so callers can retry)."""


def evaluate_expression(expr, variables=None, sources=None):
    """
    Evaluate an arithmetic expression with variable substitution.

    `variables` and `sources` are dicts of name -> number. Identifiers in the
    expression are replaced with their values; any identifier that isn't
    present raises a `ScriptingError`. Returns a number (int or float).
    """
    if variables is None:
        variables = {}
    if sources is None:
        sources = {}
    expr = expr.strip()
    if not expr:
        raise ScriptingError("Empty expression.")
    if "**" in expr:
        raise ScriptingError("Exponentiation is not allowed in expressions.")

    def _substitute(match):
        name = match.group(0)
        if name in variables:
            return str(variables[name])
        if name in sources:
            return str(sources[name])
        raise ScriptingError(f"Unknown variable '{name}' in expression.")

    substituted = _IDENTIFIER.sub(_substitute, expr)

    for ch in substituted:
        if ch not in ALLOWED_CHARS:
            raise ScriptingError("Expected numbers and standard mathematical operations in expression")

    # Prevent any term from reaching past MAX_TERM to avoid server lag from
    # frivolous expressions.
    terms = substituted
    for op in "+-*/()":
        terms = terms.replace(op, "!")
    for term in terms.split("!"):
        if term == "":
            continue
        try:
            if abs(round(float(term))) > MAX_TERM:
                raise ScriptingError("Expression takes numbers past the server's computation limit")
        except ValueError:
            raise ScriptingError("Expression has a syntax error and cannot be computed")

    try:
        return eval(substituted, {"__builtins__": {}}, {})
    except ZeroDivisionError:
        raise DivisionByZeroError("Expression divides by zero.")
    except (SyntaxError, TypeError, NameError):
        raise ScriptingError("Expression has a syntax error and cannot be computed")


def resolve_value(text, variables=None, sources=None):
    """
    Resolve an operand to a value (number or string).

    A quoted string (`"..."` or `'...'`) becomes a string literal. A bare
    identifier that names a variable or source copies its stored value, so
    `set b a` copies `a` whether it holds a number or a string. Anything else
    is evaluated as an arithmetic expression and yields a number.
    """
    if variables is None:
        variables = {}
    if sources is None:
        sources = {}
    text = text.strip()
    quoted = _QUOTED.match(text)
    if quoted:
        return quoted.group(1) if quoted.group(1) is not None else quoted.group(2)
    if _IDENTIFIER.fullmatch(text):
        if text in variables:
            return variables[text]
        if text in sources:
            return sources[text]
        raise ScriptingError(f"Unknown variable '{text}'.")
    return evaluate_expression(text, variables, sources)


# Whitelisted client fields (keys are what scripts write; values are read-only).
_CLIENT_FIELDS = {
    "id": lambda c, a: c.id,
    "char_id": lambda c, a: c.char_id,
    "char_name": lambda c, a: c.char_name,
    "showname": lambda c, a: c.showname,
    "name": lambda c, a: c.name,
    "pos": lambda c, a: c.pos,
    "pair": lambda c, a: c.charid_pair,
    "is_cm": lambda c, a: int(c in a._owners),
    "is_gm": lambda c, a: int(c in a.area_manager.owners),
    "is_owner": lambda c, a: int(c in a.owners),
    "is_afk": lambda c, a: int(c in a.afkers),
    "hidden": lambda c, a: int(c.hidden),
    "blinded": lambda c, a: int(c.blinded),
    "sneaking": lambda c, a: int(c.sneaking),
    "frozen": lambda c, a: int(c.frozen),
    "iniswap": lambda c, a: c.iniswap,
    "last_move_time": lambda c, a: c.last_move_time,
    "remote_listen": lambda c, a: c.remote_listen,
    "subtheme": lambda c, a: c.subtheme,
    "time_of_day": lambda c, a: c.time_of_day,
    "char_url": lambda c, a: c.char_url,
}


def _client_char_folder(client, area):
    """The client's character folder, mirroring /getarea's derivation."""
    char_id = client.char_id
    if char_id is None or char_id < 0 or char_id >= len(area.area_manager.char_list):
        return "Spectator"
    return area.area_manager.char_list[char_id]


def _client_field(client, area, field):
    if field == "char_folder":
        return _client_char_folder(client, area)
    if field in _CLIENT_FIELDS:
        return _CLIENT_FIELDS[field](client, area)
    raise ScriptingError(f"Unknown client field '{field}'.")


# Whitelisted area fields.
_AREA_FIELDS = {
    # Identity & description
    "name": lambda a: a.name,
    "id": lambda a: a.id,
    "abbreviation": lambda a: a.abbreviation,
    "desc": lambda a: a.desc,
    "status": lambda a: a.status,
    "doc": lambda a: a.doc,
    # Background, overlay & position
    "background": lambda a: a.background,
    "background_dark": lambda a: a.background_dark,
    "background_suffix": lambda a: a.background_suffix,
    "overlay": lambda a: a.overlay,
    "pos_lock": lambda a: " ".join(a.pos_lock),
    "bg_lock": lambda a: int(a.bg_lock),
    "overlay_lock": lambda a: int(a.overlay_lock),
    "pos_dark": lambda a: a.pos_dark,
    "desc_dark": lambda a: a.desc_dark,
    "dark": lambda a: int(a.dark),
    # Permissions & behavior
    "can_cm": lambda a: int(a.can_cm),
    "locking_allowed": lambda a: int(a.locking_allowed),
    "iniswap_allowed": lambda a: int(a.iniswap_allowed),
    "showname_changes_allowed": lambda a: int(a.showname_changes_allowed),
    "shouts_allowed": lambda a: int(a.shouts_allowed),
    "non_int_pres_only": lambda a: int(a.non_int_pres_only),
    "evidence_mod": lambda a: a.evidence_mod,
    "blankposting_allowed": lambda a: int(a.blankposting_allowed),
    "blankposting_forced": lambda a: int(a.blankposting_forced),
    "ooc_actions_enabled": lambda a: int(a.ooc_actions_enabled),
    "present_reveals_evidence": lambda a: int(a.present_reveals_evidence),
    "passing_msg": lambda a: int(a.passing_msg),
    "can_whisper": lambda a: int(a.can_whisper),
    "can_wtce": lambda a: int(a.can_wtce),
    "can_change_status": lambda a: int(a.can_change_status),
    "can_spectate": lambda a: int(a.can_spectate),
    "can_getarea": lambda a: int(a.can_getarea),
    "use_backgrounds_yaml": lambda a: int(a.use_backgrounds_yaml),
    "hide_clients": lambda a: int(a.hide_clients),
    "force_sneak": lambda a: int(a.force_sneak),
    "locked": lambda a: int(a.locked),
    "muted": lambda a: int(a.muted),
    "password": lambda a: a.password,
    "hidden": lambda a: int(a.hidden),
    "max_players": lambda a: a.max_players,
    "hp_def": lambda a: a.hp_def,
    "hp_pro": lambda a: a.hp_pro,
    "move_delay": lambda a: a.move_delay,
    "msg_delay": lambda a: a.msg_delay,
    "medieval_mode": lambda a: int(a.medieval_mode),
    # Music
    "music": lambda a: a.music,
    "music_autoplay": lambda a: int(a.music_autoplay),
    "music_looping": lambda a: a.music_looping,
    "music_effects": lambda a: a.music_effects,
    "music_ref": lambda a: a.music_ref,
    "replace_music": lambda a: int(a.replace_music),
    "client_music": lambda a: int(a.client_music),
    "ambience": lambda a: a.ambience,
    "can_dj": lambda a: int(a.can_dj),
    "jukebox": lambda a: int(a.jukebox),
    "music_locked": lambda a: int(a.music_locked),
    # Minigames
    "can_battle": lambda a: int(a.can_battle),
    "auto_pair": lambda a: int(a.auto_pair),
    "auto_pair_max": lambda a: a.auto_pair_max,
    "auto_pair_cycle": lambda a: int(a.auto_pair_cycle),
    "can_cross_swords": lambda a: int(a.can_cross_swords),
    "can_scrum_debate": lambda a: int(a.can_scrum_debate),
    "can_panic_talk_action": lambda a: int(a.can_panic_talk_action),
    "cross_swords_song_start": lambda a: a.cross_swords_song_start,
    "cross_swords_song_end": lambda a: a.cross_swords_song_end,
    "cross_swords_song_concede": lambda a: a.cross_swords_song_concede,
    "scrum_debate_song_start": lambda a: a.scrum_debate_song_start,
    "scrum_debate_song_end": lambda a: a.scrum_debate_song_end,
    "scrum_debate_song_concede": lambda a: a.scrum_debate_song_concede,
    "panic_talk_action_song_start": lambda a: a.panic_talk_action_song_start,
    "panic_talk_action_song_end": lambda a: a.panic_talk_action_song_end,
    "panic_talk_action_song_concede": lambda a: a.panic_talk_action_song_concede,
}


def _area_field(area, field):
    if field in _AREA_FIELDS:
        return _AREA_FIELDS[field](area)
    raise ScriptingError(f"Unknown area field '{field}'.")


# Whitelisted hub (AreaManager) fields.
_HUB_FIELDS = {
    "name": lambda h: h.name,
    "id": lambda h: h.id,
    "abbreviation": lambda h: h.abbreviation,
    "subtheme": lambda h: h.subtheme,
    "time_of_day": lambda h: h.time_of_day,
    "doc": lambda h: h.info,
    "info": lambda h: h.info,
    "char_count": lambda h: len(h.char_list),
    "char_list_ref": lambda h: h.char_list_ref,
    "music_ref": lambda h: h.music_ref,
    "move_delay": lambda h: h.move_delay,
    "arup_enabled": lambda h: int(h.arup_enabled),
    "can_gm": lambda h: int(h.can_gm),
    "single_cm": lambda h: int(h.single_cm),
    "hide_clients": lambda h: int(h.hide_clients),
    "replace_music": lambda h: int(h.replace_music),
    "client_music": lambda h: int(h.client_music),
    "max_areas": lambda h: h.max_areas,
    "can_spectate": lambda h: int(h.can_spectate),
    "can_getareas": lambda h: int(h.can_getareas),
    "passing_msg": lambda h: int(h.passing_msg),
    "autokick_to_latest_area": lambda h: int(h.autokick_to_latest_area),
    "current_areas": lambda h: len(h.areas),
}


def _hub_field(hub, field):
    if field in _HUB_FIELDS:
        return _HUB_FIELDS[field](hub)
    raise ScriptingError(f"Unknown hub field '{field}'.")


def _visible_clients(area):
    """Clients in the area excluding system/executor clients (ipid 0)."""
    return [c for c in getattr(area, "clients", ()) if getattr(c, "ipid", -1) != _SYSTEM_IPID]


def _join_order_key(area, client):
    """Role/status ordering used by /getarea (see `get_area_clients`)."""
    if client in area.afkers:
        return 1
    if client.hidden:
        return 2
    if client.char_id == -1:
        return 3
    if client in area._owners:
        return 4
    if client in area.area_manager.owners:
        return 5
    if client.is_mod:
        return 6
    return 0


def _client_snapshot(area):
    """Deterministic /getarea-ordered list of visible clients."""
    clients = _visible_clients(area)
    return sorted(sorted(clients, key=lambda c: c.showname), key=lambda c: _join_order_key(area, c))


def _resolve_index(text, area, variables, what="Client"):
    """Resolve an index like `client[i]`/`timer[i]`: a whole number, from a
    variable or expression."""
    index = resolve_value(text, variables, live_sources(area))
    if isinstance(index, bool):
        raise ScriptingError(f"{what} index '{text}' is not a whole number.")
    if isinstance(index, float):
        if not index.is_integer():
            raise ScriptingError(f"{what} index '{text}' is not a whole number.")
        index = int(index)
    elif not isinstance(index, int):
        raise ScriptingError(f"{what} index '{text}' is not a number.")
    return index


def _timer_remaining_ms(timer):
    """Milliseconds left on a timer (static time if paused, 0 if unset)."""
    if not timer.set:
        return 0
    if timer.started:
        import arrow

        remaining = timer.target - arrow.get()
    else:
        remaining = timer.static
    if remaining is None:
        return 0
    return int(remaining.total_seconds()) * 1000


def _timer_static_ms(timer):
    """The timer's set duration in milliseconds (0 if unset)."""
    if timer.static is None:
        return 0
    return int(timer.static.total_seconds()) * 1000


# Whitelisted timer fields. Timer 0 is the hub-wide timer; timers 1-20 are the
# area's own, matching the IDs shown by `/timer`.
_TIMER_FIELDS = {
    "set": lambda t, a: int(t.set),
    "started": lambda t, a: int(t.started),
    "remaining_ms": lambda t, a: _timer_remaining_ms(t),
    "static_ms": lambda t, a: _timer_static_ms(t),
}


def _area_timer(area, index):
    """Look up a timer by its user-facing ID (0 = hub timer, 1-20 = area)."""
    if index == 0:
        timer = getattr(getattr(area, "area_manager", None), "timer", None)
        if timer is None:
            raise ScriptingError("No hub timer available.")
        return timer
    if index < 0:
        raise ScriptingError(f"Timer index {index} is not valid (use 0 to {len(getattr(area, 'timers', ()) or ())}).")
    timers = getattr(area, "timers", ()) or ()
    if index - 1 >= len(timers):
        raise ScriptingError(f"Timer index {index} is out of range (0 to {len(timers)}).")
    return timers[index - 1]


def _timer_field(timer, area, field):
    if field in _TIMER_FIELDS:
        return _TIMER_FIELDS[field](timer, area)
    raise ScriptingError(f"Unknown timer field '{field}'.")


def live_get(path, area, variables=None):
    """
    Resolve a structured live-state path.

    Supported paths:
    - `clients.count`                      -- number of real clients in the area
    - `client[<i>].<field>`                -- one client's whitelisted field
    - `timer[<i>].<field>`                 -- a timer's state (0 = hub-wide)
    - `area.<field>` / `hub.<field>`       -- whitelisted area/hub properties

    `<i>` is resolved as an operand (a bare variable or an arithmetic
    expression). Unknown paths/fields and out-of-range indexes raise
    `ScriptingError`.
    """
    if variables is None:
        variables = {}
    path = path.strip()
    if path == "clients.count":
        return len(_visible_clients(area))
    client_match = _CLIENT_INDEX.match(path)
    if client_match:
        index = _resolve_index(client_match.group(1), area, variables)
        clients = _client_snapshot(area)
        if not 0 <= index < len(clients):
            raise ScriptingError(f"Client index {index} out of range (0 to {len(clients) - 1}).")
        return _client_field(clients[index], area, client_match.group(2))
    timer_match = _TIMER_INDEX.match(path)
    if timer_match:
        index = _resolve_index(timer_match.group(1), area, variables, "Timer")
        return _timer_field(_area_timer(area, index), area, timer_match.group(2))
    scope_match = _SCOPE_FIELD.match(path)
    if scope_match:
        scope, field = scope_match.group(1), scope_match.group(2)
        if scope == "area":
            return _area_field(area, field)
        return _hub_field(area.area_manager, field)
    raise ScriptingError(f"Unknown source '{path}'.")


def try_live_get(path, area, variables=None):
    """Return a live value for `path` if it is a live source path, else None."""
    if variables is None:
        variables = {}
    if _LIVE_PATH.fullmatch(path.strip()):
        return live_get(path, area, variables)
    return None


def substitute_placeholders(text, variables=None, sources=None, area=None):
    """
    Replace inline `<!name>` getters with variable/source/live values.

    A placeholder resolves to a variable first, then a scalar live source, then
    (when `area` is given) a structured live path such as `<!client[0].showname>`
    or `<!area.background>`. Unknown names raise a `ScriptingError`. Values are
    stringified, so numeric counters interpolate directly into packet text and
    command arguments.
    """
    if variables is None:
        variables = {}
    if sources is None:
        sources = {}

    def _replace(match):
        name = match.group(1)
        if name in variables:
            return str(variables[name])
        if name in sources:
            return str(sources[name])
        if area is not None:
            value = try_live_get(name, area, variables)
            if value is not None:
                return str(value)
        raise ScriptingError(f"Unknown variable '{name}' in inline getter.")

    return _PLACEHOLDER.sub(_replace, text)


def live_sources(area):
    """Live server state exposed to scripts as pseudo-variables."""
    sources = {
        "players": len(_visible_clients(area)),
        "max_players": getattr(area, "max_players", 0),
        "hp_def": getattr(area, "hp_def", 0),
        "hp_pro": getattr(area, "hp_pro", 0),
        "char_count": len(getattr(getattr(area, "area_manager", None), "char_list", ())),
    }
    return sources
