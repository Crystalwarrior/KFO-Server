import random
import shlex
import os
import yaml

from server import database
from server.constants import TargetType, derelative
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

from . import mod_only

__all__ = [
    "ooc_cmd_currentmusic",
    "ooc_cmd_getmusic",
    "ooc_cmd_jukebox_toggle",
    "ooc_cmd_jukebox_skip",
    "ooc_cmd_jukebox",
    "ooc_cmd_play",
    "ooc_cmd_play_once",
    "ooc_cmd_blockdj",
    "ooc_cmd_unblockdj",
    "ooc_cmd_musiclists",
    "ooc_cmd_musiclist",
    "ooc_cmd_area_musiclist",
    "ooc_cmd_hub_musiclist",
    "ooc_cmd_random_music",
    "ooc_cmd_musiclist_create",
    "ooc_cmd_musiclist_remove",
    "ooc_cmd_musiclist_add",
    "ooc_cmd_musiclist_save",
]


def ooc_cmd_currentmusic(client, arg):
    """
    Show the current music playing.
    Usage: /currentmusic
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    if client.area.music == "":
        raise ClientError("There is no music currently playing.")
    if client.is_mod:
        client.send_ooc(
            "The current music is '{}' and was played by {} ({}).".format(
                client.area.music,
                client.area.music_player,
                client.area.music_player_ipid,
            )
        )
    else:
        client.send_ooc(
            "The current music is '{}' and was played by {}.".format(
                client.area.music, client.area.music_player
            )
        )


def ooc_cmd_getmusic(client, arg):
    """
    Grab the last played track in this area.
    Usage: /getmusic
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    if client.area.music == "":
        raise ClientError("There is no music currently playing.")
    client.send_command(
        "MC",
        client.area.music,
        -1,
        "",
        client.area.music_looping,
        0,
        client.area.music_effects,
    )
    client.send_ooc(f"Playing track '{client.area.music}'.")


@mod_only(area_owners=True)
def ooc_cmd_jukebox_toggle(client, arg):
    """
    Toggle jukebox mode. While jukebox mode is on, all music changes become
    votes for the next track, rather than changing the track immediately.
    Usage: /jukebox_toggle
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    client.area.jukebox = not client.area.jukebox
    client.area.jukebox_votes = []
    client.area.broadcast_ooc(
        "{} [{}] has set the jukebox to {}.".format(
            client.showname, client.id, client.area.jukebox
        )
    )
    database.log_area(
        "jukebox_toggle", client, client.area, message=client.area.jukebox
    )


@mod_only(area_owners=True)
def ooc_cmd_jukebox_skip(client, arg):
    """
    Skip the current track.
    Usage: /jukebox_skip
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    if not client.area.jukebox:
        raise ClientError("This area does not have a jukebox.")
    if len(client.area.jukebox_votes) == 0:
        raise ClientError(
            "There is no song playing right now, skipping is pointless.")
    client.area.start_jukebox()
    if len(client.area.jukebox_votes) == 1:
        client.area.broadcast_ooc(
            "{} [{}] has forced a skip, restarting the only jukebox song.".format(
                client.showname, client.id
            )
        )
    else:
        client.area.broadcast_ooc(
            "{} [{}] has forced a skip to the next jukebox song.".format(
                client.showname, client.id
            )
        )
    database.log_area("jukebox_skip", client, client.area)


def ooc_cmd_jukebox(client, arg):
    """
    Show information about the jukebox's queue and votes.
    Usage: /jukebox
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
    if not client.area.jukebox:
        raise ClientError("This area does not have a jukebox.")
    if len(client.area.jukebox_votes) == 0:
        client.send_ooc("The jukebox has no songs in it.")
    else:
        total = 0
        songs = []
        voters = dict()
        chance = dict()
        message = ""

        for current_vote in client.area.jukebox_votes:
            if songs.count(current_vote.name) == 0:
                songs.append(current_vote.name)
                voters[current_vote.name] = [current_vote.client]
                chance[current_vote.name] = current_vote.chance
            else:
                voters[current_vote.name].append(current_vote.client)
                chance[current_vote.name] += current_vote.chance
            total += current_vote.chance

        for song in songs:
            message += "\n- " + song + "\n"
            message += "-- VOTERS: "

            first = True
            for voter in voters[song]:
                if first:
                    first = False
                else:
                    message += ", "
                message += voter.showname + " [" + str(voter.id) + "]"
                if client.is_mod:
                    message += "(" + str(voter.ipid) + ")"
            message += "\n"

            if total == 0:
                message += "-- CHANCE: 100"
            else:
                message += "-- CHANCE: " + \
                    str(round(chance[song] / total * 100))

        client.send_ooc(f"The jukebox has the following songs in it:{message}")


def ooc_cmd_play(client, arg):
    """
    Play a track and loop it. See /play_once for this command without looping.
    Usage: /play <name>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a song.")
    client.change_music(arg, client.char_id, "", 2,
                        True)  # looped change music


