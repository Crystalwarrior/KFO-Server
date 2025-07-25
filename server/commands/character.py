import shlex

import random

from server import database
from server.constants import TargetType, derelative
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    "ooc_cmd_switch",
    "ooc_cmd_pos",
    "ooc_cmd_pair",
    "ooc_cmd_triple_pair",
    "ooc_cmd_unpair",
    "ooc_cmd_pair_order",
    "ooc_cmd_forcepos",
    "ooc_cmd_force_switch",
    "ooc_cmd_kill",
    "ooc_cmd_randomchar",
    "ooc_cmd_charcurse",
    "ooc_cmd_uncharcurse",
    "ooc_cmd_charids",
    "ooc_cmd_reload",
    "ooc_cmd_blind",
    "ooc_cmd_unblind",
    "ooc_cmd_player_move_delay",
    "ooc_cmd_player_hide",
    "ooc_cmd_player_unhide",
    "ooc_cmd_hide",
    "ooc_cmd_unhide",
    "ooc_cmd_sneak",
    "ooc_cmd_unsneak",
    "ooc_cmd_freeze",
    "ooc_cmd_unfreeze",
    "ooc_cmd_listen_pos",
    "ooc_cmd_unlisten_pos",
    "ooc_cmd_save_character_data",
    "ooc_cmd_load_character_data",
    "ooc_cmd_keys_set",
    "ooc_cmd_keys_add",
    "ooc_cmd_keys_remove",
    "ooc_cmd_keys",
    "ooc_cmd_kms",
    "ooc_cmd_chardesc",
    "ooc_cmd_chardesc_clear",
    "ooc_cmd_chardesc_set",
    "ooc_cmd_chardesc_get",
    "ooc_cmd_narrate",
    "ooc_cmd_blankpost",
    "ooc_cmd_firstperson",
    "ooc_cmd_showname",
    "ooc_cmd_charlists",
    "ooc_cmd_charlist",
    "ooc_cmd_webfiles",
    "ooc_cmd_set_url",
    "ooc_cmd_get_urls",
]


def ooc_cmd_set_url(client, arg):
    """
    This command sets the URL of the current character.
    That URL is used client-side on AOG and server-side with the /get_link and /get_links commands.
    Usage: /set_url <url>
    """

    arg_strip = arg.strip()

    if arg_strip == "":
        client.send_ooc("URL has been reset successfully.")
    else:
        client.send_ooc(f"URL set to {arg_strip}")
    client.char_url = arg_strip

def ooc_cmd_get_urls(client, arg):
    """
    This command returns the server's URL List.
    Usage: /get_urls
    """
    f_server_links = "Server URLs:\n"
    for name, url in client.server.server_links.items():
        f_server_links += f"{name}: {url} \n"
    client.send_ooc(f_server_links)

def ooc_cmd_switch(client, arg):
    """
    Switch to another character. If moderator and the specified character is
    currently being used, the current user of that character will be
    automatically reassigned a character.
    Usage: /switch <name>
    """
    if len(arg) == 0:
        client.char_select()
        return
    try:
        # loser wants to spectate
        if arg == "-1" or arg.lower() == "spectator":
            cid = -1
        elif not arg.isnumeric():
            cid = client.area.area_manager.get_char_id_by_name(arg)
        else:
            cid = int(arg)
    except ServerError:
        raise
    try:
        client.change_character(
            cid, client.is_mod or client in client.area.owners)
    except ClientError:
        raise
    client.send_ooc("Character changed.")


def ooc_cmd_pos(client, arg):
    """
    Set the place your character resides in the area.
    Usage: /pos <name>
    """
    if len(arg) == 0:
        client.send_ooc(f"Your current position is {client.pos}.")
    else:
        try:
            client.change_position(arg)
        except ClientError:
            raise
        client.area.broadcast_evidence_list()
        client.send_ooc("Position changed.")


def ooc_cmd_pair(client, arg):
    """
    Pair with someone. Overrides client pairing choice.
    Run by itself to check your current (last?) pairing partner.
    Usage: /pair [cid|charname]
    """
    if len(arg) == 0:
        char = client.charid_pair
        if client.charid_pair in range(0, len(client.area.area_manager.char_list)):
            char = client.area.area_manager.char_list[client.charid_pair]
        client.send_ooc(f"Your current pair character is '{char}'.")
        return

    if arg.isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), True
        )
        if len(targets) > 0:
            client.charid_pair = targets[0].char_id
            client.charid_pair_override = True
    else:
        for i in range(0, len(client.area.area_manager.char_list)):
            if arg.lower() == client.area.area_manager.char_list[i].lower():
                client.charid_pair = i
                client.charid_pair_override = True

    if client.charid_pair_override:
        char = client.charid_pair
        if client.charid_pair in range(0, len(client.area.area_manager.char_list)):
            char = client.area.area_manager.char_list[client.charid_pair]
        client.send_ooc(f"Successfully paired with '{char}'! Ask them to pair with you back, and show up on the same /pos for it to work.")
    else:
        client.send_ooc("Pairing target not found!")


