import shlex

import random

from server import database
from server.constants import TargetType, derelative
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only, command, Arg, tokens_str

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
    "ooc_cmd_get_char_data",
    "ooc_cmd_set_char_data",
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
    "ooc_cmd_get_latest_area",
    "ooc_cmd_kick_to_latest_area",
    "ooc_cmd_set_latest_area",
]


@command(Arg("arg", rest=True, default="", help="character download URL"))
def ooc_cmd_set_url(client, arg):
    """
    This command sets the URL of the current character.
    That URL is used client-side on AOG and server-side with the /get_link and /get_links commands.
    Usage: /set_url <url>
    """
    client.char_url = arg.strip()
    if client.char_url == "":
        client.area.broadcast_ooc(f"[{client.id}] {client.showname} has cleared their download link.")
    else:
        client.area.broadcast_ooc(f"[{client.id}] {client.showname} has set their download link to:\n{client.char_url}")
    for c in client.area.clients:
        c.get_new_area_user_links()

@command()
def ooc_cmd_get_urls(client):
    """
    This command returns the server's URL List.
    Usage: /get_urls
    """
    if client.server.server_links is None:
        raise ServerError("Server's URL list is not configured.")
    f_server_links = "Server URLs:\n"
    for name, url in client.server.server_links.items():
        f_server_links += f"{name}: {url} \n"
    client.send_ooc(f_server_links)

@command(Arg("arg", rest=True, default="", help="character name/ID (blank = char select)"))
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


@command(Arg("arg", rest=True, default="", help="pos name (blank shows current)"))
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


@command(Arg("arg", rest=True, default="", help="client ID or char name (blank checks)"))
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


@command()
def ooc_cmd_unpair(client):
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


@command(Arg("arg", default="", help="front/0 or behind/1 (blank toggles)"))
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
@command(
    Arg("pos", help="pos, RANDOM or comma-separated list"),
    Arg("targets", variadic=True, default=None, help="targets (blank = everyone)"),
)
def ooc_cmd_forcepos(client, pos, targets):
    """
    Set the place another character resides in the area.
    Usage: /forcepos <pos> <target>
    if <pos> = RANDOM, all the <target>s will be forced into a random pos, pulled from the area's pos_lock.
    if <pos> contains the "," symbol then it will be treated as a list of positions to randomize by.
    """
    if targets is None:
        targets = list(client.area.clients)
    else:
        target_text = " ".join(targets)
        targets = client.server.client_manager.get_targets(
            client, TargetType.CHAR_NAME, target_text, True
        )
        if len(targets) == 0 and targets[0].isdigit():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(targets[0]), True
            )
        if len(targets) == 0:
            targets = client.server.client_manager.get_targets(
                client, TargetType.OOC_NAME, target_text, True
            )
        if len(targets) == 0:
            raise ArgumentError("No targets found.")

    for t in targets:
        try:
            _pos = pos
            choices = []
            if pos == "RANDOM":
                choices = t.area.pos_lock
            # given a list of pos
            for p in pos.split(","):
                choices.append(p.strip())
            # if we received NO choice
            if len(choices) <= 0:
                choices = ["wit", "def", "pro", "hlp", "hld", "jud"]
            elif len(choices) == 1:
                _pos = choices[0]
            else:
                _pos = random.choice(choices)
            t.change_position(_pos)
            t.area.broadcast_evidence_list()
            t.send_ooc(f"Forced into /pos {_pos}.")
            client.send_ooc(f"Forced [{t.id}] {t.showname} into /pos {_pos}.")
            database.log_area("forcepos", client, client.area,
                              target=t, message=pos)
        except ClientError:
            raise


