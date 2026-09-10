from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only, command, Arg, tokens_str

__all__ = [
    "ooc_cmd_doc",
    "ooc_cmd_cleardoc",
    "ooc_cmd_cm",
    "ooc_cmd_uncm",
    "ooc_cmd_blockwtce",
    "ooc_cmd_unblockwtce",
    "ooc_cmd_judgelog",
    "ooc_cmd_afk",  # Not strictly casing - to be reorganized
    "ooc_cmd_remote_listen",  # Not strictly casing - to be reorganized
    "ooc_cmd_testimony",
    "ooc_cmd_testimony_start",
    "ooc_cmd_testimony_continue",
    "ooc_cmd_testimony_clear",
    "ooc_cmd_testimony_remove",
    "ooc_cmd_testimony_amend",
    "ooc_cmd_testimony_swap",
    "ooc_cmd_testimony_insert",
    "ooc_cmd_cs",
    "ooc_cmd_pta",
    "ooc_cmd_concede",
    "ooc_cmd_minigame_start_song",
    "ooc_cmd_minigame_end_song",
    "ooc_cmd_minigame_concede_song",
    "ooc_cmd_subtheme",
    "ooc_cmd_time_of_day",
]

@command(Arg("arg", rest=True, default="", help="url (blank shows current)"))
def ooc_cmd_doc(client, arg):
    """
    Show or change the link for the current case document.
    Usage: /doc [url]
    """
    if len(arg) == 0:
        client.send_ooc(f"Document: {client.area.doc}")
        database.log_area("doc.request", client, client.area)
    else:
        if client.area.cannot_ic_interact(client):
            raise ClientError("You are not on the area's invite list!")
        if (
            not client.is_mod
            and not (client in client.area.owners)
            and client.char_id == -1
        ):
            raise ClientError("You may not do that while spectating!")
        client.area.change_doc(arg)
        client.area.broadcast_ooc(
            f"{client.showname} changed the doc link to: {client.area.doc}"
        )
        database.log_area("doc.change", client, client.area, message=arg)


@command()
def ooc_cmd_cleardoc(client):
    """
    Clear the link for the current case document.
    Usage: /cleardoc
    """
    if client.area.cannot_ic_interact(client):
        raise ClientError("You are not on the area's invite list!")
    if (
        not client.is_mod
        and not (client in client.area.owners)
        and client.char_id == -1
    ):
        raise ClientError("You may not do that while spectating!")
    client.area.change_doc()
    client.area.broadcast_ooc(
        "{} cleared the doc link.".format(client.showname))
    database.log_area("doc.clear", client, client.area)


@command(Arg("arg", rest=True, default="", help="client ID(s) or * (blank = self)"))
def ooc_cmd_cm(client, arg):
    """
    Add a case manager for the current area.
    Leave id blank to promote yourself if there are no CMs.
    Usage: /cm <id>
    """
    if not client.is_mod and client not in client.area.area_manager.owners and not client.area.can_cm:
        raise ClientError("You can't become a CM in this Area!")
    if len(client.area._owners) == 0 or client.is_mod or client in client.area.owners:
        # Client is trying to make someone else a CM
        if arg != "":
            # Nominate all self clients (Those not present in area will not be counted later)
            if arg == "*":
                arg = [c.id for c in client.server.client_manager.get_multiclients(
                    client.ipid, client.hdid)]
            # CM the provided targets
            else:
                arg = arg.split(" ")
                # Client is not a mod, not a CM and not a GM, meaning they're trying to nominate someone without being /cm first
                if not client.is_mod and client not in client.area.owners:
                    raise ArgumentError(
                        "You cannot 'nominate' people to be CMs when you are not one."
                    )
        else:
            # Self CM
            arg = [client.id]
        # Loop through the ID's provided
        for id in arg:
            try:
                id = int(id)
                c = client.server.client_manager.get_targets(
                    client, TargetType.ID, id, False
                )[0]
                if c not in client.area.clients:
                    raise ArgumentError(
                        "You can only 'nominate' people to be CMs when they are in the area."
                    )
                elif c in client.area._owners:
                    client.send_ooc(
                        f"{c.showname} [{c.id}] is already a CM here.")
                else:
                    client.area.add_owner(c)
                    database.log_area("cm.add", client, client.area, target=c)
            except (ValueError, IndexError):
                client.send_ooc(f"{id} does not look like a valid ID.")
            except (ClientError, ArgumentError):
                raise
    else:
        raise ClientError("You must be authorized to do that.")


