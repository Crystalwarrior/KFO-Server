import json
import shlex
import sqlite3

import arrow
import pytimeparse
from pytimeparse import parse
from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError
import asyncio

from . import mod_only, list_commands, list_submodules, help

from .messaging import lastneed
from .areas import getBGLog

__all__ = [
    "ooc_cmd_motd",
    "ooc_cmd_help",
    "ooc_cmd_kick",
    "ooc_cmd_ban",
    "ooc_cmd_banhdid",
    "ooc_cmd_areacurse",
    "ooc_cmd_unban",
    "ooc_cmd_mute",
    "ooc_cmd_unmute",
    "ooc_cmd_login",
    "ooc_cmd_refresh",
    "ooc_cmd_online",
    "ooc_cmd_mods",
    "ooc_cmd_unmod",
    "ooc_cmd_ooc_mute",
    "ooc_cmd_ooc_unmute",
    "ooc_cmd_bans",
    "ooc_cmd_baninfo",
    "ooc_cmd_time",
    "ooc_cmd_whois",
    "ooc_cmd_restart",
    "ooc_cmd_myid",
    "ooc_cmd_multiclients",
    "ooc_cmd_lastneeds",
    "ooc_cmd_lastevidence",
    "ooc_cmd_bgchanges",
    "ooc_cmd_gethdid",
    "ooc_cmd_gethdids",
    "ooc_cmd_lockdown",
    "ooc_cmd_whitelist",
    "ooc_cmd_unwhitelist",
    "ooc_cmd_togglejoins",
    "ooc_cmd_toggleshownames",
    "ooc_cmd_togglechars",
    "ooc_cmd_playtime",
    "ooc_cmd_raidcon"
]