@command(
    Arg("target", help="target id or char name"),
    Arg("char", rest=True, default="", type=tokens_str, help="character to force (blank = char select)"),
)
def ooc_cmd_force_switch(client, target, char):
    """
    Force another user to select another character.
    Optional [char] forces them into a specific character.
    Usage: /force_switch <id> [char]
    """
    try:
        if target.isnumeric():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(target), False
            )
        else:
            targets = client.server.client_manager.get_targets(
                client, TargetType.CHAR_NAME, target, False
            )
        for t in targets:
            force_switch(client, t, char)
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
@command(Arg("ids", int, variadic=True, help="client ID(s)"))
def ooc_cmd_kill(client, ids):
    """
    Force the character into spectator mode with a message that they have died.
    Usage: /kill <id(s)>
    """
    targets = []
    for targ_id in ids:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, targ_id, False
        )
        if c:
            targets = targets + c

    try:
        for target in targets:
            force_switch(client, target, "-1")
            target.send_ooc(f"💀You are dead!💀")
    except Exception as ex:
        raise ArgumentError(
            f"Error encountered: {ex}. Use /kill <id(s)> as a mod or area owner."
        )

@command()
def ooc_cmd_randomchar(client):
    """
    Select a random character.
    Usage: /randomchar
    """
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
@command(
    Arg("target", int, help="client ID"),
    Arg("charids", int, variadic=True, help="character IDs"),
)
def ooc_cmd_charcurse(client, target, charids):
    """
    Lock a user into being able to choose only from a list of characters.
    Usage: /charcurse <id> [charids...]
    """
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, target, False
        )
    except Exception:
        raise ArgumentError(
            "You must specify a valid target! Make sure it is a valid ID."
        )
    if targets:
        for c in targets:
            log_msg = ""
            part_msg = " [" + str(c.id) + "] to"
            for cid in charids:
                try:
                    c.charcurse.append(cid)
                    part_msg += " " + \
                        str(client.area.area_manager.char_list[cid]) + ","
                    log_msg += " " + \
                        str(client.area.area_manager.char_list[cid]) + ","
                except:
                    ArgumentError(
                        "" + str(cid) +
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
@command(Arg("id", int, help="client ID"))
def ooc_cmd_uncharcurse(client, id):
    """
    Remove the character choice restrictions from a user.
    Usage: /uncharcurse <id>
    """
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, id, False
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


@command()
def ooc_cmd_charids(client):
    """
    Show character IDs corresponding to each character name.
    Usage: /charids
    """
    msg = "Here is a list of all available characters on the server:"
    for c in range(0, len(client.area.area_manager.char_list)):
        msg += "\n[" + str(c) + "] " + client.area.area_manager.char_list[c]
    client.send_ooc(msg)


@command()
def ooc_cmd_reload(client):
    """
    Reload a character to its default position and state.
    Usage: /reload
    """
    try:
        client.reload_character()
    except ClientError:
        raise
    client.send_ooc("Character reloaded.")


@mod_only(hub_owners=True)
@command(Arg("ids", int, variadic=True, help="client ID(s)"))
def ooc_cmd_blind(client, ids):
    """
    Blind the targeted player(s) from being able to see or talk IC.
    Usage: /blind <id(s)>
    """
    targets = []
    for targ_id in ids:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, targ_id, False
        )
        if c:
            targets = targets + c

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
@command(Arg("ids", int, variadic=True, help="client ID(s)"))
def ooc_cmd_unblind(client, ids):
    """
    Undo effects of the /blind command.
    Usage: /unblind <id(s)>
    """
    targets = []
    for targ_id in ids:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, targ_id, False
        )
        if c:
            targets = targets + c

    if targets:
        for c in targets:
            if not c.blinded:
                client.send_ooc(f"Client [{c.id}] {c.name} already unblinded! Use /blind {c.id} to blind them.")
                continue
            c.blind(False)
            client.send_ooc(f"You have unblinded [{c.id}] {c.name}.")
    else:
        raise ArgumentError("No targets found.")