# TODO: allow running this command from outside the area you're a CM of in hubs that allow multiple CMed areas
@mod_only(area_owners=True)
@command(Arg("ids", variadic=True, type=int, default=[], help="client ID(s) (blank = self)"))
def ooc_cmd_uncm(client, ids):
    """
    Remove a case manager from the current area.
    Usage: /uncm <id>
    """
    if not ids:
        ids = [client.id]
    for _id in ids:
        try:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, _id, False
            )[0]
            if c in client.area._owners:
                client.area.remove_owner(c)
                database.log_area("cm.remove", client, client.area, target=c)
            else:
                client.send_ooc(
                    "You cannot remove someone from CMing when they aren't a CM."
                )
        except IndexError:
            client.send_ooc(f"{_id} does not look like a valid ID.")
        except (ClientError, ArgumentError):
            raise


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_blockwtce(client, id):
    """
    Prevent a user from using Witness Testimony/Cross Examination buttons
    as a judge.
    Usage: /blockwtce <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if not targets:
        raise ArgumentError("Target not found. Use /blockwtce <id>.")
    for target in targets:
        target.can_wtce = False
        target.send_ooc("A moderator blocked you from using judge signs.")
        database.log_area("blockwtce", client, client.area, target=target)
    client.send_ooc("blockwtce'd {}.".format(targets[0].char_name))


@mod_only()
@command(Arg("id", int, help="client ID"))
def ooc_cmd_unblockwtce(client, id):
    """
    Allow a user to use WT/CE again.
    Usage: /unblockwtce <id>
    """
    targets = client.server.client_manager.get_targets(
        client, TargetType.ID, id, False
    )
    if not targets:
        raise ArgumentError("Target not found. Use /unblockwtce <id>.")
    for target in targets:
        target.can_wtce = True
        target.send_ooc("A moderator unblocked you from using judge signs.")
        database.log_area("unblockwtce", client, client.area, target=target)
    client.send_ooc("unblockwtce'd {}.".format(targets[0].char_name))


@mod_only()
@command()
def ooc_cmd_judgelog(client):
    """
    List the last 10 uses of judge controls in the current area.
    Usage: /judgelog
    """
    jlog = client.area.judgelog
    if len(jlog) > 0:
        jlog_msg = "== Judge Log =="
        for x in jlog:
            jlog_msg += f"\r\n{x}"
        client.send_ooc(jlog_msg)
    else:
        raise ServerError(
            "There have been no judge actions in this area since start of session."
        )


@command()
def ooc_cmd_afk(client):
    client.server.client_manager.toggle_afk(client)


@mod_only(area_owners=True)
@command(
    Arg("option", choices=["NONE", "IC", "OOC", "ALL"], default=None, help="option (blank shows current)"),
)
def ooc_cmd_remote_listen(client, option):
    """
    Change the remote listen logs to either NONE, IC, OOC or ALL.
    It will send you those messages from the areas you are an owner of.
    Leave blank to see your current option.
    Usage: /remote_listen [option]
    """
    options = {
        "NONE": 0,
        "IC": 1,
        "OOC": 2,
        "ALL": 3,
    }
    if option is not None:
        client.remote_listen = options[option]
    reversed_options = dict(map(reversed, options.items()))
    opt = reversed_options[client.remote_listen]
    client.send_ooc(f"Your current remote listen option is: {opt}")


@command(Arg("id", int, default=None, help="statement id to move to"))
def ooc_cmd_testimony(client, id):
    """
    Display the currently recorded testimony.
    Optionally, id can be passed to move to that statement.
    Usage: /testimony [id]
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    if id is not None:
        try:
            if client.area.recording is True:
                client.send_ooc("It is not cross-examination yet!")
                return
            idx = id - 1
            client.area.testimony_send(idx)
            client.area.broadcast_ooc(
                f"{client.showname} has moved to Statement {idx+1}."
            )
        except ClientError:
            raise
        return

    msg = "Use > IC to progress, < to backtrack, = to repeat, >3 or <3 to go to specific statements."
    msg += f"\n-- {client.area.testimony_title} --"
    for i, statement in enumerate(client.area.testimony):
        # [15] SHOWNAME
        name = statement[15]
        if name == "" and statement[8] != -1:
            # [8] CID
            name = client.area.area_manager.char_list[statement[8]]
        txt = statement[4].replace("{", "").replace("}", "")
        here = "  "
        if i == client.area.testimony_index:
            here = " >"
        msg += f"\n{here}{i+1}) {name}: {txt}"
    client.send_ooc(msg)


