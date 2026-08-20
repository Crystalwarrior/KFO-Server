import shlex

import arrow
import pytimeparse

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError
import asyncio

from . import mod_only, list_commands, list_submodules, help, Arg, command

__all__ = [
    "ooc_cmd_motd",
    "ooc_cmd_help",
    "ooc_cmd_kick",
    "ooc_cmd_ban",
    "ooc_cmd_banhdid",
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
]


@command()
def ooc_cmd_motd(client):
    """
    Show the message of the day.
    Usage: /motd
    """
    client.send_motd()


@command(Arg("topic", rest=True, default="", help="command or category"))
def ooc_cmd_help(client, topic):
    """
    Show help for a command, or show general help.
    Usage: /help
    """
    import inspect

    if topic == "":
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
        arg = topic.lower()
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
@command(
    Arg("target", help="ipid, *, or **"),
    Arg("reason", rest=True, default="", help="kick reason"),
)
def ooc_cmd_kick(client, target, reason):
    """
    Kick a player.
    Usage: /kick <ipid|*|**> [reason]
    Special cases:
     - "*" kicks everyone in the current area.
     - "**" kicks everyone in the server.
    """
    ipid = None
    if target == "*":
        targets = [c for c in client.area.clients if c != client]
    elif target == "**":
        targets = [c for c in client.server.client_manager.clients if c != client]
    else:
        try:
            ipid = int(target)
        except ValueError:
            raise ClientError(f"{target} does not look like a valid IPID.")
        targets = client.server.client_manager.get_targets(
            client, TargetType.IPID, ipid, False
        )

    if targets:
        for c in targets:
            database.log_misc("kick", client, target=c,
                              data={"reason": reason})
            client.send_ooc(f"{c.showname} was kicked.")
            c.send_command("KK", reason)
            c.disconnect()
        client.server.webhooks.kick(c.ipid, reason, client, c.char_name)
    else:
        client.send_ooc(f"No targets with the IPID {ipid} were found.")


def _parse_ban_rest(rest_str):
    """Parse the <reason|ban_id> [duration] portion of a ban command.

    Returns ``(reason_text, ban_id, unban_date)`` where exactly one of
    *reason_text* / *ban_id* is set.
    """
    args = shlex.split(rest_str) if rest_str.strip() else []
    if len(args) == 0:
        raise ArgumentError("Not enough arguments.")
    elif len(args) == 1:
        try:
            return None, int(args[0]), None
        except ValueError:
            return args[0], None, arrow.get().shift(hours=6).datetime
    elif len(args) == 2:
        if "perma" in args[1]:
            return args[0], None, None
        duration = pytimeparse.parse(args[1], granularity="hours")
        if duration is None:
            raise ArgumentError("Invalid ban duration.")
        return args[0], None, arrow.get().shift(seconds=duration).datetime
    else:
        raise ArgumentError(
            f"Ambiguous input: {rest_str}\nPlease wrap your arguments in quotes."
        )


def _do_ban(client, ipid, reason, ban_id, unban_date, ban_hdid=False):
    """Execute the ban after arguments have been parsed."""
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
@command(
    Arg("ipid", type=int, help="IPID to ban"),
    Arg("reason", rest=True, default="", help="<reason> [<duration>] or <ban_id>"),
)
def ooc_cmd_ban(client, ipid, reason):
    """
    Ban a user. If a ban ID is specified instead of a reason,
    then the IPID is added to an existing ban record.
    Ban durations are 6 hours by default.
    Usage: /ban <ipid> "reason" ["<N> <minute|hour|day|week|month>(s)|perma"]
    Usage 2: /ban <ipid> <ban_id>
    """
    reason_text, ban_id, unban_date = _parse_ban_rest(reason)
    _do_ban(client, ipid, reason_text, ban_id, unban_date)


@mod_only()
@command(
    Arg("ipid", type=int, help="IPID to ban"),
    Arg("reason", rest=True, default="", help="<reason> [<duration>] or <ban_id>"),
)
def ooc_cmd_banhdid(client, ipid, reason):
    """
    Ban both a user's HDID and IPID.
    Usage: See /ban.
    """
    reason_text, ban_id, unban_date = _parse_ban_rest(reason)
    _do_ban(client, ipid, reason_text, ban_id, unban_date, ban_hdid=True)


