# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-20 Chrezm/Iuvee <thechrezm@gmail.com>
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
import importlib
import json
import random
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


class TsuserverDR:
    def __init__(self, protocol=None, client_manager=None, in_test=False):
        self.logged_packet_limit = 100  # Arbitrary
        self.logged_packets = []
        self.print_packets = False  # For debugging purposes
        self._server = None  # Internal server object, changed to proper object later

        self.release = 4
        self.major_version = 3
        self.minor_version = 0
        self.segment_version = 'b105'
        self.internal_version = 'M201230b'
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
        self.load_commandhelp()
        self.load_music()
        self.load_backgrounds()
        self.load_ids()

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

        self._server = await self.loop.create_server(lambda: self.protocol(self),
                                                     bound_ip, self.config['port'],
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

    def get_player_count(self):
        # Ignore players in the server selection screen.
        return len([client for client in self.client_manager.clients if client.char_id is not None])

    def _validate_backgrounds(self):
        with Constants.fopen('config/backgrounds.yaml', 'r', encoding='utf-8') as bgs:
            backgrounds = Constants.yaml_load(bgs)

        # Check background contents is indeed a list of strings
        if not isinstance(backgrounds, list):
            msg = (f'Expected the background list to be a list, got a'
                   f'{type(backgrounds).__name__}: {backgrounds}.')
            raise ServerError.FileSyntaxError(msg)

        for (i, background) in enumerate(backgrounds.copy()):
            if background is None:
                msg = (f'Expected all background names to be defined, but background {i} was not.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(background, (str, float, int, bool, complex)):
                msg = (f'Expected all background names to be strings or numbers, but background '
                       f'{i}: {background} was not a string or number.')
                raise ServerError.FileSyntaxError(msg)

            # Otherwise, background i is valid. Cast it as string to deal with YAML doing
            # potential casting of its own
            backgrounds[i] = str(background)

        return backgrounds

    def load_backgrounds(self):
        backgrounds = self._validate_backgrounds()

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
        with Constants.fopen('config/config.yaml', 'r', encoding='utf-8') as cfg:
            self.config = Constants.yaml_load(cfg)

        self.config['motd'] = self.config['motd'].replace('\\n', ' \n')
        self.all_passwords = list()
        # Mandatory passwords must be present in the configuration file. If they are not,
        # a server error will be raised.
        mandatory_passwords = ['modpass', 'cmpass', 'gmpass']
        for password in mandatory_passwords:
            if password not in self.config or not self.config[password]:
                err = (f'Password "{password}" is not defined in config/config.yaml. Please '
                       f'make sure it is set and try again.')
                raise ServerError(err)
            self.all_passwords.append(self.config[password])

        # Daily passwords are handled differently. They may optionally be not available.
        # What this means is the server does not want a daily password for that day
        # However, deliberately left empty passwords should still raise an error.
        optional_passwords = [f'gmpass{i}' for i in range(1, 8)]
        for password in optional_passwords:
            if password not in self.config or not self.config[password]:
                self.config[password] = None
            else:
                self.all_passwords.append(self.config[password])

        # Default values to fill in config.yaml if not present
        defaults_for_tags = {
            'utc_offset': 'local',
            'discord_link': None,
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
            'show_ms2-prober': True,
            'showname_max_length': 30,
            'sneak_handicap': 5,
            'spectator_name': 'SPECTATOR',
            'music_change_floodguard': {'times_per_interval': 1,
                                        'interval_length': 0,
                                        'mute_length': 0}}

        for (tag, value) in defaults_for_tags.items():
            if tag not in self.config:
                self.config[tag] = value

        # Check that all passwords were generated are unique
        passwords = ['guardpass',
                     'modpass',
                     'cmpass',
                     'gmpass',
                     'gmpass1',
                     'gmpass2',
                     'gmpass3',
                     'gmpass4',
                     'gmpass5',
                     'gmpass6',
                     'gmpass7']

        for (i, password1) in enumerate(passwords):
            for (j, password2) in enumerate(passwords):
                if i != j and self.config[password1] == self.config[password2] != None:
                    info = ('Passwords "{}" and "{}" in config/config.yaml match. '
                            'Please change them so they are different and try again.'
                            .format(password1, password2))
                    raise ServerError(info)

    def _validate_characters(self):
        with Constants.fopen('config/characters.yaml', 'r', encoding='utf-8') as bgs:
            characters = Constants.yaml_load(bgs)

        # Check characters contents is indeed a list of strings
        if not isinstance(characters, list):
            msg = (f'Expected the characters list to be a list, got a'
                   f'{type(characters).__name__}: {characters}.')
            raise ServerError.FileSyntaxError(msg)

        for (i, character) in enumerate(characters.copy()):
            if character is None:
                msg = (f'Expected all character names to be defined, but character {i} was not.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(character, (str, float, int, bool, complex)):
                msg = (f'Expected all character names to be strings or numbers, but character '
                       f'{i}: {character} was not a string or number.')
                raise ServerError.FileSyntaxError(msg)

            # Otherwise, background i is valid. Cast it as string to deal with YAML doing
            # potential casting of its own
            characters[i] = str(character)

        return characters

    def load_characters(self):
        characters = self._validate_characters()

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
            continue # Not really needed, but made explicit

    def load_ids(self):
        self.ipid_list = {}
        self.hdid_list = {}

        #load ipids
        try:
            with Constants.fopen('storage/ip_ids.json', 'r', encoding='utf-8') as whole_list:
                self.ipid_list = json.loads(whole_list.read())
        except Exception as ex:
            message = 'WARNING: Error loading storage/ip_ids.json. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)

            logger.log_pdebug(message)

        #load hdids
        try:
            with Constants.fopen('storage/hd_ids.json', 'r', encoding='utf-8') as whole_list:
                self.hdid_list = json.loads(whole_list.read())
        except Exception as ex:
            message = 'WARNING: Error loading storage/hd_ids.json. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)

            logger.log_pdebug(message)

    def load_iniswaps(self):
        try:
            with Constants.fopen('config/iniswaps.yaml', 'r', encoding='utf-8') as iniswaps:
                self.allowed_iniswaps = Constants.yaml_load(iniswaps)
        except Exception as ex:
            message = 'WARNING: Error loading config/iniswaps.yaml. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)

            logger.log_pdebug(message)

    def load_music(self, music_list_file='config/music.yaml', server_music_list=True,
                   check_only=False):
        with Constants.fopen(music_list_file, 'r', encoding='utf-8') as music:
            music_list = Constants.yaml_load(music)

        if check_only:
            return list()

        if server_music_list:
            self.music_list = music_list
            try:
                self.build_music_list(music_list=music_list)
            except ServerError.FileSyntaxError as exc:
                msg = (f'File {music_list_file} returned the following error when loading: '
                       f'`{exc.message}`')
                raise ServerError.FileSyntaxError(msg)

        return music_list.copy()

    def dump_ipids(self):
        with Constants.fopen('storage/ip_ids.json', 'w') as whole_list:
            json.dump(self.ipid_list, whole_list)

    def dump_hdids(self):
        with Constants.fopen('storage/hd_ids.json', 'w') as whole_list:
            json.dump(self.hdid_list, whole_list)

    def get_ipid(self, ip):
        if not ip in self.ipid_list:
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

        return self._validate_music_list(raw_music_list=specific_music_list)

    def _validate_music_list(self, raw_music_list=None):
        if raw_music_list is None:
            raw_music_list = list()

        prepared_music_list = list()

        # Check music list contents is indeed a list
        if not isinstance(raw_music_list, list):
            msg = (f'Expected the music list to be a list, got a'
                   f'{type(raw_music_list).__name__}: {raw_music_list}.')
            raise ServerError.FileSyntaxError(msg)

        # Check top level description is ok
        for (i, item) in enumerate(raw_music_list.copy()):
            if item is None:
                msg = (f'Expected all music list items to be defined, but item {i} was not.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(item, dict):
                msg = (f'Expected all music list items to be dictionaries, but item '
                       f'{i}: {item} was not a dictionary.')
                raise ServerError.FileSyntaxError(msg)
            if set(item.keys()) != {'category', 'songs'}:
                msg = (f'Expected all music list items to have exactly two keys: category and '
                       f'songs, but item {i} had keys {set(item.keys())}')
                raise ServerError.FileSyntaxError(msg)

            category, songs = item['category'], item['songs']
            if category is None:
                msg = (f'Expected all music list categories to be defined, but category {i} was '
                       f'not.')
                raise ServerError.FileSyntaxError(msg)
            if songs is None:
                msg = (f'Expected all music list song descriptions to be defined, but song '
                       f'description {i} was not.')
                raise ServerError.FileSyntaxError(msg)

            if not isinstance(category, (str, float, int, bool, complex)):
                msg = (f'Expected all music list category names to be strings or numbers, but '
                       f'category {i}: {category} was not a string or number.')
                raise ServerError.FileSyntaxError(msg)
            if not isinstance(songs, list):
                msg = (f'Expected all music list song descriptions to be a list, but '
                       f'description {i}: {songs} was not a list.')
                raise ServerError.FileSyntaxError(msg)

        # Check each song description dictionary is ok
        for (i, item) in enumerate(raw_music_list.copy()):
            category = item['category']
            songs = item['songs']
            prepared_music_list.append(category)
            for (j, song) in enumerate(songs):
                if song is None:
                    msg = (f'Expected all music list song descriptions to be defined, but song '
                           f'description {j} in category {i}: {category} was not defined.')
                    raise ServerError.FileSyntaxError(msg)
                if not isinstance(song, dict):
                    msg = (f'Expected all music list song descriptions to be dictionaries: but '
                           f'song description {j} in category {i}: {category} was not a '
                           f'dictionary: {song}.')
                    raise ServerError.FileSyntaxError(msg)
                if set(song.keys()) not in [{'name'}, {'name', 'length'}]:
                    msg = (f'Expected all music list songs to have exactly keys: name, or name and '
                           f'length, but song description {j} in category {i}: {category} had keys '
                           f'{set(song.keys())}.')
                    raise ServerError.FileSyntaxError(msg)

                if 'length' not in song:
                    name, length = song['name'], -1
                else:
                    name, length = song['name'], song['length']

                if not isinstance(name, (str, float, int, bool, complex)):
                    msg = (f'Expected all music list song names to be strings or numbers, but '
                           f'song {j}: {name} in category {i}: {category} was not a string or '
                           f'number.')
                    raise ServerError.FileSyntaxError(msg)
                if not isinstance(length, (int, float)):
                    msg = (f'Expected all music list song lengths to be numbers, but song {j}: '
                           f'{name} in category {i}: {category} had non-numerical length {length}.')
                    raise ServerError.FileSyntaxError(msg)

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
        self.send_all_cmd_pred('CT', ooc_name, msg, pred=condition)
        if self.config['use_district']:
            msg = 'GLOBAL#{}#{}#{}#{}'.format(int(as_mod), client.area.id, username, msg)
            self.district_client.send_raw_message(msg)

    def broadcast_need(self, client, msg):
        char_name = client.displayname
        area_name = client.area.name
        area_id = client.area.id
        self.send_all_cmd_pred('CT', '{}'.format(self.config['hostname']),
                               '=== Advert ===\r\n{} in {} [{}] needs {}\r\n==============='
                               .format(char_name, area_name, area_id, msg),
                               pred=lambda x: not x.muted_adverts)
        if self.config['use_district']:
            msg = 'NEED#{}#{}#{}#{}'.format(char_name, area_name, area_id, msg)
            self.district_client.send_raw_message(msg)
