class PlayerStateObserver:
    """
    Keeps the client side player list in sync with the AO 2.11 packets.

    Registration:
        PR#<player_id: int>#<update_type: int>#%
    Player data:
        PU#<player_id: int>#<data_type: int>#<data: string>#%

    Clients older than 2.11 drop both packets, so they are sent unconditionally.
    """

    ADD = 0
    REMOVE = 1

    NAME = 0
    CHARACTER = 1
    CHARACTER_NAME = 2
    AREA_ID = 3

    def __init__(self, server):
        self.server = server
        # Clients that receive player list packets.
        self.client_list = []
        # Clients that are currently listed for everyone else.
        self.listed = set()

    def register_client(self, client):
        """Hand the client the player list, then announce it to everyone else."""
        if client in self.client_list:
            return
        self.client_list.append(client)
        self.send_player_list(client)
        self.notify_visibility_changed(client)

    def unregister_client(self, client):
        """Drop the client from the player list of everyone still connected."""
        if client not in self.client_list:
            return
        self.client_list.remove(client)
        if client in self.listed:
            self.listed.discard(client)
            self.send_to_client_list(client, "PR", client.id, self.REMOVE)

    def send_player_list(self, client):
        """Send every listed player of the client's hub to that client."""
        for other in self.client_list:
            if other is client or other not in self.listed:
                continue
            if other.area.area_manager != client.area.area_manager:
                continue
            self.send_player_state(client, other)

    def send_player_state(self, target, client):
        """Send every field of a single player to one target."""
        target.send_command("PR", client.id, self.ADD)
        target.send_command("PU", client.id, self.NAME, client.name)
        target.send_command("PU", client.id, self.CHARACTER, client.char_name)
        target.send_command("PU", client.id,
                            self.CHARACTER_NAME, client.showname)
        target.send_command("PU", client.id, self.AREA_ID,
                            self.get_area_id(target, client))

    def get_area_id(self, target, client):
        """
        Get the index the client's area sits at in the target's own area list.
        Every client gets its own area list, so this cannot be broadcast as one
        value the way the other player data can.
        """
        try:
            area_id = target.local_area_list.index(client.area)
        except ValueError:
            return -1
        # The hub entry takes up the first slot of the area list.
        if len(self.server.hub_manager.hubs) > 1:
            area_id = area_id + 1
        return area_id

    def send_to_client_list(self, client, command, *args):
        """Send a packet about the client to every player list of its hub."""
        for target in self.client_list:
            if target.area.area_manager != client.area.area_manager:
                continue
            target.send_command(command, *args)

    def notify_name_changed(self, client):
        if client not in self.listed:
            return
        self.send_to_client_list(
            client, "PU", client.id, self.NAME, client.name)

    def notify_character_changed(self, client):
        """
        Announce a character change. Picking a character also takes the client
        out of spectator, so the listing itself may have to be added or dropped.
        """
        if client not in self.listed or client.hidden:
            self.notify_visibility_changed(client)
            return
        self.send_to_client_list(
            client, "PU", client.id, self.CHARACTER, client.char_name)
        self.send_to_client_list(
            client, "PU", client.id, self.CHARACTER_NAME, client.showname)

    def notify_character_name_changed(self, client):
        if client not in self.listed:
            return
        self.send_to_client_list(
            client, "PU", client.id, self.CHARACTER_NAME, client.showname)

    def notify_area_id_changed(self, client):
        if client not in self.listed:
            return
        for target in self.client_list:
            if target.area.area_manager != client.area.area_manager:
                continue
            target.send_command("PU", client.id, self.AREA_ID,
                                self.get_area_id(target, client))

    def notify_visibility_changed(self, client):
        """Add or drop the listing of a client that hid or revealed itself."""
        if client not in self.client_list:
            return
        if client.hidden:
            if client in self.listed:
                self.listed.discard(client)
                self.send_to_client_list(
                    client, "PR", client.id, self.REMOVE)
            return
        if client in self.listed:
            return
        self.listed.add(client)
        for target in self.client_list:
            if target.area.area_manager != client.area.area_manager:
                continue
            self.send_player_state(target, client)

    def notify_hub_changed(self, client, old_hub):
        """Move the client's listing over to the hub it just joined."""
        if client not in self.client_list:
            return
        for other in self.client_list:
            if other is not client and other.area.area_manager == old_hub:
                client.send_command("PR", other.id, self.REMOVE)
        if client in self.listed:
            self.listed.discard(client)
            for target in self.client_list:
                if target is not client and target.area.area_manager == old_hub:
                    target.send_command("PR", client.id, self.REMOVE)
        self.send_player_list(client)
        self.notify_visibility_changed(client)