@mod_only(area_owners=True)
@command(Arg("arg", rest=True, default="", help="testimony title"))
def ooc_cmd_testimony_start(client, arg):
    """
    Manually start a testimony with the given title.
    Usage: /testimony_start <title>
    """
    if arg == "":
        raise ArgumentError(
            "You must provite a title! /testimony_start <title>."
        )
    if len(arg) < 3:
        raise ArgumentError("Title must contain at least 3 characters!")
    client.area.testimony.clear()
    client.area.testimony_index = -1
    client.area.testimony_title = arg
    client.area.recording = True
    client.area.broadcast_ooc(
        f'-- {client.area.testimony_title} --\nTestimony recording started! All new messages will be recorded as testimony lines. Say "End" to stop recording.'
    )


@mod_only(area_owners=True)
@command()
def ooc_cmd_testimony_continue(client):
    """
    Continue an existing testimony, restarting the recording so new statements may be added.
    Usage: /testimony_continue
    """
    if client.area.testimony_title == "":
        raise ArgumentError("No testimony to continue!")
    client.area.recording = True
    client.area.broadcast_ooc(
        f'-- {client.area.testimony_title} --\nTestimony recording restarted! All new messages will be recorded as testimony lines. Say "End" to stop recording.'
    )


@mod_only(area_owners=True)
@command()
def ooc_cmd_testimony_clear(client):
    """
    Clear the current testimony.
    Usage: /testimony_clear
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    client.area.testimony.clear()
    client.area.testimony_title = ""
    client.area.broadcast_ooc(
        f"{client.showname} cleared the current testimony.")


@mod_only(area_owners=True)
@command(Arg("idx", int, help="statement index"))
def ooc_cmd_testimony_remove(client, idx):
    """
    Remove the statement at index.
    Usage: /testimony_remove <id>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    try:
        idx = idx - 1
        client.area.testimony.pop(idx)
        if client.area.testimony_index == idx:
            client.area.testimony_index = -1
        client.area.broadcast_ooc(
            f"{client.showname} has removed Statement {idx+1}.")
    except ValueError:
        raise ArgumentError("Index must be a number!")
    except IndexError:
        raise ArgumentError("Index out of bounds!")
    except ClientError:
        raise


@mod_only(area_owners=True)
@command(
    Arg("id", int, help="statement index"),
    Arg("msg", rest=True, default="", help="new message"),
)
def ooc_cmd_testimony_amend(client, id, msg):
    """
    Edit the spoken message of the statement at id.
    Usage: /testimony_amend <id> <msg>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    try:
        idx = id - 1
        lst = list(client.area.testimony[idx])
        lst[4] = "}}}" + msg
        client.area.testimony[idx] = tuple(lst)
        client.area.broadcast_ooc(
            f"{client.showname} has amended Statement {idx+1}.")
    except ValueError:
        raise ArgumentError("Index must be a number!")
    except IndexError:
        raise ArgumentError("Index out of bounds!")
    except ClientError:
        raise


@mod_only(area_owners=True)
@command(
    Arg("idx1", int, help="statement index"),
    Arg("idx2", int, help="statement index"),
)
def ooc_cmd_testimony_swap(client, idx1, idx2):
    """
    Swap the two statements by idx.
    Usage: /testimony_swap <id> <id>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    try:
        idx1 = idx1 - 1
        idx2 = idx2 - 1
        client.area.testimony[idx2], client.area.testimony[idx1] = (
            client.area.testimony[idx1],
            client.area.testimony[idx2],
        )
        client.area.broadcast_ooc(
            f"{client.showname} has swapped Statements {idx1+1} and {idx2+1}."
        )
    except ValueError:
        raise ArgumentError("Index must be a number!")
    except IndexError:
        raise ArgumentError("Index out of bounds!")
    except ClientError:
        raise


