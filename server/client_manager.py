import asyncio
from heapq import heappop, heappush
from typing import Any, Dict, Iterable, List, Optional, Set, Union, TYPE_CHECKING

from server import database
from server.client import Client
from server.constants import TargetType
from server.exceptions import ClientError

if TYPE_CHECKING:
    from tsuserver import TsuServer3


class ClientManager:
    """Holds the list of all clients currently connected to the server."""

    def __init__(self, server: "TsuServer3") -> None:
        self.clients: Set[Client] = set()
        self.server = server
        self.cur_id: List[int] = [i for i in range(self.server.config["playerlimit"])]
        # Mapping of ipid -> spam_type -> delay seconds
        self.delays: Dict[str, Dict[str, float]] = {}

    def set_spam_delay(self, ipid: int, spam_type: str, value: float) -> None:
        if str(ipid) not in self.delays:
            self.delays[str(ipid)] = {}
        self.delays[str(ipid)][spam_type] = value

    def get_spam_delay(self, ipid: int, spam_type: str) -> float:
        if str(ipid) not in self.delays:
            return 0
        if spam_type not in self.delays[str(ipid)]:
            return 0
        return self.delays[str(ipid)][spam_type]

    def new_client_preauth(self, client: Client) -> bool:
        maxclients = self.server.config["multiclient_limit"]
        for c in self.server.client_manager.clients:
            if c.ipid == client.ipid:
                if c.clientscon > maxclients:
                    return False
        return True

    def new_client(self, transport: asyncio.BaseTransport) -> Client:
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

        new_client = Client(self.server, transport, user_id, database.ipid(peername))
        self.clients.add(new_client)
        temp_ipid = new_client.ipid
        for new_client in self.server.client_manager.clients:
            if new_client.ipid == temp_ipid:
                new_client.clientscon += 1
        return new_client

    def remove_client(self, client: Client) -> None:
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

        # TODO: Maybe take into account than sending the "CU" packet can reveal your cover.
        # So you could simply treat the hidden client as if they didn't declare their char_url.
        # Probably using a bool for it.

        # Removes the client's user link from the area it was.
        if client.char_url != "":
            clients = (c for c in client.area.clients if c.id != client.id)
            for c in clients:
                c.remove_user_link(client.char_name)
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
                        "🌐 Hubs 🌐\n Double-Click me to see Areas\n  _______",
                        *[
                            f"[{hub.id}] {hub.name} (users: {hub.count})"
                            for hub in self.server.hub_manager.hubs
                        ],
                    ],
                )

    def get_targets(
        self,
        client: Client,
        key: Union[int, TargetType],
        value: Union[str, int],
        local: bool = False,
        single: bool = False,  # unused, kept for API compatibility
        all_hub: bool = False,
    ) -> List[Client]:
        """
        Find players by a combination of identifying data.
        Possible keys: player ID, OOC name, character name, HDID, IPID,
        IP address (same as IPID)

        :param client: client
        :param key: the type of identifier that `value` represents
        :param value: data identifying a client
        :param local: search in current area only (Default value = False)
        :param single: search only a single user (Default value = False)
        :param all_hub: search in all hubs (Default value = False)
        """
        targets: List[Client] = []
        if key == TargetType.ALL:
            for nkey in range(6):
                targets += self.get_targets(client, nkey, value, local)
        if all_hub and not local:
            hubs = self.server.hub_manager.hubs
        else:
            hubs = [client.area.area_manager]
        for hub in hubs:
            if local:
                areas = [client.area]
            else:
                areas = hub.areas
            for area in areas:
                for client in area.clients:
                    if key == TargetType.IP:
                        if value.lower().startswith(client.ip.lower()):
                            targets.append(client)
                    elif key == TargetType.OOC_NAME:
                        if (
                            value.lower().startswith(client.name.lower())
                            and client.name
                        ):
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

    def get_muted_clients(self) -> List[Client]:
        """Get a list of muted clients."""
        clients: List[Client] = []
        for client in self.clients:
            if client.is_muted:
                clients.append(client)
        return clients

    def get_ooc_muted_clients(self) -> List[Client]:
        """Get a list of OOC-muted clients."""
        clients: List[Client] = []
        for client in self.clients:
            if client.is_ooc_muted:
                clients.append(client)
        return clients

    def toggle_afk(self, client: Client) -> None:
        if client in client.area.afkers:
            if not client.hidden and not client.sneaking:
                client.area.broadcast_ooc(
                    "{} is no longer AFK.".format(client.showname)
                )
            client.send_ooc(
                "You are no longer AFK. Welcome back!"
            )  # Making the server a bit friendly wouldn't hurt, right?
            client.area.afkers.remove(client)
        else:
            if not client.hidden and not client.sneaking:
                client.area.broadcast_ooc("{} is now AFK.".format(client.showname))
            client.send_ooc("You are now AFK. Have a good day!")
            client.area.afkers.append(client)
        if not client.hidden and not client.sneaking:
            client.area.broadcast_player_list()

    def refresh_music(
        self, clients: Optional[Iterable[Client]] = None, reload: bool = False
    ) -> None:
        """
        Refresh the listed clients' music lists.
        :param clients: list of clients whose music lists should be regenerated.

        """
        if clients is None:
            clients = self.clients
        for client in clients:
            client.refresh_music(reload)

    def get_multiclients(self, ipid: int = -1, hdid: str = "") -> List[Client]:
        return [c for c in self.clients if c.ipid == ipid or c.hdid == hdid]

    def get_mods(self) -> List[Client]:
        return [c for c in self.clients if c.is_mod]

    class BattleChar:
        def __init__(
            self, client: Client, fighter_name: str, fighter: Dict[str, Any]
        ) -> None:
            self.fighter: str = fighter_name
            self.hp: float = float(fighter["HP"])
            self.maxhp: float = self.hp
            self.atk: float = float(fighter["ATK"])
            self.mana: float = float(fighter["MANA"])
            self.defe: float = float(fighter["DEF"])
            self.spa: float = float(fighter["SPA"])
            self.spd: float = float(fighter["SPD"])
            self.spe: float = float(fighter["SPE"])
            self.target: Optional[Client] = None
            self.selected_move: int = -1
            self.status: Optional[str] = None
            self.current_client: Client = client
            self.guild: Optional[str] = None
            self.moves: List["ClientManager.Move"] = [
                ClientManager.Move(move) for move in fighter["Moves"]
            ]

    class Move:
        def __init__(self, move: Dict[str, Any]) -> None:
            self.name: str = move["Name"]
            self.cost: float = move["ManaCost"]
            self.type: str = move["MovesType"]
            self.power: float = float(move["Power"])
            self.effect: Any = move["Effects"]
            self.accuracy: float = float(move["Accuracy"])