def ooc_cmd_unpair(client, arg):
    """
    Stop pairing with someone. Stops overriding client pairing choice.
    Usage: /unpair
    """
    if client.charid_pair_override:
        client.charid_pair = -1
        client.charid_pair_override = False
        client.send_ooc("You're no longer force-paired.")
    else:
        client.send_ooc("Serverside force-pairing is already disabled, check your client pairing settings!")


def ooc_cmd_pair_order(client, arg):
    """
    Choose if you'll appear in front or behind someone when pairing. Only works when using serverside /pair
    [order] can be either front/0 or behind/1
    Usage: /pair_order [order]
    """
    if client.charid_pair_override:
        msg = ['in front of', 'behind']
        if arg:
            if arg.lower() == 'front':
                client.pair_order = 0
            elif arg.lower() == 'behind':
                client.pair_order = 1
            elif arg.isdigit() and int(arg) in [0, 1]:
                client.pair_order = int(arg)
        else:
            client.pair_order = (client.pair_order + 1) % 2
        client.send_ooc(f"You will now appear {msg[client.pair_order]} your pairing partner.")
    else:
        client.send_ooc("Serverside pairing is disabled, use your client pairing settings or use /pair command!")


@mod_only(area_owners=True)
def ooc_cmd_forcepos(client, arg):
    """
    Set the place another character resides in the area.
    Usage: /forcepos <pos> <target>
    """
    args = arg.split()

    if len(args) < 1:
        raise ArgumentError(
            'Not enough arguments. Use /forcepos <pos> <target>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".'
        )

    targets = []

    pos = args[0]
    if len(args) > 1:
        targets = client.server.client_manager.get_targets(
            client, TargetType.CHAR_NAME, " ".join(args[1:]), True
        )
        if len(targets) == 0 and args[1].isdigit():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[1]), True
            )
        if len(targets) == 0:
            targets = client.server.client_manager.get_targets(
                client, TargetType.OOC_NAME, " ".join(args[1:]), True
            )
        if len(targets) == 0:
            raise ArgumentError("No targets found.")
    else:
        for c in client.area.clients:
            targets.append(c)

    for t in targets:
        try:
            t.change_position(pos)
            t.area.broadcast_evidence_list()
            t.send_ooc(f"Forced into /pos {pos}.")
            database.log_area("forcepos", client, client.area,
                              target=t, message=pos)
        except ClientError:
            raise

    client.area.broadcast_ooc(
        "{} forced {} client(s) into /pos {}.".format(
            client.showname, len(targets), pos
        )
    )


def ooc_cmd_force_switch(client, arg):
    """
    Force another user to select another character.
    Optional [char] forces them into a specific character.
    Usage: /force_switch <id> [char]
    """
    if not arg:
        raise ArgumentError(
            'Not enough arguments. Usage: /force_switch <id> [char]')
    args = shlex.split(arg)
    try:
        if args[0].isnumeric():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[0]), False
            )
        else:
            targets = client.server.client_manager.get_targets(
                client, TargetType.CHAR_NAME, args[0], False
            )
        for target in targets:
            force_switch(client, target, " ".join(args[1:]))
    except Exception as ex:
        raise ArgumentError(
            f"Error encountered: {ex}. Use /force_switch <target's id> [character] as a mod or area owner."
        )


def force_switch(client, target, char=""):
    if not client.is_mod and client not in target.area.owners:
        raise ClientError(f'Insufficient permissions for {char}')
    if char != "":
        try:
            if char == "-1" or char.lower() == "spectator":
                cid = -1
            elif not char.isnumeric():
                cid = target.area.area_manager.get_char_id_by_name(char)
            else:
                cid = int(char)
        except ServerError:
            raise
        try:
            if cid == -1:
                charname = "Spectator"
            else:
                charname = target.area.area_manager.char_list[cid]
            target.send_ooc(f"You've been forcibly swapped to {charname}.")
            target.change_character(cid, True)
        except ClientError:
            raise
    else:
        target.send_ooc(f"You've been forced into character select screen.")
        target.char_select()


@mod_only(area_owners=True)
def ooc_cmd_kill(client, arg):
    """
    Force the character into spectator mode with a message that they have died.
    Usage: /kill <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = []
        ids = [int(s) for s in arg.split(" ")]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, targ_id, False
            )
            if c:
                targets = targets + c
    except Exception:
        raise ArgumentError("You must specify a target. Use /kill <id(s)>.")

    try:
        for target in targets:
            force_switch(client, target, "-1")
            target.send_ooc(f"💀You are dead!💀")
    except Exception as ex:
        raise ArgumentError(
            f"Error encountered: {ex}. Use /kill <id(s)> as a mod or area owner."
        )

def ooc_cmd_randomchar(client, arg):
    """
    Select a random character.
    Usage: /randomchar
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    if len(client.charcurse) > 0:
        free_id = random.choice(client.charcurse)
    else:
        try:
            free_id = client.area.get_rand_avail_char_id()
        except AreaError:
            raise
    try:
        client.change_character(free_id)
    except ClientError:
        raise
    client.send_ooc("Randomly switched to {}".format(client.char_name))