def ooc_cmd_play_once(client, arg):
    """
    Play a track without looping it. See /play for this command with looping.
    Usage: /play_once <name>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a song.")
    client.change_music(arg, client.char_id, "", 2,
                        False)  # non-looped change music


@mod_only()
def ooc_cmd_blockdj(client, arg):
    """
    Prevent a user from changing music.
    Usage: /blockdj <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target. Use /blockdj <id>.")
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False
        )
    except Exception:
        raise ArgumentError("You must enter a number. Use /blockdj <id>.")
    if not targets:
        raise ArgumentError("Target not found. Use /blockdj <id>.")
    for target in targets:
        target.is_dj = False
        target.send_ooc("A moderator muted you from changing the music.")
        database.log_area("blockdj", client, client.area, target=target)
        target.area.remove_jukebox_vote(target, True)
    client.send_ooc("blockdj'd {}.".format(targets[0].char_name))


@mod_only()
def ooc_cmd_unblockdj(client, arg):
    """
    Unblock a user from changing music.
    Usage: /unblockdj <id>
    """
    if len(arg) == 0:
        raise ArgumentError("You must specify a target. Use /unblockdj <id>.")
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False
        )
    except Exception:
        raise ArgumentError("You must enter a number. Use /unblockdj <id>.")
    if not targets:
        raise ArgumentError("Target not found. Use /blockdj <id>.")
    for target in targets:
        target.is_dj = True
        target.send_ooc("A moderator unmuted you from changing the music.")
        database.log_area("unblockdj", client, client.area, target=target)
    client.send_ooc("Unblockdj'd {}.".format(targets[0].char_name))


def ooc_cmd_musiclists(client, arg):
    """
    Displays all the available music lists.
    Usage: /musiclists
    """
    text = "Available musiclists:"
    from os import listdir

    for F in listdir("storage/musiclists/"):
        if F.lower().endswith(".yaml"):
            text += "\n- {}".format(F[:-5])

    client.send_ooc(text)


def ooc_cmd_musiclist(client, arg):
    """
    Load a client-side music list. Pass no arguments to reset. /musiclists to see available lists.
    Note: if there is a set area/hub music list, their music lists will take priority.
    Usage: /musiclist [path]
    """
    try:
        arg = derelative(arg)
        if arg == "":
            client.clear_music()
            client.send_ooc("Clearing local musiclist.")
        else:
            client.load_music(f"storage/musiclists/{arg}.yaml")
            client.music_ref = arg
            client.send_ooc(f"Loading local musiclist {arg}...")
        client.refresh_music()
    except AreaError:
        raise
    except Exception:
        client.send_ooc("File not found!")


@mod_only(area_owners=True)
def ooc_cmd_area_musiclist(client, arg):
    """
    Load an area-wide music list. Pass no arguments to reset. /musiclists to see available lists.
    Area list takes priority over client lists.
    Usage: /area_musiclist [path]
    """
    try:
        arg = derelative(arg)
        if arg == "":
            client.area.clear_music()
            client.send_ooc("Clearing area musiclist.")
        else:
            client.area.load_music(f"storage/musiclists/{arg}.yaml")
            client.area.music_ref = arg
            client.send_ooc(f"Loading area musiclist {arg}...")
        client.server.client_manager.refresh_music(client.area.clients)
    except AreaError:
        raise
    except Exception:
        client.send_ooc("File not found!")


@mod_only(hub_owners=True)
def ooc_cmd_hub_musiclist(client, arg):
    """
    Load a hub-wide music list. Pass no arguments to reset. /musiclists to see available lists.
    Hub list takes priority over client lists.
    Usage: /hub_musiclist [path]
    """
    try:
        arg = derelative(arg)
        if arg == "":
            client.area.area_manager.clear_music()
            client.send_ooc("Clearing hub musiclist.")
        else:
            client.area.area_manager.load_music(
                f"storage/musiclists/{arg}.yaml")
            client.area.area_manager.music_ref = arg
            client.send_ooc(f"Loading hub musiclist {arg}...")
        client.server.client_manager.refresh_music(
            client.area.area_manager.clients)
    except AreaError:
        raise
    except Exception:
        client.send_ooc("File not found!")