@command(
    Arg("target", default="", help="target (blank = yourself)"),
    Arg("delay", int, default=None, help="delay in seconds (-1800..1800)"),
)
def ooc_cmd_player_move_delay(client, target, delay):
    """
    Set the player's move delay to a value in seconds. Can be negative.
    Delay must be from -1800 to 1800 in seconds or empty to check.
    Usage: /player_move_delay <id> [delay]
    """
    try:
        if target and (
            client.is_mod or client in client.area.area_manager.owners
        ):
            # Try to find by char name first
            targets = client.server.client_manager.get_targets(
                client, TargetType.CHAR_NAME, target
            )
            # If that doesn't work, find by client ID
            if len(targets) == 0 and target.isdigit():
                targets = client.server.client_manager.get_targets(
                    client, TargetType.ID, int(target)
                )
            # If that doesn't work, find by OOC Name
            if len(targets) == 0:
                targets = client.server.client_manager.get_targets(
                    client, TargetType.OOC_NAME, target
                )
            c = targets[0]
            if delay is not None:
                move_delay = min(
                    1800, max(-1800, delay)
                )  # Move delay is limited between -1800 and 1800
                c.move_delay = move_delay
                client.send_ooc(
                    f"Set move delay for {c.char_name} to {c.move_delay}.")
            else:
                client.send_ooc(
                    f"Move delay for {c.char_name} is {c.move_delay}.")
        else:
            client.send_ooc(f"Your current move delay is {client.move_delay}.")
    except IndexError:
        raise ArgumentError(
            "Target client not found. Use /player_move_delay <id> [delay]."
        )
    except (AreaError, ClientError):
        raise


@mod_only(hub_owners=True)
@command(Arg("ids", variadic=True, help="client ID(s) or *"))
def ooc_cmd_player_hide(client, ids):
    """
    Hide player(s) from /getarea and playercounts.
    If <id> is *, it will hide everyone in the area excluding yourself and CMs.
    Usage: /player_hide <id(s)>
    """
    if ids[0] == "*":
        targets = [
            c for c in client.area.clients if c != client and c != client.area.owners
        ]
    else:
        targets = []
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, int(targ_id), False
            )
            if c:
                targets = targets + c
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
@command(Arg("ids", variadic=True, help="client ID(s) or *"))
def ooc_cmd_player_unhide(client, ids):
    """
    Unhide player(s) from /getarea and playercounts.
    If <id> is *, it will unhide everyone in the area excluding yourself and CMs.
    Usage: /player_unhide <id(s)>
    """
    if ids[0] == "*":
        targets = [
            c for c in client.area.clients if c != client and c != client.area.owners
        ]
    else:
        targets = []
        for targ_id in ids:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, int(targ_id), False
            )
            if c:
                targets = targets + c
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


@command(Arg("arg", rest=True, default="", help="evidence name or id"))
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


@command()
def ooc_cmd_unhide(client):
    """
    Stop hiding.
    Usage: /unhide
    """
    client.hide(False)
    client.area.broadcast_area_list(client)


@command(Arg("arg", rest=True, default="", help="target (blank = yourself)"))
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


@command(Arg("arg", rest=True, default="", help="target (blank = yourself)"))
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
@command(Arg("ids", int, variadic=True, help="client ID(s)"))
def ooc_cmd_freeze(client, ids):
    """
    Freeze targeted player(s) from being able to move between areas.
    Usage: /freeze <id(s)>
    """
    targets = []
    for targ_id in ids:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, targ_id, False
        )
        if c:
            targets = targets + c

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
@command(Arg("ids", int, variadic=True, help="client ID(s)"))
def ooc_cmd_unfreeze(client, ids):
    """
    Undo effects of the /freeze command.
    Usage: /unfreeze <id(s)>
    """
    targets = []
    for targ_id in ids:
        c = client.server.client_manager.get_targets(
            client, TargetType.ID, targ_id, False
        )
        if c:
            targets = targets + c

    if targets:
        for c in targets:
            if not c.frozen:
                client.send_ooc(f"Client [{c.id}] {c.name} already unfrozen! Use /freeze {c.id} to freeze them.")
                continue
            c.freeze(False)
            client.send_ooc(f"You have unfrozen [{c.id}] {c.name}.")
    else:
        raise ArgumentError("No targets found.")


