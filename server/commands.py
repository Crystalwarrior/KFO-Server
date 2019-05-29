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

""" SUGGESTED IDEAS
/scream: /g but for reachable areas
/char_restrict: Restrict a char to staff only
/area_ban: Ban a user from a certain area
set what areas will listen to a scream from a given area?

"""

""" <parameter_name>: required parameter
{parameter_name}: optional parameter
"""

def arg_num(arg):
    """
    Return number of arguments, i.e. keywords separated by spaces.
    """
    if arg == "":
        return 0
    
    args = arg.split(" ")
    return len(args)

def dice_roll(arg, command_type):
    """
    HELPER FUNCTION
    Calculate roll results.
    Confront /roll documentation for more details.
    """
    NUMFACES_MAX = 11037
    NUMDICE_MAX = 20
    MODIFIER_LENGTH_MAX = 12 #Change to a higher at your own risk
    ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
    MAXDIVZERO_ATTEMPTS = 10
    MAXACCEPTABLETERM = 10 * NUMFACES_MAX #Change to a higher number at your own risk
    
    # Default values
    DEF_NUMDICE = 1
    DEF_NUMFACES = 6
    DEF_MODIFIER = ''
    
    special_calculation = False # Is it given a modifier? False until proven otherwise
    args = arg.split(' ')
    arg_length = len(args)
    
    # Parse number of dice, number of faces and modifiers
    if arg != '':
        if arg_length == 2:
            dice_type, modifiers = args
            if len(modifiers) > MODIFIER_LENGTH_MAX:
                raise ArgumentError('The given modifier is too long to compute. Please try a shorter one')
        elif arg_length == 1:
            dice_type, modifiers = arg, ''
        else:
             raise ArgumentError('This command takes one or two arguments. Use /{} {num_dice}d<num_faces> {modifiers}'.format(command_type))

        dice_type = dice_type.split('d')
        if len(dice_type) == 1:
            dice_type.insert(0, 1)
        if dice_type[0] == '':
            dice_type[0] = '1'
            
        try:
            num_dice, num_faces = int(dice_type[0]), int(dice_type[1])
        except ValueError:
            raise ArgumentError('Expected integer value for number of rolls and max value of dice')

        if not 1 <= num_dice <= NUMDICE_MAX: 
            raise ArgumentError('Number of rolls must be between 1 and {}'.format(NUMDICE_MAX))
        if not 1 <= num_faces <= NUMFACES_MAX:
            raise ArgumentError('Dice value must be between 1 and {}'.format(NUMFACES_MAX))
            
        for char in modifiers:
            if char not in ACCEPTABLE_IN_MODIFIER:
                raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
            if char == 'r':
                special_calculation = True
        if '**' in modifiers: #Exponentiation manually disabled, it can be pretty dangerous
            raise ArgumentError('Expected numbers and standard mathematical operations in modifier')
    else:
        num_dice, num_faces, modifiers = DEF_NUMDICE, DEF_NUMFACES, DEF_MODIFIER #Default
        
    roll = ''
    
    for i in range(num_dice):
        divzero_attempts = 0
        while True: # Roll until no division by zeroes happen (or it gives up)
            # raw_roll: original roll
            # mid_roll: result after modifiers (if any) have been applied to original roll
            # final_roll: result after previous result has been capped between 1 and NUMFACES_MAX
            
            raw_roll = str(random.randint(1, num_faces))
            if modifiers == '':
                aux_modifier = ''
                mid_roll = int(raw_roll)
            else:
                if special_calculation: # Ex: /roll 20 3*r+1
                    aux_modifier = modifiers.replace('r', raw_roll) + '='
                elif modifiers[0].isdigit(): # Ex /roll 20 3
                    aux_modifier = raw_roll + "+" + modifiers + '='
                else: # Ex /roll 20 -3
                    aux_modifier = raw_roll + modifiers + '='
                
                # Prevent any terms from reaching past MAXACCEPTABLETERM in order to prevent server lag due to potentially frivolous dice rolls
                # In order to do that, it will split the string by the numbers it uses
                # and check if any individual number is larger than said term.
                # This also doubles as a second-line defense to junk entries.
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
                except TypeError: #Deals with inputs like 3(r-1), which act like Python functions.
                    raise ArgumentError('Given mathematical formula has a syntax error and cannot be computed')
                except ZeroDivisionError:
                    divzero_attempts += 1
                    if divzero_attempts == MAXDIVZERO_ATTEMPTS:
                        raise ArgumentError('Given mathematical formula produces divisions by zero too often and cannot be computed')
                    continue
            break

        final_roll = min(num_faces, max(1, mid_roll))
        
        # Build output string
        if final_roll != mid_roll:
            final_roll = "|" + str(final_roll) #This visually indicates the roll was capped off due to exceeding the acceptable roll range
        else:
            final_roll = str(final_roll)
            
        if modifiers != '':
            roll += str(raw_roll+':')
        roll += str(aux_modifier+final_roll) + ', '
        
    roll = roll[:-2] # Remove last ', '
    if num_dice > 1:
        roll = '(' + roll + ')'

    return roll, num_faces

def login(client, arg, auth_command, role):
    if len(arg) == 0:
        raise ArgumentError('You must specify the password.')
    try:
        auth_command(arg)
    except ClientError:
        raise
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    client.reload_music_list() # Update music list to show all areas
    client.send_host_message('Logged in as a {}.'.format(role))
    logger.log_server('Logged in as a {}.'.format(role), client)

def parse_two_area_names(client, areas, area_duplicate = True, check_valid_range = True):
    # Convert to two-area situation
    if len(areas) == 0:
        areas = [client.area.name, client.area.name]
    elif len(areas) == 1:
        if area_duplicate:
            areas.append(areas[0])
        else:
            areas.insert(0, client.area.name)
    elif len(areas) > 2:
        raise ArgumentError('Expected at most two area names.')
    
    # Replace arguments with proper area objects
    areas = parse_area_names(client, areas)
    
    if check_valid_range and areas[0].id > areas[1].id:
        raise ClientError('The ID of the first area must be lower than the ID of the second area.')
    elif not area_duplicate and areas[0].id == areas[1].id:
        raise ClientError('Areas must be different.')
        
    return areas

def parse_area_names(client, areas):
    # Replace arguments with proper area objects
    for i in range(len(areas)):
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
                    raise ArgumentError('Could not parse area {}'.format(areas[i]))    
    return areas

def ooc_cmd_allow_iniswap(client, arg):
    """ (MOD ONLY)
    Toggles iniswapping by non-staff in the current area being allowed/disallowed.
    
    SYNTAX
    /allow_iniswap
    
    PARAMETERS
    None
    
    EXAMPLES
    /allow_iniswap
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command takes no arguments.')

    client.area.iniswap_allowed = not client.area.iniswap_allowed
    client.area.send_host_message('A mod has set iniswapping being allowed to {}.'.format(client.area.iniswap_allowed))
    logger.log_server('[{}][{}]Changed iniswapping allowed to {}'.format(client.area.id, client.get_char_name(), client.area.iniswap_allowed), client)

    # answer = {True: 'allowed', False: 'forbidden'}
    # client.send_host_message('iniswap is {}.'.format(answer[client.area.iniswap_allowed]))

def ooc_cmd_announce(client, arg):
    """ (MOD ONLY)
    Sends an "announcement" to all users in the server, regardless of whether they have global chat turned on or off.
    Returns an error if user sends an empty message.
    
    SYNTAX
    /announce <message>
    
    PARAMETERS
    <message>: Message to be sent
    
    EXAMPLE
    /announce Hello World       :: Sends Hello World to all users in the server.
    """

    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError("Can't send an empty message.")
    
    client.server.send_all_cmd_pred('CT', '{}'.format(client.server.config['hostname']),
                                    '=== Announcement ===\r\n{}\r\n=================='.format(arg))
    logger.log_server('[{}][{}][ANNOUNCEMENT]{}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_area(client, arg):
    """
    Either lists all areas in the server or switches the user to a new given area.
    Returns an error if user is unathorized to list all areas or unable to move to the intended new area.
    
    PARAMETERS
    /area {new_area_id}
    
    SYNTAX
    {new_area_id}: ID of the area
    
    EXAMPLES
    /area                   :: Lists all areas in the server with usercount.
    /area {new_area_id}     :: Moves 
    """
    args = arg.split()
    # List all areas case
    if len(args) == 0:
        if client.in_rp:
            client.send_limited_area_list()
        else:
            client.send_area_list()
    
    # Switch to new area
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

def ooc_cmd_area_list(client, arg):
    """ (MOD ONLY)
    Sets the server's current area list (what areas exist at any given time). 
    If given no arguments, it will return the area list to its original value (in areas.yaml)
    The list of area lists can be accessed with /area_lists.
    Clients that do not process 'SM' packets can be in servers that use this command without crashing, 
    but they will continue to only see the areas they could see when joining.
    Returns an error if the given area list was not found.
    
    SYNTAX
    /area_list <area_list>
    
    PARAMETERS
    <area_list>: Name of the intended area list
    
    EXAMPLES
    /area_list dr1dr2       :: Load the "dr1dr2" area list.
    /area_list              :: Reset the area list to its original value.
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
        
    if len(arg) == 0:
        client.server.area_manager.load_areas()
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                            'The area list of the server has been reset to its original value.')
    else:
        try:
            new_area_file = 'config/area_lists/{}.yaml'.format(arg)
            client.server.area_manager.load_areas(area_list_file=new_area_file)
        except FileNotFoundError:
            raise ArgumentError('Could not find the area list file {}'.format(new_area_file))
        except AreaError as exc:
            raise ArgumentError('The area list {} raised the following error when loading: {}'.format(new_area_file, exc))
            
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                            'The area list {} has been loaded.'.format(arg))
        
