"""
Reusable remote client for executing commands without a real connected player.

Subclasses the real Client class and only overrides transport/output methods.
All business logic (send_area_info, get_area_clients, etc.) is inherited.

Usage:
    from server.remote_client import RemoteClient

    client = RemoteClient(server, is_mod=True)
    client.execute("kick", "1")
    print(client.output)

    with RemoteClient(server, is_mod=True) as client:
        client.execute("ban", "1")
        print(client.output)
"""

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
    Only overrides transport/output methods to capture data.
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

        # Output capture
        self.output = []       # OOC messages
        self.raw_packets = []  # Raw protocol packets

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()
        return False

    # --- Transport overrides ---

    def send_raw_message(self, msg):
        self.raw_packets.append(("RAW", (msg,)))

    def send_ooc(self, msg):
        self.output.append(msg)

    def disconnect(self):
        pass

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
