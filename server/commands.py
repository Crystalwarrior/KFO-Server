# tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#possible keys: ip, OOC, id, cname, ipid, hdid
import random
import hashlib
import string
import time

from server.constants import TargetType

from server import logger
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError
from server.pastebin_api import paste_it

def ooc_cmd_switch(client, arg):
    if len(arg) == 0:
        raise ArgumentError('You must specify a character name.')
    try:
        cid = client.server.get_char_id_by_name(arg)
    except ServerError:
        raise
    try:
        client.change_character(cid, client.is_mod)
    except ClientError:
        raise
    client.send_host_message('Character changed.')
    
def ooc_cmd_bg(client, arg):
    if client.hub.status.lower().startswith('casing') and not client.is_cm:
        raise AreaError(
            'Hub is {} - only the CM can change /bg.'.format(client.hub.status))
    if len(arg) == 0:
        raise ArgumentError('You must specify a name. Use /bg <background>.')
    if not client.is_mod and not client.is_cm and client.area.bg_lock == True:
        raise AreaError("This area's background is locked")
    try:
        client.area.change_background(arg)
    except AreaError:
        raise
    client.area.send_host_message('{} changed the background to {}.'.format(client.get_char_name(), arg))
    logger.log_server('[{}][{}]Changed background to {}'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_bglock(client,arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.bg_lock  == True:
        client.area.bg_lock = False
    else:
        client.area.bg_lock = True
    client.area.send_host_message('A mod has set the background lock to {}.'.format(client.area.bg_lock))
    logger.log_server('[{}][{}]Changed bglock to {}'.format(client.area.id, client.get_char_name(), client.area.bg_lock), client)
    


def ooc_cmd_evidence_mod(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if not arg:
        client.send_host_message('current evidence mod: {}'.format(client.area.evidence_mod))
        return
    if arg in ['FFA', 'Mods', 'CM', 'HiddenCM']:
        if arg == client.area.evidence_mod:
            client.send_host_message('current evidence mod: {}'.format(client.area.evidence_mod))
            return
        if client.area.evidence_mod == 'HiddenCM':
            for i in range(len(client.area.evi_list.evidences)):
                client.area.evi_list.evidences[i].pos = 'all'
        client.area.evidence_mod = arg
        client.send_host_message('current evidence mod: {}'.format(client.area.evidence_mod))
        return
    else:
        raise ArgumentError('Wrong Argument. Use /evidence_mod <MOD>. Possible values: FFA, CM, Mods, HiddenCM')
        return
        
def ooc_cmd_allow_iniswap(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    client.area.iniswap_allowed = not client.area.iniswap_allowed
    answer = {True: 'allowed', False: 'forbidden'}
    client.send_host_message('iniswap is {}.'.format(answer[client.area.iniswap_allowed]))
    return
    
    
    
def ooc_cmd_roll(client, arg):
    roll_max = 11037
    if len(arg) != 0:
        try:
            val = list(map(int, arg.split(' ')))
            if not 1 <= val[0] <= roll_max:
                raise ArgumentError('Roll value must be between 1 and {}.'.format(roll_max))
        except ValueError:
            raise ArgumentError('Wrong argument. Use /roll [<max>] [<num of rolls>]')
    else:
        val = [6]
    if len(val) == 1:
        val.append(1)
    if len(val) > 2:
        raise ArgumentError('Too many arguments. Use /roll [<max>] [<num of rolls>]')
    if val[1] > 20 or val[1] < 1:
        raise ArgumentError('Num of rolls must be between 1 and 20')
    roll = ''
    for i in range(val[1]):
        roll += str(random.randint(1, val[0])) + ', '
    roll = roll[:-2]
    if val[1] > 1:
        roll = '(' + roll + ')'
    client.area.send_host_message('{} rolled {} out of {}.'.format(client.get_char_name(), roll, val[0]))
    logger.log_server(
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), roll, val[0]))
        
def ooc_cmd_rollp(client, arg):
    roll_max = 11037
    if len(arg) != 0:
        try:
            val = list(map(int, arg.split(' ')))
            if not 1 <= val[0] <= roll_max:
                raise ArgumentError('Roll value must be between 1 and {}.'.format(roll_max))
        except ValueError:
            raise ArgumentError('Wrong argument. Use /roll [<max>] [<num of rolls>]')
    else:
        val = [6]
    if len(val) == 1:
        val.append(1)
    if len(val) > 2:
        raise ArgumentError('Too many arguments. Use /roll [<max>] [<num of rolls>]')
    if val[1] > 20 or val[1] < 1:
        raise ArgumentError('Num of rolls must be between 1 and 20')
    roll = ''
    for i in range(val[1]):
        roll += str(random.randint(1, val[0])) + ', '
    roll = roll[:-2]
    if val[1] > 1:
        roll = '(' + roll + ')'
    client.send_host_message('{} rolled {} out of {}.'.format(client.get_char_name(), roll, val[0]))
    client.area.send_host_message('{} rolled.'.format(client.get_char_name(), roll, val[0]))
    SALT = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    logger.log_server(
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), hashlib.sha1((str(roll) + SALT).encode('utf-8')).hexdigest() + '|' + SALT, val[0]))