@command(Arg("pos", variadic=True, default=None, help="pos(s) (blank = your own)"))
def ooc_cmd_listen_pos(client, pos):
    """
    Start only listening to your currently occupied pos.
    All messages outside of that pos will be reflected in the OOC.
    Optional argument is a list of positions you want to listen to.
    Usage: /listen_pos [pos(s)]
    """
    value = "self" if pos is None else pos

    client.listen_pos = value
    if value == "self":
        value = f"listening to your own pos {client.pos}"
    else:
        value = ", ".join(value)
        value = f"listening to pos {value}"
    client.send_ooc(f"You are {value}. Use /unlisten_pos to stop listening.")


@command()
def ooc_cmd_unlisten_pos(client):
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
@command(Arg("arg", rest=True, default="", help="save path"))
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
@command(Arg("arg", rest=True, default="", help="load path"))
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


def _resolve_char_arg(hub, text):
    """Resolve a character id or folder name to a character id."""
    if text.isdigit():
        char_id = int(text)
        if not hub.is_valid_char_id(char_id):
            raise ArgumentError(f"Unknown character id {char_id}.")
        return char_id
    try:
        return hub.get_char_id_by_name(text)
    except ServerError:
        raise ArgumentError(f"Unknown character '{text}'.")


@mod_only(hub_owners=True)
@command(
    Arg("target", help="char id or folder name"),
    Arg("key", default="", help="data key (blank = all)"),
)
def ooc_cmd_get_char_data(client, target, key):
    """
    View the custom data saved for a character (or a single key of it).
    Usage: /get_char_data <char id|folder> [key]
    """
    hub = client.area.area_manager
    folder = hub.char_list[_resolve_char_arg(hub, target)]
    data = hub.character_data.get(folder, {})
    if key:
        if key not in data:
            raise ArgumentError(f"Character '{folder}' has no data key '{key}'.")
        client.send_ooc(f"{folder}.{key} = {data[key]}")
        return
    if not data:
        client.send_ooc(f"Character '{folder}' has no saved data.")
        return
    for key, value in data.items():
        client.send_ooc(f"{folder}.{key} = {value}")