@mod_only()
@command(Arg("ban_ids", variadic=True, type=int, help="one or more ban IDs"))
def ooc_cmd_unban(client, ban_ids):
    """
    Unban a list of users.
    Usage: /unban <ban_id...>
    """
    client.send_ooc(f"Attempting to lift {len(ban_ids)} ban(s)...")
    for ban_id in ban_ids:
        if database.unban(ban_id):
            client.send_ooc(f"Removed ban ID {ban_id}.")
            client.server.webhooks.unban(ban_id, client)
        else:
            client.send_ooc(f"{ban_id} is not on the ban list.")
        database.log_misc("unban", client, data={"id": ban_id})


@mod_only()
@command(Arg("ipids", variadic=True, type=int, help="one or more IPIDs"))
def ooc_cmd_mute(client, ipids):
    """
    Prevent a user from speaking in-character.
    Usage: /mute <ipid>
    """
    client.send_ooc(f"Attempting to mute {len(ipids)} IPIDs.")
    for ipid in ipids:
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


@mod_only()
@command(Arg("ipids", variadic=True, type=int, help="one or more IPIDs"))
def ooc_cmd_unmute(client, ipids):
    """
    Unmute a user.
    Usage: /unmute <ipid>
    """
    client.send_ooc(f"Attempting to unmute {len(ipids)} IPIDs.")
    for ipid in ipids:
        clients = client.server.client_manager.get_targets(
            client, TargetType.IPID, ipid, False
        )
        if clients:
            msg = f"Unmuted the IPID {ipid}'s following clients:"
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


@command(Arg("password", rest=True, default="", help="moderator password"))
def ooc_cmd_login(client, password):
    """
    Login as a moderator.
    Usage: /login <password>
    """
    if not password:
        raise ArgumentError("You must specify the password.")
    login_name = None
    try:
        login_name = client.auth_mod(password)
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
@command()
def ooc_cmd_refresh(client):
    """
    Reload all moderator credentials, server options, and commands without
    restarting the server.
    Usage: /refresh
    """
    try:
        client.server.refresh()
        database.log_misc("refresh", client)
        client.send_ooc("You have reloaded the server.")
    except ServerError:
        raise


@command()
def ooc_cmd_online(client):
    """
    Show the number of players online.
    Usage: /online
    """
    client.send_player_count()


@command()
def ooc_cmd_mods(client):
    """
    Show a list of moderators online.
    Usage: /mods
    """
    client.send_areas_clients(mods=True)


@command()
def ooc_cmd_unmod(client):
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


def _get_ooc_mute_targets(client, arg):
    """
    Resolve `/ooc_mute`/`/ooc_unmute` targets across the caller's hub.

    Prefer a forward partial-name match (``/ooc_mute Jo`` -> any ``Jo*``), then
    a numeric client id, then `get_targets`'s OOC_NAME branch. That last branch
    is written for `/pm <name> <msg>` layouts (it requires the query to start
    with the client's *full* name), which makes it unreliable as a standalone
    name lookup -- e.g. the query ``john`` can match a client named ``Jo`` while
    missing ``John Doe`` -- so it is only a last resort here.
    """
    term = arg.strip().lower()
    hub = client.area.area_manager
    targets = []
    if term:
        targets = [
            c for c in client.server.client_manager.clients
            if c.name and c.name.lower().startswith(term)
            and c.area is not None and c.area.area_manager is hub
        ]
    if not targets and term.isdigit():
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(term), False
        )
    if not targets:
        targets = client.server.client_manager.get_targets(
            client, TargetType.OOC_NAME, arg, False
        )
    return targets


