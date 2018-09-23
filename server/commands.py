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
    if len(arg) == 0:
        raise ArgumentError('You must specify a name. Use /bg <background>.')
    if not client.is_mod and client.area.bg_lock == True: #CHANGED
        raise AreaError("This area's background is locked")
    try:
        if client.is_mod or client.is_gm:
            client.area.change_background_mod(arg)
        else:
            client.area.change_background(arg)
    except AreaError:
        raise
    client.area.send_host_message('{} changed the background to {}.'.format(client.get_char_name(), arg))
    logger.log_server('[{}][{}]Changed background to {}'.format(client.area.id, client.get_char_name(), arg), client)


def ooc_cmd_bglock(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.bg_lock == True:
        client.area.bg_lock = False
    else:
        client.area.bg_lock = True #CHANGED
    client.area.send_host_message('A mod has set the background lock to {}.'.format(client.area.bg_lock))
    logger.log_server('[{}][{}]Changed bglock to {}'.format(client.area.id, client.get_char_name(), client.area.bg_lock), client)

def ooc_cmd_iclock(client, arg):
    if not (client.is_mod or client.is_cm or client.is_gm):
        raise ClientError('You must be authorized to do that.')
    if not (client.is_mod or client.is_cm) and (client.is_gm and not client.area.gm_iclock_allowed):
        raise ClientError('GMs are not authorized to change IC locks in this area.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.ic_lock:
        client.area.ic_lock = False
    else:
        client.area.ic_lock = True
    client.area.send_host_message('A staff member has set the IC lock to {}.'.format(client.area.ic_lock))
    logger.log_server('[{}][{}]Changed IC lock to {}'.format(client.area.id, client.get_char_name(), client.area.ic_lock), client)

def ooc_cmd_allow_iniswap(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    client.area.iniswap_allowed = not client.area.iniswap_allowed
    answer = {True: 'allowed', False: 'forbidden'}
    client.send_host_message('iniswap is {}.'.format(answer[client.area.iniswap_allowed]))
    return

def ooc_cmd_ddroll(client, arg):
    DICE_MAX = 11037
    NUMDICE_MAX = 20
    MODIFIER_LENGTH_MAX = 12 #Change to a higher at your own risk
    ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
    MAXDIVZERO_ATTEMPTS = 10
    MAXACCEPTABLETERM = 10*DICE_MAX #Change to a higher number at your own risk
    
    special_calculation = False
    args = arg.split(' ')
    arg_length = len(args)
    
    if arg != '':
        if arg_length == 2:
            dice_type, modifiers = args
            if len(modifiers) > MODIFIER_LENGTH_MAX:
                raise ArgumentError('The given modifier is too long to compute. Please try a shorter one')
        elif arg_length == 1:
            dice_type, modifiers = arg, ''
        else:
             raise ArgumentError('This command takes one or two arguments. Use /ddroll [<num of rolls>]d[<max>] [modifiers]')

        dice_type = dice_type.split('d')
        if len(dice_type) == 1:
            dice_type.insert(0,1)
        if dice_type[0] == '':
            dice_type[0] = '1'
            
        try:
            num_dice,chosen_max = int(dice_type[0]),int(dice_type[1])
        except ValueError:
            raise ArgumentError('Expected integer value for number of rolls and max value of dice')

        if not 1 <= num_dice <= NUMDICE_MAX: 
            raise ArgumentError('Number of rolls must be between 1 and {}'.format(NUMDICE_MAX))
        if not 1 <= chosen_max <= DICE_MAX:
            raise ArgumentError('Dice value must be between 1 and {}'.format(DICE_MAX))
            
        for char in modifiers:
            if char not in ACCEPTABLE_IN_MODIFIER:
                raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
            if char == 'r':
                special_calculation = True
        if '**' in modifiers: #Exponentiation manually disabled, it can be pretty dangerous
            raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
    else:
        num_dice,chosen_max,modifiers = 1,6,'' #Default
        
    roll = ''
    
    for i in range(num_dice):
        divzero_attempts = 0
        while True:
            raw_roll = str(random.randint(1, chosen_max))
            if modifiers == '':
                aux_modifier = ''
                mid_roll = int(raw_roll)
            else:
                if special_calculation:
                    aux_modifier = modifiers.replace('r',raw_roll)+'='
                elif modifiers[0].isdigit():
                    aux_modifier = raw_roll+"+"+modifiers+'='
                else:
                    aux_modifier = raw_roll+modifiers+'='
                
                #Prevent any terms from reaching past MAXACCEPTABLETERM in order to prevent server lag due to potentially frivolous dice rolls
                aux = aux_modifier[:-1]
                for i in "+-*/()":
                    aux = aux.replace(i,"!")
                aux = aux.split('!')
                for i in aux:
                    try:
                        if i != '' and round(float(i)) > MAXACCEPTABLETERM:
                            raise ArgumentError("Given mathematical formula takes numbers past the server's computation limit")
                    except ValueError:
                        raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                        
                try: 
                    mid_roll = round(eval(aux_modifier[:-1])) #By this point it should be 'safe' to run eval
                except SyntaxError:
                    raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                except TypeError: #Deals with inputs like 3(r-1)
                    raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                except ZeroDivisionError:
                    divzero_attempts += 1
                    if divzero_attempts == MAXDIVZERO_ATTEMPTS:
                        raise ArgumentError('Given mathematical formula produces divisions by zero too often and cannot be computed')
                    continue
            break

        final_roll = min(chosen_max,max(1,mid_roll))
        if final_roll != mid_roll:
            final_roll = "|"+str(final_roll) #This visually indicates the roll was capped off due to exceeding the acceptable roll range
        else:
            final_roll = str(final_roll)
        if modifiers != '':
            roll += str(raw_roll+':')
        roll += str(aux_modifier+final_roll) + ', '
    roll = roll[:-2]
    if num_dice > 1:
        roll = '(' + roll + ')'
    
    
    
    client.area.send_host_message('{} rolled {} out of {}.'.format(client.get_char_name(), roll, chosen_max))
    logger.log_server(
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), roll, chosen_max), client)
    
def ooc_cmd_ddrollp(client, arg):
    if not client.area.rollp_allowed and (not client.is_mod and not client.is_gm and not client.is_cm):
        client.send_host_message("This command has been restricted to authorized users only in this area.")
        return
    
    DICE_MAX = 11037
    NUMDICE_MAX = 20
    MODIFIER_LENGTH_MAX = 12 #Change to a higher at your own risk
    ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
    MAXDIVZERO_ATTEMPTS = 10
    MAXACCEPTABLETERM = 10*DICE_MAX #Change to a higher number at your own risk
    
    special_calculation = False
    args = arg.split(' ')
    arg_length = len(args)
    
    if arg != '':
        if arg_length == 2:
            dice_type, modifiers = args
            if len(modifiers) > MODIFIER_LENGTH_MAX:
                raise ArgumentError('The given modifier is too long to compute. Please try a shorter one')
        elif arg_length == 1:
            dice_type, modifiers = arg, ''
        else:
             raise ArgumentError('This command takes one or two arguments. Use /ddroll [<num of rolls>]d[<max>] [modifiers]')

        dice_type = dice_type.split('d')
        if len(dice_type) == 1:
            dice_type.insert(0,1)
        if dice_type[0] == '':
            dice_type[0] = '1'
            
        try:
            num_dice,chosen_max = int(dice_type[0]),int(dice_type[1])
        except ValueError:
            raise ArgumentError('Expected integer value for number of rolls and max value of dice')

        if not 1 <= num_dice <= NUMDICE_MAX: 
            raise ArgumentError('Number of rolls must be between 1 and {}'.format(NUMDICE_MAX))
        if not 1 <= chosen_max <= DICE_MAX:
            raise ArgumentError('Dice value must be between 1 and {}'.format(DICE_MAX))
            
        for char in modifiers:
            if char not in ACCEPTABLE_IN_MODIFIER:
                raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
            if char == 'r':
                special_calculation = True
        if '**' in modifiers: #Exponentiation manually disabled, it can be pretty dangerous
            raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
    else:
        num_dice,chosen_max,modifiers = 1,6,'' #Default
        
    roll = ''
    
    for i in range(num_dice):
        divzero_attempts = 0
        while True:
            raw_roll = str(random.randint(1, chosen_max))
            if modifiers == '':
                aux_modifier = ''
                mid_roll = int(raw_roll)
            else:
                if special_calculation:
                    aux_modifier = modifiers.replace('r',raw_roll)+'='
                elif modifiers[0].isdigit():
                    aux_modifier = raw_roll+"+"+modifiers+'='
                else:
                    aux_modifier = raw_roll+modifiers+'='
                
                #Prevent any terms from reaching past MAXACCEPTABLETERM in order to prevent server lag due to potentially frivolous dice rolls
                aux = aux_modifier[:-1]
                for i in "+-*/()":
                    aux = aux.replace(i,"!")
                aux = aux.split('!')
                for i in aux:
                    try:
                        if i != '' and round(float(i)) > MAXACCEPTABLETERM:
                            raise ArgumentError("Given mathematical formula takes numbers past the server's computation limit")
                    except ValueError:
                        raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                        
                try: 
                    mid_roll = round(eval(aux_modifier[:-1])) #By this point it should be 'safe' to run eval
                except SyntaxError:
                    raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                except TypeError: #Deals with inputs like 3(r-1)
                    raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                except ZeroDivisionError:
                    divzero_attempts += 1
                    if divzero_attempts == MAXDIVZERO_ATTEMPTS:
                        raise ArgumentError('Given mathematical formula produces divisions by zero too often and cannot be computed')
                    continue
            break

        final_roll = min(chosen_max,max(1,mid_roll))
        if final_roll != mid_roll:
            final_roll = "|"+str(final_roll) #This visually indicates the roll was capped off due to exceeding the acceptable roll range
        else:
            final_roll = str(final_roll)
        if modifiers != '':
            roll += str(raw_roll+':')
        roll += str(aux_modifier+final_roll) + ', '
    roll = roll[:-2]
    if num_dice > 1:
        roll = '(' + roll + ')'
        
    client.send_host_message('You privately rolled {} out of {}.'.format(roll, chosen_max))    
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    'Someone rolled.', pred=lambda c: not (c.is_mod or c.is_gm or c.is_cm) 
                                    and c != client and c.area.id == client.area.id) 
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    '{} privately rolled {} out of {} in {} ({}).'
                                    .format(client.get_char_name(), roll, chosen_max, client.area.name, client.area.id), 
                                    pred=lambda c: (c.is_mod or c.is_gm or c.is_cm) and c != client)
    
    SALT = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    logger.log_server(
        '[{}][{}]Used /ddrollp and got {} out of {}.'.format(client.area.id, client.get_char_name(), hashlib.sha1((str(roll) + SALT).encode('utf-8')).hexdigest() + '|' + SALT, chosen_max), client)

                                      
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
        raise ArgumentError('Too much arguments. Use /roll [<max>] [<num of rolls>]')
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
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), roll, val[0]), client)

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
        raise ArgumentError('Too much arguments. Use /roll [<max>] [<num of rolls>]')
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
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), hashlib.sha1((str(roll) + SALT).encode('utf-8')).hexdigest() + '|' + SALT, val[0]), client)