def ooc_cmd_motd(client, arg):
    """
    Show the message of the day.
    Usage: /motd
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.send_motd()


def ooc_cmd_help(client, arg):
    """
    Show help for a command, or show general help.
    Usage: /help
    """
    import inspect

    if arg == "":
        msg = inspect.cleandoc(
            """
        Welcome to tsuserver3! You can use /help <command> on any known
        command to get up-to-date help on it.
        You may also use /help <category> to see available commands for that category.

        If you don't understand a specific core feature, check the official
        repository for more information:

        https://github.com/Crystalwarrior/KFO-Server/blob/master/README.md 

        Available Categories:
        """
        )
        msg += "\n"
        msg += list_submodules()
        client.send_ooc(msg)
    else:
        arg = arg.lower()
        try:
            if arg in client.server.command_aliases:
                arg = client.server.command_aliases[arg]
            client.send_ooc(help(f"ooc_cmd_{arg}"))
        except AttributeError:
            try:
                msg = f'Submodule "{arg}" commands:\n\n'
                msg += list_commands(arg)
                client.send_ooc(msg)
            except AttributeError:
                client.send_ooc(
                    f"No such command or submodule ({arg}) has been found in the help docs."
                )


@mod_only()
def ooc_cmd_kick(client, arg):
    """
    Kick a player.
    Usage: /kick <ipid|*|**> [reason]
    Special cases:
     - "*" kicks everyone in the current area.
     - "**" kicks everyone in the server.
    """
    if len(arg) == 0:
        raise ArgumentError(
            "You must specify a target. Use /kick <ipid> [reason]")
    elif arg[0] == "*":
        targets = [c for c in client.area.clients if c != client]
    elif arg[0] == "**":
        #targets = [c for c in client.server.client_manager.clients if c != client]
        client.send_ooc("Do not try to kick the whole server/hub please!")
        return
    else:
        targets = None

    args = list(arg.split(" "))
    if targets is None:
        raw_ipid = args[0]
        try:
            ipid = int(raw_ipid)
        except Exception:
            raise ClientError(f"{raw_ipid} does not look like a valid IPID.")
        targets = client.server.client_manager.get_targets(
            client, TargetType.IPID, ipid, False
        )

    if targets:
        reason = " ".join(args[1:])
        for c in targets:
            database.log_misc("kick", client, target=c,
                              data={"reason": reason})
            client.send_ooc(f"{c.showname} was kicked.")
            c.send_command("KK", reason)
            c.disconnect()
        client.server.webhooks.kick(c.ipid, reason, client, c.char_name)
    else:
        client.send_ooc(f"No targets with the IPID {ipid} were found.")

@mod_only()
def ooc_cmd_ban(client, arg):
    """
    Ban a user. If a ban ID is specified instead of a reason,
    then the IPID is added to an existing ban record.
    Ban durations are 6 hours by default.
    Usage: /ban <ipid> "reason" ["<N> <minute|hour|day|week|month>(s)|perma"]
    Usage 2: /ban <ipid> <ban_id>
    """
    kickban(client, arg, False)

@mod_only()
def ooc_cmd_banhdid(client, arg):
    """
    Ban both a user's HDID and IPID.
    Usage: See /ban.
    """
    kickban(client, arg, True)

def _convert_ipid_to_int(value):
    try:
        return int(value)
    except ValueError:
        raise ClientError(f'{value} does not look like a valid IPID.')

def _find_area(client, area_name):
    try:
        return client.server.area_manager.get_area_by_id(int(area_name))
    except:
        try:
            return client.server.area_manager.get_area_by_name(area_name)
        except ValueError:
            raise ArgumentError('Area ID must be a name or a number.')

@mod_only()
def ooc_cmd_areacurse(client, arg):
    """
    Ban a player from all areas except one, such that when they connect, they
    will be placed in a specified area and can't switch areas unless forcefully done
    by a moderator.

    To unban, use the /unban command.
    To add more IPIDs/HDIDs, use the /ban command as usual.

    Usage: /area_curse <ipid> <area_name> "reason" ["<N> <minute|hour|day|week|month>(s)|perma"]
    """
    args = shlex.split(arg)
    default_ban_duration = client.server.config['default_ban_duration']

    if len(args) < 3:
        raise ArgumentError('Not enough arguments.')
    else:
        ipid = _convert_ipid_to_int(args[0])
        target_area = _find_area(client, args[1])
        reason = args[2]

    if len(args) == 3:
        ban_duration = parse(str(default_ban_duration))
        unban_date = arrow.get().shift(seconds=ban_duration).datetime
    elif len(args) == 4:
        duration = args[3]
        ban_duration = parse(str(duration))

        if duration is None:
            raise ArgumentError('Invalid ban duration.')
        elif 'perma' in duration.lower():
            unban_date = None
        else:
            if ban_duration is not None:
                unban_date = arrow.get().shift(seconds=ban_duration).datetime
            else:
                raise ArgumentError(f'{duration} is an invalid ban duration')

    else:
        raise ArgumentError(f'Ambiguous input: {arg}\nPlease wrap your arguments '
                            'in quotes.')

    special_ban_data = json.dumps({
        'ban_type': 'area_curse',
        'target_area': target_area.id
    })

    ban_id = database.ban(ipid, reason, ban_type='ipid', banned_by=client,
                          unban_date=unban_date, special_ban_data=special_ban_data)

    targets = client.server.client_manager.get_targets(
        client, TargetType.IPID, ipid, False)

    for c in targets:
        c.send_ooc('You are now bound to this area.')
        c.area_curse = target_area.id
        c.area_curse_info = database.find_ban(ban_id=ban_id)
        try:
            c.change_area(target_area)
        except ClientError:
            pass
        database.log_misc('area_curse', client, target=c, data={'ban_id': ban_id, 'reason': reason})
    if targets:
        client.send_ooc(f'{len(targets)} clients were area cursed.')
    client.send_ooc(f'{ipid} was area cursed. Ban ID: {ban_id}')

@mod_only()
def kickban(client, arg, ban_hdid):
    args = shlex.split(arg)
    if len(args) < 2:
        raise ArgumentError("Not enough arguments.")
    elif len(args) == 2:
        reason = None
        ban_id = None
        try:
            ban_id = int(args[1])
            unban_date = None
        except ValueError:
            reason = args[1]
            unban_date = arrow.get().shift(hours=6).datetime
    elif len(args) == 3:
        ban_id = None
        reason = args[1]
        if "perma" in args[2]:
            unban_date = None
        else:
            duration = pytimeparse.parse(args[2], granularity="hours")
            if duration is None:
                raise ArgumentError("Invalid ban duration.")
            unban_date = arrow.get().shift(seconds=duration).datetime
    else:
        raise ArgumentError(
            f"Ambiguous input: {arg}\nPlease wrap your arguments " "in quotes."
        )

    try:
        raw_ipid = args[0]
        ipid = int(raw_ipid)
    except ValueError:
        raise ClientError(f"{raw_ipid} does not look like a valid IPID.")

    ban_id = database.ban(
        ipid,
        reason,
        ban_type="ipid",
        banned_by=client,
        ban_id=ban_id,
        unban_date=unban_date,
    )

    char = None
    hdid = None
    if ipid is not None:
        targets = client.server.client_manager.get_targets(
            client, TargetType.IPID, ipid, False
        )
        if targets:
            for c in targets:
                if ban_hdid:
                    database.ban(c.hdid, reason,
                                 ban_type="hdid", ban_id=ban_id)
                    hdid = c.hdid
                c.send_command("KB", reason)
                c.disconnect()
                char = c.char_name
                database.log_misc("ban", client, target=c,
                                  data={"reason": reason})
            client.send_ooc(f"{len(targets)} clients were kicked.")
        client.send_ooc(f"{ipid} was banned. Ban ID: {ban_id}")
    client.server.webhooks.ban(
        ipid, ban_id, reason, client, hdid, char, unban_date)


@mod_only()
def ooc_cmd_unban(client, arg):
    """
    Unban a list of users.
    Usage: /unban <ban_id...>
    """
    if len(arg) == 0:
        raise ArgumentError(
            "You must specify a target. Use /unban <ban_id...>")
    args = list(arg.split(" "))
    client.send_ooc(f"Attempting to lift {len(args)} ban(s)...")
    for ban_id in args:
        if database.unban(ban_id):
            client.send_ooc(f"Removed ban ID {ban_id}.")
            client.server.webhooks.unban(ban_id, client)
        else:
            client.send_ooc(f"{ban_id} is not on the ban list.")
        database.log_misc("unban", client, data={"id": ban_id})


@mod_only()
def ooc_cmd_mute(client, arg):
    """
    Prevent a user from speaking in-character.
    Usage: /mute <ipid>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target. Use /mute <ipid>.")
    args = list(arg.split(" "))
    client.send_ooc(f"Attempting to mute {len(args)} IPIDs.")
    for raw_ipid in args:
        if raw_ipid.isdigit():
            ipid = int(raw_ipid)
            clients = client.server.client_manager.get_targets(
                client, TargetType.IPID, ipid, False
            )
            if clients:
                msg = "Muted the IPID " + str(ipid) + "'s following clients:"
                for c in clients:
                    c.is_muted = True
                    database.log_misc("mute", client, target=c)
                    msg += " " + c.showname + " [" + str(c.id) + "],"
                msg = msg[:-1]
                msg += "."
                client.send_ooc(msg)
            else:
                client.send_ooc(
                    "No targets found. Use /mute <ipid> <ipid> ... for mute."
                )
        else:
            client.send_ooc(f"{raw_ipid} does not look like a valid IPID.")


