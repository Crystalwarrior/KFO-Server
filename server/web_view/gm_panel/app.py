"""GM Control Panel web application.

A separate aiohttp app (own port, own session cookie/store) that lets an
in-game GM micromanage their hub through a browser: areas as a graph, who's
present, characters/character-data, GM-scoped OOC commands, and the Automation
Demos system.

Unlike `admin_panel.py`, this panel never runs commands through a synthetic
`RemoteClient`. Every privileged action executes through the GM's real, live,
in-game `Client` object (see `GMSession.execute_command`), so the exact same
`mod_only(area_owners=...)`/`mod_only(hub_owners=...)` checks the command layer
already performs are what gate the panel too -- there is no separate permission
system to keep in sync or get wrong.
"""

import logging
import os
import ssl

from aiohttp import web

from server.web_view.gm_panel.bridge import GMPanelBridge
from server.web_view.gm_panel.sessions import GMSessionManager
from server.web_view.gm_panel.routes.areas import AreaRoutes
from server.web_view.gm_panel.routes.assets import AssetRoutes
from server.web_view.gm_panel.routes.auth import AuthRoutes
from server.web_view.gm_panel.routes.characters import CharacterRoutes
from server.web_view.gm_panel.routes.clients import ClientRoutes
from server.web_view.gm_panel.routes.commands import CommandRoutes
from server.web_view.gm_panel.routes.evidence import EvidenceRoutes
from server.web_view.gm_panel.routes.hub_data import HubDataRoutes
from server.web_view.gm_panel.routes.moderator import ModeratorRoutes

logger = logging.getLogger("gm_panel")