def ooc_cmd_toggle_rollp(client, arg):
    if (not client.is_mod and not client.is_gm and not client.is_cm):
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.rollp_allowed:
        client.area.rollp_allowed = False
        client.area.send_host_message('The use of the private roll commands in this area has been restricted to authorized users only.')
    else:
        client.area.rollp_allowed = True
        client.area.send_host_message('The use of the private roll commands in this area has been enabled to all users.')

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
        '[{}][{}]Used /coinflip and got {}.'.format(client.area.id, client.get_char_name(), flip), client)


def ooc_cmd_motd(client, arg):
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    client.send_motd()


def ooc_cmd_pos(client, arg):
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


def ooc_cmd_help(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    help_url = 'https://github.com/AttorneyOnlineVidya/tsuserver3'
    help_msg = 'Available commands, source code and issues can be found here: {}'.format(help_url)
    client.send_host_message(help_msg)

	
def ooc_cmd_kick(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10:
        raise ArgumentError('You must specify a target. Use /kick <id, ipid>.')
    if len(arg) == 10 and arg.isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    elif len(arg) < 10 and arg.isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    try:
        if targets:
            for c in targets:
                logger.log_server('Kicked {}.'.format(c.ipid), client)
                client.area.send_host_message("{} was kicked.".format(c.get_char_name()))
                c.disconnect()
        else:
            client.send_host_message("No targets found.")
    except UnboundLocalError:
        raise ClientError('Unrecognized client ID or IPID: {}'.format(arg))
		
def ooc_cmd_kickself(client, arg):
    targets = client.server.client_manager.get_targets(client, TargetType.IPID, client.ipid, False)
    for target in targets:
        if target != client:
            target.disconnect()
    client.send_host_message('Kicked other instances of client.')
	
	
def ooc_cmd_ban(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    try:
        ipid = int(arg.strip())
        if len(str(ipid)) != 10:
            raise ClientError('Argument must be an IP address or 10-digit number.')
        integer = True
    except ValueError:
        ipid = arg.strip()
        integer = False
    try:
        client.server.ban_manager.add_ban(ipid)
    except ServerError:
        raise
    if ipid is not None:
        if integer:
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, ipid, False)
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.IP, ipid, False)
        if targets:
            for c in targets:
                c.disconnect()
            client.send_host_message('{} clients were kicked.'.format(len(targets)))
        client.area.send_host_message('{} was banned.'.format(c.get_char_name))
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
    if not client.is_mod and not client.is_gm and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a song.')
    client.area.play_music(arg, client.char_id, -1)
    client.area.add_music_playing(client, arg)
    logger.log_server('[{}][{}]Changed music to {}.'.format(client.area.id, client.get_char_name(), arg), client)


def ooc_cmd_mute(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            c = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            c = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
        c.is_muted = True
        client.send_host_message('{} existing client(s).'.format(c.get_char_name()))
    except:
        client.send_host_message("No targets found. Use /mute <id> for mute")


def ooc_cmd_unmute(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            c = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            c = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
        c.is_muted = False
        client.send_host_message('{} existing client(s).'.format(c.get_char_name()))
    except:
        client.send_host_message("No targets found. Use /mute <id> for mute")


def ooc_cmd_loginrp(client, arg):
    if len(arg) == 0:
        raise ArgumentError('You must specify the password.')
    try:
        client.auth_gm(arg)
    except ClientError:
        raise
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.send_host_message('Logged in as a game master.')
    logger.log_server('Logged in as game master.', client)


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
	
	
def ooc_cmd_logincm(client, arg):
    if len(arg) == 0:
        raise ArgumentError('You must specify the password.')
    try:
        client.auth_cm(arg)
    except ClientError:
        raise
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.send_host_message('Logged in as a community manager.')
    logger.log_server('Logged in as community manager.', client)


def ooc_cmd_g(client, arg):
    if client.muted_global:
        raise ClientError('Global chat toggled off.')
    if len(arg) == 0:
        raise ArgumentError("You can't send an empty message.")
    client.server.broadcast_global(client, arg)
    logger.log_server('[{}][{}][GLOBAL]{}.'.format(client.area.id, client.get_char_name(), arg), client)


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


def ooc_cmd_doc(client, arg):
    if len(arg) == 0:
        client.send_host_message('Document: {}'.format(client.area.doc))
        logger.log_server(
            '[{}][{}]Requested document. Link: {}'.format(client.area.id, client.get_char_name(), client.area.doc), client)
    else:
        client.area.change_doc(arg)
        client.area.send_host_message('{} changed the doc link.'.format(client.get_char_name()))
        logger.log_server('[{}][{}]Changed document to: {}'.format(client.area.id, client.get_char_name(), arg), client)


def ooc_cmd_cleardoc(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    client.area.send_host_message('{} cleared the doc link.'.format(client.get_char_name()))
    logger.log_server('[{}][{}]Cleared document. Old link: {}'
                      .format(client.area.id, client.get_char_name(), client.area.doc), client)
    client.area.change_doc()


def ooc_cmd_area(client, arg):
    args = arg.split()
    if len(args) == 0:
        if client.in_rp:
            client.send_limited_area_list()
        else:
            client.send_area_list()
    elif len(args) == 1:
        try:
            area = client.server.area_manager.get_area_by_id(int(args[0]))
            client.change_area(area)
        except ValueError:
            raise ArgumentError('Area ID must be a number.')
        except (AreaError, ClientError):
            raise
    else:
        raise ArgumentError('Too many arguments. Use /area <id>.')


def ooc_cmd_pm(client, arg):
    args = arg.split()
    key = ''
    msg = None
    if len(args) < 2:
        raise ArgumentError('Not enough arguments. use /pm <target> <message>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".')
    targets = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, arg, True)
    key = TargetType.CHAR_NAME
    if len(targets) == 0 and args[0].isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
        key = TargetType.ID
    if len(targets) == 0:
        targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, True)
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
    c = targets[0]
    if c.pm_mute:
        raise ClientError('This user muted all pm conversation')
    else:
        c.send_host_message('PM from {} in {} ({}): {}'.format(client.name, client.area.name, client.get_char_name(), msg))
        client.send_host_message('PM sent to {}. Message: {}'.format(args[0], msg))


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
                if len(arg) < 10 and arg.isdigit():
                    client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].char_select()
                elif len(arg) == 10 and arg.isdigit():
                    client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False).char_select()
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
    if client.in_rp and client.area.rp_getarea_allowed == False:
        client.send_host_message("This command has been restricted to authorized users only in this area while in RP mode.")
        return
    client.send_area_info(client.area, client.area.id, False)

