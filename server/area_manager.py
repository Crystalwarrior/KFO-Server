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
        def __init__(self, area_id, server, name, background, bg_lock, evidence_mod = 'FFA', locking_allowed = False, 
                     iniswap_allowed = True, rp_getarea_allowed = True, rp_getareas_allowed = True, 
                     rollp_allowed = True, reachable_areas = '<ALL>', change_reachability_allowed = True,
                     gm_iclock_allowed = True, afk_delay = 0, afk_sendto = 0, lobby_area = False, private_area = False,
                     sound_proof = False):
            self.iniswap_allowed = iniswap_allowed
            self.clients = set()
            self.invite_list = {}
            self.id = area_id
            self.name = name
            self.background = background
            self.bg_lock = bg_lock
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
            self.evidence_mod = evidence_mod
            self.locking_allowed = locking_allowed
            self.owned = False
            self.lobby_area = lobby_area
            self.private_area = private_area
            self.rp_getarea_allowed = rp_getarea_allowed
            self.rp_getareas_allowed = rp_getareas_allowed
            self.rollp_allowed = rollp_allowed
            self.ic_lock = False
            self.gm_iclock_allowed = gm_iclock_allowed
            self.sound_proof = sound_proof
            
            self.reachable_areas = reachable_areas.split(", ")
            for i in range(len(self.reachable_areas)): #Ah, escape characters... again...
                self.reachable_areas[i] = self.reachable_areas[i].replace(',\\',',')
            self.default_reachable_areas = set(self.reachable_areas[:])
            self.staffset_reachable_areas = set(self.reachable_areas[:])
            self.reachable_areas = set(self.reachable_areas)

            if '<ALL>' not in self.reachable_areas:
                self.reachable_areas.add(self.name) #Safety feature, yay sets
            self.change_reachability_allowed = change_reachability_allowed
            self.default_change_reachability_allowed = change_reachability_allowed #yay
            
            self.afk_delay = afk_delay
            self.afk_sendto = afk_sendto
            """
            #debug
            self.evidence_list.append(Evidence("WOW", "desc", "1.png"))
            self.evidence_list.append(Evidence("wewz", "desc2", "2.png"))
            self.evidence_list.append(Evidence("weeeeeew", "desc3", "3.png"))
            """
            
            self.is_locked = False
            self.is_gmlocked = False
            self.is_modlocked = False

        def new_client(self, client):
            self.clients.add(client)

        def remove_client(self, client):
            self.clients.remove(client)
            if len(self.clients) == 0:
                self.unlock()
            
            # Commented out, uncommenting forces CMs to relog every time
            # they switch areas.
#            if client.is_cm:
#                client.is_cm = False
#                self.owned = False
#                if self.is_locked:
#                    self.unlock()
        
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
        
        def is_char_available(self, char_id):
            return (char_id == -1) or (char_id not in [x.char_id for x in self.clients])

        def get_rand_avail_char_id(self):
            avail_set = set(range(len(self.server.char_list))) - set([x.char_id for x in self.clients])
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
        self.cur_id = 0
        self.areas = []
        self.area_names = set()
        self.reachable_area_names = set() #only used for validation
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
        
    def load_areas(self):
        with open('config/areas.yaml', 'r') as chars:
            areas = yaml.load(chars)
        for item in areas:
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
            if 'sound_proof' not in item:
                item['sound_proof'] = False
            self.areas.append(
                self.Area(self.cur_id, self.server, item['area'], item['background'], 
                          item['bglock'], item['evidence_mod'], item['locking_allowed'], 
                          item['iniswap_allowed'], item['rp_getarea_allowed'], item['rp_getareas_allowed'], 
                          item['rollp_allowed'], item['reachable_areas'], item['change_reachability_allowed'],
                          item['gm_iclock_allowed'], item['afk_delay'], item['afk_sendto'],
                          item['lobby_area'], item['private_area'], item['sound_proof']))
            if item['area'] in self.area_names:
                raise AreaError('Unexpected duplicated area names in areas.yaml: {}'.format(item['area']))
            self.area_names.add(item['area'])
            self.reachable_area_names = self.reachable_area_names.union(self.areas[-1].reachable_areas)
            self.cur_id += 1
        
        unrecognized_areas = self.reachable_area_names-self.area_names-{'<ALL>'}
        if unrecognized_areas != set():
            raise AreaError('Unrecognized area names defined as a reachable area in areas.yaml: {}'.format(unrecognized_areas))
        
    def default_area(self):
        return self.areas[self.server.default_area]

