from server import database
from server.constants import TargetType
from server.exceptions import ArgumentError

from . import mod_only

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
def ooc_cmd_disemvowel(client, arg):
    """
    Remove all vowels from a user's IC chat.
    Usage: /disemvowel <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /disemvowel <id>.")
    if targets:
        for c in targets:
            database.log_area("disemvowel", client, client.area, target=c)
            c.disemvowel = True
        client.send_ooc(f"Disemvowelled {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
def ooc_cmd_undisemvowel(client, arg):
    """
    Give back the freedom of vowels to a user.
    Usage: /undisemvowel <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /undisemvowel <id>.")
    if targets:
        for c in targets:
            database.log_area("undisemvowel", client, client.area, target=c)
            c.disemvowel = False
        client.send_ooc(f"Undisemvowelled {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
def ooc_cmd_shake(client, arg):
    """
    Scramble the words in a user's IC chat.
    Usage: /shake <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /shake <id>.")
    if targets:
        for c in targets:
            database.log_area("shake", client, client.area, target=c)
            c.shaken = True
        client.send_ooc(f"Shook {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


@mod_only()
def ooc_cmd_unshake(client, arg):
    """
    Give back the freedom of coherent grammar to a user.
    Usage: /unshake <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /unshake <id>.")
    if targets:
        for c in targets:
            database.log_area("unshake", client, client.area, target=c)
            c.shaken = False
        client.send_ooc(f"Unshook {len(targets)} existing client(s).")
    else:
        client.send_ooc("No targets found.")


def ooc_cmd_rainbow(client, arg):
    """
    rainbow text is back baybee
    Usage: /rainbow [true/false]
    """
    client.rainbow = not client.rainbow
    toggle = "now" if client.rainbow else "no longer"
    client.send_ooc(f"You will {toggle} have rainbowtext.")


@mod_only()
def ooc_cmd_medieval(client, arg):
    """
    Transform a user's IC chat into Ye Olde English.
    Usage: /medieval <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /medieval <id>.")
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
def ooc_cmd_unmedieval(client, arg):
    """
    Return a user's IC chat to normal speech.
    Usage: /unmedieval <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except Exception:
        raise ArgumentError("You must specify a target. Use /unmedieval <id>.")
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
def ooc_cmd_medieval_mode(client, arg):
    """
    Toggle medieval mode for this area. All IC messages will be transformed into Ye Olde English.
    Usage: /medieval_mode [on/off]
    """
    if len(arg.split()) > 1:
        raise ArgumentError("This command can only take one argument ('on' or 'off') or no arguments at all!")
    if arg:
        if arg == "on":
            client.area.medieval_mode = True
        elif arg == "off":
            client.area.medieval_mode = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.area.medieval_mode = not client.area.medieval_mode
    stat = "now" if client.area.medieval_mode else "no longer"
    client.area.broadcast_ooc(f"This area is {stat} in Medieval Mode. Hark!")