def ooc_cmd_getareas(client, arg):
    if client.in_rp and client.area.rp_getareas_allowed == False:
        client.send_host_message("This command has been restricted to authorized users only in this area while in RP mode.")
        return
    client.send_area_info(client.area, -1, False)

def ooc_cmd_toggle_rpgetarea(client, arg):
    if (not client.is_mod and not client.is_gm and not client.is_cm):
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.rp_getarea_allowed == True:
        client.area.rp_getarea_allowed = False
        client.area.send_host_message('The use of the /getarea command in this area while in RP mode has been restricted to authorized users only.')
    else:
        client.area.rp_getarea_allowed = True
        client.area.send_host_message('The use of the /getarea command in this area while in RP mode has been enabled to all users.')

def ooc_cmd_toggle_rpgetareas(client, arg):
    if (not client.is_mod and not client.is_gm and not client.is_cm):
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.rp_getareas_allowed == True:
        client.area.rp_getareas_allowed = False
        client.area.send_host_message('The use of the /getareas command in this area while in RP mode has been restricted to authorized users only.')
    else:
        client.area.rp_getareas_allowed = True
        client.area.send_host_message('The use of the /getareas command in this area while in RP mode has been enabled to all users.')

def ooc_cmd_minimap(client, arg):
    info = '== Areas reachable from {} =='.format(client.area.name)
    try:
        sorted_areas = sorted(client.area.reachable_areas,key = lambda area_name: client.server.area_manager.get_area_by_name(area_name).id)
        if len(sorted_areas) == 0 or sorted_areas == [client.area.name]:
            info += '\r\n*No areas available.'
        else:
            for area in sorted_areas:
                if area != client.area.name:
                    info += '\r\n*{}'.format(area)
    except AreaError:
        info += '\r\n<ALL>'
    client.send_host_message(info)
    
