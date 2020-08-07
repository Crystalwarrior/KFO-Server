# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# possible keys: ip, OOC, id, cname, ipid, hdid

import datetime
import random
import hashlib
import string
import time
import traceback

from server import logger
from server.constants import Constants, TargetType
from server.exceptions import ArgumentError, AreaError, ClientError, ServerError
from server.exceptions import PartyError, ZoneError
from server.client_manager import ClientManager

""" <parameter_name>: required parameter
{parameter_name}: optional parameter
"""

def ooc_cmd_announce(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Sends an "announcement" to all users in the server, regardless of whether they have global chat
    turned on or off.
    Returns an error if user sends an empty message.

    SYNTAX
    /announce <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /announce Hello World       :: Sends Hello World to all users in the server.
    """

    try:
        Constants.assert_command(client, arg, is_mod=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You cannot send an empty announcement.')

    client.server.send_all_cmd_pred('CT', '{}'.format(client.server.config['hostname']),
                                    '=== Announcement ===\r\n{}\r\n=================='.format(arg))
    logger.log_server('[{}][{}][ANNOUNCEMENT]{}.'
                      .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_area(client: ClientManager.Client, arg: str):
    """
    Either lists all areas in the server or switches the user to a new given area.
    Returns an error if user is unathorized to list all areas or unable to move to the intended new
    area.

    SYNTAX
    /area {new_area_id}

    OPTIONAL PARAMETERS
    {new_area_id}: ID of the area

    EXAMPLES
    /area       :: Lists all areas in the server along with their user count.
    /area 1     :: Moves you to area 1
    """

    args = arg.split()
    # List all areas
    if len(args) == 0:
        if client.in_rp:
            client.send_limited_area_list()
        else:
            client.send_area_list()

    # Switch to new area
    elif len(args) == 1:
        try:
            area = client.server.area_manager.get_area_by_id(int(args[0]))
            client.change_area(area, from_party=(client.party is not None))
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
    else:
        raise ArgumentError('Too many arguments. Use /area <id>.')

def ooc_cmd_area_kick(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Kicks a player by client ID or IPID to a given area by ID or name, or the default area if not
    given an area. GMs cannot perform this command on users in lobby areas.
    If given IPID, it will kick all clients opened by the user. Otherwise, it will just kick the
    given client.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user, or if there was some
    sort of error in the process of kicking the user to the area (e.g. full area).

    SYNTAX
    /area_kick <client_id> {target_area}
    /area_kick <client_ipid> {target_area}

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    OPTIONAL PARAMETERS
    {target_area}: Intended area to kick the player, by ID or name

    EXAMPLES
    Assuming the default area of the server is area 0...
    /area_kick 1                        :: Kicks the player whose client ID is 1 to area 0.
    /area_kick 1234567890 3             :: Kicks all the clients opened by the player whose IPID is 1234567890 to area 3.
    /area_kick 0987654321 Lobby         :: Kicks all the clients opened by the player whose IPID is 0987654321 to Lobby.
    /area_kick 3 Class Trial Room,\ 2   :: Kicks the player whose client ID is 1 to Class Trial Room, 2 (note the ,\).
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='&1-2', split_spaces=True)
    arg = arg.split(' ')

    if not client.is_mod and not client.is_cm and client.area.lobby_area:
        raise ClientError('You must be authorized to kick clients in lobby areas.')

    if len(arg) == 1:
        area = client.server.area_manager.get_area_by_id(client.server.default_area)
    else:
        area = Constants.parse_area_names(client, [" ".join(arg[1:])])[0]

    for c in Constants.parse_id_or_ipid(client, arg[0]):
        # Failsafe in case kicked player has their character changed due to its character being used
        current_char = c.displayname
        old_area = c.area

        try:
            c.change_area(area, override_passages=True, override_effects=True, ignore_bleeding=True)
        except ClientError as error:
            error_mes = ", ".join([str(s) for s in error.args])
            client.send_ooc('Unable to kick client {} ({}) to area {}: {}'
                            .format(c.id, current_char, area.id, error_mes))
        else:
            client.send_ooc('You kicked client {} ({}) from area {} to area {}.'
                            .format(c.id, current_char, old_area.id, area.id))
            c.send_ooc('You were kicked from the area to area {}.'.format(area.id))
            client.send_ooc_others('(X) {} [{}] kicked client {} from area {} to area {}.'
                                   .format(client.displayname, client.id, c.id, old_area.id,
                                           area.id),
                                   not_to={c}, is_staff=True)

            if old_area.is_locked or old_area.is_modlocked:
                try: # Try and remove the IPID from the area's invite list
                    old_area.invite_list.pop(c.ipid)
                except KeyError:
                    pass # Would only happen if target had joined the locked area through mod powers

            if client.party:
                party = client.party
                party.remove_member(client)
                client.send_ooc('You were also kicked off your party.')
                for member in party.get_members():
                    member.send_ooc('{} was area kicked off your party.'.format(current_char))

def ooc_cmd_area_list(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Sets the server's current area list (what areas exist at any given time). If given no arguments,
    it will return the area list to its original value (in areas.yaml). The list of area lists can
    be accessed with /area_lists. Clients that do not process 'SM' packets can be in servers that
    use this command without crashing, but they will continue to only see the areas they could see
    when joining.
    Returns an error if the given area list was not found.

    SYNTAX
    /area_list <area_list>

    PARAMETERS
    <area_list>: Name of the intended area list

    EXAMPLES
    /area_list dr1dr2       :: Load the "dr1dr2" area list.
    /area_list              :: Reset the area list to its original value.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # lists which areas are locked before the reload
    old_locked_areas = [area.name for area in client.server.area_manager.areas if area.is_locked]

    if not arg:
        client.server.area_manager.load_areas()
        client.send_ooc('You have restored the original area list of the server.')
        client.send_ooc_others('The original area list of the server has been restored.',
                               is_officer=False)
        client.send_ooc_others('{} [{}] has restored the original area list of the server.'
                               .format(client.name, client.id), is_officer=True)
    else:
        try:
            new_area_file = 'config/area_lists/{}.yaml'.format(arg)
            client.server.area_manager.load_areas(area_list_file=new_area_file)
        except ServerError as exc:
            try:
                code = exc.code
            except AttributeError:
                code = None

            if code == 'FileNotFound':
                raise ArgumentError('Could not find the area list file `{}`.'.format(new_area_file))
            elif code == 'OSError':
                raise ArgumentError('Unable to open area list file `{}`: `{}`.'
                                    .format(new_area_file, exc.message))
            raise # Weird exception, reraise it
        except AreaError as exc:
            raise ArgumentError('The area list {} returned the following error when loading: `{}`.'
                                .format(new_area_file, exc))

        client.send_ooc('You have loaded the area list {}.'.format(arg))
        client.send_ooc_others('The area list {} has been loaded.'.format(arg), is_officer=False)
        client.send_ooc_others('{} [{}] has loaded the area list {}.'
                               .format(client.name, client.id, arg),
                               is_officer=True)

    # Every area that was locked before the reload gets warned that their areas were unlocked.
    for area_name in old_locked_areas:
        try:
            area = client.server.area_manager.get_area_by_name(area_name)
            area.broadcast_ooc('This area became unlocked after the area reload. Relock it using '
			                   '/lock.')
        # if no area is found with that name, then an old locked area does not exist anymore, so
        # we do not need to do anything.
        except AreaError:
            pass

def ooc_cmd_area_lists(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Lists all available area lists as established in config/area_lists.yaml. Note that, as this
    file is updated independently from the other area lists, an area list does not need to be in
    this file in order to be usable, and an area list in this list may no longer exist.

    SYNTAX
    /area_lists

    PARAMETERS
    None

    EXAMPLES
    /area_lists             :: Return all available area lists
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    try:
        with Constants.fopen('config/area_lists.yaml', 'r') as f:
            output = 'Available area lists:\n'
            for line in f:
                output += '*{}'.format(line)
            client.send_ooc(output)
    except ServerError as exc:
        if exc.code == 'FileNotFound':
            raise ClientError('Server file area_lists.yaml not found.')

def ooc_cmd_autopass(client: ClientManager.Client, arg: str):
    """
    Toggles enter/leave messages being sent automatically or not to users in the current area.
    It will not send those messages if the client is spectator or while sneaking. Altered messages
    will be sent if the area's lights are turned off.

    SYNTAX
    /autopass

    PARAMETERS
    None

    EXAMPLE
    /autopass
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.autopass = not client.autopass
    status = {False: 'off', True: 'on'}

    client.send_ooc('Autopass turned {}.'.format(status[client.autopass]))

def ooc_cmd_ban(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Kicks given user from the server and prevents them from rejoining. The user can be identified
    by either their IPID or IP address. Requires /unban to undo.
    Returns an error if given identifier does not correspond to a user.

    SYNTAX
    /ban <client_ipid>
    /ban <client_ip>

    PARAMETERS
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    <client_ip>: user IP

    EXAMPLES
    /ban 1234567890             :: Bans the user whose IPID is 1234567890
    /ban 127.0.0.1              :: Bans the user whose IP is 127.0.0.1
    """

    arg = arg.strip()
    Constants.assert_command(client, arg, parameters='>0', is_mod=True)

    # Guesses that any number is an IPID
    # and that any non-numerical entry is an IP address.
    if arg.isdigit():
        # IPID
        idnt = int(arg)
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, idnt, False)
    else:
        # IP Address
        idnt = arg
        targets = client.server.client_manager.get_targets(client, TargetType.IP, idnt, False)

    # Try and add the user to the ban list based on the given identifier
    client.server.ban_manager.add_ban(idnt)

    # Kick+ban all clients opened by the targeted user.
    if targets:
        for c in targets:
            client.send_ooc('You banned {} [{}/{}].'.format(c.displayname, c.ipid, c.hdid))
            client.send_ooc_others('{} was banned.'.format(c.displayname), is_officer=False,
                                   in_area=True)
            client.send_ooc_others('{} [{}] banned {} [{}/{}].'
                                   .format(client.name, client.id, c.displayname, c.ipid, c.hdid),
                                   is_officer=True)
            c.disconnect()

    plural = 's were' if len(targets) != 1 else ' was'
    client.send_ooc('You banned `{}`. As a result, {} client{} kicked as well.'
                    .format(idnt, len(targets), plural))
    client.send_ooc_others('{} banned `{}`. As a result, {} client{} kicked as well.'
                           .format(client.name, idnt, len(targets), plural), is_officer=True)
    logger.log_server('Banned {}.'.format(idnt), client)

def ooc_cmd_banhdid(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Similar to /ban (kicks given user from the server if they are there and prevents them from
    rejoining), but the identifier must be an HDID. It does not require the player to be online.
    Requires /unbanhdid to undo.
    Returns an error if given identifier does not correspond to a user, or if the user is already
    banned.

    SYNTAX
    /banhdid <client_hdid>

    PARAMETERS
    <client_hdid>: User HDID (available in server logs and through a mod /whois)

    EXAMPLES
    /banhdid abcd1234             :: Bans the user whose HDID is abcd1234
    """

    Constants.assert_command(client, arg, parameters='=1', is_mod=True)

    if not arg in client.server.hdid_list:
        raise ClientError('Unrecognized HDID {}.'.format(arg))

    # This works by banning one of the IPIDs the player is associated with. The way ban handling
    # works is that the server keeps track of all the IPIDs a player has logged in with their HDID
    # and checks on joining if any of those IPIDs was banned in the past. If that is the case,
    # then the server assumes that player is banned, even if they have changed IPIDs in the meantime

    # Thus, banning one IPID is sufficient, so check if any associated IPID is already banned.
    for ipid in client.server.hdid_list[arg]:
        if client.server.ban_manager.is_banned(ipid):
            raise ClientError('Player is already banned.')

    identifier = random.choice(client.server.hdid_list[arg])
    # Try and add the user to the ban list based on the given identifier
    client.server.ban_manager.add_ban(identifier)

    # Try and kick the user from the server, as well as announce their ban.
    targets = client.server.client_manager.get_targets(client, TargetType.HDID, arg, False)

    # Kick+ban all clients opened by the targeted user.
    if targets:
        for c in targets:
            client.send_ooc('You HDID banned {} [{}/{}].'.format(c.displayname, c.ipid, c.hdid))
            client.send_ooc_others('{} was banned.'.format(c.displayname), is_officer=False,
                                   in_area=True)
            client.send_ooc_others('{} [{}] HDID banned {} [{}/{}].'
                                   .format(client.name, client.id, c.displayname, c.ipid, c.hdid),
                                   is_officer=True)
            c.disconnect()

    plural = 's were' if len(targets) != 1 else ' was'
    client.send_ooc('You banned HDID `{}`. As a result, {} client{} kicked as well.'
                    .format(arg, len(targets), plural))
    client.send_ooc_others('{} [{}] banned HDID `{}`. As a result, {} client{} kicked as well.'
                           .format(client.name, client.id, arg, len(targets), plural),
                           is_officer=True)
    logger.log_server('HDID-banned {}.'.format(identifier), client)

def ooc_cmd_bg(client: ClientManager.Client, arg: str):
    """
    Change the background of the current area.
    Returns an error if area background is locked and the user is unathorized or if the sought
    background does not exist.

    SYNTAX
    /bg <background_name>

    PARAMETERS
    <background_name>: New background name, possibly with spaces (e.g. Principal's Room)

    EXAMPLES
    /bg Principal's Room   :: Changes background to Principal's Room
    """

    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a name. Use /bg <background>.')
    if not client.is_mod and client.area.bg_lock:
        raise AreaError("This area's background is locked.")

    client.area.change_background(arg, validate=not (client.is_staff() or client.area.cbg_allowed))
    client.area.broadcast_ooc('{} changed the background to {}.'
                              .format(client.displayname, arg))
    logger.log_server('[{}][{}]Changed background to {}'
                      .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_bglock(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Toggles background changes by non-mods in the current area being allowed/disallowed.

    SYNTAX
    /bglock

    PARAMETERS
    None

    EXAMPLES
    /bglock
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    client.area.bg_lock = not client.area.bg_lock
    client.area.broadcast_ooc('A mod has set the background lock to {}.'
                              .format(client.area.bg_lock))
    logger.log_server('[{}][{}]Changed bglock to {}'
                      .format(client.area.id, client.get_char_name(), client.area.bg_lock), client)

def ooc_cmd_bilock(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Changes the passage status between given areas by name or ID. Passages are unidirectional, so
    to change a passage in just one direction, use /unilock instead.
    If given one area, it will change the passage status between the current area and the given one.
    If given two areas instead, it  will change the passage status between them (but requires
    staff role to use).
    Returns an error if the user is unauthorized to create new passages or change existing ones in
    any of the relevant areas. In particular, non-staff members are not allowed to create passages
    that did not exist when the areas were loaded or that a staff member did not create before.

    SYNTAX
    /bilock <target_area>
    /bilock <target_area_1>, <target_area_2>

    PARAMETERS
    <target_area>: Area whose passage status with the current area will be changed.
    <target_area_1>: Area whose passage status with <target_area_2> will be changed.
    <target_area_2>: Area whose passage status with <target_area_1> will be changed.

    EXAMPLES
    Assuming the player is in area 0 when executing these commands and originally the only existing
    passage lock is from area 1 'Class Trial Room' to area 2 'Class Trial Room, 2'...
    /bilock Class Trial Room            :: Locks the passage between area 0 and Class Trial Room.
    /bilock 1, 2                        :: Unlocks the passage from Class Trial Room to Class Trial
                                           Room, 2; and locks it from Class Trial Room, 2 to Class
                                           Trial Room.
    /bilock Class Trial Room,\ 2, 0     :: Locks the passage in both directions between areas 0
                                           and Class Trial Room, 2 (note the ,\ in the command.
    """

    Constants.assert_command(client, arg, parameters='&1-2', split_commas=True)
    areas = arg.split(', ')
    if len(areas) == 2 and not client.is_staff():
        raise ClientError('You must be authorized to use the two-parameter version of this command.')

    areas = Constants.parse_two_area_names(client, areas, area_duplicate=False,
                                           check_valid_range=False)
    now_reachable = Constants.parse_passage_lock(client, areas, bilock=True)

    status = {True: 'unlocked', False: 'locked'}
    now0, now1 = status[now_reachable[0]], status[now_reachable[1]]
    name0, name1 = areas[0].name, areas[1].name

    if now_reachable[0] == now_reachable[1]:
        client.send_ooc('You have {} the passage between {} and {}.'.format(now0, name0, name1))
        client.send_ooc_others('(X) {} [{}] has {} the passage between {} and {} ({}).'
                               .format(client.displayname, client.id, now0,
                                       name0, name1, client.area.id),
                               is_zstaff_flex=True)
        logger.log_server('[{}][{}]Has {} the passage between {} and {}.'
                          .format(client.area.id, client.get_char_name(), now0, name0, name1))

    else:
        client.send_ooc('You have {} the passage from {} to {} and {} it the other way around.'
                        .format(now0, name0, name1, now1))
        client.send_ooc_others('(X) {} [{}] has {} the passage from {} and {} and {} it the other '
                               'way around ({}).'
                               .format(client.displayname, client.id, now0,
                                       name0, name1, now1, client.area.id),
                               is_zstaff_flex=True)
        logger.log_server('[{}][{}]Has {} the passage from {} to {} and {} it the other way around.'
                          .format(client.area.id, client.get_char_name(), now0, name0, name1, now1))

def ooc_cmd_blind(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Changes the blind status of a player by client ID.
    Blind players will receive no character sprites nor background with IC messages and cannot
    use "visual" commands such as /look, /getarea, etc.
    Immediately after blinding/unblinding, the target will receive sense-appropiate blood
    notifications in the area if needed (e.g. players bleeding, blood trails, etc.).
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /blind <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLES
    Assuming client 1 starts sighted...
    /blind 1            :: Blinds client 1
    /blind 1            :: Unblinds client 1
    """

    Constants.assert_command(client, arg, is_staff=True)
    target = Constants.parse_id(client, arg)

    status = {False: 'unblinded', True: 'blinded'}
    new_blind = not target.is_blind

    client.send_ooc('You have {} {}.'.format(status[new_blind], target.displayname))
    target.send_ooc('You have been {}.'.format(status[new_blind]))
    target.send_ooc_others('(X) {} [{}] has {} {} ({}).'
                           .format(client.displayname, client.id, status[new_blind],
                                   target.displayname, target.area.id),
                           not_to={client}, is_zstaff_flex=True)

    target.change_blindness(new_blind)

def ooc_cmd_blockdj(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Revokes the ability of a player by client ID (number in brackets) or IPID (number in
    parentheses) to change music.
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /blockdj <client_id>
    /blockdj <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /blockdj 1                     :: Revokes DJ permissions to the client whose ID is 1.
    /blockdj 1234567890            :: Revokes DJ permissions to all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_officer=True)

    # Block DJ permissions to matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.is_dj = False
        logger.log_server('Revoked DJ permissions to {}.'.format(c.ipid), client)
        client.area.broadcast_ooc('{} had their DJ permissions revoked.'.format(c.displayname))

def ooc_cmd_bloodtrail(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles a client by client ID leaving a blood trail wherever they go or not. OOC announcements are
    made to players joining an area regarding the existence of a blood trail and where it leads to.
    Turning off a player leaving a blood trail does not clean the blood in the area. For that,
    use /bloodtrail_clean.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /bloodtrail <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLE
    Assuming a player with client ID 0 starts without leaving a blood trail
    /bloodtrail 0            :: This player will now leave a blood trail wherever they go.
    """

    Constants.assert_command(client, arg, is_staff=True)
    target = Constants.parse_id(client, arg)

    status = {False: 'no longer', True: 'now'}
    status2 = {False: 'stop', True: 'start'}
    target.is_bleeding = not target.is_bleeding

    if target.is_bleeding:
        target.area.bleeds_to.add(target.area.name)

    target.send_ooc('You are {} bleeding.'.format(status[target.is_bleeding]))
    if target.is_visible and target.area.lights and target.area == client.area:
        connector = ''
    else:
        connector = '(X) '

    if target != client:
        client.send_ooc('{}You made {} {} bleeding.'
                        .format(connector, target.displayname, status2[target.is_bleeding]))
        target.send_ooc_others('(X) {} [{}] made {} {} bleeding ({}).'
                               .format(client.displayname, client.id, target.displayname,
                                       status2[target.is_bleeding], target.area.id),
                               is_zstaff_flex=True, not_to={client})
    else:
        target.send_ooc_others('(X) {} [{}] made themselves {} bleeding ({}).'
                               .format(client.displayname, client.id, status2[target.is_bleeding],
                                       target.area.id),
                               is_zstaff_flex=True, not_to={client})

    target.area_changer.notify_others_blood(target, target.area, target.displayname,
                                            status='stay', send_to_staff=False)

def ooc_cmd_bloodtrail_clean(client: ClientManager.Client, arg: str):
    """
    Cleans the blood trails of the current area or (STAFF ONLY) given areas by ID or name separated
    by commas. If not given any areas, it will clean the blood trail of the current area.
    Blind non-staff players (or players in a dark area) who attempt to run this command will only
    smear the blood in the area, and regardless of whether there was blood or not, they will
    believe they cleaned it.
    Attempting to clean blood in a clean area or an area where there is someone bleeding will fail.

    SYNTAX
    /bloodtrail_clean {area_1}, {area_2}, ....

    OPTIONAL PARAMETERS
    {area_n}: Area ID or name

    EXAMPLE
    Assuming the player is in area 0
    /bloodtrail_clean                           :: Cleans the blood trail in area 0
    /bloodtrail_clean 3, Class Trial Room,\ 2   :: Cleans the blood trail in area 3 and Class Trial Room, 2 (note the ,\)
    """

    if not arg:
        areas_to_clean = [client.area]
    else:
        if not client.is_staff():
            raise ClientError('You must be authorized to do that.')
        # Make sure the input is valid before starting
        raw_areas_to_clean = arg.split(", ")
        areas_to_clean = set(Constants.parse_area_names(client, raw_areas_to_clean))

    successful_cleans = set()
    for area in areas_to_clean:
        if not area.bleeds_to and not area.blood_smeared:
            if client.is_staff() or not (client.is_blind or not area.lights):
                if not arg:
                    mes = 'You could not find any blood in the area.'
                else:
                    mes = 'There is no blood in area {}.'.format(area.name)
                client.send_ooc(mes)
                continue
            # Blind non-staff members will believe they clean the area.

        # Check if someone is currently bleeding in the area,
        # which would prevent it from being cleaned.
        # Yes, you can use for/else in Python, it works exactly like regular flags.
        for c in area.clients:
            if c.is_bleeding:
                mes = ''
                if not client.is_staff() and not client.is_blind:
                    mes = 'You tried to clean the place up, but the blood just keeps coming.'
                elif client.is_staff():
                    mes = ('(X) {} in area {} is still bleeding, so the area cannot be cleaned.'
                           .format(c.displayname, area.name))

                if mes:
                    client.send_ooc(mes)
                    break
        else:
            if (client.is_blind or not area.lights) and not (area.bleeds_to or area.blood_smeared):
                # Poke fun
                client.send_ooc_others('(X) {} [{}] tried to clean the blood trail in the area, '
                                       'unaware that there was no blood to begin with.'
                                       .format(client.displayname, client.id),
                                       in_area=area, is_zstaff_flex=True)
                client.send_ooc_others('{} tried to clean the blood trail in the area, '
                                       'unaware that there was no blood to begin with.'
                                       .format(client.displayname),
                                       in_area=area, to_blind=False, is_zstaff_flex=False,
                                       pred=lambda c: area.lights)
            elif not client.is_staff() and (client.is_blind or not area.lights):
                client.send_ooc_others('{} tried to clean the blood trail in the area, but '
                                       'only managed to smear it all over the place.'
                                       .format(client.displayname),
                                       in_area=area, to_blind=False, is_zstaff_flex=False,
                                       pred=lambda c: area.lights)
                area.blood_smeared = True
            else:
                client.send_ooc_others('{} cleaned the blood trail in your area.'
                                       .format(client.displayname), is_zstaff_flex=False,
                                       in_area=area, to_blind=False, pred=lambda c: area.lights)
                area.bleeds_to = set()
                area.blood_smeared = False
            successful_cleans.add(area.name)

    if successful_cleans:
        if not arg:
            message = client.area.name
            client.send_ooc('You cleaned the blood trail in your area.')
            aname1 = 'your area'
            aname2 = 'area {}'.format(client.area.name)

            if client.is_staff():
                mes = '(X) {} [{}] cleaned the blood trail in {}.'
                client.send_ooc_others(mes.format(client.displayname, client.id, aname1),
                                       is_zstaff_flex=True, in_area=True)
                client.send_ooc_others(mes.format(client.displayname, client.id, aname2),
                                       is_zstaff_flex=True, in_area=False)
            else:
                mes = ''

                if (client.is_blind or not area.lights) and area.blood_smeared:
                    mes = ('(X) {} [{}] tried to clean the blood trail in {}, but as they could '
                           'not see, they only managed to smear it all over the place.')
                elif not (client.is_blind or not area.lights):
                    mes = '(X) {} [{}] cleaned the blood trail in {}.'

                client.send_ooc_others(mes.format(client.displayname, client.id, aname1),
                                       is_zstaff_flex=True, in_area=True)
                client.send_ooc_others(mes.format(client.displayname, client.id, aname2),
                                       is_zstaff_flex=True, in_area=False)

        elif len(successful_cleans) == 1:
            message = str(successful_cleans.pop())
            client.send_ooc('You cleaned the blood trail in area {}.'.format(message))
            client.send_ooc_others('(X) {} [{}] cleaned the blood trail in area {}.'
                                   .format(client.displayname, client.id, message),
                                   is_zstaff_flex=True)
        elif len(successful_cleans) > 1:
            message = Constants.cjoin(successful_cleans)
            client.send_ooc('You cleaned the blood trails in areas {}.'.format(message))
            client.send_ooc_others('(X) {} [{}] cleaned the blood trails in areas {}.'
                                   .format(client.displayname, client.id, message),
                                   is_zstaff_flex=True)
        logger.log_server('[{}][{}]Cleaned the blood trail in {}.'
                          .format(client.area.id, client.get_char_name(), message), client)

def ooc_cmd_bloodtrail_list(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Lists all areas that contain non-empty blood trails and how those look like.

    SYNTAX
    /bloodtrail_list

    PARAMETERS
    None

    EXAMPLE
    /bloodtrail_list
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    # Get all areas with blood in them
    areas = sorted([area for area in client.server.area_manager.areas if len(area.bleeds_to) > 0 or
                    area.blood_smeared], key=lambda x: x.name)

    # No areas found means there are no blood trails
    if not areas:
        raise ClientError('No areas have blood.')

    # Otherwise, build the list of all areas with blood
    info = '== Blood trails in this server =='
    for area in areas:
        area_bleeds_to = sorted(area.bleeds_to)

        if area_bleeds_to == [area.name]:
            pre_info = area.name
        else:
            area_bleeds_to.remove(area.name)
            pre_info = ", ".join(area_bleeds_to)

        if area.blood_smeared:
            pre_info += ' (SMEARED)'

        info += '\r\n*({}) {}: {}'.format(area.id, area.name, pre_info)

    client.send_ooc(info)

def ooc_cmd_bloodtrail_set(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sets (and replaces!) the blood trail of the current area to link all relevant areas by ID or
    name separated by commas. If not given any areas, it will set the blood trail to be a single
    unconnected pool of blood in the area.
    Requires /bloodtrail_clean to undo.

    SYNTAX
    /bloodtrail_set {area_1}, {area_2}, ....

    OPTIONAL PARAMETERS
    {area_n}: Area ID or name

    EXAMPLE
    Assuming the player is in area 0
    /bloodtrail_set                           :: Sets the blood trail in area 0 to be a single pool of blood
    /bloodtrail_set 3, Class Trial Room,\ 2   :: Sets the blood trail in area 0 to go to area 3 and Class Trial Room, 2 (note the ,\).

    NOTE: This command will automatically add the current area to the blood trail if not explicitly
    included, as it does not make too much physical sense to have a trail lead out of an area
    while there being no blood in the current area.
    """

    Constants.assert_command(client, arg, is_staff=True)

    if not arg:
        areas_to_link = [client.area]
        message = 'be an unconnected pool of blood'
    else:
        # Make sure the input is valid before starting
        raw_areas_to_link = arg.split(", ")
        areas_to_link = set(Constants.parse_area_names(client, raw_areas_to_link) + [client.area])
        message = 'go to {}'.format(Constants.cjoin([a.name for a in areas_to_link], the=True))

    client.send_ooc('Set the blood trail in this area to {}.'.format(message))
    client.send_ooc_others('The blood trail in this area was set to {}.'.format(message),
                           is_zstaff_flex=False, in_area=True, to_blind=False)
    client.send_ooc_others('(X) {} [{}] set the blood trail in area {} to {}.'
                           .format(client.displayname, client.id, client.area.name, message),
                           is_zstaff_flex=True)
    client.area.bleeds_to = {area.name for area in areas_to_link}

def ooc_cmd_bloodtrail_smear(client: ClientManager.Client, arg: str):
    """
    Smears the blood trails of the current area or (STAFF ONLY) given areas by ID or name separated
    by commas. If not given any areas, it will smear the blood trail of the current area.
    As long as the area has smeared blood, no new blood trails will be recorded and any visual
    indication of preexisting blood trails will be replaced with a 'Smeared' indication for
    non-staff members.
    Returns an error if the area has no blood or its blood is already smeared.

    SYNTAX
    /bloodtrail_smear {area_1}, {area_2}, ....

    OPTIONAL PARAMETERS
    {area_n}: Area ID or name

    EXAMPLE
    Assuming the player is in area 0
    /bloodtrail_smear                           :: Smears the blood trail in area 0
    /bloodtrail_smear 3, Class Trial Room,\ 2   :: Smears the blood trail in area 3 and Class Trial Room, 2 (note the ,\)
    """

    if not arg:
        areas_to_smear = [client.area]
    else:
        if not client.is_staff():
            raise ClientError('You must be authorized to do that.')
        # Make sure the input is valid before starting
        raw_areas_to_smear = arg.split(", ")
        areas_to_smear = set(Constants.parse_area_names(client, raw_areas_to_smear))

    successful_smears = set()
    for area in areas_to_smear:
        if not area.bleeds_to and not client.is_staff():
            if not arg:
                mes = 'You could not find any blood in the area.'
            else:
                mes = 'There is no blood in area {}.'.format(area.name)
            client.send_ooc(mes)
            continue

        if area.blood_smeared:
            client.send_ooc('Area {} already has its blood trails smeared.'.format(area.name))
        else:
            client.send_ooc_others('{} smeared the blood trail in your area.'
                                   .format(client.displayname), is_zstaff_flex=False,
                                   in_area=area, to_blind=False, pred=lambda c: area.lights)
            area.blood_smeared = True
            successful_smears.add(area.name)

    if successful_smears:
        if not arg:
            yarea = 'your area'
            oarea = 'area {}'.format(client.area.name)

            message = client.area.name
            client.send_ooc('You smeared the blood trail in your area.')

            mes = '(X) {} [{}] smeared the blood trail in {}.'
            client.send_ooc_others(mes.format(client.displayname, client.id, yarea),
                                   is_zstaff_flex=True, in_area=True)
            client.send_ooc_others(mes.format(client.displayname, client.id, oarea),
                                   is_zstaff_flex=True, in_area=False)
        elif len(successful_smears) == 1:
            message = str(successful_smears.pop())
            client.send_ooc("You smeared the blood trail in area {}.".format(message))
            client.send_ooc_others('(X) {} [{}] smeared the blood trail in area {}.'
                                   .format(client.displayname, client.id, message),
                                   is_zstaff_flex=True)
        elif len(successful_smears) > 1:
            message = Constants.cjoin(successful_smears)
            client.send_ooc("You smeared the blood trails in areas {}.".format(message))
            client.send_ooc_others('(X) {} [{}] smeared the blood trails in areas {}.'
                                   .format(client.displayname, client.id, message),
                                   is_zstaff_flex=True)
        logger.log_server('[{}][{}]Smeared the blood trail in {}.'
                          .format(client.area.id, client.get_char_name(), message), client)

def ooc_cmd_can_iniswap(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Toggles iniswapping by non-staff in the current area being allowed/disallowed.

    SYNTAX
    /can_iniswap

    PARAMETERS
    None

    EXAMPLES
    /can_iniswap
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    status = {True: 'now', False: 'no longer'}
    client.area.iniswap_allowed = not client.area.iniswap_allowed

    client.area.broadcast_ooc('Iniswapping is {} allowed in this area.'
                              .format(status[client.area.iniswap_allowed]))
    logger.log_server('[{}][{}]Set iniswapping as {} allowed in the area.'
                      .format(client.area.id, client.get_char_name(),
                              status[client.area.iniswap_allowed]), client)

def ooc_cmd_can_passagelock(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles the ability of using /unilock and /bilock for non-staff members in the current area.
    In particular, the area cannot be used as an argument either implicitly or explicitly in
    /bilock, or implicitly in /unilock if ability is turned off (but can be used explicitly).

    SYNTAX
    /can_passagelock

    PARAMETERS
    None

    EXAMPLE
    Assuming the current area started allowing the use of both commands...
    /can_passagelock         :: Non-staff members can no longer use /bilock or /unilock.
    /can_passagelock         :: Non-staff members can now use /bilock and /unilock again.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.area.change_reachability_allowed = not client.area.change_reachability_allowed
    status = {True: 'enabled', False: 'disabled'}

    client.area.broadcast_ooc('A staff member has {} the use of /unilock or /bilock that '
                              'affect this area.'
                              .format(status[client.area.change_reachability_allowed]))

def ooc_cmd_can_rollp(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles private rolls by non-staff in the current area being allowed/disallowed.

    SYNTAX
    /can_rollp

    PARAMETERS
    None

    EXAMPLES
    /can_rollp
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.area.rollp_allowed = not client.area.rollp_allowed
    status = {False: 'disabled', True: 'enabled'}

    client.area.broadcast_ooc('A staff member has {} the use of private roll commands in this '
                              'area.'.format(status[client.area.rollp_allowed]))
    logger.log_server('[{}][{}]{} private roll commands in this area.'
                      .format(client.area.id, client.get_char_name(),
                              status[client.area.rollp_allowed].capitalize()), client)

def ooc_cmd_can_rpgetarea(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles users subject to RP mode being able/unable to use /getarea in the current area.

    SYNTAX
    /can_rpgetarea

    PARAMETERS
    None

    EXAMPLE
    /can_rpgetarea
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.area.rp_getarea_allowed = not client.area.rp_getarea_allowed
    status = {False: 'disabled', True: 'enabled'}

    client.area.broadcast_ooc('A staff member has {} the use of /getarea in this area.'
                              .format(status[client.area.rp_getarea_allowed]))
    logger.log_server('[{}][{}]{} /getarea in this area.'
                      .format(client.area.id, client.get_char_name(),
                              status[client.area.rp_getarea_allowed].capitalize()), client)

def ooc_cmd_can_rpgetareas(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles users subject to RP mode being able/unable to use /getareas in the current area.

    SYNTAX
    /can_rpgetareas

    PARAMETERS
    None

    EXAMPLE
    /can_rpgetareas
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.area.rp_getareas_allowed = not client.area.rp_getareas_allowed
    status = {False: 'disabled', True: 'enabled'}

    client.area.broadcast_ooc('A staff member has {} the use of /getareas in this area.'
                              .format(status[client.area.rp_getareas_allowed]))
    logger.log_server('[{}][{}]{} /getareas in this area.'
                      .format(client.area.id, client.get_char_name(),
                              status[client.area.rp_getareas_allowed].capitalize()), client)

def ooc_cmd_charselect(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Opens the character selection screen for the current user
    OR (MOD ONLY) forces another user by identifier to have that screen open, freeing up their
    character in the process.

    SYNTAX
    /charselect
    /charselect {client_id}
    /charselect {client_ipid}

    PARAMETERS
    {client_id}: Client identifier (number in brackets in /getarea).
    {client_ipid}: IPID for the client (number in parentheses in /getarea).

    EXAMPLES
    /charselect                    :: Open character selection screen for the current user.
    /charselect 1                  :: Forces open the character selection screen for the user whose client ID is 1
    /charselect 1234567890         :: Forces open the character selection screen for the user whose IPID is 1234567890
    """

    # Open for current user case
    if not arg:
        client.send_ooc('You opened the character select screen.')
        client.char_select()

    # Force open for different user
    else:
        if not client.is_mod:
            raise ClientError('You must be authorized to do that.')

        for c in Constants.parse_id_or_ipid(client, arg):
            client.send_ooc(f'You forced {c.displayname} to open the character select screen.')
            if client != c:
                c.send_ooc('You were forced to open the character select screen.')
            client.send_ooc_others(f'{c.name} [{c.id}] forced {c.displayname} to open the '
                                   f'character select screen ({c.area.id})',
                                   not_to={c}, is_officer=True)
            c.char_select()

def ooc_cmd_char_restrict(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggle a character by folder name (not showname!) being able to be used in the current area
    by non-staff members.
    Returns an error if the character name is not recognized.

    SYNTAX
    /char_restrict <char_name>

    PARAMETERS
    <char_name>: Character name to restrict.

    EXAMPLES
    Assuming Phantom_HD is initially unrestricted....
    /char_restrict Phantom_HD           :: Restrict the use of Phantom_HD.
    /char_restrict Phantom_HD           :: Unrestrict the use of Phantom_HD.
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('This command takes one character name.')

    if arg not in client.server.char_list:
        raise ArgumentError('Unrecognized character folder name: {}'.format(arg))

    status = {True: 'enabled', False: 'disabled'}
    new_stat = status[arg in client.area.restricted_chars]

    client.send_ooc('You have {} the use of character `{}` in this area.'
                    .format(new_stat, arg))
    client.send_ooc_others('A staff member has {} the use of character {} in this area.'
                           .format(new_stat, arg), is_zstaff_flex=False, in_area=True)
    client.send_ooc_others('(X) {} [{}] has {} the use of character `{}` in area {} ({}).'
                           .format(client.displayname, client.id, new_stat, arg, client.area.name,
                                   client.area.id), is_zstaff=True)

    # If intended character not in area's restriction, add it
    if arg not in client.area.restricted_chars:
        client.area.restricted_chars.add(arg)
        # For all clients using the now restricted character, switch them to some other character.
        for c in client.area.clients:
            if not c.is_staff() and c.get_char_name() == arg:
                try:
                    new_char_id = c.area.get_rand_avail_char_id(allow_restricted=False)
                except AreaError:
                    # Force into spectator mode if all other available characters are taken
                    new_char_id = -1
                c.change_character(new_char_id, announce_zwatch=False)
                c.send_ooc('Your character has been set to restricted in this area by a staff '
                           'member. Switching you to `{}`.'.format(c.get_char_name()))
                c.send_ooc_others('(X) Client {} had their character changed from `{}` to '
                                  '`{}` in your zone as their old character was just '
                                  'restricted in their new area ({}).'
                                  .format(c.id, arg, c.get_char_name(), c.area.id),
                                  is_zstaff_flex=True)
    else:
        client.area.restricted_chars.remove(arg)

def ooc_cmd_chars_restricted(client: ClientManager.Client, arg: str):
    """
    Returns a list of all characters that are restricted in an area.

    SYNTAX
    /chars_restricted

    PARAMETERS
    None

    EXAMPLES
    If only Phantom_HD is restricted in the current area...
    /chars_restricted           :: Returns 'Phantom_HD'
    """

    Constants.assert_command(client, arg, parameters='=0')

    info = '== Characters restricted in area {} =='.format(client.area.name)
    # If no characters restricted, print a manual message.
    if len(client.area.restricted_chars) == 0:
        info += '\r\n*No characters restricted.'
    # Otherwise, build the list of all restricted chars.
    else:
        for char_name in client.area.restricted_chars:
            info += '\r\n*{}'.format(char_name)

    client.send_ooc(info)

def ooc_cmd_cleardoc(client: ClientManager.Client, arg: str):
    """
    Clears the current area's doc.

    SYNTAX
    /cleardoc

    PARAMETERS
    None

    EXAMPLES
    /cleardoc
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.area.broadcast_ooc('{} cleared the doc link.'.format(client.displayname))
    logger.log_server('[{}][{}]Cleared document. Old link: {}'
                      .format(client.area.id, client.get_char_name(), client.area.doc), client)
    client.area.change_doc()

def ooc_cmd_cleargm(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Logs out all game masters in the server and puts them in RP mode if needed.

    SYNTAX
    /cleargm

    PARAMETERS
    None

    EXAMPLE
    /cleargm
    """

    Constants.assert_command(client, arg, is_officer=True, parameters='=0')

    gm_list = ''
    for area in client.server.area_manager.areas:
        for c in [x for x in area.clients if x.is_gm]:
            gm_list += '{} {} [{}]'.format((':' if not gm_list else ','), c.name, c.id)
            c.send_ooc('You are no longer a GM.')
            c.logout()

    client.send_ooc('All GMs logged out.')
    if len(gm_list) > 0:
        client.send_ooc_others('The following GMs have been logged out by {} [{}]{}.'
                               .format(client.name, client.id, gm_list), is_officer=True)

def ooc_cmd_clock(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sets up a day cycle that will tick one hour every given number of seconds and provide a time
    announcement to a given range of areas. Starting hour is also given. The clock ID is by default
    the client ID of the player who started the clock. Doing /clock while running an active clock
    will silently overwrite the old clock with the new one.
    Requires /clock_cancel to undo.

    SYNTAX
    /clock <area_range_start> <area_range_end> <hour_length> <hour_start>

    PARAMETERS
    <area_range_start>: Send notifications from this area onwards up to...
    <area_range_end>: Send notifications up to (and including) this area.
    <hour_length>: Length of each ingame hour (in seconds)
    <hour_start>: Starting hour (integer from 0 to 23)

    EXAMPLES
    /clock 16 116 900 8         :: Start a 900-second hour clock spanning areas 16 through 116, with starting hour 8 a.m.
    /clock 0 5 10 19            :: Start a 10-second hour clock spanning areas 0 through 5, with starting hour 7 p.m.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=4', split_spaces=True)

    # Inputs already validated, move on
    pre_area_1, pre_area_2, pre_hour_length, pre_hour_start = arg.split(' ')

    areas = Constants.parse_two_area_names(client, [pre_area_1, pre_area_2], check_valid_range=True)
    area_1, area_2 = areas[0].id, areas[1].id

    try:
        hour_length = int(pre_hour_length)
        if hour_length <= 0:
            raise ValueError
    except ValueError:
        raise ArgumentError('Invalid hour length {}.'.format(pre_hour_length))

    try:
        hour_start = int(pre_hour_start)
        if hour_start < 0 or hour_start >= 24:
            raise ValueError
    except ValueError:
        raise ArgumentError('Invalid hour start {}.'.format(pre_hour_start))

    # Code after this assumes input is validated
    try:
        client.server.tasker.get_task(client, ['as_day_cycle'])
    except KeyError:
        normie_notif = True
    else:
        # Already existing day cycle. Will overwrite preexisting one
        # But first, make sure normies do not get a new notification.
        normie_notif = False

    client.send_ooc('You initiated a day cycle of length {} seconds per hour in areas {} through '
                    '{}. The cycle ID is {}.'.format(hour_length, area_1, area_2, client.id))
    client.send_ooc_others('(X) {} [{}] initiated a day cycle of length {} seconds per hour in '
                           'areas {} through {}. The cycle ID is {} ({}).'
                           .format(client.displayname, client.id, hour_length, area_1, area_2,
                                   client.id, client.area.id), is_zstaff_flex=True)
    if normie_notif:
        client.send_ooc_others('{} initiated a day cycle.'.format(client.displayname),
                               is_zstaff_flex=False, pred=lambda c: area_1 <= c.area.id <= area_2)

    client.server.tasker.create_task(client, ['as_day_cycle', time.time(), area_1, area_2,
                                              hour_length, hour_start, normie_notif])

def ooc_cmd_clock_cancel(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Cancel the day cycle established by a player by client ID (or own if not given ID)
    Returns an error if the given player has no associated active day cycle.

    SYNTAX
    /clock_cancel {client_id}

    OPTIONAL PARAMETERS
    {client_id}: Client identifier (number in brackets in /getarea)

    EXAMPLE
    /clock_cancel 0         :: Cancels the day cycle established by the player whose client ID is 0.
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        arg = str(client.id)

    try:
        c = Constants.parse_id(client, arg)
    except ClientError:
        raise ArgumentError('Client {} is not online.'.format(arg))

    try:
        client.server.tasker.remove_task(c, ['as_day_cycle'])
    except KeyError:
        raise ClientError('Client {} has not initiated any day cycles.'.format(arg))

def ooc_cmd_clock_pause(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Pauses the day cycle established by a player by client ID (or own if not given an ID).
    Requires /clock_unpause to undo.
    Returns an error if the given player has no associated active day cycle, or if their day cycle
    is already paused.

    SYNTAX
    /clock_pause {client_id}

    OPTIONAL PARAMETERS
    {client_id}: Client identifier (number in brackets in /getarea)

    EXAMPLE
    /clock_pause 0         :: Pauses the day cycle established by the player whose client ID is 0.
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        arg = str(client.id)

    try:
        c = Constants.parse_id(client, arg)
    except ClientError:
        raise ArgumentError('Client {} is not online.'.format(arg))

    try:
        task = client.server.tasker.get_task(c, ['as_day_cycle'])
    except KeyError:
        raise ClientError('Client {} has not initiated any day cycles.'.format(arg))

    is_paused = client.server.tasker.get_task_attr(c, ['as_day_cycle'], 'is_paused')
    if is_paused:
        raise ClientError('Day cycle is already paused.')

    client.server.tasker.set_task_attr(c, ['as_day_cycle'], 'is_paused', True)
    client.server.tasker.cancel_task(task)

def ooc_cmd_clock_unpause(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Unpauses the day cycle established by a player by client ID (or own if not given an ID).
    Requires /clock_pause to undo.
    Returns an error if the given player has no associated active day cycle, or if their day cycle
    is already unpaused.

    SYNTAX
    /clock_unpause {client_id}

    OPTIONAL PARAMETERS
    {client_id}: Client identifier (number in brackets in /getarea)

    EXAMPLE
    /clock_unpause 0         :: Unpauses the day cycle established by the player whose client ID is 0.
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        arg = str(client.id)

    try:
        c = Constants.parse_id(client, arg)
    except ClientError:
        raise ArgumentError('Client {} is not online.'.format(arg))

    try:
        client.server.tasker.get_task(c, ['as_day_cycle'])
    except KeyError:
        raise ClientError('Client {} has not initiated any day cycles.'.format(arg))

    is_paused = client.server.tasker.get_task_attr(c, ['as_day_cycle'], 'is_paused')
    if not is_paused:
        raise ClientError('Day cycle is already unpaused.')

    client.server.tasker.set_task_attr(c, ['as_day_cycle'], 'is_paused', False)
    client.server.tasker.set_task_attr(c, ['as_day_cycle'], 'just_unpaused', True)

def ooc_cmd_coinflip(client: ClientManager.Client, arg: str):
    """
    Flips a coin and returns the result. If given a call, it includes the call with the result.

    SYNTAX
    /coinflip {call}

    OPTIONAL PARAMETERS
    {call}: A call to the coin flip

    EXAMPLES
    If Phantom is running the following...
    /coinflip           :: May return something like "Phantom flipped a coin and got tails."
    /coinflip `heads`   :: May return something like "Phantom called `heads`, flipped a coin and got heads"
    """

    coin = ['heads', 'tails']
    flip = random.choice(coin)
    if arg:
        mes = '{} called `{}`, flipped a coin and got {}.'.format(client.displayname, arg, flip)
    else:
        mes = '{} flipped a coin and got {}.'.format(client.displayname, flip)
    client.area.broadcast_ooc(mes)
    logger.log_server('[{}][{}]Used /coinflip and got {}.'
                      .format(client.area.id, client.get_char_name(), flip), client)

def ooc_cmd_cure(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Cures the target of some of three effects (blindness, deafened, or gagged) as follows:
     For each effect in the cure:
     * If the target is subject to some poison that as one of its effects will cause the effect in
       the future, cancel that part of the poison.
     * If the target is currently experiencing that effect (either as a result of a poison that
       kicked in or being manually set before), remove the effect from the target.
     * If neither is true, do nothing for that effect.
     In particular, cancel that part of the poison and effect from the target if they are subject
     to them.
    Returns an error if the given identifier does not correspond to a user, or if the effects
    contain an unrecognized/repeated character.

    SYNTAX
    /cure <client_id> <effects>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <effects>: Effects to cure (a string consisting of non-case-sensitive 'b', 'd', and/or 'g' in
    some order corresponding to the initials of the supported effects)

    EXAMPLES
    Assuming client 1 is blind, deafened and gagged and these are run immediately one after the other:
    /cure 1 b      :: Cures client 1 of blindness.
    /cure 1 Bd     :: Cures client 1 of deafedness (note they were not blind).
    /cure 1 gDB    :: Cures client 1 of being gagged (note they were neither deafened or blind).
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=2')
    raw_target, raw_effects = arg.split(' ')
    target = Constants.parse_id(client, raw_target)
    effects = Constants.parse_effects(client, raw_effects)

    sorted_effects = sorted(effects, key=lambda effect: effect.name)
    for effect in sorted_effects:
        # Check if the client is subject to a countdown for that effect
        try:
            client.server.tasker.remove_task(target, [effect.async_name])
        except KeyError:
            pass # Do nothing if not subject to one

        if target != client:
            target.send_ooc('You were cured of the effect `{}`.'.format(effect.name))
            client.send_ooc('You cured {} of the effect `{}`.'
                            .format(target.displayname, effect.name))
            client.send_ooc_others('(X) {} [{}] cured {} of the effect `{}` ({}).'
                                   .format(client.displayname, client.id, target.displayname,
                                           effect.name, client.area.id,),
                                   is_zstaff_flex=True, not_to={target})
        else:
            client.send_ooc('You cured yourself of the effect `{}`.'.format(effect.name))
            client.send_ooc_others('(X) {} [{}] cured themselves of the effect `{}` ({}).'
                                   .format(client.displayname, client.id, effect.name,
                                           client.area.id),
                                   is_zstaff_flex=True)

        effect.function(target, False)

def ooc_cmd_currentmusic(client: ClientManager.Client, arg: str):
    """
    Returns the music currently playing and who played it, or None if no music is playing.

    SYNTAX
    /currentmusic

    PARAMETERS
    None

    EXAMPLES
    /currentmusic
    """

    Constants.assert_command(client, arg, parameters='=0')

    if client.area.current_music == '':
        raise ClientError('There is no music currently playing.')
    client.send_ooc('The current music is {} and was played by {}.'
                    .format(client.area.current_music, client.area.current_music_player))

def ooc_cmd_deafen(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Changes the deafened status of a player by client ID.
    Deaf players will be unable to read IC messages properly or receive other audio cues from
    commands such as /knock, /scream, etc.
    Immediately after deafening/undeafening, the target will receive sense-appropiate blood
    notifications in the area if needed (e.g. players bleeding while sneaking).
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /deafen <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLES
    Assuming client 1 starts hearing...
    /deafen 1            :: Deafens client 1
    /deafen 1            :: Undeafens client 1
    """

    Constants.assert_command(client, arg, is_staff=True)
    target = Constants.parse_id(client, arg)

    status = {False: 'undeafened', True: 'deafened'}
    new_deaf = not target.is_deaf

    client.send_ooc('You have {} {}.'.format(status[new_deaf], target.displayname))
    target.send_ooc('You have been {}.'.format(status[new_deaf]))
    target.send_ooc_others('(X) {} [{}] has {} {} ({}).'
                           .format(client.displayname, client.id, status[new_deaf],
                                   target.displayname, target.area.id),
                           is_zstaff_flex=True, not_to={client})

    target.change_deafened(new_deaf)

def ooc_cmd_defaultarea(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Set the default area by area ID for all future clients to join when connecting to the server.
    Returns an error if the area ID is invalid.

    SYNTAX
    /defaultarea <area_id>

    PARAMETERS
    <area_id>: Intended default area ID

    EXAMPLES
    /defaultarea 1          :: Set area 1 to be the default area.
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=1')

    try:
        client.server.area_manager.get_area_by_id(int(arg))
    except ValueError:
        raise ArgumentError('Expected numerical value for area ID.')
    except AreaError:
        raise ClientError('ID {} does not correspond to a valid area ID.'.format(arg))

    client.server.default_area = int(arg)
    client.send_ooc('Set default area to {}.'.format(arg))

def ooc_cmd_dicelog(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Obtains the last 20 roll results from the target by client ID or the user if not given any.
    Returns an error if the identifier does not correspond to a user.

    SYNTAX
    /dicelog
    /dicelog <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLES
    /dicelog        :: Returns the user's last 20 rolls
    /dicelog 1      :: Returns the user with ID 1's last 20 rolls
    """

    Constants.assert_command(client, arg, is_staff=True)
    if len(arg) == 0:
        arg = str(client.id)

    # Obtain target's dicelog
    target = Constants.parse_id(client, arg)
    info = target.get_dicelog()
    client.send_ooc(info)

def ooc_cmd_dicelog_area(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Obtains the last 20 roll resuls from an area by its ID or name or the user's current one if
    not given any.
    Returns an error if the identifier does not correspond to an area.

    SYNTAX
    /dicelog_area
    /dicelog_area <target_area>

    PARAMETERS
    <target_area>: Area whose rolls will be listed

    EXAMPLES
    /dicelog_area       :: Returns the last 20 rolls of the user's current area
    /dicelog_area 1     :: Returns the last 20 rolls of Area 1
    """

    Constants.assert_command(client, arg, is_staff=True)
    if len(arg) == 0:
        arg = str(client.area.id)

    # Obtain target area's dicelog
    target = Constants.parse_area_names(client, [arg])[0]
    info = target.get_dicelog()
    client.send_ooc(info)

def ooc_cmd_discord(client: ClientManager.Client, arg: str):
    """
    Returns the server's Discord server invite link.

    SYNTAX
    /discord

    PARAMETERS
    None

    EXAMPLE
    /discord            :: Sends the Discord invite link
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.send_ooc('Discord Invite Link: {}'.format(client.server.config['discord_link']))

def ooc_cmd_disemconsonant(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Disemconsonants all IC and OOC messages of a player by client ID (number in brackets) or IPID
    (number in parentheses). In particular, all their messages will have all their consonants
    removed. If given IPID, it will affect all clients opened by the user. Otherwise, it will just
    affect the given client. Requires /undisemconsonant to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /disemconsonant <client_id>
    /disemconsonant <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /disemconsonant 1           :: Disemconsonants the player whose client ID is 1.
    /disemconsonant 1234567890  :: Disemconsonants all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Disemconsonant matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.disemconsonant = True
        logger.log_server('Disemconsonanted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was disemconsonanted.".format(c.displayname))

def ooc_cmd_disemvowel(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Disemvowels all IC and OOC messages of a player by client ID (number in brackets) or IPID
    (number in parentheses). In particular, all their messages will have all their vowels removed.
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client. Requires /undisemvowel to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /disemvowel <client_id>
    /disemvowel <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /disemvowel 1                     :: Disemvowels the player whose client ID is 1.
    /disemvowel 1234567890            :: Disemwvowels all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Disemvowel matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.disemvowel = True
        logger.log_server('Disemvowelled {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was disemvowelled.".format(c.displayname))

def ooc_cmd_doc(client: ClientManager.Client, arg: str):
    """
    Sends the area's current doc link to the user, or sets it to a new one.

    SYNTAX
    /doc {doc_link}

    PARAMETERS
    {doc_link}: Link to new document.

    EXAMPLES
    /doc https://www.google.com     :: Sets the document link to the Google homepage.
    /doc                            :: Returns the current document (e.g. https://www.google.com)
    """

    # Clear doc case
    if len(arg) == 0:
        client.send_ooc('Document: {}'.format(client.area.doc))
        logger.log_server('[{}][{}]Requested document. Link: {}'
                          .format(client.area.id, client.get_char_name(), client.area.doc), client)
    # Set new doc case
    else:
        client.area.change_doc(arg)
        client.area.broadcast_ooc('{} changed the doc link.'.format(client.displayname))
        logger.log_server('[{}][{}]Changed document to: {}'
                          .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_files(client: ClientManager.Client, arg: str):
    """
    Obtains the download link of a player by client ID (number in brackets).
    If given no identifier, it will return your download link.
    A warning is also given in either case reminding the user to be careful of clicking external
    links, as the server provides no guarantee on the safety of the link.
    Returns an error if the given identifier does not correspond to a user or if the target has not
    set a download link for their files.

    SYNTAX
    /files
    /files <user_id>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    Assuming client 1 on character Phantom_HD and iniswapped to Spam_HD has set their files'
    download link to https://example.com
    /files 1           :: May return something like this:
        $HOST: Files set by client 1 for Spam_HD: https://example.com
        $HOST: Links are spoopy. Exercise caution when opening external links.
    """

    if arg:
        target, match, _ = client.server.client_manager.get_target_public(client, arg)

        if target.files:
            if match.isdigit():
                match = 'client {}'.format(match)
            client.send_ooc('Files set by {} for `{}`: {}'
                            .format(match, target.files[0], target.files[1]))
            client.send_ooc('Links are spoopy. Exercise caution when opening external links.')
        else:
            if match.isdigit():
                match = 'Client {}'.format(match)
            raise ClientError('{} has not provided a download link for their files.'.format(match))
    else:
        if client.files:
            client.send_ooc('Files set by yourself for `{}`: {}'
                            .format(client.files[0], client.files[1]))
            client.send_ooc('Links are spoopy. Exercise caution when opening external links.')
        else:
            raise ClientError('You have not provided a download link for your files.')

def ooc_cmd_files_set(client: ClientManager.Client, arg: str):
    """
    Sets the download link to the character the player is using (or has iniswapped to if available)
    as the  given argument; otherwise, clears it.

    SYNTAX
    /files_set
    /files_set <url>

    PARAMETERS
    <url>: URL to the download link of the characther the player is using.

    EXAMPLES
    If client 1 is on character Phantom_HD and iniswapped to Spam_HD
    /files_set https://example.com  :: Sets the download link to Spam_HD to https://example.com
    """

    if arg:
        client.files = [client.char_folder, arg]
        client.send_ooc('You have set the download link for the files of `{}` to {}'
                        .format(client.char_folder, arg))
        client.send_ooc('Let others access them with /files {}'.format(client.id))
    else:
        if client.files:
            client.send_ooc('You have removed the download link for the files of `{}`.'
                            .format(client.files[0]))
            client.files = None
        else:
            raise ClientError('You have not provided a download link for your files.')

def ooc_cmd_follow(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Starts following a player by their client ID. When the target area moves area, you will follow
    them automatically except if disallowed by the new area.
    Requires /unfollow to undo.
    Returns an error if the client is part of a party.

    SYNTAX
    /follow <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLE
    /follow 1                     :: Starts following the player whose client ID is 1
    """

    Constants.assert_command(client, arg, is_staff=True)

    if client.party:
        raise PartyError('You cannot follow someone while in a party.')

    c = Constants.parse_id(client, arg)
    client.follow_user(c)
    logger.log_server('{} began following {}.'
                      .format(client.get_char_name(), c.get_char_name()), client)

def ooc_cmd_g(client: ClientManager.Client, arg: str):
    """
    Sends a global message in the OOC chat visible to all users in the server who have not disabled
    global chat. Returns an error if the user has global chat off or sends an empty message.

    SYNTAX
    /g <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /g Hello World      :: Sends Hello World to global chat.
    """

    if client.muted_global:
        raise ClientError('You have the global chat muted.')
    if len(arg) == 0:
        raise ArgumentError("You cannot send an empty message.")

    client.server.broadcast_global(client, arg)
    logger.log_server('[{}][{}][GLOBAL]{}.'
                      .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_gag(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Changes the gagged status of a player by client ID.
    Gagged players will be unable to talk IC properly or use other talking features such as /scream.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /gag <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLES
    Assuming client 1 starts hearing...
    /gag 1            :: Gags client 1
    /gag 1            :: Ungags client 1
    """

    Constants.assert_command(client, arg, is_staff=True)
    target = Constants.parse_id(client, arg)

    status = {False: 'ungagged', True: 'gagged'}
    new_gagged = not target.is_gagged

    client.send_ooc('You have {} {}.'.format(status[new_gagged], target.displayname))
    target.send_ooc('You have been {}.'.format(status[new_gagged]))
    target.send_ooc_others('(X) {} [{}] has {} {} ({}).'
                           .format(client.displayname, client.id, status[new_gagged],
                                   target.displayname, target.area.id),
                           is_zstaff_flex=True, not_to={client})

    target.change_gagged(new_gagged)

def ooc_cmd_getarea(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Lists the characters (and associated client IDs) in the current area
    OR (STAFF ONLY) lists the character (and associated client IDs) in the given area by ID or name.
    Returns an error if the user is subject to RP mode and is in an area that disables /getarea, if
    they are blind and not staff, or if the given identifier does not correspond to an area.

    SYNTAX
    /getarea
    /getarea <target_area>

    PARAMETERS
    <target_area>: The area whose characters will be listed. By default it is the user's area.

    EXAMPLE
    If Phantom is a staff member in area 0
    /getarea            :: Lists characters in area 0
    /getarea 1          :: Lists characters in area 1.
    /getarea Basement   :: Lists characters in area Basement.
    """

    if arg:
        if not client.is_staff():
            raise ClientError.UnauthorizedError('You must be authorized to use the one-parameter '
                                                'version of this command.')
        else:
            area_id = Constants.parse_area_names(client, [arg])[0].id
    else:
        area_id = client.area.id

    if not client.is_staff() and client.is_blind:
        raise ClientError('You are blind, so you cannot see anything.')

    client.send_area_info(client.area, area_id, False)

def ooc_cmd_getareas(client: ClientManager.Client, arg: str):
    """
    List the characters (and associated client IDs) in each area.
    Returns an error if the user is subject to RP mode and is in an area that disables /getareas,
    or if they are blind and not staff.

    SYNTAX
    /getareas

    PARAMETERS
    None

    EXAMPLE
    /getareas
    """

    Constants.assert_command(client, arg, parameters='=0')

    if not client.is_staff() and client.is_blind:
        raise ClientError('You are blind, so you cannot see anything.')

    client.send_area_info(client.area, -1, False)

def ooc_cmd_gimp(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Gimps all IC messages of a player by client ID (number in brackets) or IPID (number in
    parentheses). In particular, their message will be replaced by one of the messages listed in
    Constants.gimp_message in Constants.py. If given IPID, it will affect all clients opened by the
    user. Otherwise, it will just affect the given client. Requires /ungimp to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /gimp <client_id>
    /gimp <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /gimp 1                     :: Gimps the player whose client ID is 1.
    /gimp 1234567890            :: Gimps all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Gimp matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.gimp = True
        logger.log_server('Gimping {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was gimped.".format(c.displayname))

def ooc_cmd_globalic(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Send client's subsequent IC messages to users only in specified areas. Can take either area IDs
    or area names. If current user is not in intended destination range, it will NOT send messages
    to their area. Requires /unglobalic to undo.
    Returns an error if the given identifier does not correspond to an area.

    If given two areas, it will send the IC messages to all areas between the given ones inclusive.
    If given one area, it will send the IC messages only to the given area.

    SYNTAX
    /globalic <target_area>
    /globalic <area_range_start>, <area_range_end>

    PARAMETERS
    <target_area>: Send IC messages just to this area.

    <area_range_start>: Send IC messages from this area onwards up to...
    <area_range_end>: Send IC messages up to (and including) this area.

    EXAMPLES
    /globalic 1, Courtroom 3                :: Send IC messages to areas 1 through "Courtroom 3" (if client in area 0, they will not see their own message).
    /globalic 3                             :: Send IC messages just to area 3.
    /globalic 1, 1                          :: Send IC messages just to area 1.
    /globalic Courtroom,\ 2, Courtroom 3    :: Send IC messages to areas "Courtroom, 2" through "Courtroom 3" (note the escape character).
    """

    Constants.assert_command(client, arg, parameters='&1-2', is_staff=True, split_commas=True)
    areas = Constants.parse_two_area_names(client, arg.split(', '))

    client.multi_ic = areas

    if areas[0] == areas[1]:
        client.send_ooc('Your IC messages will now be sent to area {}.'.format(areas[0].name))
    else:
        client.send_ooc('Your IC messages will now be sent to areas {} through {}.'
                        .format(areas[0].name, areas[1].name))
    client.send_ooc('Set up a global IC prefix with /globalic_pre')

def ooc_cmd_globalic_pre(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    If given an argument, it sets the client's message prefix that must be included in their IC
    messages in order for them to be globally sent as part of a /globalic command. Messages that
    do not start with this prefix will only be sent to their current area as usual. This prefix
    will also be filtered out from their message.
    If given nothing, it removes the prefix requirement and all messages will be sent globally if
    /globalic is on.

    SYNTAX
    /globalic_pre {prefix}

    OPTIONAL PARAMETERS
    {prefix}: Message prefix

    EXAMPLES
    Assuming /globalic is on...
    /globalic_pre >>>       :: Only IC messages that start with >>> will be sent globally-
    /globalic_pre           :: All IC messages will be sent globally.
    """

    Constants.assert_command(client, arg, is_staff=True)

    client.multi_ic_pre = arg
    if arg:
        client.send_ooc('You have set your global IC prefix to {}'.format(arg))
    else:
        client.send_ooc('You have removed your global IC prefix.')

def ooc_cmd_gm(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Similar to /g, but with the following changes:
    *Includes a "[GLOBAL-MOD]" tag to the message to indicate a mod sent the message.
    *Uses the OOC username as opposed to the character name when displaying the message.
    Returns an error if the user has global chat off or sends an empty message.

    SYNTAX
    /gm <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /gm Hello World     :: Sends Hello World to globat chat, preceded with [GLOBAL-MOD].
    """

    try:
        Constants.assert_command(client, arg, is_mod=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError("You cannot send an empty message.")

    if client.muted_global:
        raise ClientError('You have the global chat muted.')

    client.server.broadcast_global(client, arg, True)
    logger.log_server('[{}][{}][GLOBAL-MOD]{}.'
                      .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_gmlock(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sets the current area as accessible only to staff members. Players in the area at the time of
    the lock will be able to leave and return to the area, regardless of authorization.
    Requires /unlock to undo.
    Returns an error if the area is already gm-locked or if the area is set to be unlockable.

    SYNTAX
    /gmlock

    PARAMETERS
    None

    EXAMPLE
    /gmlock             :: Sets the current area as accessible only to staff members.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    if not client.area.locking_allowed:
        raise ClientError('Area locking is disabled in this area.')
    if client.area.is_gmlocked:
        raise ClientError('Area is already gm-locked.')

    client.area.is_gmlocked = True
    client.area.broadcast_ooc('Area gm-locked.')
    for i in client.area.clients:
        client.area.invite_list[i.ipid] = None

def ooc_cmd_gmself(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY):
    Makes all opened multiclients login as game master without them needing to put in a GM password.
    Returns an error if all opened multiclients are already game masters.

    SYNTAX
    /gmself

    PARAMETERS
    None

    EXAMPLES
    If client 0 is GM has multiclients with ID 1 and 3, neither GM, and runs...
    /gmself      :: Client 0 logs in clients 1 and 3 as game master.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    targets = [c for c in client.get_multiclients() if not c.is_gm]
    if not targets:
        raise ClientError('All opened clients are logged in as game master.')

    for target in targets:
        target.login(client.server.config['gmpass'], target.auth_gm, 'game master',
                     announce_to_officers=False)

    client.send_ooc('Logged in client{} {} as game master.'
                    .format('s' if len(targets) > 1 else '',
                            Constants.cjoin([target.id for target in targets])))

def ooc_cmd_guide(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sends an IC personal message to a specified user by some ID. Unlike /whisper, the messages do
    not have the showname of the sender nor do they send notifications to other players in the area.
    Elevated notifications are sent to zone watchers/staff members on /guide, which include the
    message content, so this is not meant to act as a private means of communication between
    players, for which /pm is recommended.
    As this is meant to act as a "subconscious/guider/personal narrator" command, deafened players
    are not affected and receive the message as is.
    Returns an error if the user could not be found, if the message is empty, if the sender is
    IC-muted, or if the user attempts to guide themselves.

    SYNTAX
    /guide <user_ID> <message>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.
    <message>: Message to be sent.

    EXAMPLES
    /guide 1 Hey, is that blood?        :: Sends that message to player with client ID 1.
    /guide 0 Check out his clothes!     :: Sends that message to player with client ID 0.
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>1')
    except ArgumentError:
        raise ArgumentError('Not enough arguments. Use /guide <target> <message>. Target should '
                            'be ID, char-name, edited-to character, custom showname or OOC-name.')
    if client.is_muted:
        raise ClientError('You have been muted by a moderator.')

    cm = client.server.client_manager
    target, _, msg = cm.get_target_public(client, arg)
    msg = msg[:256] # Cap

    if client == target:
        raise ClientError('You cannot guide yourself.')

    client.send_ooc('You gave the following guidance to {}: `{}`.'
                    .format(target.displayname, msg))

    target.send_ooc('You hear a guiding voice in your head.')
    target.send_ic(msg=msg, bypass_replace=True)

    client.send_ooc_others('(X) {} [{}] gave the following guidance to {}: `{}` ({}).'
                           .format(client.displayname, client.id, target.displayname, msg,
                                   client.area.id),
                           is_zstaff_flex=target.area, not_to={target})

def ooc_cmd_handicap(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Sets a movement handicap on a client by ID or IPID so that they need to wait a set amount of
    time between changing areas. This will override any previous handicaps the client(s) may have
    had, including custom ones and server ones (such as through sneak). Server handicaps will
    override custom handicaps if the server handicap is longer. However, as soon as the server
    handicap is over, it will recover the old custom handicap.
    If given IPID, it will set the movement handicap on all the clients opened by the user.
    Otherwise, it will just do it to the given client.
    Search by IPID can only be performed by CMs and mods.
    Requires /unhandicap to undo.
    Returns an error if the given identifier does not correspond to a user, or if given a
    non-positive length of time.

    SYNTAX
    /handicap <client_id> <length> {name} {announce_if_over}
    /handicap <client_ipid> <length> {name} {announce_if_over}

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    <length>: Handicap length (in seconds)

    OPTIONAL PARAMETERS
    {name}: Name of the handicap (e.g. "Injured", "Sleepy", etc.). By default it is "Handicap".
    {announce_if_over}: If the server will send a notification once the player may move areas after
    waiting for their handicap timer. By default it is true. For the server not to send them, put
    one of these keywords: False, false, 0, No, no

    EXAMPLES
    /handicap 0 5                   :: Sets a 5 second movement handicap on the player whose client ID is 0.
    /handicap 1234567890 10 Injured :: Sets a 10 second movement handicap called "Injured" on the clients whose IPID is 1234567890.
    /handicap 1 15 StabWound False  :: Sets a 15 second movement handicap called "StabWound" on the player whose client ID is 0
    which will not send notifications once the timer expires.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='&2-4', split_spaces=True)

    args = arg.split(' ')

    # Obtain targets
    targets = Constants.parse_id_or_ipid(client, args[0])

    # Check if valid length and convert to seconds
    length = Constants.parse_time_length(args[1]) # Also internally validates

    # Check name
    if len(args) >= 3:
        name = args[2]
    else:
        name = "Handicap" # No spaces!

    # Check announce_if_over status
    if len(args) >= 4 and args[3] in ['False', 'false', '0', 'No', 'no']:
        announce_if_over = False
    else:
        announce_if_over = True

    for c in targets:
        client.send_ooc('You imposed a movement handicap "{}" of length {} seconds on {}.'
                        .format(name, length, c.displayname))
        client.send_ooc_others('(X) {} [{}] imposed a movement handicap "{}" of length {} seconds '
                               'on {} in area {} ({}).'
                               .format(client.displayname, client.id, name, length, c.displayname,
                                       client.area.name, client.area.id),
                               is_zstaff_flex=True, pred=lambda x: x != c)
        c.send_ooc('You were imposed a movement handicap "{}" of length {} seconds when '
                   'changing areas.'.format(name, length))

        client.server.tasker.create_task(c, ['as_handicap', time.time(), length, name,
                                             announce_if_over])
        c.handicap_backup = (client.server.tasker.get_task(c, ['as_handicap']),
                             client.server.tasker.get_task_args(c, ['as_handicap']))

def ooc_cmd_help(client: ClientManager.Client, arg: str):
    """
    Returns a brief description of the command syntax and its functionality of a command by name
    according to the user's current rank, or if unauthorized to use it, display its functionality
    as if the user had the minimum rank they need to run it but warn them they need said rank to
    use it. The syntax and functionality descriptions are pulled from README.md on server boot-up.
    If not given a command name, returns the website with all available commands and their
    instructions (usually a GitHub repository).
    Returns an error if a given command name had no associated instructions on README.md.

    SYNTAX
    /help
    /help <command_name>

    PARAMETERS
    <command_name>: Name of the command (e.g. help)

    EXAMPLES
    /help       :: Displays website with all commands and instructions
    /help help  :: Displays the syntax and functionality of the help command.
    """

    if not arg:
        url = 'https://github.com/Chrezm/TsuserverDR'
        help_msg = ('Available commands, source code and issues can be found here: {}. If you are '
                    'looking for help with a specific command, do /help <command_name>'.format(url))
        client.send_ooc(help_msg)
        return

    ranks_to_try = [
            ('normie', True),
            ('gm', client.is_staff()),
            ('cm', client.is_mod or client.is_cm),
            ('mod', client.is_mod)
            ]

    # Try and find the most elevated description
    command_info, found_match, command_authorization = None, False, False
    for (rank, authorized) in ranks_to_try:
        try:
            pre_info = client.server.commandhelp[rank][arg]
        except KeyError:
            continue

        found_match = True
        if not authorized: # Check if client is authorized to use this command with this rank
            break # If not authorized now, won't be authorized later, so break out

        command_info = pre_info
        command_authorization = True # This means at least one suitable variant of the command
        # that can be run with the user's rank was found

    # If a command was found somewhere among the user's available commands, command_info
    # would be non-empty.
    if not found_match:
        raise ClientError('Could not find help for command "{}"'.format(arg))

    message = 'Help for command "{}"'.format(arg)
    # If user was not authorized to run the command, display help for command version that requires
    # the least rank possible.
    if not command_authorization:
        command_info = pre_info

    for detail in command_info:
        message += ('\n' + detail)

    if not command_authorization:
        message += ('\nYou need rank at least {} to use this command.'.format(rank))

    client.send_ooc(message)

def ooc_cmd_iclock(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles IC messages by non-staff in the current area being allowed/disallowed. Returns an error
    if not authorized, or if a GM attempts to lock IC in an area where such an action is forbidden.

    SYNTAX
    /iclock

    PARAMETERS
    None

    EXAMPLES
    /iclock
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')
    if not (client.is_mod or client.is_cm) and (client.is_gm and not client.area.gm_iclock_allowed):
        raise ClientError('GMs are not authorized to change IC locks in this area.')

    client.area.ic_lock = not client.area.ic_lock
    status = {True: 'locked', False: 'unlocked'}

    client.send_ooc('You {} the IC chat in this area.'.format(status[client.area.ic_lock]))
    client.send_ooc_others('The IC chat has been {} in this area.'
                           .format(status[client.area.ic_lock]), is_zstaff_flex=False, in_area=True)
    client.send_ooc_others('(X) {} [{}] has {} the IC chat in area {} ({}).'
                           .format(client.displayname, client.id, status[client.area.ic_lock],
                                   client.area.name, client.area.id),
                           is_zstaff_flex=True)

    logger.log_server('[{}][{}]Changed IC lock to {}'
                      .format(client.area.id, client.get_char_name(), client.area.ic_lock), client)

def ooc_cmd_invite(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Adds a client based on some ID to the area's invite list. Only staff members can invite based
    on IPID. Invites are IPID based, so anyone with the same IPID becomes part of the area's invite
    list.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user or if target is already
    invited.

    SYNTAX
    /invite <client_ipid>
    /invite <user_id>

    PARAMETERS
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    /invite 1                     :: Invites the player whose client ID is 1.
    /invite 1234567890            :: Invites all clients of the player whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, parameters='>0')

    if not client.area.is_locked and not client.area.is_modlocked and not client.area.is_gmlocked:
        raise ClientError('Area is not locked.')

    targets = list() # Start with empty list
    if (client.is_cm or client.is_mod) and arg.isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        if targets:
            some_target = targets[0]
    if not targets:
        # Under the hood though, we need the IPID of the target, so we will still end up obtaining
        # it anyway. We want to get all clients whose IPID match the IPID of whatever we match
        some_target, _, _ = client.server.client_manager.get_target_public(client, arg)
        targets = client.server.client_manager.get_targets(client, TargetType.IPID,
                                                           some_target.ipid, False)

    # Check if target is already invited
    if some_target.ipid in client.area.invite_list:
        raise ClientError('Target is already invited to your area.')

    # Add to invite list and notify targets
    client.area.invite_list[some_target.ipid] = None
    for c in targets:
        # If inviting yourself, send special message
        if client == c:
            client.send_ooc('You have invited yourself to this area.')
        else:
            client.send_ooc('Client {} has been invited to your area.'.format(c.id))
            c.send_ooc('You have been invited to area {}.'.format(client.area.name))

def ooc_cmd_judgelog(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    List the last 20 judge actions performed in the current area. This includes using the judge
    buttons and changing the penalty bars. If given an argument, it will return the judgelog of the
    given area by ID or name. Otherwise, it will obtain the one from the current area.
    Returns an error if the given identifier does not correspond to an area.

    SYNTAX
    /judgelog {target_area}

    OPTIONAL PARAMETERS
    {target_area}: area whose judgelog will be returned (either ID or name)

    EXAMPLE
    If currently in the Basement (area 0)...
    /judgelog           :: You may get something like the next example
    /judgelog 0         :: You may get something like this

    == Judge log of Basement (0) ==
    *Sat Jun 29 12:06:03 2019 | [1] Judge (1234567890) used judge button testimony1.
    *Sat Jun 29 12:06:07 2019 | [1] Judge (1234567890) used judge button testimony4.
    *Sat Jun 29 12:06:12 2019 | [1] Judge (1234567890) changed penalty bar 2 to 9.
    *Sat Jun 29 12:06:12 2019 | [1] Judge (1234567890) changed penalty bar 2 to 8.
    *Sat Jun 29 12:06:14 2019 | [1] Judge (1234567890) changed penalty bar 1 to 9.
    *Sat Jun 29 12:06:15 2019 | [1] Judge (1234567890) changed penalty bar 1 to 8.
    *Sat Jun 29 12:06:16 2019 | [1] Judge (1234567890) changed penalty bar 1 to 7.
    *Sat Jun 29 12:06:17 2019 | [1] Judge (1234567890) changed penalty bar 1 to 8.
    *Sat Jun 29 12:06:19 2019 | [1] Judge (1234567890) changed penalty bar 2 to 9.
    """

    Constants.assert_command(client, arg, is_staff=True)
    if len(arg) == 0:
        arg = client.area.name

    # Obtain matching area's judgelog
    for area in Constants.parse_area_names(client, [arg]):
        info = area.get_judgelog()
        client.send_ooc(info)

def ooc_cmd_kick(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Kicks a user from the server. The target is identified by either client ID (number in brackets)
    or IPID (number in parentheses). If given IPID, it will kick all clients opened by the user.
    Otherwise, it will just kick the given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /kick <client_id>
    /kick <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /kick 1                     :: Kicks client whose ID is 1.
    /kick 1234567890            :: Kick all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_officer=True)

    # Kick matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        client.send_ooc('You kicked {} [{}/{}].'.format(c.displayname, c.ipid, c.hdid))
        client.send_ooc_others('{} was kicked.'.format(c.displayname), is_officer=False,
                               in_area=True)
        client.send_ooc_others('{} [{}] kicked {} [{}/{}].'
                               .format(client.name, client.id, c.displayname, c.ipid, c.hdid),
                               is_officer=True)
        logger.log_server('Kicked {}.'.format(c.ipid), client)
        c.disconnect()

def ooc_cmd_kickself(client: ClientManager.Client, arg: str):
    """
    Kicks other clients opened by the current user. Useful whenever a user loses connection and the
    old client is ghosting.

    SYNTAX
    /kickself

    PARAMETERS
    None

    EXAMPLES
    /kickself
    """

    Constants.assert_command(client, arg, parameters='=0')

    for target in client.get_multiclients():
        if target != client:
            target.disconnect()

    client.send_ooc('Kicked other instances of client.')

def ooc_cmd_knock(client: ClientManager.Client, arg: str):
    """
    'Knock' on some area's door, sending a notification to users in said area.
    Returns an error if the area could not be found, if the user is already in the target area,
    if the area cannot be reached as per the DEFAULT server configuration (as users may lock
    passages, but that does not mean the door no longer exists, usually), or if the user is either
    in an area marked as lobby or attempting to knock the door to a lobby area.

    SYNTAX
    /knock <area_name>
    /knock <area_id>

    PARAMETERS
    <area_name>: Name of the area whose door you want to knock.
    <area_id>: ID of the area whose door you want to knock.

    EXAMPLES
    /knock 0                :: Knock the door to area 0
    /knock Courtroom, 2     :: Knock the door to area "Courtroom, 2"
    """

    Constants.assert_command(client, arg, parameters='=1')

    # Get area by either name or ID
    try:
        target_area = client.server.area_manager.get_area_by_name(arg)
    except AreaError:
        try:
            target_area = client.server.area_manager.get_area_by_id(int(arg))
        except Exception:
            raise ArgumentError('Could not parse area name {}.'.format(arg))

    # Filter out edge cases
    if target_area.name == client.area.name:
        raise ClientError('You cannot knock on the door of your current area.')
    if client.area.lobby_area:
        raise ClientError('You cannot knock doors from a lobby area.')
    if target_area.lobby_area:
        raise ClientError('You cannot knock the door to a lobby area.')

    if client.area.default_reachable_areas != {'<ALL>'} and \
    target_area.name not in client.area.default_reachable_areas | client.area.reachable_areas:
        raise ClientError('You tried to knock on the door to {} but you realized the room is too '
                          'far away.'.format(target_area.name))

    client.send_ooc('You knocked on the door to area {}.'.format(target_area.name))
    client.send_ooc_others('Someone knocked on your door from area {}.'.format(client.area.name),
                           is_zstaff_flex=False, in_area=target_area, to_deaf=False)
    client.send_ooc_others('(X) {} [{}] knocked on the door to area {} in area {} ({}).'
                           .format(client.displayname, client.id, target_area.name,
                                   client.area.name, client.area.id),
                           is_zstaff_flex=True)

    for c in client.area.clients:
        c.send_ic(msg='', ding=0 if c.is_deaf else 7)
    for c in target_area.clients:
        c.send_ic(msg='', ding=0 if c.is_deaf else 7)

def ooc_cmd_lasterror(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Obtain the latest uncaught error as a result of a client packet. This message emulates what is
    output on the server console (i.e. it includes the full traceback as opposed to just the last
    error which is what is usually sent to the offending client).
    Note that ClientErrors, ServerErrors, AreaErrors and Argumenterrors are usually caught by the
    client itself, and would not normally cause issues.
    Returns a (Client)error if no errors had been raised and not been caught since server bootup.

    SYNTAX
    /lasterror

    PARAMETERS
    None

    EXAMPLE
    /lasterror      :: May return something like this:

     The last uncaught error message was the following:
    TSUSERVER HAS ENCOUNTERED AN ERROR HANDLING A CLIENT PACKET
    *Server time: Mon Jul 1 14:10:26 2019
    *Packet details: CT ['Iuvee', '/lasterror']
    *Client status: C::0:1639795399:Iuvee:Kaede Akamatsu_HD:True:0
    *Area status: A::0:Basement:1
    Traceback (most recent call last):
    File "...\server\aoprotocol.py", line 88, in data_received
    self.net_cmd_dispatcher[cmd](self, args)
    File "...\server\aoprotocol.py", line 500, in net_cmd_ct
    function(self.client, arg)
    File "...\server\commands.py", line 4210, in ooc_cmd_lasterror
    final_trace = "".join(traceback.format_exc(etype, evalue, etraceback))
    TypeError: format_exc() takes from 0 to 2 positional arguments but 3 were given

    Note: yes, this is an error message that was created while testing this command.
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    if not client.server.last_error:
        raise ClientError('No error messages have been raised and not been caught since server '
                          'bootup.')

    pre_info, etype, evalue, etraceback = client.server.last_error
    final_trace = "".join(traceback.format_exception(etype, evalue, etraceback))
    info = ('The last uncaught error message was the following:\n{}\n{}'
            .format(pre_info, final_trace))
    client.send_ooc(info)

def ooc_cmd_lights(client: ClientManager.Client, arg: str):
    """
    Toggles lights on or off in the background. If area is background locked, it requires mod
    privileges. If turned off, the background will change to the server's blackout background.
    If turned on, the background will revert to the background before the blackout one.

    SYNTAX
    /lights <new_status>

    PARAMETERS
    <new_status>: 'on' or 'off'

    EXAMPLES
    Assuming lights were initially turned on
    /lights off             :: Turns off lights
    /lights on              :: Turns on lights
    """

    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify either on or off.')
    if arg not in ['off', 'on']:
        raise ClientError('Expected on or off.')
    if not client.is_staff() and not client.area.has_lights:
        raise AreaError('This area has no lights to turn off or on.')
    if not client.is_mod and client.area.bg_lock:
        raise AreaError('The background of this area is locked.')

    if not client.is_staff() and client.is_blind:
        new_lights = not client.area.lights
    else:
        new_lights = (arg == 'on')
    client.area.change_lights(new_lights, initiator=client)

def ooc_cmd_lm(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Similar to /lm, but only broadcasts the message to users in the current area, regardless of
    their global chat status.
    Returns an error if the user sends an empty message.

    SYNTAX
    /lm <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /lm Hello World     :: Sends Hello World to all users in the current area, preceded with [MOD].
    """

    try:
        Constants.assert_command(client, arg, is_mod=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You cannot send an empty message.')

    client.area.send_command('CT', '{}[MOD][{}]'
                             .format(client.server.config['hostname'], client.displayname), arg)
    logger.log_server('[{}][{}][LOCAL-MOD]{}.'
                      .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_lock(client: ClientManager.Client, arg: str):
    """
    Locks the current area, preventing anyone not in the area (except staff) from joining. It also
    clears out the current invite list.
    Returns an error if the area does not allow locking or is already locked.

    SYNTAX
    /lock

    PARAMETERS
    None

    EXAMPLE
    /lock
    """

    Constants.assert_command(client, arg, parameters='=0')

    if not client.area.locking_allowed:
        raise ClientError('Area locking is disabled in this area.')
    if client.area.is_locked:
        raise ClientError('Area is already locked.')

    client.area.is_locked = True
    for i in client.area.clients:
        client.area.invite_list[i.ipid] = None

    client.area.broadcast_ooc('Area locked.')

def ooc_cmd_login(client: ClientManager.Client, arg: str):
    """
    Logs in current user as a moderator, provided they input the correct password.

    SYNTAX
    /login <mod_password>

    PARAMETERS
    <mod_password>: Mod password, found in \config\config.yaml

    EXAMPLES
    /login Mod      :: Attempt to log in as mod with "Mod" as password.
    """

    client.login(arg, client.auth_mod, 'moderator')

def ooc_cmd_logincm(client: ClientManager.Client, arg: str):
    """
    Logs in current user as a community manager, provided they input the correct password.

    SYNTAX
    /logincm <cm_password>

    PARAMETERS
    <cm_password>: Community manager password, found in \config\config.yaml

    EXAMPLES
    /logincm CM     :: Attempt to log in as community maanger with "CM" as password.
    """

    client.login(arg, client.auth_cm, 'community manager')

def ooc_cmd_loginrp(client: ClientManager.Client, arg: str):
    """
    Logs in current user as a game master, provided they input the correct password.

    SYNTAX
    /loginrp <gm_password>

    PARAMETERS
    <gm_password>: Game master password, found in \config\config.yaml

    EXAMPLES
    /loginrp GM     :: Attempt to log in as game master with "GM" as password.
    """

    client.login(arg, client.auth_gm, 'game master')

def ooc_cmd_logout(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Logs out the current user from all staff roles and puts them in RP mode if needed.

    SYNTAX
    /logout

    PARAMETERS
    None

    EXAMPLE
    /logout
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    if client.is_mod:
        role = 'moderator'
    elif client.is_cm:
        role = 'community manager'
    else:
        role = 'game master'

    client.send_ooc('You are no longer logged in.')
    client.send_ooc_others('{} [{}] is no longer a {}.'
                           .format(client.name, client.id, role), is_officer=True)
    client.logout()

def ooc_cmd_look(client: ClientManager.Client, arg: str):
    """
    Obtain the current area's description, which is either the description in the area list
    configuration, or a customized one defined via /look_set. If the area has no set description,
    it will return the server's default description stored in the default_area_description server
    parameter. If the area has its lights turned off, it will send a generic 'cannot see anything'
    message to non-staff members.

    SYNTAX
    /look

    PARAMETERS
    None

    EXAMPLES
    If the current area's description is "Literally a courtroom"...
    /look               :: Returns "Literally a courtroom"
    """

    Constants.assert_command(client, arg, parameters='=0')

    if not client.is_staff() and client.is_blind:
        raise ClientError('You are blind, so you cannot see anything.')
    if not client.is_staff() and not client.area.lights:
        raise ClientError('The lights are off, so you cannot see anything.')

    client.send_ooc(client.area.description)

def ooc_cmd_look_clean(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Restores the default area descriptions of the given areas by ID or name separated by commas.
    If not given any areas, it will restore the default area description of the current area.

    SYNTAX
    /look_clean {area_1}, {area_2}, ....

    OPTIONAL PARAMETERS
    {area_n}: Area ID or name

    EXAMPLE
    Assuming the player is in area 0
    /look_clean                           :: Restores the default area description in area 0
    /look_clean 3, Class Trial Room,\ 2   :: Restores the default area descriptions in area 3 and Class Trial Room, 2 (note the ,\)
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        areas_to_clean = [client.area]
    else:
        # Make sure the input is valid before starting
        raw_areas_to_clean = arg.split(", ")
        areas_to_clean = set(Constants.parse_area_names(client, raw_areas_to_clean))

    successful_cleans = set()
    for area in areas_to_clean:
        area.description = area.default_description
        client.send_ooc_others('The area description was updated to {}.'.format(area.description),
                               is_zstaff_flex=False, in_area=area)
        successful_cleans.add(area.name)

    if len(successful_cleans) == 1:
        message = str(successful_cleans.pop())
        client.send_ooc('Restored the original area description of area {}.'
                        .format(message))
        client.send_ooc_others('(X) {} [{}] restored the original area description of area {}.'
                               .format(client.displayname, client.id, message),
                               is_zstaff_flex=True)
    elif len(successful_cleans) > 1:
        message = Constants.cjoin(successful_cleans)
        client.send_ooc('Restored the original area descriptions of areas {}.'
                        .format(message))
        client.send_ooc_others('(X) {} [{}] restored the original area descriptions of areas {}.'
                               .format(client.displayname, client.id, message),
                               is_zstaff_flex=True)

    logger.log_server('[{}][{}]Reset the area description in {}.'
                      .format(client.area.id, client.get_char_name(), message), client)

def ooc_cmd_look_list(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Lists all areas that contain custom descriptions.

    SYNTAX
    /look_list

    PARAMETERS
    None

    EXAMPLE
    If area 0 called Basement is the only one with a custom description, and its description
    happens to be "Not a courtroom"...
    /look_list              :: May return something like
    == Areas in this server with custom descriptions ==
    *(0) Basement: Not a courtroom
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    info = '== Areas in this server with custom descriptions =='
    # Get all areas with changed descriptions
    areas = [area for area in client.server.area_manager.areas if area.description != area.default_description]

    # No areas found means there are no areas with changed descriptions
    if len(areas) == 0:
        info += '\r\n*No areas have changed their description.'
    # Otherwise, build the list of all areas with changed descriptions
    else:
        for area in areas:
            info += '\r\n*({}) {}: {}'.format(area.id, area.name, area.description)

    client.send_ooc(info)

def ooc_cmd_look_set(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sets (and replaces!) the area description of the current area to the given one.
    If not given any description, it will set the description to be the area's default description.
    Requires /look_clean to undo.

    SYNTAX
    /look_set {area_description}

    OPTIONAL PARAMETERS
    {area_description}: New area description

    EXAMPLE
    Assuming the player is in area 0, which was set to have a default description of "A courtroom"
    /look_set "Not literally a courtroom"       :: Sets the area description in area 0 to be "Not literally a courtroom".
    /look_set                                   :: Sets the area description in area 0 to be the default "A courtroom".
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        client.area.description = client.area.default_description
        client.send_ooc('Reset the area description to its original value.')
        client.send_ooc_others('(X) {} [{}] reset the area description of your area to its '
                               'original value.'
                               .format(client.displayname, client.id),
                               is_zstaff_flex=True, in_area=True)
        client.send_ooc_others('(X) {} [{}] reset the area description of area {} to its original '
                               'value.'
                               .format(client.displayname, client.id, client.area.name),
                               is_zstaff_flex=True, in_area=False)
        logger.log_server('[{}][{}]Reset the area description in {}.'
                          .format(client.area.id, client.get_char_name(), client.area.name), client)

    else:
        client.area.description = arg
        client.send_ooc('Updated the area descriptions to `{}`.'.format(arg))
        client.send_ooc_others('(X) {} [{}] set the area description of your area to `{}`.'
                               .format(client.displayname, client.id, client.area.description),
                               is_zstaff_flex=True, in_area=True)
        client.send_ooc_others('(X) {} [{}] set the area descriptions of area {} to `{}`.'
                               .format(client.displayname, client.id, client.area.name,
                                       client.area.description),
                               is_zstaff_flex=True, in_area=False)
        logger.log_server('[{}][{}]Set the area descriptions to {}.'
                          .format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_make_gm(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Makes a player by ID a GM without them needing to put in a GM password.
    Returns an error if the target is already a GM, or if the player is not community manager or
    moderator and tries to GM a client that is not a multiclient of them.

    SYNTAX
    /make_gm <client_id>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)

    EXAMPLES
    /make_gm 3      :: Makes the client with ID 3 a GM
    """

    Constants.assert_command(client, arg, is_staff=True)
    target = Constants.parse_id(client, arg)

    if not (client.is_cm or client.is_mod) and target not in client.get_multiclients():
        raise ClientError('You must be authorized to login as game masters players other than your '
                          'multiclients.')
    if target.is_gm:
        raise ClientError('Client {} is already a GM.'.format(target.id))

    target.login(client.server.config['gmpass'], target.auth_gm, 'game master',
                 announce_to_officers=False)
    client.send_ooc('Logged client {} as a GM.'.format(target.id))
    client.send_ooc_others('{} [{}] has been logged in as a game master by {} [{}].'
                           .format(target.name, target.id, client.name, client.id), is_officer=True)

def ooc_cmd_minimap(client: ClientManager.Client, arg: str):
    """
    Lists all areas that can be reached from the current area according to areas.yaml and passages
    set in-game.
    Returns all areas if no passages were defined or created for the current area.

    SYNTAX
    /minimap

    PARAMETERS
    None

    EXAMPLE
    /minimap
    """

    Constants.assert_command(client, arg, parameters='=0')

    info = '== Areas reachable from {} =='.format(client.area.name)
    try:
        # Get all reachable areas and sort them by area ID
        sorted_areas = sorted(client.area.reachable_areas,
                              key=lambda area_name: client.server.area_manager.get_area_by_name(area_name).id)

        # No areas found or just the current area found means there are no reachable areas.
        if len(sorted_areas) == 0 or sorted_areas == [client.area.name]:
            info += '\r\n*No areas available.'
        # Otherwise, build the list of all reachable areas
        else:
            for area in sorted_areas:
                if area != client.area.name:
                    info += '\r\n*{}-{}'.format(client.server.area_manager.get_area_by_name(area).id, area)
    except AreaError:
        # In case no passages are set, send '<ALL>' as default answer.
        info += '\r\n<ALL>'

    client.send_ooc(info)

def ooc_cmd_modlock(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Sets the current area as accessible only to moderators. Players in the area at the time of the
    lock will be able to leave and return to the area, regardless of authorization.
    Requires /unlock to undo.

    Returns an error if the area is already mod-locked or if the area is set to be unlockable.

    SYNTAX
    /modlock

    PARAMETERS
    None

    EXAMPLE
    /modlock             :: Sets the current area as accessible only to staff members.
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    if not client.area.locking_allowed:
        raise ClientError('Area locking is disabled in this area.')
    if client.area.is_modlocked:
        raise ClientError('Area is already mod-locked.')

    client.area.is_modlocked = True
    client.area.broadcast_ooc('Area mod-locked.')
    for i in client.area.clients:
        client.area.invite_list[i.ipid] = None

def ooc_cmd_motd(client: ClientManager.Client, arg: str):
    """
    Returns the server's Message Of The Day.

    SYNTAX
    /motd

    PARAMETERS
    None

    EXAMPLES
    /motd
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.send_motd()

def ooc_cmd_multiclients(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Lists all clients and the areas they are opened by a player by client ID or IPID.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /multiclients <client_id>
    /multiclients <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    Assuming client 1 with IPID 1234567890 is in the Basement (area 0) and has another client open,
    whose client ID is 4...
    /multiclients 1             :: May return something like the example below (except with 1 instead of 1234567890)
    /multiclients 1234567890    :: May return something like the following:

    == Clients of 1234567890 ==
    == Area 0: Basement ==
    [1] Spam_HD (1234567890)
    == Area 4: Test 1 ==
    [4] Eggs_HD (1234567890)
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=1')

    target = Constants.parse_id_or_ipid(client, arg)[0]
    info = target.prepare_area_info(client.area, -1, False, as_mod=client.is_staff(),
                                    include_ipid=client.is_mod or client.is_cm,
                                    only_my_multiclients=True)
    info = '== Clients of {} =={}'.format(arg, info)
    client.send_ooc(info)

def ooc_cmd_music_list(client: ClientManager.Client, arg: str):
    """
    Sets the client's current music list. This list is persistent between area changes and works on
    a client basis. If given no arguments, it will return the music list to its default value
    (in music.yaml). The list of music lists can be accessed with /music_lists. Clients that do not
    process 'SM' packets can use this command without crashing, but it will have no visual effect.
    Returns an error if the given music list was not found.

    SYNTAX
    /music_list <music_list>

    PARAMETERS
    <music_list>: Name of the intended music_list

    EXAMPLES
    /music_list dr2         :: Load the "dr2" music list.
    /music_list             :: Reset the music list to its default value.
    """

    if not arg:
        client.music_list = None
        client.reload_music_list()
        client.send_ooc('You have restored the original music list of the server.')
    else:
        try:
            new_music_file = 'config/music_lists/{}.yaml'.format(arg)
            client.reload_music_list(new_music_file=new_music_file)
        except ServerError.MusicInvalidError as exc:
            raise ArgumentError('The music list {} returned the following error when loading: `{}`.'
                                .format(new_music_file, exc))
        except ServerError as exc:
            try:
                code = exc.code
            except AttributeError:
                code = None

            if code == 'FileNotFound':
                raise ArgumentError('Could not find the music list file `{}`.'
                                    .format(new_music_file))
            elif code == 'OSError':
                raise ArgumentError('Unable to open music list file `{}`: `{}`.'
                                    .format(new_music_file, exc.message))
            raise # Weird exception, reraise it

        client.send_ooc('You have loaded the music list {}.'.format(arg))

def ooc_cmd_music_lists(client: ClientManager.Client, arg: str):
    """
    Lists all available music lists as established in config/music_lists.yaml
    Note that, as this file is updated independently from the other music lists,
    some music list does not need to be in this file in order to be usable, and
    a music list in this list may no longer exist.

    SYNTAX
    /music_lists

    PARAMETERS
    None

    EXAMPLES
    /music_lists            :: Return all available music lists
    """

    Constants.assert_command(client, arg, parameters='=0')

    try:
        with Constants.fopen('config/music_lists.yaml', 'r') as f:
            output = 'Available music lists:\n'
            for line in f:
                output += '*{}'.format(line)
            client.send_ooc(output)
    except ServerError as exc:
        if exc.code == 'FileNotFound':
            raise ClientError('Server file music_lists.yaml not found.')
        raise # Weird exception, reraise

def ooc_cmd_mute(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Mutes given user based on client ID or IPID so that they are unable to speak in IC chat.
    If given IPID, it will mute all clients opened by the user. Otherwise, it will just mute the
    given client.
    Requires /unmute to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /mute <client_id>
    /mute <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /mute 1                     :: Mutes client whose ID is 1.
    /mute 1234567890            :: Mutes all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_officer=True)

    # Mute matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        logger.log_server('Muted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was muted.".format(c.displayname))
        c.is_muted = True

def ooc_cmd_online(client: ClientManager.Client, arg: str):
    """
    Returns how many players are online.

    SYNTAX
    /online

    PARAMETERS
    None

    EXAMPLE
    If there are 2 players online in a server of maximum capacity 100
    /online         :: Will return: "Online: 2/100"
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.send_ooc("Online: {}/{}"
                    .format(client.server.get_player_count(), client.server.config['playerlimit']))

def ooc_cmd_ooc_mute(client: ClientManager.Client, arg: str):
    """ (MOD AND CM ONLY)
    Mutes a player from the OOC chat by their OOC username.
    Requires /ooc_unmute to undo.
    Returns an error if no player has the given OOC username.

    SYNTAX
    /ooc_mute <ooc_name>

    PARAMETERS
    <ooc_name>: Client OOC username

    EXAMPLE
    /ooc_mute Aba           :: Mutes from OOC the player whose username is Aba
    """

    try:
        Constants.assert_command(client, arg, is_officer=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a target. Use /ooc_mute <ooc_name>.')

    targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, False)
    if not targets:
        raise ArgumentError('Targets not found. Use /ooc_mute <ooc_name>.')

    for c in targets:
        c.is_ooc_muted = True
        logger.log_server('OOC-muted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was OOC-muted.".format(c.name))

def ooc_cmd_ooc_unmute(client: ClientManager.Client, arg: str):
    """ (MOD AND CM ONLY)
    Unmutes a player from the OOC chat by their OOC username.
    Requires /ooc_mute to undo.
    Returns an error if no player has the given OOC username.

    SYNTAX
    /ooc_unmute <ooc_name>

    PARAMETERS
    <ooc_name>: Client OOC username

    EXAMPLE
    /ooc_unmute Aba         :: Unmutes from OOC the player whose username is Aba
    """

    try:
        Constants.assert_command(client, arg, is_officer=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a target. Use /ooc_unmute <ooc_name>.')

    targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, False)
    if not targets:
        raise ArgumentError('Target not found. Use /ooc_mute <ooc_name>.')

    for c in targets:
        c.is_ooc_muted = False
        logger.log_server('OOC-unmuted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was OOC-unmuted.".format(c.name))

def ooc_cmd_party(client: ClientManager.Client, arg: str):
    """
    Creates a party and makes you the leader of it. Party members will all move in groups
    automatically. It also returns a party ID players can use to join the party.
    Returns an error if the player is in area where the lights are off, if the server has
    reached its party limit, or if they are following someone.

    SYNTAX
    /party

    PARAMETERS
    None

    EXAMPLES
    /party      :: May return something like "You have created party 11037."
    """

    Constants.assert_command(client, arg, parameters='=0')

    if not client.is_staff() and client.is_blind:
        raise ClientError('You cannot create a party as you are blind.')
    if not client.area.lights:
        raise AreaError('You cannot create a party while the lights are off.')
    if client.following:
        raise PartyError('You cannot create a party while following someone.')

    party = client.server.party_manager.new_party(client, tc=True)
    client.send_ooc('You have created party {}.'.format(party.get_id()))
    client.send_ooc('Invite others to your party with /party_invite <user_id>')
    client.send_ooc_others('(X) {} [{}] has created party {} ({}).'
                           .format(client.displayname, client.id, party.get_id(), client.area.id),
                           is_zstaff_flex=True)

def ooc_cmd_party_disband(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Disbands your party if not given arguments, or (STAFF ONLY) disbands a party by party ID.
    Also sends notifications to the former members if you were visible.
    Returns an error for non-authorized users if they try to disband other parties or they are not
    a leader of their own party.

    SYNTAX
    /party_disband {party_id}

    OPTIONAL PARAMETERS
    {party_id}: Party to disband

    EXAMPLES
    If you were part of party 11037...
    /party_disband          :: Disbands party 11037
    /party_disband 11037    :: Disbands party 11037
    /party_disband 73011    :: Disbands party 73011
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='<2')
    except ClientError.UnauthorizedError:
        Constants.assert_command(client, arg, parameters='=0')

    if not arg:
        party = client.get_party()
    else:
        party = client.server.party_manager.get_party(arg)

    if not party.is_leader(client) and not client.is_staff():
        raise PartyError('You are not a leader of your party.')

    client.server.party_manager.disband_party(party)
    if arg:
        client.send_ooc('You have disbanded party {}.'.format(party.get_id()))
    else:
        client.send_ooc('You have disbanded your party.')

    culprit = client.displayname if not arg else 'A staff member'
    for x in party.get_members(uninclude={client}):
        if x.is_staff() or client.is_visible:
            x.send_ooc('{} has disbanded your party.'.format(culprit))

def ooc_cmd_party_id(client: ClientManager.Client, arg: str):
    """
    Obtains your party ID.
    Returns an error if you are not part of a party.

    SYNTAX
    /party_id

    PARAMETERS
    None

    EXAMPLES
    If you were part of party 11037...
    /party_id           :: May return something like "Your party ID is 11037".
    """

    Constants.assert_command(client, arg, parameters='=0')

    party = client.get_party(tc=True)
    client.send_ooc('Your party ID is: {}'.format(party.get_id()))

def ooc_cmd_party_invite(client: ClientManager.Client, arg: str):
    """
    Sends an invite to another player by client ID to join the party. The invitee will receive an
    OOC message with your name and party ID so they can join.
    The invitee must be in the same area as the player. If that is not the case (and the player
    used a client ID), but the invitee is in an area that can be reached by screams and is not
    deaf, they will receive a notification of the party invitation attempt, but will not be invited.
    Returns an error if you are not part of a party, you are not a party leader or staff member,
    if the player is not in the same area as you, or if the player is already invited.

    SYNTAX
    /party_invite <client_id>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    /party_invite 2         :: Invites the player with ID 2 to join your party.
    """

    Constants.assert_command(client, arg, parameters='=1')

    party = client.get_party(tc=True)
    if not party.is_leader(client) and not client.is_staff():
        raise PartyError('You are not a leader of your party.')

    c, _, _ = client.server.client_manager.get_target_public(client, arg)
    # Check if invitee is in the same area
    if c.area != party.area:
        if c.area.name in client.area.scream_range and not c.is_deaf:
            msg = ('You hear screeching of someone asking you to join their party but they seem '
                   'too far away to even care all that much.')
            c.send_ooc(msg)
        raise PartyError('The player is not in your area.')

    party.add_invite(c, tc=False)

    client.send_ooc('You have invited {} to join your party.'.format(c.displayname))
    for x in party.get_leaders(uninclude={client}):
        x.send_ooc('{} has invited {} to join your party.'
                   .format(client.displayname, c.displayname))
    c.send_ooc('{} has invited you to join their party {}.'
               .format(client.displayname, party.get_id()))
    c.send_ooc('Accept the invitation with /party_join {}'.format(party.get_id()))

def ooc_cmd_party_join(client: ClientManager.Client, arg: str):
    """
    Enrolls you into a party by party ID provided you were previously invited to it.
    Returns an error if you are already part of a party, if the party reached its maximum number
    of members, or if you are following someone.

    SYNTAX
    /party_join <party_id>

    PARAMETERS
    <party_id>: Party ID

    EXAMPLES
    /party_join 11037       :: If previously invited, you will join party 11037.
    """

    Constants.assert_command(client, arg, split_spaces=True, parameters='=1')
    if client.following:
        raise PartyError('You cannot join a party while following someone.')

    party = client.server.party_manager.get_party(arg)
    party.add_member(client, tc=True)

    client.send_ooc('You have joined party {}.'.format(party.get_id()))

    for c in party.get_members(uninclude={client}):
        if c.is_staff() or client.is_visible:
            c.send_ooc('{} has joined your party.'.format(client.displayname))

def ooc_cmd_party_kick(client: ClientManager.Client, arg: str):
    """
    Kicks a player by some ID off your party. Also sends a notification to party leaders and the
    target if you were visible.
    Returns an error if you are not a leader of your party or the target is not a member.

    SYNTAX
    /party_kick <client_id>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    /party_kick 2       :: Kicks the player with client ID 2 off your party.
    """

    Constants.assert_command(client, arg, parameters='=1')

    party = client.get_party()
    if not party.is_leader(client) and not client.is_staff():
        raise PartyError('You are not a leader of your party.')

    c, _, _ = client.server.client_manager.get_target_public(client, arg)
    if c == client:
        raise PartyError('You cannot kick yourself off your party.')

    party.remove_member(c)
    client.send_ooc('You have kicked {} off your party.'.format(c.displayname))
    if c.is_staff() or client.is_visible:
        c.send_ooc('{} has kicked you off your party.'.format(client.displayname))
    for x in party.get_leaders(uninclude={client}):
        if x.is_staff() or client.is_visible:
            x.send_ooc('{} has kicked {} off your party.'
                       .format(client.displayname, c.displayname))

def ooc_cmd_party_lead(client: ClientManager.Client, arg: str):
    """
    Sets you as leader of your party and announces all other party leaders of it. Party leaders
    can send invites to other players to join the party.
    Returns an error if you are not part of a party or you are already a leader.

    SYNTAX
    /party_lead

    PARAMETERS
    None

    EXAMPLES
    /party_lead         :: Sets you as leader of your party.
    """

    Constants.assert_command(client, arg, parameters='=0')

    party = client.get_party()
    party.add_leader(client, tc=True)
    client.send_ooc('You are now a leader of your party.')
    for c in party.get_leaders(uninclude={client}):
        if c.is_staff() or client.is_visible:
            c.send_ooc('{} is now a leader of your party.'.format(client.displayname))

def ooc_cmd_party_leave(client: ClientManager.Client, arg: str):
    """
    Makes you leave your current party. It will also notify all other remaining members if you were
    not sneaking. If instead you were the only member of the party, the party will be disbanded.
    Returns an error if you are not part of a party.

    SYNTAX
    /party_leave

    PARAMETERS
    None

    EXAMPLES
    /party_leave        :: Makes you leave your current party.
    """

    Constants.assert_command(client, arg, parameters='=0')

    party = client.get_party(tc=True)
    party.remove_member(client)

    client.send_ooc('You have left party {}.'.format(party.get_id()))

    for c in party.get_members(uninclude={client}):
        if c.is_staff() or client.is_visible:
            c.send_ooc('{} has left your party.'.format(client.displayname))

def ooc_cmd_party_list(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Lists all active parties in the server. Includes details such as: party ID, the number of
    members it has and its member limit, the area the party is at, and who are its leaders and
    regular members.
    Returns an error if there are no active parties.

    SYNTAX
    /party_list

    PARAMETERS
    None

    EXAMPLES
    /party_list         :: May return something like this:
    == Active parties ==
    *Party 11037 [2/7] (3). Leaders: Phantom_HD. Regular members: Spam_HD
    """

    Constants.assert_command(client, arg, parameters='=0', is_staff=True)

    info = '== Active parties =='
    for party in client.server.party_manager.get_parties():
        pid, area, player_limit, raw_leaders, raw_regulars = party.get_details()
        num_members = len(raw_leaders.union(raw_regulars))
        leaders = ', '.join([c.displayname for c in raw_leaders]) if raw_leaders else 'None'
        regulars = ', '.join([c.displayname for c in raw_regulars]) if raw_regulars else 'None'
        info += ('\r\n*Party {} [{}/{}] ({}). Leaders: {}. Regular members: {}.'
                 .format(pid, num_members, player_limit, area.id, leaders, regulars))
    client.send_ooc(info)

def ooc_cmd_party_members(client: ClientManager.Client, arg: str):
    """
    Obtains the leaders and regular members of your party. Any members that are sneaking will
    continue to appear in this list.
    Returns an error if you are not part of a party.

    SYNTAX
    /party_members

    PARAMETERS
    None

    EXAMPLES
    /party_members      :: May return something like this
    == Members of party 11037 ==
    *Leaders: Phantom_HD, Spam_HD
    *Members: Eggs_HD
    """

    Constants.assert_command(client, arg, parameters='=0')

    party = client.get_party(tc=True)
    regulars, leaders = party.get_members_leaders()
    regulars, leaders = sorted(regulars, key=lambda c: c.id), sorted(leaders, key=lambda c: c.id)
    info = '== Members of party {} =='.format(party.get_id())
    if leaders:
        names = ' '.join([f'[{c.id}] {c.displayname}' for c in leaders])
        info += '\r\n*Leaders: {}'.format(names)
    if regulars:
        names = ' '.join([f'[{c.id}] {c.displayname}' for c in regulars])
        info += '\r\n*Members: {}'.format(names)
    client.send_ooc(info)

def ooc_cmd_party_uninvite(client: ClientManager.Client, arg: str):
    """
    Revokes an invitation for a player by some ID to join your party. They will no longer be able
    to join your party until they are invited again.
    Returns an error if you are not part of a party, you are not a party leader or staff member, if
    the player is not invited, or if some ID other than client ID was used and the player is not in
    the area of the party.

    SYNTAX
    /party_uninvite <client_id>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    /party_uninvite 2       :: Revokes the invitation sent to player with ID 2 to join your party.
    """

    Constants.assert_command(client, arg, split_spaces=True, parameters='=1')

    party = client.get_party(tc=True)
    if not party.is_leader(client) and not client.is_staff():
        raise PartyError('You are not a leader of your party.')

    c, _, _ = client.server.client_manager.get_target_public(client, arg)
    party.remove_invite(c, tc=False)

    client.send_ooc('You have uninvited {} to join your party.'.format(c.displayname))
    for x in party.get_leaders(uninclude={client}):
        x.send_ooc('{} has uninvited {} to join your party.'
                   .format(client.displayname, c.displayname))
    c.send_ooc('{} has revoked your invitation to join their party {}.'
               .format(client.displayname, party.get_id()))

def ooc_cmd_party_unlead(client: ClientManager.Client, arg: str):
    """
    Removes your party leader role and announces all other party leaders of it. If a party has no
    leaders, all leader functions are available to all members.
    Returns an error if you are not part of a party or you are not a leader of your party.

    SYNTAX
    /party_unlead

    PARAMETERS
    None

    EXAMPLES
    /party_unlead       :: Removes your party leader role.
    """

    Constants.assert_command(client, arg, parameters='=0')

    party = client.get_party()
    party.remove_leader(client, tc=True)
    client.send_ooc('You are no longer a leader of your party.')
    for x in party.get_leaders(uninclude={client}):
        if x.is_staff() or client.is_visible:
            x.send_ooc('{} is no longer a leader of your party.'.format(client.displayname))

def ooc_cmd_passage_clear(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Clears all the passage locks that start in the areas between two given ones by name or ID, or
    does that only to the given area if not given any. In particular, players in any of the affected
    areas will be able to freely move to any other from the area they were in.
    Note that, as passages are unidirectional, passages from areas outside the given range that end
    in an area that is in the range will be conserved.

    SYNTAX
    /passage_clear
    /passage_clear <area_range_start>, <area_range_end>

    PARAMETERS
    <area_range_start>: Start of area range (inclusive)
    <area_range_end>: End of area range (inclusive)

    EXAMPLES
    Assuming the player is in area 0...
    /passage_clear                :: Clears the passages starting in area 0.
    /passage_clear 16, 116        :: Restores the passages starting in areas 16 through 116.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='<3', split_commas=True)

    areas = Constants.parse_two_area_names(client, arg.split(', '))

    for i in range(areas[0].id, areas[1].id+1):
        area = client.server.area_manager.get_area_by_id(i)
        area.reachable_areas = {'<ALL>'}

    if areas[0] == areas[1]:
        client.send_ooc('Area passage locks have been removed in {}.'.format(areas[0].name))
    else:
        client.send_ooc('Area passage locks have been removed in areas {} through {}'
                        .format(areas[0].name, areas[1].name))

def ooc_cmd_passage_restore(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Restores the passages in the areas between two given ones by name or ID to their original state
    when the areas were loaded, or does that to the current area if not given any.
    Note that, as passages are unidirectional, passages from areas outside the given range that end
    in an area that is in the range will be conserved.

    SYNTAX
    /passage_restore
    /passage_restore <area_range_start>, <area_range_end>

    PARAMETERS
    <area_range_start>: Start of area range (inclusive)
    <area_range_end>: End of area range (inclusive)

    EXAMPLES
    Assuming the player is in area 0...
    /passage_restore                :: Restores the passages starting in area 0 to default.
    /passage_restore 16, 116        :: Restores the passages starting in areas 16 through 116.
    """

    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    areas = arg.split(', ')
    if len(areas) > 2:
        raise ClientError('This command takes at most two arguments.')

    areas = Constants.parse_two_area_names(client, areas)

    for i in range(areas[0].id, areas[1].id+1):
        area = client.server.area_manager.get_area_by_id(i)
        area.reachable_areas = set(list(area.default_reachable_areas)[:])
        area.change_reachability_allowed = area.default_change_reachability_allowed

    if areas[0] == areas[1]:
        client.send_ooc('Passages in this area have been restored to their original state.')
    else:
        client.send_ooc('Passages in areas {} through {} have been restored to their original '
                        'state.'.format(areas[0].name, areas[1].name))

def ooc_cmd_ping(client: ClientManager.Client, arg: str):
    """
    Returns "Pong" and nothing else. Useful to check if the player has lost connection.

    SYNTAX
    /ping

    PARAMETERS

    EXAMPLES
    /ping               :: Returns "Pong"
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.send_ooc('Pong.')

def ooc_cmd_play(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Plays a given track, even if not explicitly in the music list. It is the way to play custom
    music. If the area parameter 'song_switch_allowed' is set to true, anyone in the area can use
    this command even if they are not logged in.

    SYNTAX
    /play <track_name>

    PARAMETERS:
    <track_name>: Track to play

    EXAMPLES:
    /play Trial(AJ).mp3         :: Plays Trial(AJ).mp3
    /play CustomTrack.mp3       :: Plays CustomTrack.mp3 (will only be audible to users with CustomTrack.mp3)
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>0')
    except ClientError.UnauthorizedError:
        if not client.area.song_switch_allowed:
            raise
    except ArgumentError:
        raise ArgumentError('You must specify a song.')

    client.area.play_track(arg, client, raise_if_not_found=False, reveal_sneaked=False)

    client.send_ooc('You have played track `{}` in your area.'
                    .format(arg))
    client.send_ooc_others('(X) {} [{}] has played track `{}` in your area.'
                           .format(client.displayname, client.id, arg),
                           is_zstaff_flex=True, in_area=True)

    # Warn if track is not in the music list
    try:
        client.server.get_song_data(arg, c=client)
    except ServerError.MusicNotFoundError:
        client.send_ooc(f'(X) Warning: `{arg}` is not a recognized track name, so it will not '
                        'loop.')

def ooc_cmd_pm(client: ClientManager.Client, arg: str):
    """
    Sends a personal message to a specified user.
    Returns an error if the user could not be found, if the user or target muted PMs, or if
    multiple users match the given identifier.

    SYNTAX
    /pm <user_id> <message>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.
    <message>: Message to be sent.

    EXAMPLES
    /pm Santa What will I get for Christmas?    :: Sends that message to the user whose OOC name is Santa.
    /pm 0 Nothing                               :: Sends that message to the user whose client ID is 0.
    /pm Santa_HD Sad                            :: Sends that message to the user whose character name is Santa_HD.
    """

    try:
        Constants.assert_command(client, arg, parameters='>1')
    except ArgumentError:
        raise ArgumentError('Not enough arguments. Use /pm <target> <message>. Target should be '
                            'ID, char-name, edited-to character, custom showname or OOC-name.')
    if client.pm_mute:
        raise ClientError('You have muted all PM conversations.')

    cm = client.server.client_manager
    target, recipient, msg = cm.get_target_public(client, arg)

    # Attempt to send the message to the target, provided they do not have PMs disabled.
    if target.pm_mute:
        raise ClientError('This user muted all PM conversations.')

    client.send_ooc('PM sent to {}. Message: {}'.format(recipient, msg))
    target.send_ooc('PM from {} in {} ({}): {}'
                    .format(client.name, client.area.name, client.displayname, msg))

def ooc_cmd_poison(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Poisons the target with some of three effects (blindness, deafened or gagged) that kick in
    a specified length of time. Multiple effects can be used within the same poison.
    If the target is already subject to some poison, stack them together as follows:
     For each effect in the new poison:
     * If the target's current poison does not include the effect, poison the target such that the
       effect kicks in the new poison's established length.
     * Otherwise, poison the target such that the effect kicks in the new poison's established
       length or the remaining length of the old poison, whichever is shorter.
    If for some effect of the poison the target is already subject to it after its time expires
    (which would happen if some staff manually sets it in), do nothing for that effect.
    Returns an error if the given identifier does not correspond to a user, if the length is not a
    positive number or exceeds the server time limit, or if the effects contain an unrecognized or
    repeated character.

    SYNTAX
    /poison <client_id> <effects> <length>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <effects>: Effects to apply with the current poison (a string consisting of non-case-sensitive
    'b', 'd', and/or 'g' in some order corresponding to the initials of the supported effects)
    <length>: Time to wait before the effects take place (in seconds)

    EXAMPLES
    Assuming these are run immediately one after the other:
    /poison 1 b 10      :: Poisons client 1 with a poison that in 10 seconds will turn them blind.
    /poison 1 bD 8      :: Poisons client 1 with a poison that in 8 seconds will turn them blind and deafened (old poison discarded)
    /poison 1 Dg 15     :: Poisons client 1 with a poison that in 8 seconds will turn them gagged in 15 seconds (old deafened poison of 8 seconds remains)
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=3')
    raw_target, raw_effects, raw_length = arg.split(' ')
    target = Constants.parse_id(client, raw_target)
    effects = Constants.parse_effects(client, raw_effects)
    length = Constants.parse_time_length(raw_length)

    effect_results = target.set_timed_effects(effects, length)
    target_message = ''
    self_message = ''
    zstaff_message = ''

    for effect_name in sorted(effect_results.keys()):
        effect_length, effect_reapplied = effect_results[effect_name]
        formatted_effect_length = Constants.time_format(effect_length)

        if effect_length == length and not effect_reapplied:
            target_message = ('{}\r\n*{}: acts in {}.'
                              .format(target_message, effect_name, formatted_effect_length))
            self_message = ('{}\r\n*{}: acts in {}.'
                            .format(self_message, effect_name, formatted_effect_length))
            zstaff_message = ('{}\r\n*{}: acts in {}.'
                              .format(zstaff_message, effect_name, formatted_effect_length))
        elif effect_length == length and effect_reapplied:
            # The new effect time was lower than the remaining time for the current effect
            target_message = ('{}\r\n*{}: now acts in {}.'
                              .format(target_message, effect_name, formatted_effect_length))
            self_message = ('{}\r\n*{}: now acts in {}.'
                            .format(self_message, effect_name, formatted_effect_length))
            zstaff_message = ('{}\r\n*{}: now acts in {}.'
                              .format(zstaff_message, effect_name, formatted_effect_length))
        else:
            target_message = ('{}\r\n*{}: still acts in {}.'
                              .format(target_message, effect_name, formatted_effect_length))
            self_message = ('{}\r\n*{}: still acts in {} (remaining effect time shorter than new '
                            'length).'.format(self_message, effect_name, formatted_effect_length))
            zstaff_message = ('{}\r\n*{}: still acts in {} (remaining time shorter than new '
                              'length).'.format(zstaff_message, effect_name,
                                                formatted_effect_length))

    if target != client:
        target.send_ooc('You were poisoned. The following effects will apply shortly: {}'
                        .format(target_message))
        client.send_ooc('You poisoned {} with the following effects: {}'
                        .format(target.displayname, self_message))
        client.send_ooc_others('(X) {} [{}] poisoned {} with the following effects ({}): {}'
                               .format(client.displayname, client.id, target.displayname,
                                       client.area.id, zstaff_message),
                               is_zstaff_flex=True, not_to={target})
    else:
        client.send_ooc('You poisoned yourself with the following effects: {}'
                        .format(self_message))
        client.send_ooc_others('(X) {} [{}] poisoned themselves with the following effects ({}): {}'
                               .format(client.displayname, client.id, client.area.id,
                                       zstaff_message),
                               is_zstaff_flex=True)

def ooc_cmd_pos(client: ClientManager.Client, arg: str):
    """
    Switches the character to the given position, or to its original position if not given one.
    Returns an error if position is invalid.

    SYNTAX
    /pos {new_position}

    OPTIONAL PARAMETERS
    {new_position}: New character position (jud, def, pro, hlp, hld)

    EXAMPLES
    /pos jud                :: Switches to the judge position
    /pos                    :: Resets to original position
    """

    # Resetting to original position
    if len(arg) == 0:
        client.change_position()
        client.send_ooc('Position reset.')

    # Switching position
    else:
        client.change_position(arg)
        client.area.broadcast_evidence_list()
        client.send_ooc('Position changed.')

def ooc_cmd_randomchar(client: ClientManager.Client, arg: str):
    """
    Switches the user to a random character.
    Returns an error if new character is available.

    SYNTAX
    /randomchar

    PARAMETERS
    None

    EXAMPLE
    /randomchar
    """

    Constants.assert_command(client, arg, parameters='=0')

    free_id = client.area.get_rand_avail_char_id(allow_restricted=client.is_staff())
    client.change_character(free_id)
    client.send_ooc('Randomly switched to `{}`.'.format(client.get_char_name()))

def ooc_cmd_refresh(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Reloads the following files for the server: characters, default music list, and background list.

    SYNTAX
    /refresh

    PARAMETERS
    None

    EXAMPLE
    /refresh
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    client.server.reload()
    client.send_ooc('You have reloaded the server.')

def ooc_cmd_reload(client: ClientManager.Client, arg: str):
    """
    Reloads the character for the current user (equivalent to switching to the current character).

    SYNTAX
    /reload

    PARAMETERS
    None

    EXAMPLE
    /reload
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.reload_character()
    client.send_ooc('Character reloaded.')

def ooc_cmd_reload_commands(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Reloads the commands.py file. Use only if restarting is not a viable option.
    Note that this ONLY updates the contents of this file. If anything you update relies on other
    files (for example, you call a method in client_manager), they will still use the old contents,
    regardless of whatever changes you may have made to the other files.

    SYNTAX
    /reload_commands

    PARAMETERS
    None

    EXAMPLE
    /reload_commands
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    outcome = client.server.reload_commands()
    if outcome:
        info = "\n{}: {}".format(type(outcome).__name__, outcome)
        raise ClientError('Server ran into a problem while reloading the commands: {}'.format(info))

    client.send_ooc("The commands have been reloaded.")

def ooc_cmd_remove_h(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes all letter H's from all IC and OOC messages of a player by client ID (number in
    brackets) or IPID (number in parentheses).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Requires /unremove_h to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /remove_h <client_id>
    /remove_h <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /remove_h 1           :: Has all messages sent by the player whose client ID is 1 have their H's removed.
    /remove_h 1234567890  :: Has all messages sent by all clients opened by the user whose IPID is 1234567890 have their H's removed.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Removes H's to matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.remove_h = True
        logger.log_server('Removing h from {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("Removed h from {}.".format(c.displayname))

def ooc_cmd_reveal(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Sets given user based on client ID or IPID to no longer be sneaking so that they are visible
    through /getarea(s).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Search by IPID can only be performed by CMs and mods.
    Requires /sneak to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /reveal <client_id>
    /reveal <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /reveal 1                     :: Set client whose ID is 1 to no longer be sneaking.
    /reveal 1234567890            :: Set all clients opened by the user whose IPID is 1234567890 to no longer be sneaking.
    """

    Constants.assert_command(client, arg, is_staff=True)

    # Unsneak matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        if c != client:
            client.send_ooc("{} is no longer sneaking.".format(c.displayname))
        c.change_visibility(True)
        client.send_ooc_others('(X) {} [{}] revealed {} ({}).'
                               .format(client.displayname, client.id, c.displayname, c.area.id),
                               not_to={c}, is_zstaff=True)

def ooc_cmd_roll(client: ClientManager.Client, arg: str):
    """
    Rolls a given number of dice with given number of faces and modifiers. If certain parameters
    are not given, command assumes preset defaults. The result is broadcast to all players in the
    area as well as staff members who have turned foreign roll notifications with /toggle_allrolls.
    The roll is also logged in the client's and area's dice log.
    Returns an error if parameters exceed specified constants or an invalid mathematical operation
    is put as a modifier.

    For modifiers, the modifier's result will ignore the given number of faces cap and instead use
    NUMFACES_MAX (so dice rolls can exceed number of faces). However, the modifier's result is
    bottom capped at 1 (so non-positive values are not allowed). Modifiers follow PEMDAS, and if
    not given the dice result (character "r"), will try and perform the operation directly.

    SYNTAX
    /roll {num_faces} {modifier}
    /roll {num_dice}d<num_faces> {modifier}

    OPTIONAL PARAMETERS
    {num_faces}: Number of faces the dice will have (capped at NUMFACES_MAX).
    {num_dice}: Number of dice to roll (capped at NUMDICE_MAX).
    {modifier}: Operation to perform on rolls.

    EXAMPLES
    Assuming DEF_NUMDICE = 1, DEF_NUMFACES = 6, DEF_MODIFIER = ''...
    /roll               :: Rolls a d6.
    /roll 20            :: Rolls a d20.
    /roll 5d30          :: Rolls 5 d30's.
    /roll d20 +3        :: Rolls a d20 and adds 3 to the result.
    /roll 1d20 +3*2     :: Rolls a d20 and adds 3*2=6 to the result.
    /roll 6 -1+3*r      :: Rolls a d6, multiplies the result by 3 and subtracts 1 to it.
    /roll 3d6 (-1+3)*r  :: Rolls 3 d6's and multiplies each result by 2.
    """

    roll_result, num_faces = Constants.dice_roll(arg, 'roll', client.server)
    roll_message = 'rolled {} out of {}'.format(roll_result, num_faces)
    client.send_ooc('You {}.'.format(roll_message))
    client.send_ooc_others('{} {}.'.format(client.displayname, roll_message), in_area=True)
    client.send_ooc_others('(X) {} [{}] {} in {} ({}).'
                           .format(client.displayname, client.id, roll_message,
                                   client.area.name, client.area.id),
                           is_zstaff_flex=client.area, in_area=False,
                           pred=lambda c: c.get_foreign_rolls)
    client.add_to_dicelog(roll_message + '.')
    client.area.add_to_dicelog(client, roll_message + '.')
    logger.log_server('[{}][{}]Used /roll and got {} out of {}.'
                      .format(client.area.id, client.get_char_name(), roll_result, num_faces), client)

def ooc_cmd_rollp(client: ClientManager.Client, arg: str):
    """
    Similar to /roll, but instead announces roll results (and who rolled) only to yourself and
    staff members who are in the area or who have foreign roll notifications with /toggle_allrolls.
    The roll is also logged in the client's and area's dice log, but marked as private.
    Returns an error if current area does not authorize /rollp and user is not logged in.

    SYNTAX
    /rollp {num_faces} {modifier}
    /rollp {num_dice}d<num_faces> {modifier}

    OPTIONAL PARAMETERS
    {num_faces}: Number of faces the dice will have (capped at NUMFACES_MAX).
    {num_dice}: Number of dice to roll (capped at NUMDICE_MAX).
    {modifier}: Operation to perform on rolls.

    EXAMPLES
    Assuming DEF_NUMDICE = 1, DEF_NUMFACES = 6, DEF_MODIFIER = ''...
    /rollp               :: Rolls a d6.
    /rollp 20            :: Rolls a d20.
    /rollp 5d30          :: Rolls 5 d30's.
    /rollp d20 +3        :: Rolls a d20 and adds 3 to the result.
    /rollp 1d20 +3*2     :: Rolls a d20 and adds 3*2=6 to the result.
    /rollp 6 -1+3*r      :: Rolls a d6, multiplies the result by 3 and subtracts 1 to it.
    /rollp 3d6 (-1+3)*r  :: Rolls 3 d6's and multiplies each result by 2.
    """

    if not client.area.rollp_allowed and not client.is_staff():
        raise ClientError('This command has been restricted to authorized users only in this area.')

    roll_result, num_faces = Constants.dice_roll(arg, 'rollp', client.server)
    roll_message = 'privately rolled {} out of {}'.format(roll_result, num_faces)
    client.send_ooc('You {}.'.format(roll_message))
    client.send_ooc_others('Someone rolled.', is_zstaff_flex=False, in_area=True)
    client.send_ooc_others('(X) {} [{}] {}.'.format(client.displayname, client.id, roll_message),
                           is_zstaff_flex=True, in_area=True)
    client.send_ooc_others('(X) {} [{}] {} in {} ({}).'
                           .format(client.displayname, client.id, roll_message, client.area.name,
                                   client.area.id),
                           is_zstaff_flex=client.area, in_area=False,
                           pred=lambda c: c.get_foreign_rolls)

    client.add_to_dicelog(roll_message + '.')
    client.area.add_to_dicelog(client, roll_message + '.')

    SALT = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    encoding = hashlib.sha1((str(roll_result) + SALT).encode('utf-8')).hexdigest() + '|' + SALT
    logger.log_server('[{}][{}]Used /rollp and got {} out of {}.'
                      .format(client.area.id, client.get_char_name(), encoding, num_faces), client)

def ooc_cmd_rplay(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Plays a given track in currently reachable areas, even if not explicitly in the music list.
    It is the way to play custom music in multiple areas.

    SYNTAX
    /rplay <track_name>

    PARAMETERS
    <track_name>: Track to play

    EXAMPLES
    /rplay Trial(AJ).mp3         :: Plays Trial(AJ).mp3
    /rplay CustomTrack.mp3       :: Plays CustomTrack.mp3 (will only be audible to users with CustomTrack.mp3)
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a song.')

    if client.area.reachable_areas == '<ALL>':
        areas = set(client.area.areas)
    else:
        areas = {client.server.area_manager.get_area_by_name(reachable_area_name)
                 for reachable_area_name in client.area.reachable_areas}

    for area in areas:
        area.play_track(arg, client, raise_if_not_found=False, reveal_sneaked=False)

    client.send_ooc('You have played track `{}` in the areas reachable from your area.'
                    .format(arg))
    client.send_ooc_others('(X) {} [{}] has played track `{}` in the areas reachable from your '
                           'area.'
                           .format(client.displayname, client.id, arg),
                           is_zstaff_flex=True, in_area=True)
    client.send_ooc_others('(X) {} [{}] has played track `{}` in the areas reachable from area '
                           '{}, which included your area.'
                           .format(client.displayname, client.id, arg, client.area.name),
                           is_zstaff_flex=True, in_area=areas-{client.area})

    # Warn if track is not in the music list
    try:
        client.server.get_song_data(arg, c=client)
    except ServerError.MusicNotFoundError:
        client.send_ooc(f'(X) Warning: `{arg}` is not a recognized track name, so it will not '
                        'loop.')

def ooc_cmd_rpmode(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles RP mode on/off in the server. If turned on, all non-logged in users will be subject to
    RP rules. Some effects include: unable to use /getarea and /getareas in areas that disable it.

    SYNTAX
    /rpmode <new_status>

    PARAMETERS
    <new_status>: 'on' or 'off'

    EXAMPLES
    /rpmode on              :: Turns on RP mode
    /rpmode off             :: Turns off RP mode
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='=1')
    except ArgumentError:
        raise ArgumentError('You must specify either on or off.')
    if not client.server.config['rp_mode_enabled']:
        raise ClientError("RP mode is disabled in this server.")
    if len(arg) == 0:
        raise ArgumentError('You must specify either on or off.')

    if arg == 'on':
        client.server.rp_mode = True
        for c in client.server.client_manager.clients:
            c.send_ooc('RP mode enabled.')
            if not c.is_staff():
                c.in_rp = True
    elif arg == 'off':
        client.server.rp_mode = False
        for c in client.server.client_manager.clients:
            c.send_ooc('RP mode disabled.')
            c.in_rp = False
    else:
        client.send_ooc('Expected on or off.')

def ooc_cmd_scream(client: ClientManager.Client, arg: str):
    """
    Sends a message in the OOC chat visible to all staff members and non-deaf users that are in an
    area whose screams are reachable from the sender's area. It also sends an IC message with the
    scream message.
    If the user is gagged, a special message is instead sent to non-deaf players in the same area.
    If a recipient is deaf, they receive a special OOC message and a blank IC message.
    Staff always get normal messages.
    Returns an error if the user has global chat off or sends an empty message.

    SYNTAX
    /scream <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /scream Hello World      :: Sends Hello World to users in scream reachable areas+staff.
    """

    arg = arg[:256] # Cap
    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You cannot send an empty message.')
    if client.muted_global:
        raise ClientError('You have the global chat muted.')

    if not client.is_gagged:
        client.send_ooc('You screamed "{}".'.format(arg))

        client.send_ooc_others(msg="You heard {} scream nearby.".format(client.displayname),
                               is_zstaff_flex=False, to_deaf=False,
                               pred=lambda c: (not c.muted_global and
                                               (c.area == client.area or
                                                c.area.name in client.area.scream_range)))
        client.send_ooc_others('(X) {} [{}] screamed "{}" ({}).'
                               .format(client.displayname, client.id, arg, client.area.id),
                               is_zstaff_flex=True, pred=lambda c: not c.muted_global)

        client.send_ic(msg=arg, pos=client.pos, cid=client.char_id, showname=client.showname)
        client.send_ic_others(msg=arg, to_deaf=False, showname=client.showname,
                              pred=lambda c: (not c.muted_global and
                                              (c.area == client.area or
                                               c.area.name in client.area.scream_range)))
        client.send_ic_others(msg=arg, to_deaf=True,
                              pred=lambda c: (not c.muted_global and
                                              (c.area == client.area or
                                               c.area.name in client.area.scream_range)))
    else:
        client.send_ooc('You attempted to scream but you have no mouth.')
        client.send_ooc_others('You hear some grunting noises.', is_zstaff_flex=False,
                               to_deaf=False, in_area=True, pred=lambda c: not c.muted_global)
        # Deaf players get no notification on a gagged player screaming
        client.send_ooc_others('(X) {} [{}] attempted to scream "{}" while gagged ({}).'
                               .format(client.displayname, client.id, arg, client.area.id),
                               is_zstaff_flex=True, pred=lambda c: not c.muted_global)

    logger.log_server('[{}][{}][SCREAM]{}.'.format(client.area.id, client.get_char_name(), arg),
                      client)

def ooc_cmd_scream_range(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Returns the current area's scream range (i.e. users in which areas who would hear a /scream from
    the current area).

    SYNTAX
    /scream_range

    PARAMETERS
    None

    EXAMPLES
    /scream_range           :: Obtain the current area's scream range, for example {'Basement'}
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    info = '== Areas in scream range of area {} =='.format(client.area.name)
    # If no areas in scream range, print a manual message.
    if len(client.area.scream_range) == 0:
        info += '\r\n*No areas.'
    # Otherwise, build the list of all areas.
    else:
        for area in client.area.scream_range:
            info += '\r\n*({}) {}'.format(client.server.area_manager.get_area_by_name(area).id, area)

    client.send_ooc(info)

def ooc_cmd_scream_set(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles the ability of ONE given area by name or ID to hear a scream from the current area on
    or off. This only modifies the given area's status in the current area's scream range, unlike
    /scream_set_range. Note that scream ranges are unidirectional, so if you want two areas to hear
    one another, you must use this command twice.
    Returns an error if an invalid area name or area ID is given, or if the current area is the
    target of the selection.

    SYNTAX
    /scream_set <target_area>

    PARAMETERS
    <target_area>: The area whose ability to hear screams from the current area must be switched.

    EXAMPLES
    Assuming Area 2: Class Trial Room, 2 starts as not part of the current area's (say Basement) scream range...
    /scream_set Class Trial Room,\ 2 :: Adds "Class Trial Room, 2" to the scream range of Basement (note the \ escape character)-
    /scream_set 2                    :: Removes "Class Trial Room, 2" from the scream range of Basement.
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=1')

    # This should just return a list with one area
    intended_area = Constants.parse_area_names(client, arg.split(', '))
    if len(intended_area) > 1:
        raise ArgumentError('This command takes one area name (did you mean /scream_set_range ?).')

    intended_area = intended_area[0] # Convert the one element list into the area name
    if intended_area == client.area:
        raise ArgumentError('You cannot add or remove the current area from the scream range.')

    # If intended area not in range, add it
    if intended_area.name not in client.area.scream_range:
        client.area.scream_range.add(intended_area.name)
        client.send_ooc('Added area {} to the scream range of area {}.'
                        .format(intended_area.name, client.area.name))
        client.send_ooc_others('(X) {} [{}] added area {} to the scream range of area {} ({}).'
                               .format(client.displayname, client.id, intended_area.name,
                                       client.area.name, client.area.id), is_zstaff_flex=True)
        logger.log_server('[{}][{}]Added area {} to the scream range of area {}.'
                          .format(client.area.id, client.get_char_name(), intended_area.name,
                                  client.area.name), client)
    else: # Otherwise, add it
        client.area.scream_range.remove(intended_area.name)
        client.send_ooc('Removed area {} from the scream range of area {}.'
                        .format(intended_area.name, client.area.name))
        client.send_ooc_others('(X) {} [{}] removed area {} from the scream range of area {} ({}).'
                               .format(client.displayname, client.id, intended_area.name,
                                       client.area.name, client.area.id), is_zstaff_flex=True)
        logger.log_server('[{}][{}]Removed area {} from the scream range of area {}.'
                          .format(client.area.id, client.get_char_name(), intended_area.name,
                                  client.area.name), client)

def ooc_cmd_scream_set_range(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sets the current area's scream range to a given list of areas by name or ID separated by commas.
    This completely overrides the old scream range, unlike /scream_set.
    Passing in no arguments sets the scream range to nothing (i.e. a soundproof room).
    Note that scream ranges are unidirectional, so if you want two areas to hear one another, you
    must use this command twice.
    Returns an error if an invalid area name or area ID is given, or if the current area is part of
    the selection.

    SYNTAX
    /scream_set_range {area_1}, {area_2}, {area_3}, ...

    PARAMETERS
    {area_n}: An area to add to the current scream range. Can be either an area name or area ID.

    EXAMPLES:
    Assuming the current area is Basement...
    /scream_set_range Class Trial Room 3                            :: Sets Basement's scream range to "Class Trial Room 3"
    /scream_set_range Class Trial Room,\ 2, 1, Class Trial Room 3   :: Sets Basement's scream range to "Class Trial Room, 2" (note the \ escape character"), area 1 and "Class Trial Room 3".
    /scream_set_range                                               :: Sets Basement's scream range to no areas.
    """

    Constants.assert_command(client, arg, is_staff=True)

    if len(arg) == 0:
        client.area.scream_range = set()
        area_names = '{}'
    else:
        areas = Constants.parse_area_names(client, arg.split(', '))
        if client.area in areas:
            raise ArgumentError('You cannot add the current area to the scream range.')
        area_names = {area.name for area in areas}
        client.area.scream_range = area_names

    client.send_ooc('Set the scream range of area {} to be: {}.'
                    .format(client.area.name, area_names))
    client.send_ooc_others('(X) {} [{}] set the scream range of area {} to be: {} ({}).'
                           .format(client.displayname, client.id, client.area.name, area_names,
                                   client.area.id), is_zstaff_flex=True)
    logger.log_server('[{}][{}]Set the scream range of area {} to be: {}.'
                      .format(client.area.id, client.get_char_name(), client.area.name, area_names), client)

def ooc_cmd_shoutlog(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    List the last 20 shouts performed in the current area (Hold it, Objection, Take That, etc.).
    If given an argument, it will return the shoutlog of the given area by ID or name.
    Otherwise, it will obtain the one from the current area.
    Returns an error if the given identifier does not correspond to an area.

    SYNTAX
    /shoutlog {target_area}

    OPTIONAL PARAMETERS
    {target_area}: area whose shoutlog will be returned (either ID or name)

    EXAMPLE
    If currently in the Basement (area 0)...
    /shoutlog           :: You may get something like the next example
    /shoutlog 0         :: You may get something like this

    == Shout log of Basement (0) ==
    *Sat Jun 29 13:15:56 2019 | [1] Phantom (1234567890) used shout 1 with the message: I consent
    *Sat Jun 29 13:16:41 2019 | [1] Phantom (1234567890) used shout 3 with the message: u wrong m9
    """

    Constants.assert_command(client, arg, is_staff=True)
    if len(arg) == 0:
        arg = client.area.name

    # Obtain matching area's shoutlog
    for area in Constants.parse_area_names(client, [arg]):
        info = area.get_shoutlog()
        client.send_ooc(info)

def ooc_cmd_showname(client: ClientManager.Client, arg: str):
    """
    If given an argument, sets the client's showname to that. Otherwise, it clears their showname
    to use the default setting (character showname). These custom shownames override whatever client
    showname the current character has, and is persistent between between character swaps, area
    changes, etc.
    Returns an error if new custom showname exceeds the server limit (server parameter
    'showname_max_length', is already used in the current area, or if shownames have been frozen
    and the user is not logged in.

    SYNTAX
    /showname <new_showname>
    /showname

    PARAMETERS
    <new_showname>: New desired showname.

    EXAMPLES
    /showname Phantom       :: Sets your showname to Phantom
    /showname               :: Clears your showname
    """

    if client.server.showname_freeze and not client.is_staff():
        raise ClientError('Shownames are frozen.')

    old_showname = client.showname
    try:
        client.change_showname(arg, forced=False)
    except ValueError:
        raise ClientError('Given showname `{}` is already in use in this area.'.format(arg))

    if arg:
        s_message = 'You have set your showname to `{}`.'.format(arg)
        if old_showname:
            w_message = ('(X) Client {} changed their showname from `{}` to `{}` in your zone ({}).'
                         .format(client.id, old_showname, client.showname, client.area.id))
        else:
            w_message = ('(X) Client {} set their showname to `{}` in your zone ({}).'
                         .format(client.id, client.showname, client.area.id))
        l_message = '{} set their showname to `{}`.'.format(client.ipid, arg)
    else:
        s_message = 'You have removed your showname.'
        w_message = ('(X) Client {} removed their showname `{}` in your zone ({}).'
                         .format(client.id, old_showname, client.area.id))
        l_message = '{} removed their showname.'.format(client.ipid)

    client.send_ooc(s_message)
    client.send_ooc_others(w_message, is_zstaff=True)
    logger.log_server(l_message, client)

def ooc_cmd_showname_area(client: ClientManager.Client, arg: str):
    """
    List the characters (and associated client IDs) in the current area, as well as their custom
    shownames if they have one in parentheses.
    OR (STAFF ONLY) lists the character (and associated client IDs) in the given area by ID or name.
    as well as their custom shownames if they have one in parentheses.
    Returns an error if the user is subject to RP mode and is in an area that disables /getarea, if
    they are blind and not staff, or if the given identifier does not correspond to an area.

    SYNTAX
    /showname_area
    /showname_area <target_area>

    PARAMETERS
    <target_area>: The area whose characters will be listed. By default it is the user's area.

    EXAMPLE
    If Phantom is in area 0
    /showname_area          :: May list something like this

    == Area 0: Basement ==
    [0] Phantom_HD
    [1] Spam_HD (Spam, Spam, Spam...)

    /showname_area Courtroom    :: May list something like this

    == Area 8: Courtroom ==
    [2] Eggs_HD (Eggy Egg)
    [3] Judge_HD (Gavel Guy)
    """

    if arg:
        if not client.is_staff():
            raise ClientError.UnauthorizedError('You must be authorized to use the one-parameter '
                                                'version of this command.')
        else:
            area_id = Constants.parse_area_names(client, [arg])[0].id
    else:
        area_id = client.area.id

    if not client.is_staff() and client.is_blind:
        raise ClientError('You are blind, so you cannot see anything.')

    client.send_area_info(client.area, area_id, False, include_shownames=True)

def ooc_cmd_showname_areas(client: ClientManager.Client, arg: str):
    """
    List the characters (and associated client IDs) in each area, as well as their custom shownames
    if they have one in parentheses.
    Returns an error if the user is subject to RP mode and is in an area that disables /getareas
    or if they are blind.

    SYNTAX
    /showname_areas

    PARAMETERS
    None

    EXAMPLE
    /showname_areas          :: May list something like this

    == Area List ==
    == Area 0: Basement ==
    [0] Phantom_HD
    [1] Spam_HD (Spam, Spam, Spam...)
    == Area 1: Class Trial Room 1 ==
    [2] Eggs_HD (Not Spam?)
    """

    Constants.assert_command(client, arg, parameters='=0')
    if not client.is_staff() and client.is_blind:
        raise ClientError('You are blind, so you cannot see anything.')

    client.send_area_info(client.area, -1, False, include_shownames=True)

def ooc_cmd_showname_freeze(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Toggles non-staff members being able to use /showname or not.
    It does NOT clear their shownames (see /showname_nuke).
    Staff can still use /showname_set to set shownames of others.

    SYNTAX
    /showname_freeze

    PARAMETERS
    None

    EXAMPLE
    Assuming shownames are not frozen originally...
    /showname_freeze        :: Freezes all shownames. Only staff members can change or remove them.
    /showname_freeze        :: Unfreezes all shownames. Everyone can use /showname again.
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    client.server.showname_freeze = not client.server.showname_freeze
    status = {False: 'unfrozen', True: 'frozen'}

    client.send_ooc('You have {} all shownames.'.format(status[client.server.showname_freeze]))
    client.send_ooc_others('A mod has {} all shownames.'
                           .format(status[client.server.showname_freeze]), is_officer=False)
    client.send_ooc_others('{} [{}] has {} all shownames.'
                           .format(client.name, client.id, status[client.server.showname_freeze]),
                           is_officer=True)
    logger.log_server('{} has {} all shownames.'
                      .format(client.name, status[client.server.showname_freeze]), client)

def ooc_cmd_showname_history(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    List all shownames a client by ID or IPID has had during the session. Output differentiates
    between self-initiated showname changes (such as the ones via /showname) by using "Self"
    and third-party-initiated ones by using "Was" (such as /showname_set, or by changing areas and
    having a showname conflict).

    If given IPID, it will obtain the showname history of all the clients opened by the user.
    Otherwise, it will just obtain the showname history of the given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /showname_history <client_id>
    /showname_history <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLE
    /showname_history 1         :: For the client whose ID is 1, you may get something like this

    == Showname history of client 1 ==
    *Sat Jun 1 18:52:32 2019 | Self set to Cas
    *Sat Jun 1 18:52:56 2019 | Was set to NotCas
    *Sat Jun 1 18:53:47 2019 | Was set to Ces
    *Sat Jun 1 18:53:54 2019 | Self cleared
    *Sat Jun 1 18:54:36 2019 | Self set to Cos
    *Sat Jun 1 18:54:46 2019 | Was cleared
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Obtain matching targets's showname history
    for c in Constants.parse_id_or_ipid(client, arg):
        info = c.get_showname_history()
        client.send_ooc(info)

def ooc_cmd_showname_nuke(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Clears all shownames from non-staff members.

    SYNTAX
    /showname_nuke

    PARAMETERS
    None

    EXAMPLE
    /showname_nuke          :: Clears all shownames
    """

    Constants.assert_command(client, arg, is_mod=True, parameters='=0')

    for c in client.server.client_manager.clients:
        if not c.is_staff() and c.showname != '':
            c.change_showname('')

    client.send_ooc('You have nuked all shownames.')
    client.send_ooc_others('A mod has nuked all shownames.', is_officer=False)
    client.send_ooc_others('{} [{}] has nuked all shownames.'
                           .format(client.name, client.id), is_officer=True)
    logger.log_server('{} has nuked all shownames.'.format(client.name), client)

def ooc_cmd_showname_set(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    If given a second argument, sets the showname of the given client by ID or IPID to that.
    Otherwise, it clears their showname to use the default setting (character showname).
    These custom shownames override whatever showname the current character has, and is persistent
    between between character swaps/area changes/etc.
    If given IPID, it will set the shownames of all the clients opened by the user. Otherwise, it
    will just set the showname of the given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /showname_set <client_id> {new_showname}
    /showname_set <client_ipid> {new_showname}

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    {new_showname}: New desired showname.

    EXAMPLES
    /showname_set 1 Phantom     :: Sets the showname of the client whose ID is 1 to Phantom.
    /showname_set 1234567890    :: Clears the showname of the client(s) whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_staff=True)

    try:
        separator = arg.index(" ")
    except ValueError:
        separator = len(arg)

    ID = arg[:separator]
    showname = arg[separator+1:]

    # Set matching targets's showname
    for c in Constants.parse_id_or_ipid(client, ID):
        old_showname = c.showname
        try:
            c.change_showname(showname)
        except ValueError:
            raise ClientError('Unable to set the showname of client {}: Given showname `{}` is '
                              'already in use in area {}.'.format(c.id, showname, c.area.name))

        if showname:
            s_message = 'You have set the showname of client {} to `{}`.'.format(c.id, showname)
            if old_showname:
                w_message = ('(X) {} [{}] changed the showname of client {} from `{}` to `{}` in '
                             'your zone ({}).'
                             .format(client.displayname, client.id, c.id, old_showname, c.showname,
                                     c.area.id))
            else:
                w_message = ('(X) {} [{}] set the showname of client {} to `{}` in your zone ({}).'
                             .format(client.displayname, client.id, c.id, c.showname, c.area.id))
            o_message = 'Your showname was set to `{}` by a staff member.'.format(showname)
            l_message = 'Set showname of {} to {}.'.format(c.ipid, showname)
        else:
            s_message = 'You have removed the showname of client {}.'.format(c.id)
            w_message = ('(X) {} [{}] removed the showname `{}` of client {} in your zone ({}).'
                         .format(client.displayname, client.id, old_showname, c.id, c.area.id))
            o_message = 'Your showname was removed by a staff member.'
            l_message = 'Removed showname {} of {}.'.format(showname, c.ipid)

        client.send_ooc(s_message)
        client.send_ooc_others(w_message, not_to={c}, is_zstaff=c.area)
        c.send_ooc(o_message)
        logger.log_server(l_message, client)

def ooc_cmd_sneak(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Sets given user based on client ID or IPID to be sneaking so that they are invisible through
    /getarea(s), /showname_list and /area.
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Search by IPID can only be performed by CMs and mods.
    Requires /reveal to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /sneak <client_id>
    /sneak <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /sneak 1                     :: Set client whose ID is 1 to be sneaking.
    /sneak 1234567890            :: Set all clients opened by the user whose IPID is 1234567890 to be sneaking.
    """

    Constants.assert_command(client, arg, is_staff=True)

    # Sneak matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        if client.is_gm and c.area.lobby_area:
            client.send_ooc('Target client is in a lobby area. You have insufficient permissions '
                            'to hide someone in such an area.')
            continue
        if c.area.private_area:
            client.send_ooc('Target client is in a private area. You are not allowed to hide '
                            'someone in such an area.')
            continue

        if c != client:
            client.send_ooc("{} is now sneaking.".format(c.displayname))
        c.change_visibility(False)
        client.send_ooc_others('(X) {} [{}] sneaked {} ({}).'
                               .format(client.displayname, client.id, c.displayname, c.area.id),
                               not_to={c}, is_zstaff=True)

def ooc_cmd_spectate(client: ClientManager.Client, arg):
    """
    Switches user's current character to the SPECTATOR character.
    Returns an error if their character is already a SPECTATOR.

    SYNTAX
    /spectate

    PARAMETERS
    None

    EXAMPLES
    /spectate                       :: Returns "You are now spectating." or "You are already spectating."
    """

    if len(arg) != 0:
        client.send_ooc('This command has no arguments.')

    # If user is already SPECTATOR, no need to change.
    if client.char_id == -1:
        raise ClientError('You are already spectating.')

    # Change the character to SPECTATOR
    client.change_character(-1)
    client.send_ooc('You are now spectating.')

def ooc_cmd_st(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Send a message to the private server-wide staff chat. Only staff members can send and receive
    messages from it (i.e. it is not a report command for normal users).

    SYNTAX
    /st <message>

    PARAMETERS
    <message>: Your message

    EXAMPLES
    /st Need help in area 0.       :: Sends "Need help in area 0" to all staff members.
    """

    Constants.assert_command(client, arg, is_staff=True)

    pre = '{} [Staff] {}'.format(client.server.config['hostname'], client.name)
    client.server.send_all_cmd_pred('CT', pre, arg, pred=lambda c: c.is_staff())
    logger.log_server('[{}][STAFFCHAT][{}][{}]{}.'
                      .format(client.area.id, client.get_char_name(), client.name, arg), client)

def ooc_cmd_switch(client: ClientManager.Client, arg: str):
    """
    Switches current user's character to a different one.
    Returns an error if character is unavailable or non-existant.

    SYNTAX
    /switch <char_name>

    PARAMETERS
    <char_name>: Character name

    EXAMPLES
    /switch Phoenix_HD
    """

    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a character name.')

    # Obtain char_id if character exists and then try and change to given char if available
    cid = client.server.get_char_id_by_name(arg)
    client.change_character(cid, client.is_mod)
    client.send_ooc('Character changed.')

def ooc_cmd_time(client: ClientManager.Client, arg: str):
    """
    Return the current server date and time. If the server specified a UTC time offset, it will use
    that offset instead (and also include it).

    SYNTAX
    /time

    PARAMETERS
    None

    EXAMPLES
    /time           :: May return something like "Sat Apr 27 19:04:17 2019"
    """

    Constants.assert_command(client, arg, parameters='=0')

    offset = client.server.config['utc_offset']
    if offset == 'local':
        current_time = time.strftime('%a %b %e %H:%M:%S %Y')
    else:
        offset_str = offset if float(offset) < 0 else '+{}'.format(offset)
        current_time_str = datetime.datetime.utcnow() + datetime.timedelta(hours=float(offset))
        current_time = current_time_str.strftime('%a %b %e %H:%M:%S (UTC{}) %Y'.format(offset_str))
    client.send_ooc(current_time)

def ooc_cmd_time12(client: ClientManager.Client, arg: str):
    """
    Return the current server date and time in 12 hour format.
    Also includes the server timezone. If the server specified a UTC time offset, it will use
    that offset.

    SYNTAX
    /time12

    PARAMETERS
    None

    EXAMPLES
    /time12         :: May return something like "Sat Apr 27 07:04:47 PM (+0200) 2019"
    """

    Constants.assert_command(client, arg, parameters='=0')

    offset = client.server.config['utc_offset']
    if offset == 'local':
        current_time = time.strftime('%a %b %e %I:%M:%S %p (%z) %Y')
    else:
        offset_str = offset if float(offset) < 0 else '+{}'.format(offset)
        current_time_str = datetime.datetime.utcnow() + datetime.timedelta(hours=float(offset))
        current_time = current_time_str.strftime('%a %b %e %I:%M:%S %p (UTC{}) %Y'
                                                 .format(offset_str))
    client.send_ooc(current_time)

def ooc_cmd_timer(client: ClientManager.Client, arg: str):
    """
    Start a timer.

    SYNTAX
    /timer <length> {timername} {public}

    PARAMETERS
    <length>: time in seconds, or in mm:ss, or in h:mm:ss; limited to TIMER_LIMIT in function
             Constants.parse_time_length

    OPTIONAL PARAMETERS
    {timername}: Timer name; defaults to username+"Timer" if empty
    {public or not}: Whether the timer is public or not; defaults to public if not fed one of
    "False", "false", "0", "No", "no".

    EXAMPLES
    Assuming the player has OOC name Phantom...
    /timer 10               :: Starts a public timer "PhantomTimer" of 10 seconds.
    /timer 3:00 T           :: Starts a public timer "T" of length 3 minutes.
    /timer 5:53:21 Spam No  :: Starts a private timer "Spam" of length 5 hours, 53 mins and 21 secs.

    Public status functionality
    * Non-public timers will only send timer announcements/can only be consulted by
      the person who initiated the timer and staff
    * Public timers initiated by non-staff will only send timer announcements/can only be
      be consulted by staff and people in the same area as the person who initiated the timer
    * Public timers initiated by staff will send timer announcements/can be consulted by
      anyone at any area.
    """

    Constants.assert_command(client, arg, parameters='&1-3', split_spaces=True)

    arg = arg.split(' ')

    # Check if valid length and convert to seconds
    length = Constants.parse_time_length(arg[0]) # Also internally validates

    # Check name
    if len(arg) > 1:
        name = arg[1]
    else:
        name = client.name.replace(" ", "") + "Timer" # No spaces!
    if name in client.server.tasker.active_timers.keys():
        raise ClientError('Timer name {} is already taken.'.format(name))

    # Check public status
    if len(arg) > 2 and arg[2] in ['False', 'false', '0', 'No', 'no']:
        is_public = False
    else:
        is_public = True

    client.server.tasker.active_timers[name] = client #Add to active timers list
    client.send_ooc('You initiated a timer "{}" of length {} seconds.'.format(name, length))
    client.send_ooc_others('(X) {} [{}] initiated a timer "{}" of length {} seconds in area {} '
                           '({}).'
                           .format(client.displayname, client.id, name, length,
                                   client.area.name, client.area.id), is_zstaff_flex=True)
    client.send_ooc_others('{} initiated a timer "{}" of length {} seconds.'
                           .format(client.displayname, name, length), is_zstaff_flex=False,
                           pred=lambda c: is_public)

    client.server.tasker.create_task(client, ['as_timer', time.time(), length, name, is_public])

def ooc_cmd_timer_cancel(client: ClientManager.Client, arg: str):
    """
    Cancel given timer by timer name. Requires logging in to cancel timers initiated by other users.
    Returns an error if timer does not exist or if the user is not authorized to cancel the timer.

    SYNTAX
    /timer_cancel <timername>

    PARAMETERS
    <timername>: Timer name to cancel

    EXAMPLES
    Assuming player Spam started a timer "S", and the moderator Phantom started a timer "P"...
    /timer_cancel S     :: Both Spam and Phantom would cancel timer S if either ran this.
    /timer_cancel P     :: Only Phantom would cancel timer P if either ran this.
    """

    Constants.assert_command(client, arg, parameters='=1', split_spaces=True)

    arg = arg.split(' ')

    timer_name = arg[0]
    try:
        timer_client = client.server.tasker.active_timers[timer_name]
    except KeyError:
        raise ClientError('Timer {} is not an active timer.'.format(timer_name))

    # Non-staff are only allowed to cancel their own timers
    if not client.is_staff() and client != timer_client:
        raise ClientError('You must be authorized to do that.')

    timer = client.server.tasker.get_task(timer_client, ['as_timer'])
    client.server.tasker.cancel_task(timer)

def ooc_cmd_timer_get(client: ClientManager.Client, arg: str):
    """
    Get remaining time from given timer if given a timer name. Otherwise, list all viewable timers.
    Returns an error if user attempts to consult a timer they have no permissions for.

    SYNTAX
    /timer_get {timername}

    OPTIONAL PARAMETERS
    {timername}: Check time remaining in given timer; defaults to all timers if not given one.

    EXAMPLES
    Assuming a player Spam started a private timer "S", a moderator Phantom started a timer "P",
    and a third player Eggs started a public timer "E"...
    /timer_get      :: Spam and Phantom would get the remaining times of S, P and E; Eggs only S and P.
    /timer_get S    :: Spam and Phantom would get the remaining time of S, Eggs would get an error.
    /timer_get P    :: Spam, Phantom and Eggs would get the remaining time of P.
    /timer_get E    :: Spam, Phantom and Eggs would get the remaining time of E.
    """

    Constants.assert_command(client, arg, parameters='<2')
    arg = arg.split(' ') if arg else list()

    string_of_timers = ""

    if len(arg) == 1:
        # Check specific timer
        timer_name = arg[0]
        if timer_name not in client.server.tasker.active_timers.keys():
            raise ClientError('Timer {} is not an active timer.'.format(timer_name))
        timers_to_check = [timer_name]
    else: # Case len(arg) == 0
        # List all timers
        timers_to_check = client.server.tasker.active_timers.keys()
        if len(timers_to_check) == 0:
            raise ClientError('No active timers.')

    for timer_name in timers_to_check:
        timer_client = client.server.tasker.active_timers[timer_name]
        start, length, _, is_public = client.server.tasker.get_task_args(timer_client, ['as_timer'])

        # Non-public timers can only be consulted by staff and the client who started the timer
        if not is_public and not (client.is_staff() or client == timer_client):
            continue

        # Non-staff initiated public timers can only be consulted by all staff and
        # clients in the same area as the timer initiator
        if (is_public and not timer_client.is_staff() and not
              (client.is_staff() or client == timer_client or client.area == timer_client.area)):
            continue

        _, remain_text = Constants.time_remaining(start, length)
        string_of_timers += 'Timer {} has {} remaining.\n*'.format(timer_name, remain_text)

    if string_of_timers == "": # No matching timers
        if len(arg) == 1: # Checked for a specific timer
            # This case happens when a non-authorized user attempts to check
            # a non-public timer
            string_of_timers = "Timer {} is not an active timer.  ".format(timer_name)
            # Double space intentional
        else: # len(arg) == 0
            # This case happens when a non-authorized user attempts to check
            # all timers and all timers are non-public or non-viewable.
            string_of_timers = "No timers available.  " # Double space intentional
    elif len(arg) == 0: # Used /timer_get
        string_of_timers = "Current active timers:\n*" + string_of_timers # Add lead

    client.send_ooc(string_of_timers[:-2]) # Ignore last newline character

def ooc_cmd_ToD(client: ClientManager.Client, arg: str):
    """
    Chooses "Truth" or "Dare". Intended to be use for participants in Truth or Dare games.

    SYNTAX
    /ToD

    PARAMETERS
    None

    EXAMPLES
    /ToD                :: May return something like 'Phoenix_HD has to do a truth.'
    """

    Constants.assert_command(client, arg, parameters='=0')

    coin = ['truth', 'dare']
    flip = random.choice(coin)
    client.area.broadcast_ooc('{} has to do a {}.'.format(client.displayname, flip))
    logger.log_server('[{}][{}]has to do a {}.'
                      .format(client.area.id, client.get_char_name(), flip), client)

def ooc_cmd_toggle_allrolls(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles receiving /roll and /rollp notifications from areas other than the current one.
    Notifications are turned off by default.

    SYNTAX
    /toggle_allrolls

    PARAMETERS
    None

    EXAMPLE
    /toggle_allrolls
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.get_foreign_rolls = not client.get_foreign_rolls
    status = {False: 'no longer', True: 'now'}

    client.send_ooc('You are {} receiving roll results from other areas.'
                    .format(status[client.get_foreign_rolls]))

def ooc_cmd_toggle_fp(client: ClientManager.Client, arg: str):
    """
    Toggles first person mode on or off. If on, you will not receive your character sprites when you
    send messages yourself, but instead will keep whatever the last sprite used was onscreen.

    SYNTAX
    /toggle_fp

    PARAMETERS
    None

    EXAMPLE
    Assuming you start in normal mode...
    /toggle_fp          :: Toggles first person mode on.
    /toggle_fp          :: Toggles first person mode off.
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.first_person = not client.first_person
    status = {True: 'now', False: 'no longer'}

    client.send_ooc('You are {} in first person mode.'.format(status[client.first_person]))

def ooc_cmd_toggle_global(client: ClientManager.Client, arg: str):
    """
    Toggles global messages being sent to the current user being allowed/disallowed.

    SYNTAX
    /toggle_global

    PARAMETERS
    None

    EXAMPLE
    /toggle_global
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.muted_global = not client.muted_global
    status = {True: 'no longer', False: 'now'}

    client.send_ooc('You will {} receive global messages.'.format(status[client.muted_global]))

def ooc_cmd_toggle_pm(client: ClientManager.Client, arg: str):
    """
    Toggles between being able to receive PMs or not.

    SYNTAX
    /toggle_pm

    PARAMETERS
    None

    EXAMPLE
    /toggle_pm
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.pm_mute = not client.pm_mute
    status = {True: 'You will no longer receive PMs.', False: 'You will now receive PMs.'}

    client.send_ooc(status[client.pm_mute])

def ooc_cmd_toggle_shownames(client: ClientManager.Client, arg: str):
    """
    Toggles between receiving IC messages with custom shownames or receiving them all with
    character names. When joining, players will receive IC messages with shownames.

    SYNTAX
    /toggle_shownames

    PARAMETERS
    None

    EXAMPLE
    Assuming a player who just joined
    /toggle_shownames           :: All subsequent messages will only include character names as the message sender.
    /toggle_shownames           :: All subsequent messages will include the shownames of the senders if they have one.
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.show_shownames = not client.show_shownames
    status = {False: 'off', True: 'on'}

    client.send_ooc('Shownames turned {}.'.format(status[client.show_shownames]))

def ooc_cmd_transient(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Toggles a client by IP or IPID being transient or not to passage locks (i.e. can access all
    areas or only reachable areas)
    If given IPID, it will invert the transient status of all the clients opened by the user.
    Otherwise, it will just do it to the given client.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /transient <client_id>
    /transient <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLE
    Assuming a player with client ID 0 and IPID 1234567890 starts as not being transient to passage locks
    /transient 0            :: This player can now access all areas regardless of passage locks.
    /transient 1234567890   :: This player can now only access only reachable areas.
    """

    Constants.assert_command(client, arg, is_staff=True)

    # Invert current transient status of matching targets
    status = {False: 'no longer', True: 'now'}
    for c in Constants.parse_id_or_ipid(client, arg):
        c.is_transient = not c.is_transient
        client.send_ooc('{} ({}) is {} transient to passage locks.'
                        .format(c.displayname, c.area.id, status[c.is_transient]))
        c.send_ooc('You are {} transient to passage locks.'.format(status[c.is_transient]))
        c.reload_music_list() # Update their music list to reflect their new status

def ooc_cmd_unban(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes given user from the server banlist, allowing them to rejoin the server.
    Returns an error if given identifier does not correspond to a banned user.

    SYNTAX
    /unban <client_ipid>
    /unban <client_ip>

    PARAMETERS
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    <client_ip>: user IP

    EXAMPLES
    /unban 1234567890             :: Unbans the user whose IPID is 1234567890
    /unban 127.0.0.1              :: Unbans the user whose IP is 127.0.0.1
    """

    arg = arg.strip()
    Constants.assert_command(client, arg, parameters='>0', is_mod=True)

    if arg.isdigit():
        # IPID
        idnt = int(arg.strip())
    else:
        # IP Address
        idnt = arg.strip()

    client.server.ban_manager.remove_ban(idnt)

    client.send_ooc('Unbanned `{}`.'.format(idnt))
    client.send_ooc_others('{} [{}] unbanned `{}`.'
                           .format(client.name, client.id, idnt), is_officer=True)
    logger.log_server('Unbanned {}.'.format(idnt), client)

def ooc_cmd_unbanhdid(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes given user by HDID from the server banlist, allowing them to rejoin the server.
    Returns an error if given HDID does not correspond to a banned user.

    SYNTAX
    /unbanhdid <client_hdid>

    PARAMETERS
    <client_hdid>: User HDID (available in server logs and through a mod /whois)

    EXAMPLES
    /unbanhdid abcd1234         :: Unbans user whose HDID is abcd1234
    """

    Constants.assert_command(client, arg, parameters='=1', is_mod=True)

    if not arg in client.server.hdid_list:
        raise ClientError('Unrecognized HDID {}.'.format(arg))

    # The server checks for any associated banned IPID for a player, so in order to unban by HDID
    # all the associated IPIDs must be unbanned.

    found_banned = False
    for ipid in client.server.hdid_list[arg]:
        if client.server.ban_manager.is_banned(ipid):
            client.server.ban_manager.remove_ban(ipid)
            found_banned = True

    if not found_banned:
        raise ClientError('User is already not banned.')

    client.send_ooc('Unbanned HDID `{}`.'.format(arg))
    client.send_ooc_others('{} [{}] unbanned HDID `{}`.'
                           .format(client.name, client.id, arg), is_officer=True)
    logger.log_server('HDID-unbanned {}.'.format(arg), client)

def ooc_cmd_unblockdj(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Restores the ability of a player by client ID (number in brackets) or IPID (number in
    parentheses) to change music.
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /unblockdj <client_id>
    /unblockdj <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /unblockdj 1                     :: Restores DJ permissions to the client whose ID is 1.
    /unblockdj 1234567890            :: Restores DJ permissions to all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_officer=True)

    # Restore DJ permissions to matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.is_dj = True
        logger.log_server('Restored DJ permissions to {}.'.format(c.ipid), client)
        client.area.broadcast_ooc('{} had their DJ permissions restored.'.format(c.displayname))

def ooc_cmd_undisemconsonant(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes the disemconsonant effect on all IC and OOC messages of a player by client ID
    (number in brackets) or IPID (number in parentheses).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Requires /disemconsonant to undo.
    Returns an error f the given identifier does not correspond to a user.

    SYNTAX
    /undisemconsonant <client_id>
    /undisemconsonant <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /undisemconsonant 1           :: Undisemconsonants the player whose client ID is 1.
    /undisemconsonant 1234567890  :: Undisemconsonants all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Undisemconsonant matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.disemconsonant = False
        logger.log_server('Undisemconsonanted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was undisemconsonanted.".format(c.displayname))

def ooc_cmd_undisemvowel(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes the disemvowel effect on all IC and OOC messages of a player by client ID (number in
    brackets) or IPID (number in parentheses).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Requires /disemvowel to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /undisemvowel <client_id>
    /undisemvowel <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /undisemvowel 1           :: Undisemvowel the player whose client ID is 1.
    /undisemvowel 1234567890  :: Undisemvowel all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Undisemvowel matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.disemvowel = False
        logger.log_server('Undisemvowelled {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was undisemvowelled.".format(c.displayname))

def ooc_cmd_unfollow(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Stops following the player you are following.
    Returns an error if you are not following anyone.

    SYNTAX
    /unfollow

    PARAMETERS
    None

    EXAMPLE
    Assuming you were following someone...
    /unfollow                     :: Stops following the player
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.unfollow_user()

def ooc_cmd_ungimp(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Ungimps all IC messages of a player by client ID (number in brackets) or IPID (number in
    parentheses).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Requires /gimp to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /ungimp <client_id>
    /ungimp <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /ungimp 1                     :: Gimps the player whose client ID is 1.
    /ungimp 1234567890            :: Gimps all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Ungimp matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.gimp = False
        logger.log_server('Ungimping {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was ungimped.".format(c.displayname))

def ooc_cmd_unglobalic(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Send subsequent IC messages to users in the same area as the client (i.e. as normal).
    It is the way to undo a /globalic command.

    SYNTAX
    /unglobalic

    PARAMETERS
    None

    EXAMPLES
    /unglobalic             :: Send subsequent messages normally (only to users in current area).
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.multi_ic = None
    client.send_ooc('Your IC messages will now be only sent to your current area.')

def ooc_cmd_unhandicap(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Removes movement handicaps on a client by ID or IPID so that they no longer need to wait a set
    amount of time between changing areas. This will also remove server handicaps, if any (such as
    automatic sneak handicaps).
    If given IPID, it will remove the movement handicap on all the clients opened by the user.
    Otherwise, it will just do it to the given client.
    Requires /handicap to undo.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /unhandicap <client_id>
    /unhandicap <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /unhandicap 0           :: Removes all movement handicaps on the player whose client ID is 0
    /unhandicap 1234567890  :: Removes all movement handicaps on the clients whose IPID is 1234567890
    """

    Constants.assert_command(client, arg, is_staff=True)

    # Obtain targets
    for c in Constants.parse_id_or_ipid(client, arg):
        try:
            _, _, name, _ = client.server.tasker.get_task_args(c, ['as_handicap'])
        except KeyError:
            client.send_ooc('{} does not have an active movement handicap.'
                            .format(c.displayname))
        else:
            client.send_ooc('You removed the movement handicap "{}" on {}.'
                            .format(name, c.displayname))
            client.send_ooc_others('(X) {} [{}] removed the movement handicap "{}" on {} in area '
                                   '{} ({}).'
                                   .format(client.displayname, client.id, name, c.displayname,
                                           client.area.name, client.area.id),
                                   is_zstaff_flex=True)
            c.send_ooc('Your movement handicap "{}" when changing areas was removed.'.format(name))
            c.handicap_backup = None
            client.server.tasker.remove_task(c, ['as_handicap'])

def ooc_cmd_unilock(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Changes the passage status from a given area to another by name or ID. Passages are
    unidirectional, so to change a passage in both directions simultaneously, use /bilock instead.
    If given one area, it will change the passage status FROM the current area TO the given one.
    If given two areas instead, it  will change the passage status FROM the first given area TO
    the second give one (but requires staff role to use).
    Returns an error if the user is unauthorized to create new passages or change existing ones in
    the originating area. In particular, non-staff members are not allowed to create passages
    that did not exist when the areas were loaded or that a staff member did not create before.

    SYNTAX
    /unilock <target_area>
    /unilock <target_area_1>, <target_area_2>

    PARAMETERS
    <target_area>: Area whose passage status that starts in the current area will be changed.
    <target_area_1>: Area whose passage status that ends in <target_area_2> will be changed.
    <target_area_2>: Area whose passage status that starts in <target_area_1> will be changed.

    EXAMPLES
    Assuming the player is in area 0 when executing these commands and originally the only existing
    passage lock is from area 1 'Class Trial Room' to area 2 'Class Trial Room, 2'...
    /unilock Class Trial Room            :: Locks the passage from area 0 to Class Trial Room.
    /unilock 1, 2                        :: Unlocks the passage from Class Trial Room to Class Trial
                                            Room, 2 (keeps it unlocked the other way).
    /unilock Class Trial Room,\ 2, 0     :: Locks the passage in from Class Trial Room, 2 to area 0
                                            (note the ,\ in the command).
    """

    Constants.assert_command(client, arg, parameters='&1-2', split_commas=True)

    areas = arg.split(', ')
    if len(areas) == 2 and not client.is_staff():
        raise ClientError('You must be authorized to use the two-parameter version of this '
                          'command.')

    areas = Constants.parse_two_area_names(client, areas, area_duplicate=False,
                                           check_valid_range=False)
    now_reachable = Constants.parse_passage_lock(client, areas, bilock=False)

    status = {True: 'unlocked', False: 'locked'}
    now0 = status[now_reachable[0]]
    name0, name1 = areas[0].name, areas[1].name

    client.send_ooc('You have {} the passage from {} to {}.'
                    .format(now0, name0, name1))
    client.send_ooc_others('(X) {} [{}] has {} the passage from {} to {} ({}).'
                           .format(client.displayname, client.id, now0, name0, name1,
                                   client.area.id),
                           is_zstaff_flex=True)
    logger.log_server('[{}][{}]Has {} the passage from {} to {}.'
                      .format(client.area.id, client.get_char_name(), now0, name0, name1))

def ooc_cmd_uninvite(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Removes a client based on some ID to the area's invite list. Only staff members can invite based
    on IPID. Invites are IPID based, so anyone with the same IPID is no longer part of the area's
    invite list.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user or if target is already
    not invited.

    SYNTAX
    /uninvite <client_ipid>
    /uninvite <user_id>

    PARAMETERS
    <client_ipid>: IPID for the client (number in parentheses in /getarea)
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    /uninvite 1                   :: Uninvites the player whose client ID is 1.
    /uninvite 1234567890          :: Uninvites all clients opened by the player whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, parameters='=1')

    if not client.area.is_locked and not client.area.is_modlocked and not client.area.is_gmlocked:
        raise ClientError('Area is not locked.')

    targets = list() # Start with empty list
    if (client.is_mod or client.is_cm) and arg.isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        if targets:
            some_target = targets[0]
    if not targets:
        # Under the hood though, we need the IPID of the target, so we will still end up obtaining
        # it anyway. We want to get all clients whose IPID match the IPID of whatever we match
        some_target, _, _ = client.server.client_manager.get_target_public(client, arg)
        targets = client.server.client_manager.get_targets(client, TargetType.IPID,
                                                           some_target.ipid, False)

    # Check if target is already invited
    if some_target.ipid not in client.area.invite_list:
        raise ClientError('Target is already not invited to your area.')

    # Remove from invite list and notify targets
    client.area.invite_list.pop(some_target.ipid)

    for c in targets:
        # If uninviting yourself, send special message
        if client == c:
            client.send_ooc('You have uninvited yourself from this area.')
        else:
            client.send_ooc('Client {} has been uninvited from your area.'.format(c.id))
            c.send_ooc('You have been uninvited from area {}.'.format(client.area.name))

def ooc_cmd_unlock(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    If the area is locked in some manner, attempt to perform exactly one of the following area
    unlocks in order.
    1. If player is a mod and the area is mod-locked, then mod-unlock.
    2. If player is staff and the area is gm-locked, then gm-unlock.
    3. If the area is not mod-locked nor gm-locked, then unlock.

    Returns an error if the area was locked but the unlock could not be performed (would happen due
    to insufficient permissions).

    SYNTAX
    /unlock

    PARAMETERS
    None

    EXAMPLE
    /unlock             :: Perform one of the unlocks described above if possible
    """

    Constants.assert_command(client, arg, parameters='=0')

    if not client.area.is_locked and not client.area.is_modlocked and not client.area.is_gmlocked:
        raise ClientError('Area is already open.')

    if client.is_mod and client.area.is_modlocked:
        client.area.modunlock()
    elif client.is_staff() and not client.area.is_modlocked:
        client.area.gmunlock()
    elif not client.area.is_gmlocked and not client.area.is_modlocked:
        client.area.unlock()
    else:
        raise ClientError('You must be authorized to do that.')
    client.send_ooc('Area is unlocked.')

def ooc_cmd_unmute(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Unmutes given user based on client ID or IPID so that they are unable to speak in IC chat.
    This command does nothing for clients that are not actively muted.
    If given IPID, it will unmute all clients opened by the user. Otherwise, it will just mute the
    given client.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /unmute <client_id>
    /unmute <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /unmute 1                     :: Unmutes client whose ID is 1.
    /unmute 1234567890            :: Unmutes all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_officer=True)

    # Mute matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        logger.log_server('Unmuted {}.'.format(c.ipid), client)
        client.area.broadcast_ooc("{} was unmuted.".format(c.displayname))
        c.is_muted = False

def ooc_cmd_unremove_h(client: ClientManager.Client, arg: str):
    """ (MOD ONLY)
    Removes the 'Remove H' effect on all IC and OOC messages of a player by client ID (number in
    brackets) or IPID (number in parentheses).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect
    the given client.
    Requires /remove_h to undo.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /unremove_h <client_id>
    /unremove_h <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    /unremove_h 1           :: Removes the 'Remove H' effect on the player whose client ID is 1.
    /unremove_h 1234567890  :: Removes the 'Remove H' effect on all clients opened by the user whose IPID is 1234567890.
    """

    Constants.assert_command(client, arg, is_mod=True)

    # Remove the 'Remove H' effect on matching targets
    for c in Constants.parse_id_or_ipid(client, arg):
        c.remove_h = False
        logger.log_server("Removed 'Remove H' effect on {}.".format(c.ipid), client)
        client.area.broadcast_ooc("{} had the 'Remove H' effect removed.".format(c.displayname))

def ooc_cmd_version(client: ClientManager.Client, arg: str):
    """
    Obtains the current version of the server software.

    SYNTAX
    /version

    PARAMETERS
    None

    EXAMPLES
    /version        :: May return something like: This server is running TsuserverDR 4.0.0 (190801a)
    """

    Constants.assert_command(client, arg, parameters='=0')

    client.send_ooc('This server is running {}.'.format(client.server.version))

def ooc_cmd_whereis(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Obtains the current area of a player by client ID (number in brackets) or IPID (number in
    parentheses).
    If given IPID, it will obtain the area info for all clients opened by the user. Otherwise, it
    will just obtain the one from the given client.
    Search by IPID can only be performed by CMs and mods.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /whereis <client_id>
    /whereis <client_ipid>

    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: IPID for the client (number in parentheses in /getarea)

    EXAMPLES
    Assuming client 1 with IPID 1234567890 is in the Basement (area 0)...
    /whereis 1           :: May return something like this: Client 1 (1234567890) is in Basement (0)
    /whereis 1234567890  :: May return something like this: Client 1 (1234567890) is in Basement (0)
    """

    Constants.assert_command(client, arg, is_staff=True)

    for c in Constants.parse_id_or_ipid(client, arg):
        client.send_ooc("Client {} ({}) is in {} ({})."
                        .format(c.id, c.ipid, c.area.name, c.area.id))

def ooc_cmd_whisper(client: ClientManager.Client, arg: str):
    """
    Sends an IC personal message to a specified user by some ID. The messages have the showname
    of the sender and their message, but does not include their sprite.
    Elevated notifications are sent to zone watchers/staff members on whispers to other people,
    which include the message content, so this is not meant to act as a private means of
    communication between players, for which /pm is recommended.
    Whispers sent by sneaked players include an empty showname so as to not reveal their identity.
    Whispers sent to sneaked players will succeed only if the sender is sneaking and both the sender
    and recipient are part of the same party. If the attempt fails but the player is staff member,
    they will get a friendly suggestion to use /guide instead.
    Deafened recipients will receive a nerfed message if whispered to.
    Non-zone watchers/non-staff players in the same area as the whisperer will be notified that
    they whispered to their target (but will not receive the content of the message), provided they
    are not blind (in which case no notification is sent) and that this was not a self-whisper.
    Returns an error if the user could not be found, if the message is empty or if the sender is
    gagged or IC-muted.

    SYNTAX
    /whisper <user_ID> <message>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.
    <message>: Message to be sent.

    EXAMPLES
    /whisper 1 Hey, client 1!   :: Sends that message to player with client ID 1.
    /whisper 0 Yo               :: Sends that message to player with client ID 0.
    """

    try:
        Constants.assert_command(client, arg, parameters='>1')
    except ArgumentError:
        raise ArgumentError('Not enough arguments. Use /whisper <target> <message>. Target should '
                            'be ID, char-name, edited-to character, custom showname or OOC-name.')
    if client.is_muted:
        raise ClientError('You have been muted by a moderator.')
    if client.is_gagged:
        raise ClientError('Your attempt at whispering failed because you are gagged.')

    cm = client.server.client_manager
    target, _, msg = cm.get_target_public(client, arg, only_in_area=True)
    msg = msg[:256] # Cap
    public_area = not client.area.private_area

    final_sender = client.displayname
    final_rec_sender = 'Someone' if (target.is_deaf and target.is_blind) else client.displayname
    final_st_sender = client.displayname
    final_target = target.displayname
    final_message = msg

    if client == target:
        # Player whispered to themselves. Why? Dunno, ask them, not me
        client.send_ooc('You whispered `{}` to yourself.'.format(final_message))
        client.send_ic(msg=msg, pos=client.pos, cid=client.char_id, showname=client.showname,
                       bypass_deafened_starters=True)
    elif not (client.is_visible ^ target.is_visible):
        # Either both client and target are visible
        # Or they are both not, where cm.get_target_public already handles removing sneaked targets
        # if they are not part of the same party as the client (or the client is not staff)
        client.send_ooc('You whispered `{}` to {}.'.format(final_message, final_target))
        client.send_ic(msg=msg, pos=client.pos, cid=client.char_id, showname=client.showname,
                       bypass_replace=False, bypass_deafened_starters=True)

        target.send_ooc('{} whispered something to you.'.format(final_sender), to_deaf=False)
        target.send_ooc('{} seemed to whisper something to you, but you could not make it out.'
                        .format(final_rec_sender), to_deaf=True)
        target.send_ic(msg=msg, pos=client.pos, cid=client.char_id, showname=client.showname,
                       bypass_deafened_starters=True) # send_ic handles nerfing for deafened

        if not client.is_visible and public_area:
            # This code should run if client and target are sneaked and part of same party
            # and also if the area is public
            client.send_ooc_others('(X) {} [{}] whispered `{}` to {} while both were sneaking and '
                                   'part of the same party ({}).'
                                   .format(final_st_sender, client.id, final_message,
                                           final_target, client.area.id),
                                   is_zstaff_flex=True, not_to={target})
        else:
            # Otherwise, announce it to everyone. If the area is private, zone watchers and staff
            # get normal whisper reports if in the same area.
            if public_area:
                client.send_ooc_others('(X) {} [{}] whispered `{}` to {} ({}).'
                                       .format(final_st_sender, client.id, final_message,
                                               final_target, client.area.id),
                                       is_zstaff_flex=True, not_to={target})
            client.send_ooc_others('{} whispered something to {}.'
                                   .format(final_sender, final_target),
                                   is_zstaff_flex=False if public_area else None, in_area=True,
                                   not_to={target}, to_blind=False)
    elif target.is_visible:
        client.send_ooc('You spooked {} by whispering `{}` to them while sneaking.'
                        .format(final_target, final_message))
        client.send_ic(msg=msg, pos='jud', showname='???', bypass_deafened_starters=True)
        # Note this uses pos='jud' instead of pos=client.pos. This is to mask the position of the
        # sender, so that the target cannot determine who it is based on knowing usual positions
        # of people.
        # If target is deafened, behavior is different
        target.send_ooc('You heard a whisper and you think it was directed at you, but you could '
                        'not seem to tell where it came from.', to_deaf=False)
        target.send_ooc('Your ears seemed to pick up something.', to_deaf=True)
        target.send_ic(msg=msg, pos='jud', showname='???', bypass_deafened_starters=True)

        if not client.area.private_area:
            client.send_ooc_others('(X) {} [{}] whispered `{}` to {} while sneaking ({}).'
                                   .format(final_st_sender, client.id, final_message, final_target,
                                           client.area.id), is_zstaff_flex=True, not_to={target})
    else: # Sender is not sneaked, target is
        if client.is_staff():
            msg = ('Your target {} is sneaking and whispering to them would reveal them. Instead, '
                   'use /guide'.format(target.displayname))
            raise ClientError(msg)
        # Normal clients should never get here except if get_target_public is wrong
        # which would be very sad.
        raise ValueError('Never should have come here!')

def ooc_cmd_whois(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY+VARYING REQUIREMENTS)
    Lists A LOT of a client properties. CMs and mods additionally get access to a client's HDID.
    The player can be filtered by either client ID, IPID, HDID, OOC username (in the same area),
    character name (in the same area) or custom showname (in the same area).
    However, only CMs and mods can search through IPID or HDID.
    If multiple clients match the given identifier, only one of them will be returned.
    For best results, use client ID (number in brackets), as this is the only tag that is
    guaranteed to be unique.
    If given no identifier, it will return your properties.
    Returns an error if the given identifier does not correspond to a user.

    SYNTAX
    /whois <target_id>

    PARAMETER
    <target_id>: Either client ID, IPID, OOC username or character name

    EXAMPLES
    For player with client ID 1, IPID 1234567890, HDID abb0011, OOC username Phantom, character name Phantom_HD, and showname The phantom, all of these do the same
    /whois 1            :: Returns client info.
    /whois 1234567890   :: Returns client info.
    /whois abb0011      :: Returns client info.
    /whois Phantom      :: Returns client info.
    /whois The Phantom  :: Returns client info.
    /whois Phantom_HD   :: Returns client info.
    """

    Constants.assert_command(client, arg, is_staff=True)
    if not arg:
        targets = [client]
        arg = client.id
    else:
        targets = []

    # If needed, pretend the identifier is a client ID
    if not targets and arg.isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)

    # If still needed, pretend the identifier is a client IPID (only CM and mod)
    if not targets and arg.isdigit() and (client.is_mod or client.is_cm):
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)

    # If still needed, pretend the identifier is a client IPID (only CM and mod)
    if not targets and (client.is_mod or client.is_cm):
        targets = client.server.client_manager.get_targets(client, TargetType.HDID, arg, False)

    # If still needed, pretend the identifier is an OOC username
    if not targets:
        targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, True)

    # If still needed, pretend the identifier is a character name
    if not targets:
        targets = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, arg, True)

    # If still needed, pretend the identifier is a showname
    if not targets:
        targets = client.server.client_manager.get_targets(client, TargetType.SHOWNAME, arg, True)

    # If still not found, too bad
    if not targets:
        raise ArgumentError('Target not found.')

    # Otherwise, send information
    info = targets[0].get_info(as_mod=client.is_mod, as_cm=client.is_cm, identifier=arg)
    client.send_ooc(info)

def ooc_cmd_zone(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Makes a zone that spans the given area range, or just the given area if just given one area, or
    the current area if not given any.
    Returns an error if the user is already watching some other zone, or if any of the areas to be
    made part of the zone to be created already belong to some other zone.

    SYNTAX
    /zone
    /zone <sole_area_in_zone>
    /zone <area_range_start>, <area_range_end>

    PARAMETERS
    <sole_area_in_zone>: Sole area to add to the zone
    <area_range_start>: Start of area range (inclusive)
    <area_range_end>: End of area range (inclusive)

    EXAMPLES
    Assuming the player is in area 0...
    /zone                       :: Creates a zone that has area 0.
    /zone Class Trial Room 1    :: Creates a zone that only has area Class Trial Room 1
    /zone 16, 116               :: Creates a zone that has areas 16 through 116.
    """

    Constants.assert_command(client, arg, is_staff=True)

    # Obtain area range and create zone based on it
    raw_area_names = arg.split(', ') if arg else []
    lower_area, upper_area = Constants.parse_two_area_names(client, raw_area_names,
                                                            check_valid_range=True)
    areas = client.server.area_manager.get_areas_in_range(lower_area, upper_area)

    try:
        zone_id = client.server.zone_manager.new_zone(areas, {client})
    except ZoneError.AreaConflictError:
        raise ZoneError('Some of the areas of your new zone are already part of some other zone.')
    except ZoneError.WatcherConflictError:
        raise ZoneError('You cannot create a zone while watching another.')

    # Prepare client output
    if lower_area == upper_area:
        output = 'just area {}'.format(lower_area.id)
    else:
        output = 'areas {} through {}'.format(lower_area.id, upper_area.id)

    client.send_ooc('You have created zone `{}` containing {}.'.format(zone_id, output))
    client.send_ooc_others('(X) {} [{}] has created zone `{}` containing {} ({}).'
                           .format(client.displayname, client.id, zone_id, output, client.area.id),
                           is_officer=True)
    for area in areas:
        for c in area.clients:
            if c.is_staff() and c != client:
                c.send_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format(zone_id, zone_id))

def ooc_cmd_zone_add(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Adds an area by name or ID to the zone the user is watching.
    Returns an error if the area identifier does not correspond to an area, if the area is part of
    some other zone, or if the user is not watching a zone.

    SYNTAX
    /zone_add <area_name>
    /zone_add <area_id>

    PARAMETERS
    <area_name>: Name of the area whose door you want to knock.
    <area_id>: ID of the area whose door you want to knock.

    EXAMPLES
    /zone_add 0                :: Add area 0 to the zone
    /zone_add Courtroom, 2     :: Add area "Courtroom, 2" to the zone
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=1')

    if not client.zone_watched:
        raise ZoneError('You are not watching a zone.')
    area = Constants.parse_area_names(client, arg).pop()

    try:
        client.zone_watched.add_area(area)
    except ZoneError.AreaConflictError:
        raise ZoneError('Area {} already belongs to a zone.'.format(arg))

    client.send_ooc('You have added area {} to your zone.'.format(area.id))
    client.send_ooc_others('(X) {} [{}] has added area {} to your zone.'
                           .format(client.displayname, client.id, area.id), is_zstaff=True)

    zone_id = client.zone_watched.get_id()
    for c in area.clients:
        if c.is_staff() and c != client and c.zone_watched != client.zone_watched:
            c.send_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                       'its notifications, start watching it with /zone_watch {}'
                       .format(zone_id, zone_id))

def ooc_cmd_zone_delete(client: ClientManager.Client, arg: str):
    """ (VARYING REQUIREMENTS)
    Deletes the zone the user is watching, so that it is no longer part of the server's zone list,
    if no argument is given (GM OR ABOVE ONLY), or deletes the zone by its name (CM OR MOD ONLY)
    Returns an error if the user gives no zone name and is not watching a zone.

    SYNTAX
    /zone_delete

    PARAMETERS
    None

    EXAMPLES
    If the user is watching zone 1000
    /zone_delete       :: Deletes the zone 1000
    """

    try:
        Constants.assert_command(client, arg, is_officer=True)
    except ClientError.UnauthorizedError:
        # Case GM, who can only delete a zone they are watching
        try:
            Constants.assert_command(client, arg, is_staff=True, parameters='=0')
        except ArgumentError:
            raise ClientError.UnauthorizedError('You must be authorized to use a zone name with '
                                                'this command.')

    if arg:
        try:
            target_zone = client.server.zone_manager.get_zone(arg)
        except KeyError:
            raise ZoneError('`{}` is not a valid zone ID.'.format(arg))
    else:
        if not client.zone_watched:
            raise ZoneError('You are not watching a zone.')
        target_zone = client.zone_watched

    backup_watchers = target_zone.get_watchers() # Keep backup reference to send to others
    backup_id = target_zone.get_id()

    client.server.zone_manager.delete_zone(backup_id)

    if arg:
        client.send_ooc('You have deleted zone `{}`.'.format(backup_id))
    else:
        client.send_ooc('You have deleted your zone.')
    client.send_ooc_others('(X) {} [{}] has deleted your zone.'
                           .format(client.displayname, client.id), part_of=backup_watchers)
    client.send_ooc_others('(X) {} [{}] has deleted zone `{}`.'
                           .format(client.displayname, client.id, backup_id),
                           is_officer=True, not_to=backup_watchers)

def ooc_cmd_zone_global(client: ClientManager.Client, arg: str):
    """
    Sends a global message in the OOC chat visible to all users in the zone the user area's belongs
    to who have not disabled global chat.
    Returns an error if the user has global chat off, sends an empty message, or is in an area
    not part of a zone.

    SYNTAX
    /zone_global <message>

    PARAMETERS
    <message>: Message to be sent

    EXAMPLE
    /zone_global Hello World      :: Sends Hello World to global chat.
    """

    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You cannot send an empty message.')

    if client.zone_watched:
        target_zone = client.zone_watched
    elif client.area.in_zone:
        target_zone = client.area.in_zone
    else:
        raise ZoneError('You are not in a zone.')

    targets = target_zone.get_watchers()
    for area in target_zone.get_areas():
        targets.update({c for c in area.clients if c.zone_watched in [None, target_zone]})

    for target in targets:
        target.send_ooc(arg, username='<dollar>ZG[{}][{}]'
                        .format(client.area.id, client.displayname),
                        pred=lambda c: not c.muted_global)

def ooc_cmd_zone_info(client: ClientManager.Client, arg: str):
    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    if not client.zone_watched:
        raise ZoneError('You are not watching a zone.')

    zone = client.zone_watched
    info = f'== Zone {zone.get_id()} ==\r\n{zone.get_info()}'
    client.send_ooc(info)
    client.send_area_info(client.area, -2, False, include_shownames=True)

def ooc_cmd_zone_lights(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles lights on or off in the background for every area in a zone. If turned off,
    the background will change to the server's blackout background. If turned on,
    the background will revert to the background before the blackout one.
    If an area already has the requested light status, has a locked background, or
    has no lights to change, the area is left alone.
    Returns an error if the user is not watching a zone.

    SYNTAX
    /zone_lights

    PARAMETERS
    <new_status>: 'on' or 'off'

    EXAMPLES
    Assuming the user is watching z0, with areas 1-4
    /zone_lights off    :: Turns every light off in areas 1-4.
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify either on or off.')
    if arg not in ['off', 'on']:
        raise ClientError('Expected on or off.')

    if client.zone_watched:
        target_zone = client.zone_watched.get_areas()
        new_lights = (arg == 'on')
    else:
        raise ZoneError('You are not watching a zone.')

    for area in target_zone:
        if area.bg_lock or not area.has_lights:
            continue
        try:
            area.change_lights(new_lights, initiator=client, area=area)
        except AreaError:
          pass

    client.send_ooc('You have turned {} the lights in zone.'
                    .format(arg))
    client.send_ooc_others('(X) {} [{}] has turned {} the lights in your zone.'
                           .format(client.displayname, client.id, arg), is_zstaff=True)

def ooc_cmd_zone_list(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Lists all active zones in the server. For each zone, it lists details such as: zone ID,
    the number of players it has, the areas it contains, and who is watching it.
    Returns an error if there are no active zones.

    SYNTAX
    /zone_list

    PARAMETERS
    None

    EXAMPLES
    /zone_list         :: May return something like this:
    == Active zones ==
    *Zone 1000 [15] (2, 16-116). Watchers: Phantom (16)
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    info = client.server.zone_manager.get_info()
    client.send_ooc(info)

def ooc_cmd_zone_play(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Plays a given track in all areas of the zone, even if not explicitly in the music list.
    It is the way to play custom music in all areas of a zone simultaneously.

    SYNTAX
    /zone_play <track_name>

    PARAMETERS
    <track_name>: Track to play

    EXAMPLES
    Assuming the user is watching zone z0
    /zone_play Trial(AJ).mp3         :: Plays Trial(AJ).mp3 for all areas in zone z0
    /zone_play CustomTrack.mp3       :: Plays CustomTrack.mp3 (will only be audible to users with CustomTrack.mp3) for all areas in zone z0
    """

    try:
        Constants.assert_command(client, arg, is_staff=True, parameters='>0')
    except ArgumentError:
        raise ArgumentError('You must specify a song.')

    if not client.zone_watched:
        raise ZoneError('You are not watching a zone.')

    for zone_area in client.zone_watched.get_areas():
        zone_area.play_track(arg, client, raise_if_not_found=False, reveal_sneaked=False)

    client.send_ooc('You have played track `{}` in your zone.'
                    .format(arg))
    client.send_ooc_others('(X) {} [{}] has played track `{}` in your zone.'
                           .format(client.displayname, client.id, arg), is_zstaff=True)

    # Warn if track is not in the music list
    try:
        client.server.get_song_data(arg, c=client)
    except ServerError.MusicNotFoundError:
        client.send_ooc(f'(X) Warning: `{arg}` is not a recognized track name, so it will not '
                        'loop.')

def ooc_cmd_zone_remove(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Removes an area by name or ID from the zone the user is watching.
    Returns an error if the area identifier does not correspond to an area, if the area is not part
    of the zone the user is watching, or if the user is not watching a zone.

    SYNTAX
    /zone_remove <area_name>
    /zone_remove <area_id>

    PARAMETERS
    <area_name>: Name of the area whose door you want to knock.
    <area_id>: ID of the area whose door you want to knock.

    EXAMPLES
    /zone_remove 0                :: Remove area 0 from the zone
    /zone_remove Courtroom, 2     :: Remove area "Courtroom, 2" from the zone
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=1')

    if not client.zone_watched:
        raise ZoneError('You are not watching a zone.')
    area = Constants.parse_area_names(client, arg).pop()

    target_zone = client.zone_watched
    backup_watchers = client.zone_watched.get_watchers() # In case zone gets automatically deleted
    try:
        target_zone.remove_area(area)
    except ZoneError.AreaNotInZoneError:
        raise ZoneError('Area {} is not part of your zone.'.format(arg))

    # Announce area removal, taking care of using the backup watchers in case the zone got
    # automatically deleted
    client.send_ooc('You have removed area {} from your zone.'.format(area.id))
    client.send_ooc_others('(X) {} [{}] has removed area {} from your zone.'
                           .format(client.displayname, client.id, area.id), part_of=backup_watchers)

    # Announce automatic deletion if needed.
    zone_id = target_zone.get_id()
    if not target_zone.get_areas():
        for c in backup_watchers:
            c.send_ooc('(X) As your zone no longer covers any areas, it has been deleted.')
        client.send_ooc_others('(X) Zone `{}` was automatically deleted as it no longer covered '
                               'any areas.'.format(zone_id), is_officer=True,
                               not_to=backup_watchers)
    # Otherwise, suggest zone watchers who were in the removed area to stop watching the zone
    else:
        for c in area.clients:
            if c.is_staff() and c != client and c in backup_watchers:
                c.send_ooc('(X) Your area has been removed from your zone. To stop receiving its '
                           'notifications, stop watching it with /zone_unwatch')

def ooc_cmd_zone_unwatch(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Makes the user no longer watch the zone they are watching.
    Returns an error if the user is not watching a zone.

    SYNTAX
    /zone_unwatch

    PARAMETERS
    None

    EXAMPLES
    /zone_unwatch           :: Makes the user no longer watch their zone
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')
    if not client.zone_watched:
        raise ClientError('You are not watching any zone.')

    target_zone = client.zone_watched
    target_zone.remove_watcher(client)

    client.send_ooc('You are no longer watching zone `{}`.'.format(target_zone.get_id()))
    if target_zone.get_watchers():
        client.send_ooc_others('(X) {} [{}] is no longer watching your zone.'
                               .format(client.displayname, client.id),
                               part_of=target_zone.get_watchers())
    else:
        client.send_ooc('As you were the last person watching it, your zone has been deleted.')
        client.send_ooc_others('(X) Zone `{}` was automatically deleted as no one was watching it '
                               'anymore.'.format(target_zone.get_id()), is_officer=True)

def ooc_cmd_zone_watch(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Makes the user start watching a zone by ID.
    Returns an error if the user is already watching a zone or if the zone ID does not exist.

    SYNTAX
    /zone_watch <zone_ID>

    PARAMETERS
    <zone_ID>: Identifier of zone to watch

    EXAMPLES
    /zone_watch 1000       :: Makes the user watch zone 1000
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=1')

    try:
        target_zone = client.server.zone_manager.get_zone(arg)
    except KeyError:
        raise ZoneError('`{}` is not a valid zone ID.'.format(arg))

    try:
        target_zone.add_watcher(client)
    except ZoneError.WatcherConflictError:
        raise ZoneError('You cannot watch a zone while watching another.')

    client.send_ooc('You are now watching zone `{}`.'.format(target_zone.get_id()))
    for c in target_zone.get_watchers():
        if c == client:
            continue
    client.send_ooc_others('(X) {} [{}] is now watching your zone.'
                           .format(client.displayname, client.id), is_zstaff=True)

def ooc_cmd_8ball(client: ClientManager.Client, arg: str):
    """
    Calls upon the wisdom of a magic 8 ball. The result is sent to all clients in the sender's area.
    If given a question, it is included as part of the result.

    SYNTAX
    /8ball {question}

    OPTIONAL PARAMETERS
    {question}: Question to ask the magic 8 ball.

    EXAMPLES
    If Phantom is using the magic 8 ball.
    /8ball              :: May return something like "In response to Phantom, the magic 8 ball says `It is certain`."
    /8ball Am I bae?    :: May return something like "In response to Phantom's question `Am I bae?`, the magic 8 ball says `My sources say no`."
    """

    responses = ['It is certain',
                 'It is decidedly so',
                 'Without a doubt',
                 'Yes - definitely',
                 'You may rely on it',
                 'As I see it, yes',
                 'Most likely',
                 'Outlook good',
                 'Yes',
                 'Signs point to yes',
                 'Reply hazy, try again',
                 'Ask again later',
                 'Better not tell you now',
                 'Cannot predict now',
                 'Concentrate and ask again',
                 "Don't count on it",
                 'My reply is no',
                 'My sources say no',
                 'Outlook not so good',
                 'Very doubtful',
                 'No',
                 'As I see it, no',
                 'Unlikely',
                 'Absolutely not',
                 'Certainly not']
    response = random.choice(responses)

    if arg:
        output = ("In response to {}'s question `{}`, the magic 8 ball says `{}`."
                  .format(client.displayname, arg, response))
    else:
        output = ("In response to {}, the magic 8 ball says `{}`."
                  .format(client.displayname, response))
    client.area.broadcast_ooc(output)

    logger.log_server('[{}][{}]called upon the magic 8 ball and it said {}.'
                      .format(client.area.id, client.get_char_name(), response), client)

def ooc_cmd_narrate(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Sends a message from the "Narrator" position to all players in the area. This will override
    any existing IC message, or any hearing properties of the targets.

    SYNTAX
    /narrate <message>

    PARAMETERS
    <message>: Message to send

    EXAMPLES
    /narrate Hello World!   :: Sends `Hello World!` to the people in the area as a narrator.
    """

    arg = arg[:256] # Cap
    Constants.assert_command(client, arg, is_staff=True)

    for c in client.area.clients:
        c.send_ic(msg=arg, bypass_replace=True)

def ooc_cmd_mod_narrate(client: ClientManager.Client, arg: str):
    """ (CM AND MOD ONLY)
    Sends a message from the "Narrator" position to all players in the area using the mod color.
    This will override any existing IC message, or any hearing properties of the targets.

    SYNTAX
    /mod_narrate <message>

    PARAMETERS
    <message>: Message to send

    EXAMPLES
    /mod_narrate Hello World!   :: Sends `Hello World!` to the people in the area as a narrator with mod color.
    """

    arg = arg[:256] # Cap
    Constants.assert_command(client, arg, is_staff=True)

    for c in client.area.clients:
        c.send_ic(msg=arg, color=5, bypass_replace=True)

def ooc_cmd_toggle_allpasses(client: ClientManager.Client, arg: str):
    """ (STAFF ONLY)
    Toggles receiving autopass notifications from players who do not have autopass on. Note this
    does not toggle autopass for everyone.
    Receiving such notifications is turned off by default.

    SYNTAX
    /toggle_allpasses

    PARAMETERS
    None

    EXAMPLE
    /toggle_allpasses
    """

    Constants.assert_command(client, arg, is_staff=True, parameters='=0')

    client.get_nonautopass_autopass = not client.get_nonautopass_autopass
    status = {False: 'no longer', True: 'now'}

    client.send_ooc('You are {} receiving autopass notifications from players without autopass.'
                    .format(status[client.get_nonautopass_autopass]))

def ooc_cmd_cid(client: ClientManager.Client, arg: str):
    """
    Returns the client ID of the given target (number in brackets in /getarea), or the player's if
    not given a target.
    Returns an error if, given a target identifier, it does not match any identifiers visible to
    the player among players in the same area.

    SYNTAX
    /cid <user_ID>

    PARAMETERS
    <user_id>: Either the client ID, character name, edited-to character, custom showname or OOC name of the intended recipient.

    EXAMPLES
    If Phantom_HD is in the same area as the player, iniswapped to Spam_HD, has client ID 3, has showname Phantom and OOC Name ThePhantom
    /cid Phantom_HD     :: Returns 'The client ID of Phantom_HD is 3.'
    /cid Spam_HD        :: Returns 'The client ID of Spam_HD is 3.'
    /cid 3              :: Returns 'The client ID of 3 is 3.'
    /cid Phantom        :: Returns 'The client ID of Phantom is 3.'
    /cid ThePhantom     :: Returns 'The client ID of ThePhantom is 3.'
    /cid                :: Returns 'Your client ID is 0.' (assuming your client ID is actually 0)
    """

    if not arg:
        client.send_ooc('Your client ID is {}.'.format(client.id))
    else:
        cm = client.server.client_manager
        target, _, _ = cm.get_target_public(client, arg, only_in_area=True)
        client.send_ooc('The client ID of {} is {}.'.format(arg, target.id))

def ooc_cmd_party_whisper(client: ClientManager.Client, arg: str):
    """
    Sends an IC personal message to everyone in the sender's party. The messages have the showname
    of the sender and their message, but does not include their sprite.
    Elevated notifications are sent to zone watchers/staff members on whispers to other people,
    which include the message content, so this is not meant to act as a private means of
    communication between players, for which /pm is recommended.
    Whispers sent by sneaked players include an empty showname so as to not reveal their identity,
    except if some members of the party are sneaking as well, in which case they will receive the
    message with showname.
    Deafened recipients will receive a nerfed message if whispered to.
    Non-zone watchers/non-staff players in the same area as the whisperer will be notified that
    they whispered to their target (but will not receive the content of the message), provided they
    are not blind (in which case no notification is sent) and that this was not a self-whisper.
    Returns an error if the player is not part of a party, if the message is empty or if the
    sender is gagged or IC-muted.

    SYNTAX
    /party_whisper <user_ID> <message>

    PARAMETERS
    <user_id>: Either the client ID (number in brackets in /getarea), character name, edited-to character, custom showname or OOC name of the intended recipient.
    <message>: Message to be sent.

    EXAMPLES
    /party_whisper Hey, all!   :: Sends that message to all players of the party.
    """

    try:
        Constants.assert_command(client, arg, parameters='>0')
    except ArgumentError:
        raise ArgumentError('Not enough arguments. Use /party_whisper <message>. Target should '
                            'be ID, char-name, edited-to character, custom showname or OOC-name.')

    party = client.get_party(tc=True)
    if client.is_muted:
        raise ClientError('You have been muted by a moderator.')
    if client.is_gagged:
        raise ClientError('Your attempt at whispering failed because you are gagged.')

    msg = arg[:256] # Cap
    public_area = not client.area.private_area

    client.send_ooc('You whispered `{}` to your party members.'.format(msg))
    client.send_ic(msg=msg, pos=client.pos, cid=client.char_id, showname=client.showname,
                   bypass_deafened_starters=True) # send_ic handles nerfing for deafened

    members = party.get_members()-{client}
    if client.is_visible:
        for target in members:
            target.send_ooc('{} whispered something to your party.'
                            .format(client.displayname), to_deaf=False)
            target.send_ooc('{} seemed to whisper something to your party, but you could not make '
                            'it out.'
                            .format(client.displayname), to_deaf=True, to_blind=False)
            target.send_ooc('Someone seemed to whisper something to your party, but you could '
                            'not make it out.',
                            to_deaf=True, to_blind=True)


            target.send_ic(msg=msg, pos=client.pos, cid=client.char_id,
                           showname=(client.showname if not (target.is_deaf and target.is_blind)
                                     else '???'),
                           bypass_deafened_starters=True) # send_ic handles nerfing for deafened

        if public_area:
            client.send_ooc_others('(X) {} [{}] whispered `{}` to their party ({}).'
                                   .format(client.displayname, client.id, msg, client.area.id),
                                   is_zstaff_flex=True, not_to=members)
            client.send_ooc_others('You see a group of people huddling together.',
                                   in_area=True, to_blind=False, is_zstaff_flex=False,
                                   not_to=members)
        else:
            # For private areas, zone watchers and staff get normal whisper reports if in the same
            # area.
            client.send_ooc_others('(X) You see a group of people huddling together.',
                                   in_area=True, is_zstaff_flex=True, not_to=members)
    else:
        sneaked = {member for member in members if not member.is_visible}
        not_sneaked = members-sneaked
        for target in sneaked:
            target.send_ooc('{} whispered something to your party while sneaking.'
                            .format(client.displayname), to_deaf=False)
            target.send_ooc('{} seemed to whisper something to your party while sneaking, but you '
                            'could not make it out.'
                            .format(client.displayname), to_deaf=True, to_blind=False)
            # No different notification
            target.send_ooc('Someone seemed to whisper something to your party, but you could '
                            'not make it out.',
                            to_deaf=True, to_blind=True)
            target.send_ic(msg=msg, pos=client.pos, cid=client.char_id,
                           showname=(client.showname if not (target.is_deaf and target.is_blind)
                                     else '???'),
                           bypass_deafened_starters=True) # send_ic handles nerfing for deafened

        for target in not_sneaked:
            target.send_ooc('You heard a whisper, but you could not seem to tell where it came '
                            'from.', to_deaf=False)
            target.send_ooc('Your ears seemed to pick up something.', to_deaf=True)
            target.send_ic(msg=msg, pos='jud', showname='???', bypass_deafened_starters=True)

        if public_area:
            client.send_ooc_others('(X) {} [{}] whispered `{}` to their party while sneaking ({}).'
                                   .format(client.displayname, client.id, msg, client.area.id),
                                   is_zstaff_flex=True, not_to=members)
            client.send_ooc_others('You heard a whisper, but you could not seem to tell where it '
                                   'came from.',
                                   in_area=True, to_deaf=False, is_zstaff_flex=False,
                                   not_to=members)
            client.send_ooc_others('Your ears seemed to pick up something.',
                                   in_area=True, to_deaf=True, is_zstaff_flex=True,
                                   not_to=members)
        else:
            # For private areas, zone watchers and staff get normal whisper reports if in the same
            # area.
            client.send_ooc_others('(X) You see a group of people huddling together',
                                   in_area=True, is_zstaff_flex=True, not_to=members)

def ooc_cmd_exec(client: ClientManager.Client, arg: str):
    """
    VERY DANGEROUS. SHOULD ONLY BE ENABLED FOR DEBUGGING.

    DID I MENTION THIS IS VERY DANGEROUS?

    DO NOT ENABLE THIS FUNCTION UNLESS YOU KNOW WHAT YOU ARE DOING.

    I MEAN IT.

    PEOPLE WILL BREAK YOUR SERVER AND POSSIBLY THE HOST MACHINE IT IS ON IF YOU KEEP IT ON.

    DO NOT BE STUPID.

    Executes a Python expression and returns the evaluated expression.
    If passed in a Python statement, it will execute code in the global environment.
    Returns an error if the expression would raise an error in a normal Python environment.

    SYNTAX
    /exec <command>

    PARAMETERS
    <command>

    EXAMPLES
    /exec 1+1                                           :: Returns 2
    /exec while True: client.send_ooc("Hi")             :: Commit sudoku
    """

    # IF YOU WANT TO DISABLE /exec: SET debug TO 0 (debug = 0)
    # IF YOU WANT TO ENABLE /exec: SET debug TO 1 (debug = 1)
    debug = 0
    if not debug:
        return None

    logger.log_print("Attempting to run instruction {}".format(arg))

    try:
        client.server.send_all_cmd_pred('CT', '>>>', arg, pred=lambda c: c == client)
        result = eval(arg)
        if result is not None:
            client.server.send_all_cmd_pred('CT', '', result, pred=lambda c: c == client)
    except Exception:
        try:
            # Temporarily add "client" as a global variable, to allow using
            # expressions such as client.send_ooc("Hi")
            globals()['client'] = client
            exec(arg, globals())
            #client.send_ooc("Executed {}".format(arg))
        except Exception as e:
            try:
                client.server.send_all_cmd_pred('CT', '',
                                                'Python error: {}: {}'.format(type(e).__name__, e),
                                                pred=lambda c: c == client)
            except Exception:
                pass
    globals().pop('client', None) # Don't really want "client" to be a global variable
    return 1    # Indication that /exec is live
