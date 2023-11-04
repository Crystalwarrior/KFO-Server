# KFO-Server, an Attorney Online server
#
# Copyright (C) 2020 Crystalwarrior <varsash@gmail.com>
#
# Derivative of tsuserver3, an Attorney Online server. Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import logging
import logging.handlers


def setup_logging(debug: bool = False):
    formatter = logging.Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s] %(message)s")

    # Log to terminal (stdout)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stdout_handler)

    # Log to server.log
    serverlog_handler = logging.handlers.RotatingFileHandler(
        "logs/server.log", encoding="utf-8", maxBytes=1024 * 512
    )
    # The serverlog should never log debug messages
    serverlog_handler.setLevel(logging.INFO)
    serverlog_handler.setFormatter(formatter)
    logging.getLogger().addHandler(serverlog_handler)

    if debug:
        # Log to debug.log
        debuglog_handler = logging.handlers.RotatingFileHandler(
            "logs/debug.log", encoding="utf-8", maxBytes=1024 * 1024 * 4
        )
        debuglog_handler.setFormatter(formatter)
        logging.getLogger().addHandler(debuglog_handler)

    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


def parse_client_info(client):
    """Prepend information about a client to a log entry."""
    if client is None:
        return ""
    ipid = client.ip
    prefix = f"[{ipid:<15}][{client.id:<3}][{client.name}]"
    if client.is_mod:
        prefix += "[MOD]"
    return prefix
