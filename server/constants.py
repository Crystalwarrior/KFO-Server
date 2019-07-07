import random
import re
import time

from enum import Enum
from server.exceptions import ClientError, ServerError, ArgumentError, AreaError

class TargetType(Enum):
    #possible keys: ip, OOC, id, cname, ipid, hdid
    IP = 0
    OOC_NAME = 1
    ID = 2
    CHAR_NAME = 3
    IPID = 4
    HDID = 5
    ALL = 6

class Constants():
    @staticmethod
    def get_time():
        return time.asctime(time.localtime(time.time()))

    @staticmethod
    def get_time_iso():
        return time.strftime('[%Y-%m-%dT%H:%M:%S]')

    @staticmethod
    def time_remaining(start, length):
        current = time.time()
        remaining = start+length-current
        return remaining, Constants.time_format(remaining)

    @staticmethod
    def time_elapsed(start):
        current = time.time()
        return Constants.time_format(current-start)

    @staticmethod
    def time_format(length):
        if length < 10:
            text = "{} seconds".format('{0:.1f}'.format(length))
        elif length < 60:
            text = "{} seconds".format(int(length))
        elif length < 3600:
            text = "{}:{}".format(int(length//60),
                                  '{0:02d}'.format(int(length%60)))
        else:
            text = "{}:{}:{}".format(int(length//3600),
                                     '{0:02d}'.format(int((length%3600)//60)),
                                     '{0:02d}'.format(int(length%60)))
        return text

    @staticmethod
    def dice_roll(arg, command_type):
        """
        Calculate roll results.
        Confront /roll documentation for more details.
        """
        NUMFACES_MAX = 11037
        NUMDICE_MAX = 20
        MODIFIER_LENGTH_MAX = 12 #Change to a higher number at your own risk
        ACCEPTABLE_IN_MODIFIER = '1234567890+-*/().r'
        MAXDIVZERO_ATTEMPTS = 10
        MAXACCEPTABLETERM = 2 * NUMFACES_MAX #Change to a higher number at your own risk

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
                raise ArgumentError('This command takes one or two arguments. Use /{} <num_dice>d<num_faces> <modifiers>'.format(command_type))

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

        for _ in range(num_dice):
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
                    for j in "+-*/()":
                        aux = aux.replace(j, "!")
                    aux = aux.split('!')
                    for j in aux:
                        try:
                            if j != '' and round(float(j)) > MAXACCEPTABLETERM:
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

            final_roll = min(MAXACCEPTABLETERM, max(1, mid_roll))

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

    @staticmethod
    def disemvowel_message(message):
        return Constants.remove_letters(message, 'aeiou')

    @staticmethod
    def disemconsonant_message(message):
        return Constants.remove_letters(message, 'bcdfghjklmnpqrstvwxyz')

    @staticmethod
    def fix_and_setify(csv_values):
        """
        For the area parameters that include lists of comma-separated values, parse them appropiately
        before turning them into sets.
        """
        l = csv_values.split(', ')
        for i in range(len(l)): #Ah, escape characters... again...
            l[i] = l[i].replace(',\\', ',')

        if l in [list(), ['']]:
            return set()
        return set(l)

    @staticmethod
    def gimp_message():
        message = ['ERP IS BAN',
                   'I\'m fucking gimped because I\'m both autistic and a retard!',
                   'HELP ME',
                   'Boy, I sure do love Dia, the best admin, and the cutest!!!!!',
                   'I\'M SEVERELY AUTISTIC!!!!',
                   '[PEES FREELY]',
                   'KILL ME',
                   'I found this place on reddit XD',
                   '(((((case????)))))',
                   'Anyone else a fan of MLP?',
                   'does this server have sans from undertale?',
                   'what does call mod do',
                   'does anyone have a miiverse account?',
                   'Drop me a PM if you want to ERP',
                   'Join my discord server please',
                   'can I have mod pls?',
                   'why is everyone a missingo?',
                   'how 2 change areas?',
                   'does anyone want to check out my tumblr? :3',
                   '19 years of perfection, i don\'t play games to fucking lose',
                   'nah... your taunts are fucking useless... only defeat angers me... by trying to taunt just earns you my pitty',
                   'When do we remove dangits',
                   'MODS STOP GIMPING ME',
                   'Please don\'t say things like ni**er and f**k it\'s very rude and I don\'t like it',
                   'PLAY NORMIES PLS']
        return random.choice(message)

    @staticmethod
    def parse_area_names(client, areas):
        """
        Convert a list of area names or IDs into area objects.
        """
        area_list = list()
        # Replace arguments with proper area objects
        for i in range(len(areas)):
            #The escape character combination for areas that have commas in their name is ',\' (yes, I know it's inverted)
            #This double try block takes into account the possibility that some weird person wants ',\' as part of their actual area name
            #If you are that person... just... why
            try:
                area_list.append(client.server.area_manager.get_area_by_name(areas[i].replace(',\\', ',')))
            except AreaError:
                try:
                    area_list.append(client.server.area_manager.get_area_by_name(areas[i]))
                except AreaError:
                    try:
                        area_list.append(client.server.area_manager.get_area_by_id(int(areas[i])))
                    except:
                        raise ArgumentError('Could not parse area {}'.format(areas[i]))
        return area_list

    @staticmethod
    def parse_id(client, identifier):
        """
        Given a client ID, returns the client that matches this identifier.
        """
        if identifier == '':
            raise ArgumentError('Expected client ID.')
        if not identifier.isdigit():
            raise ArgumentError('{} does not look like a valid client ID.'.format(identifier))

        targets = client.server.client_manager.get_targets(client, TargetType.ID, int(identifier), False)

        if not targets:
            raise ClientError('No targets found.')

        return targets[0]

    @staticmethod
    def parse_id_or_ipid(client, identifier):
        """
        Given either a client ID or IPID, returns all clients that match this identifier.

        Assumes that all 10 digit numbers are IPIDs and any smaller numbers are client IDs.
        This places the assumption that there are no more than 10 billion clients connected simultaneously
        but if that is the case, you probably have a much larger issue at hand.
        """
        if identifier == '':
            raise ArgumentError('Expected client ID or IPID.')
        if not identifier.isdigit() or len(identifier) > 10:
            raise ArgumentError('{} does not look like a valid client ID or IPID.'.format(identifier))

        if len(identifier) == 10:
            targets = client.server.client_manager.get_targets(client, TargetType.IPID, int(identifier), False)
        else:
            targets = client.server.client_manager.get_targets(client, TargetType.ID, int(identifier), False)

        if not targets:
            raise ArgumentError('No targets found.')

        return targets

    @staticmethod
    def parse_passage_lock(client, areas, bilock=False):
        now_reachable = []
        num_areas = 2 if bilock else 1

        # First check if it is the case a non-authorized use is trying to change passages to areas that
        # do not allow their passages to be modified
        for i in range(num_areas):
            if not areas[i].change_reachability_allowed and not client.is_staff():
                raise ClientError('Changing area passages without authorization is disabled in area {}.'
                                  .format(areas[i].name))

        # Just in case something goes wrong, have a backup to revert back
        formerly_reachable = [areas[i].reachable_areas for i in range(num_areas)]

        for i in range(num_areas):
            reachable = areas[i].reachable_areas
            now_reachable.append(False)

            if reachable == {'<ALL>'}: # Case removing a passage from an area with passages to all areas
                reachable = client.server.area_manager.area_names - {areas[1-i].name}
            elif areas[1-i].name in reachable: # Case removing a passage
                reachable = reachable - {areas[1-i].name}
            else: # Case creating a passage
                # Make sure that non-authorized users cannot create passages that were not already there
                if not (client.is_staff() or areas[1-i].name in areas[i].staffset_reachable_areas or
                        areas[i].staffset_reachable_areas == {'<ALL>'}):
                    # And if they do, restore formerly reachable areas
                    areas[0].reachable_areas = formerly_reachable[0]
                    areas[1].reachable_areas = formerly_reachable[1]
                    raise ClientError('You must be authorized to create a new area passage from {} to {}.'
                                      .format(areas[i].name, areas[1-i].name))
                reachable.add(areas[1-i].name)
                now_reachable[i] = True

            areas[i].reachable_areas = reachable
            if client.is_staff():
                areas[i].staffset_reachable_areas = reachable

        return now_reachable

    @staticmethod
    def parse_time_length(time_length):
        """
        Convert seconds into a formatted string representing timelength.
        """
        TIMER_LIMIT = 21600 # 6 hours in seconds
        # Check if valid length and convert to seconds
        raw_length = time_length.split(':')
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
        if length <= 0:
            raise ClientError('Expected positive time length.')
        return length

    @staticmethod
    def parse_two_area_names(client, areas, area_duplicate=True, check_valid_range=True):
        """
        Convert the area passage commands inputs into inputs for parse_area_names.
        and check for the different cases it needs to possibly handle
        """
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
        areas = Constants.parse_area_names(client, areas)

        if check_valid_range and areas[0].id > areas[1].id:
            raise ArgumentError('The ID of the first area must be lower than the ID of the second area.')
        if not area_duplicate and areas[0].id == areas[1].id:
            raise ArgumentError('Areas must be different.')

        return areas

    @staticmethod
    def remove_h_message(message):
        return Constants.remove_letters(message, 'h')

    @staticmethod
    def remove_letters(message, target):
        message = re.sub("[{}]".format(target), "", message, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", message)