@mod_only()
def ooc_cmd_unmute(client, arg):
    """
    Unmute a user.
    Usage: /unmute <ipid>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target.")
    args = list(arg.split(" "))
    client.send_ooc(f"Attempting to unmute {len(args)} IPIDs.")
    for raw_ipid in args:
        if raw_ipid.isdigit():
            ipid = int(raw_ipid)
            clients = client.server.client_manager.get_targets(
                client, TargetType.IPID, ipid, False
            )
            if clients:
                msg = f"Unmuted the IPID ${str(ipid)}'s following clients:"
                for c in clients:
                    c.is_muted = False
                    database.log_misc("unmute", client, target=c)
                    msg += " " + c.showname + " [" + str(c.id) + "],"
                msg = msg[:-1]
                msg += "."
                client.send_ooc(msg)
            else:
                client.send_ooc(
                    "No targets found. Use /unmute <ipid> <ipid> ... for unmute."
                )
        else:
            client.send_ooc(f"{raw_ipid} does not look like a valid IPID.")


def ooc_cmd_login(client, arg):
    """
    Login as a moderator.
    Usage: /login <password>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify the password.")
    login_name = None
    try:
        login_name = client.auth_mod(arg)
    except ClientError:
        database.log_misc("login.invalid", client)
        raise

    # Make sure the client's available areas are updated
    client.area.broadcast_area_list(client)

    client.area.broadcast_evidence_list()
    client.send_ooc("Logged in as a moderator.")
    client.server.webhooks.login(client, login_name)
    database.log_misc("login", client, data={"profile": login_name})


