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

import logging
import asyncio

import stun
import aiohttp

logger = logging.getLogger("debug")


class MasterServerClient:
    """Advertises information about this server to the master server."""

    def __init__(self, server):
        self.server = server
        self.masterserver_url = 'https://servers.aceattorneyonline.com/servers'
        cfg = self.server.config
        self.serverinfo = {
            'port': cfg['port'],
            'name': cfg['masterserver_name'],
            'description': cfg['masterserver_description'],
            'players': self.server.player_count,
            'ip': cfg['masterserver_custom_hostname'] if 'masterserver_custom_hostname' in cfg else MasterServerClient.get_my_ip()
        }

        if 'use_websockets' in cfg and cfg['use_websockets']:
            self.serverinfo['ws_port'] = cfg['websocket_port']
        if 'use_securewebsockets' in cfg and cfg['use_securewebsockets']:
            self.serverinfo['wss_port'] = cfg['securewebsocket_port']

    # Sends server info to masterserver every 60 seconds
    async def advertising_loop(self):
        async with aiohttp.ClientSession() as http:
            while True:
                try:
                    await self.send_server_info(http)
                except Exception as e:
                    logger.error("Failed to send server info to masterserver.")
                    # We don't know how to handle or recover from this error, so re-raise it.
                    raise e
                finally:
                    await asyncio.sleep(60)

    async def send_server_info(self, http: aiohttp.ClientSession):
        # Update playercount
        self.serverinfo['players'] = self.server.player_count

        async with http.post(self.masterserver_url, json=self.serverinfo) as res:
            response_body = await res.text()
            if res.status >= 300:
                logger.error(
                    "Failed to send info to masterserver: received status code: %d and body: %s",
                    res.status, response_body)
            else:
                logger.debug(
                    'Sent server info to masterserver: %s', self.masterserver_url)

    @staticmethod
    # Use STUN servers to get our public IP address, should work for both ipv4 and ipv6
    def get_my_ip():
        stun_servers = [
            ('stun.l.google.com', 19302),
            ('global.stun.twilio.com', 3478),
            ('stun.voip.blackberry.com', 3478),
        ]

        for stun_ip, stun_port in stun_servers:
            nat_type, external_ip, _external_port = \
                stun.get_ip_info(stun_host=stun_ip, stun_port=stun_port)
            if nat_type != stun.Blocked:
                return external_ip

        # Should be a rare case
        logger.error("Failed to fetch public IP address from STUN servers.")
        return ''