@mod_only(area_owners=True)
@command(
    Arg("idx1", int, help="statement index"),
    Arg("idx2", int, help="statement index"),
)
def ooc_cmd_testimony_insert(client, idx1, idx2):
    """
    Insert the targeted statement at idx.
    Usage: /testimony_insert <id> <id>
    """
    if len(client.area.testimony) <= 0:
        client.send_ooc("There is no testimony recorded!")
        return
    try:
        idx1 = idx1 - 1
        idx2 = idx2 - 1
        statement = client.area.testimony.pop(idx1)
        client.area.testimony.insert(idx2, statement)

        client.area.broadcast_ooc(
            f"{client.showname} has inserted Statement {idx1+1} into {idx2+1}."
        )
    except ValueError:
        raise ArgumentError("Index must be a number!")
    except IndexError:
        raise ArgumentError("Index out of bounds!")
    except ClientError:
        raise


@command(
    Arg("id", int, default=None, help="target client ID (blank shows current)"),
    Arg("pta", default="", help="internal"),
)
def ooc_cmd_cs(client, id, pta):
    """
    Start a one-on-one "Cross Swords" debate with targeted player!
    Expires in 5 minutes. If there's an ongoing cross-swords already,
    it will turn into a Scrum Debate (team vs team debate)
    with you joining the side *against* the <id>.
    Usage: /cs <id>
    """
    if id is None:
        if (
            client.area.minigame_schedule
            and not client.area.minigame_schedule.cancelled()
        ):
            msg = f"Current minigame is {client.area.minigame}!\n"
            red = []
            for cid in client.area.red_team:
                name = client.area.area_manager.char_list[cid]
                for c in client.area.clients:
                    if c.char_id == cid:
                        name = f"[{c.id}] {c.showname}"
                red.append(f"🔴{name} (Red)")
            msg += "\n".join(red)
            msg += "\n⚔VERSUS⚔\n"
            blue = []
            for cid in client.area.blue_team:
                name = client.area.area_manager.char_list[cid]
                for c in client.area.clients:
                    if c.char_id == cid:
                        name = f"[{c.id}] {c.showname}"
                blue.append(f"🔵{name} (Blue)")
            msg += "\n".join(blue)
            msg += f"\n⏲{int(client.area.minigame_time_left)} seconds left."
            client.send_ooc(msg)
        else:
            client.send_ooc("There is no minigame running right now.")
        return
    try:
        target = client.server.client_manager.get_targets(
            client, TargetType.ID, id, True
        )[0]
    except Exception:
        raise ArgumentError("Target not found.")
    else:
        try:
            pta = pta == "1"
            prev_mini = client.area.minigame
            client.area.start_debate(client, target, pta=pta)
            if prev_mini != client.area.minigame:
                us = f"[{client.id}] ~{client.showname}~"
                them = f"[{target.id}] √{target.showname}√"
                if client.area.minigame == "Scrum Debate":
                    for cid in client.area.blue_team:
                        if client.char_id == cid:
                            us = f"[{client.id}] √{client.showname}√"
                            them = f"[{target.id}] ~{target.showname}~"
                            break
                msg = f"~~}}}}`{client.area.minigame}!`\\n{us} objects to {them}!"
                client.area.send_ic(
                    msg=msg,
                    showname="System",
                )
        except AreaError as ex:
            raise ex


@command(Arg("id", int, help="target client ID"))
def ooc_cmd_pta(client, id):
    """
    Start a one-on-one "Panic Talk Action" debate with targeted player!
    Unlike /cs, a Panic Talk Action (PTA) cannot evolve into a Scrum Debate.
    Expires in 5 minutes.
    Usage: /pta <id>
    """
    ooc_cmd_cs(client, f"{id} 1")