def ooc_cmd_area_lists(client, arg):
    """ (MOD ONLY)
    Lists all available area lists as established in config/area_lists.yaml
    Note that, as this file is updated independently from the other area lists,
    an area list does not need to be in this file in order to be usable, and
    an area list in this list may no longer exist.
    
    SYNTAX
    /area_lists
    
    PARAMETERS
    None
    
    EXAMPLES
    /area_lists             :: Return all available area lists
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    try:
        with open('config/area_lists.yaml', 'r') as f:
            output = 'Available area lists:\n'
            for line in f:
                output += '*{}'.format(line)
            client.send_host_message(output)
    except FileNotFoundError:
        raise ClientError('Server file area_lists.yaml not found.')
        
def ooc_cmd_ban(client, arg):
    """ (MOD ONLY)
    Kicks given user from the server and prevents them from rejoining. The user can be identified by either their IPID or IP address.
    Requires /unban to undo.
    Returns an error if given identifier does not correspond to a user.
    
    SYNTAX
    /ban <client_ipid>
    /ban <client_ip>
    
    PARAMETERS
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    <client_ip>: user IP
    
    EXAMPLES
    /ban 1234567890             :: Bans the user whose IPID is 1234567890
    /ban 127.0.0.1              :: Bans the user whose IP is 127.0.0.1
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    
    # Guesess that any number of length 10 is an IPID
    # and that any non-numerical entry is an IP address.
    try:
        # IPID
        identifier = int(arg.strip())
        if len(str(identifier)) != 10:
            raise ClientError('Argument must be an IP address or 10-digit number.')
        is_ipid = True
    except ValueError:
        # IP Address
        identifier = arg.strip()
        is_ipid = False
        
    # Try and add the user to the ban list based on the given identifier
    try:
        client.server.ban_manager.add_ban(identifier)
    except ServerError:
        raise
    
    # Try and kick the user from the server, as well as announce their ban.
    if identifier:
        if is_ipid:
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, identifier, False)
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.IP, identifier, False)
        
        # Kick+ban all clients opened by the targeted user.
        if targets:
            for c in targets:
                client.area.send_host_message('{} was banned.'.format(c.get_char_name()))
                c.disconnect()
        
        client.send_host_message('{} clients were banned.'.format(len(targets)))
        logger.log_server('Banned {}.'.format(identifier), client)
    
def ooc_cmd_bg(client, arg):
    """
    Change the background of the current area.
    Returns an error if area background is locked and user is unathorized or sought background does not exist.
    
    SYNTAX
    /bg <background_name>
    
    PARAMETERS
    <background_name>: New background name, possibly with spaces (e.g. Principal's Room)
    
    EXAMPLES
    /bg Principal's Room   :: Changes background to Principal's Room
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a name. Use /bg <background>.')
    
    if not client.is_mod and client.area.bg_lock == True: 
        raise AreaError("This area's background is locked.")
    try:
        if client.is_staff():
            client.area.change_background_mod(arg)
        else:
            client.area.change_background(arg)
    except AreaError:
        raise
    client.area.send_host_message('{} changed the background to {}.'.format(client.get_char_name(), arg))
    logger.log_server('[{}][{}]Changed background to {}'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_bglock(client, arg):
    """ (MOD ONLY)
    Toggles background changes by non-mods in the current area being allowed/disallowed.
    
    SYNTAX
    /bglock
    
    PARAMETERS
    None
    
    EXAMPLES
    /bglock         
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.area.bg_lock = not client.area.bg_lock
    client.area.send_host_message('A mod has set the background lock to {}.'.format(client.area.bg_lock))
    logger.log_server('[{}][{}]Changed bglock to {}'.format(client.area.id, client.get_char_name(), client.area.bg_lock), client)

def ooc_cmd_charselect(client, arg):
    """
    Opens the character selection screen for the current user
    OR (MOD ONLY) forces another user by identifier to have that screen open, freeing up their character in the process.
    
    SYNTAX
    /charselect 
    /charselect {client_id}
    /charselect {client_ipid}
    
    PARAMETERS
    {client_id}: Client identifier (number in brackets in /getarea).
    {client_ipid}: 10-digit user identifier (number in parentheses in /getarea).
    
    EXAMPLES
    /charselect                    :: Open character selection screen for the current user.
    /charselect 1                  :: Forces open the character selection screen for the user whose client ID is 1   
    /charselect 1234567890         :: Forces open the character selection screen for the user whose IPID is 1234567890
    """
    
    # Open for current user case
    if not arg:
        client.char_select()
    
    # Force open for different user
    else:
        if not client.is_mod:
            raise ClientError('You must be authorized to do that.')
        elif not arg.isdigit() or len(arg) > 10:
            raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
 
        # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
        # This places the assumption that there are no more than 10 billion clients connected simultaneously
        # but if that is the case, you probably have a much larger issue at hand.
        if len(arg) == 10:
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
        
        # Force character selection screen on matching targets
        if targets:
            for c in targets:
                c.char_select()
        else:
            client.send_host_message("No targets found.")
            
def ooc_cmd_cleardoc(client, arg):
    """
    Clears the current area's doc.
    
    SYNTAX
    /cleardoc
    
    PARAMETERS
    None
    
    EXAMPLES
    /cleardoc
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    client.area.send_host_message('{} cleared the doc link.'.format(client.get_char_name()))
    logger.log_server('[{}][{}]Cleared document. Old link: {}'
                      .format(client.area.id, client.get_char_name(), client.area.doc), client)
    client.area.change_doc()

def ooc_cmd_cleargm(client, arg):
    """ (CM AND MOD ONLY)
    Logs out all game masters in the server and puts them in RP mode if needed.
    
    SYNTAX
    /cleargm
    
    PARAMETERS
    None
    
    EXAMPLE
    /cleargm
    """
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    for i, area in enumerate(client.server.area_manager.areas):
        for c in [x for x in area.clients if x.is_gm]:
            c.is_gm = False
            if client.server.rp_mode:
                c.in_rp = True
            # Update the music list to show reachable areas and activate the AFK timer
            c.reload_music_list()
            c.server.create_task(client, ['as_afk_kick', client.area.afk_delay, client.area.afk_sendto])

            c.send_host_message('You are no longer a GM.')
    client.send_host_message('All GMs logged out.')

def ooc_cmd_coinflip(client, arg):
    """
    Flips a coin and returns the result.
    
    SYNTAX
    /coinflip
    
    PARAMETERS
    None
    
    EXAMPLES
    /coinflip
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    coin = ['heads', 'tails']
    flip = random.choice(coin)
    client.area.send_host_message('{} flipped a coin and got {}.'.format(client.get_char_name(), flip))
    logger.log_server(
        '[{}][{}]Used /coinflip and got {}.'.format(client.area.id, client.get_char_name(), flip), client)