def ooc_cmd_random_music(client, arg):
    """
    Play a random track from your current muisc list. If supplied, [category] will pick the song from that category.
    Usage: /random_music [category]
    """
    songs = []
    for c in client.local_music_list:
        if "category" in c and (
            arg == "" or c["category"].strip("==").lower() == arg.lower()
        ):
            if "songs" in c:
                songs = songs + c["songs"]
    if len(songs) <= 0:
        raise ArgumentError(
            "Could not find a single song that fit the criteria!")
    song_name = songs[random.randint(0, len(songs) - 1)]["name"]
    client.change_music(song_name, client.char_id, "", 2)


def musiclist_rebuild(musiclist, path):
    prepath = ""
    for item in musiclist:
        if (
            "use_unique_folder" in item
            and item["use_unique_folder"] is True
        ):
            prepath = os.path.splitext(
                os.path.basename(f"storage/musiclists/{path}"))[0] + "/"

        if "category" not in item:
            continue

        for song in item["songs"]:
            song["name"] = prepath + song["name"]
            
    return musiclist


@mod_only(hub_owners=True)
def ooc_cmd_musiclist_save(client, arg):
    """
    Allow you to save a musiclist on server list!
    Usage: /musiclist_save <local/area/hub>
    """
    if arg == "":
        client.send_ooc("Usage: /musiclist_save <local/area/hub>")
        return

    if arg not in ["local", "area", "hub"]:
        client.send_ooc("Usage: /musiclist_save <local/area/hub>")
        return
    
    if arg == "local":
        musiclist = client.music_list
        name = client.music_ref
    elif arg == "area":
        musiclist = client.area.music_list
        name = client.area.music_ref
    else:
        musiclist = client.area.area_manager.music_list
        name = client.area.area_manager.music_ref
       
    with open(f"storage/musiclists/{name}.yaml", "w", encoding="utf-8") as yaml_save:
        yaml.dump(musiclist, yaml_save)
    


def ooc_cmd_musiclist_remove(client, arg):
    """
    Allow you to remove a song from a musiclist!
    Remember to insert also Music extension in <MusicName>
    Usage: /musiclist_remove <local/area/hub> <Category> <MusicName>
    """
    if arg == "":
        client.send_ooc(
            "Usage: /musiclist_remove <local/area/hub> <Category> <MusicName>"
        )
        return

    args = shlex.split(arg)
    if len(args) != 3:
        client.send_ooc(
            "Usage: /musiclist_remove <local/area/hub> <Category> <MusicName>"
        )
        return

    if args[0] not in ["local", "area", "hub"]:
        client.send_ooc("You can add a song if musiclist is loaded in local or in area or in hub.\nUsage: /musiclist_add <local/area/hub> <Category> <MusicName>")
        return
    
    if args[0] == "local":
        targets = [client]
        musiclist = client.music_list
    elif args[0] == "area":
        if client not in client.area.owners and client not in client.area.area_manager.owners and not client.is_mod:
            client.send_ooc("You should be at least cm to add a song in a musiclist!")
            return
        targets = client.area.clients
        musiclist = client.area.music_list
    else:
        if client not in client.area.area_manager.owners and not client.is_mod:
            client.send_ooc("You should be at least gm to add a song in a musiclist!")
            return
        targets = client.area.area_manager.clients
        musiclist = client.area.area_manager.music_list
        
    if musiclist == []:
        client.send_ooc("You can add a song if a musiclist is loaded in local or in area or in hub.")
        return

    categories = []
    for i in range(0, len(musiclist)):
        if "category" in musiclist[i]:
            categories.append(musiclist[i]["category"])
        else:
            categories.append(None)

    if f"=={args[1]}==" not in categories:
        client.send_ooc("Category has not been found!")
        return

    category_id = categories.index(f"=={args[1]}==")

    songs = [
        musiclist[category_id]["songs"][i]["name"]
        for i in range(0, len(musiclist[category_id]["songs"]))
    ]

    if args[2] not in songs:
        client.send_ooc("Song has not been found!")
        return

    song_id = songs.index(args[2])
    musiclist[category_id]["songs"].pop(song_id)
    if len(musiclist[category_id]["songs"]) == 0:
        musiclist.pop(category_id)

    if args[0] == "local":
        path = client.music_ref
        client.music_list = musiclist_rebuild(musiclist, path)
    elif args[0] == "area":
        path = client.area.music_ref
        client.area.music_list = musiclist_rebuild(musiclist, path)
    else:
        path = client.area.area_manager.music_ref
        client.area.area_manager.music_list = musiclist_rebuild(musiclist, path)
        
    client.server.client_manager.refresh_music(targets)
    client.send_ooc(f"'{args[2]}' song has been removed to '{path}' musiclist.")