def ooc_cmd_logout(client, arg):
    client.is_mod = False
    client.is_gm = False
    client.is_cm = False
    if client.server.rp_mode:
        client.in_rp = True
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.send_host_message('You are no longer logged in.')


def ooc_cmd_cleargm(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ClientError('This command does not take arguments.')
    for i, area in enumerate(client.server.area_manager.areas):
        for c in [x for x in area.clients if x.is_gm]:
            c.is_gm = False
            if client.server.rp_mode:
                c.in_rp = True
            c.send_host_message('You are no longer a GM.')
    client.send_host_message('All GMs logged out.')


def ooc_cmd_lock(client, arg):
    if not client.area.locking_allowed:
        client.send_host_message('Area locking is disabled in this area.')
        return
    if client.area.is_locked:
        client.send_host_message('Area is already locked.')
    else:
        client.area.is_locked = True
        client.area.send_host_message('Area locked.')
        for i in client.area.clients:
            client.area.invite_list[i.ipid] = None
        return

def ooc_cmd_bilock(client, arg):
    areas = arg.split(', ')
    if len(areas) > 2 or arg == '':
        raise ClientError('This command takes one or two arguments.')
    if len(areas) == 1:
        areas.insert(0,client.area.name)
    elif not (client.is_mod or client.is_gm or client.is_cm):
        raise ClientError('You must be authorized to use the two-parameter version of this command.')
    for i in range(2):
        #The escape character combination for areas that have commas in their name is ',\' (yes, I know it's inverted)
        #This double try block takes into account the possibility that some weird person wants ',\' as part of their actual area name
        #If you are that person... just... why
        try:
            areas[i] = client.server.area_manager.get_area_by_name(areas[i].replace(',\\',','))
        except AreaError:
            try:
                areas[i] = client.server.area_manager.get_area_by_name(areas[i])
            except AreaError:
                try:
                    areas[i] = client.server.area_manager.get_area_by_id(int(areas[i]))
                except:
                    raise ClientError('Could not parse argument {}'.format(areas[i]))
        if not areas[i].change_reachability_allowed and not (client.is_mod or client.is_cm or client.is_gm):
            client.send_host_message('Changing area reachability without authorization is disabled in area {}.'.format(areas[i].name))
            return
    
    if areas[0] == areas[1]:
        raise ClientError('Areas must be different.')
        
    now_reachable = []
    formerly_reachable = [areas[i].reachable_areas for i in range(2)] #Just in case something goes wrong, revert back
    for i in range(2):
        reachable = areas[i].reachable_areas
        #print(areas[i].name,reachable)
        now_reachable.append(False)
        if reachable == {'<ALL>'}:
            reachable = client.server.area_manager.area_names - {areas[1-i].name}
        else:
            if areas[1-i].name in reachable:
                reachable = reachable - {areas[1-i].name}
            else:
                if not (client.is_mod or client.is_cm or client.is_gm) and not (areas[1-i].name in areas[i].staffset_reachable_areas or
                       areas[i].staffset_reachable_areas == {'<ALL>'}):
                    client.send_host_message('You must be authorized to create a new area link from {} to {}.'.format(areas[i].name,areas[1-i].name))
                    areas[0].reachable_areas = formerly_reachable[0]
                    areas[1].reachable_areas = formerly_reachable[1]
                    return
                reachable.add(areas[1-i].name)
                now_reachable[i] = True
        areas[i].reachable_areas = reachable
        if (client.is_mod or client.is_cm or client.is_gm):
            areas[i].staffset_reachable_areas = reachable
        
    if now_reachable[0] == now_reachable[1]:
        client.send_host_message('Set area reachability between {} and {} to {}'.format(areas[0].name,areas[1].name,now_reachable[0]))
 
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    '{} used /bilock to {} area reachability between {} and {} in {} ({}).'
                                    .format(client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name, 
                                            client.area.name, client.area.id), pred=lambda c: (c.is_mod or c.is_gm or c.is_cm) and c != client)
        logger.log_server(
            '[{}][{}]Used /bilock to {} area reachability between {} and {}.'
            .format(client.area.id, client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name), client)

    else:
        client.send_host_message('Set area reachability from {} to {} to {}'.format(areas[0].name,areas[1].name,now_reachable[0]))
        client.send_host_message('Set area reachability from {} to {} to {}'.format(areas[1].name,areas[0].name,now_reachable[1]))
        
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    '{} used /bilock to {} area reachability from {} to {} and to {} area reachability from {} to {} in {} ({}).'
                                    .format(client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name, 
                                            'unlock' if now_reachable[1] else 'lock', areas[1].name, areas[0].name, 
                                            client.area.name, client.area.id), pred=lambda c: (c.is_mod or c.is_gm or c.is_cm) and c != client)
        logger.log_server(
            '[{}][{}]Used /bilock to {} area reachability from {} to {} and to {} area reachability from {} to {}.'
            .format(client.area.id, client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name, 
                                                            'unlock' if now_reachable[1] else 'lock', areas[1].name, areas[0].name), client)