def ooc_cmd_currentmusic(client, arg):
    """
    Returns the music currently playing (and who played it), or None if no music is playing.
    
    SYNTAX
    /currentmusic
    
    PARAMETERS
    None
    
    EXAMPLES
    /currentmusic
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    if client.area.current_music == '':
        raise ClientError('There is no music currently playing.')
    client.send_host_message('The current music is {} and was played by {}.'.format(client.area.current_music,
                                                                                    client.area.current_music_player))
    
def ooc_cmd_defaultarea(client, arg):
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
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ClientError('This command takes one argument.')
        
    try:
        area = client.server.area_manager.get_area_by_id(int(arg)) 
    except ValueError:
        raise ArgumentError('Expected numerical value for area ID.')
    except AreaError:
        raise ClientError('ID {} does not correspond to a valid area ID.'.format(arg))

    client.server.default_area = int(arg)
    client.send_host_message('Set default area to {}'.format(arg))        
    
def ooc_cmd_doc(client, arg):
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
        client.send_host_message('Document: {}'.format(client.area.doc))
        logger.log_server(
            '[{}][{}]Requested document. Link: {}'.format(client.area.id, client.get_char_name(), client.area.doc), client)
    # Set new doc case
    else:
        client.area.change_doc(arg)
        client.area.send_host_message('{} changed the doc link.'.format(client.get_char_name()))
        logger.log_server('[{}][{}]Changed document to: {}'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_g(client, arg):
    """
    Sends a global message in the OOC chat (i.e. visible to all users in the server who have not disabled global chat).
    Returns an error if the user has global chat off or sends an empty message.
    
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
    logger.log_server('[{}][{}][GLOBAL]{}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_getarea(client, arg):
    """
    List the characters (and associated client IDs) in the current area.
    Returns an error if the user is subject to RP mode and is in an area that disables /getarea.
    
    SYNTAX
    /getarea
    
    PARAMETERS
    None
    
    EXAMPLE
    /getarea
    """
    if client.in_rp and not client.area.rp_getarea_allowed:
        raise ClientError("This command has been restricted to authorized users only in this area while in RP mode.")
        
    client.send_area_info(client.area, client.area.id, False)

def ooc_cmd_getareas(client, arg):
    """
    List the characters (and associated client IDs) in each area.
    Returns an error if the user is subject to RP mode and is in an area that disables /getareas.
    
    SYNTAX
    /getarea
    
    PARAMETERS
    None
    
    EXAMPLE
    /getarea
    """
    if client.in_rp and not client.area.rp_getareas_allowed:
        raise ClientError("This command has been restricted to authorized users only in this area while in RP mode.")

    client.send_area_info(client.area, -1, False)

def ooc_cmd_globalic(client, arg):
    """ (STAFF ONLY)
    Send client's subsequent IC messages to users only in specified areas. Can take either area IDs or area names.
    If current user is not in intended destination range, it will NOT send messages to their area.
    Requires /unglobalic to undo.
    
    If given two areas, it will send their IC messages to all areas between the given ones inclusive.
    If given one area, it will send their IC messages only to the given area.
    
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
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    areas = arg.split(', ')
    if len(arg) == 0 or len(areas) > 2:
        raise ArgumentError('This command takes either one or two arguments.')
    
    areas = parse_two_area_names(client, areas)
    client.multi_ic = areas
    
    if areas[0] == areas[1]:    
        client.send_host_message('Your IC messages will now be sent to area {}.'.format(areas[0].name))
    else:
        client.send_host_message('Your IC messages will now be sent to areas {} through {}.'.format(areas[0].name,areas[1].name))

def ooc_cmd_gm(client, arg):
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
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if client.muted_global:
        raise ClientError('You have the global chat muted.')
    if len(arg) == 0:
        raise ArgumentError("You cannot send an empty message.")
        
    client.server.broadcast_global(client, arg, True)
    logger.log_server('[{}][{}][GLOBAL-MOD]{}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_help(client, arg):
    """
    Returns the website with all available commands and their instructions (usually a GitHub repository)
    
    SYNTAX
    /help
    
    PARAMETERS
    None
    
    EXAMPLES
    /help
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    help_url = 'https://github.com/AttorneyOnlineVidya/tsuserver3'
    help_msg = 'Available commands, source code and issues can be found here: {}'.format(help_url)
    client.send_host_message(help_msg)
    
def ooc_cmd_iclock(client, arg):
    """ (STAFF ONLY)
    Toggles IC messages by non-staff in the current area being allowed/disallowed.
    Returns an error if not authorized, or if a GM attempts to lock IC in an area where such an action is forbidden.
    
    SYNTAX
    /iclock
    
    PARAMETERS
    None
    
    EXAMPLES
    /iclock
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if not (client.is_mod or client.is_cm) and (client.is_gm and not client.area.gm_iclock_allowed):
        raise ClientError('GMs are not authorized to change IC locks in this area.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.area.ic_lock = not client.area.ic_lock
    client.area.send_host_message('A staff member has set the IC lock to {}.'.format(client.area.ic_lock))
    logger.log_server('[{}][{}]Changed IC lock to {}'.format(client.area.id, client.get_char_name(), client.area.ic_lock), client)

def ooc_cmd_kick(client, arg):
    """ (CM AND MOD ONLY)
    Kicks a user from the server. The target is identified by either client ID (number in brackets) or IPID (number in parentheses).
    If given IPID, it will kick all clients opened by the user. Otherwise, it will just kick the given client.
    Returns an error if the given identifier does not correspond to a user.
    
    SYNTAX
    /kick <client_id>
    /kick <client_ipid>
    
    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /kick 1                     :: Kicks client whose ID is 1.
    /kick 1234567890            :: Kick all clients opened by the user whose IPID is 1234567890.
    """
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10 or not arg.isdigit():
        raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
    
    # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
    # This places the assumption that there are no more than 10 billion clients connected simultaneously
    # but if that is the case, you probably have a much larger issue at hand.
    if len(arg) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    else:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    
    # Kick matching targets
    if targets:
        for c in targets:
            logger.log_server('Kicked {}.'.format(c.ipid), client)
            client.area.send_host_message("{} was kicked.".format(c.get_char_name()))
            c.disconnect()
    else:
        client.send_host_message("No targets found.")
		
def ooc_cmd_kickself(client, arg):
    """
    Kicks other clients opened by the current user. Useful whenever a user loses connection and the old client is ghosting.
    
    SYNTAX
    /kickself
    
    PARAMETERS
    None
    
    EXAMPLES
    /kickself
    """
    targets = client.server.client_manager.get_targets(client, TargetType.IPID, client.ipid, False)
    
    for target in targets:
        if target != client:
            target.disconnect()
    
    client.send_host_message('Kicked other instances of client.')

def ooc_cmd_knock(client, arg):
    """
    'Knock' on some area's door, sending a notification to users in said area.
    Returns an error if the area could not be found, if the user is already in the 
    target area or if the area cannot be reached as per the DEFAULT server configuration 
    (as users may lock passages, but that does not mean the door no longer exists, usually).
    
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
    if len(arg) == 0:
        raise ArgumentError('This command takes one argument.')

    # Get area by either name or ID    
    try:
        target_area = client.server.area_manager.get_area_by_name(arg)
    except AreaError:
        try:
            target_area = client.server.area_manager.get_area_by_id(int(arg))
        except:
            raise ArgumentError('Could not parse area name {}.'.format(arg))
    
    # Filter out edge cases
    if target_area.name == client.area.name:
        raise ClientError('You cannot knock on the door of your current area.')
        
    if client.area.default_reachable_areas != {'<ALL>'} and \
    target_area.name not in client.area.default_reachable_areas | client.area.reachable_areas:
        raise ClientError("You tried to knock on {}'s door but you realized the room is too far away."
                          .format(target_area.name))

    client.send_host_message('You knocked on the door to area {}.'.format(target_area.name))
    client.server.send_all_cmd_pred('CT', '{}'.format(client.server.config['hostname']),
                                'Someone knocked on your door from area {}.'.format(client.area.name),
                                pred=lambda c: not c.is_staff() and c.area == target_area)
    client.server.send_all_cmd_pred('CT', '{}'.format(client.server.config['hostname']),
                                '{} knocked on the door to area {} in area {} ({}).'
                                .format(client.get_char_name(), target_area.name, client.area.name, client.area.id),
                                pred=lambda c: c != client and c.is_staff())
        
def ooc_cmd_lm(client, arg):
    """ (MOD ONLY)
    Similar to /lm, but only broadcasts the message to users in the current area, regardless of their global chat status.
    Returns an error if the user sends an empty message.
    SYNTAX
    /lm <message>
    
    PARAMETERS
    <message>: Message to be sent
    
    EXAMPLE
    /lm Hello World     :: Sends Hello World to all users in the current area, preceded with [MOD].
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError("Can't send an empty message.")
    client.area.send_command('CT', '{}[MOD][{}]'
                             .format(client.server.config['hostname'], client.get_char_name()), arg)
    logger.log_server('[{}][{}][LOCAL-MOD]{}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_lock(client, arg):
    """
    Locks the current area, preventing anyone not in the area (except staff) from joining. It also clears out the current invite list.
    Returns an error if the area does not allow locking or is already locked.
    
    SYNTAX
    /lock
    
    PARAMETERS
    None
    
    EXAMPLE
    /lock
    """
    if not client.area.locking_allowed:
        raise ClientError('Area locking is disabled in this area.')
    if client.area.is_locked:
        raise ClientError('Area is already locked.')
        
    client.area.is_locked = True
    for i in client.area.clients:
        client.area.invite_list[i.ipid] = None

    client.area.send_host_message('Area locked.')
    
def ooc_cmd_login(client, arg):
    """
    Logs in current user as a moderator, provided they input the correct password.
    
    SYNTAX
    /login <mod_password>
    
    PARAMETERS
    <mod_password>: Mod password, found in \config\config.yaml
    
    EXAMPLES
    /login Mod      :: Attempt to log in as mod with "Mod" as password.
    """
    login(client, arg, client.auth_mod, 'moderator')
	
def ooc_cmd_logincm(client, arg):
    """
    Logs in current user as a community manager, provided they input the correct password.
    
    SYNTAX
    /login <cm_password>
    
    PARAMETERS
    <cm_password>: Community manager password, found in \config\config.yaml
    
    EXAMPLES
    /logincm CM     :: Attempt to log in as community maanger with "CM" as password.
    """
    login(client, arg, client.auth_cm, 'community manager')

def ooc_cmd_loginrp(client, arg):
    """
    Logs in current user as a game master, provided they input the correct password.
    
    SYNTAX
    /login <gm_password>
    
    PARAMETERS
    <gm_password>: Game master password, found in \config\config.yaml
    
    EXAMPLES
    /loginrp GM     :: Attempt to log in as game master with "GM" as password.
    """
    login(client, arg, client.auth_gm, 'game master')

def ooc_cmd_logout(client, arg):
    """
    Logs out the current user from all staff roles and puts them in RP mode if needed.
    
    SYNTAX
    /logout
    
    PARAMETERS
    None
    
    EXAMPLE
    /logout
    """
    client.is_mod = False
    client.is_gm = False
    client.is_cm = False
    
    client.send_host_message('You are no longer logged in.')
        
    # Clean-up operations
    
    if client.server.rp_mode:
        client.in_rp = True
    if client.area.evidence_mod == 'HiddenCM':
        client.area.broadcast_evidence_list()
    
    # Update the music list to show reachable areas and activate the AFK timer
    client.reload_music_list()
    client.server.create_task(client, ['as_afk_kick', client.area.afk_delay, client.area.afk_sendto])

    # If using a character restricted in the area, switch out
    if client.get_char_name() in client.area.restricted_chars:
        try:
            new_char_id = client.area.get_rand_avail_char_id(allow_restricted=False)
        except AreaError:
            new_char_id = -1 # Force into spectator mode if all other available characters are taken
        client.change_character(new_char_id)
        client.send_host_message('Your character has been set to restricted in this area by a staff member. Switching you to {}.'.format(client.get_char_name()))
     
def ooc_cmd_minimap(client, arg):
    """
    Lists all areas that can be reached from the current area according to areas.yaml and passages set in-game.
    Returns all areas if no passages were defined or created for the current area.
    
    SYNTAX
    /minimap
    
    PARAMETERS
    None
    
    EXAMPLE
    /minimap
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    info = '== Areas reachable from {} =='.format(client.area.name)
    try:
        # Get all reachable areas and sort them by area ID
        sorted_areas = sorted(client.area.reachable_areas,
                              key = lambda area_name: client.server.area_manager.get_area_by_name(area_name).id)
        
        # No areas found or just the current area found means there are no reachable areas.
        if len(sorted_areas) == 0 or sorted_areas == [client.area.name]:
            info += '\r\n*No areas available.'
        # Otherwise, build the list of all reachable areas
        else:
            for area in sorted_areas:
                if area != client.area.name:
                    info += '\r\n*{}'.format(area)
    except AreaError:
        # In case no passages are set, send '<ALL>' as default answer.
        info += '\r\n<ALL>'
        
    client.send_host_message(info)
    
def ooc_cmd_motd(client, arg):
    """
    Returns the server's Message Of The Day.
    
    SYNTAX
    /motd
    
    PARAMETERS
    None
    
    EXAMPLES
    /motd
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.send_motd()

def ooc_cmd_music_list(client, arg):
    """
    Sets the client's current music list. This list is persistent between area changes and works on a client basis.
    If given no arguments, it will return the music list to its default value (in music.yaml)
    The list of music lists can be accessed with /music_lists.
    Clients that do not process 'SM' packets can use this command without crashing, but it will have no visual effect.
    Returns an error if the given music list was not found.
    
    SYNTAX
    /music_list <music_list>
    
    PARAMETERS
    <music_list>: Name of the intended music_list
    
    EXAMPLES
    /music_list dr2         :: Load the "dr2" music list.
    /music_list             :: Reset the music list to its default value.
    """
    if len(arg) == 0:
        client.music_list = None
        client.reload_music_list()
        client.send_host_message('Restored music list to its default value.')
    else:
        try:
            new_music_file = 'config/music_lists/{}.yaml'.format(arg)
            client.reload_music_list(new_music_file=new_music_file)
        except ServerError:
            raise ArgumentError('Could not find music list file: {}'.format(arg))
        
        client.send_host_message('Loaded music list: {}'.format(arg))

def ooc_cmd_music_lists(client, arg):
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
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    try:
        with open('config/music_lists.yaml', 'r') as f:
            output = 'Available music lists:\n'
            for line in f:
                output += '*{}'.format(line)
            client.send_host_message(output)
    except FileNotFoundError:
        raise ClientError('Server file music_lists.yaml not found.')
        
def ooc_cmd_mute(client, arg):
    """ (CM AND MOD ONLY)
    Mutes given user based on client ID or IPID so that they are unable to speak in IC chat.
    If given IPID, it will mute all clients opened by the user. Otherwise, it will just mute the given client.
    Requires /unmute to undo.
    Returns an error if the given identifier does not correspond to a user.
    
    SYNTAX
    /mute <client_id>
    /mute <client_ipid>
    
    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /mute 1                     :: Mutes client whose ID is 1.
    /mute 1234567890            :: Mutes all clients opened by the user whose IPID is 1234567890.
    """
    
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10 or not arg.isdigit():
        raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
    
    # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
    # This places the assumption that there are no more than 10 billion clients connected simultaneously
    # but if that is the case, you probably have a much larger issue at hand.
    if len(arg) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    else:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    
    # Mute matching targets
    if targets:
        for c in targets:
            logger.log_server('Muted {}.'.format(c.ipid), client)
            client.area.send_host_message("{} was muted.".format(c.get_char_name()))
            c.is_muted = True
    else:
        client.send_host_message("No targets found.")

def ooc_cmd_mutepm(client, arg):
    """
    Toggles between being able to receive PMs or not.
    
    SYNTAX
    /mutepm
    
    PARAMETERS
    None
    
    EXAMPLE
    /mutepm
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments.")
    
    client.pm_mute = not client.pm_mute
    status = {True: 'You stopped receiving PMs.', False: 'You are now receiving PMs.'}
    client.send_host_message(status[client.pm_mute]) 
    
def ooc_cmd_play(client, arg):
    """ (STAFF ONLY)
    Plays a given track, even if not explicitly in the music list. It is the way to play custom music.
    
    SYNTAX
    /play <track_name>
    
    PARAMETERS:
    <track_name>: Track to play
    
    EXAMPLES:
    /play Trial(AJ).mp3         :: Plays Trial(AJ).mp3
    /play CustomTrack.mp3       :: Plays CustomTrack.mp3 (will only be audible to users with CustomTrack.mp3)
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    
    if len(arg) == 0:
        raise ArgumentError('You must specify a song.')
    
    client.area.play_music(arg, client.char_id, -1)
    client.area.add_music_playing(client, arg)
    logger.log_server('[{}][{}]Changed music to {}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_pm(client, arg):
    """
    Sends a personal message to a specified user.
    Returns an error if the user could not be found.
    
    SYNTAX
    /pm <user_id> <message>
    
    PARAMETERS
    <user_id>: Either the character name, the client ID (number in brackets in /getarea) or OOC username of the intended recipient.
    <message>: Message to be sent.
    
    EXAMPLES
    /pm Santa What will I get for Christmas?    :: Sends that message to the user whose name is Santa.
    /pm 0 Nothing                               :: Sends that message to the user whose client ID is 0.
    /pm Santa_HD Sad                            :: Sends that message to the user whose character name is Santa_HD.
    """
    args = arg.split()
    key = ''
    msg = None
    if len(args) < 2:
        raise ArgumentError('Not enough arguments. use /pm <target> <message>. Target should be ID, OOC-name or char-name. Use /getarea for getting info like "[ID] char-name".')
    
    # Pretend the identifier is a character name
    targets = client.server.client_manager.get_targets(client, TargetType.CHAR_NAME, arg, True)
    key = TargetType.CHAR_NAME
    
    # If still needed, pretend the identifier is a client ID
    if len(targets) == 0 and args[0].isdigit():
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(args[0]), False)
        key = TargetType.ID
    
    # If still needed, pretend the identifier is an OOC username
    if len(targets) == 0:
        targets = client.server.client_manager.get_targets(client, TargetType.OOC_NAME, arg, True)
        key = TargetType.OOC_NAME
    
    # If no matching targets found, be sad.
    if len(targets) == 0:
        raise ArgumentError('No targets found.')
        
    # Obtain the message from the given arguments
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
    
    # Attempt to send the message to the target, provided they do not have PMs disabled.
    c = targets[0]
    if c.pm_mute:
        raise ClientError('This user muted all pm conversation.')
    else:
        c.send_host_message('PM from {} in {} ({}): {}'.format(client.name, client.area.name, client.get_char_name(), msg))
        client.send_host_message('PM sent to {}. Message: {}'.format(args[0], msg))
        
def ooc_cmd_pos(client, arg):
    """ 
    Switches the character to the given position, or to its original position if not given one.
    Returns an error if position is invalid.
    
    SYNTAX
    /pos {new_position}
    
    PARAMETERS
    {new_position}: New character position (jud, def, pro, hlp, hld)
    
    EXAMPLES
    /pos jud                :: Switches to the judge position
    /pos                    :: Resets to original position
    """
    # Resetting to original position
    if len(arg) == 0:
        client.change_position()
        client.send_host_message('Position reset.')
    
    # Switching position
    else:
        try:
            client.change_position(arg)
        except ClientError:
            raise
        client.area.broadcast_evidence_list()
        client.send_host_message('Position changed.')   

def ooc_cmd_randomchar(client, arg):
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
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
   
    try:
        free_id = client.area.get_rand_avail_char_id(allow_restricted=client.is_staff())
    except AreaError:
        raise
    
    try:
        client.change_character(free_id)
    except ClientError:
        raise
    
    client.send_host_message('Randomly switched to {}'.format(client.get_char_name()))

def ooc_cmd_reload(client, arg):
    """
    Reloads the character for the current user (equivalent to switching to the current character).
    
    SYNTAX
    /reload
    
    PARAMETERS
    None
    
    EXAMPLE
    /reload
    """
    if len(arg) != 0:
        raise ArgumentError("This command doesn't take any arguments")
    
    try:
        client.reload_character()
    except ClientError:
        raise
    
    client.send_host_message('Character reloaded.') 

def ooc_cmd_reveal(client, arg):    
    """ (STAFF ONLY)
    Sets given user based on client ID or IPID to no longer be sneaking so that they are visible through /getarea(s).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect the given client.
    Requires /sneak to undo.
    Returns an error if the given identifier does not correspond to a user.
    
    SYNTAX
    /reveal <client_id>
    /reveal <client_ipid>
    
    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /reveal 1                     :: Set client whose ID is 1 to no longer be sneaking.
    /reveal 1234567890            :: Set all clients opened by the user whose IPID is 1234567890 to no longer be sneaking.
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10 or not arg.isdigit():
        raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
        
    # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
    # This places the assumption that there are no more than 10 billion clients connected simultaneously
    # but if that is the case, you probably have a much larger issue at hand.
    if len(arg) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    else:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    
    # Unsneak matching targets
    if targets:
        for c in targets:
            logger.log_server('{} is no longer sneaking.'.format(c.ipid), client)
            if c != client:
                client.send_host_message("{} is no longer sneaking.".format(c.get_char_name()))
            c.send_host_message("You are no longer sneaking.")
            c.is_visible = True
    else:
        client.send_host_message("No targets found.")
    
def ooc_cmd_roll(client, arg):
    """
    Rolls a given number of dice with given number of faces and modifiers.
    If certain parameters are not given, command assumes preset defaults.
    Raises an error if parameters exceed specified constants or an invalid mathematical operation is put as a modifier.
    
    For modifiers, the modifier's result will ignore the given number of faces cap and instead use NUMFACES_MAX (so dice rolls can exceed number of faces).
    However, the modifier's result is bottom capped at 1 (so non-positive values are not allowed).
    Modifiers follow PEMDAS, and if not given the dice result (character "r"), will try and perform the operation directly.
    
    SYNTAX
    /roll {num_faces} {modifier}
    /roll {num_dice}d<num_faces> {modifier}
    
    PARAMETERS
    <num_faces>: Number of faces the dice will have (capped at NUMFACES_MAX)
    {num_dice}: Number of dice to roll (capped at NUMDICE_MAX)
    {modifier}: Operation to perform on rolls
    
    EXAMPLES
    /roll                           :: Rolls DEF_NUMDICE dice with DEF_NUMFACES faces and DEF_MODIFIER modifier
    /roll 20                        :: Rolls a d20.
    /roll 5d30                      :: Rolls 5 d30's.
    /roll d20 +3                    :: Rolls a d20 and adds 3 to the result.
    /roll 1d20 +3*2                 :: Rolls a d20 and adds 3*2=6 to the result.
    /roll 6 -1+3*r                  :: Rolls a d6, multiplies the result by 3 and subtracts 1 to it.
    /roll 3d6 (-1+3)*r              :: Rolls 3 d6's and mutliplies each result by 2.
    """
    
    roll_result, num_faces = dice_roll(arg, 'roll') # Moved calculation of roll code to helper function so rollp can reuse it

    client.area.send_host_message('{} rolled {} out of {}.'.format(client.get_char_name(), roll_result, num_faces))
    logger.log_server(
        '[{}][{}]Used /roll and got {} out of {}.'.format(client.area.id, client.get_char_name(), roll_result, num_faces), client)
    
def ooc_cmd_rollp(client, arg):
    """
    Similar to /roll, but instead only announces roll results (and who rolled) to staff members.
    Returns an error if current area does not authorize /rollp and user is not logged in.
    
    SYNTAX
    /rollp {num_faces} {modifier}
    /rollp {num_dice}d<num_faces> {modifier}
    
    PARAMETERS
    {num_faces}: Number of faces the dice will have (capped at NUMFACES_MAX)
    {num_dice}: Number of dice to roll (capped at NUMDICE_MAX)
    {modifier}: Operation to perform on rolls
    
    EXAMPLES
    /rollp                           :: Rolls DEF_NUMDICE dice with DEF_NUMFACES faces and DEF_MODIFIER modifier
    /rollp 20                        :: Rolls a d20.
    /rollp 5d30                      :: Rolls 5 d30's.
    /rollp d20 +3                    :: Rolls a d20 and adds 3 to the result.
    /rollp 1d20 +3*2                 :: Rolls a d20 and adds 3*2=6 to the result.
    /rollp 6 -1+3*r                  :: Rolls a d6, multiplies the result by 3 and subtracts 1 to it.
    /rollp 3d6 (-1+3)*r              :: Rolls 3 d6's and mutliplies each result by 2.
    """
    if not client.area.rollp_allowed and not client.is_staff():
        client.send_host_message("This command has been restricted to authorized users only in this area.")
        return
    
    roll_result, num_faces = dice_roll(arg, 'rollp') # Moved calculation of roll code to helper function so roll can reuse it
        
    client.send_host_message('You privately rolled {} out of {}.'.format(roll_result, num_faces))    
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    'Someone rolled.', pred=lambda c: not c.is_staff() 
                                    and c != client and c.area.name == client.area.name) 
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    '{} privately rolled {} out of {} in {} ({}).'
                                    .format(client.get_char_name(), roll_result, num_faces, client.area.name, client.area.id), 
                                    pred=lambda c: c.is_staff() and c != client)
    
    SALT = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    logger.log_server(
        '[{}][{}]Used /rollp and got {} out of {}.'
        .format(client.area.id, client.get_char_name(), 
                hashlib.sha1((str(roll_result) + SALT).encode('utf-8')).hexdigest() + '|' + SALT, num_faces), client)

