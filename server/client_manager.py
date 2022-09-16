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

from heapq import heappop, heappush


from server import database
from server.client import Client
from server.constants import TargetType
from server.exceptions import ClientError

import oyaml as yaml  # ordered yaml


class ClientManager:
    """Holds the list of all clients currently connected to the server."""
    def __init__(self, server):
        self.clients = set()
        self.server = server
        self.cur_id = [i for i in range(self.server.config["playerlimit"])]

    def new_client_preauth(self, client):
        maxclients = self.server.config["multiclient_limit"]
        for c in self.server.client_manager.clients:
            if c.ipid == client.ipid:
                if c.clientscon > maxclients:
                    return False
        return True

    def new_client(self, transport):
        """
        Create a new client, add it to the list, and assign it a player ID.
        :param transport: asyncio transport
        """
        try:
            user_id = heappop(self.cur_id)
        except IndexError:
            transport.write(b"BD#This server is full.#%")
            raise ClientError

        peername = transport.get_extra_info("peername")[0]

        c = Client(self.server, transport, user_id,
                        database.ipid(peername))
        self.clients.add(c)
        temp_ipid = c.ipid
        for client in self.server.client_manager.clients:
            if client.ipid == temp_ipid:
                client.clientscon += 1
        return c

    def remove_client(self, client):
        """
        Remove a disconnected client from the client list.
        :param client: disconnected client
        """
        if client in client.area.area_manager.owners:
            client.area.area_manager.owners.remove(client)
        for hub in self.server.hub_manager.hubs:
            for a in hub.areas:
                if client in a._owners:
                    a.remove_owner(client, dc=True)
                # This discards the client's ID from any of the area invite lists
                # as that ID will no longer refer to this specific player.
                if client.id in a.invite_list:
                    a.invite_list.discard(client.id)
        heappush(self.cur_id, client.id)
        temp_ipid = client.ipid
        for c in self.server.client_manager.clients:
            if c.ipid == temp_ipid:
                c.clientscon -= 1
            if c.following == client:
                c.unfollow()
        self.clients.remove(client)
        for hub in self.server.hub_manager.hubs:
            count = 0
            for c in hub.clients:
                if not c.area.hide_clients and not c.hidden:
                    count = count + 1
            hub.count = count
        for c in self.server.client_manager.clients:
            if c.viewing_hub_list:
                c.send_command(
                    "FA",
                    *[
                        "{ Hubs }\n Double-Click me to see Areas\n  _______",
                        *[
                            f"[{hub.id}] {hub.name} (users: {hub.count})"
                            for hub in self.server.hub_manager.hubs
                        ],
                    ],
                )

    def get_targets(self, client, key, value, local=False, single=False):
        """
        Find players by a combination of identifying data.
        Possible keys: player ID, OOC name, character name, HDID, IPID,
        IP address (same as IPID)

        :param client: client
        :param key: the type of identifier that `value` represents
        :param value: data identifying a client
        :param local: search in current area only (Default value = False)
        :param single: search only a single user (Default value = False)
        """
        areas = None
        if local:
            areas = [client.area]
        else:
            areas = client.area.area_manager.areas
        targets = []
        if key == TargetType.ALL:
            for nkey in range(6):
                targets += self.get_targets(client, nkey, value, local)
        for area in areas:
            for client in area.clients:
                if key == TargetType.IP:
                    if value.lower().startswith(client.ip.lower()):
                        targets.append(client)
                elif key == TargetType.OOC_NAME:
                    if value.lower().startswith(client.name.lower()) and client.name:
                        targets.append(client)
                elif key == TargetType.CHAR_NAME:
                    if value.lower().startswith(client.char_name.lower()):
                        targets.append(client)
                elif key == TargetType.ID:
                    if client.id == value:
                        targets.append(client)
                elif key == TargetType.IPID:
                    if client.ipid == value:
                        targets.append(client)
                elif key == TargetType.AFK:
                    if client in area.afkers:
                        targets.append(client)
        return targets

    def get_muted_clients(self):
        """Get a list of muted clients."""
        clients = []
        for client in self.clients:
            if client.is_muted:
                clients.append(client)
        return clients

    def get_ooc_muted_clients(self):
        """Get a list of OOC-muted clients."""
        clients = []
        for client in self.clients:
            if client.is_ooc_muted:
                clients.append(client)
        return clients

    def toggle_afk(self, client):
        if client in client.area.afkers:
            client.area.broadcast_ooc(
                "{} is no longer AFK.".format(client.showname))
            client.send_ooc(
                "You are no longer AFK. Welcome back!"
            )  # Making the server a bit friendly wouldn't hurt, right?
            client.area.afkers.remove(client)
        else:
            client.area.broadcast_ooc("{} is now AFK.".format(client.showname))
            client.send_ooc("You are now AFK. Have a good day!")
            client.area.afkers.append(client)

    def refresh_music(self, clients=None):
        """
        Refresh the listed clients' music lists.
        :param clients: list of clients whose music lists should be regenerated.

        """
        if clients is None:
            clients = self.clients
        for client in clients:
            client.refresh_music()

    def get_multiclients(self, ipid=-1, hdid=""):
        return [c for c in self.clients if c.ipid == ipid or c.hdid == hdid]

    def get_mods(self):
        return [c for c in self.clients if c.is_mod]