@mod_only()
def ooc_cmd_charcurse(client, arg):
    """
    Lock a user into being able to choose only from a list of characters.
    Usage: /charcurse <id> [charids...]
    """
    if len(arg) == 0:
        raise ArgumentError(
            "You must specify a target (an ID) and at least one character ID. Consult /charids for the character IDs."
        )
    elif len(arg) == 1:
        raise ArgumentError(
            "You must specific at least one character ID. Consult /charids for the character IDs."
        )
    args = arg.split()
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(args[0]), False
        )
    except Exception:
        raise ArgumentError(
            "You must specify a valid target! Make sure it is a valid ID."
        )
    if targets:
        for c in targets:
            log_msg = ""
            part_msg = " [" + str(c.id) + "] to"
            for raw_cid in args[1:]:
                try:
                    cid = int(raw_cid)
                    c.charcurse.append(cid)
                    part_msg += " " + \
                        str(client.area.area_manager.char_list[cid]) + ","
                    log_msg += " " + \
                        str(client.area.area_manager.char_list[cid]) + ","
                except:
                    ArgumentError(
                        "" + str(raw_cid) +
                        " does not look like a valid character ID."
                    )
            part_msg = part_msg[:-1]
            part_msg += "."
            log_msg = log_msg[:-1]
            c.char_select()
            database.log_area(
                "charcurse", client, client.area, target=c, message=log_msg
            )
            client.send_ooc("Charcursed" + part_msg)
    else:
        client.send_ooc("No targets found.")


@mod_only()
def ooc_cmd_uncharcurse(client, arg):
    """
    Remove the character choice restrictions from a user.
    Usage: /uncharcurse <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target (an ID).")
    args = arg.split()
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(args[0]), False
        )
    except Exception:
        raise ArgumentError(
            "You must specify a valid target! Make sure it is a valid ID."
        )
    if targets:
        for c in targets:
            if len(c.charcurse) > 0:
                c.charcurse = []
                database.log_area("uncharcurse", client, client.area, target=c)
                client.send_ooc(f"Uncharcursed [{c.id}].")
                c.char_select()
            else:
                client.send_ooc(f"[{c.id}] is not charcursed.")
    else:
        client.send_ooc("No targets found.")


def ooc_cmd_charids(client, arg):
    """
    Show character IDs corresponding to each character name.
    Usage: /charids
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    msg = "Here is a list of all available characters on the server:"
    for c in range(0, len(client.area.area_manager.char_list)):
        msg += "\n[" + str(c) + "] " + client.area.area_manager.char_list[c]
    client.send_ooc(msg)


def ooc_cmd_reload(client, arg):
    """
    Reload a character to its default position and state.
    Usage: /reload
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    try:
        client.reload_character()
    except ClientError:
        raise
    client.send_ooc("Character reloaded.")


@mod_only(hub_owners=True)
def ooc_cmd_blind(client, arg):
    """
    Blind the targeted player(s) from being able to see or talk IC.
    Usage: /blind <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = []
        ids = [int(s) for s in arg.split(" ")]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, targ_id, False
            )
            if c:
                targets = targets + c
    except Exception:
        raise ArgumentError("You must specify a target. Use /blind <id>.")

    if targets:
        for c in targets:
            if c.blinded:
                client.send_ooc(f"Client [{c.id}] {c.name} already blinded! Use /unblind {c.id} to undo.")
                continue
            c.blind(True)
            client.send_ooc(
                f"You have blinded [{c.id}] {c.name} from using /getarea and seeing non-broadcasted IC messages."
            )
    else:
        raise ArgumentError("No targets found.")