@mod_only(hub_owners=True)
@command(
    Arg("target", help="char id or folder name"),
    Arg("key", help="data key"),
    Arg("value", rest=True, default="", help="new value (blank removes the key)"),
)
def ooc_cmd_set_char_data(client, target, key, value):
    """
    Set (or clear) a custom data key for a character; omit the value to remove the key.
    Usage: /set_char_data <char id|folder> <key> [value...]
    """
    hub = client.area.area_manager
    folder = hub.char_list[_resolve_char_arg(hub, target)]
    data = hub.character_data.setdefault(folder, {})
    if not value.strip():
        if key in data:
            del data[key]
            client.send_ooc(f"Removed '{folder}.{key}'.")
        else:
            client.send_ooc(f"Character '{folder}' has no data key '{key}'.")
    else:
        hub.set_character_data(folder, key, value)
        client.send_ooc(f"Set '{folder}.{key}' = {value}.")
    hub.save_character_data()


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
@command(Arg("arg", rest=True, default="", help="<char> [key(s)]"))
def ooc_cmd_keys_set(client, arg):
    """
    Sets the keys of the target client/character folder/character id to the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_set <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_set <char> [key(s)].")

    mod_keys(client, arg)


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="<char> [key(s)]"))
def ooc_cmd_keys_add(client, arg):
    """
    Adds the keys of the target client/character folder/character id to the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_add <char> [key(s)]
    """
    if not arg:
        raise ArgumentError("Usage: /keys_add <char> [key(s)].")

    mod_keys(client, arg, 1)


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="<char> [key(s)]"))
def ooc_cmd_keys_remove(client, arg):
    """
    Remvove the keys of the target client/character folder/character id from the key(s). Keys must be a number like 5 or a link eg. 1-5.
    Usage: /keys_remove <char> [key(s)]
    """
    if not arg:
        raise ArgumentError(
            "Usage: /keys_remove <char> [area id(s)]. Removes the selected 'keys' from the user."
        )

    mod_keys(client, arg, 2)@command(Arg("target", default="", help="target (blank = your own)"))
def ooc_cmd_keys(client, target):
    """
    Check your own keys, or someone else's (if admin).
    Keys allow you to /lock or /unlock specific areas, OR
    area links if it's formatted like 1-5
    Usage: /keys [target_id]
    """
    if not target:
        client.send_ooc(f"Your current keys are {client.keys}")
        return
    if not client.is_mod and not (client in client.area.area_manager.owners):
        raise ClientError("Only mods and GMs can check other people's keys.")
    try:
        if target.isnumeric():
            t = client.server.client_manager.get_targets(
                client, TargetType.ID, int(target), False
            )
            if t:
                char_id = t[0].char_id
            else:
                if target != "-1" and (int(target) in client.area.area_manager.char_list):
                    char_id = int(target)
                else:
                    raise ArgumentError("Target not found.")
        else:
            try:
                char_id = client.area.area_manager.get_char_id_by_name(target)
            except (ServerError):
                raise
        keys = client.area.area_manager.get_character_data(
            char_id, "keys", [])
        client.send_ooc(
            f"{client.area.area_manager.char_list[char_id]} current keys are {keys}"
        )
    except Exception:
        raise ArgumentError("Target not found.")


@command()
def ooc_cmd_kms(client):
    """
    Stands for Kick MySelf - Kick other instances of the client opened by you.
    Useful if you lose connection and the old client is ghosting.
    Usage: /kms
    """
    for target in client.server.client_manager.get_multiclients(
        client.ipid, client.hdid
    ):
        if target != client:
            target.disconnect()
    client.send_ooc("Kicked other instances of client.")
    database.log_misc("kms", client)


@command(Arg("arg", rest=True, default="", help="description or ID (blank shows yours)"))
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
        arg = arg.strip()
        if arg == "":
            ooc_cmd_chardesc_clear(client)
            return
        client.desc = arg
        if not client.hidden and not client.sneaking:
            desc = arg[:128]
            if len(arg) > len(desc):
                desc += f"... Use /chardesc {client.id} to read the rest."
            client.area.broadcast_ooc(
                f"{client.showname} changed their character description to: {desc}."
            )
            client.area.broadcast_player_list()
        database.log_area("chardesc.change", client, client.area, message=arg)


@command()
def ooc_cmd_chardesc_clear(client):
    """
    Clear your chardesc.
    Usage: /chardesc_clear
    """
    client.area.area_manager.set_character_data(client.char_id, "desc", "")
    if not client.hidden and not client.sneaking:
        client.area.broadcast_ooc(
            f"{client.showname} cleared their character description."
        )
        client.area.broadcast_player_list()
    else:
        client.send_ooc(f"You cleared your character description.")
    database.log_area(
        "chardesc.clear", client, client.area
    )


@mod_only(hub_owners=True)
@command(
    Arg("target", help="client ID, char id or char name"),
    Arg("desc", rest=True, default="", help="new description (blank clears)"),
)
def ooc_cmd_chardesc_set(client, target, desc):
    """
    Set someone else's character description to desc or clear it.
    Usage: /chardesc_set <id> [desc]
    """
    try:
        if target.isnumeric():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(target), False
            )
            if targets:
                target = targets[0].char_id
            else:
                if target != "-1" and (int(target) in client.area.area_manager.char_list):
                    target = int(target)
        else:
            try:
                target = client.area.area_manager.get_char_id_by_name(target)
            except (ServerError):
                raise
        desc = desc.strip()
        client.area.area_manager.set_character_data(target, "desc", desc)
        target = client.area.area_manager.char_list[target]
        client.send_ooc(f"📜{target} Description: {desc}")
        database.log_area(
            "chardesc.set", client, client.area, message=f"{target}: {desc}"
        )
        if not client.hidden and not client.sneaking:
            client.area.broadcast_player_list()
    except Exception:
        raise ArgumentError("Target not found.")


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="client ID, char id or char name"))
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


@command(Arg("tog", bool, default=None, help="on/off"))
def ooc_cmd_narrate(client, tog):
    """
    Speak as a Narrator for your next emote.
    If using 2.9.1, when you speak IC only the chat box will be affected, making you "narrate" over the current visuals.
    tog can be `on`, `off` or empty.
    Usage: /narrate [tog]
    """
    client.narrator = not client.narrator if tog is None else tog
    if client.blankpost is True:
        client.blankpost = False
        client.send_ooc(
            "You cannot be a narrator and blankposting at the same time. Blankposting disabled!"
        )
    stat = "no longer be narrating"
    if client.narrator:
        stat = "be narrating now"
    client.send_ooc(f"You will {stat}.")


@command(Arg("tog", bool, default=None, help="on/off"))
def ooc_cmd_blankpost(client, tog):
    """
    Use a blank image for your next emote (base/misc/blank.png, will be a missingno if you don't have it)
    tog can be `on`, `off` or empty.
    Usage: /blankpost [tog]
    """
    client.blankpost = not client.blankpost if tog is None else tog
    if client.narrator is True:
        client.narrator = False
        client.send_ooc(
            "You cannot be a narrator and blankposting at the same time. Narrating disabled!"
        )
    stat = "no longer be blankposting"
    if client.blankpost:
        stat = "be blankposting now"
    client.send_ooc(f"You will {stat}.")


@command(Arg("tog", bool, default=None, help="on/off"))
def ooc_cmd_firstperson(client, tog):
    """
    Speak as a Narrator for your next emote, but only to yourself. Everyone else will see the emote you used.
    If using 2.9.1, when you speak IC only the chat box will be affected.
    tog can be `on`, `off` or empty.
    Usage: /firstperson [tog]
    """
    client.firstperson = not client.firstperson if tog is None else tog
    if client.narrator is True:
        client.narrator = False
        client.send_ooc(
            "You cannot be a narrator and firstperson at the same time. Narrating disabled!"
        )
    stat = "no longer be firstperson"
    if client.firstperson:
        stat = "be firstperson now"
    client.send_ooc(f"You will {stat}.")


@command(Arg("arg", rest=True, default="", help="showname (blank resets)"))
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
        client.server.player_state_observer.notify_character_name_changed(
            client)
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
    client.server.player_state_observer.notify_character_name_changed(client)
    if not client.hidden and not client.sneaking:
        client.area.broadcast_player_list()


@command()
def ooc_cmd_charlists(client):
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


@command(Arg("arg", rest=True, default="", help="client ID or *"))
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
@command(Arg("arg", rest=True, default="", help="charlist path (blank resets)"))
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


@command(Arg("arg", rest=True, default="", help="client ID or char name (blank checks)"))
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

def get_latest_area(client, char_id: int):
    char_folder = None
    if char_id in range(0, len(client.area.area_manager.char_list)):
        char_folder = client.area.area_manager.char_list[char_id]
    if char_folder == None:
        print(char_folder, ' ', char_id)
        client.send_ooc(f"Can't get latest area when spectating!")
        return None
    latest_area_id = client.area.area_manager.get_character_data(char_id, "latest_area", None)
    if latest_area_id == None:
        client.send_ooc(f"{char_folder} has no latest occupied area defined!")
        return None
    target_area = None
    try:
        target_area = client.area.area_manager.get_area_by_id(latest_area_id)
    except Exception:
        client.send_ooc(f"{char_folder} latest occupied area [{latest_area_id}] is not valid for current hub!")
        return None
    return target_area

@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="client ID or char name (blank = yours)"))
def ooc_cmd_get_latest_area(client, arg):
    """
    Get a character's latest occupied area. Lobby area is always excluded.
    If used by itself, gets your character's latest occupied area instead.
    Usage: /get_latest_area [cid|charname]
    """
    target_charid = -1
    if len(arg) == 0:
        target_charid = client.char_id
    elif arg.isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), True
        )
        if len(targets) > 0:
            target_charid = targets[0].char_id
    else:
        arg = arg.replace("\"", "").lower()
        for i in range(0, len(client.area.area_manager.char_list)):
            if arg == client.area.area_manager.char_list[i].lower():
                target_charid = i
    area = get_latest_area(client, target_charid)
    if area:
        client.send_ooc(f"{client.area.area_manager.char_list[target_charid]} latest occupied area is [{area.id}] {area.name}.")
    else:  
        client.send_ooc(f"Area not found!")

@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="client ID or char name (blank = yours)"))
def ooc_cmd_kick_to_latest_area(client, arg):
    """
    Kick the occupied character in current area to their latest occupied area.
    This command is best used in lobby area. If used by itself, kicks you instead.
    Usage: /kick_to_latest_area [cid|charname]
    """
    target_charid = -1
    if len(arg) == 0:
        target_charid = client.char_id
        targets = [client]
    elif arg.isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), True
        )
        if len(targets) > 0:
            target_charid = targets[0].char_id
    else:
        arg = arg.replace("\"", "").lower()
        for i in range(0, len(client.area.area_manager.char_list)):
            if arg == client.area.area_manager.char_list[i].lower():
                target_charid = i
        targets = client.server.client_manager.get_targets(
            client, TargetType.CHAR_NAME, client.area.area_manager.char_list[target_charid], True
        )
    area = get_latest_area(client, target_charid)
    if area:
        try:
            for target in targets:
                old_area = target.area
                target.set_area(area)
                target.send_ooc(
                    f"You were kicked from [{old_area.id}] {old_area.name} to [{area.id}] {area.name}."
                )
                database.log_area(
                    "kick_to_latest_area", client, client.area, target=target, message=area.id
                )
                client.area.invite_list.discard(target.id)
                client.send_ooc(
                    f"Kicked [{target.id}] {target.showname} from [{old_area.id}] {old_area.name} to [{area.id}] {area.name}."
                )
        except AreaError:
            raise
        except ClientError:
            raise

@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="<cid|charname> [area_id]"))
def ooc_cmd_set_latest_area(client, arg):
    """
    Set a character's latest occupied area. Lobby area is always excluded.
    If used by itself, gets your character's latest occupied area instead.
    Usage: /set_latest_area <cid|charname> [area_id]
    """
    args = shlex.split(arg)
    if len(args) == 0:
        raise ArgumentError(
            "Not enough args. Usage: /set_latest_area <cid|charname> [area_id]"
        )
    target_charid = -1
    if len(args) == 1:
        target_charid = client.char_id
    elif args[0].isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(args[1]), True
        )
        if len(targets) > 0:
            target_charid = targets[0].char_id
    else:
        for i in range(0, len(client.area.area_manager.char_list)):
            if args[0].lower() == client.area.area_manager.char_list[i].lower():
                target_charid = i
    char_folder = None
    if target_charid in range(0, len(client.area.area_manager.char_list)):
        char_folder = client.area.area_manager.char_list[target_charid]
    if not char_folder:
        client.send_ooc(f"Invalid character id!")
        return None
    if len(args) >= 2:
        to_area = int(args[1])
    else:
        to_area = int(args[0])
    client.area.area_manager.set_character_data(target_charid, "latest_area", to_area)
    try:
        target_area = client.area.area_manager.get_area_by_id(to_area)
        client.send_ooc(f"Successfuly set {char_folder} latest occupied area to [{target_area.id}] {target_area.name}.")
    except Exception:
        client.send_ooc(f"Warning: setting {char_folder} latest occupied area to an invalid area for current hub. Area ID: [{to_area}].")