@mod_only()
@command(Arg("target", rest=True, default="", help="ooc-name or client-id"))
def ooc_cmd_ooc_mute(client, target):
    """
    Prevent a user from talking out-of-character.
    Usage: /ooc_mute <ooc-name|client-id>
    """
    if not target:
        raise ArgumentError(
            "You must specify a target. Use /ooc_mute <OOC-name>.")
    targets = _get_ooc_mute_targets(client, target)
    if not targets:
        raise ArgumentError("Targets not found. Use /ooc_mute <OOC-name>.")
    for t in targets:
        t.is_ooc_muted = True
        database.log_area("ooc_mute", client, client.area, target=t)
    client.send_ooc("Muted {} existing client(s).".format(len(targets)))


@mod_only()
@command(Arg("target", rest=True, default="", help="ooc-name or client-id"))
def ooc_cmd_ooc_unmute(client, target):
    """
    Allow an OOC-muted user to talk out-of-character.
    Usage: /ooc_unmute <ooc-name|client-id>
    """
    if not target:
        raise ArgumentError(
            "You must specify a target. Use /ooc_unmute <OOC-name>.")
    targets = [
        c for c in _get_ooc_mute_targets(client, target) if c.is_ooc_muted
    ]
    if not targets:
        raise ArgumentError("Targets not found. Use /ooc_unmute <OOC-name>.")
    for t in targets:
        t.is_ooc_muted = False
        database.log_area("ooc_unmute", client, client.area, target=t)
    client.send_ooc("Unmuted {} existing client(s).".format(len(targets)))


@mod_only()
@command()
def ooc_cmd_bans(client):
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
@command(
    Arg("identifier", help="ban id, ipid, or hdid"),
    Arg(
        "lookup_type",
        default="ban_id",
        choices=("ban_id", "ipid", "hdid"),
        help="what the id identifies",
    ),
)
def ooc_cmd_baninfo(client, identifier, lookup_type):
    """
    Get information about a ban.
    Usage: /baninfo <id> ['ban_id'|'ipid'|'hdid']
    By default, id identifies a ban_id.
    """
    ban = database.find_ban(**{lookup_type: identifier})
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


@command()
def ooc_cmd_time(client):
    """
    Returns the current server time.
    Usage:  /time
    """
    from time import asctime, gmtime, time

    msg = "The current time in UTC (aka GMT) is:\n["
    msg += asctime(gmtime(time()))
    msg += "]"
    client.send_ooc(msg)


@mod_only()
@command(
    Arg("query", rest=True, default="", help="name, id, ipid, showname, or character")
)
def ooc_cmd_whois(client, query):
    """
    Get information about an online user.
    Usage: /whois <name|id|ipid|showname|character>
    """
    found_clients = set()
    for c in client.server.client_manager.clients:
        if (
            query.lower() in c.name.lower()
            or query in c.showname.lower()
            or query.lower() in c.char_name.lower()
            or query in str(c.id)
            or query in str(c.ipid)
        ):
            found_clients.add(c)

    info = f"WHOIS lookup for {query}:"
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
@command(Arg("password", rest=True, default="", help="restart password"))
def ooc_cmd_restart(client, password):
    """
    Restart the server (WARNING: The server will be *stopped* unless you set up a restart batch/bash file!)
    Usage: /restart
    """
    if password != client.server.config["restartpass"]:
        raise ArgumentError("no")
    print(f"!!!{client.name} called /restart!!!")
    client.server.send_all_cmd_pred(
        "CT", "WARNING", "Restarting the server...")
    asyncio.get_running_loop().stop()


@command()
def ooc_cmd_myid(client):
    """
    Get information for your current client, such as client ID.
    Usage: /myid
    """
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
@command(Arg("ipid", type=int, help="IPID to look up"))
def ooc_cmd_multiclients(client, ipid):
    """
    Get all the multi-clients of the IPID provided, detects multiclients on the same hardware even if the IPIDs are different.
    Usage: /multiclients <ipid>
    """
    found_clients = set()
    for c in client.server.client_manager.clients:
        if ipid == c.ipid:
            found_clients.add(c)
            found_clients |= set(
                client.server.client_manager.get_multiclients(c.ipid, c.hdid)
            )

    info = f"Clients belonging to {ipid}:"
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