@mod_only(hub_owners=True)
def ooc_cmd_unblind(client, arg):
    """
    Undo effects of the /blind command.
    Usage: /unblind <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = []
        ids = [int(s) for s in arg.split(" ")]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, targ_id, False
            )
            if c:
                targets = targets + c
    except Exception:
        raise ArgumentError("You must specify a target. Use /unblind <id>.")

    if targets:
        for c in targets:
            if not c.blinded:
                client.send_ooc(f"Client [{c.id}] {c.name} already unblinded! Use /blind {c.id} to blind them.")
                continue
            c.blind(False)
            client.send_ooc(f"You have unblinded [{c.id}] {c.name}.")
    else:
        raise ArgumentError("No targets found.")


def ooc_cmd_player_move_delay(client, arg):
    """
    Set the player's move delay to a value in seconds. Can be negative.
    Delay must be from -1800 to 1800 in seconds or empty to check.
    Usage: /player_move_delay <id> [delay]
    """
    args = shlex.split(arg)
    try:
        if len(args) > 0 and (
            client.is_mod or client in client.area.area_manager.owners
        ):
            # Try to find by char name first
            targets = client.server.client_manager.get_targets(
                client, TargetType.CHAR_NAME, args[0]
            )
            # If that doesn't work, find by client ID
            if len(targets) == 0 and args[0].isdigit():
                targets = client.server.client_manager.get_targets(
                    client, TargetType.ID, int(args[0])
                )
            # If that doesn't work, find by OOC Name
            if len(targets) == 0:
                targets = client.server.client_manager.get_targets(
                    client, TargetType.OOC_NAME, args[0]
                )
            c = targets[0]
            if len(args) > 1:
                move_delay = min(
                    1800, max(-1800, int(args[1]))
                )  # Move delay is limited between -1800 and 1800
                c.move_delay = move_delay
                client.send_ooc(
                    f"Set move delay for {c.char_name} to {c.move_delay}.")
            else:
                client.send_ooc(
                    f"Move delay for {c.char_name} is {c.move_delay}.")
        else:
            client.send_ooc(f"Your current move delay is {client.move_delay}.")
    except ValueError:
        raise ArgumentError("Delay must be an integer between -1800 and 1800.")
    except IndexError:
        raise ArgumentError(
            "Target client not found. Use /player_move_delay <id> [delay]."
        )
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_player_hide(client, arg):
    """
    Hide player(s) from /getarea and playercounts.
    If <id> is *, it will hide everyone in the area excluding yourself and CMs.
    Usage: /player_hide <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    args = arg.split()
    if args[0] == "*":
        targets = [
            c for c in client.area.clients if c != client and c != client.area.owners
        ]
    else:
        try:
            targets = []
            ids = [int(s) for s in args]
            for targ_id in ids:
                c = client.server.client_manager.get_targets(
                    client, TargetType.ID, targ_id, False
                )
                if c:
                    targets = targets + c
        except Exception:
            raise ArgumentError(
                "You must specify a target. Use /player_unhide <id> [id(s)]."
            )
    if targets:
        for c in targets:
            if c.hidden:
                raise ClientError(
                    f"Client [{c.id}] {c.showname} already hidden!")
            c.hide(True)
            client.send_ooc(
                f"You have hidden [{c.id}] {c.showname} from /getarea and playercounts."
            )
    else:
        client.send_ooc("No targets found.")