def ooc_cmd_rplay(client, arg):
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
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('You must specify a song.')
    
    for reachable_area_name in client.area.reachable_areas:
        reachable_area = client.server.area_manager.get_area_by_name(reachable_area_name)
        reachable_area.play_music(arg, client.char_id, -1)
        reachable_area.add_music_playing(client, arg)
        logger.log_server('[{}][{}]Changed music to {}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_scream(client, arg):
    """
    Sends a message in the OOC chat visible to all staff members and users that 
    are in an area reachable from the sender's area that is not soundproof.
    Returns an error if the user has global chat off or sends an empty message.
    
    SYNTAX
    /scream <message>
    
    PARAMETERS
    <message>: Message to be sent
    
    EXAMPLE
    /scream Hello World      :: Sends Hello World to users in reachable areas+staff.
    """
    if client.muted_global:
        raise ClientError('You have the global chat muted.')
    if len(arg) == 0:
        raise ArgumentError("You cannot send an empty message.")
    
    client.server.broadcast_global(client, arg, mtype="<dollar>SCREAM", 
                                   condition=lambda c: not c.muted_global and 
                                   (c.is_staff() or c.area == client.area or 
                                    c.area.name in client.area.scream_range))
    logger.log_server('[{}][{}][SCREAM]{}.'.format(client.area.id, client.get_char_name(), arg), client)

def ooc_cmd_showname(client, arg):
    """
    If given an argument, sets the client's showname to that. 
    Otherwise, it clears their showname to use the default setting (character showname).
    
    These custom shownames override whatever showname the current character has, and is 
    persistent between between character swaps/area changes/etc.
    
    SYNTAX
    /showname <new_showname>
    /showname
    
    PARAMETERS
    <new_showname>: New desired showname.
    
    EXAMPLES
    /showname Phantom       :: Sets your showname as Phantom
    /showname               :: Clears your showname
    """
    client.showname = arg
    if arg != '':
        client.send_host_message('You have set your showname as: {}'.format(arg))
    else:
        client.send_host_message('You have removed your custom showname.')

def ooc_cmd_sneak(client, arg):    
    """ (STAFF ONLY)
    Sets given user based on client ID or IPID to be sneaking so that they are invisible through /getarea(s).
    If given IPID, it will affect all clients opened by the user. Otherwise, it will just affect the given client.
    Requires /reveal to undo.
    Returns an error if the given identifier does not correspond to a user.
    
    SYNTAX
    /sneak <client_id>
    /sneak <client_ipid>
    
    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /sneak 1                     :: Set client whose ID is 1 to be sneaking.
    /sneak 1234567890            :: Set all clients opened by the user whose IPID is 1234567890 to be sneaking.
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10 or not arg.isdigit():
        raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
     
    # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
    # This places the assumption that there are no more than 10 billion clients connected simultaneously
    # but if that is the case, you probably have a much larger issue at hand.
    if len(arg) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    else:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    
    # Sneak matching targets
    if targets:
        for c in targets:
            if client.is_gm and c.area.lobby_area:
                client.send_host_message('Target client is in a lobby area. You have insufficient permissions to hide someone in such an area.')
                continue
            if c.area.private_area:
                client.send_host_message('Target client is in a private area. You are not allowed to hide someone in such an area.')
                continue
            
            logger.log_server('{} is now sneaking.'.format(c.ipid), client)
            if c != client:
                client.send_host_message("{} is now sneaking.".format(c.get_char_name()))
            c.send_host_message("You are now sneaking.")
            c.is_visible = False
    else:
        client.send_host_message("No targets found.")

def ooc_cmd_st(client, arg):
    """ (STAFF ONLY)
    Send a message to the private server-wide staff chat. Only staff members can send
    and receive messages from it (i.e. it is not a report command for normal users).
    
    SYNTAX
    /st <message>
    
    PARAMETERS
    <message>: Your message
    
    EXAMPLES
    /st Need help in area 0.       :: Sends "Need help in area 0" to all staff members.
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
        
    client.server.send_all_cmd_pred('CT','{} [Staff] {}'.format(client.server.config['hostname'], client.name), arg,
                                    pred=lambda c: c.is_staff())
    logger.log_server('[{}][STAFFCHAT][{}][{}]{}.'.format(client.area.id, client.get_char_name(), client.name, arg), client)
            
def ooc_cmd_switch(client, arg):
    """ 
    Switches current user's character to a different one. 
    Raises an error if character is unavailable or non-existant.
    
    SYNTAX
    /switch <char_name>
    
    PARAMETERS
    <char_name>: Character name 
    
    EXAMPLES
    /switch Phoenix_HD      
    """
    if len(arg) == 0:
        raise ArgumentError('You must specify a character name.')
#    
    # Obtain char_id if character exists
    try:
        cid = client.server.get_char_id_by_name(arg)
    except ServerError:
        raise
        
    # Try and change to given char if available
    try:
        client.change_character(cid, client.is_mod)
    except ClientError:
        raise
    client.send_host_message('Character changed.')

def ooc_cmd_time(client, arg):
    """
    Return the current server date and time.
    
    SYNTAX
    /time
    
    PARAMETERS
    None
    
    EXAMPLES
    /time           :: May return something like "Sat Apr 27 09:04:17 2019"
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.send_host_message(time.asctime(time.localtime(time.time())))

def ooc_cmd_time12(client, arg):
    """
    Return the current server date and time in 12 hour format.
    Also includes the server timezone.
    
    SYNTAX
    /time12
    
    PARAMETERS
    None
    
    EXAMPLES
    /time12         :: May return something like "Sat Apr 27 09:04:47 AM (EST) 2019"
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.send_host_message(time.strftime('%a %b %e %I:%M:%S %p (%z) %Y'))
			
def ooc_cmd_ToD(client, arg):
    """
    Choose "Truth" or "Dare". Intended to be use for participants in Truth or Dare games.
    
    SYNTAX
    /ToD
    
    PARAMETERS
    None
    
    EXAMPLES
    /ToD                :: May return something like 'Phoenix_HD has to do a truth.'
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    coin = ['truth', 'dare']
    flip = random.choice(coin)
    client.area.send_host_message('{} has to do a {}.'.format(client.get_char_name(), flip))
    logger.log_server(
        '[{}][{}]has to do a {}.'.format(client.area.id, client.get_char_name(), flip), client)

def ooc_cmd_toggleglobal(client, arg):
    """
    Toggles global messages being sent to the current user being allowed/disallowed
    
    SYNTAX
    /toggleglobal
    
    PARAMETERS
    None
    
    EXAMPLE
    /toggleglobal
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
        
    client.muted_global = not client.muted_global
    status = {False: 'on', True: 'off'}

    client.send_host_message('Global chat turned {}.'.format(status[client.muted_global]))
    
def ooc_cmd_toggle_rollp(client, arg):
    """ (STAFF ONLY)
    Toggles private rolls by non-staff in the current area being allowed/disallowed.
    
    SYNTAX
    /toggle_rollp
    
    PARAMETERS
    None
    
    EXAMPLES
    /toggle_rollp 
    """
    
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    client.area.rollp_allowed = not client.area.rollp_allowed
    status = {False: 'disabled', True: 'enabled'}
    
    client.area.send_host_message('A staff member has {} the use of private roll commands in this area.'.format(status[client.area.rollp_allowed]))
    logger.log_server('[{}][{}]{} private roll commands in this area.'
                      .format(client.area.id, client.get_char_name(), 
                              status[client.area.rollp_allowed].capitalize()), client)

def ooc_cmd_toggle_rpgetarea(client, arg):
    """ (STAFF ONLY)
    Toggles users subject to RP mode being able/unable to use /getarea in the current area.
    
    SYNTAX
    /toggle_rpgetarea
    
    PARAMETERS
    None
    
    EXAMPLE
    /toggle_rpgetarea
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    client.area.rp_getarea_allowed = not client.area.rp_getarea_allowed
    status = {False: 'disabled', True: 'enabled'}
    
    client.area.send_host_message('A staff member has {} the use of /getarea in this area.'.format(status[client.area.rp_getarea_allowed]))
    logger.log_server('[{}][{}]{} /getarea in this area.'
                      .format(client.area.id, client.get_char_name(), 
                              status[client.area.rp_getarea_allowed].capitalize()), client)
     
def ooc_cmd_toggle_rpgetareas(client, arg):
    """ (STAFF ONLY)
    Toggles users subject to RP mode being able/unable to use /getareas in the current area.
    
    SYNTAX
    /toggle_rpgetareas
    
    PARAMETERS
    None
    
    EXAMPLE
    /toggle_rpgetareas
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    client.area.rp_getareas_allowed = not client.area.rp_getareas_allowed
    status = {False: 'disabled', True: 'enabled'}
    
    client.area.send_host_message('A staff member has {} the use of /getareas in this area.'.format(status[client.area.rp_getareas_allowed]))
    logger.log_server('[{}][{}]{} /getareas in this area.'
                      .format(client.area.id, client.get_char_name(), 
                              status[client.area.rp_getareas_allowed].capitalize()), client)
     
def ooc_cmd_unban(client, arg):
    """ (MOD ONLY)
    Removes given user from the server banlist, allowing them to rejoin the server.
    Returns an error if given IPID does not correspond to a banned user.
    
    SYNTAX
    /unban <client_ipid>
    
    PARAMETERS
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /unban 1234567890           :: Unbans user whose IPID is 1234567890
    """
    if not client.is_mod:
        raise ClientError('You must be authorized to do that.')
    
    # Assumes that any error is caused by putting something other than an IPID.
    try:
        client.server.ban_manager.remove_ban(int(arg.strip()))
    except:
        raise ClientError('You must specify \'hdid\'')
    
    logger.log_server('Unbanned {}.'.format(arg), client)
    client.send_host_message('Unbanned {}'.format(arg))

def ooc_cmd_unglobalic(client, arg):
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
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    client.multi_ic = None
    client.send_host_message('Your IC messages will now be just sent to your current area.')

def ooc_cmd_unmute(client, arg):
    """ (CM AND MOD ONLY)
    Unmutes given user based on client ID or IPID so that they are unable to speak in IC chat.
    If given IPID, it will unmute all clients opened by the user. Otherwise, it will just mute the given client.
    This command does nothing for clients that are not actively muted.
    Returns an error if the given identifier does not correspond to a user.
    
    SYNTAX
    /unmute <client_id>
    /unmute <client_ipid>
    
    PARAMETERS
    <client_id>: Client identifier (number in brackets in /getarea)
    <client_ipid>: 10-digit user identifier (number in parentheses in /getarea)
    
    EXAMPLES
    /unmute 1                     :: Unmutes client whose ID is 1.
    /unmute 1234567890            :: Unmutes all clients opened by the user whose IPID is 1234567890.
    """
    
    if not client.is_mod and not client.is_cm:
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0 or len(arg) > 10 or not arg.isdigit():
        raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(arg))
    
    # Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
    # This places the assumption that there are no more than 10 billion clients connected simultaneously
    # but if that is the case, you probably have a much larger issue at hand.
    if len(arg) == 10:
        targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(arg), False)
    else:
        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg), False)
    
    # Mute matching targets
    if targets:
        for c in targets:
            logger.log_server('Unmuted {}.'.format(c.ipid), client)
            client.area.send_host_message("{} was unmuted.".format(c.get_char_name()))
            c.is_muted = False
    else:
        client.send_host_message("No targets found.")
    
