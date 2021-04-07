# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-21 Chrezm/Iuvee <thechrezm@gmail.com>
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

# WARNING!
# This class will suffer major reworkings for 4.3

import asyncio
import errno
import importlib
import json
import random
import socket
import ssl
import sys
import traceback
import urllib.request, urllib.error
import warnings

from server import logger
from server.aoprotocol import AOProtocol
from server.area_manager import AreaManager
from server.ban_manager import BanManager
from server.constants import Constants
from server.client_manager import ClientManager
from server.districtclient import DistrictClient
from server.exceptions import ServerError
from server.game_manager import GameManager
from server.masterserverclient import MasterServerClient
from server.party_manager import PartyManager
from server.timer_manager import TimerManager
from server.tasker import Tasker
from server.trial_manager import TrialManager
from server.zone_manager import ZoneManager

from server.validate.backgrounds import ValidateBackgrounds
from server.validate.characters import ValidateCharacters
from server.validate.config import ValidateConfig
from server.validate.gimp import ValidateGimp
from server.validate.music import ValidateMusic


class TsuserverDR:
    def __init__(self, protocol=None, client_manager=None, in_test=False):
        self.logged_packet_limit = 100  # Arbitrary
        self.logged_packets = []
        self.print_packets = False  # For debugging purposes
        self._server = None  # Internal server object, changed to proper object later

        self.release = 4
        self.major_version = 3
        self.minor_version = 0
        self.segment_version = 'b145'
        self.internal_version = 'M210406b'
        version_string = self.get_version_string()
        self.software = 'TsuserverDR {}'.format(version_string)
        self.version = 'TsuserverDR {} ({})'.format(version_string, self.internal_version)
        self.in_test = in_test

        self.protocol = AOProtocol if protocol is None else protocol
        client_manager = ClientManager if client_manager is None else client_manager
        logger.log_print = logger.log_print2 if self.in_test else logger.log_print
        logger.log_server = logger.log_server2 if self.in_test else logger.log_server
        self.random = importlib.reload(random)

        logger.log_print('Launching {}...'.format(self.version))
        logger.log_print('Loading server configurations...')

        self.config = None
        self.local_connection = None
        self.district_connection = None
        self.masterserver_connection = None
        self.shutting_down = False
        self.loop = None
        self.last_error = None
        self.allowed_iniswaps = None
        self.area_list = None
        self.old_area_list = None
        self.default_area = 0
        self.all_passwords = list()

        self.load_config()
        self.client_manager = client_manager(self)
        self.char_list = list()
        self.load_iniswaps()
        self.load_characters()

        self.game_manager = GameManager(self)
        self.trial_manager = TrialManager(self)
        self.zone_manager = ZoneManager(self)
        self.area_manager = AreaManager(self)
        self.ban_manager = BanManager(self)
        self.party_manager = PartyManager(self)

        self.ipid_list = {}
        self.hdid_list = {}
        self.music_list = None
        self.backgrounds = None
        self.gimp_list = list()
        self.load_commandhelp()
        self.load_music()
        self.load_backgrounds()
        self.load_ids()
        self.load_gimp()

        self.district_client = None
        self.ms_client = None
        self.rp_mode = False
        self.user_auth_req = False
        self.showname_freeze = False
        self.commands = importlib.import_module('server.commands')
        self.commands_alt = importlib.import_module('server.commands_alt')
        self.logger_handlers = logger.setup_logger(debug=self.config['debug'])

        logger.log_print('Server configurations loaded successfully!')

        self.error_queue = None
        self._server = None

        self._timermanager = TimerManager(self)
        self._b = self._timermanager.new_timer(start_value=40, tick_rate=-1)

    async def start(self):
        self.loop = asyncio.get_event_loop()
        self.error_queue = asyncio.Queue()

        self.tasker = Tasker(self, self.loop)
        bound_ip = '0.0.0.0'
        if self.config['local']:
            bound_ip = '127.0.0.1'
            server_name = 'localhost'
            logger.log_print('Starting a local server...')
        else:
            server_name = self.config['masterserver_name']
            logger.log_print('Starting a nonlocal server...')

        # Check if port is available
        port = self.config['port']
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((bound_ip, port))
            except socket.error as exc:
                if exc.errno == errno.EADDRINUSE:
                    msg = (f'Port {port} is in use by another application. Make sure to close any '
                           f'conflicting applications (even another instance of this server) and '
                           f'try again.')
                    raise ServerError(msg)
                raise exc
            except OverflowError as exc:
                msg = str(exc).replace('bind(): ', '').capitalize()
                msg += ' Make sure to set your port number to an appropriate value and try again.'
                raise ServerError(msg)

        # Yes there is a race condition here (between checking if port is available, and actually
        # using it). The only side effect of a race condition is a slightly less nice error
        # message, so it's not that big of a deal.
        self._server = await self.loop.create_server(lambda: self.protocol(self),
                                                     bound_ip, port,
                                                     start_serving=False)
        asyncio.create_task(self._server.serve_forever())
        logger.log_pserver('Server started successfully!')

        if self.config['local']:
            host_ip = '127.0.0.1'
        else:
            try:
                host_ip = (urllib.request.urlopen('https://api.ipify.org',
                                                  context=ssl.SSLContext())
                           .read().decode('utf8'))
            except urllib.error.URLError as ex:
                host_ip = None
                logger.log_pdebug('Unable to obtain personal IP from https://api.ipify.org\n'
                                  '{}: {}\n'
                                  'Players may be unable to join.'
                                  .format(type(ex).__name__, ex.reason))
        if host_ip is not None:
            logger.log_pdebug('Server should be now accessible from {}:{}:{}'
                              .format(host_ip, self.config['port'], server_name))

        if not self.config['local']:
            logger.log_pdebug('If you want to join your server from this device, you may need to '
                              'join with this IP instead: 127.0.0.1:{}:localhost'
                              .format(self.config['port']))

        if self.config['local']:
            self.local_connection = asyncio.ensure_future(self.tasker.do_nothing(), loop=self.loop)

        if self.config['use_district']:
            self.district_client = DistrictClient(self)
            self.district_connection = asyncio.ensure_future(self.district_client.connect(),
                                                             loop=self.loop)
            print(' ')
            logger.log_print('Attempting to connect to district at {}:{}.'
                             .format(self.config['district_ip'], self.config['district_port']))

        if self.config['use_masterserver']:
            self.ms_client = MasterServerClient(self)
            self.masterserver_connection = asyncio.ensure_future(self.ms_client.connect(),
                                                                 loop=self.loop)
            print(' ')
            logger.log_print('Attempting to connect to the master server at {}:{} with the '
                             'following details:'.format(self.config['masterserver_ip'],
                                                         self.config['masterserver_port']))
            logger.log_print('*Server name: {}'.format(self.config['masterserver_name']))
            logger.log_print('*Server description: {}'
                             .format(self.config['masterserver_description']))

        raise await self.error_queue.get()

    async def normal_shutdown(self):

        # Cleanup operations
        self.shutting_down = True

        # Cancel further polling for district/master server
        if self.local_connection:
            self.local_connection.cancel()
            await self.tasker.await_cancellation(self.local_connection)

        if self.district_connection:
            self.district_connection.cancel()
            await self.tasker.await_cancellation(self.district_connection)

        if self.masterserver_connection:
            self.masterserver_connection.cancel()
            await self.tasker.await_cancellation(self.masterserver_connection)
            await self.tasker.await_cancellation(self.ms_client.shutdown())

        # Cancel pending client tasks and cleanly remove them from the areas
        players = self.get_player_count()
        logger.log_print('Kicking {} remaining client{}.'
                         .format(players, 's' if players != 1 else ''))

        for client in self.client_manager.clients:
            client.disconnect()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def get_version_string(self):
        mes = '{}.{}.{}'.format(self.release, self.major_version, self.minor_version)
        if self.segment_version:
            mes = '{}-{}'.format(mes, self.segment_version)
        return mes

    def reload(self):
        # Keep backups in case of failure
        backup = [self.char_list.copy(), self.music_list.copy(), self.backgrounds.copy()]

        # Do a dummy YAML load to see if the files can be loaded and parsed at all first.
        reloaded_assets = [self.load_characters, self.load_backgrounds, self.load_music]
        for reloaded_asset in reloaded_assets:
            try:
                reloaded_asset()
            except ServerError.YAMLInvalidError as exc:
                # The YAML exception already provides a full description. Just add the fact the
                # reload was undone to ease the person who ran the command's nerves.
                msg = (f'{exc} Reload was undone.')
                raise ServerError.YAMLInvalidError(msg)
            except ServerError.FileSyntaxError as exc:
                msg = f'{exc} Reload was undone.'
                raise ServerError(msg)

        # Only on success reload
        self.load_characters()
        self.load_backgrounds()

        try:
            self.load_music()
        except ServerError as exc:
            self.char_list, self.music_list, self.backgrounds = backup
            msg = ('The new music list returned the following error when loading: `{}`. Fix the '
                   'error and try again. Reload was undone.'
                   .format(exc))
            raise ServerError.MusicInvalidError(msg)

    def reload_commands(self):
        try:
            self.commands = importlib.reload(self.commands)
            self.commands_alt = importlib.reload(self.commands_alt)
        except Exception as error:
            return error

    def log_packet(self, client, packet, incoming):
        while len(self.logged_packets) > self.logged_packet_limit:
            self.logged_packets.pop(0)
        entry = ('R:' if incoming else 'S:', Constants.get_time_iso(), str(client.id), packet)
        self.logged_packets.append(entry)

    def new_client(self, transport, ip=None, my_protocol=None):
        c = self.client_manager.new_client(transport, my_protocol=my_protocol)
        if self.rp_mode:
            c.in_rp = True
        c.server = self
        c.area = self.area_manager.default_area()
        c.area.new_client(c)
        return c

    def remove_client(self, client):
        client.area.remove_client(client)
        self.client_manager.remove_client(client)

    def is_client(self, client):
        # This should only be False for clients that have been disconnected.
        return self.client_manager.is_client(client)

    def get_clients(self):
        """
        Return a copy of all the clients connected to the server, sorted in ascending order by
        client ID.

        Returns
        -------
        list of ClientManager.Client
            Clients connected to the server.

        """
        return sorted(self.client_manager.clients)

    def get_player_count(self):
        # Ignore players in the server selection screen.
        return len([client for client in self.client_manager.clients if client.char_id is not None])

    def load_backgrounds(self):
        backgrounds = ValidateBackgrounds().validate('config/backgrounds.yaml')

        self.backgrounds = backgrounds
        default_background = self.backgrounds[0]
        # Make sure each area still has a valid background
        for area in self.area_manager.areas:
            if area.background not in self.backgrounds and not area.cbg_allowed:
                # The area no longer has a valid background, so change it to some valid background
                # like the first one
                area.change_background(default_background)
                area.broadcast_ooc(f'After a server refresh, your area no longer had a valid '
                                   f'background. Switching to {default_background}.')

        return backgrounds.copy()

    def load_config(self):
        self.config = ValidateConfig().validate('config/config.yaml')

        self.config['motd'] = self.config['motd'].replace('\\n', ' \n')
        self.all_passwords = list()
        passwords = [
            'modpass',
            'cmpass',
            'gmpass',
            'gmpass1',
            'gmpass2',
            'gmpass3',
            'gmpass4',
            'gmpass5',
            'gmpass6',
            'gmpass7',
            ]

        self.all_passwords = [self.config[password] for password in passwords if self.config[password]]

        # Default values to fill in config.yaml if not present
        defaults_for_tags = {
            'show_ms2-prober': True,

            'discord_link': None,
            'utc_offset': 'local',

            'max_numdice': 20,
            'max_numfaces': 11037,
            'max_modifier_length': 12,
            'max_acceptable_term': 22074,
            'def_numdice': 1,
            'def_numfaces': 6,
            'def_modifier': '',

            'blackout_background': 'Blackout_HD',
            'default_area_description': 'No description.',
            'party_lights_timeout': 10,
            'showname_max_length': 30,
            'sneak_handicap': 5,
            'spectator_name': 'SPECTATOR',

            'music_change_floodguard': {'times_per_interval': 1,
                                        'interval_length': 0,
                                        'mute_length': 0}
            }

        for (tag, value) in defaults_for_tags.items():
            if tag not in self.config:
                self.config[tag] = value

        return self.config

    def load_characters(self):
        characters = ValidateCharacters().validate('config/characters.yaml')

        if self.char_list != characters:
            # Inconsistent character list, so change everyone to spectator
            for client in self.client_manager.clients:
                if client.char_id != -1:
                    # Except those that are already spectators
                    client.change_character(-1)
                client.send_ooc('The server character list was changed and no longer reflects your '
                                'client character list. Please rejoin the server.')

        self.char_list = characters
        return characters.copy()

    def load_commandhelp(self):
        with Constants.fopen('README.md', 'r', encoding='utf-8') as readme:
            lines = [x.rstrip() for x in readme.readlines()]

        self.linetorank = {
            '### User Commands': 'normie',
            '### GM Commands': 'gm',
            '### Community Manager Commands': 'cm',
            '### Moderator Commands': 'mod'}

        self.commandhelp = {
            'normie': dict(),
            'gm': dict(),
            'cm': dict(),
            'mod': dict()}

        # Look for the start of the command list
        try:
            start_index = lines.index('## Commands')
            end_index = lines.index('### Debug commands')
        except ValueError as error:
            error_mes = ", ".join([str(s) for s in error.args])
            message = ('Unable to generate help based on README.md: {}. Are you sure you have the '
                       'latest README.md?'.format(error_mes))
            raise ServerError(message)

        rank = None
        current_command = None

        for line in lines[start_index:end_index]:
            # Check if empty line
            if not line:
                continue

            # Check if this line defines the rank we are taking a look at right now
            if line in self.linetorank.keys():
                rank = self.linetorank[line]
                current_command = None
                continue

            # Otherwise, check if we do not have a rank yet
            if rank is None:
                continue

            # Otherwise, check if this is the start of a command
            if line[0] == '*':
                # Get the command name
                command_split = line[4:].split('** ')
                if len(command_split) == 1:
                    # Case: * **version**
                    current_command = command_split[0][:-2]
                else:
                    # Case: * **uninvite** "ID/IPID"
                    current_command = command_split[0]

                formatted_line = '/{}'.format(line[2:])
                formatted_line = formatted_line.replace('**', '')
                self.commandhelp[rank][current_command] = [formatted_line]
                continue

            # Otherwise, line is part of command description, so add it to its current command desc
            #     - Unlocks your area, provided the lock came as a result of /lock.
            # ... assuming we have a command
            if current_command:
                self.commandhelp[rank][current_command].append(line[4:])
                continue

            # Otherwise, we have a line that is a description of the rank
            # Do nothing about them
            continue  # Not really needed, but made explicit

    def load_ids(self):
        self.ipid_list = dict()
        self.hdid_list = dict()

        # load ipids
        try:
            with Constants.fopen('storage/ip_ids.json', 'r', encoding='utf-8') as whole_list:
                self.ipid_list = json.load(whole_list)
        except ServerError.FileNotFoundError:
            with Constants.fopen('storage/ip_ids.json', 'w', encoding='utf-8') as whole_list:
                json.dump(dict(), whole_list)
            message = 'WARNING: File not found: storage/ip_ids.json. Creating a new one...'
            logger.log_pdebug(message)
        except Exception as ex:
            message = 'WARNING: Error loading storage/ip_ids.json. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)
            logger.log_pdebug(message)

        # If the IPID list is not a dict, fix the file
        # Why on earth is it called an IPID list if it is a Python dict is beyond me.
        if not isinstance(self.ipid_list, dict):
            message = (f'WARNING: File storage/ip_ids.json had a structure of the wrong type: '
                       f'{self.ipid_list}. Replacing it with a proper type.')
            logger.log_pdebug(message)
            self.ipid_list = dict()
            self.dump_ipids()

        # load hdids
        try:
            with Constants.fopen('storage/hd_ids.json', 'r', encoding='utf-8') as whole_list:
                self.hdid_list = json.loads(whole_list.read())
        except ServerError.FileNotFoundError:
            with Constants.fopen('storage/hd_ids.json', 'w', encoding='utf-8') as whole_list:
                json.dump(dict(), whole_list)
            message = 'WARNING: File not found: storage/hd_ids.json. Creating a new one...'
            logger.log_pdebug(message)
        except Exception as ex:
            message = 'WARNING: Error loading storage/hd_ids.json. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)
            logger.log_pdebug(message)

        # If the HDID list is not a dict, fix the file
        # Why on earth is it called an HDID list if it is a Python dict is beyond me.
        if not isinstance(self.hdid_list, dict):
            message = (f'WARNING: File storage/hd_ids.json had a structure of the wrong type: '
                       f'{self.hdid_list}. Replacing it with a proper type.')
            logger.log_pdebug(message)
            self.hdid_list = dict()
            self.dump_hdids()

    def load_iniswaps(self):
        try:
            with Constants.fopen('config/iniswaps.yaml', 'r', encoding='utf-8') as iniswaps:
                self.allowed_iniswaps = Constants.yaml_load(iniswaps)
        except Exception as ex:
            message = 'WARNING: Error loading config/iniswaps.yaml. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)

            logger.log_pdebug(message)

    def load_music(self, music_list_file='config/music.yaml', server_music_list=True):
        music_list = ValidateMusic().validate(music_list_file)

        if server_music_list:
            self.music_list = music_list
            try:
                self.build_music_list(music_list=music_list)
            except ServerError.FileSyntaxError as exc:
                msg = (f'File {music_list_file} returned the following error when loading: '
                       f'`{exc.message}`')
                raise ServerError.FileSyntaxError(msg)

        return music_list.copy()

    def load_gimp(self):
        try:
            gimp_list = ValidateGimp().validate('config/gimp.yaml')
        except ServerError.FileNotFoundError:
            gimp_list = [
                'ERP IS BAN',
                'HELP ME',
                '(((((case????)))))',
                'Anyone else a fan of MLP?',
                'does this server have sans from undertale?',
                'what does call mod do',
                'Join my discord server please',
                'can I have mod pls?',
                'why is everyone a missingo?',
                'how 2 change areas?',
                '19 years of perfection, i don\'t play games to fucking lose',
                ('nah... your taunts are fucking useless... only defeat angers me... by trying '
                 'to taunt just earns you my pitty'),
                'When do we remove dangits',
                'MODS STOP GIMPING ME',
                'PLAY NORMIES PLS',
                'share if you not afraid of herobrine',
                'New Killer Choosen! Hold On!!',
                'The cake killed Nether.',
                'How you win Class Trials is simple, call your opposition cucks.',
                ]
            with Constants.fopen('config/gimp.yaml', 'w') as gimp:
                Constants.yaml_dump(gimp_list, gimp)
            message = 'WARNING: File not found: config/gimp.yaml. Creating a new one...'
            logger.log_pdebug(message)

        self.gimp_list = gimp_list
        return gimp_list.copy()

    def dump_ipids(self):
        with Constants.fopen('storage/ip_ids.json', 'w') as whole_list:
            json.dump(self.ipid_list, whole_list)

    def dump_hdids(self):
        with Constants.fopen('storage/hd_ids.json', 'w') as whole_list:
            json.dump(self.hdid_list, whole_list)

    def get_ipid(self, ip):
        if ip not in self.ipid_list:
            while True:
                ipid = random.randint(0, 10**10-1)
                if ipid not in self.ipid_list.values():
                    break
            self.ipid_list[ip] = ipid
            self.dump_ipids()
        return self.ipid_list[ip]

    def build_music_list(self, from_area=None, c=None, music_list=None, include_areas=True,
                         include_music=True):
        built_music_list = list()

        # add areas first, if needed
        if include_areas:
            built_music_list.extend(self.prepare_area_list(c=c, from_area=from_area))

        # then add music, if needed
        if include_music:
            built_music_list.extend(self.prepare_music_list(c=c, specific_music_list=music_list))

        return built_music_list

    def prepare_area_list(self, c=None, from_area=None):
        """
        Return the area list of the server. If given c and from_area, it will send an area list
        that matches the perspective of client `c` as if they were in area `from_area`.

        Parameters
        ----------
        c: ClientManager.Client
            Client whose perspective will be taken into account, by default None
        from_area: AreaManager.Area
            Area from which the perspective will be considered, by default None

        Returns
        -------
        list of AreaManager.Area
            Area list that matches intended perspective.
        """

        # Determine whether to filter the areas in the results
        need_to_check = (from_area is None or (c is not None and (c.is_staff() or c.is_transient)))

        # Now add areas
        prepared_area_list = list()
        for area in self.area_manager.areas:
            if need_to_check or area.name in from_area.visible_reachable_areas:
                prepared_area_list.append("{}-{}".format(area.id, area.name))

        return prepared_area_list

    def prepare_music_list(self, c=None, specific_music_list=None):
        """
        If `specific_music_list` is not None, return a client-ready version of that music list.
        Else, if `c` is a client with a custom chosen music list, return their latest music list.
        Otherwise, return a client-ready version of the server music list.

        Parameters
        ----------
        c: ClientManager.Client
            Client whose current music list if it exists will be considered if `specific_music_list`
            is None
        specific_music_list: list of dictionaries with key sets {'category', 'songs'}
            Music list to use if given

        Returns
        -------
        list of str
            Music list ready to be sent to clients
        """

        # If not provided a specific music list to overwrite
        if specific_music_list is None:
            specific_music_list = self.music_list  # Default value
            # But just in case, check if this came as a request of a client who had a
            # previous music list preference
            if c and c.music_list is not None:
                specific_music_list = c.music_list

        prepared_music_list = list()
        for item in specific_music_list:
            category = item['category']
            songs = item['songs']
            prepared_music_list.append(category)
            for song in songs:
                name = song['name']
                prepared_music_list.append(name)

        return prepared_music_list

    def is_valid_char_id(self, char_id):
        return len(self.char_list) > char_id >= -1

    def get_char_id_by_name(self, name):
        if name == self.config['spectator_name']:
            return -1
        for i, ch in enumerate(self.char_list):
            if ch.lower() == name.lower():
                return i
        raise ServerError('Character not found.')

    def get_song_data(self, music, c=None):
        # The client's personal music list should also be a valid place to search
        # so search in there too if possible
        if c and c.music_list:
            valid_music = self.music_list + c.music_list
        else:
            valid_music = self.music_list

        for item in valid_music:
            if item['category'] == music:
                return item['category'], -1
            for song in item['songs']:
                if song['name'] == music:
                    try:
                        return song['name'], song['length']
                    except KeyError:
                        return song['name'], -1
        raise ServerError.MusicNotFoundError('Music not found.')

    def send_all_cmd_pred(self, cmd, *args, pred=lambda x: True):
        for client in self.client_manager.clients:
            if pred(client):
                client.send_command(cmd, *args)

    def make_all_clients_do(self, function, *args, pred=lambda x: True, **kwargs):
        for client in self.client_manager.clients:
            if pred(client):
                getattr(client, function)(*args, **kwargs)

    def send_error_report(self, client, cmd, args, ex):
        """
        In case of an error caused by a client packet, send error report to user, notify moderators
        and have full traceback available on console and through /lasterror
        """

        # Send basic logging information to user
        info = ('=========\nThe server ran into a Python issue. Please contact the server owner '
                'and send them the following logging information:')
        etype, evalue, etraceback = sys.exc_info()
        tb = traceback.extract_tb(tb=etraceback)
        current_time = Constants.get_time()
        file, line_num, module, func = tb[-1]
        file = file[file.rfind('\\')+1:]  # Remove unnecessary directories
        version = self.version
        info += '\r\n*Server version: {}'.format(version)
        info += '\r\n*Server time: {}'.format(current_time)
        info += '\r\n*Packet details: {} {}'.format(cmd, args)
        info += '\r\n*Client status: {}'.format(client)
        info += '\r\n*Area status: {}'.format(client.area)
        info += '\r\n*File: {}'.format(file)
        info += '\r\n*Line number: {}'.format(line_num)
        info += '\r\n*Module: {}'.format(module)
        info += '\r\n*Function: {}'.format(func)
        info += '\r\n*Error: {}: {}'.format(type(ex).__name__, ex)
        info += '\r\nYour help would be much appreciated.'
        info += '\r\n========='
        client.send_ooc(info)
        client.send_ooc_others('Client {} triggered a Python error through a client packet. '
                               'Do /lasterror to take a look at it.'.format(client.id),
                               pred=lambda c: c.is_mod)

        # Print complete traceback to console
        info = 'TSUSERVERDR HAS ENCOUNTERED AN ERROR HANDLING A CLIENT PACKET'
        info += '\r\n*Server time: {}'.format(current_time)
        info += '\r\n*Packet details: {} {}'.format(cmd, args)
        info += '\r\n*Client status: {}'.format(client)
        info += '\r\n*Area status: {}'.format(client.area)
        info += '\r\n\r\n{}'.format("".join(traceback.format_exception(etype, evalue, etraceback)))
        logger.log_print(info)
        self.last_error = [info, etype, evalue, etraceback]

        # Log error to file
        logger.log_error(info, server=self, errortype='C')

        if self.in_test:
            raise ex

    def broadcast_global(self, client, msg, as_mod=False,
                         mtype="<dollar>G", condition=lambda x: not x.muted_global):
        username = client.name
        ooc_name = '{}[{}][{}]'.format(mtype, client.area.id, username)
        if as_mod:
            ooc_name += '[M]'
        targets = [c for c in self.client_manager.clients if condition(c)]
        for c in targets:
            c.send_ooc(msg, username=ooc_name)
        if self.config['use_district']:
            msg = 'GLOBAL#{}#{}#{}#{}'.format(int(as_mod), client.area.id, username, msg)
            self.district_client.send_raw_message(msg)

    def broadcast_need(self, client, msg):
        char_name = client.displayname
        area_name = client.area.name
        area_id = client.area.id

        targets = [c for c in self.client_manager.clients if not c.muted_adverts]
        msg = ('=== Advert ===\r\n{} in {} [{}] needs {}\r\n==============='
               .format(char_name, area_name, area_id, msg))
        for c in targets:
            c.send_ooc(msg)

        if self.config['use_district']:
            msg = 'NEED#{}#{}#{}#{}'.format(char_name, area_name, area_id, msg)
            self.district_client.send_raw_message(msg)