@mod_only()
def ooc_cmd_refresh(client, arg):
    """
    Reload all moderator credentials, server options, and commands without
    restarting the server.
    Usage: /refresh
    """
    if len(arg) > 0:
        raise ClientError("This command does not take in any arguments!")
    else:
        try:
            client.server.refresh()
            database.log_misc("refresh", client)
            client.send_ooc("You have reloaded the server.")
        except ServerError:
            raise


def ooc_cmd_online(client, _):
    """
    Show the number of players online.
    Usage: /online
    """
    client.send_player_count()


def ooc_cmd_mods(client, arg):
    """
    Show a list of moderators online.
    Usage: /mods
    """
    client.send_areas_clients(mods=True)


def ooc_cmd_unmod(client, arg):
    """
    Log out as a moderator.
    Usage: /unmod
    """
    client.is_mod = False
    client.mod_profile_name = None

    # Make sure the client's available areas are updated
    client.area.broadcast_area_list(client)

    client.area.broadcast_evidence_list()
    client.send_ooc("You're no longer a mod.")


@mod_only()
def ooc_cmd_ooc_mute(client, arg):
    """
    Prevent a user from talking out-of-character.
    Usage: /ooc_mute <ooc-name>
    """
    if len(arg) == 0:
        raise ArgumentError(
            "You must specify a target. Use /ooc_mute <OOC-name>.")
    targets = client.server.client_manager.get_targets(
        client, TargetType.OOC_NAME, arg, False
    )
    if not targets:
        raise ArgumentError("Targets not found. Use /ooc_mute <OOC-name>.")
    for target in targets:
        target.is_ooc_muted = True
        database.log_area("ooc_mute", client, client.area, target=target)
    client.send_ooc("Muted {} existing client(s).".format(len(targets)))


@mod_only()
def ooc_cmd_ooc_unmute(client, arg):
    """
    Allow an OOC-muted user to talk out-of-character.
    Usage: /ooc_unmute <ooc-name>
    """
    if len(arg) == 0:
        raise ArgumentError(
            "You must specify a target. Use /ooc_unmute <OOC-name>.")
    targets = client.server.client_manager.get_ooc_muted_clients()
    if not targets:
        raise ArgumentError("Targets not found. Use /ooc_unmute <OOC-name>.")
    for target in targets:
        target.is_ooc_muted = False
        database.log_area("ooc_unmute", client, client.area, target=target)
    client.send_ooc("Unmuted {} existing client(s).".format(len(targets)))


