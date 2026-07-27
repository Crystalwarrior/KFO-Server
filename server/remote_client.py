"""
Reusable remote client for executing commands without a real connected player.

Subclasses the real Client class and acts as a real area participant.
It joins area.clients and server.client_manager.clients so it receives
all packets naturally (area OOC, hub OOC, global OOC, IC).

CT/MS packets are intercepted in send_command and forwarded to registered
listeners (e.g. the admin panel WebSocket).

Usage:
    from server.remote_client import RemoteClient

    client = RemoteClient(server, is_mod=True)
    client.join_area()
    client.execute("kick", "1")
    print(client.output)

    with RemoteClient(server, is_mod=True) as client:
        client.join_area()
        client.execute("ban", "1")
        print(client.output)
"""

import time

from server.client_manager import ClientManager

# Reserved ipid for remote/system clients. Ensures FK constraints are satisfied
# without polluting the database with fake connection records.
_SYSTEM_IPID = 0
_system_ipid_seeded = False


def _ensure_system_ipid(db):
    """Insert the system ipid into the ipids table if it doesn't exist."""
    global _system_ipid_seeded
    if _system_ipid_seeded:
        return
    with db.db as conn:
        conn.execute(
            "INSERT OR IGNORE INTO ipids(ipid, ip_address) VALUES (?, ?)",
            (_SYSTEM_IPID, "system"),
        )
    _system_ipid_seeded = True


class RemoteClient(ClientManager.Client):
    """
    A remote client that inherits from the real Client class.
    Joins the area as a real participant and intercepts CT/MS packets
    for admin panel monitoring.
    """

    def __init__(self, server, is_mod=True, name="[SYSTEM]"):
        from server import database
        _ensure_system_ipid(database._database_singleton)
        super().__init__(server, _RemoteTransport(), user_id=-1, ipid=_SYSTEM_IPID)
        self.char_id = -1
        self.is_mod = is_mod
        self.name = name
        self.showname = name
        self.first_joined = False

        # Output capture for command execution
        self.output = []
        self.raw_packets = []

        # Event listeners: list of callbacks for OOC/IC monitoring
        self._listeners = []
        self._in_area = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.leave_area()
        self.clear()
        return False

    # --- Area participation ---

    def join_area(self):
        """Add self to area.clients and server.client_manager.clients."""
        if self._in_area:
            return
        area = self.area
        if self not in area.clients:
            area.clients.add(self)
        if self not in self.server.client_manager.clients:
            self.server.client_manager.clients.add(self)
        self._in_area = True

    def leave_area(self):
        """Remove self from area.clients and server.client_manager.clients."""
        if not self._in_area:
            return
        area = self.area
        if self in area.clients:
            area.clients.discard(self)
        if self in self.server.client_manager.clients:
            self.server.client_manager.clients.discard(self)
        self._in_area = False

    def add_listener(self, callback):
        """Register a callback for OOC/IC events: callback(event_dict)."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        """Unregister a callback."""
        self._listeners = [cb for cb in self._listeners if cb is not callback]

    # --- Transport overrides ---

    def send_raw_message(self, msg):
        self.raw_packets.append(("RAW", (msg,)))

    def send_ooc(self, msg):
        self.output.append(msg)

    def send_command(self, command, *args):
        """Intercept CT/MS packets and notify listeners."""
        if command == "CT" and len(args) >= 2:
            name = str(args[0]).replace("<dollar>", "$")
            msg = str(args[1]) if len(args) > 1 else ""
            entry = {
                "type": "ooc",
                "area_id": self.area.id if self.area else -1,
                "area_name": self.area.name if self.area else "?",
                "name": name,
                "msg": msg,
                "ts": time.time(),
            }
            for cb in list(self._listeners):
                try:
                    cb(entry)
                except Exception:
                    pass

        elif command == "MS" and len(args) >= 16:
            text = str(args[4]) if len(args) > 4 else ""
            showname = str(args[15]) if len(args) > 15 else ""
            cid = args[8] if len(args) > 8 else -1
            color = args[14] if len(args) > 14 else 0
            # Look up char folder name and client id
            char_name = ""
            client_id = -1
            if self.area:
                for c in self.area.clients:
                    if c.char_id == cid:
                        client_id = c.id
                        char_name = getattr(c, 'char_name', '')
                        break
                if not char_name:
                    try:
                        char_name = self.area.area_manager.char_list[cid]
                    except (IndexError, KeyError, AttributeError):
                        pass
            entry = {
                "type": "ic",
                "area_id": self.area.id if self.area else -1,
                "area_name": self.area.name if self.area else "?",
                "text": text,
                "showname": showname,
                "client_id": client_id,
                "char_name": char_name,
                "color": color,
                "ts": time.time(),
            }
            for cb in list(self._listeners):
                try:
                    cb(entry)
                except Exception:
                    pass

        # Let parent build the packet and send to the silent transport
        super().send_command(command, *args)

    def disconnect(self):
        self.leave_area()

    def record_latest_area(self):
        pass

    def kick_to_latest_area(self):
        pass

    # --- Utility ---

    def clear(self):
        self.output.clear()
        self.raw_packets.clear()

    def execute(self, cmd, arg=""):
        """
        Execute a command via commands.call() and capture the output.
        Returns the list of OOC messages that would have been sent.
        """
        self.output.clear()
        self.raw_packets.clear()
        from server import commands
        try:
            commands.call(self, cmd, arg)
        except Exception as e:
            self.send_ooc(f"[ERROR] {type(e).__name__}: {e}")
        return self.output


class _RemoteTransport:
    """Minimal transport stub that silently discards data."""

    def write(self, data):
        pass

    def get_extra_info(self, key, default=None):
        if key == "peername":
            return ("127.0.0.1", 0)
        if key == "sockname":
            return ("127.0.0.1", 0)
        return default

    def is_closing(self):
        return False

    def close(self):
        pass