def ooc_cmd_8ball(client, arg):
    """
    Call upon the wisdom of a magic 8 ball. The result is sent to all clients in the sender's area.
    
    SYNTAX
    /8ball
    
    PARAMETERS
    None
    
    EXAMPLES
    /8ball              :: May return something like "The magic 8 ball says You shouldn't ask that."
    """
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
        
    coin = ['yes', 'no', 'maybe', "I don't know", 'perhaps', 'please do not', 'try again', "you shouldn't ask that"]
    flip = random.choice(coin)
    client.area.send_host_message('The magic 8 ball says {}.'.format(flip))
    logger.log_server(
        '[{}][{}]called upon the magic 8 ball and it said {}.'.format(client.area.id,client.get_char_name(),flip), client)
		
def ooc_cmd_bilock(client, arg):
    areas = arg.split(', ')
    if len(areas) > 2 or arg == '':
        raise ArgumentError('This command takes one or two arguments.')
    elif len(areas) == 2 and not client.is_staff():
        raise ClientError('You must be authorized to use the two-parameter version of this command.')
    
    areas = parse_two_area_names(client, areas, area_duplicate = False,
                                 check_valid_range = False)
    
    for i in range(2):
        if not areas[i].change_reachability_allowed and not client.is_staff():
            raise ClientError('Changing area reachability without authorization is disabled in area {}.'.format(areas[i].name))
        
    now_reachable = []
    formerly_reachable = [areas[i].reachable_areas for i in range(2)] #Just in case something goes wrong, revert back
    for i in range(2):
        reachable = areas[i].reachable_areas
        now_reachable.append(False)
        if reachable == {'<ALL>'}:
            reachable = client.server.area_manager.area_names - {areas[1-i].name}
        else:
            if areas[1-i].name in reachable:
                reachable = reachable - {areas[1-i].name}
            else:
                if not client.is_staff() and not (areas[1-i].name in areas[i].staffset_reachable_areas or
                       areas[i].staffset_reachable_areas == {'<ALL>'}):
                    client.send_host_message('You must be authorized to create a new area link from {} to {}.'.format(areas[i].name,areas[1-i].name))
                    areas[0].reachable_areas = formerly_reachable[0]
                    areas[1].reachable_areas = formerly_reachable[1]
                    return
                reachable.add(areas[1-i].name)
                now_reachable[i] = True
        areas[i].reachable_areas = reachable
        if client.is_staff():
            areas[i].staffset_reachable_areas = reachable
        
    if now_reachable[0] == now_reachable[1]:
        client.send_host_message('Set area reachability between {} and {} to {}'.format(areas[0].name,areas[1].name,now_reachable[0]))
 
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                    '{} used /bilock to {} area reachability between {} and {} in {} ({}).'
                                    .format(client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name, 
                                            client.area.name, client.area.id), pred=lambda c: c.is_staff() and c != client)
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
                                            client.area.name, client.area.id), pred=lambda c: c.is_staff() and c != client)
        logger.log_server(
            '[{}][{}]Used /bilock to {} area reachability from {} to {} and to {} area reachability from {} to {}.'
            .format(client.area.id, client.get_char_name(), 'unlock' if now_reachable[0] else 'lock', areas[0].name, areas[1].name, 
                                                            'unlock' if now_reachable[1] else 'lock', areas[1].name, areas[0].name), client)