@mod_only(hub_owners=True)
def ooc_cmd_player_unhide(client, arg):
    """
    Unhide player(s) from /getarea and playercounts.
    If <id> is *, it will unhide everyone in the area excluding yourself and CMs.
    Usage: /player_unhide <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    args = arg.split()
    if args[0] == "*":
        targets = [
            c for c in client.area.clients if c != client and c != client.area.owners
        ]
    else:
        try:
            targets = []
            ids = [int(s) for s in args]
            for targ_id in ids:
                c = client.server.client_manager.get_targets(
                    client, TargetType.ID, targ_id, False
                )
                if c:
                    targets = targets + c
        except Exception:
            raise ArgumentError(
                "You must specify a target. Use /player_unhide <id> [id(s)]."
            )
    if targets:
        for c in targets:
            if not c.hidden:
                raise ClientError(
                    f"Client [{c.id}] {c.showname} already revealed!")
            c.hide(False)
            client.send_ooc(
                f"You have revealed [{c.id}] {c.showname} for /getarea and playercounts."
            )
    else:
        client.send_ooc("No targets found.")


def ooc_cmd_hide(client, arg):
    """
    Try to hide in the targeted evidence name or ID.
    Usage: /hide <evi_name/id>
    """
    if arg == "":
        raise ArgumentError(
            "Use /hide <evi_name/id> to hide in evidence, or /unhide to stop hiding."
        )
    try:
        if arg.isnumeric():
            arg = str(int(arg) - 1)
        client.hide(True, arg)
        client.area.broadcast_area_list(client)
    except ValueError:
        raise
    except (AreaError, ClientError):
        raise


def ooc_cmd_unhide(client, arg):
    """
    Stop hiding.
    Usage: /unhide
    """
    client.hide(False)
    client.area.broadcast_area_list(client)


def ooc_cmd_sneak(client, arg):
    """
    Begin sneaking a.k.a. hide your area moving messages from the OOC.
    Optional [id] forces a character to sneak.
    Usage: /sneak [id]
    """
    if not arg:
        if client.sneaking:
            raise ClientError(
                "You are already sneaking! Use /unsneak to stop sneaking.")
        client.sneak(True)
    else:
        args = shlex.split(arg)
        try:
            if args[0].isnumeric():
                targets = client.server.client_manager.get_targets(
                    client, TargetType.ID, int(args[0]), False
                )
            else:
                targets = client.server.client_manager.get_targets(
                    client, TargetType.CHAR_NAME, args[0], False
                )
            for x in targets:
                force_sneak(client, x)
        except Exception as ex:
            raise ArgumentError(
                f"Error encountered: {ex}. Use /sneak [id]")


def ooc_cmd_unsneak(client, arg):
    """
    Stop sneaking a.k.a. show your area moving messages in the OOC.
    Optional [id] forces a character to stop sneaking.
    Usage: /unsneak [id]
    """
    if not arg:
        if not client.sneaking:
            raise ClientError(
                "You are not sneaking! Use /sneak to start sneaking.")
        client.sneak(False)
    else:
        args = shlex.split(arg)
        try:
            if args[0].isnumeric():
                targets = client.server.client_manager.get_targets(
                    client, TargetType.ID, int(args[0]), False
                )
            else:
                targets = client.server.client_manager.get_targets(
                    client, TargetType.CHAR_NAME, args[0], False
                )
            for x in targets:
                force_unsneak(client, x)
        except Exception as ex:
            raise ArgumentError(
                f"Error encountered: {ex}. Use /unsneak [id]")


@mod_only(area_owners=True)
def force_sneak(client, arg):
    arg.sneak(True)


@mod_only(area_owners=True)
def force_unsneak(client, arg):
    arg.sneak(False)


@mod_only(area_owners=True)
def ooc_cmd_freeze(client, arg):
    """
    Freeze targeted player(s) from being able to move between areas.
    Usage: /freeze <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = []
        ids = [int(s) for s in arg.split(" ")]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, targ_id, False
            )
            if c:
                targets = targets + c
    except Exception:
        raise ArgumentError("You must specify a target. Use /freeze <id>.")

    if targets:
        for c in targets:
            if c.frozen:
                client.send_ooc(f"Client [{c.id}] {c.name} already frozen! Use /unfreeze {c.id} to undo.")
                continue
            c.freeze(True)
            client.send_ooc(
                f"You have frozen [{c.id}] {c.name} from being able to move between areas."
            )
    else:
        raise ArgumentError("No targets found.")


@mod_only(hub_owners=True)
def ooc_cmd_unfreeze(client, arg):
    """
    Undo effects of the /freeze command.
    Usage: /unfreeze <id(s)>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    try:
        targets = []
        ids = [int(s) for s in arg.split(" ")]
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, targ_id, False
            )
            if c:
                targets = targets + c
    except Exception:
        raise ArgumentError("You must specify a target. Use /unfreeze <id>.")

    if targets:
        for c in targets:
            if not c.frozen:
                client.send_ooc(f"Client [{c.id}] {c.name} already unfrozen! Use /freeze {c.id} to freeze them.")
                continue
            c.freeze(False)
            client.send_ooc(f"You have unfrozen [{c.id}] {c.name}.")
    else:
        raise ArgumentError("No targets found.")


def ooc_cmd_listen_pos(client, arg):
    """
    Start only listening to your currently occupied pos.
    All messages outside of that pos will be reflected in the OOC.
    Optional argument is a list of positions you want to listen to.
    Usage: /listen_pos [pos(s)]
    """
    args = arg.split()
    value = "self"
    if len(args) > 0:
        value = args

    client.listen_pos = value
    if value == "self":
        value = f"listening to your own pos {client.pos}"
    else:
        value = ", ".join(value)
        value = f"listening to pos {value}"
    client.send_ooc(f"You are {value}. Use /unlisten_pos to stop listening.")


def ooc_cmd_unlisten_pos(client, arg):
    """
    Undo the effects of /listen_pos command so you stop listening to the position(s).
    Usage: /unlisten_pos
    """
    if client.listen_pos is None:
        raise ClientError("You are not listening to any pos at the moment!")
    client.listen_pos = None
    client.send_ooc(
        "You re no longer listening to any pos (All IC messages will appear as normal)."
    )


@mod_only(hub_owners=True)
def ooc_cmd_save_character_data(client, arg):
    """
    Save the move_delay, keys, etc. for characters into a file in the storage/character_data/ folder.
    Usage: /save_character_data <path>
    """
    if len(arg) < 3:
        client.send_ooc("Filename must be at least 3 symbols long!")
        return

    try:
        path = "storage/character_data"
        arg = f"{path}/{derelative(arg)}.yaml"
        client.area.area_manager.save_character_data(arg)
        client.send_ooc(f"Saving as {arg} character data...")
    except AreaError:
        raise


@mod_only(hub_owners=True)
def ooc_cmd_load_character_data(client, arg):
    """
    Load the move_delay, keys, etc. for characters from a file in the storage/character_data/ folder.
    Usage: /load_character_data <path>
    """
    try:
        path = "storage/character_data"
        arg = f"{path}/{derelative(arg)}.yaml"
        client.area.area_manager.load_character_data(arg)
        client.send_ooc(f"Loading {arg} character data...")
    except AreaError:
        raise


def mod_keys(client, arg, mod=0):
    """
    A helper function to reduce copy-pasted code for /keys_(set|add|remove) commands.
    Modifies the keys of the target client/character folder/character id.
    :param arg: The arguments passed from the /keys_(set|add|remove) commands.
    :param mod: A number from 0-2 that dictates the operation. 0 = set, 1 = add, 2 = remove.
    """
    args = arg.split()
    if len(args) <= 1 and mod != 0:
        raise ArgumentError(
            "Please provide the key(s) to set. Keys must be a number 5 or a link eg. 1-5."
        )
    try:
        if args[0].isnumeric():
            target = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[0]), False
            )
            if target:
                target = target[0].char_id
            else:
                if args[0] != "-1" and (int(args[0]) in client.area.area_manager.char_list):
                    target = int(args[0])
        else:
            try:
                target = client.area.area_manager.get_char_id_by_name(arg)
            except (ServerError):
                raise

        if len(args) > 1:
            args = args[1:]
        else:
            args = []
        keys = []

        for a in args:
            for key in a.split("-"):
                # make sure all the keys are integers
                key = int(key)
            if mod in (1, 2):
                keys = client.area.area_manager.get_character_data(
                    target, "keys", [])
            if a in keys and mod == 2:
                keys.remove(a)
            elif not (a in keys):
                keys.append(a)
        client.area.area_manager.set_character_data(target, "keys", keys)
        client.send_ooc(
            f"Character folder {client.area.area_manager.char_list[target]}'s keys are updated: {keys}"
        )
    except ValueError:
        raise ArgumentError("Keys must be a number like 5 or a link eg. 1-5.")
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
def ooc_cmd_keys_set(client, arg):
    """
    Sets the keys of the target client/character folder/character id to the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_set <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_set <char> [key(s)].")

    mod_keys(client, arg)