def set_minigame_song(client, minigame="", song="", condition=0):
    minigames = ["cs", "sd", "pta"]
    minigame = minigame.lower()
    if minigame not in minigames:
        raise ArgumentError("Must provide minigame!")

    condition_str = ""
    if condition == 0:
        condition_str = "start"
    elif condition == 1:
        condition_str = "end"
    elif condition == 2:
        condition_str = "concede"

    # Songname is provided
    if song != "":
        if minigame == "cs":
            if condition == 0:
                client.area.cross_swords_song_start = song
            elif condition == 1:
                client.area.cross_swords_song_end = song
            elif condition == 2:
                client.area.cross_swords_song_concede = song
        elif minigame == "sd":
            if condition == 0:
                client.area.scrum_debate_song_start = song
            elif condition == 1:
                client.area.scrum_debate_song_end = song
            elif condition == 2:
                client.area.scrum_debate_song_concede = song
        elif minigame == "pta":
            if condition == 0:
                client.area.panic_talk_action_song_start = song
            elif condition == 1:
                client.area.panic_talk_action_song_end = song
            elif condition == 2:
                client.area.panic_talk_action_song_concede = song
        client.send_ooc(
            f"Setting the {minigame} {condition_str} song to {song}.")
        return

    # Songname is not provided
    client.editing_minigame_song = minigame
    client.editing_minigame_song_condition = condition
    client.send_ooc(
        f"Play a song to set the {minigame} {condition_str} song to...")


@mod_only(area_owners=True)
@command(
    Arg("minigame", default="", help="cs/sd/pta"),
    Arg("song", rest=True, default="", type=tokens_str, help="song name (blank to pick)"),
)
def ooc_cmd_minigame_start_song(client, minigame, song):
    """
    Edit a starting song for any specific minigame. If songname is blank, it lets you choose a song from the music list to use.
    Usage: /minigame_start_song <cs/sd/pta> [songname]
    """
    print(minigame, song)
    set_minigame_song(client, minigame, song, condition=0)


@mod_only(area_owners=True)
@command(
    Arg("minigame", default="", help="cs/sd/pta"),
    Arg("song", rest=True, default="", type=tokens_str, help="song name (blank to pick)"),
)
def ooc_cmd_minigame_end_song(client, minigame, song):
    """
    Edit a ending song for any specific minigame. If songname is blank, it lets you choose a song from the music list to use.
    Usage: /minigame_end_song <cs/sd/pta> [songname]
    """
    set_minigame_song(client, minigame, song, condition=1)


@mod_only(area_owners=True)
@command(
    Arg("minigame", default="", help="cs/sd/pta"),
    Arg("song", rest=True, default="", type=tokens_str, help="song name (blank to pick)"),
)
def ooc_cmd_minigame_concede_song(client, minigame, song):
    """
    Edit a concede song for any specific minigame. If songname is blank, it lets you choose a song from the music list to use.
    Usage: /minigame_concede_song <cs/sd/pta> [songname]
    """
    set_minigame_song(client, minigame, song, condition=2)


@command(Arg("arg", default="", help="not-pta (internal)"))
def ooc_cmd_concede(client, arg):
    """
    Concede a trial minigame and withdraw from either team you're part of.
    Usage: /concede
    """
    if client.area.minigame != "":
        try:
            if arg.lower() == "not-pta" and client.area.minigame == "Panic Talk Action":
                client.send_ooc(
                    "Current minigame is Panic Talk Action - not conceding this one."
                )
                return
            # CM's end the minigame automatically using /concede
            if client in client.area.owners:
                client.area.end_minigame("Forcibly ended.")
                client.area.broadcast_ooc(
                    "The minigame has been forcibly ended.")
                return
            if client.char_id not in client.area.blue_team and client.char_id not in client.area.red_team:
                client.area.vote_end_minigame(client)
                return
            client.area.start_debate(
                client, client
            )  # starting a debate against yourself is a concede
        except AreaError as ex:
            raise ex
    else:
        client.send_ooc("There is no minigame running right now.")


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="subtheme name"))
def ooc_cmd_subtheme(client, arg):
    """
    Change the subtheme (DRO gamemode) for the hub.
    Usage: /subtheme <subtheme_name>
    """
    client.area.area_manager.subtheme = arg.strip()
    # Set everyone's subthemes
    client.area.area_manager.broadcast_subtheme()
    client.send_ooc(
        f"Setting hub subtheme to {arg}."
    )


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="time of day name"))
def ooc_cmd_time_of_day(client, arg):
    """
    Change the time of day for the hub.
    Usage: /time_of_day <tod_name>
    """
    client.area.area_manager.time_of_day = arg.strip()
    # Set everyone's time_of_day
    client.area.area_manager.broadcast_subtheme()
    client.send_ooc(
        f"Setting hub time_of_day to {arg}."
    )
