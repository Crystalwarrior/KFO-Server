from server import database
from server.constants import TargetType

from . import mod_only, command, Arg

__all__ = [
    "ooc_cmd_disemvowel",
    "ooc_cmd_undisemvowel",
    "ooc_cmd_shake",
    "ooc_cmd_unshake",
    "ooc_cmd_rainbow",
    "ooc_cmd_medieval",
    "ooc_cmd_unmedieval",
    "ooc_cmd_medieval_mode",
]


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_disemvowel(client, id):
    """
    Remove all vowels from a user's IC chat.
    Usage: /disemvowel <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            database.log_area("disemvowel", client, client.area, target=c)
            c.disemvowel = True
        client.send_ooc(f"Disemvowelled {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_undisemvowel(client, id):
    """
    Give back the freedom of vowels to a user.
    Usage: /undisemvowel <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            database.log_area("undisemvowel", client, client.area, target=c)
            c.disemvowel = False
        client.send_ooc(f"Undisemvowelled {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_shake(client, id):
    """
    Scramble the words in a user's IC chat.
    Usage: /shake <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            database.log_area("shake", client, client.area, target=c)
            c.shaken = True
        client.send_ooc(f"Shook {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_unshake(client, id):
    """
    Give back the freedom of coherent grammar to a user.
    Usage: /unshake <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            database.log_area("unshake", client, client.area, target=c)
            c.shaken = False
        client.send_ooc(f"Unshook {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@command(Arg("tog", bool, default=None, help="on/off"))
def ooc_cmd_rainbow(client, tog):
    """
    rainbow text is back baybee
    Usage: /rainbow [true/false]
    """
    client.rainbow = not client.rainbow if tog is None else tog
    toggle = "now" if client.rainbow else "no longer"
    client.send_ooc(
        f"You will {toggle} have rainbowtext."
    )


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_medieval(client, id):
    """
    Transform a user's IC chat into Ye Olde English.
    Usage: /medieval <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            if c.medieval:
                client.send_ooc("That player is already speaking Ye Olde English!")
            else:
                database.log_area("medieval", client, client.area, target=c)
                c.medieval = True
                c.send_ooc("Forsooth! Thine speech will henceforth be Ye Olde!")
        client.send_ooc(f"It is done, sire. Medieval'd {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_unmedieval(client, id):
    """
    Return a user's IC chat to normal speech.
    Usage: /unmedieval <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if targets:
        for c in targets:
            if not c.medieval:
                client.send_ooc("That player is not speaking Ye Olde English!")
            else:
                database.log_area("unmedieval", client, client.area, target=c)
                c.medieval = False
                c.send_ooc("Hark! Thine speech hast been returneth to normal.")
        client.send_ooc(f"Un-medieval'd {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only(area_owners=True)
@command(Arg("tog", bool, default=None, help="on/off"))
def ooc_cmd_medieval_mode(client, tog):
    """
    Toggle medieval mode for this area. All IC messages will be transformed into Ye Olde English.
    Usage: /medieval_mode [on/off]
    """
    client.area.medieval_mode = not client.area.medieval_mode if tog is None else tog
    stat = "now" if client.area.medieval_mode else "no longer"
    client.area.broadcast_ooc(f"This area is {stat} in Medieval Mode. Hark!")