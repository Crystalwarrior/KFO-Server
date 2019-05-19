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
import asyncio
import random

import time
import yaml

from server.exceptions import AreaError
from server.evidence import EvidenceList


class AreaManager:
    class Area:
        def __init__(self, area_id, server, parameters):            
            self.clients = set()
            self.invite_list = {}
            self.id = area_id
            self.server = server
            self.music_looper = None
            self.next_message_time = 0
            self.hp_def = 10
            self.hp_pro = 10
            self.doc = 'No document.'
            self.status = 'IDLE'
            self.judgelog = []
            self.current_music = ''
            self.current_music_player = ''
            self.evi_list = EvidenceList()
            self.is_recording = False
            self.recorded_messages = []
            self.owned = False
            self.ic_lock = False
            self.is_locked = False
            self.is_gmlocked = False
            self.is_modlocked = False
            
            self.name = parameters['area']
            self.background = parameters['background']
            self.bg_lock = parameters['bglock']
            self.evidence_mod = parameters['evidence_mod']
            self.locking_allowed = parameters['locking_allowed']
            self.iniswap_allowed = parameters['iniswap_allowed']
            self.rp_getarea_allowed = parameters['rp_getarea_allowed']
            self.rp_getareas_allowed = parameters['rp_getareas_allowed'] 
            self.rollp_allowed = parameters['rollp_allowed']
            self.reachable_areas = parameters['reachable_areas'].split(", ")
            self.change_reachability_allowed = parameters['change_reachability_allowed']
            self.default_change_reachability_allowed = parameters['change_reachability_allowed']
            self.gm_iclock_allowed = parameters['gm_iclock_allowed']
            self.afk_delay = parameters['afk_delay']
            self.afk_sendto = parameters['afk_sendto']
            self.lobby_area = parameters['lobby_area']
            self.private_area = parameters['private_area']
            self.scream_range = parameters['scream_range'].split(", ")
            self.restricted_chars = parameters['restricted_chars'].split(", ")
            
            for i in range(len(self.reachable_areas)): #Ah, escape characters... again...
                self.reachable_areas[i] = self.reachable_areas[i].replace(',\\',',')
            for i in range(len(self.scream_range)): #Ah, escape characters... again...
                self.scream_range[i] = self.scream_range[i].replace(',\\',',')
            for i in range(len(self.scream_range)): #Ah, escape characters... again...
                self.restricted_chars[i] = self.restricted_chars[i].replace(',\\',',')
                
            self.default_reachable_areas = set(self.reachable_areas[:])
            self.staffset_reachable_areas = set(self.reachable_areas[:])
            self.reachable_areas = set(self.reachable_areas)
            if '<ALL>' not in self.reachable_areas:
                self.reachable_areas.add(self.name) #Safety feature, yay sets

            self.scream_range = setify(self.scream_range)
            self.restricted_chars = setify(self.restricted_chars)
            # Make sure only characters that exist are part of the restricted char set
            try:
                for char_name in self.restricted_chars:
                    self.server.char_list.index(char_name)
            except ValueError:
                raise AreaError('Area {} has an unrecognized character {} as a restricted character. Please make sure this character exists and try again.'.format(self.name, char_name))
                
        def new_client(self, client):
            self.clients.add(client)

        def remove_client(self, client):
            self.clients.remove(client)
            if len(self.clients) == 0:
                self.unlock()
        
        def unlock(self):
            self.is_locked = False
            if not self.is_gmlocked and not self.is_modlocked:
                self.invite_list = {}

        def gmunlock(self):
            self.is_gmlocked = False
            self.is_locked = False
            if not self.is_modlocked:
                self.invite_list = {}

        def modunlock(self):
            self.is_modlocked = False
            self.is_gmlocked = False
            self.is_locked = False
            self.invite_list = {}
        
        def get_chars_unusable(self, allow_restricted=False):
            if allow_restricted:
                return set([x.char_id for x in self.clients])
            else:
                return set([x.char_id for x in self.clients]).union(set([self.server.char_list.index(char_name) for char_name in self.restricted_chars]))
        
        def is_char_available(self, char_id, allow_restricted=False):
            return (char_id == -1) or (char_id not in self.get_chars_unusable(allow_restricted=allow_restricted))

        def get_rand_avail_char_id(self, allow_restricted=False):
            avail_set = set(range(len(self.server.char_list))) - self.get_chars_unusable(allow_restricted=allow_restricted)
            if len(avail_set) == 0:
                raise AreaError('No available characters.')
            return random.choice(tuple(avail_set))

        def send_command(self, cmd, *args):
            for c in self.clients:
                c.send_command(cmd, *args)

        def send_host_message(self, msg):
            self.send_command('CT', self.server.config['hostname'], msg)

        def set_next_msg_delay(self, msg_length):
            delay = min(3000, 100 + 60 * msg_length)
            self.next_message_time = round(time.time() * 1000.0 + delay)
        
        def is_iniswap(self, client, anim1, anim2, char):
            if self.iniswap_allowed:
                return False
            if '..' in anim1 or '..' in anim2:
                return True
            for char_link in self.server.allowed_iniswaps:
                if client.get_char_name() in char_link and char in char_link:
                    return False
            return True
        
        def play_music(self, name, cid, length=-1):
            self.send_command('MC', name, cid)
            if self.music_looper:
                self.music_looper.cancel()
            if length > 0:
                self.music_looper = asyncio.get_event_loop().call_later(length,
                                                                        lambda: self.play_music(name, -1, length))

        def can_send_message(self):
            return (time.time() * 1000.0 - self.next_message_time) > 0

        def change_hp(self, side, val):
            if not 0 <= val <= 10:
                raise AreaError('Invalid penalty value.')
            if not 1 <= side <= 2:
                raise AreaError('Invalid penalty side.')
            if side == 1:
                self.hp_def = val
            elif side == 2:
                self.hp_pro = val
            self.send_command('HP', side, val)

        def change_background(self, bg):
            if bg.lower() not in (name.lower() for name in self.server.backgrounds):
                raise AreaError('Invalid background name.')
            self.background = bg
            self.send_command('BN', self.background)

        def change_background_mod(self, bg):
            self.background = bg
            self.send_command('BN', self.background)

        def change_status(self, value):
            allowed_values = ('idle', 'building-open', 'building-full', 'casing-open', 'casing-full', 'recess')
            if value.lower() not in allowed_values:
                raise AreaError('Invalid status. Possible values: {}'.format(', '.join(allowed_values)))
            self.status = value.upper()

        def change_doc(self, doc='No document.'):
            self.doc = doc

        def add_to_judgelog(self, client, msg):
            if len(self.judgelog) >= 10:
                self.judgelog = self.judgelog[1:]
            self.judgelog.append('{} ({}) {}.'.format(client.get_char_name(), client.get_ip(), msg))

        def add_music_playing(self, client, name):
            self.current_music_player = client.get_char_name()
            self.current_music = name

        def get_evidence_list(self, client):
            client.evi_list, evi_list = self.evi_list.create_evi_list(client)
            return evi_list

        def broadcast_evidence_list(self):
            """
                LE#<name>&<desc>&<img>#<name>
                
            """
            for client in self.clients:
                client.send_command('LE', *self.get_evidence_list(client))

    def __init__(self, server):
        self.server = server
        self.areas = []
        self.area_names = set()
        self.load_areas()

    def get_area_by_name(self, name):
        for area in self.areas:
            if area.name == name:
                return area
        raise AreaError('Area not found.')

    def get_area_by_id(self, num):
        for area in self.areas:
            if area.id == num:
                return area
        raise AreaError('Area not found.')
        
    def load_areas(self, area_list_file='config/areas.yaml'):
        self.area_names = set()
        current_area_id = 0
        temp_areas = list()
        temp_area_names = set()
        temp_reachable_area_names = set()
                    
        # Check if valid area list file
        try:
            with open(area_list_file, 'r') as chars:
                areas = yaml.load(chars)
        except FileNotFoundError:
            raise FileNotFoundError('Could not find area list file {}'.format(area_list_file))
        
        # Create the areas
        for item in areas:
            if 'area' not in item:
                raise AreaError('Area {} has no name.'.format(current_area_id))
            if 'background' not in item:
                raise AreaError('Area {} has no background.'.format(item['area']))
            if 'bglock' not in item:
                item['bglock'] = False
            if 'evidence_mod' not in item:
                item['evidence_mod'] = 'FFA'
            if 'locking_allowed' not in item:
                item['locking_allowed'] = False
            if 'iniswap_allowed' not in item:
                item['iniswap_allowed'] = True
            if 'rp_getarea_allowed' not in item:
                item['rp_getarea_allowed'] = True
            if 'rp_getareas_allowed' not in item:
                item['rp_getareas_allowed'] = True
            if 'rollp_allowed' not in item:
                item['rollp_allowed'] = True
            if 'reachable_areas' not in item:
                item['reachable_areas'] = '<ALL>'
            if 'change_reachability_allowed' not in item:
                item['change_reachability_allowed'] = True
            if 'gm_iclock_allowed' not in item:
                item['gm_iclock_allowed'] = True
            if 'afk_delay' not in item:
                item['afk_delay'] = 0
            if 'afk_sendto' not in item:
                item['afk_sendto'] = 0
            if 'lobby_area' not in item:
                item['lobby_area'] = False
            if 'private_area' not in item:
                item['private_area'] = False
            if 'scream_range' not in item:
                item['scream_range'] = ''
            if 'restricted_chars' not in item:
                item['restricted_chars'] = ''
            
            # Backwards compatibility notice
            if 'sound_proof' in item:
                raise AreaError('The sound_proof property was defined for area {}. Support for sound_proof was removed in favor of scream_range. Please replace the sound_proof tag with scream_range in your area list and try again.'.format(item['area']))
            # Avoid having areas with the same name
            if item['area'] in temp_area_names:
                raise AreaError('Unexpected duplicated area names in area list: {}. Please rename the duplicated areas and try again.'.format(item['area']))
                
            temp_areas.append(self.Area(current_area_id, self.server, item))
            temp_area_names.add(item['area'])
            temp_reachable_area_names = temp_reachable_area_names.union(temp_areas[-1].reachable_areas)
            current_area_id += 1
            
        # Check if a reachable area is not an area name
        # Can only be done once all areas are created
    
        unrecognized_areas = temp_reachable_area_names-temp_area_names-{'<ALL>'}
        if unrecognized_areas != set():
            raise AreaError('Unrecognized area names defined as a reachable area in area list file: {}. Please rename the affected areas and try again.'.format(unrecognized_areas))
        
        # Only once all areas have been created, actually set the corresponding values
        # Helps avoiding junk area lists if there was an error
        self.areas = temp_areas
        self.area_names = temp_area_names
        
        # If the default area ID is now past the number of available areas, reset it back to zero
        if self.server.default_area >= len(self.areas):
            self.server.default_area = 0
            
        # Move existing clients to new corresponding area (or to default area if their previous area no longer exists)
        for client in self.server.client_manager.clients:
            try:
                new_area = self.get_area_by_name(client.area.name)
                client.change_area(new_area, override_all=True)
                client.send_host_message('Moving you to new area {}'.format(new_area.name))
            except AreaError:
                client.change_area(self.default_area(), override_all=True)
                client.send_host_message('Your previous area no longer exists. Moving you to default area {}'.format(client.area.name))
        
    def default_area(self):
        return self.areas[self.server.default_area]

def setify(l):
    if l in [list(), ['']]:
        return set()
    else:
        return set(l)
    