class GMPanelApp:
    """
    Owns the aiohttp `Application`, its route table, static/template mounting,
    SSL setup, and lifecycle (`build()`). Composes everything else via
    constructor injection (`server`, `config`) -- no business logic of its own.
    """

    def __init__(self, server, config):
        self._server = server
        self._config = config
        self._templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self._static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        self._gm_html = None
        self._gm_login_html = None
        self._session_manager = GMSessionManager(server, config)
        self.bridge = GMPanelBridge(server, self._session_manager, config)

    def _load_template(self, name):
        path = os.path.join(self._templates_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def build(self):
        """Build and return `(aiohttp.web.Application, ssl_context_or_None)`."""
        self._gm_html = self._load_template("gm.html")
        self._gm_login_html = self._load_template("gm_login.html")

        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

        # Web scanners / port-probers hitting the panel's plain-HTTP port with a
        # TLS handshake make aiohttp log a noisy "Error handling request"
        # BadStatusLine traceback -- it's harmless probes. Silence only that
        # case and keep every real error visible. aiohttp logs the generic
        # message "Error handling request" and attaches the real error via
        # exc_info, so the filter must inspect the exception, not just the msg.
        class _TlsProbeFilter(logging.Filter):
            def filter(self, record):
                message = record.getMessage()
                if "BadStatusLine" in message or "Invalid method encountered" in message:
                    return False
                if record.exc_info and record.exc_info[1] is not None:
                    if type(record.exc_info[1]).__name__ == "BadStatusLine":
                        return False
                return True

        logging.getLogger("aiohttp.server").addFilter(_TlsProbeFilter())

        auth_routes = AuthRoutes(
            self._session_manager, self._server, self.bridge,
            self._gm_html, self._gm_login_html,
        )
        area_routes = AreaRoutes(self._session_manager, self._server, self._config, self.bridge)
        client_routes = ClientRoutes(self._session_manager, self._server)
        command_routes = CommandRoutes(self._session_manager, self._server)
        character_routes = CharacterRoutes(self._session_manager, self._server)
        hub_data_routes = HubDataRoutes(self._session_manager, self._server, self.bridge)
        evidence_routes = EvidenceRoutes(self._session_manager, self._server)
        asset_routes = AssetRoutes(self._server, self._config)
        moderator_routes = ModeratorRoutes(self._session_manager, self._server)

        require = self._session_manager.require

        app = web.Application()
        app["config"] = self._config
        app["server"] = self._server

        # Page + auth routes
        app.router.add_get("/", auth_routes.handle_root)
        app.router.add_post("/api/gm/session/exchange", auth_routes.handle_session_exchange)
        app.router.add_get("/api/gm/session", require(auth_routes.handle_session_get))
        app.router.add_post("/api/gm/logout", require(auth_routes.handle_logout))
        app.router.add_get("/ws/gm/live", require(auth_routes.handle_ws_live))

        # Password login (NOT behind require -- this is what establishes the session).
        app.router.add_post("/api/gm/login", auth_routes.handle_login)

        # Admin-only moderator routes (log viewer + live log stream). The admin
        # console and the OOC/IC monitors live on the shared Commands tab
        # (/api/gm/commands/*, /api/gm/monitor/*) so GMs and admins both get them.
        app.router.add_get("/api/gm/logs/hubs", require(moderator_routes.handle_api_hubs))
        app.router.add_get("/api/gm/logs/areas", require(moderator_routes.handle_api_areas))
        app.router.add_get("/api/gm/logs/event_types", require(moderator_routes.handle_api_event_types))
        app.router.add_get("/api/gm/logs/area_events", require(moderator_routes.handle_api_area_events))
        app.router.add_get("/api/gm/logs/connect_events", require(moderator_routes.handle_api_connect_events))
        app.router.add_get("/api/gm/logs/misc_events", require(moderator_routes.handle_api_misc_events))
        app.router.add_post("/api/gm/logs/live", require(moderator_routes.handle_api_log_live))

        # Areas tab -- literal/collection routes ("hub/areas/...") registered
        # separately from the per-area "{area_id}/..." routes.
        app.router.add_get("/api/gm/areas", require(area_routes.handle_list_areas))
        app.router.add_get(
            "/api/gm/areas/background_thumb_base_url",
            require(area_routes.handle_background_thumb_base_url),
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/background", require(area_routes.handle_set_background)
        )
        app.router.add_get(
            "/api/gm/areas/{area_id}/detail", require(area_routes.handle_area_detail)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/pref", require(area_routes.handle_set_pref)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/edit", require(area_routes.handle_edit_area)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/add", require(area_routes.handle_link_add)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/remove", require(area_routes.handle_link_remove)
        )
        app.router.add_post(
            "/api/gm/areas/{area_id}/links/set", require(area_routes.handle_link_set)
        )

        # Hub-level area management (create/remove/swap) -- distinct prefix from
        # the per-area routes above since these act on the whole hub.
        app.router.add_post(
            "/api/gm/hub/areas/create", require(area_routes.handle_create_area)
        )
        app.router.add_post(
            "/api/gm/hub/areas/swap", require(area_routes.handle_swap_areas)
        )
        app.router.add_post(
            "/api/gm/hub/areas/switch", require(area_routes.handle_switch_areas)
        )
        app.router.add_post(
            "/api/gm/hub/areas/{area_id}/duplicate", require(area_routes.handle_duplicate_area)
        )
        app.router.add_post(
            "/api/gm/hub/areas/{area_id}/remove", require(area_routes.handle_remove_area)
        )

        # Shared local-content resolution config (GMLocalContent).
        app.router.add_get("/api/gm/assets/config", require(asset_routes.handle_config))

        # Clients tab
        app.router.add_get("/api/gm/clients", require(client_routes.handle_list_clients))
        app.router.add_post(
            "/api/gm/clients/{client_id}/gm", require(client_routes.handle_promote)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/ungm", require(client_routes.handle_demote)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/pm", require(client_routes.handle_pm)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/area", require(client_routes.handle_teleport_to_area)
        )
        app.router.add_post(
            "/api/gm/clients/{client_id}/teleport_here",
            require(client_routes.handle_teleport_here),
        )

        # Commands tab -- the single free-form console for both GMs and admins,
        # plus the admin-only travel scope (GMs are hub-bound, admins travel).
        app.router.add_get("/api/gm/commands", require(command_routes.handle_list_commands))
        app.router.add_post("/api/gm/commands/run", require(command_routes.handle_run_command))
        app.router.add_get("/api/gm/commands/scope", require(command_routes.handle_get_scope))
        app.router.add_post("/api/gm/commands/travel", require(command_routes.handle_travel))
        app.router.add_post("/api/gm/monitor/{kind}", require(command_routes.handle_set_monitor))

        # Characters tab
        app.router.add_get(
            "/api/gm/characters", require(character_routes.handle_list_characters)
        )
        app.router.add_get("/api/gm/charlists", require(character_routes.handle_list_charlists))
        app.router.add_post(
            "/api/gm/charlists/apply", require(character_routes.handle_apply_charlist)
        )
        app.router.add_get(
            "/api/gm/character_data", require(character_routes.handle_character_data)
        )
        app.router.add_get(
            "/api/gm/character_data_snapshots", require(character_routes.handle_snapshots_list)
        )
        app.router.add_post(
            "/api/gm/character_data_snapshots/save",
            require(character_routes.handle_snapshots_save),
        )
        app.router.add_post(
            "/api/gm/character_data_snapshots/load",
            require(character_routes.handle_snapshots_load),
        )
        app.router.add_get(
            "/api/gm/character_data/{folder}/{key}",
            require(character_routes.handle_character_data_get_key),
        )
        app.router.add_post(
            "/api/gm/character_data/{folder}/set",
            require(character_routes.handle_character_data_set),
        )
        app.router.add_get(
            "/api/gm/character_data/{folder}",
            require(character_routes.handle_character_data_one),
        )

        # Hub Data tab -- hub save/load, generic yaml import/export for all five
        # GM-facing data kinds, the charlist editor, the music editor.
        app.router.add_get("/api/gm/hub/saves", require(hub_data_routes.handle_hub_saves))
        app.router.add_post("/api/gm/hub/save", require(hub_data_routes.handle_hub_save))
        app.router.add_post("/api/gm/hub/load", require(hub_data_routes.handle_hub_load))

        # Literal routes ("data/{kind}/files") registered before the dynamic
        # "data/{kind}/file" route to mirror the Evidence tab's ordering
        # convention -- these don't actually collide (aiohttp matches on full
        # path shape) but keeping the convention consistent makes the route
        # table easier to scan.
        app.router.add_get(
            "/api/gm/data/{kind}/files", require(hub_data_routes.handle_data_files)
        )
        app.router.add_get("/api/gm/data/{kind}/file", require(hub_data_routes.handle_data_file_get))
        app.router.add_put("/api/gm/data/{kind}/file", require(hub_data_routes.handle_data_file_put))
        app.router.add_post("/api/gm/data/{kind}/load", require(hub_data_routes.handle_data_file_load))

        app.router.add_get("/api/gm/charlist", require(hub_data_routes.handle_charlist_get))
        app.router.add_post(
            "/api/gm/charlist/submit", require(hub_data_routes.handle_charlist_submit)
        )

        app.router.add_get("/api/gm/music", require(hub_data_routes.handle_music_get))
        app.router.add_post("/api/gm/music/apply", require(hub_data_routes.handle_music_apply))

        # Evidence tab (formerly "Demos") -- literal routes registered before the
        # dynamic {evidence_id} route so e.g. "status" isn't swallowed as an id.
        app.router.add_get("/api/gm/evidence", require(evidence_routes.handle_list_evidence))
        app.router.add_post("/api/gm/evidence/eval", require(evidence_routes.handle_eval))
        app.router.add_get("/api/gm/evidence_packs", require(evidence_routes.handle_list_packs))
        app.router.add_post(
            "/api/gm/evidence_packs/save", require(evidence_routes.handle_save_pack)
        )
        app.router.add_post(
            "/api/gm/evidence_packs/{name}/load", require(evidence_routes.handle_load_pack)
        )
        app.router.add_get(
            "/api/gm/evidence/{area_id}/status", require(evidence_routes.handle_status)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/new", require(evidence_routes.handle_new_evidence)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/stop_all",
            require(evidence_routes.handle_stop_all_evidence),
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/stop", require(evidence_routes.handle_stop_evidence)
        )
        app.router.add_post(
            "/api/gm/evidence/{area_id}/{evidence_id}/run",
            require(evidence_routes.handle_run_evidence),
        )
        app.router.add_get(
            "/api/gm/evidence/{area_id}/{evidence_id}", require(evidence_routes.handle_get_evidence)
        )
        app.router.add_put(
            "/api/gm/evidence/{area_id}/{evidence_id}", require(evidence_routes.handle_put_evidence)
        )
        app.router.add_delete(
            "/api/gm/evidence/{area_id}/{evidence_id}",
            require(evidence_routes.handle_delete_evidence),
        )

        # Static assets -- same physical folder as admin_panel.py's, served on a
        # separate port, so gm.css/gm.js can't collide with admin's.
        app.router.add_static("/static", self._static_dir)

        self._session_manager.start_sweep()

        return app, self._build_ssl_context()

    def _build_ssl_context(self):
        ssl_cert = self._config.get("ssl_cert")
        ssl_key = self._config.get("ssl_key")
        domain = self._config.get("domain")

        if ssl_cert and ssl_key:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(ssl_cert, ssl_key)
            logger.info("GM panel SSL enabled (cert: %s, key: %s)", ssl_cert, ssl_key)
            return ctx

        if domain:
            logger.info(
                "GM panel domain set to %s. "
                "Set up Caddy to reverse proxy to this port. Example Caddyfile:\n"
                "  %s {\n"
                "      reverse_proxy localhost:%s\n"
                "  }\n"
                "Then run: caddy run",
                domain, domain, self._config.get("port", 27018),
            )
            return None

        logger.warning(
            "GM panel has no SSL configured (ssl_cert/ssl_key or domain). "
            "Running over plain HTTP."
        )
        return None


