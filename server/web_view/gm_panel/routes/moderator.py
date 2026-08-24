"""Moderator routes: the admin log viewer.

These are the GM panel's port of ``server/web_view/admin_panel.py``'s moderator
surface. They are the ONLY part of the panel that can see ipid/hdid or query the
global event log, so every handler here is gated to sessions whose role is
``admin`` (a password login of ``role: admin``). Live-client GM sessions and
``role: gm`` remote sessions receive a 403.

The admin console and the OOC/IC monitors live on the shared Commands tab
(``CommandRoutes``) -- the console is the same free-form runner a GM uses, and
the monitor toggles are de-gated there so GMs and admins both get them. The
"Go Live" log stream is the one moderator-specific live feature: ``handle_api_log_live``
turns on a per-session subscription to ``database.subscribe()`` whose frames are
fanned out over the shared ``/ws/gm/live`` WebSocket.

The log viewer itself is one unified feed (``handle_api_all_events``): the
former area/connect/misc endpoints are merged into a single chronological
query so the tab shows all event categories in sequence with a shared column set.
"""

from aiohttp import web

from server import database


class ModeratorRoutes:
    """Admin-only routes: log viewer + its live stream."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    def _require_admin(self, request):
        """Return the admin session, or a 401/403 response."""
        session = request["gm_session"]
        if not session.is_valid():
            return None, web.json_response({"error": "session_invalid"}, status=401)
        if not session.is_admin:
            return None, web.json_response({"error": "not_authorized"}, status=403)
        return session, None

    @staticmethod
    def _int(value, default=None):
        if value in (None, ""):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # -- log viewer ---------------------------------------------------

    async def handle_api_hubs(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        db = database._database_singleton
        hubs = db.get_hubs()
        for hub in hubs:
            hub["areas"] = db.get_areas_for_hub(hub["hub_id"])
        return web.json_response(hubs)

    async def handle_api_areas(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        hub_id = self._int(request.query.get("hub_id"))
        return web.json_response(database._database_singleton.get_areas_for_hub(hub_id))

    async def handle_api_event_types(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        category = request.query.get("category", "area")
        if category not in ("area", "misc", "all"):
            return web.json_response({"error": "invalid category"}, status=400)
        return web.json_response(database._database_singleton.get_event_types(category))

    async def handle_api_all_events(self, request):
        """The unified event feed: area+connect+misc rows merged chronologically.

        Backs the log viewer's single table (the former Area Events /
        Connections / System-Misc sub-tabs). Filters: hub_id/area_id scope to
        area-category rows, event_subtype matches area/misc subtype names,
        ipid/since/until apply everywhere.
        """
        session, err = self._require_admin(request)
        if err is not None:
            return err
        db = database._database_singleton
        hub_id = self._int(request.query.get("hub_id"))
        area_id = self._int(request.query.get("area_id"))
        event_subtype = request.query.get("event_subtype")
        ipid = self._int(request.query.get("ipid"))
        since = request.query.get("since")
        until = request.query.get("until")
        limit = self._int(request.query.get("limit"), 100)
        offset = self._int(request.query.get("offset"), 0)
        events = db.query_all_events(
            hub_id, area_id, event_subtype, ipid, since, until, limit, offset
        )
        total = db.count_all_events(hub_id, area_id, event_subtype, ipid, since, until)
        return web.json_response({"events": events, "total": total})

    # -- live log stream ----------------------------------------------

    async def handle_api_log_live(self, request):
        """Toggle the live event-log stream for this admin session.

        Enabling subscribes the session to ``database.subscribe()``; rows are
        fanned out over the shared ``/ws/gm/live`` WebSocket as
        ``{"type": "area"|"connect"|"misc", "data": {...}}`` frames. Disabling
        cancels the subscription. The de-gated Commands-tab monitors keep their
        own ``set_monitor`` toggle.
        """
        session, err = self._require_admin(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        enabled = bool(data.get("enabled", False))
        session.set_log_live(enabled)
        return web.json_response({"ok": True, "live": enabled})