"""Bridge: translates game-side hook calls into scoped WS events.

`GMPanelBridge` is the only object the core server (`area.py`, `area_manager.py`,
`client_manager.py`) knows about, via `getattr(server, "gm_panel_bridge", None)`.
It translates those raw hook calls into structured event dicts and fans them out
to every in-scope `GMSession`.
"""

from server.remote_client import RemoteClient

from server.web_view.gm_panel.serializers import ClientSerializer


class GMPanelBridge:
    """
    Translates raw hook calls from area/client code into structured event dicts
    and fans them out to every in-scope `GMSession`. Holds no session storage
    itself -- that's `GMSessionManager`'s job.
    """

    def __init__(self, server, session_manager, config):
        self._server = server
        self.session_manager = session_manager
        self._config = config

    @property
    def login_token_ttl(self):
        return self.session_manager.login_token_ttl

    def public_url_for_token(self, token):
        domain = self._config.get("domain")
        if domain:
            return f"https://{domain}/?token={token}"
        port = self._config.get("port", 27018)
        host = self._config.get("host", "0.0.0.0")
        has_ssl = bool(self._config.get("ssl_cert") and self._config.get("ssl_key"))
        scheme = "https" if has_ssl else "http"
        display_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
        return f"{scheme}://{display_host}:{port}/?token={token}"

    def _broadcast_to_hub(self, hub_ids, type_, data):
        for session in self.session_manager.all_sessions():
            if not session.is_valid():
                continue
            try:
                hub_id = session.current_hub().id
            except Exception:
                continue
            if hub_id in hub_ids:
                session.push_event(type_, data)

    def on_client_moved(self, client, old_area, new_area):
        """Hook: `Client.set_area` completed. The animation trigger."""
        if isinstance(client, RemoteClient):
            return
        from_hub_id = old_area.area_manager.id
        to_hub_id = new_area.area_manager.id
        data = {
            "client_id": client.id,
            "from_area_id": old_area.id,
            "to_area_id": new_area.id,
            "from_hub_id": from_hub_id,
            "to_hub_id": to_hub_id,
            # Showname + character folder ride along so the front-end's
            # traveling token can label itself with the SHOWNAME (not #id).
            # Whitelisted fields only (ClientSerializer-shaped); no
            # ipid/hdid/ip here.
            "showname": client.showname,
            "char_name": client.char_name,
            "iniswap": client.iniswap,
        }
        self._broadcast_to_hub({from_hub_id, to_hub_id}, "client_moved", data)
        if from_hub_id != to_hub_id:
            for session in self.session_manager.find_sessions_for_client(client):
                session.push_event("hub_switched", {
                    "new_hub_id": to_hub_id,
                    "new_hub_name": new_area.area_manager.name,
                })

    def on_client_present(self, client, area):
        """Hook: `Area.new_client` -- a client fully joined this area."""
        if isinstance(client, RemoteClient):
            return
        data = ClientSerializer.to_dict(client)
        self._broadcast_to_hub({area.area_manager.id}, "client_present", data)

    def on_client_absent(self, client, area):
        """Hook: `Area.remove_client` -- a client left this area."""
        if isinstance(client, RemoteClient):
            return
        data = {"client_id": client.id, "area_id": area.id}
        self._broadcast_to_hub({area.area_manager.id}, "client_absent", data)

    def on_client_disconnected(self, client):
        """Hook: `Server.remove_client`, before the client's id is recycled."""
        if isinstance(client, RemoteClient):
            return
        area = getattr(client, "area", None)
        if area is not None:
            data = {"client_id": client.id, "last_area_id": area.id}
            self._broadcast_to_hub({area.area_manager.id}, "client_disconnected", data)
        self.session_manager.invalidate_for_client(client)

    def on_hub_gm_roster_changed(self, area_manager):
        """Hook: `AreaManager.add_owner`/`remove_owner`."""
        gm_ids = [c.id for c in area_manager.real_owners()]
        data = {"hub_id": area_manager.id, "gm_client_ids": gm_ids}
        self._broadcast_to_hub({area_manager.id}, "hub_gm_roster_changed", data)

    def on_area_cm_roster_changed(self, area):
        """Hook: `Area.add_owner`/`remove_owner`."""
        cm_ids = [c.id for c in area.real_cms()]
        data = {"area_id": area.id, "cm_client_ids": cm_ids}
        self._broadcast_to_hub({area.area_manager.id}, "area_cm_roster_changed", data)

    def on_area_background_changed(self, area):
        """Hook: `Area.change_background`/`change_background_suffix`."""
        data = {"area_id": area.id, "background": area.background, "overlay": area.overlay}
        self._broadcast_to_hub({area.area_manager.id}, "background_changed", data)

    def push_areas_changed(self, hub_id):
        """
        Called directly by `AreaRoutes` after every successful area/pref/link
        mutation, so every open panel on this hub refetches its areas snapshot.
        """
        self._broadcast_to_hub({hub_id}, "areas_changed", {"hub_id": hub_id})