def ooc_cmd_unilock(client, arg):
    areas = arg.split(', ')
    if len(areas) > 2 or arg == '':
        raise ArgumentError('This command takes one or two arguments.')
    elif len(areas) == 2 and not client.is_staff():
        raise ClientError('You must be authorized to use the two-parameter version of this command.')
    
    areas = parse_two_area_names(client, areas, area_duplicate = False,
                                 check_valid_range = False)
    
    if not areas[0].change_reachability_allowed and not client.is_staff():
        raise ClientError('Changing area reachability without authorization is disabled in area {}.'.format(areas[0].name))
        
    now_reachable = False
    reachable = areas[0].reachable_areas
    if reachable == {'<ALL>'}:
        reachable = client.server.area_manager.area_names - {areas[1].name}
    else:
        if areas[1].name in reachable:
            reachable = reachable - {areas[1].name}
        else:
            if not client.is_staff() and not (areas[1].name in areas[0].staffset_reachable_areas or
                   areas[0].staffset_reachable_areas == {'<ALL>'}):
                client.send_host_message('You must be authorized to create a new area link from {} to {}.'.format(areas[0].name,areas[1].name))
                return
            reachable.add(areas[1].name)
            now_reachable = True
    areas[0].reachable_areas = reachable
    if client.is_staff():
        areas[0].staffset_reachable_areas = reachable
    client.send_host_message('Set area reachability from {} to {} to {}'.format(areas[0].name,areas[1].name,now_reachable))
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                '{} used /unilock to {} area reachability from {} to {} in {} ({}).'
                                .format(client.get_char_name(), 'unlock' if now_reachable else 'lock', areas[0].name, areas[1].name, 
                                        client.area.name, client.area.id), pred=lambda c: c.is_staff() and c != client)
    logger.log_server(
        '[{}][{}]Used /unilock to {} area reachability from {} to {}.'
        .format(client.area.id, client.get_char_name(), 'unlock' if now_reachable else 'lock', areas[0].name, areas[1].name), client)


