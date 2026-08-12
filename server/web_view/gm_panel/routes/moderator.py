"""Moderator routes: admin log viewer, admin console, and OOC/IC monitoring.

These are the GM panel's port of ``server/web_view/admin_panel.py``'s moderator
surface. They are the ONLY part of the panel that can see ipid/hdid or query the
global event log, so every handler here is gated to sessions whose role is
``admin`` (a password login of ``role: admin``). Live-client GM sessions and
``role: gm`` remote sessions receive a 403.

The live-log WebSocket (``/ws/gm/admin_live``) carries two kinds of frame:

* ``{"type": "area"|"connect"|"misc", "data": {...}}`` -- drained from
  ``database.subscribe()`` (the global event log).
* ``{"type": "ooc"|"ic", ...}`` -- flat frames forwarded from the session's
  ``RemoteClient`` when the OOC/IC monitor is enabled.
"""

import asyncio
import json

import aiohttp
from aiohttp import web

from server import database
from server.constants import _SYSTEM_IPID
from server.remote_client import RemoteClient


class ModeratorRoutes:
    """Admin-only routes: log viewer, admin console, OOC/IC monitor, live WS."""

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    def _require_admin(self, request):
        """Return the admin ``RemoteSession``, or a 401/403 response."""
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
        if category not in ("area", "misc"):
            return web.json_response({"error": "invalid category"}, status=400)
        return web.json_response(database._database_singleton.get_event_types(category))

    async def handle_api_area_events(self, request):
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
        events = db.query_area_events(
            hub_id, area_id, event_subtype, ipid, since, until, limit, offset
        )
        total = db.count_area_events(
            hub_id, area_id, event_subtype, ipid, since, until
        )
        return web.json_response({"events": events, "total": total})

    async def handle_api_connect_events(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        db = database._database_singleton
        ipid = self._int(request.query.get("ipid"))
        failed = request.query.get("failed")
        if failed not in (None, ""):
            failed = failed.lower() in ("1", "true", "yes")
        else:
            failed = None
        since = request.query.get("since")
        until = request.query.get("until")
        limit = self._int(request.query.get("limit"), 100)
        offset = self._int(request.query.get("offset"), 0)
        events = db.query_connect_events(ipid, failed, since, until, limit, offset)
        total = db.count_connect_events(ipid, failed, since, until)
        return web.json_response({"events": events, "total": total})

    async def handle_api_misc_events(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        db = database._database_singleton
        event_subtype = request.query.get("event_subtype")
        ipid = self._int(request.query.get("ipid"))
        since = request.query.get("since")
        until = request.query.get("until")
        limit = self._int(request.query.get("limit"), 100)
        offset = self._int(request.query.get("offset"), 0)
        events = db.query_misc_events(event_subtype, ipid, since, until, limit, offset)
        total = db.count_misc_events(event_subtype, ipid, since, until)
        return web.json_response({"events": events, "total": total})

    # -- admin console -------------------------------------------------

    async def handle_api_players(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        players = []
        for c in list(self._server.client_manager.clients):
            if isinstance(c, RemoteClient) or c.ipid == _SYSTEM_IPID:
                continue
            area = getattr(c, "area", None)
            players.append({
                "id": c.id,
                "name": getattr(c, "name", ""),
                "char_name": getattr(c, "char_name", ""),
                "showname": getattr(c, "showname", ""),
                "ipid": c.ipid,
                "area_id": area.id if area is not None else -1,
                "area_name": area.name if area is not None else "?",
                "is_mod": getattr(c, "is_mod", False),
                "is_muted": getattr(c, "is_muted", False),
                "is_ooc_muted": getattr(c, "is_ooc_muted", False),
            })
        return web.json_response(players)

    async def handle_api_command(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid request body."]}, status=400
            )

        cmd = str(data.get("cmd", "")).strip()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        arg = str(data.get("arg", ""))

        remote = session.bound_client
        if cmd == "ooc":
            name = ("[M]" + remote.name) if remote.is_mod else remote.name
            remote.area.send_command("CT", name, arg)
            output = []
        else:
            output = remote.execute(cmd, arg)
        return web.json_response({"ok": True, "output": output})

    async def handle_api_ooc_monitor(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        enabled = bool(data.get("enabled", False))
        session.set_monitor("ooc", enabled)
        area = session.current_area()
        return web.json_response({
            "ok": True,
            "monitoring": enabled,
            "area_name": area.name if area is not None else "?",
            "area_id": area.id if area is not None else -1,
        })

    async def handle_api_ic_monitor(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_request"}, status=400)
        enabled = bool(data.get("enabled", False))
        session.set_monitor("ic", enabled)
        area = session.current_area()
        return web.json_response({
            "ok": True,
            "monitoring": enabled,
            "area_name": area.name if area is not None else "?",
            "area_id": area.id if area is not None else -1,
        })

    # -- live-log WebSocket -------------------------------------------

    async def handle_admin_ws_live(self, request):
        session, err = self._require_admin(request)
        if err is not None:
            return err
        db = database._database_singleton
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        session.add_ws(ws)
        queue = db.subscribe()

        async def drain():
            try:
                while True:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    await ws.send_json(entry)
            except asyncio.TimeoutError:
                await ws.ping()

        listener = asyncio.ensure_future(drain())
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except Exception:
                        continue
                    if payload.get("type") == "ping":
                        await ws.send_json({"type": "pong", "data": {}})
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        finally:
            listener.cancel()
            session.remove_ws(ws)
            db.unsubscribe(queue)
        return ws