"""
Single source of truth for area link properties.

A "link" is the dict stored under ``area.links[str(target_id)]`` (see
``Area.link`` in ``server/area.py``). Every property is declared exactly once
here, and each consumer derives its field list / command pairs / coercion from
this table instead of re-declaring it:

- ``server/area.py`` ``Area.link()`` / ``Area.load()``  -- default values
- ``server/commands/area_access.py`` ``ooc_cmd_links``  -- flag display
- ``server/scripting.py`` ``_LINK_FIELDS``              -- read whitelist
- ``server/web_view/gm_panel`` serializers/routes       -- JSON + bool routing

Adding a link property means adding ONE ``LinkProp`` entry here (plus whatever
real behaviour/commands the property needs in ``server/commands/area_access.py``
and/or ``server/area.py``); every surface above picks it up automatically.

This module is a LEAF: it imports nothing from ``server.*``.
"""


class LinkProp:
    """Declarative description of one field in a link dict."""

    __slots__ = ("name", "default", "kind", "export", "bool_cmds", "prop", "serialize")

    def __init__(self, name, default, kind, export=None, bool_cmds=None, prop=None, serialize=None):
        self.name = name
        self.default = default
        self.kind = kind  # "bool" | "str" | "list"
        self.export = export if export is not None else name  # GM-panel JSON key
        self.bool_cmds = bool_cmds  # (on_cmd, off_cmd) for boolean props
        self.prop = prop if prop is not None else name  # frontend ``data-prop`` name
        self.serialize = serialize

    def to_json(self, value):
        """Coerce a raw link-dict value to its GM-panel JSON form."""
        if self.serialize is not None:
            return self.serialize(value)
        if self.kind == "bool":
            return bool(value)
        return value


# The ordered declaration table. ``default`` mirrors what ``Area.link()``
# historically used; ``export`` mirrors the GM-panel JSON keys; ``bool_cmds``
# mirrors the on/off command pairs the panel routes bool toggles through;
# ``prop`` mirrors the frontend ``data-prop`` names.
LINK_PROPERTY_SCHEMA = (
    LinkProp("locked", False, "bool", bool_cmds=("link_lock", "link_unlock"), prop="lock"),
    LinkProp("hidden", False, "bool", bool_cmds=("link_hide", "link_unhide"), prop="hide"),
    LinkProp("target_pos", "", "str", prop="pos"),
    LinkProp("can_peek", True, "bool", bool_cmds=("link_peekable", "link_unpeekable"), prop="peekable"),
    LinkProp("evidence", [], "list", serialize=lambda v: [int(e) for e in v]),
    LinkProp("password", "", "str", export="has_password", serialize=bool),
    LinkProp("seethrough", False, "bool", bool_cmds=("link_seethrough", "link_unseethrough")),
)

LINK_PROPERTIES = {p.name: p for p in LINK_PROPERTY_SCHEMA}