def ooc_cmd_currentmusic(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.current_music == '':
        raise ClientError('There is no music currently playing.')
    client.send_host_message('The current music is {} and was played by {}.'.format(client.area.current_music,
                                                                                    client.area.current_music_player))

def ooc_cmd_coinflip(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    coin = ['heads', 'tails']
    flip = random.choice(coin)
    client.area.send_host_message('{} flipped a coin and got {}.'.format(client.get_char_name(), flip))
    logger.log_server(
        '[{}][{}]Used /coinflip and got {}.'.format(client.area.id, client.get_char_name(), flip))
    
def ooc_cmd_motd(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.send_motd()
    
def ooc_cmd_pos(client, arg):
    if client.area.pos_lock:
        raise ClientError('Positions are locked in this area.')
    if len(arg) == 0:
        client.change_position()
        client.send_host_message('Position reset.')
    else:
        try:
            client.change_position(arg)
        except ClientError:
            raise
        client.area.broadcast_evidence_list()
        client.send_host_message('Position changed.')   

def ooc_cmd_poslock(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if not arg:
        client.send_host_message(
            'Poslock is currently {}.'.format(client.area.pos_lock))
        return
    if arg == 'clear':
        client.area.pos_lock = None
        client.area.send_host_message('Position lock cleared.')
        return
    if arg not in ('def', 'pro', 'hld', 'hlp', 'jud', 'wit'):
        raise ClientError('Invalid pos.')
    client.area.pos_lock = arg
    client.area.send_host_message('Locked pos into {}.'.format(arg))

def ooc_cmd_forcepos(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if client.area.pos_lock:
        raise ClientError('Positions are locked in this area.')

    args = arg.split()

    if len(args) < 1:
        raise ArgumentError(
            'Not enough arguments. Use /forcepos <pos> <target>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".')

    targets = []

    pos = args[0]
    if len(args) > 1:
        targets = client.server.client_manager.get_targets(
            client, TargetType.CHAR_NAME, " ".join(args[1:]), True)
        if len(targets) == 0 and args[1].isdigit():
            targets = client.server.client_manager.get_targets(
                client, TargetType.ID, int(arg[1]), True)
        if len(targets) == 0:
            targets = client.server.client_manager.get_targets(
                client, TargetType.OOC_NAME, " ".join(args[1:]), True)
        if len(targets) == 0:
            raise ArgumentError('No targets found.')
    else:
        for c in client.area.clients:
            targets.append(c)



    for t in targets:
        try:
            t.change_position(pos)
            t.area.broadcast_evidence_list()
            t.send_host_message('Forced into /pos {}.'.format(pos))
        except ClientError:
            raise

    client.area.send_host_message(
        '{} forced {} client(s) into /pos {}.'.format(client.get_char_name(), len(targets), pos))
    logger.log_server(
        '[{}][{}]Used /forcepos {} for {} client(s).'.format(client.area.id, client.get_char_name(), pos, len(targets)))

def ooc_cmd_help(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    help_url = 'https://github.com/AttorneyOnline/tsuserver3/blob/master/README.md'
    help_msg = 'Available commands, source code and issues can be found here: {}'.format(help_url)
    client.send_host_message(help_msg)
        
def ooc_cmd_kick(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /kick <ipid>.')
    targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    if targets:
        for c in targets:
            logger.log_server('Kicked {}.'.format(c.ipid), client)
            client.send_host_message("{} was kicked.".format(c.get_char_name()))
            c.disconnect()
    else:
        client.send_host_message("No targets found.")
        
def ooc_cmd_ban(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    try:
        ipid = int(arg.strip())
    except:
        raise ClientError('You must specify ipid')
    try:
        client.server.ban_manager.add_ban(ipid)
    except ServerError:
        raise
    if ipid != None:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, ipid, False)
        if targets:
            for c in targets:
                c.disconnect()
            client.send_host_message('{} clients was kicked.'.format(len(targets)))
        client.send_host_message('{} was banned.'.format(ipid))
        logger.log_server('Banned {}.'.format(ipid), client)
        
def ooc_cmd_unban(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    try:
        client.server.ban_manager.remove_ban(int(arg.strip()))
    except:
        raise ClientError('You must specify \'hdid\'')
    logger.log_server('Unbanned {}.'.format(arg), client)
    client.send_host_message('Unbanned {}'.format(arg))


def ooc_cmd_play(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a song.')
    client.area.play_music(arg, client.char_id, -1)
    client.area.add_music_playing(client, arg)
    logger.log_server('[{}][{}]Changed music to {}.'.format(client.area.id, client.get_char_name(), arg), client)
    
def ooc_cmd_mute(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        c = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)[0]
        c.is_muted = True
        client.send_host_message('{} existing client(s).'.format(c.get_char_name()))
    except:
        client.send_host_message("No targets found. Use /mute <id> for mute")

def ooc_cmd_unmute(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        c = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0]
        c.is_muted = False
        client.send_host_message('{} existing client(s).'.format(c.get_char_name()))
    except:
        client.send_host_message("No targets found. Use /mute <id> for mute")

def ooc_cmd_iclogs(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')

    args = arg.split()
    area = client.area

    if len(args) == 0:
        args = [10]

    if args[0] == "link":
        client.send_host_message("Fetching pastebin for full IC log...")
        logs = '[{}] IC logs for area [{}] {} in hub [{}] {}'.format(time.strftime(
            "%d-%b-%y|%H:%M:%S UTC", area.record_start), area.id, area.name, client.hub.id, client.hub.name)
        for line in area.recorded_messages:
            logs += '\n{}'.format(line)
        #print(logs)
        try:
            paste = paste_it()
            link = paste.create_paste(logs, 'IC logs for area [{}] {} in hub [{}] {}'.format(
                area.id, area.name, client.hub.id, client.hub.name))
            client.send_host_message('Success! Pastebin: {}'.format(link))
        except:
            raise ArgumentError('Failed...')

    if len(args) > 1:
        try:
            area = client.hub.get_area_by_id(int(args[1]))
        except:
            raise ArgumentError('Invalid area! Try /iclogs [num_lines OR "link"] [area_id]')

    try:
        lines = int(args[0])
        if lines > 50:
            lines = 50
        if lines < 0:
            raise
        i = 0
        for line in area.recorded_messages[-lines:]:
            if i >= lines:
                break
            client.send_host_message(line)
            i += 1
        if i == 0:
            client.send_host_message('Error: logs are empty!')
            return
        client.send_host_message('Displaying last {} IC messages in area [{}] {} of hub {}.'.format(i, area.id, area.name, client.hub.id))
    except:
        raise ArgumentError(
            'Bad number of lines! Try /iclogs [num_lines OR "link"] [area_id]')

def ooc_cmd_login(client, arg):
    if len(arg) == 0:
        raise ArgumentError('You must specify the password.')
    try:
        client.auth_mod(arg)
    except ClientError:
        raise
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.send_host_message('Logged in as a moderator.')
    logger.log_server('Logged in as moderator.', client)
    
def ooc_cmd_g(client, arg):
    if client.muted_global:
        raise ClientError('Global chat toggled off.')
    if len(arg) == 0:
        raise ArgumentError("You can't send an empty message.")
    client.server.broadcast_global(client, arg)
    logger.log_server('[{}][{}][GLOBAL]{}.'.format(client.hub.id, client.get_char_name(), arg), client)

def ooc_cmd_a(client, arg):
    if len(arg) == 0:
        raise ArgumentError("You can't send an empty message.")
    cm = ''
    if client.is_cm:
        cm = '[CM]'
    elif client.is_mod:
        cm = '[MOD]'
    client.area.send_command('CT', '~A{}[{}]'.format(
        cm, client.get_char_name()), arg)
    logger.log_server('[{}][{}][AOOC]{}.'.format(client.hub.id, client.get_char_name(), arg), client)

def ooc_cmd_gm(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if client.muted_global:
        raise ClientError('You have the global chat muted.')
    if len(arg) == 0:
        raise ArgumentError("Can't send an empty message.")
    client.server.broadcast_global(client, arg, True)
    logger.log_server('[{}][{}][GLOBAL-MOD]{}.'.format(client.area.id, client.get_char_name(), arg), client)
    
def ooc_cmd_lm(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError("Can't send an empty message.")
    client.area.send_command('CT', '{}[MOD][{}]'
                             .format(client.server.config['hostname'], client.get_char_name()), arg)
    logger.log_server('[{}][{}][LOCAL-MOD]{}.'.format(client.area.id, client.get_char_name(), arg), client)
    
def ooc_cmd_announce(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError("Can't send an empty message.")
    client.server.send_all_cmd_pred('CT', '{}'.format(client.server.config['hostname']),
                                    '=== Announcement ===\r\n{}\r\n=================='.format(arg))
    logger.log_server('[{}][{}][ANNOUNCEMENT]{}.'.format(client.area.id, client.get_char_name(), arg), client)
    
def ooc_cmd_toggleglobal(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.muted_global = not client.muted_global
    glob_stat = 'on'
    if client.muted_global:
        glob_stat = 'off'
    client.send_host_message('Global chat turned {}.'.format(glob_stat))

def ooc_cmd_toggleooc(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    client.hub.is_ooc_muted = not client.hub.is_ooc_muted
    glob_stat = 'on'
    if client.hub.is_ooc_muted:
        glob_stat = 'off'
    client.hub.send_host_message('OOC chat turned {}.'.format(glob_stat))

def ooc_cmd_need(client, arg):
    if client.muted_adverts:
        raise ClientError('You have advertisements muted.')
    if len(arg) == 0:
        raise ArgumentError("You must specify what you need.")
    client.server.broadcast_need(client, arg)
    logger.log_server('[{}][{}][NEED]{}.'.format(client.hub.id, client.get_char_name(), arg), client)
    
def ooc_cmd_toggleadverts(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.muted_adverts = not client.muted_adverts
    adv_stat = 'on'
    if client.muted_adverts:
        adv_stat = 'off'
    client.send_host_message('Advertisements turned {}.'.format(adv_stat))
    
def ooc_cmd_doc(client, arg):
    if len(arg) == 0:
        client.send_host_message('Document: {}'.format(client.hub.doc))
        logger.log_server(
            '[{}][{}]Requested document. Link: {}'.format(client.area.id, client.get_char_name(), client.hub.doc))
    else:
        if client.hub.status.lower().startswith('casing') and not client.is_cm:
            raise AreaError(
                'Hub is {} - only the CM can change /doc.'.format(client.hub.status))
        client.hub.change_doc(arg)
        client.hub.send_host_message('{} changed the doc link.'.format(client.get_char_name()))
        logger.log_server('[{}][{}]Changed document to: {}'.format(client.hub.id, client.get_char_name(), arg))

def ooc_cmd_desc(client, arg):
    if len(arg) == 0:
        client.send_host_message('Area Description: {}'.format(client.area.desc))
        logger.log_server(
            '[{}][{}]Requested description: {}'.format(client.area.id, client.get_char_name(), client.area.desc))
    else:
        if client.hub.status.lower().startswith('casing') and not client.is_cm:
            raise AreaError(
                'Hub is {} - only the CM can change /desc for this area.'.format(client.hub.status))
        client.area.desc = arg
        client.area.send_host_message('{} changed the area description.'.format(client.get_char_name()))
        logger.log_server('[{}][{}]Changed document to: {}'.format(client.area.id, client.get_char_name(), arg))

def ooc_cmd_cleardoc(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    client.area.send_host_message('{} cleared the doc link.'.format(client.get_char_name()))
    logger.log_server('[{}][{}]Cleared document. Old link: {}'
                      .format(client.area.id, client.get_char_name(), client.area.doc))
    client.area.change_doc()


def ooc_cmd_status(client, arg):
    if len(arg) == 0:
        client.send_host_message('Current status: {}'.format(client.hub.status))
    else:
        if not client.is_cm and not client.is_mod:
            raise ClientError('Only CM or mods can change status.')
        try:
            client.hub.change_status(arg)
            client.hub.send_host_message('{} changed status to {}.'.format(client.get_char_name(), client.hub.status))
            logger.log_server(
                '[{}][{}]Changed status to {}'.format(client.hub.id, client.get_char_name(), client.hub.status))
        except AreaError:
            raise

def ooc_cmd_online(client, _):
    client.send_player_count()

def ooc_cmd_hub(client, arg):
    args = arg.split()
    if len(args) == 0:
        client.send_hub_list()
        return

    try:
        hub = client.server.hub_manager.get_hub_by_id_or_name(
            ' '.join(args[0:]))
        client.change_hub(hub)
    except ValueError:
        raise ArgumentError('Hub ID must be a number or name.')
    except (AreaError, ClientError):
        raise
        
def ooc_cmd_area(client, arg):
    args = arg.split()
    casing = client.hub.status.lower().startswith('casing')
    if len(args) == 0:
        client.send_area_list(casing, casing)
        return

    try:
        area = client.hub.get_area_by_id_or_name(' '.join(args[0:]))

        if area.is_locked and not client.is_mod and not client.is_cm and not client.ipid in area.invite_list:
            raise ClientError("That area is locked!")
        if area != client.area and casing and len(client.area.accessible) > 0 and area.id not in client.area.accessible and not client.is_cm and not client.is_mod:
            raise AreaError(
                'Area ID not accessible from your current area!')
        client.change_area(area)
    except ValueError:
        raise ArgumentError('Area ID must be a number or name.')
    except (AreaError, ClientError):
        raise

def ooc_cmd_area_add(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')

    if client.hub.cur_id < client.hub.max_areas:
        client.hub.create_area('Area {}'.format(client.hub.cur_id), True,
                           client.server.backgrounds[0], False, None, 'FFA', True, True, True, [])
        client.hub.send_host_message(
            'New area created! ({}/{})'.format(client.hub.cur_id, client.hub.max_areas))
    else:
        raise AreaError('Too many areas! ({}/{})'.format(client.hub.cur_id, client.hub.max_areas))
    
def ooc_cmd_area_remove(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    args = arg.split()
    if len(args) == 0:
        args = [client.area.id]

    if len(args) == 1:
        try:
            area = client.hub.get_area_by_id(int(args[0]))
            if not area.can_remove:
                raise AreaError('This area cannot be removed!')
            client.hub.send_host_message('Area {} ({}) removed! ({}/{})'.format(
                area.id, area.name, client.hub.cur_id-1, client.hub.max_areas))
            client.hub.remove_area(area)
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
        except (AreaError, ClientError):
            raise
    else:
        raise ArgumentError('Invalid number of arguments. Use /area <id>.')

def ooc_cmd_rename(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if not client.area.can_rename:
        raise ClientError('This area cannot be renamed!')

    if len(arg) == 0:
        client.area.name = 'Area {}'.format(client.area.id)
    else:
        client.area.name = arg[:24]
    
    client.area.send_host_message('Area renamed to {}.'.format(client.area.name))

def ooc_cmd_pm(client, arg):
    args = arg.split()
    key = ''
    msg = None
    if len(args) < 2:
        raise ArgumentError('Not enough arguments. use /pm <target> <message>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".')

    targets = []
    if args[0].lower()[:2] in ['cm', 'gm']:
        targets = client.hub.get_cm_list()
        key = TargetType.ID
    if len(targets) == 0:
        targets = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, arg, False)
        key = TargetType.CHAR_NAME
    if len(targets) == 0 and args[0].isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
        key = TargetType.ID
    if len(targets) == 0:
        targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, False)
        key = TargetType.OOC_NAME
    if len(targets) == 0:
        raise ArgumentError('No targets found.')
    try:
        if key == TargetType.ID:
            msg = ' '.join(args[1:])
        else:
            if key == TargetType.CHAR_NAME:
                msg = arg[len(targets[0].get_char_name()) + 1:]
            if key == TargetType.OOC_NAME:
                msg = arg[len(targets[0].name) + 1:]
    except:
        raise ArgumentError('Not enough arguments. Use /pm <target> <message>.')
    for c in targets:
        if c.pm_mute:
            raise ClientError('User {} muted all pm conversation'.format(c.name))
        else:
            c.send_host_message('PM from [{}] {} in {} ({}): {}'.format(client.id, client.name, client.hub.name, client.get_char_name(), msg))
            c.hub.send_to_cm('[PMLog] PM from [{}] {} ({}) to [{}] {} in {}: {}'.format(client.id, client.name, client.get_char_name(), c.id, c.name, client.hub.name, msg), targets)
            client.send_host_message('PM sent to [{}] {}. Message: {}'.format(c.id, c.name, msg))
 
def ooc_cmd_mutepm(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.pm_mute = not client.pm_mute
    client.send_host_message({True:'You stopped receiving PMs', False:'You are now receiving PMs'}[client.pm_mute]) 

def ooc_cmd_charselect(client, arg):
    if not arg:
        client.char_select()
    else:
        if client.is_mod:
            try:
                client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].char_select()
            except:
                raise ArgumentError('Wrong arguments. Use /charselect <target\'s id>')
                
def ooc_cmd_reload(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    try:
        client.reload_character()
    except ClientError:
        raise
    client.send_host_message('Character reloaded.') 
    
def ooc_cmd_randomchar(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    try:
        free_id = client.area.get_rand_avail_char_id()
    except AreaError:
        raise
    try:
        client.change_character(free_id)
    except ClientError:
        raise
    client.send_host_message('Randomly switched to {}'.format(client.get_char_name()))
    
def ooc_cmd_getarea(client, arg):
    # if client.hub.status.lower().startswith('casing') and not client.is_cm:
    #     raise AreaError('Hub is {} - /getarea functionality disabled.'.format(client.hub.status))
    id = client.area.id
    if len(arg) > 0:
        if not client.is_cm and not client.is_mod:
            raise ClientError('You must be authorized to /getarea <id>.')
        id = int(arg)
    client.send_area_info(id, False)

def ooc_cmd_hide(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /hide <id>.')
    if targets:
        c = targets[0]
        if c.hidden:
            raise ClientError(
                'Client [{}] {} already hidden!'.format(c.id, c.name))
        c.hide(True)
        client.send_host_message(
            'You have hidden [{}] {} from /getarea.'.format(c.id, c.name))
    else:
        client.send_host_message('No targets found.')

def ooc_cmd_unhide(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = client.server.client_manager.get_targets(
            client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /unhide <id>.')
    if targets:
        c = targets[0]
        if not c.hidden:
            raise ClientError(
                'Client [{}] {} already revealed!'.format(c.id, c.name))
        c.hide(False)
        client.send_host_message('You have revealed [{}] {} for /getarea.'.format(c.id, c.name))
    else:
        client.send_host_message('No targets found.')

# def ooc_cmd_blind(client, arg):
#     if not client.is_cm and not client.is_mod:
#         raise ClientError('You must be authorized to do that.')
#     elif len(arg) == 0:
#         raise ArgumentError('You must specify a target.')
#     try:
#         targets = client.server.client_manager.get_targets(
#             client, TargetType.ID, int(arg), False)
#     except:
#         raise ArgumentError('You must specify a target. Use /blind <id>.')
#     if targets:
#         c = targets[0]
#         if c.hidden:
#             raise ClientError(
#                 'Client [{}] {} already blinded!'.format(c.id, c.name))
#         c.blind(True)
#         client.send_host_message(
#             'You have blinded [{}] {} from using /getarea and seeing non-broadcasted IC messages.'.format(c.id, c.name))
#     else:
#         client.send_host_message('No targets found.')

# def ooc_cmd_unblind(client, arg):
#     if not client.is_cm and not client.is_mod:
#         raise ClientError('You must be authorized to do that.')
#     elif len(arg) == 0:
#         raise ArgumentError('You must specify a target.')
#     try:
#         targets = client.server.client_manager.get_targets(
#             client, TargetType.ID, int(arg), False)
#     except:
#         raise ArgumentError('You must specify a target. Use /unblind <id>.')
#     if targets:
#         c = targets[0]
#         if not c.hidden:
#             raise ClientError(
#                 'Client [{}] {} already unblinded!'.format(c.id, c.name))
#         c.blind(False)
#         client.send_host_message(
#             'You have revealed [{}] {} for using /getarea and seeing non-broadcasted IC messages.'.format(c.id, c.name))
#     else:
#         client.send_host_message('No targets found.')

def ooc_cmd_getareas(client, arg):
    if client.hub.status.lower().startswith('casing') and not client.is_cm:
        raise AreaError('Hub is {} - /getareas functionality disabled.'.format(client.hub.status))
    client.send_area_info(-1, False)
    
def ooc_cmd_mods(client, arg):
    if client.hub.status.lower().startswith('casing') and not client.is_cm:
        raise AreaError('Hub is {} - /getarea functionality disabled.'.format(client.hub.status))
    client.send_area_info(-1, True)  
    
def ooc_cmd_evi_swap(client, arg):
    args = list(arg.split(' '))
    if len(args) != 2:
        raise ClientError("you must specify 2 numbers")
    try:
        client.area.evi_list.evidence_swap(client, int(args[0]), int(args[1]))
        client.area.broadcast_evidence_list()
    except:
        raise ClientError("you must specify 2 numbers")
     
def ooc_cmd_cm(client, arg):
    if len(arg) > 0:
        if not client.is_cm or client.hub.master != client:
            raise ClientError('You must be the master CM to promote co-CM\'s.')
        try:
            c = client.server.client_manager.get_targets(
                client, TargetType.ID, int(arg), False)[0]
            if c == client:
                raise
            if c.is_cm:
                c.is_cm = False
                client.hub.send_host_message(
                    '{} is no longer a co-CM.'.format(c.get_char_name()))
                c.send_host_message(
                    'You are no longer a co-CM of hub {}.'.format(client.hub.name))
            else:
                c.is_cm = True
                client.hub.send_host_message(
                    '{} has been made a co-CM.'.format(c.get_char_name()))
                c.send_host_message(
                    'You have been made a co-CM of hub {} by {}.'.format(client.hub.name, client.get_char_name()))
        except:
            raise ClientError('You must specify a target. Use /cm <id>')
    else:
        if not client.hub.allow_cm:
            raise ClientError('You can\'t become a master CM in this hub')
        if not client.hub.master and (len(client.hub.get_cm_list()) <= 0 or client.is_cm):
            client.hub.master = client
            client.is_cm = True
            if client.area.evidence_mod == 'HiddenCM':
                client.area.broadcast_evidence_list()
            client.hub.send_host_message('{} is master CM in this hub now.'.format(client.get_char_name()))
        else:
            raise ClientError('Master CM exists. Use /cm <id>')

def ooc_cmd_cms(client, arg):
    client.send_host_message('=CM\'s in this hub:=')
    for cm in client.hub.get_cm_list():
        m = 'co-'
        if client.hub.master == cm:
            m = 'Master '
        client.send_host_message('=>{}CM [{}] {}'.format(m, cm.id, cm.get_char_name()))

def ooc_cmd_broadcast_ic(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('Only CM or mods can broadcast IC.')
    if not arg or arg == 'clear':
        client.broadcast_ic.clear()
        client.send_host_message('You have cleared the broadcast_ic list.')
    else:
        if arg == 'all':
            client.broadcast_ic.clear()
            for area in client.hub.areas:
                client.broadcast_ic.append(area.id)
        else:
            arg = arg.split()
            for a in arg:
                try:
                    client.broadcast_ic.append(int(a))
                except:
                    raise ClientError('Invalid area ID.')
        client.send_host_message('You will now broadcast IC across areas {} in this hub.'.format(client.broadcast_ic))

def ooc_cmd_area_access(client, arg):
    if not arg:
        client.send_host_message(
            'Areas that can be accessed from this area: {}.'.format(client.area.accessible))
        return

    if not client.is_cm and not client.is_mod:
        raise ClientError('Only CM or mods can set area accessibility.')

    if arg == 'clear' or arg == 'all':
        client.area.accessible.clear()
        client.send_host_message('You have cleared the area accessibility list.')
    else:
        arg = arg.split()
        for a in arg:
            if client.area.id == int(a):
                continue
            try:
                client.area.accessible.append(int(a))
            except:
                raise ClientError('Invalid area ID.')
        client.area.send_host_message(
            'Areas that can now be accessed from this area: {}.'.format(client.area.accessible))

def ooc_cmd_unmod(client, arg):
    client.is_mod = False
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.send_host_message('you\'re not a mod now')
    
def ooc_cmd_lockarea(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('Only CM or mods can lock the area.')
    args = []
    if arg == 'all':
        for area in client.hub.areas:
            args.append(area.id)
    elif len(arg) == 0:
        args = [client.area.id]
    else:
        args = arg.split()
    
    i = 0
    for area in client.hub.areas:
        if area.id in args:
            if not area.locking_allowed:
                client.send_host_message(
                    'Area locking is disabled in area {}.'.format(area.id))
                continue
            if area.is_locked:
                client.send_host_message('Area is already locked.')
                continue
            
            area.lock()
            i += 1
    client.send_host_message('Locked {} areas.'.format(i))
        
def ooc_cmd_unlockarea(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('Only CM or mods can unlock the area.')
    args = []
    if arg == 'all':
        for area in client.hub.areas:
            args.append(area.id)
    elif len(arg) == 0:
        args = [client.area.id]
    else:
        args = arg.split()
    
    i = 0
    for area in client.hub.areas:
        if area.id in args:
            if not area.locking_allowed:
                client.send_host_message(
                    'Area locking is disabled in area {}.'.format(area.id))
            if not area.is_locked:
                client.send_host_message('Area is already unlocked.')
            
            area.unlock()
            i += 1
    client.send_host_message('Unlocked {} areas.'.format(i))

def ooc_cmd_savehub(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('Only CM or mods can save the hub.')
    area = client.hub.default_area()
    area.evi_list.add_evidence(client, '--HUB SAVE DATA--', client.hub.save(), '2.png', 'all')
    area.broadcast_evidence_list()
    client.send_host_message('The hub data has been saved in an evidence file in area [{}] {}.'.format(area.id, area.name))

def ooc_cmd_loadhub(client, arg):
    client.send_host_message('Due to the character limit tied to the OOC commands, to load hub save data you must:\n1: Create a piece of evidence\n2: Set its description to the save data\n3: Change its name to /loadhub, press enter\n4: Press the [X] button to upload it\n5:???\n6: Profit!')

def ooc_cmd_akick(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if not arg:
        raise ClientError('You must specify a target. Use /akick <id> [destination #] [hub #]')
    arg = arg.split()
    targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg[0]), False)
    output = [0, 0]
    if targets:
        try:
            for c in targets:
                if len(arg) == 1:
                    area = client.server.hub_manager.default_hub().get_area_by_id(int(0))
                else:
                    try:
                        if len(arg) > 2 and client.is_mod:
                            hub = client.server.hub_manager.get_hub_by_id(int(arg[2]))
                            output[1] = arg[2]
                        else:
                            hub = client.hub
                            output[1] = client.hub.id
                        area = hub.get_area_by_id(int(arg[1]))
                        output[0] = arg[1]
                    except AreaError:
                        raise
                client.send_host_message("Attempting to kick {} to area {} [Hub {}].".format(
                    c.get_char_name(), output[0], output[1]))
                if c.area.is_locked:
                    c.area.invite_list.pop(c.ipid)
                if area.is_locked:
                    area.invite_list[c.ipid] = None
                c.change_area(area)
                c.send_host_message("You were kicked from the area to area {} [Hub {}].".format(output[0], output[1]))
        except AreaError:
            raise
        except ClientError:
            raise
    else:
        client.send_host_message("No targets found.")
    
def ooc_cmd_ooc_mute(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /ooc_mute <OOC-name>.')
    targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, False)
    if not targets:
        raise ArgumentError('Targets not found. Use /ooc_mute <OOC-name>.')
    for target in targets:
        target.is_ooc_muted = True
    client.send_host_message('Muted {} existing client(s).'.format(len(targets)))

def ooc_cmd_ooc_unmute(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /ooc_mute <OOC-name>.')
    targets = client.server.client_manager.get_targets(client, TargetType.ID, arg, False)
    if not targets:
        raise ArgumentError('Target not found. Use /ooc_mute <OOC-name>.')
    for target in targets:
        target.is_ooc_muted = False
    client.send_host_message('Unmuted {} existing client(s).'.format(len(targets)))

def ooc_cmd_disemvowel(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /disemvowel <id>.')
    if targets:
        for c in targets:
            logger.log_server('Disemvowelling {}.'.format(c.get_ip()), client)
            c.disemvowel = True
        client.send_host_message('Disemvowelled {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')

def ooc_cmd_undisemvowel(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /disemvowel <id>.')
    if targets:
        for c in targets:
            logger.log_server('Undisemvowelling {}.'.format(c.get_ip()), client)
            c.disemvowel = False
        client.send_host_message('Undisemvowelled {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')

def ooc_cmd_blockdj(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /blockdj <id>.')
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
         raise ArgumentError('You must enter a number. Use /blockdj <id>.')
    if not targets:
        raise ArgumentError('Target not found. Use /blockdj <id>.')
    for target in targets:
        target.is_dj = False
        target.send_host_message('A moderator muted you from changing the music.')
    client.send_host_message('blockdj\'d {}.'.format(targets[0].get_char_name()))

def ooc_cmd_unblockdj(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /unblockdj <id>.')
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
         raise ArgumentError('You must enter a number. Use /unblockdj <id>.')
    if not targets:
        raise ArgumentError('Target not found. Use /blockdj <id>.')
    for target in targets:
        target.is_dj = True
        target.send_host_message('Now you can change music.')
    client.send_host_message('Unblockdj\'d {}.'.format(targets[0].get_char_name()))

def ooc_cmd_rolla_reload(client, arg):
    if not client.is_mod:
        raise ClientError('You must be a moderator to load the ability dice configuration.')
    rolla_reload(client.area)
    client.send_host_message('Reloaded ability dice configuration.')

def rolla_reload(area):
    try:
        import yaml
        with open('config/dice.yaml', 'r') as dice:
            area.ability_dice = yaml.load(dice)
    except:
        raise ServerError('There was an error parsing the ability dice configuration. Check your syntax.')

def ooc_cmd_rolla_set(client, arg):
    if not hasattr(client.area, 'ability_dice'):
        rolla_reload(client.area)
    available_sets = client.area.ability_dice.keys()
    if len(arg) == 0:
        raise ArgumentError('You must specify the ability set name.\nAvailable sets: {}'.format(available_sets))
    if arg in client.area.ability_dice:
        client.ability_dice_set = arg
        client.send_host_message("Set ability set to {}.".format(arg))
    else:
        raise ArgumentError('Invalid ability set \'{}\'.\nAvailable sets: {}'.format(arg, available_sets))

def ooc_cmd_rolla(client, arg):
    if not hasattr(client.area, 'ability_dice'):
        rolla_reload(client.area)
    if not hasattr(client, 'ability_dice_set'):
        raise ClientError('You must set your ability set using /rolla_set <name>.')
    ability_dice = client.area.ability_dice[client.ability_dice_set]
    max_roll = ability_dice['max'] if 'max' in ability_dice else 6
    roll = random.randint(1, max_roll)
    ability = ability_dice[roll] if roll in ability_dice else "Nothing happens"
    client.area.send_host_message(
        '{} rolled a {} (out of {}): {}.'.format(client.get_char_name(), roll, max_roll, ability))
        
def ooc_cmd_refresh(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len (arg) > 0:
        raise ClientError('This command does not take in any arguments!')
    else:
        try:
            client.server.refresh()
            client.send_host_message('You have reloaded the server.')
        except ServerError:
            raise

def ooc_cmd_sfx(client, arg):
    if not client.is_cm and not client.is_mod:
        raise ClientError('You must be a CM or moderator to use this command.')
    if len(arg) == 0:
        raise ArgumentError('Not enough arguments. Use /sfx <name>.')

    if (time.time() * 1000.0 - client.command_time) <= 0:
        return
        #raise ArgumentError('Please don\'t spam.')
    client.command_time = round(time.time() * 1000.0 + 200)
    client.send_host_message('Playing sound: {}.'.format(arg))

    client.area.send_command('MS', 'chat', '-', ' ', '../../background/blackout/defensedesk',
                             '((/sfx {}))'.format(arg), client.pos, '0', 1, client.char_id, 0, 0, 0, 0, 0, 0)
    client.area.send_command('MS', 'chat', '-', ' ', '../../background/blackout/defensedesk',
                             ' ', client.pos, arg, 1, 0, 0, 0, 0, 0, 0, 0)

    logger.log_server('[{}][{}]Played  sfx {}.'.format(client.area.id, client.get_char_name(), arg), client)
