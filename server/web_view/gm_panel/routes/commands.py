"""Commands tab routes: auto-generated command list + free-form runner."""

import re

from aiohttp import web

from server.web_view.gm_panel.commands_meta import CommandLister
from server.web_view.gm_panel.sessions import SessionInvalid
from server.web_view.gm_panel.storage import _command_response


class CommandRoutes:
    """
    Commands tab: the auto-generated command list (`CommandLister`, not a
    whitelist) + the free-form command runner.

    `CommandLister` is UX curation only -- it is not consulted to decide what a
    GM can run. The *only* gate on what a GM can run is the command layer
    itself: `GMSession.execute_command` always dispatches through the GM's real,
    live `Client`, so every `mod_only(...)` decorator and other in-command
    permission check applies exactly as it would if the GM had typed the command
    in their AO client.
    """

    _COMMAND_NAME_RE = re.compile(r"^[a-z0-9_]+$")

    _DOCS_URL = "https://github.com/Crystalwarrior/KFO-Server/blob/master/docs/commands.md"

    def __init__(self, session_manager, server):
        self._session_manager = session_manager
        self._server = server

    async def handle_list_commands(self, request):
        return web.json_response({
            "ok": True,
            "groups": CommandLister.to_groups(),
            "docs_url": self._DOCS_URL,
        })

    async def handle_run_command(self, request):
        session = request["gm_session"]
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_request"}, status=400)

        cmd = str(data.get("cmd", "")).strip()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        cmd = cmd.lower()
        arg = str(data.get("arg", ""))

        if not self._COMMAND_NAME_RE.match(cmd):
            return web.json_response(
                {"ok": False, "output": ["[ERROR] Invalid command name."]}, status=400
            )

        try:
            output = session.execute_command(cmd, arg)
        except SessionInvalid:
            return web.json_response({"error": "session_invalid"}, status=401)
        return _command_response(output)