def ooc_cmd_unilock(client, arg):
    areas = arg.split(', ')
    if len(areas) > 2 or arg == '':
        raise ClientError('This command takes one or two arguments.')
    if len(areas) == 1:
        areas.insert(0,client.area.name)
    elif not (client.is_mod or client.is_gm or client.is_cm):
        raise ClientError('You must be authorized to use the two-parameter version of this command')
    for i in range(2):
        #The escape character combination for areas that have commas in their name is ',\' (yes, I know it's inverted)
        #This double try block takes into account the possibility that some weird person wants ',\' as part of their actual area name
        #If you are that person... just... why
        try:
            areas[i] = client.server.area_manager.get_area_by_name(areas[i].replace(',\\',','))
        except AreaError:
            try:
                areas[i] = client.server.area_manager.get_area_by_name(areas[i])
            except AreaError:
                try:
                    areas[i] = client.server.area_manager.get_area_by_id(int(areas[i]))
                except:
                    raise ClientError('Could not parse argument {}'.format(areas[i]))

    if not areas[0].change_reachability_allowed and not (client.is_mod or client.is_cm or client.is_gm):
        client.send_host_message('Changing area reachability without authorization is disabled in area {}.'.format(areas[0].name))
        return

    if areas[0] == areas[1]:
        raise ClientError('Areas must be different.')
        
    now_reachable = False
    reachable = areas[0].reachable_areas
    if reachable == {'<ALL>'}:
        reachable = client.server.area_manager.area_names - {areas[1].name}
    else:
        if areas[1].name in reachable:
            reachable = reachable - {areas[1].name}
        else:
            if not (client.is_mod or client.is_cm or client.is_gm) and not (areas[1].name in areas[0].staffset_reachable_areas or
                   areas[0].staffset_reachable_areas == {'<ALL>'}):
                client.send_host_message('You must be authorized to create a new area link from {} to {}.'.format(areas[0].name,areas[1].name))
                return
            reachable.add(areas[1].name)
            now_reachable = True
    areas[0].reachable_areas = reachable
    if (client.is_mod or client.is_cm or client.is_gm):
        areas[0].staffset_reachable_areas = reachable
    client.send_host_message('Set area reachability from {} to {} to {}'.format(areas[0].name,areas[1].name,now_reachable))
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                '{} used /unilock to {} area reachability from {} to {} in {} ({}).'
                                .format(client.get_char_name(), 'unlock' if now_reachable else 'lock', areas[0].name, areas[1].name, 
                                        client.area.name, client.area.id), pred=lambda c: (c.is_mod or c.is_gm or c.is_cm) and c != client)
    logger.log_server(
        '[{}][{}]Used /unilock to {} area reachability from {} to {}.'
        .format(client.area.id, client.get_char_name(), 'unlock' if now_reachable else 'lock', areas[0].name, areas[1].name), client)