def ooc_cmd_musiclist_add(client, arg):
    """
    Allow you to add a song in a loaded musiclist!
    Remember to insert also Music extension in <MusicName>
    Usage: /musiclist_add <local/area/hub> <Category> <MusicName>
    """
    if arg == "":
        client.send_ooc("Usage: /musiclist_add <local/area/hub> <Category> <MusicName>")
        return

    args = shlex.split(arg)
    if len(args) != 3:
        client.send_ooc("Usage: /musiclist_add <local/area/hub> <Category> <MusicName>")
        return
    
    if args[0] not in ["local", "area", "hub"]:
        client.send_ooc("You can add a song if musiclist is loaded in local or in area or in hub.\nUsage: /musiclist_add <local/area/hub> <Category> <MusicName>")
        return
    
    if args[0] == "local":
        targets = [client]
        musiclist = client.music_list
    elif args[0] == "area":
        if client not in client.area.owners and client not in client.area.area_manager.owners and not client.is_mod:
            client.send_ooc("You should be at least cm to add a song in a musiclist!")
            return
        targets = client.area.clients
        musiclist = client.area.music_list
    else:
        if client not in client.area.area_manager.owners and not client.is_mod:
            client.send_ooc("You should be at least gm to add a song in a musiclist!")
            return
        targets = client.area.area_manager.clients
        musiclist = client.area.area_manager.music_list
        
    if musiclist == []:
        client.send_ooc("You can add a song if a musiclist is loaded in local or in area or in hub.")
        return
             
    categories = []
    for i in range(0, len(musiclist)):
        if "category" in musiclist[i]:
            categories.append(musiclist[i]["category"])
        else:
            categories.append(None)

    if f"=={args[1]}==" not in categories:
        musiclist.append({})
        category_id = len(musiclist) - 1
        musiclist[category_id]["category"] = f"=={args[1]}=="
        musiclist[category_id]["songs"] = []
    else:
        category_id = categories.index(f"=={args[1]}==")

    musiclist[category_id]["songs"].append({})
    song_id = len(musiclist[category_id]["songs"]) - 1

    musiclist[category_id]["songs"][song_id]["name"] = args[2]
    musiclist[category_id]["songs"][song_id]["length"] = -1

    if args[0] == "local":
        path = client.music_ref
        client.music_list = musiclist_rebuild(musiclist, path)
    elif args[0] == "area":
        path = client.area.music_ref
        client.area.music_list = musiclist_rebuild(musiclist, path)
    else:
        path = client.area.area_manager.music_ref
        client.area.area_manager.music_list = musiclist_rebuild(musiclist, path)
                
    client.server.client_manager.refresh_music()
    client.send_ooc(f"'{args[2]}' song has been added to '{path}' musiclist.")


@mod_only(hub_owners=True)
def ooc_cmd_musiclist_create(client, arg):
    """
    Allow you to create a musiclist!
    <Replace> and <UseUniqueFolder> are optional arguments
    Usage: /musiclist_create <MusiclistName> <Replace> <UseUniqueFolder>
    """
    if arg == "":
        client.send_ooc(
            "Usage: /musiclist_create <MusiclistName> <Replace> <UseUniqueFolder>"
        )
        return

    args = shlex.split(arg)
    args[0] = f"storage/musiclists/{derelative(args[0])}.yaml"

    if os.path.isfile(args[0]):
        raise ArgumentError(f"Musiclist {args[0]} already exists")

    musiclist = [{}]
    replace = False
    if "replace" in args or "Replace" in args:
        replace = True

    useuniquefolder = False
    if (
        "UseUniqueFolder" in args
        or "Useuniquefolder" in args
        or "useuniquefolder" in args
    ):
        useuniquefolder = True

    musiclist[0]["replace"] = replace
    musiclist[0]["use_unique_folder"] = useuniquefolder
    with open(args[0], "w", encoding="utf-8") as yaml_save:
        yaml.dump(musiclist, yaml_save)

    name = shlex.split(arg)[0]
    client.send_ooc(
        f"Musiclist has been saved as '{derelative(name)}' on the server."
    )
