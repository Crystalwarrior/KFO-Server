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

import asyncio
import importlib
import json
import random
import sys
import time
import traceback
import urllib.request
import yaml

from server import logger
from server.aoprotocol import AOProtocol
from server.area_manager import AreaManager
from server.ban_manager import BanManager
from server.constants import Constants
from server.client_manager import ClientManager
from server.districtclient import DistrictClient
from server.exceptions import ServerError
from server.masterserverclient import MasterServerClient
from server.party_manager import PartyManager

class TsuserverDR:
    def __init__(self, protocol=None, client_manager=None, in_test=False):
        self.release = 4
        self.major_version = 1
        self.minor_version = 0
        self.segment_version = 'RC3'
        self.internal_version = '190818c'
        version_string = self.get_version_string()
        self.software = 'TsuserverDR {}'.format(version_string)
        self.version = 'TsuserverDR {} ({})'.format(version_string, self.internal_version)
        self.in_test = in_test

        self.protocol = AOProtocol if protocol is None else protocol
        client_manager = ClientManager if client_manager is None else client_manager
        logger.log_print = logger.log_print2 if self.in_test else logger.log_print
        logger.log_server = logger.log_server2 if self.in_test else logger.log_server

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
        self.load_config()
        self.load_iniswaps()
        self.char_list = list()
        self.char_pages_ao1 = None
        self.load_characters()
        self.client_manager = client_manager(self)
        self.area_manager = AreaManager(self)
        self.ban_manager = BanManager(self)
        self.party_manager = PartyManager(self)

        self.ipid_list = {}
        self.hdid_list = {}
        self.music_list = None
        self.music_list_ao2 = None
        self.music_pages_ao1 = None
        self.backgrounds = None
        self.load_music()
        self.load_backgrounds()
        self.load_ids()
        self.district_client = None
        self.ms_client = None
        self.rp_mode = False
        self.user_auth_req = False
        self.client_tasks = dict()
        self.active_timers = dict()
        self.showname_freeze = False
        self.commands = importlib.import_module('server.commands')
        self.commands_alt = importlib.import_module('server.commands_alt')
        self.logger_handlers = logger.setup_logger(debug=self.config['debug'])

        logger.log_print('Server configurations loaded successfully!')

    def start(self):
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()

        bound_ip = '0.0.0.0'
        if self.config['local']:
            bound_ip = '127.0.0.1'
            server_name = 'localhost'
            logger.log_print('Starting a local server...')
        else:
            server_name = self.config['masterserver_name'] if self.config['use_masterserver'] else ''
            logger.log_print('Starting a nonlocal server...')

        ao_server_crt = self.loop.create_server(lambda: self.protocol(self), bound_ip, self.config['port'])
        ao_server = self.loop.run_until_complete(ao_server_crt)

        logger.log_pdebug('Server started successfully!')

        if self.config['local']:
            host_ip = '127.0.0.1'
        else:
            host_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')

        logger.log_pdebug('Server should be now accessible from {}:{}:{}'
                          .format(host_ip, self.config['port'], server_name))

        if self.config['local']:
            self.local_connection = asyncio.ensure_future(self.do_nothing(), loop=self.loop)

        if self.config['use_district']:
            self.district_client = DistrictClient(self)
            self.district_connection = asyncio.ensure_future(self.district_client.connect(), loop=self.loop)
            print(' ')
            logger.log_print('Attempting to connect to district at {}:{}.'.format(self.config['district_ip'], self.config['district_port']))

        if self.config['use_masterserver']:
            self.ms_client = MasterServerClient(self)
            self.masterserver_connection = asyncio.ensure_future(self.ms_client.connect(), loop=self.loop)
            print(' ')
            logger.log_print('Attempting to connect to the master server at {}:{} with the following details:'.format(self.config['masterserver_ip'], self.config['masterserver_port']))
            logger.log_print('*Server name: {}'.format(self.config['masterserver_name']))
            logger.log_print('*Server description: {}'.format(self.config['masterserver_description']))

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass

        print('') # Lame
        logger.log_pdebug('You have initiated a server shut down.')
        self.shutdown()

        ao_server.close()
        self.loop.run_until_complete(ao_server.wait_closed())
        self.loop.close()
        logger.log_print('Server has successfully shut down.')

    def shutdown(self):
        # Cleanup operations
        self.shutting_down = True

        # Cancel further polling for district/master server
        if self.local_connection:
            self.local_connection.cancel()
            self.loop.run_until_complete(self.await_cancellation(self.local_connection))

        if self.district_connection:
            self.district_connection.cancel()
            self.loop.run_until_complete(self.await_cancellation(self.district_connection))

        if self.masterserver_connection:
            self.masterserver_connection.cancel()
            self.loop.run_until_complete(self.await_cancellation(self.masterserver_connection))

        # Cancel pending client tasks and cleanly remove them from the areas
        logger.log_print('Kicking {} remaining clients.'.format(self.get_player_count()))

        for area in self.area_manager.areas:
            while area.clients:
                client = next(iter(area.clients))
                area.remove_client(client)
                for task_id in self.client_tasks[client.id].keys():
                    task = self.get_task(client, [task_id])
                    self.loop.run_until_complete(self.await_cancellation(task))

    def get_version_string(self):
        return ('{}.{}.{}{}'
                .format(self.release, self.major_version, self.minor_version, self.segment_version))

    def reload(self):
        with Constants.fopen('config/characters.yaml', 'r') as chars:
            self.char_list = yaml.safe_load(chars)
        with Constants.fopen('config/music.yaml', 'r') as music:
            self.music_list = yaml.safe_load(music)
        self.build_music_pages_ao1()
        self.build_music_list_ao2()
        with Constants.fopen('config/backgrounds.yaml', 'r') as bgs:
            self.backgrounds = yaml.safe_load(bgs)

    def reload_commands(self):
        try:
            self.commands = importlib.reload(self.commands)
            self.commands_alt = importlib.reload(self.commands_alt)
        except Exception as error:
            return error

    def new_client(self, transport, ip=None, my_protocol=None):
        c = self.client_manager.new_client(transport)
        if self.rp_mode:
            c.in_rp = True
        c.server = self
        c.area = self.area_manager.default_area()
        c.area.new_client(c)
        return c

    def remove_client(self, client):
        client.area.remove_client(client)
        self.client_manager.remove_client(client)

    def get_player_count(self):
        # Ignore players in the server selection screen.
        return len([client for client in self.client_manager.clients if client.char_id is not None])

    def load_backgrounds(self):
        with Constants.fopen('config/backgrounds.yaml', 'r', encoding='utf-8') as bgs:
            self.backgrounds = yaml.safe_load(bgs)

    def load_config(self):
        with Constants.fopen('config/config.yaml', 'r', encoding='utf-8') as cfg:
            self.config = yaml.safe_load(cfg)
            self.config['motd'] = self.config['motd'].replace('\\n', ' \n')

        for i in range(1, 8):
            daily_gmpass = 'gmpass{}'.format(i)
            if daily_gmpass not in self.config or not self.config[daily_gmpass]:
                self.config[daily_gmpass] = None

        if 'music_change_floodguard' not in self.config:
            self.config['music_change_floodguard'] = {'times_per_interval': 1, 'interval_length': 0, 'mute_length': 0}
        # Backwards compatibility checks
        if 'spectator_name' not in self.config:
            self.config['spectator_name'] = 'SPECTATOR'
        if 'showname_max_length' not in self.config:
            self.config['showname_max_length'] = 30
        if 'sneak_handicap' not in self.config:
            self.config['sneak_handicap'] = 5 # Seconds
        if 'blackout_background' not in self.config:
            self.config['blackout_background'] = 'Blackout_HD'
        if 'discord_link' not in self.config:
            self.config['discord_link'] = 'None'
        if 'default_area_description' not in self.config:
            self.config['default_area_description'] = 'No description.'
        if 'party_lights_timeout' not in self.config:
            self.config['party_lights_timeout'] = 10

        # Check that all passwords were generated and that they are unique
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
        for password_type in passwords:
            if password_type not in self.config:
                info = ('Password "{}" not defined in server/config.yaml. Please make sure it is '
                        'set and try again.'.format(password_type))
                raise ServerError(info)

        for (i, password1) in enumerate(passwords):
            for (j, password2) in enumerate(passwords):
                if i != j and self.config[password1] == self.config[password2] != None:
                    info = ('Passwords "{}" and "{}" in server/config.yaml match. '
                            'Please change them so they are different and try again.'
                            .format(password1, password2))
                    raise ServerError(info)

    def load_characters(self):
        with Constants.fopen('config/characters.yaml', 'r', encoding='utf-8') as chars:
            self.char_list = yaml.safe_load(chars)
        self.build_char_pages_ao1()

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
                self.allowed_iniswaps = yaml.safe_load(iniswaps)
        except Exception as ex:
            message = 'WARNING: Error loading config/iniswaps.yaml. Will assume empty values.\n'
            message += '{}: {}'.format(type(ex).__name__, ex)

            logger.log_pdebug(message)

    def load_music(self, music_list_file='config/music.yaml', server_music_list=True):
        with Constants.fopen(music_list_file, 'r', encoding='utf-8') as music:
            music_list = yaml.safe_load(music)

        if server_music_list:
            self.music_list = music_list
            self.build_music_pages_ao1()
            self.build_music_list_ao2(music_list=music_list)

        return music_list

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
                if ipid not in self.ipid_list:
                    break
            self.ipid_list[ip] = ipid
            self.dump_ipids()
        return self.ipid_list[ip]

    def build_char_pages_ao1(self):
        self.char_pages_ao1 = [self.char_list[x:x + 10] for x in range(0, len(self.char_list), 10)]
        for i in range(len(self.char_list)):
            self.char_pages_ao1[i // 10][i % 10] = '{}#{}&&0&&&0&'.format(i, self.char_list[i])

    def build_music_pages_ao1(self):
        self.music_pages_ao1 = []
        index = 0
        # add areas first
        for area in self.area_manager.areas:
            self.music_pages_ao1.append('{}#{}'.format(index, area.name))
            index += 1
        # then add music
        for item in self.music_list:
            self.music_pages_ao1.append('{}#{}'.format(index, item['category']))
            index += 1
            for song in item['songs']:
                self.music_pages_ao1.append('{}#{}'.format(index, song['name']))
                index += 1
        self.music_pages_ao1 = [self.music_pages_ao1[x:x + 10] for x in range(0, len(self.music_pages_ao1), 10)]

    def build_music_list_ao2(self, from_area=None, c=None, music_list=None):
        # If not provided a specific music list to overwrite
        if music_list is None:
            music_list = self.music_list # Default value
            # But just in case, check if this came as a request of a client who had a
            # previous music list preference
            if c and c.music_list is not None:
                music_list = c.music_list

        self.music_list_ao2 = []
        # Determine whether to filter the music list or not
        need_to_check = (from_area is None or '<ALL>' in from_area.reachable_areas
                         or (c is not None and (c.is_staff() or c.is_transient)))

        # add areas first
        for area in self.area_manager.areas:
            if need_to_check or area.name in from_area.reachable_areas:
                self.music_list_ao2.append("{}-{}".format(area.id, area.name))

        # then add music
        for item in music_list:
            self.music_list_ao2.append(item['category'])
            for song in item['songs']:
                self.music_list_ao2.append(song['name'])

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
        raise ServerError('Music not found.')

    def send_all_cmd_pred(self, cmd, *args, pred=lambda x: True):
        for client in self.client_manager.clients:
            if pred(client):
                client.send_command(cmd, *args)

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
        file = file[file.rfind('\\')+1:] # Remove unnecessary directories
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
                               'Do /lasterror to take a look.'.format(client.id),
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
            raise

    def broadcast_global(self, client, msg, as_mod=False,
                         mtype="<dollar>G", condition=lambda x: not x.muted_global):
        username = client.name
        ooc_name = '{}[{}][{}]'.format(mtype, client.area.id, username)
        if as_mod:
            ooc_name += '[M]'
        self.send_all_cmd_pred('CT', ooc_name, msg, pred=condition)
        if self.config['use_district']:
            self.district_client.send_raw_message(
                'GLOBAL#{}#{}#{}#{}'.format(int(as_mod), client.area.id, username, msg))

    def broadcast_need(self, client, msg):
        char_name = client.get_char_name()
        area_name = client.area.name
        area_id = client.area.id
        self.send_all_cmd_pred('CT', '{}'.format(self.config['hostname']),
                               '=== Advert ===\r\n{} in {} [{}] needs {}\r\n==============='
                               .format(char_name, area_name, area_id, msg), pred=lambda x: not x.muted_adverts)
        if self.config['use_district']:
            self.district_client.send_raw_message('NEED#{}#{}#{}#{}'.format(char_name, area_name, area_id, msg))

    def create_task(self, client, args):
        # Abort old task if it exists
        try:
            old_task = self.get_task(client, args)
            if not old_task.done() and not old_task.cancelled():
                self.cancel_task(old_task)
        except KeyError:
            pass

        # Start new task
        self.client_tasks[client.id][args[0]] = (asyncio.ensure_future(getattr(self, args[0])(client, args[1:]), loop=self.loop),
                                                 args[1:], dict())

    def cancel_task(self, task):
        """ Cancels current task and sends order to await cancellation """
        task.cancel()
        asyncio.ensure_future(self.await_cancellation(task))

    def remove_task(self, client, args):
        """ Given client and task name, removes task from server.client_tasks, and cancels it """
        task = self.client_tasks[client.id].pop(args[0])
        self.cancel_task(task[0])

    def get_task(self, client, args):
        """ Returns actual task instance """
        return self.client_tasks[client.id][args[0]][0]

    def get_task_args(self, client, args):
        """ Returns input arguments of task """
        return self.client_tasks[client.id][args[0]][1]

    def get_task_attr(self, client, args, attr):
        """ Returns task attribute """
        return self.client_tasks[client.id][args[0]][2][attr]

    def set_task_attr(self, client, args, attr, value):
        """ Sets task attribute """
        self.client_tasks[client.id][args[0]][2][attr] = value

    async def await_cancellation(self, old_task):
        # Wait until it is able to properly retrieve the cancellation exception
        try:
            await old_task
        except asyncio.CancelledError:
            pass

    async def as_afk_kick(self, client, args):
        afk_delay, afk_sendto = args
        try:
            delay = int(afk_delay)*60 # afk_delay is in minutes, so convert to seconds
        except (TypeError, ValueError):
            info = ('The area file contains an invalid AFK kick delay for area {}: {}'.
                    format(client.area.id, afk_delay))
            raise ServerError(info)

        if delay <= 0: # Assumes 0-minute delay means that AFK kicking is disabled
            return

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        else:
            try:
                area = client.server.area_manager.get_area_by_id(int(afk_sendto))
            except Exception:
                info = ('The area file contains an invalid AFK kick destination area for area {}: '
                        '{}'.format(client.area.id, afk_sendto))
                raise ServerError(info)
            if client.area.id == afk_sendto: # Don't try and kick back to same area
                return
            if client.char_id < 0: # Assumes spectators are exempted from AFK kicks
                return
            if client.is_staff(): # Assumes staff are exempted from AFK kicks
                return

            try:
                original_area = client.area
                original_name = client.get_char_name()
                client.change_area(area, override_passages=True, override_effects=True,
                                   ignore_bleeding=True)
            except Exception:
                pass # Server raised an error trying to perform the AFK kick, ignore AFK kick
            else:
                client.send_ooc('You were kicked from area {} to area {} for being inactive for '
                                '{} minutes.'.format(original_area.id, afk_sendto, afk_delay))

                if client.area.is_locked or client.area.is_modlocked:
                    try: # Try and remove the IPID from the area's invite list
                        client.area.invite_list.pop(client.ipid)
                    except KeyError:
                        pass # Would only happen if they joined the locked area through mod powers

                if client.party:
                    p = client.party
                    client.party.remove_member(client)
                    client.send_ooc('You were also kicked off from your party.')
                    for c in p.get_members():
                        c.send_ooc('{} was AFK kicked from your party.'.format(original_name))

    async def as_timer(self, client, args):
        _, length, name, is_public = args # Length in seconds, already converted
        client_name = client.name # Failsafe in case client disconnects before task is cancelled/expires

        try:
            await asyncio.sleep(length)
        except asyncio.CancelledError:
            self.send_all_cmd_pred('CT', '{}'.format(self.config['hostname']),
                                   'Timer "{}" initiated by {} has been canceled.'
                                   .format(name, client_name),
                                   pred=lambda c: (c == client or c.is_staff() or
                                                   (is_public and c.area == client.area)))
        else:
            self.send_all_cmd_pred('CT', '{}'.format(self.config['hostname']),
                                   'Timer "{}" initiated by {} has expired.'
                                   .format(name, client_name),
                                   pred=lambda c: (c == client or c.is_staff() or
                                                   (is_public and c.area == client.area)))
        finally:
            del self.active_timers[name]

    async def as_handicap(self, client, args):
        _, length, _, announce_if_over = args
        client.is_movement_handicapped = True

        try:
            await asyncio.sleep(length)
        except asyncio.CancelledError:
            pass # Cancellation messages via send_oocs must be sent manually
        else:
            if announce_if_over and not client.is_staff():
                client.send_ooc('Your movement handicap has expired. You may move to a new area.')
        finally:
            client.is_movement_handicapped = False

    async def as_day_cycle(self, client, args):
        time_start, area_1, area_2, hour_length, hour_start, send_first_hour = args
        hour = hour_start
        minute_at_interruption = 0
        hour_paused_at = time.time() # Does not need initialization, but PyLint complains otherwise
        self.set_task_attr(client, ['as_day_cycle'], 'just_paused', False) # True after /clock_pause, False after 1 second
        self.set_task_attr(client, ['as_day_cycle'], 'just_unpaused', False) # True after /clock_unpause, False after current hour elapses
        self.set_task_attr(client, ['as_day_cycle'], 'is_paused', False) # True after /clock_pause, false after /clock_unpause

        while True:
            try:
                # If an hour just finished without any interruptions
                if (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                    not self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    targets = [c for c in self.client_manager.clients if c == client or
                               ((c.is_staff() or send_first_hour) and area_1 <= c.area.id <= area_2)]
                    for c in targets:
                        c.send_ooc('It is now {}:00.'.format('{0:02d}'.format(hour)))
                        c.send_command('CL', client.id, hour)

                    hour_started_at = time.time()
                    minute_at_interruption = 0
                    client.last_sent_clock = hour
                    self.set_task_attr(client, ['as_day_cycle'], 'just_paused', False)
                    await asyncio.sleep(hour_length)
                # If the clock was just unpaused, send out notif and restart the current hour
                elif (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                      self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    client.send_ooc('Your day cycle in areas {} through {} has been unpaused.'
                                    .format(area_1, area_2))
                    client.send_ooc_others('The day cycle initiated by {} in areas {} through {} has been unpaused.'
                                           .format(client.name, area_1, area_2), is_staff=True)
                    self.set_task_attr(client, ['as_day_cycle'], 'just_paused', False)
                    self.set_task_attr(client, ['as_day_cycle'], 'just_unpaused', False)

                    minute = minute_at_interruption + (hour_paused_at - hour_started_at)/hour_length*60
                    hour_started_at = time.time()
                    minute_at_interruption = minute
                    self.send_all_cmd_pred('CT', '{}'.format(self.config['hostname']),
                                           'It is now {}:{}.'
                                           .format('{0:02d}'.format(hour),
                                                   '{0:02d}'.format(int(minute))),
                                           pred=lambda c: c == client or (c.is_staff() and area_1 <= c.area.id <= area_2))

                    await asyncio.sleep((60-minute_at_interruption)/60 * hour_length)


                # Otherwise, is paused. Check again in one second.
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                # Code can run here for one of two reasons
                # 1. The timer was canceled
                # 2. The timer was just paused

                try:
                    is_paused = self.get_task_attr(client, ['as_day_cycle'], 'is_paused')
                except KeyError: # Task may be canceled, so it'll never get this values
                    is_paused = False

                if not is_paused:
                    client.send_ooc('Your day cycle in areas {} through {} has been canceled.'
                                    .format(area_1, area_2))
                    client.send_ooc_others('The day cycle initiated by {} in areas {} through {} has been canceled.'
                                           .format(client.name, area_1, area_2), is_staff=True)
                    targets = [c for c in self.client_manager.clients if c == client or
                               area_1 <= c.area.id <= area_2]
                    for c in targets:
                        c.send_command('CL', client.id, -1)

                    break
                else:
                    hour_paused_at = time.time()
                    minute = minute_at_interruption + (hour_paused_at - hour_started_at)/hour_length*60
                    time_at_pause = '{}:{}'.format('{0:02d}'.format(hour),
                                                   '{0:02d}'.format(int(minute)))
                    client.send_ooc('Your day cycle in areas {} through {} has been paused at {}.'
                                    .format(area_1, area_2, time_at_pause))
                    client.send_ooc_others('The day cycle initiated by {} in areas {} through {} has been paused at {}.'
                                           .format(client.name, area_1, area_2, time_at_pause),
                                           is_staff=True)
                    self.set_task_attr(client, ['as_day_cycle'], 'just_paused', True)
            else:
                if (not self.get_task_attr(client, ['as_day_cycle'], 'is_paused') and
                    not self.get_task_attr(client, ['as_day_cycle'], 'just_unpaused')):
                    hour = (hour + 1) % 24
            finally:
                send_first_hour = True

    async def do_nothing(self):
        while True:
            try:
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                raise