@mod_only()
def ooc_cmd_bans(client, _arg):
    """
    Get the 5 most recent bans.
    Usage: /bans
    """
    msg = "Last 5 bans:\n"
    for ban in database.recent_bans():
        time = arrow.get(ban.ban_date).humanize()
        msg += (
            f"{time}: {ban.banned_by_name} ({ban.banned_by}) issued ban "
            f"{ban.ban_id} ('{ban.reason}')\n"
        )
    client.send_ooc(msg)


@mod_only()
def ooc_cmd_baninfo(client, arg):
    """
    Get information about a ban.
    Usage: /baninfo <id> ['ban_id'|'ipid'|'hdid']
    By default, id identifies a ban_id.
    """
    args = arg.split(" ")
    if len(arg) == 0:
        raise ArgumentError("You must specify an ID.")
    elif len(args) == 1:
        lookup_type = "ban_id"
    else:
        lookup_type = args[1]

    if lookup_type not in ("ban_id", "ipid", "hdid"):
        raise ArgumentError("Incorrect lookup type.")

    ban = database.find_ban(**{lookup_type: args[0]})
    if ban is None:
        client.send_ooc("No ban found for this ID.")
    else:
        msg = f"Ban ID: {ban.ban_id}\n"
        msg += "Affected IPIDs: " + \
            ", ".join([str(ipid) for ipid in ban.ipids]) + "\n"
        msg += "Affected HDIDs: " + ", ".join(ban.hdids) + "\n"
        msg += f'Reason: "{ban.reason}"\n'
        msg += f"Banned by: {ban.banned_by_name} ({ban.banned_by})\n"

        ban_date = arrow.get(ban.ban_date)
        msg += f"Banned on: {ban_date.format()} ({ban_date.humanize()})\n"
        if ban.unban_date is not None:
            unban_date = arrow.get(ban.unban_date)
            msg += f"Unban date: {unban_date.format()} ({unban_date.humanize()})"
        else:
            msg += "Unban date: N/A"
        client.send_ooc(msg)


def ooc_cmd_time(client, arg):
    """
    Returns the current server time.
    Usage:  /time
    """
    if len(arg) > 0:
        raise ArgumentError("This command takes no arguments")
    from time import asctime, gmtime, time

    msg = "The current time in UTC (aka GMT) is:\n["
    msg += asctime(gmtime(time()))
    msg += "]"
    client.send_ooc(msg)


@mod_only()
def ooc_cmd_whois(client, arg):
    """
    Get information about an online user.
    Usage: /whois <name|id|ipid|showname|character>
    """
    found_clients = set()
    for c in client.server.client_manager.clients:
        if (
            arg.lower() in c.name.lower()
            or arg in c.showname.lower()
            or arg.lower() in c.char_name.lower()
            or arg in str(c.id)
            or arg in str(c.ipid)
        ):
            found_clients.add(c)

    info = f"WHOIS lookup for {arg}:"
    for c in found_clients:
        info += f"\n[{c.id}] "
        if c.showname != c.char_name:
            info += f'"{c.showname}" ({c.char_name})'
        else:
            info += f"{c.showname}"
        info += f" ({c.ipid})"
        if c.name != "":
            info += f": {c.name}"
    info += f"\nMatched {len(found_clients)} online clients."
    client.send_ooc(info)


@mod_only()
def ooc_cmd_restart(client, arg):
    """
    Restart the server (WARNING: The server will be *stopped* unless you set up a restart batch/bash file!)
    Usage: /restart
    """
    if arg != client.server.config["restartpass"]:
        raise ArgumentError("no")
    print(f"!!!{client.name} called /restart!!!")
    client.server.send_all_cmd_pred(
        "CT", "WARNING", "Restarting the server...")
    asyncio.get_running_loop().stop()