def ooc_cmd_restore_areareachlock(client, arg):
    if not (client.is_mod or client.is_cm or client.is_gm): 
        raise ClientError('You must be authorized to do that.')
    areas = arg.split(', ')
    if len(areas) > 2:
        raise ClientError('This command takes at most two arguments.')
    elif arg == '':
        areas = [client.area.name,client.area.name]
    elif len(areas) == 1:
        areas.append(areas[0])
        
    for i in range(2):
        #The escape character combination for areas that have commas in their name is ',\' (yes, I know it's inverted)
        #This double try block takes into account the possibility that some weird person wants ',\' as part of their actual area name
        #If you are that person... just... why
        try:
            areas[i] = client.server.area_manager.get_area_by_name(areas[i].replace(',\\',','))
        except AreaError:
            try:
                areas[i] = client.server.area_manager.get_area_by_name(areas[i])
            except AreaError:
                try:
                    areas[i] = client.server.area_manager.get_area_by_id(int(areas[i]))
                except:
                    raise ClientError('Could not parse argument {}'.format(areas[i]))
    
    if areas[0].id > areas[1].id:
        raise ClientError('The ID of the first area must be lower than the ID of the second area.')
        
    for i in range(areas[0].id,areas[1].id+1):
        area = client.server.area_manager.get_area_by_id(i)
        area.reachable_areas = set(list(area.default_reachable_areas)[:])
        area.change_reachability_allowed = area.default_change_reachability_allowed

    if areas[0] == areas[1]:    
        client.send_host_message('Area passage locks have been set to standard in {}.'.format(areas[0].name))
    else:
        client.send_host_message('Area passage locks have been set to standard in {} through {}'.format(areas[0].name,areas[1].name))

def ooc_cmd_toggle_areareachlock(client, arg):
    if not (client.is_mod or client.is_gm or client.is_cm):
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    if client.area.change_reachability_allowed:
        client.area.change_reachability_allowed = False
        client.area.send_host_message('The use of the /unilock and /bilock commands affecting this area has been restricted to authorized users only.')
    else:
        client.area.change_reachability_allowed = True
        client.area.send_host_message('The use of the /unilock and /bilock commands affecting this area commands in this area has been enabled to all users.')

def ooc_cmd_gmlock(client, arg):
    if not client.area.locking_allowed:
        client.send_host_message('Area locking is disabled in this area')
        return
    if not client.is_gm and not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if client.area.is_gmlocked:
        raise ClientError('Area is already gm-locked.')
    else:
        client.area.is_gmlocked = True
        client.area.send_host_message('Area gm-locked.')
        for i in client.area.clients:
            client.area.invite_list[i.ipid] = None
        return