@mod_only(hub_owners=True)
def ooc_cmd_keys_add(client, arg):
    """
    Adds the keys of the target client/character folder/character id to the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_add <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_add <char> [key(s)].")

    mod_keys(client, arg, 1)


@mod_only(hub_owners=True)
def ooc_cmd_keys_remove(client, arg):
    """
    Remvove the keys of the target client/character folder/character id from the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_remove <char> [key(s)]
    """
    if not arg:
        raise ArgumentError(
            "Usage: /keys_remove <char> [area id(s)]. Removes the selected 'keys' from the user."
        )

    mod_keys(client, arg, 2)


def ooc_cmd_keys(client, arg):
    """
    Check your own keys, or someone else's (if admin).
    Keys allow you to /lock or /unlock specific areas, OR
    area links if it's formatted like 1-5
    Usage: /keys [target_id]
    """
    args = arg.split()
    if len(args) < 1:
        client.send_ooc(f"Your current keys are {client.keys}")
        return
    if not client.is_mod and not (client in client.area.area_manager.owners):
        raise ClientError("Only mods and GMs can check other people's keys.")
    if len(args) == 1:
        try:
            if args[0].isnumeric():
                target = client.server.client_manager.get_targets(
                    client, TargetType.ID, int(args[0]), False
                )
                if target:
                    target = target[0].char_id
                else:
                    if args[0] != "-1" and (int(args[0]) in client.area.area_manager.char_list):
                        target = int(args[0])
            else:
                try:
                    target = client.area.area_manager.get_char_id_by_name(arg)
                except (ServerError):
                    raise
            keys = client.area.area_manager.get_character_data(
                target, "keys", [])
            client.send_ooc(
                f"{client.area.area_manager.char_list[target]} current keys are {keys}"
            )
        except Exception:
            raise ArgumentError("Target not found.")
    else:
        raise ArgumentError("Usage: /keys [target_id].")


def ooc_cmd_kms(client, arg):
    """
    Stands for Kick MySelf - Kick other instances of the client opened by you.
    Useful if you lose connection and the old client is ghosting.
    Usage: /kms
    """
    if arg != "":
        raise ArgumentError("This command takes no arguments!")
    for target in client.server.client_manager.get_multiclients(
        client.ipid, client.hdid
    ):
        if target != client:
            target.disconnect()
    client.send_ooc("Kicked other instances of client.")
    database.log_misc("kms", client)


def ooc_cmd_chardesc(client, arg):
    """
    Look at your own character description if no arugments are provided.
    Look at another person's character description if only ID is provided.
    Set your own character description* if description is provided instead of ID.
    * Do note that the first sentence of your chardesc is displayed during area transfer messages!
    To set someone else's char desc as an admin/GM, or look at their desc, use /chardesc_set or /chardesc_get.
    Usage: /chardesc [desc/id]
    """
    if len(arg) == 0:
        client.send_ooc(f"📜{client.char_name} Description: {client.desc}")
        database.log_area("chardesc.request", client, client.area)
        return

    if client.blinded:
        raise ClientError("You are blinded!")

    if client.area.dark:
        raise ClientError("This area is shrouded in darkness!")

    if arg.isnumeric():
        try:
            target = client.server.client_manager.get_targets(
                client, TargetType.ID, int(arg), True
            )[0].char_id
            desc = client.area.area_manager.get_character_data(
                target, "desc", "")
            target = client.area.area_manager.char_list[target]
            client.send_ooc(f"📜{target} Description: {desc}")
            database.log_area("chardesc.request", client,
                              client.area, message=target)
        except Exception:
            raise ArgumentError("Target not found.")
    else:
        client.desc = arg
        if not client.hidden and not client.sneaking:
            desc = arg[:128]
            if len(arg) > len(desc):
                desc += f"... Use /chardesc {client.id} to read the rest."
            client.area.broadcast_ooc(
                f"{client.showname} changed their character description to: {desc}."
            )
        database.log_area("chardesc.change", client, client.area, message=arg)


def ooc_cmd_chardesc_clear(client, arg):
    """
    Clear your chardesc.
    Usage: /chardesc_clear
    """
    client.area.area_manager.set_character_data(client.char_id, "desc", "")
    client.area.broadcast_ooc(
        f"{client.showname} cleared their character description."
    )
    database.log_area(
        "chardesc.clear", client, client.area
    )


@mod_only(hub_owners=True)
def ooc_cmd_chardesc_set(client, arg):
    """
    Set someone else's character description to desc or clear it.
    Usage: /chardesc_set <id> [desc]
    """
    args = arg.split(" ")
    if len(args) < 1:
        raise ArgumentError(
            "Not enough arguments. Usage: /chardesc_set <id> [desc]")
    try:
        if args[0].isnumeric():
            target = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[0]), False
            )
            if target:
                target = target[0].char_id
            else:
                if args[0] != "-1" and (int(args[0]) in client.area.area_manager.char_list):
                    target = int(args[0])
        else:
            try:
                target = client.area.area_manager.get_char_id_by_name(arg)
            except (ServerError):
                raise
        desc = ""
        if len(args) > 1:
            desc = " ".join(args[1:])
        client.area.area_manager.set_character_data(target, "desc", desc)
        target = client.area.area_manager.char_list[target]
        client.send_ooc(f"📜{target} Description: {desc}")
        database.log_area(
            "chardesc.set", client, client.area, message=f"{target}: {desc}"
        )
    except Exception:
        raise ArgumentError("Target not found.")


@mod_only(hub_owners=True)
def ooc_cmd_chardesc_get(client, arg):
    """
    Get someone else's character description.
    Usage: /chardesc_get <id>
    """
    try:
        if arg.isnumeric():
            target = client.server.client_manager.get_targets(
                client, TargetType.ID, int(arg), False
            )
            if target:
                target = target[0].char_id
            else:
                if arg != "-1" and (int(arg) in client.area.area_manager.char_list):
                    target = int(arg)
        else:
            try:
                target = client.area.area_manager.get_char_id_by_name(arg)
            except (ServerError):
                raise
        desc = client.area.area_manager.get_character_data(target, "desc", "")
        target = client.area.area_manager.char_list[target]
        client.send_ooc(f"📜{target} Description: {desc}")
        database.log_area(
            "chardesc.get", client, client.area, message=f"{target}: {desc}"
        )
    except Exception:
        raise ArgumentError("Target not found.")


def ooc_cmd_narrate(client, arg):
    """
    Speak as a Narrator for your next emote.
    If using 2.9.1, when you speak IC only the chat box will be affected, making you "narrate" over the current visuals.
    tog can be `on`, `off` or empty.
    Usage: /narrate [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError(
            "This command can only take one argument ('on' or 'off') or no arguments at all!"
        )
    if arg:
        if arg == "on":
            client.narrator = True
        elif arg == "off":
            client.narrator = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.narrator = not client.narrator
    if client.blankpost is True:
        client.blankpost = False
        client.send_ooc(
            "You cannot be a narrator and blankposting at the same time. Blankposting disabled!"
        )
    stat = "no longer be narrating"
    if client.narrator:
        stat = "be narrating now"
    client.send_ooc(f"You will {stat}.")


def ooc_cmd_blankpost(client, arg):
    """
    Use a blank image for your next emote (base/misc/blank.png, will be a missingno if you don't have it)
    tog can be `on`, `off` or empty.
    Usage: /blankpost [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError(
            "This command can only take one argument ('on' or 'off') or no arguments at all!"
        )
    if arg:
        if arg == "on":
            client.blankpost = True
        elif arg == "off":
            client.blankpost = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.blankpost = not client.blankpost
    if client.narrator is True:
        client.narrator = False
        client.send_ooc(
            "You cannot be a narrator and blankposting at the same time. Narrating disabled!"
        )
    stat = "no longer be blankposting"
    if client.blankpost:
        stat = "be blankposting now"
    client.send_ooc(f"You will {stat}.")


def ooc_cmd_firstperson(client, arg):
    """
    Speak as a Narrator for your next emote, but only to yourself. Everyone else will see the emote you used.
    If using 2.9.1, when you speak IC only the chat box will be affected.
    tog can be `on`, `off` or empty.
    Usage: /firstperson [tog]
    """
    if len(arg.split()) > 1:
        raise ArgumentError(
            "This command can only take one argument ('on' or 'off') or no arguments at all!"
        )
    if arg:
        if arg == "on":
            client.firstperson = True
        elif arg == "off":
            client.firstperson = False
        else:
            raise ArgumentError("Invalid argument: {}".format(arg))
    else:
        client.firstperson = not client.firstperson
    if client.narrator is True:
        client.narrator = False
        client.send_ooc(
            "You cannot be a narrator and firstperson at the same time. Narrating disabled!"
        )
    stat = "no longer be firstperson"
    if client.firstperson:
        stat = "be firstperson now"
    client.send_ooc(f"You will {stat}.")


def ooc_cmd_showname(client, arg):
    """
    Set your own showname similar to the showname box in the client.
    Note that using this command will override the showname box.
    Passing no [name] will reset your showname and start using the showname box again.
    Usage: /showname [name]
    """
    if len(arg) == 0:
        client.used_showname_command = False
        client.showname = ""
        client.send_ooc("Your showname is now reset.")
        return
    # having to copy-paste code from aoprotocol is kinda poopy, need to create a set_showname def
    if len(arg) > 20:
        client.send_ooc("Your IC showname is way too long!")
        return
    if not client.is_mod and arg.lstrip().lower().startswith("[m"):
        client.send_ooc(
            "Nice try! You may not spoof [M] tag in your showname.")
        return
    client.used_showname_command = True
    client.showname = arg
    client.send_ooc(f"You set your showname to '{client.showname}'.")


def ooc_cmd_charlists(client, arg):
    """
    Displays all the available charlists.
    Usage: /charlists
    """
    text = "Available charlists:"
    from os import listdir

    for F in listdir("storage/charlists/"):
        if F.lower().endswith(".yaml"):
            text += "\n- {}".format(F[:-5])

    client.send_ooc(text)


def ooc_cmd_webfiles(client, arg):
    """
    Gives a link to download each characters files from webAO
    Usage: /webfiles <id>
    """
    args = arg.split(" ")

    try:
        if args[0] == "*":
            targets = [
                c
                for c in client.area.clients
                if c != client and c != client.area.owners
            ]
        else:
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(args[0]), False
            )
    except ValueError:
        raise ArgumentError("Target ID must be a number or *.")

    try:
        for c in targets:
            client.send_ooc(f"To download the files, visit https://attorneyonline.github.io/webDownloader/index.html?char={c.iniswap}")
    except Exception:
        raise ClientError("You must specify a target. Use /webfiles <id>")


@mod_only(hub_owners=True)
def ooc_cmd_charlist(client, arg):
    """
    Load a character list. /charlists to see available character lists.
    Run /charlist by itself to reset it to the server's default.
    Usage: /charlist [path]
    """
    try:
        client.area.area_manager.load_characters(arg)
        if arg == "":
            client.send_ooc("Resetting the charlist...")
        else:
            client.send_ooc(f"Loading charlist {arg}...")
    except AreaError:
        raise
    except Exception:
        client.send_ooc("File not found!")


def ooc_cmd_triple_pair(client, arg):
    """
    Triple Pair with someone.
    Run by itself to check your current (last?) pairing partner.
    Usage: /triple_pair [cid|charname]
    """
    if len(arg) == 0:
        char = client.third_charid
        if client.third_charid in range(0, len(client.area.area_manager.char_list)):
            char = client.area.area_manager.char_list[client.third_charid]
        client.send_ooc(f"Your current triple pair character is '{char}'.")
        return

    if arg.isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), True
        )
        if len(targets) > 0:
            client.third_charid = targets[0].char_id
    else:
        for i in range(0, len(client.area.area_manager.char_list)):
            if arg.lower() == client.area.area_manager.char_list[i].lower():
                client.third_charid = i

    char = client.third_charid
    if client.third_charid in range(0, len(client.area.area_manager.char_list)):
        char = client.area.area_manager.char_list[client.third_charid]
    client.send_ooc(f"Successfully paired with '{char}'! Ask them to pair with you back, and show up on the same /pos for it to work.")
