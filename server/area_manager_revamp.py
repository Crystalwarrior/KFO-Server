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

import asyncio
import random

import time
import yaml

from server.exceptions import AreaError
from server.evidence import EvidenceList


class AreaManager:
    class Area:
        def __init__(self, area_id, server, name, background, bg_lock, evidence_mod = 'FFA',
                     locking_allowed = False, iniswap_allowed = True, rp_getarea_allowed = True, rp_getareas_allowed = True):
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
            #New lines
            self.rp_getarea_allowed = rp_getarea_allowed
            self.rp_getareas_allowed = rp_getareas_allowed
            self.owned = False

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
            if client.is_cm:
                client.is_cm = False
                self.owned = False
                if self.is_locked:
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

        def is_char_available(self, char_id):
            return char_id not in [x.char_id for x in self.clients]

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
        self.load_areas()

    def load_areas(self):
        AREA_LIMIT = 1000 #This only affects the use of template ranges, not the number of areas you may have at any given time
        area_parameters = {'area', 'background', 'bglock', 'evidence_mod', 'locking_allowed',
                           'iniswap_allowed', 'rp_getarea_allowed', 'rp_getareas_allowed'}
        default_parameters = {'area': 'Area <AN>', 'background': 'gs4', 'bglock': False, #why was this set as a string
                                  'evidence_mod': 'FFA', 'locking_allowed': False, 'iniswap_allowed': True,
                                  'rp_getarea_allowed': True, 'rp_getareas_allowed': True}
        area_templates = dict()
        area_template_ranges = dict()
        area_template_ranges_ordered = list() # This is done to force multiple apparitions of the same area in different ranges
        # to be read in the correct order, so that for example, say area 4 appears in the 'default' and 'RP' template ranges, and in
        # area_templates.yaml, 'default' appears first. With this, I'd like it so that it will first read the default values
        # of the 'default' template, and then overwrite the parameters that appear in both 'default' and 'RP' with the ones
        # from 'RP'
        try:
            with open('config/area_templates.yaml', 'r') as template_file:
                init_area_templates = yaml.load(template_file)
                if init_area_templates is None:
                    raise FileNotFoundError
        except FileNotFoundError:
            init_area_templates = dict()

        for item in init_area_templates:
            if 'template_name' not in item:
                if 'apply_template_ranges' not in item or not item['apply_template_ranges']:
                    continue
                # This method performs the template area range checks
                for template in item:
                    if template == 'apply_template_ranges':
                        continue #We don't want to check the template_application line, it has nothing useful
                    raw_areas = str(item[template]).split(", ")
                    affected_areas = set()

                    for entry in raw_areas:
                        limits = entry.split("/")
                        if len(limits) > 2 or limits[0] == '' or limits[-1] == '': #Allows ez testing of length 1 and 2 lists
                            continue
                        try:
                            limits[0] = int(limits[0])
                            limits[-1] = int(limits[-1])
                        except ValueError:
                            continue
                        if limits[0] < 0 or limits[-1] > AREA_LIMIT or limits[0] > limits[-1]:
                            continue
                        for i in range(limits[0],limits[-1]+1):
                            affected_areas.add(i)
                    area_template_ranges[template] = affected_areas
                    area_template_ranges_ordered.append(template)
                continue

            # The rest of this method deals with actually loading the templates in memory
            area_templates[item['template_name']] = item

             #This is so that the area template does not include 'template_name' as an actual parameter
             #while also doubling down as a way to determine if this is a 'default' template
            template_name = area_templates[item['template_name']].pop('template_name')
            # Be careful, the 'pop' instruction also removes the template_name parameter from 'item' (yay mutability)
            # If you want to refer to the template name in this routine, you must use template_name or you will get a key error
            if template_name == 'default':
                for parameter in area_templates[template_name]:
                    default_parameters[parameter] = area_templates[template_name][parameter]
            # The idea here is that if there is an actual 'default' template, DRO will use whatever values this default
            # template has as a backup, and if for whatever reason this default template does not have whatever parameters
            # we may need, it will fall back to some hard-coded values in order to prevent crashes

        with open('config/areas.yaml', 'r') as chars:
            areas = yaml.load(chars)

        # Here's the established priority for determining area parameters
        # 1. It will first look for manually defined parameters in areas.yaml
        # 2. If some parameter is not manually set, it will look for the default value in the associated template
        # 3. If it does not have an explicitly associated template, it will determine if the area belongs to a template area range
        # 4. If none of the above, it will load hard-coded parameter values

        for item in areas:
            for parameter in area_parameters:
                if parameter not in item:
                    if 'template' in item and item['template'] in area_templates and parameter in area_templates[item['template']]:
                        item[parameter] = area_templates[item['template']][parameter] # The template's default parameters will only
                        # kick in if there are no valid parameters in the areas.yaml file, i.e. you can override template
                        # parameters if you so choose
                    else:
                        flag = False
                        for template in area_template_ranges_ordered:
                            if self.cur_id in area_template_ranges[template] and parameter in area_templates[template]:
                                item[parameter] = area_templates[template][parameter]
                                flag = True
                        if not flag:
                            item[parameter] = default_parameters[parameter]

            item['area'] = item['area'].replace('<AN>',str(self.cur_id))

            self.areas.append(
                self.Area(self.cur_id, self.server, item['area'], item['background'],
                          item['bglock'], item['evidence_mod'], item['locking_allowed'],
                          item['iniswap_allowed'], item['rp_getarea_allowed'], item['rp_getareas_allowed']))
            self.cur_id += 1

    def default_area(self):
        return self.areas[0]

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