def ooc_cmd_modlock(client, arg):
    if not client.area.locking_allowed:
        client.send_host_message('Area locking is disabled in this area')
        return
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if client.area.is_modlocked:
        raise ClientError('Area is already mod-locked.')
    else:
        client.area.is_modlocked = True
        client.area.send_host_message('Area mod-locked.')
        for i in client.area.clients:
            client.area.invite_list[i.ipid] = None
        return


def ooc_cmd_unlock(client, arg):
    if not client.area.is_locked and not client.area.is_modlocked and not client.area.is_gmlocked:
        raise ClientError('Area is already open.')
    else:
        if client.is_mod and client.area.is_modlocked:
            client.area.modunlock()
        elif client.is_gm or client.is_cm or client.is_mod and not client.area.is_modlocked:
            client.area.gmunlock()
        elif not client.area.is_gmlocked and not client.area.is_modlocked:
            client.area.unlock()
        else:
            raise ClientError('You must be of higher authorization to do that.')
    client.send_host_message('Area is unlocked.')


def ooc_cmd_invite(client, arg):
    if not client.is_cm and not client.is_gm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if not client.area.is_locked and not client.area.is_modlocked and not client.area.is_gmlocked:
        raise ClientError('Area isn\'t locked.')
    if not arg:
        raise ClientError('You must specify a target. Use /invite <id>')
    try:
        if len(arg) == 10 and arg.isdigit():
            client.area.invite_list[arg] = None
            client.send_host_message('{} is invited to your area.'.format(arg))
        elif len(arg) < 10 and arg.isdigit():
            client.area.invite_list[client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].ipid] = None
            client.send_host_message('{} is invited to your area.'.format(client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].get_char_name()))
        else:
            raise ClientError('You must specify a valid target. Use /invite <id>')
    except:
        raise ClientError('You must specify a target. Use /invite <id>')


def ooc_cmd_uninvite(client, arg):
    if len(arg) == 0:
        raise ClientError('You must specify a user to uninvite.')
    else:
        if len(arg) == 10 and arg.isdigit():
            try:
                client.area.invite_list.pop(arg)
                client.send_host_message('{} was removed from the invite list.'.format(arg))
            except KeyError:
                raise ClientError('User is not on invite list.')
        elif len(arg) < 10 and arg.isdigit():
            try:
                client.area.invite_list.pop(client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].ipid)
                client.send_host_message('{} was removed from the invite list.'.format(client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)[0].get_char_name()))
            except KeyError:
                raise ClientError('User is not on invite list.')
            except IndexError:
                raise ClientError('User is not on invite list.')
        else:
            raise ClientError('You must specify an ID or IPID.')


def ooc_cmd_area_kick(client, arg):
    if not client.is_cm and not client.is_gm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if not client.area.is_locked and not client.is_gm and not client.is_mod:
        raise ClientError('Area isn\'t locked.')
    if not arg:
        raise ClientError('You must specify a target. Use /area_kick <id>')
    arg = arg.split(' ')
    if len(arg[0]) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg[0]), False)
    elif len(arg[0]) < 10:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg[0]), False)
    if targets:
        try:
            for c in targets:
                if len(arg) == 1:
                    area = client.server.area_manager.get_area_by_id(int(0))
                    output = 0
                else:
                    try:
                        area = client.server.area_manager.get_area_by_id(int(arg[1]))
                        output = arg[1]
                    except AreaError:
                        raise
                client.send_host_message("Attempting to kick {} to area {}.".format(c.get_char_name(), output))
                c.change_area(area,override=True)
                c.send_host_message("You were kicked from the area to area {}.".format(output))
                if client.area.is_locked or client.area.is_modlocked:
                    client.area.invite_list.pop(c.ipid)
        except AreaError:
            raise
        except ClientError:
            raise
    else:
        client.send_host_message("No targets found.")