def ooc_cmd_restore_areareachlock(client, arg):
    if not client.is_staff(): 
        raise ClientError('You must be authorized to do that.')
    areas = arg.split(', ')
    if len(areas) > 2:
        raise ClientError('This command takes at most two arguments.')
    
    areas = parse_two_area_names(client, areas)  
    
    for i in range(areas[0].id, areas[1].id+1):
        area = client.server.area_manager.get_area_by_id(i)
        area.reachable_areas = set(list(area.default_reachable_areas)[:])
        area.change_reachability_allowed = area.default_change_reachability_allowed

    if areas[0] == areas[1]:    
        client.send_host_message('Area passage locks have been set to standard in {}.'.format(areas[0].name))
    else:
        client.send_host_message('Area passage locks have been set to standard in {} through {}'.format(areas[0].name,areas[1].name))

def ooc_cmd_delete_areareachlock(client, arg):
    if not client.is_staff(): 
        raise ClientError('You must be authorized to do that.')
    areas = arg.split(', ')
    if len(areas) > 2:
        raise ClientError('This command takes at most two arguments.')
    
    areas = parse_two_area_names(client, areas)
        
    for i in range(areas[0].id, areas[1].id+1):
        area = client.server.area_manager.get_area_by_id(i)
        area.reachable_areas = '<ALL>'

    if areas[0] == areas[1]:    
        client.send_host_message('Area passage locks have been removed in {}.'.format(areas[0].name))
    else:
        client.send_host_message('Area passage locks have been removed in areas {} through {}'.format(areas[0].name,areas[1].name))

def ooc_cmd_toggle_areareachlock(client, arg):
    if not client.is_staff():
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
    if not client.is_staff():
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
        elif client.is_staff() and not client.area.is_modlocked:
            client.area.gmunlock()
        elif not client.area.is_gmlocked and not client.area.is_modlocked:
            client.area.unlock()
        else:
            raise ClientError('You must be of higher authorization to do that.')
    client.send_host_message('Area is unlocked.')

def ooc_cmd_invite(client, arg):
    if not client.is_staff():
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
    if not client.is_staff():
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
                c.change_area(area, override_passages=True)
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

def ooc_cmd_rpmode(client, arg):
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if not client.server.config['rp_mode_enabled']:
        raise ClientError("RP mode is disabled in this server.")
    if len(arg) == 0:
        raise ArgumentError('You must specify either on or off.')
        
    if arg == 'on':
        client.server.rp_mode = True
        for c in client.server.client_manager.clients:
            c.send_host_message('RP mode enabled.')
            if not c.is_staff():
                c.in_rp = True
    elif arg == 'off':
        client.server.rp_mode = False
        for c in client.server.client_manager.clients:
            c.send_host_message('RP mode disabled.')
            c.in_rp = False
    else:
        client.send_host_message('Invalid argument! Valid arguments: on, off. Your argument: ' + arg)

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
            
def ooc_cmd_discord(client, arg):
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    client.send_host_message('Discord Invite Link: \r\ninsert link here \r\nBlank\'s tag: \r\nName(tag)0000 \r\nBlank\'s tag: \r\nName(tag)0000 \r\nBlank\'s tag: \r\nName(hashtag)0000')

def ooc_cmd_follow(client, arg):
    if not client.is_staff():
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
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    try:
        client.unfollow_user()
    except AttributeError:
        client.send_host_message('You are not following anyone.')