def ooc_cmd_myid(client, arg):
    """
    Get information for your current client, such as client ID.
    Usage: /myid
    """
    if len(arg) > 0:
        raise ArgumentError("This command takes no arguments")
    info = f"You are: [{client.id}] "
    if client.showname != client.char_name:
        info += f'"{client.showname}" ({client.char_name})'
    else:
        info += f"{client.showname}"
    if client.is_mod:
        info += f" ({client.ipid})"
    if client.name != "":
        info += f": {client.name}"
    client.send_ooc(info)


@mod_only()
def ooc_cmd_multiclients(client, arg):
    """
    Get all the multi-clients of the IPID provided, detects multiclients on the same hardware even if the IPIDs are different.
    Usage: /multiclients <ipid>
    """
    found_clients = set()
    for c in client.server.client_manager.clients:
        if arg == str(c.ipid):
            found_clients.add(c)
            found_clients |= set(client.server.client_manager.get_multiclients(c.ipid, c.hdid))

    info = f"Clients belonging to {arg}:"
    for c in found_clients:
        info += f"\n[{c.id}] "
        if c.showname != c.char_name:
            info += f'"{c.showname}" ({c.char_name})'
        else:
            info += f"{c.showname}"
        info += f" ({c.ipid})"
        if c.name != "":
            info += f": {c.name}"
    info += f"\nMatched {len(found_clients)} online clients."
    client.send_ooc(info)

@mod_only()
def ooc_cmd_lastneeds(client, _):
    """
    Get information about the last 3 calls of /need.
    Usage: /lastneeds
    No /need user will be able to troll now.
    Mess with the best, die like the rest
    """
    lastneeds = lastneed()
    msg = []
    if all(v is None for v in lastneeds):
        client.send_ooc("There is no /need logged at the moment.")
        return None
    #Don't ask me why, it looks horrible, but .reverse() does not work on that
    for i in [lastneeds[len(lastneeds)-1-i] for i in range(len(lastneeds))]:
        if i:
            msg.append(f"\nIPID: {i[0]}\nMessage: '{i[1]}'")

    client.send_ooc("\n".join(msg))


@mod_only()
def ooc_cmd_lastevidence(client, arg):
    """
    Get information about the last additions to evidence
    of the current area you are in.
    Usage: /lastevidence
    'Extraordinary claims require extraordinary evidence.'
    ― Carl Sagan
    """
    evidence = client.area.getEvidenceLogs()

    msg = []
    if all(v is None for v in evidence):
        client.send_ooc("There is no evidence logged at the moment.")
        return None
    # Don't ask me why, it looks horrible, but .reverse() does not work on that
    for i in [evidence[len(evidence) - 1 - i] for i in range(len(evidence))]:
        if i:
            msg.append(f"\nIPID: {i[0]}\nName: '{i[1]}'\nDescription: '{i[2]}'")

    client.send_ooc(f"\nArea: {client.area.name}" + "\n".join(msg))


@mod_only()
def ooc_cmd_bgchanges(client, _):
    """
    Get information about the last background-changes.
    Usage: /bgchanges
    'You never realize how much of your background is sewn into the lining of your clothes.'
    - Tom Wolfe
    """
    bg_logs = getBGLog()
    msg = []
    if all(v is None for v in bg_logs):
        client.send_ooc("There is no bg change logged at the moment.")
        return None
    #Don't ask me why, it looks horrible, but .reverse() does not work on that
    for i in [bg_logs[len(bg_logs)-1-i] for i in range(len(bg_logs))]:
        if i:
            msg.append(f"\nIPID: {i[0]}\nChanged the background to: '{i[1]}'")

    client.send_ooc("\n".join(msg))
    
@mod_only()
def ooc_cmd_gethdid(client, arg):
    """
    Show HDIDs of all users in the current area.
    Usage: /gethdid
    """
    if not client.is_mod:
        raise ClientError("You must be a moderator to use this command.")
    client.send_area_info(client.area.id, show_hdid=True)

@mod_only()
def ooc_cmd_gethdids(client, arg):
    """
    Show HDIDs of all users in all areas of the current hub.
    Usage: /gethdids
    """
    if not client.is_mod:
        raise ClientError("You must be a moderator to use this command.")
    client.send_areas_clients(show_hdid=True)