def ooc_cmd_ooc_mute(client, arg):
    if not client.is_mod and not client.is_cm:
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
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /ooc_mute <OOC-name>.')
    targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, False)
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
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
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
		
		
def ooc_cmd_disemconsonant(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /disemconsonant <id>.')
    if targets:
        for c in targets:
            logger.log_server('Disemconsonanting {}.'.format(c.get_ip()), client)
            c.disemconsonant = True
        client.send_host_message('Disemconsonanted {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')
		
		
def ooc_cmd_undisemconsonant(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /disemvowel <id>.')
    if targets:
        for c in targets:
            logger.log_server('Undisemconsonanting {}.'.format(c.get_ip()), client)
            c.disemconsonant = False
        client.send_host_message('Undisemconsonanted {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')
		
		
def ooc_cmd_remove_h(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /remove_h <id>.')
    if targets:
        for c in targets:
            logger.log_server('Removing h from {}.'.format(c.get_ip()), client)
            c.remove_h = True
        client.send_host_message('Removed h from {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')


def ooc_cmd_undisemvowel(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
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
		

def ooc_cmd_unremove_h(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /unremove_h <id>.')
    if targets:
        for c in targets:
            logger.log_server('Adding h to {}.'.format(c.get_ip()), client)
            c.remove_h = False
        client.send_host_message('Added h to {} existing client(s).'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')


def ooc_cmd_gimp(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /gimp <id, ipid>.')
    if targets:
        for c in targets:
            logger.log_server('Gimping {}.'.format(c.get_ip(), client))
            c.gimp = True
        client.send_host_message('Gimped {} targets.'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')


def ooc_cmd_ungimp(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    elif len(arg) == 0:
        raise ArgumentError('You must specify a target.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must specify a target. Use /gimp <id, ipid>.')
    if targets:
        for c in targets:
            logger.log_server('Ungimping {}.'.format(c.get_ip(), client))
            c.gimp = False
        client.send_host_message('Ungimped {} targets.'.format(len(targets)))
    else:
        client.send_host_message('No targets found.')


def ooc_cmd_blockdj(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a target. Use /blockdj <id>.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
         raise ArgumentError('You must enter a number. Use /blockdj <id, ipid>.')
    if not targets:
        raise ArgumentError('Target not found. Use /blockdj <id, ipid>.')
    for target in targets:
        target.is_dj = False
        target.send_host_message('You have been muted of changing music by moderator.')
    client.send_host_message('blockdj\'d {}.'.format(targets[0].get_char_name()))


def ooc_cmd_unblockdj(client, arg):
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 and len(arg) < 10:
        raise ArgumentError('You must specify a target. Use /unblockdj <id>.')
    try:
        if len(arg) == 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        elif len(arg) < 10 and arg.isdigit():
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    except:
        raise ArgumentError('You must enter a number. Use /unblockdj <id>.')
    if not targets:
        raise ArgumentError('Target not found. Use /blockdj <id>.')
    for target in targets:
        target.is_dj = True
        target.send_host_message('Now you can change music.')
    client.send_host_message('Unblockdj\'d {}.'.format(targets[0].get_char_name()))


def ooc_cmd_rpmode(p_client, arg):
    if not p_client.server.config['rp_mode_enabled']:
        p_client.send_host_message("RP mode is disabled in this server!")
        return
    if not p_client.is_mod and not p_client.is_gm and not p_client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify either on or off')
    if arg == 'on':
        p_client.server.rp_mode = True
        for i_client in p_client.server.client_manager.clients:
            i_client.send_host_message('RP mode enabled!')
            if not i_client.is_mod and not i_client.is_cm and not i_client.is_gm:
                i_client.in_rp = True
    elif arg == 'off':
        p_client.server.rp_mode = False
        for i_client in p_client.server.client_manager.clients:
            i_client.send_host_message('RP mode disabled!')
            i_client.in_rp = False
    else:
        p_client.send_host_message('Invalid argument! Valid arguments: on, off. Your argument: ' + arg)


def ooc_cmd_refresh(client, arg):
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len (arg) > 0:
        raise ClientError('This command does not take in any arguments!')
    else:
        try:
            client.server.reload()
            client.send_host_message('You have reloaded the server.')
        except ServerError:
            raise
			
			
def ooc_cmd_ToD(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    coin = ['truth', 'dare']
    flip = random.choice(coin)
    client.area.send_host_message('{} has to do a {}.'.format(client.get_char_name(), flip))
    logger.log_server(
        '[{}][{}]has to do a {}.'.format(client.area.id, client.get_char_name(), flip), client)

				
def ooc_cmd_8ball(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    coin = ['yes', 'no', 'maybe', 'I dont know', 'perhaps', 'Please do not', 'try again', 'you shouldn\'t ask that']
    flip = random.choice(coin)
    client.area.send_host_message('The magic 8 ball says {}.'.format(flip))
    logger.log_server(
        '[{}][{}]called upon the magic 8 ball and it said {}.'.format(client.area.id,client.get_char_name(),flip), client)
		

def ooc_cmd_discord(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    client.send_host_message('Discord Invite Link: \r\ninsert link here \r\nBlank\'s tag: \r\nName(tag)0000 \r\nBlank\'s tag: \r\nName(tag)0000 \r\nBlank\'s tag: \r\nName(hashtag)0000')

	
def ooc_cmd_follow(client, arg):
    if not client.is_gm and not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        client.send_host_message('You must specify an ID. Use /follow <id>.')
    try:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
        c = targets[0]
        client.follow_user(c)
        logger.log_server('{} began following {}.'.format(client.get_char_name(), c.get_char_name()), client)
    except:
        raise ClientError('Target not found.')


def ooc_cmd_unfollow(client, arg):
    if not client.is_gm and not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    try:
        client.unfollow_user()
    except AttributeError:
        client.send_host_message('You are not following anyone.')


def ooc_cmd_time(client, arg):
    client.send_host_message(time.asctime(time.localtime(time.time())))

def ooc_cmd_time12(client, arg):
    client.send_host_message(time.strftime('%a %b %e %I:%M:%S %p (%z) %Y'))
    
def ooc_cmd_st(client, arg):
    if not client.is_gm and not client.is_cm and not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    client.server.send_all_cmd_pred('CT','{} [Staff] {}'.format(client.server.config['hostname'],client.name),arg,
                                    pred=lambda c: c.is_mod or c.is_gm or c.is_cm)
    logger.log_server('[{}][STAFFCHAT][{}][{}]{}.'.format(client.area.id,client.get_char_name(),client.name,arg), client)