def ooc_cmd_timer(client, arg):
    TIMER_LIMIT = 21600 # 6 hours in seconds, can be changed to any amount in seconds
    
    if len(arg) == 0:
        raise ClientError('This command takes at least one argument.')
    arg = arg.split(' ')
    arg_type = arg[0]
    
    # Support for three command variations at the moment
    # Start (start timers)
    # Get (get status of given timer(s))
    # Cancel (cancel given timer)
    
    if arg_type == 'start':
        """ Start a timer
        SYNTAX 
        /timer start $length <timername> <public or not>
        
        REQUIRED
         $length: time in seconds, or in mm:ss, or in h:mm:ss; limited to TIMER_LIMIT
        
        OPTIONAL
         <timername>: Timer name; defaults to username+"Timer" if empty
         <public or not>: Whether the timer is public or not; defaults to public if
         not fed one of "False", "false", "0", "No", "no".

        Public status functionality
        * Non-public timers will only send timer announcements/can only be consulted by
          the person who initiated the timer and staff
        * Public timers initiated by non-staff will only send timer announcements/can only be
          be consulted by staff and people in the same area as the person who initiated the timer
        * Public timers initiated by staff will send timer announcements/can be consulted by
          anyone at any area.
        """
        if len(arg) == 1:
            raise ClientError('This command variation takes at least one subargument.')
        elif len(arg) >= 5:
            raise ClientError('This command variation takes at most three subarguments.')

        # Check if valid length and convert to seconds        
        raw_length = arg[1].split(':')
        try:
            length = [int(entry) for entry in raw_length]
        except ValueError:
            raise ClientError('Expected length of time.')

        if len(length) == 1:
            length = length[0]
        elif len(length) == 2:
            length = length[0]*60 + length[1]
        elif len(length) == 3:
            length = length[0]*3600 + length[1]*60 + length[2]
        else:
            raise ClientError('Expected length of time.')
        
        if length > TIMER_LIMIT:
            raise ClientError('Suggested timer length exceeds server limit.')
        
        # Check name
        if len(arg) > 2:
            name = arg[2]
        else:
            name = client.name.replace(" ", "") + "Timer" # No spaces!
        if name in client.server.active_timers.keys():
            raise ClientError('Timer name {} is already taken.'.format(name))
        
        # Check public status
        if len(arg) > 3 and arg[3] in ['False', 'false', '0', 'No', 'no']:
            is_public = False
        else:
            is_public = True
        
        client.server.active_timers[name] = client #Add to active timers list
        client.send_host_message('You initiated a timer "{}" of length {} seconds.'.format(name, length))
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                        '{} initiated a timer "{}" of length {} seconds in area {} ({}).'
                                        .format(client.get_char_name(), name, length, client.area.name, client.area.id),
                                        pred=lambda c: (c.is_staff()
                                                        or (is_public and c.area == client.area)) and c != client)
        
        client.server.create_task(client, ['as_timer', time.time(), length, name, is_public])
    elif arg_type == 'get':
        """ Get remaining time from given timer.
        SYNTAX
        /timer get <timername>
        
        OPTIONAL
        <timername>: Check time remaining in given timer; defaults to all timers
        if not given one.
        """
        if len(arg) > 2:
            raise ClientError('This command variation takes at most one subargument.')

        string_of_timers = ""
        
        
        if len(arg) == 2:
            # Check specific timer
            timer_name = arg[1]
            if timer_name not in client.server.active_timers.keys():
                raise ClientError('Timer {} is not an active timer.'.format(timer_name))
            timers_to_check = [timer_name]
            
        else: # Case len(arg) == 1
            # List all timers
            timers_to_check = client.server.active_timers.keys()
            if len(timers_to_check) == 0:
                raise ClientError('No active timers.')
            
        for timer_name in timers_to_check:
            timer_client = client.server.active_timers[timer_name]
            start, length, _, is_public = client.server.get_task_args(timer_client, ['as_timer']) 
            current = time.time()
            remaining = start+length-current
            
            # Non-public timers can only be consulted by staff and the client who started the timer
            if not is_public and not (client.is_staff() or client == timer_client):
                continue
            
            
            # Non-staff initiated public timers can only be consulted by all staff and 
            # clients in the same area as the timer initiator
            elif is_public and not timer_client.is_staff() \
                 and not (client.is_staff() or client == timer_client or client.area == timer_client.area):
                continue
            
            if remaining < 10:
                remain_text = "{} seconds".format('{0:.1f}'.format(remaining))
            elif remaining < 60:
                remain_text = "{} seconds".format(int(remaining))
            elif remaining < 3600:
                remain_text = "{}:{}".format(int(remaining//60), 
                                             '{0:02d}'.format(int(remaining%60)))
            else:
                remain_text = "{}:{}:{}".format(int(remaining//3600), 
                                                '{0:02d}'.format(int((remaining%3600)//60)), 
                                                '{0:02d}'.format(int(remaining%60)))
            string_of_timers += 'Timer {} has {} remaining.\n*'.format(timer_name, remain_text)        
        
        if string_of_timers == "": # No matching timers
            if len(arg) == 2: # Checked for a specific timer
                # This case happens when a non-authorized user attempts to check
                # a non-public timer
                string_of_timers = "Timer {} is not an active timer.  ".format(timer_name)
                # Double space intentional
            else: # len(arg) == 1
                # This case happens when a non-authorized user attempts to check
                # all timers and all timers are non-public or non-viewable.
                string_of_timers = "No timers available.  " # Double space intentional
        elif len(arg) == 1: # Used /timer get
            string_of_timers = "Current active timers:\n*" + string_of_timers # Add lead
                
        client.send_host_message(string_of_timers[:-2]) # Ignore last newline character
    elif arg_type == 'cancel':
        """ Cancel given timer. Requires logging in to cancel timers initiated by
        other users.
        SYNTAX
        /timer cancel $timername
        
        PARAMETERS
         $timername: Given timer name; returns an error if non-existant or if 
         unauthorized to cancel the timer.
        """
        if len(arg) != 2:
            raise ClientError('This command variation takes exactly one subargument.')

        timer_name = arg[1]
        try:
            timer_client = client.server.active_timers[timer_name]
        except KeyError:
            raise ClientError('Timer {} is not an active timer.'.format(timer_name))
        
        # Non-staff are only allowed to cancel their own timers
        if not client.is_staff() and client != timer_client:
            raise ClientError('You must be authorized to do that.')
            
        timer = client.server.get_task(timer_client, ['as_timer'])
        client.server.cancel_task(timer)
    else:
        """ Default case where the argument type is unrecognized. """
        raise ClientError('The command variation {} does not exist.'.format(arg_type))
    
def ooc_cmd_scream_set_range(client, arg):
    """ (STAFF ONLY)
    Set the current area's scream range to a given list of areas by name or ID separated by commas.
    This completely overrides the old scream range, unlike /scream_set.
    Passing in no arguments sets the scream range to nothing (i.e. a soundproof room).
    Note that scream ranges are unidirectional, so if you want two areas to hear one another, you must use this command twice.
    Raises an error if an invalid area name or area ID is given, or if the current area is part of the selection.
    
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
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    
    if len(arg) == 0:
        client.area.scream_range = set()
        area_names = '{}'
    else:
        areas = parse_area_names(client, arg.split(', '))       
        if client.area in areas:
            raise ArgumentError('You cannot add the current area to the scream range.')
        area_names = set([area.name for area in areas]) 
        client.area.scream_range = area_names
        
    client.send_host_message('Set the scream range of area {} to be: {}.'.format(client.area.name, area_names))
    client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                            '{} set the scream range of area {} to be: {} ({}).'
                            .format(client.get_char_name(), client.area.name, area_names, client.area.id), 
                            pred=lambda c: c.is_staff() and c != client)
    logger.log_server(
    '[{}][{}]Set the scream range of area {} to be: {}.'
    .format(client.area.id, client.get_char_name(), client.area.name, area_names), client)
    
def ooc_cmd_scream_set(client, arg):
    """ (STAFF ONLY)
    Toggles the ability of ONE given area by name or ID to hear a scream from the current area on or off.
    This only modifies the given area's status in the current area's scream range, unlike /scream_set_range.
    Note that scream ranges are unidirectional, so if you want two areas to hear one another, you must use this command twice.
    Raises an error if an invalid area name or area ID is given, or if the current area is the target of the selection.
    
    SYNTAX
    /scream_set <target_area>
    
    PARAMETERS
    <target_area>: The area whose ability to hear screams from the current area must be switched.
    
    EXAMPLES
    Assuming Area 2: Class Trial Room, 2 starts as not part of the current area's (say Basement) scream range...
    /scream_set Class Trial Room,\ 2 :: Adds "Class Trial Room, 2" to the scream range of Basement (note the \ escape character)-
    /scream_set 2                    :: Removes "Class Trial Room, 2" from the scream range of Basement.
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('This command takes one area name.')
        
    intended_area = parse_area_names(client, arg.split(', ')) # This should just return a list with one area
    if len(intended_area) > 1:
        raise ArgumentError('This command takes one area name (did you mean /scream_set_range ?).')
        
    intended_area = intended_area[0] # Convert the one element list into the area name
    if intended_area == client.area:
        raise ArgumentError('You cannot add or remove the current area from the scream range.')
    
    # If intended area not in range, add it
    if intended_area.name not in client.area.scream_range:
        client.area.scream_range.add(intended_area.name)
        client.send_host_message('Added area {} to the scream range of area {}.'.format(intended_area.name, client.area.name))
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                '{} added area {} to the scream range of area {} ({}).'
                                .format(client.get_char_name(), intended_area.name, client.area.name, client.area.id), 
                                pred=lambda c: c.is_staff() and c != client)
        logger.log_server(
        '[{}][{}]Added area {} to the scream range of area {}.'
        .format(client.area.id, client.get_char_name(), intended_area.name, client.area.name), client)
    else: # Otherwise, add it
        client.area.scream_range.remove(intended_area.name)
        client.send_host_message('Removed area {} from the scream range of area {}.'.format(intended_area.name, client.area.name))
        client.server.send_all_cmd_pred('CT','{}'.format(client.server.config['hostname']),
                                '{} removed area {} from the scream range of area {} ({}).'
                                .format(client.get_char_name(), intended_area.name, client.area.name, client.area.id), 
                                pred=lambda c: c.is_staff() and c != client)
        logger.log_server(
        '[{}][{}]Removed area {} from the scream range of area {}.'
        .format(client.area.id, client.get_char_name(), intended_area.name, client.area.name), client)

def ooc_cmd_scream_range(client, arg):
    """ (STAFF ONLY)
    Return the current area's scream range (i.e. users in which areas who would hear a /scream from the current area).
    
    SYNTAX
    /scream_range
    
    PARAMETERS
    None
    
    EXAMPLES
    /scream_range           :: Obtain the current area's scream range, for example {'Basement'}
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    info = '== Areas in scream range of area {} =='.format(client.area.name)
    # If no areas in scream range, print a manual message.
    if len(client.area.scream_range) == 0:
        info += '\r\n*No areas.'
    # Otherwise, build the list of all areas.
    else:
        for area in client.area.scream_range:
            info += '\r\n*{}'.format(area)
                
    client.send_host_message(info)
    
def ooc_cmd_char_restrict(client, arg):
    """ (STAFF ONLY)
    Toggle a character by folder name (not showname!) being able to be used in the current area by non-staff members.
    Raises an error if the character name is not recognized.
    
    SYNTAX
    /char_restrict <char_name>
    
    PARAMETERS
    <char_name>: Character name to restrict.
    
    EXAMPLES
    Assuming Phantom_HD is initially unrestricted....
    /char_restrict Phantom_HD           :: Restrict the use of Phantom_HD.
    /char_restrict Phantom_HD           :: Unrestrict the use of Phantom_HD.
    """
    if not client.is_staff():
        raise ClientError('You must be authorized to do that.')
    if len(arg) == 0:
        raise ArgumentError('This command takes one character name.')
        
    if arg not in client.server.char_list:
        raise ArgumentError('Unrecognized character folder name: {}'.format(arg))

    status = {True: 'enabled', False: 'disabled'}
    client.area.send_host_message('A staff member has {} the use of character {} in this area.'.format(status[arg in client.area.restricted_chars], arg))

    # If intended character not in area's restriction, add it
    if arg not in client.area.restricted_chars:
        client.area.restricted_chars.add(arg)
        # For all clients using the now restricted character, switch them to some other character.
        for c in client.area.clients:
            if not c.is_staff() and c.get_char_name() == arg:
                try:
                    new_char_id = c.area.get_rand_avail_char_id(allow_restricted=False)
                except AreaError:
                    new_char_id = -1 # Force into spectator mode if all other available characters are taken
                c.change_character(new_char_id)
                c.send_host_message('Your character has been set to restricted in this area by a staff member. Switching you to {}.'.format(c.get_char_name()))
    else:
        client.area.restricted_chars.remove(arg)
        
def ooc_cmd_chars_restricted(client, arg):
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
    if len(arg) != 0:
        raise ArgumentError('This command has no arguments.')
    
    info = '== Characters restricted in area {} =='.format(client.area.name)
    # If no characters restricted, print a manual message.
    if len(client.area.restricted_chars) == 0:
        info += '\r\n*No characters restricted.'
    # Otherwise, build the list of all restricted chars.
    else:
        for char_name in client.area.restricted_chars:
            info += '\r\n*{}'.format(char_name)
                
    client.send_host_message(info)

def ooc_cmd_autopass(client, arg):
    """
    Toggles enter/leave messages being sent automatically or not to users in the current area.
    Will not send those messages if logged in as staff or spectator, or while sneaking.
    Staff members will NOT receive these messages either.
    
    SYNTAX
    /autopass
    
    PARAMETERS
    None
    
    EXAMPLE
    /autopass
    """
    if len(arg) != 0:
        raise ArgumentError("This command has no arguments.")
        
    client.autopass = not client.autopass
    status = {False: 'off', True: 'on'}

    client.send_host_message('Autopass turned {}.'.format(status[client.autopass]))
    
def ooc_cmd_exec(client, arg):
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
    /exec while True: client.send_host_message("Hi")    :: Commit sudoku
    """
    # IF YOU WANT TO DISABLE /exec: REMOVE THE # IN FRONT OF return
    # IF YOU WANT TO ENABLE /exec: ADD A # IN FRONT OF return, LIKE SO: # return
    return
    
    print("Attempting to run instruction {}".format(arg))

    try:
        result = eval(arg)
        if result is not None:
            client.send_host_message(eval(arg))
    except:
        try:
            # Temporarily add "client" as a global variable, to allow using 
            # expressions such as client.send_host_message("Hi")
            globals()['client'] = client 
            exec(arg, globals())
            client.send_host_message("Executed {}".format(arg))
        except Exception as e:
            try:
                client.send_host_message("Python error: {}: {}".format(type(e).__name__, e))
            except:
                pass
    globals().pop('client', None) # Don't really want "client" to be a global variable
    return 1    # Indication that /exec is live