@mod_only()
def ooc_cmd_lockdown(client, arg):
    """
    Toggle lockdown mode. In lockdown mode, only whitelisted HDIDs can join.
    Usage: /lockdown [on/off/update]
    """
        
    if len(arg) == 0:
        client.send_ooc("Current lockdown status: " + 
                       ("on" if client.server.lockdown else "off") +
                       f"\nWhitelist entries: {len(client.server.whitelist)}")
        return
        
    cmd = arg.lower()
    
    if cmd == 'on':
        client.server.lockdown = True
        min_time = client.server.config['lockdown']['min_playtime']
        trusted_hdids = client.server.database.get_trusted_hdids(min_time)
        client.server.whitelist.update(trusted_hdids)
        
        kicked = 0
        for c in client.server.client_manager.clients:
            if c.hdid not in client.server.whitelist:
                c.send_ooc('You have been kicked: Server entering lockdown mode.')
                c.disconnect()
                kicked += 1

        client.send_ooc(f'Lockdown mode enabled. {len(trusted_hdids)} HDIDs whitelisted. {kicked} players kicked.')
    elif cmd == 'off':
        client.server.lockdown = False
        client.send_ooc("Lockdown mode disabled.")
    elif cmd == 'update':
        try:
            existing_hdids = set()
            try:
                with open('storage/whitelist.txt', 'r') as f:
                    existing_hdids = {line.strip() for line in f if line.strip()}
            except FileNotFoundError:
                pass
                
            with sqlite3.connect('storage/db.sqlite3') as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT DISTINCT hdid FROM hdids')
                db_hdids = {row['hdid'] for row in cursor.fetchall()}
                
            new_hdids = db_hdids - existing_hdids
            
            if not new_hdids:
                client.send_ooc("No new HDIDs found to add to whitelist.")
                return
                
            with open('storage/whitelist.txt', 'a') as f:
                for hdid in new_hdids:
                    f.write(f"{hdid}\n")

            client.server.whitelist = existing_hdids | new_hdids
            
            client.send_ooc(f"Added {len(new_hdids)} new HDIDs to whitelist. Total whitelist entries: {len(client.server.whitelist)}")
            
        except sqlite3.Error as e:
            raise ClientError(f"Database error: {e}")
        except IOError as e:
            raise ClientError(f"Failed to write to whitelist.txt: {e}")
    else:
        raise ArgumentError("Invalid argument. Usage: /lockdown [on/off/update]")
        
@mod_only()
def ooc_cmd_whitelist(client, arg):
    """
    Add a HDID to the whitelist.
    Usage: /whitelist <hdid>
    """
        
    if not arg:
        raise ArgumentError("You must specify a HDID.")
        
    hdid = arg.strip()
    client.server.whitelist.add(hdid)
    client.server.save_whitelist()
    client.send_ooc(f"HDID {hdid} has been added to the whitelist.")
  
@mod_only()
def ooc_cmd_unwhitelist(client, arg):
    """
    Remove a HDID from the whitelist.
    Usage: /unwhitelist <hdid>
    """
        
    if not arg:
        raise ArgumentError("You must specify a HDID.")
        
    hdid = arg.strip()
    if hdid in client.server.whitelist:
        client.server.whitelist.remove(hdid)
        client.server.save_whitelist()

        if client.server.lockdown:
            kicked_clients = []
            for c in client.server.client_manager.clients:
                if c.hdid == hdid:
                    kicked_clients.append(c)
                    c.send_ooc("You have been kicked: Unwhitelisted during lockdown.")
                    c.disconnect()
                    
            if kicked_clients:
                client.send_ooc(f"HDID {hdid} has been removed from the whitelist and {len(kicked_clients)} client(s) were kicked.")
            else:
                client.send_ooc(f"HDID {hdid} has been removed from the whitelist. No clients were connected with this HDID.")
        else:
            client.send_ooc(f"HDID {hdid} has been removed from the whitelist.")
    else:
        client.send_ooc(f"HDID {hdid} is not in the whitelist.")
        
@mod_only()
def ooc_cmd_togglejoins(client, arg):
    """
    Toggle the display of joining players' information (HDID, IPID) and track their name changes.
    Usage: /togglejoins
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    
    if not hasattr(client.server, 'join_trackers'):
        client.server.join_trackers = set()
    
    if client.id in client.server.join_trackers:
        client.server.join_trackers.remove(client.id)
        client.send_ooc('Join tracking turned OFF.')
    else:
        client.server.join_trackers.add(client.id)
        client.send_ooc('Join tracking turned ON.')
        
@mod_only()
def ooc_cmd_togglechars(client, arg):
    """
    Toggle tracking of character selections.
    Usage: /togglechars
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    
    if not hasattr(client.server, 'char_trackers'):
        client.server.char_trackers = set()
    
    if client.id in client.server.char_trackers:
        client.server.char_trackers.remove(client.id)
        client.send_ooc('Character tracking turned OFF.')
    else:
        client.server.char_trackers.add(client.id)
        client.send_ooc('Character tracking turned ON.')
        
@mod_only()
def ooc_cmd_toggleshownames(client, arg):
    """
    Toggle tracking of showname changes.
    Usage: /toggleshownames
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    
    if not hasattr(client.server, 'showname_trackers'):
        client.server.showname_trackers = set()
    
    if client.id in client.server.showname_trackers:
        client.server.showname_trackers.remove(client.id)
        client.send_ooc('Showname tracking turned OFF.')
    else:
        client.server.showname_trackers.add(client.id)
        client.send_ooc('Showname tracking turned ON.')
        
@mod_only()
def ooc_cmd_playtime(client, arg):
    """
    Check total playtime for an HDID.
    Usage: /playtime <hdid>
    """
    if not arg:
        raise ArgumentError("You must specify an HDID.")
        
    hdid = arg.strip()
    total_time = client.server.database.get_hdid_time(hdid)
    
    if total_time is None:
        client.send_ooc(f"No playtime recorded for HDID {hdid}")
    else:
        formatted_time = client.format_time_interval(total_time)
        client.send_ooc(f"Total playtime for HDID {hdid}: {formatted_time}")
    
@mod_only()    
def ooc_cmd_raidcon(client, arg):
    """
    Change or view raid control level.
    Usage: /raidcon [0-3]
           /raidcon whitelist [on/off]
    """
    if not client.is_mod:
        raise ClientError("You must be a moderator to use this command.")
        
    if not arg:
        client.send_ooc(client.server.raidmode.get_status_message())
        return

    args = arg.split()
    
    # Check for whitelist command first
    if args[0].lower() == "whitelist":
        if len(args) != 2:
            raise ArgumentError("Usage: /raidcon whitelist [on/off]")
            
        if args[1].lower() == "on":
            client.server.raidmode.whitelist_enabled = True
            client.send_ooc("Raidmode whitelist exemptions enabled.")
        elif args[1].lower() == "off":
            client.server.raidmode.whitelist_enabled = False
            client.send_ooc("Raidmode whitelist exemptions disabled.")
        else:
            raise ArgumentError("Options are 'on' or 'off'")
            
        client.send_ooc(client.server.raidmode.get_status_message())
        return
        
    # If not whitelist command, try to parse level
    try:
        level = int(args[0])
    except ValueError:
        raise ArgumentError("Level must be a number. For whitelist, use '/raidcon whitelist [on/off]'")
        
    if client.server.raidmode.set_level(level):
        client.send_ooc(f"Raid control level set to {level}")
        client.send_ooc(client.server.raidmode.get_status_message())
    else:
        raise ArgumentError("Invalid raid control level.")