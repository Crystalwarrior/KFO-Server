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

import datetime
import time

from server import client_changearea
from server import fantacrypt
from server import logger
from server.exceptions import ClientError, PartyError
from server.constants import TargetType, Constants, Clients

class ClientManager:
    class Client:
        def __init__(self, server, transport, user_id, ipid, my_protocol=None, ip=None):
            self.server = server
            self.transport = transport
            self.area_changer = client_changearea.ClientChangeArea(self)
            self.can_join = 0 # Needs to be 2 to actually connect
            self.can_askchaa = True # Needs to be true to process an askchaa packet
            self.version = ('Undefined', 'Undefined') # AO version used, established through ID pack
            self.packet_handler = Clients.ClientDRO

            self.hdid = ''
            self.ipid = ipid
            self.id = user_id
            self.char_id = None
            self.name = ''
            self.fake_name = ''
            self.char_folder = ''
            self.pos = ''
            self.showname = ''
            self.joined = time.time()
            self.last_active = Constants.get_time()

            self.area = server.area_manager.default_area()
            self.party = None
            self.is_mod = False
            self.is_gm = False
            self.is_dj = True
            self.is_cm = False
            self.is_muted = False
            self.is_ooc_muted = False
            self.pm_mute = False
            self.mod_call_time = 0
            self.evi_list = []
            self.muted_adverts = False
            self.muted_global = False
            self.pm_mute = False

            self.in_rp = False
            self.autopass = False
            self.disemvowel = False
            self.disemconsonant = False
            self.remove_h = False
            self.gimp = False
            self.is_visible = True
            self.multi_ic = None
            self.multi_ic_pre = ''
            self.following = None
            self.followedby = set()
            self.music_list = None
            self.showname_history = list()
            self.is_transient = False
            self.handicap_backup = None # Use if custom handicap is overwritten with a server one
            self.is_movement_handicapped = False
            self.show_shownames = True
            self.is_bleeding = False
            self.get_foreign_rolls = False
            self.last_sent_clock = None
            self.last_ic_message = ''
            self.last_ooc_message = ''
            self.first_person = False
            self.last_ic_notme = None, None
            self.is_blind = False
            self.is_deaf = False
            self.is_gagged = False
            self.send_deaf_space = False
            self.dicelog = list()
            self._zone_watched = None
            self.files = None
            self.get_nonautopass_autopass = False

            # Pairing stuff
            self.charid_pair = -1
            self.offset_pair = 0
            self.last_sprite = ''
            self.flip = 0
            self.claimed_folder = ''

            #music flood-guard stuff
            self.mus_counter = 0
            self.mute_time = 0
            self.mflood_interval = self.server.config['music_change_floodguard']['interval_length']
            self.mflood_times = self.server.config['music_change_floodguard']['times_per_interval']
            self.mflood_mutelength = self.server.config['music_change_floodguard']['mute_length']
            self.mus_change_time = [x * self.mflood_interval for x in range(self.mflood_times)]

        def send_raw_message(self, msg):
            self.transport.write(msg.encode('utf-8'))

        def send_command(self, command, *args):
            if args:
                if command == 'MS':
                    for evi_num in range(len(self.evi_list)):
                        if self.evi_list[evi_num] == args[11]:
                            lst = list(args)
                            lst[11] = evi_num
                            args = tuple(lst)
                            break
                self.send_raw_message('{}#{}#%'.format(command, '#'.join([str(x) for x in args])))
            else:
                self.send_raw_message('{}#%'.format(command))

        def send_ooc(self, msg, username=None, allow_empty=False,
                     is_staff=None, is_officer=None, in_area=None, not_to=None, part_of=None,
                     to_blind=None, to_deaf=None, is_zstaff=None, is_zstaff_flex=None,
                     pred=None):
            if pred is None:
                pred = lambda x: True
            if not_to is None:
                not_to = set()
            if not allow_empty and not msg:
                return
            if username is None:
                username = self.server.config['hostname']

            cond = Constants.build_cond(self, is_staff=is_staff, is_officer=is_officer,
                                        in_area=in_area, not_to=not_to, part_of=part_of,
                                        to_blind=to_blind, to_deaf=to_deaf,
                                        is_zstaff=is_zstaff, is_zstaff_flex=is_zstaff_flex,
                                        pred=pred)

            if cond(self):
                self.send_command('CT', username, msg)

        def send_ooc_others(self, msg, username=None, allow_empty=False,
                            is_staff=None, is_officer=None, in_area=None, not_to=None, part_of=None,
                            to_blind=None, to_deaf=None, is_zstaff=None, is_zstaff_flex=None,
                            pred=None):
            if not allow_empty and not msg:
                return

            if pred is None:
                pred = lambda x: True
            if not_to is None:
                not_to = set()
            if username is None:
                username = self.server.config['hostname']

            cond = Constants.build_cond(self, is_staff=is_staff, is_officer=is_officer,
                                        in_area=in_area, not_to=not_to.union({self}),
                                        part_of=part_of, to_blind=to_blind, to_deaf=to_deaf,
                                        is_zstaff=is_zstaff, is_zstaff_flex=is_zstaff_flex,
                                        pred=pred)
            self.server.make_all_clients_do("send_ooc", msg, pred=cond, allow_empty=allow_empty,
                                            username=username)

        def send_ic(self, params=None, sender=None, pred=None, not_to=None, gag_replaced=False,
                    is_staff=None, in_area=None, to_blind=None, to_deaf=None,
                    bypass_replace=False, bypass_deafened_starters=False,
                    msg=None, pos=None, cid=None, ding=None, color=None, showname=None):

            # sender is the client who sent the IC message
            # self is who is receiving the IC message at this particular moment

            # Assert correct call to the function
            if params is None and msg is None:
                raise ValueError('Expected message.')

            # Fill in defaults
            # Expected behavior is as follows:
            #  If params is None, then the sent IC message will only include custom details
            #  about the ding and the message, everything else is fixed. However, sender details
            #  are considered when replacing the parameters based on sender/receiver's properties
            #  If params is not None, then the sent IC message will use the parameters given in
            #  params, and use the properties of sender to replace the parameters if needed.

            pargs = {x: y for (x, y) in self.packet_handler.MS_OUTBOUND.value}
            if params is None:
                pargs['msg'] = msg
                pargs['pos'] = pos
                pargs['cid'] = cid
                pargs['ding'] = ding
                pargs['color'] = color
                pargs['showname'] = showname
            else:
                for key in params:
                    pargs[key] = params[key]
                if msg is not None:
                    pargs['msg'] = msg

            # Check if receiver is actually meant to receive the message. Bail out early if not.
            cond = Constants.build_cond(self, is_staff=is_staff, in_area=in_area, not_to=not_to,
                                        to_blind=to_blind, to_deaf=to_deaf, pred=pred)
            if not cond(self):
                return

            # Remove None values from pargs, which could have happened while setting default values
            # from the function call
            to_pop = list()
            for (key, value) in pargs.items():
                if pargs[key] is None:
                    to_pop.append(key)
            for key in to_pop:
                pargs.pop(key)

            def pop_if_there(dictionary, argument):
                if argument in dictionary:
                    dictionary.pop(argument)

            # Change the message to account for receiver's properties
            if not bypass_replace:
                # Change "character" parts of IC port
                if self.is_blind:
                    pargs['anim'] = '../../misc/blank'
                    self.send_command('BN', self.server.config['blackout_background'])
                elif sender == self and self.first_person:
                    last_area, last_args = self.last_ic_notme
                    # Check that the last received message exists and comes from the current area
                    if self.area.id == last_area and last_args:
                        pargs['folder'] = last_args['folder']
                        pargs['anim'] = last_args['anim']
                        pargs['pos'] = last_args['pos']
                        pargs['anim_type'] = last_args['anim_type']
                        pargs['flip'] = last_args['flip']
                    # Otherwise, send blank
                    else:
                        pargs['anim'] = '../../misc/blank'

                    # Regardless of anything, pairing is visually canceled while in first person
                    # so set them to default values

                    pop_if_there(pargs, 'other_offset')
                    pop_if_there(pargs, 'other_emote')
                    pop_if_there(pargs, 'other_flip')
                    pop_if_there(pargs, 'other_folder')
                    pop_if_there(pargs, 'offset_pair')
                    pop_if_there(pargs, 'charid_pair')
                    # Note this does not affect the client object internal values, it just
                    # simulates the client is not part of their pair if they are in first person
                    # mode.
                elif sender != self and self.first_person:
                    # Address the situation where this client is in first person mode, paired with
                    # someone else, and that someone else speaks in IC. This will 'visually' cancel
                    # pairing for this client, but not remove it completely. It is just so that
                    # the client's own sprites do not appear.
                    if pargs.get('charid_pair', -1) == self.char_id:
                        pop_if_there(pargs, 'other_offset')
                        pop_if_there(pargs, 'other_emote')
                        pop_if_there(pargs, 'other_flip')
                        pop_if_there(pargs, 'other_folder')
                        pop_if_there(pargs, 'offset_pair')
                        pop_if_there(pargs, 'charid_pair')

                # Change "message" parts of IC port
                allowed_starters = ('(', '*', '[')

                # Nerf message for deaf
                if self.is_deaf and pargs['msg']:
                    if (not pargs['msg'].startswith(allowed_starters) or
                        (sender.is_gagged and gag_replaced) or bypass_deafened_starters):
                        pargs['msg'] = '(Your ears are ringing)'
                        if self.send_deaf_space:
                            pargs['msg'] = pargs['msg'] + ' '
                        self.send_deaf_space = not self.send_deaf_space

                if self.is_blind and self.is_deaf and sender:
                    pargs['showname'] = '???'
                elif self.show_shownames and sender:
                    pargs['showname'] = sender.showname

            # Done modifying IC message
            # Now send it

            # This step also takes care of filtering out the packet arguments that the client
            # cannot parse, and also make sure they are in the correct order.
            final_pargs = dict()
            to_send = list()
            for (field, default_value) in self.packet_handler.MS_OUTBOUND.value:
                try:
                    value = pargs[field]
                except KeyError: # Case the key was popped (e.g. in pair code), use defaults then
                    value = default_value
                to_send.append(value)
                final_pargs[field] = value

            # Keep track of packet details in case this was sent by someone else
            # This is used, for example, for first person mode
            if sender != self:
                self.last_ic_notme = self.area.id, final_pargs

            self.send_command('MS', *to_send)

        def send_ic_others(self, params=None, sender=None, bypass_replace=False, pred=None,
                           not_to=None, gag_replaced=False, is_staff=None, in_area=None,
                           to_blind=None, to_deaf=None,
                           msg=None, pos=None, cid=None, ding=None, color=None, showname=None):

            if not_to is None:
                not_to = {self}
            else:
                not_to = not_to.union({self})

            for c in self.server.client_manager.clients:
                c.send_ic(params=None, sender=sender, bypass_replace=bypass_replace, pred=pred,
                          not_to=not_to, gag_replaced=gag_replaced, is_staff=is_staff,
                          in_area=in_area, to_blind=to_blind, to_deaf=to_deaf,
                          msg=msg, pos=pos, cid=cid, ding=ding, color=color, showname=showname)

        def disconnect(self):
            self.transport.close()

        def send_motd(self):
            self.send_ooc('=== MOTD ===\r\n{}\r\n============='.format(self.server.config['motd']))

        def is_valid_name(self, name):
            name_ws = name.replace(' ', '')
            if not name_ws or name_ws.isdigit():
                return False
            #for client in self.server.client_manager.clients:
                #print(client.name == name)
                #if client.name == name:
                    #return False
            return True

        @property
        def displayname(self):
            if  self.showname:
                return self.showname
            return self.get_char_name()

        def change_character(self, char_id, force=False, target_area=None, announce_zwatch=True):
            # Added target_area parameter because when switching areas, the change character code
            # is run before the character's area actually changes, so it would look for the wrong
            # area if I just did self.area
            if target_area is None:
                target_area = self.area

            if not self.server.is_valid_char_id(char_id):
                raise ClientError('Invalid character ID.')
            if not target_area.is_char_available(char_id, allow_restricted=self.is_staff()):
                if force:
                    for client in self.area.clients:
                        if client.char_id == char_id:
                            client.char_select()
                else:
                    raise ClientError('Character {} not available.'
                                      .format(self.get_char_name(char_id)))

            if self.char_id < 0 and char_id >= 0: # No longer spectator?
                # Now bound by AFK rules
                self.server.tasker.create_task(self, ['as_afk_kick', self.area.afk_delay,
                                                      self.area.afk_sendto])
                # And to lurk callouts, if any, provided not staff member
                self.check_lurk()

            elif self.char_id >= 0 and char_id < 0: # Now a spectator?
                # No longer bound to AFK rules
                try:
                    self.server.tasker.remove_task(self, ['as_afk_kick'])
                except KeyError:
                    pass
                # And to lurk callouts
                self.check_lurk()

            old_char = self.get_char_name()
            self.char_id = char_id
            self.char_folder = self.get_char_name() # Assumes players are not iniswapped initially
            self.pos = ''
            self.send_command('PV', self.id, 'CID', self.char_id)

            if announce_zwatch:
                self.send_ooc_others('(X) Client {} has changed from character `{}` to `{}` in '
                                     'your zone ({}).'
                                     .format(self.id, old_char, self.char_folder, self.area.id),
                                     is_zstaff=target_area)
            logger.log_server('[{}]Changed character from {} to {}.'
                              .format(self.area.id, old_char, self.get_char_name()), self)

        def change_music_cd(self):
            if self.is_mod or self.is_cm:
                return 0
            if self.mute_time:
                if time.time() - self.mute_time < self.mflood_mutelength:
                    return self.mflood_mutelength - (time.time() - self.mute_time)
                self.mute_time = 0

            index = (self.mus_counter - self.mflood_times + 1) % self.mflood_times
            if time.time() - self.mus_change_time[index] < self.mflood_interval:
                self.mute_time = time.time()
                return self.mflood_mutelength

            self.mus_counter = (self.mus_counter + 1) % self.mflood_times
            self.mus_change_time[self.mus_counter] = time.time()
            return 0

        def reload_character(self):
            self.change_character(self.char_id, True)

        def reload_music_list(self, new_music_file=None):
            """
            Rebuild the music list so that it only contains the target area's
            reachable areas+music. Useful when moving areas/logging in or out.
            """

            # Check if a new music file has been chosen, and if so, parse it
            if new_music_file:
                raw_music_list = self.server.load_music(music_list_file=new_music_file,
                                                        server_music_list=False)
            else:
                raw_music_list = None

            # KFO deals with music lists differently than other clients
            # They want the area lists and music lists separate, so they will have it like that
            if self.packet_handler != Clients.ClientKFO2d8:
                reloaded_music_list = self.server.build_music_list_ao2(from_area=self.area, c=self,
                                                                       music_list=raw_music_list)

                # KEEP THE ASTERISK, unless you want a very weird single area comprised
                # of all areas back to back forming a black hole area of doom and despair
                # that crashes all clients that dare attempt join this area.
                self.send_command('FM', *reloaded_music_list)
            else:
                area_list = self.server.build_music_list_ao2(from_area=self.area, c=self,
                                                             include_areas=True,
                                                             include_music=False)
                self.send_command('FA', *area_list)
                if raw_music_list:
                    music_list = self.server.prepare_music_list(c=self,
                                                                specific_music_list=raw_music_list)
                    self.send_command('FM', *music_list)

            # Update the new music list of the client once everything is done, if a new music list
            # was indeed loaded. Doing this only now prevents setting the music list to something
            # broken, as build_music_list_ao2 checks for syntax and raises an error if bad syntax
            # so if the code makes it here, the loaded music list is good.
            if raw_music_list:
                self.music_list = raw_music_list

        def check_change_area(self, area, override_passages=False, override_effects=False,
                              more_unavail_chars=None):
            checker = self.area_changer.check_change_area
            results = checker(area, override_passages=override_passages,
                              override_effects=override_effects,
                              more_unavail_chars=more_unavail_chars)
            return results

        def notify_change_area(self, area, old_char, ignore_bleeding=False, just_me=False):
            notifier = self.area_changer.notify_change_area
            notifier(area, old_char, ignore_bleeding=ignore_bleeding, just_me=just_me)

        def check_lurk(self):
            if self.area.lurk_length > 0 and not self.is_staff() and self.char_id >= 0:
                self.server.tasker.create_task(self, ['as_lurk', self.area.lurk_length])
            else: # Otherwise, cancel any existing lurk, if there exists
                try:
                    self.server.tasker.remove_task(self, ['as_lurk'])
                except KeyError:
                    pass

        def change_area(self, area, override_all=False, override_passages=False,
                        override_effects=False, ignore_bleeding=False, ignore_followers=False,
                        ignore_checks=False, ignore_notifications=False, more_unavail_chars=None,
                        change_to=None, from_party=False):
            changer = self.area_changer.change_area
            changer(area, override_all=override_all, override_passages=override_passages,
                    override_effects=override_effects, ignore_bleeding=ignore_bleeding,
                    ignore_followers=ignore_followers, ignore_checks=ignore_checks,
                    ignore_notifications=ignore_notifications, change_to=change_to,
                    more_unavail_chars=more_unavail_chars, from_party=from_party)

        def change_blindness(self, blind):
            changed = (self.is_blind != blind)
            self.is_blind = blind

            if self.is_blind:
                self.send_command('BN', self.server.config['blackout_background'])
            else:
                self.send_command('BN', self.area.background)

            self.area_changer.notify_me_blood(self.area, changed_visibility=changed,
                                              changed_hearing=False)

        def change_deafened(self, deaf):
            changed = (self.is_deaf != deaf)
            self.is_deaf = deaf

            self.area_changer.notify_me_blood(self.area, changed_visibility=False,
                                              changed_hearing=changed)

        def change_gagged(self, gagged):
            # changed = (self.is_gagged != gagged)
            self.is_gagged = gagged

        def change_showname(self, showname, target_area=None, forced=True):
            # forced=True means that someone else other than the user themselves requested the
            # showname change. Should only be false when using /showname.
            if target_area is None:
                target_area = self.area

            # Check length
            if len(showname) > self.server.config['showname_max_length']:
                raise ClientError("Showname `{}` exceeds the server's character limit of {}."
                                  .format(showname, self.server.config['showname_max_length']))

            # Check if non-empty showname is already used within area
            if showname != '':
                for c in target_area.clients:
                    if c.showname == showname and c != self:
                        raise ValueError("Showname `{}` is already in use in this area."
                                         .format(showname))
                        # This ValueError must be recaught, otherwise the client will crash.

            if self.showname != showname:
                status = {True: 'Was', False: 'Self'}
                ctime = Constants.get_time()
                if showname != '':
                    self.showname_history.append("{} | {} set to {}"
                                                 .format(ctime, status[forced], showname))
                else:
                    self.showname_history.append("{} | {} cleared"
                                                 .format(ctime, status[forced]))
            self.showname = showname

        def change_visibility(self, new_status):
            if new_status: # Changed to visible (e.g. through /reveal)
                self.send_ooc("You are no longer sneaking.")
                self.is_visible = True

                # Player should also no longer be under the effect of the server's sneaked handicap.
                # Thus, we check if there existed a previous movement handicap that had a shorter
                # delay than the server's sneaked handicap and restore it (as by default the server
                # will take the largest handicap when dealing with the automatic sneak handicap)
                try:
                    _, _, name, _ = self.server.tasker.get_task_args(self, ['as_handicap'])
                except KeyError:
                    pass
                else:
                    if name == "Sneaking":
                        if self.server.config['sneak_handicap'] > 0 and self.handicap_backup:
                            # Only way for a handicap backup to exist and to be in this situation is
                            # for the player to had a custom handicap whose length was shorter than
                            # the server's sneak handicap, then was set to be sneaking, then was
                            # revealed. From this, we can recover the old handicap backup
                            _, old_length, old_name, old_announce_if_over = self.handicap_backup[1]

                            msg = ('(X) {} was automatically imposed their old movement handicap '
                                   '"{}" of length {} seconds after being revealed in area {} ({}).'
                                   .format(self.displayname, old_name, old_length,
                                           self.area.name, self.area.id))
                            self.send_ooc_others(msg, is_zstaff_flex=True)
                            self.send_ooc('You were automatically imposed your former movement '
                                          'handicap "{}" of length {} seconds when changing areas.'
                                          .format(old_name, old_length))
                            self.server.tasker.create_task(self, ['as_handicap', time.time(),
                                                                  old_length, old_name,
                                                                  old_announce_if_over])
                        else:
                            self.server.tasker.remove_task(self, ['as_handicap'])

                logger.log_server('{} is no longer sneaking.'.format(self.ipid), self)
            else: # Changed to invisible (e.g. through /sneak)
                self.send_ooc("You are now sneaking.")
                self.is_visible = False
                shandicap = self.server.config['sneak_handicap']
                # Check to see if should impose the server's sneak handicap on the player
                # This should only happen if two conditions are satisfied:
                # 1. There is a positive sneak handicap and,
                # 2. The player has no movement handicap or one shorter than the sneak handicap
                if shandicap > 0:
                    try:
                        _, length, _, _ = self.server.tasker.get_task_args(self, ['as_handicap'])
                        if length < shandicap:
                            msg = ('(X) {} was automatically imposed the longer movement handicap '
                                   '"Sneaking" of length {} seconds in area {} ({}).'
                                   .format(self.displayname, shandicap, self.area.name,
                                           self.area.id))
                            self.send_ooc_others(msg, is_zstaff_flex=True)
                            raise KeyError # Lazy way to get there, but it works
                    except KeyError:
                        self.send_ooc('You were automatically imposed a movement handicap '
                                      '"Sneaking" of length {} seconds when changing areas.'
                                      .format(shandicap))
                        self.server.tasker.create_task(self, ['as_handicap', time.time(), shandicap,
                                                              "Sneaking", True])

                logger.log_server('{} is now sneaking.'.format(self.ipid), self)

        def set_timed_effects(self, effects, length):
            """
            Parameters
            ----------
            effects: set of Constants.Effect
            length: float
            """

            resulting_effects = dict()

            for effect in effects:
                name = effect.name
                async_name = effect.async_name
                new_args = [async_name, time.time(), length, effect]

                try:
                    args = self.server.tasker.get_task_args(self, [async_name])
                except KeyError:
                    # New effect
                    self.server.tasker.create_task(self, new_args)
                    resulting_effects[name] = (length, False)
                else:
                    # Effect existed before, check if need to replace it with a shorter effect
                    old_start, old_length, _ = args
                    old_remaining, _ = Constants.time_remaining(old_start, old_length)
                    if length < old_remaining:
                        # Replace with shorter timed effect
                        self.server.tasker.create_task(self, new_args)
                        resulting_effects[name] = (length, True)
                    else:
                        # Do not replace, current effect's time is shorter
                        resulting_effects[name] = (old_remaining, False)

            return resulting_effects

        def follow_user(self, target):
            if target == self:
                raise ClientError('You cannot follow yourself.')
            if target == self.following:
                raise ClientError('You are already following that player.')

            self.send_ooc('Began following client {} at {}'.format(target.id, Constants.get_time()))

            # Notify the player you were following before that you are no longer following them
            # and with notify I mean internally.
            if self.following:
                self.following.followedby.remove(self)
            self.following = target
            target.followedby.add(self)

            if self.area != target.area:
                self.follow_area(target.area, just_moved=False)

        def unfollow_user(self):
            if not self.following:
                raise ClientError('You are not following anyone.')

            self.send_ooc("Stopped following client {} at {}."
                          .format(self.following.id, Constants.get_time()))
            self.following.followedby.remove(self)
            self.following = None

        def follow_area(self, area, just_moved=True):
            # just_moved if True assumes the case where the followed user just moved
            # It being false is the case where, when the following started, the followed user was
            # in another area, and thus the followee is moved automtically
            if just_moved:
                self.send_ooc('Followed user moved to {} at {}'
                              .format(area.name, Constants.get_time()))
            else:
                self.send_ooc('Followed user was at {}'.format(area.name))

            try:
                self.change_area(area, ignore_followers=True)
            except ClientError as error:
                self.send_ooc('Unable to follow to {}: {}'.format(area.name, error))

        def send_area_list(self):
            msg = '=== Areas ==='
            lock = {True: '[LOCKED]', False: ''}
            for i, area in enumerate(self.server.area_manager.areas):
                owner = 'FREE'
                if area.owned:
                    for client in [x for x in area.clients if x.is_cm]:
                        owner = 'MASTER: {}'.format(client.get_char_name())
                        break
                locked = area.is_gmlocked or area.is_modlocked or area.is_locked

                if self.is_staff():
                    n_clt = len([c for c in area.clients if c.char_id is not None])
                else:
                    n_clt = len([c for c in area.clients if c.is_visible and c.char_id is not None])

                msg += '\r\nArea {}: {} (users: {}) {}'.format(i, area.name, n_clt, lock[locked])
                if self.area == area:
                    msg += ' [*]'
            self.send_ooc(msg)

        def send_limited_area_list(self):
            msg = '=== Areas ==='
            for i, area in enumerate(self.server.area_manager.areas):
                msg += '\r\nArea {}: {}'.format(i, area.name)
                if self.area == area:
                    msg += ' [*]'
            self.send_ooc(msg)

        def get_area_info(self, area_id, mods, as_mod=None, include_shownames=False,
                          include_ipid=None, only_my_multiclients=False):
            if as_mod is None:
                as_mod = self.is_mod or self.is_cm # Cheap, but decent
            if include_ipid is None and as_mod:
                include_ipid = True

            area = self.server.area_manager.get_area_by_id(area_id)
            info = '== Area {}: {} =='.format(area.id, area.name)
            sorted_clients = []

            for c in area.clients:
                # Conditions to print out a client in /getarea(s)
                # * Client is not in the server selection screen and,
                # * Any of the four
                # 1. Client is yourself.
                # 2. You are a staff member.
                # 3. Client is visible.
                # 4. Client is a mod when requiring only mods be printed.

                # If only_my_multiclients is set to True, only the clients opened by the current
                # user will be listed. Useful for /multiclients.
                if c.char_id is not None:
                    cond = (c == self or self.is_staff() or c.is_visible or (mods and c.is_mod))
                    multiclient_cond = not only_my_multiclients or c in self.get_multiclients()

                    if cond and multiclient_cond:
                        sorted_clients.append(c)

            sorted_clients = sorted(sorted_clients, key=lambda x: x.get_char_name())

            for c in sorted_clients:
                info += '\r\n[{}] {}'.format(c.id, c.get_char_name())
                if include_shownames and c.showname != '':
                    info += ' ({})'.format(c.showname)
                if len(c.get_multiclients()) > 1 and as_mod:
                    # If client is multiclienting add (MC) for officers
                    info += ' (MC)'
                if not c.is_visible:
                    info += ' (S)'
                if include_ipid:
                    info += ' ({})'.format(c.ipid)
            return len(sorted_clients), info

        def send_area_info(self, current_area, area_id, mods, as_mod=None, include_shownames=False,
                           include_ipid=None, only_my_multiclients=False):
            info = self.prepare_area_info(current_area, area_id, mods, as_mod=as_mod,
                                          include_shownames=include_shownames,
                                          include_ipid=include_ipid,
                                          only_my_multiclients=only_my_multiclients)
            if area_id == -1:
                info = '== Area List ==' + info
            self.send_ooc(info)

        def prepare_area_info(self, current_area, area_id, mods, as_mod=None,
                              include_shownames=False, include_ipid=None,
                              only_my_multiclients=False):
            #If area_id is -1, then return all areas.
            #If mods is True, then return only mods.
            #If include_shownames is True, then include non-empty custom shownames.
            #If include_ipid is True, then include IPIDs.
            #If only_my_multiclients is True, then include only clients opened by the current player
            # Verify that it should send the area info first
            if not self.is_staff() and not as_mod:
                getareas_restricted = (area_id == -1 and not self.area.rp_getareas_allowed)
                getarea_restricted = (area_id != -1 and not self.area.rp_getarea_allowed)
                if getareas_restricted or getarea_restricted:
                    raise ClientError('This command has been restricted to authorized users only '
                                      'in this area while in RP mode.')
                if not self.area.lights:
                    raise ClientError('The lights are off, so you cannot see anything.')

            # All code from here on assumes the area info will be sent successfully
            info = ''
            if area_id == -1:
                # all areas info
                unrestricted_access_area = '<ALL>' in current_area.reachable_areas
                for (i, area) in enumerate(self.server.area_manager.areas):
                    # Get area i details...
                    # If staff and there are clients in the area OR
                    # If not staff, there are visible clients in the area, and one of the following
                    # 1. The area has no passage restrictions.
                    # 2. The area is reachable from the current one
                    # 3. The client is transient to area passages
                    norm_check = (len([c for c in area.clients if c.is_visible or c == self]) > 0
                                  and (unrestricted_access_area or self.is_transient
                                       or area.name in current_area.reachable_areas))

                    if (self.is_staff() and len(area.clients) > 0) or \
                    (not self.is_staff() and norm_check):
                        num, ainfo = self.get_area_info(i, mods, as_mod=as_mod,
                                                        include_shownames=include_shownames,
                                                        include_ipid=include_ipid,
                                                        only_my_multiclients=only_my_multiclients)
                        if num:
                            info += '\r\n{}'.format(ainfo)
            else:
                num, info = self.get_area_info(area_id, mods,
                                               include_shownames=include_shownames,
                                               include_ipid=include_ipid)
                if num == 0:
                    info += '\r\n*No players in this area.'

            return info

        def send_area_hdid(self, area_id):
            info = self.get_area_hdid(area_id)
            self.send_ooc(info)

        def get_area_hdid(self, area_id):
            raise NotImplementedError

        def send_all_area_hdid(self):
            info = '== HDID List =='
            for i in range(len(self.server.area_manager.areas)):
                if len(self.server.area_manager.areas[i].clients) > 0:
                    info += '\r\n{}'.format(self.get_area_hdid(i))
            self.send_ooc(info)

        def send_all_area_ip(self):
            info = '== IP List =='
            for i in range(len(self.server.area_manager.areas)):
                if len(self.server.area_manager.areas[i].clients) > 0:
                    info += '\r\n{}'.format(self.get_area_ip(i))
            self.send_ooc(info)

        def get_area_ip(self, ip):
            raise NotImplementedError

        def send_done(self):
            unusable = self.area.get_chars_unusable(allow_restricted=self.is_staff())
            avail_char_ids = set(range(len(self.server.char_list))) - unusable
            # Readd sneaked players if needed so that they don't appear as taken
            # Their characters will not be able to be reused, but at least that's one less clue
            # about their presence.
            if not self.is_staff():
                avail_char_ids |= {c.char_id for c in self.area.clients if not c.is_visible}

            char_list = [-1] * len(self.server.char_list)
            for x in avail_char_ids:
                char_list[x] = 0
            self.send_command('CharsCheck', *char_list)
            self.send_command('HP', 1, self.area.hp_def)
            self.send_command('HP', 2, self.area.hp_pro)
            self.send_command('BN', self.area.background)
            self.send_command('LE', *self.area.get_evidence_list(self))
            self.send_command('MM', 1)
            self.send_command('OPPASS', fantacrypt.fanta_encrypt(self.server.config['guardpass']))
            if self.char_id is None:
                self.char_id = -1 # Set to a valid ID if still needed
            self.send_command('DONE')

        def char_select(self):
            self.char_id = -1
            self.send_done()

        def get_party(self, tc=False):
            if not self.party:
                raise PartyError('You are not part of a party.')
            return self.party

        def add_to_dicelog(self, msg):
            if len(self.dicelog) >= 20:
                self.dicelog = self.dicelog[1:]

            info = '{} | {} {}'.format(Constants.get_time(), self.displayname, msg)
            self.dicelog.append(info)

        def get_dicelog(self):
            info = '== Roll history of client {} =='.format(self.id)

            if not self.dicelog:
                info += '\r\nThe player has not rolled since joining the server.'
            else:
                for log in self.dicelog:
                    info += '\r\n*{}'.format(log)
            return info

        def is_staff(self):
            """
            Returns True if logged in as 'any' staff role.
            """
            return self.is_mod or self.is_cm or self.is_gm

        def login(self, arg, auth_command, role, announce_to_officers=True):
            """
            Wrapper function for the login method for all roles (GM, CM, Mod)
            """
            if len(arg) == 0:
                raise ClientError('You must specify the password.')
            auth_command(arg, announce_to_officers=announce_to_officers)

            # The following actions are true for all logged in roles
            if self.area.evidence_mod == 'HiddenCM':
                self.area.broadcast_evidence_list()
            self.reload_music_list() # Update music list to show all areas

            self.send_ooc('Logged in as a {}.'.format(role))
            # Filter out messages about GMs because they were called earlier in auth_gm
            if not self.is_gm and announce_to_officers:
                self.send_ooc_others('{} logged in as a {}.'.format(self.name, role), is_officer=True)
            logger.log_server('Logged in as a {}.'.format(role), self)

            if self.area.in_zone and self.area.in_zone != self.zone_watched:
                zone_id = self.area.in_zone.get_id()
                self.send_ooc('(X) You are in an area part of zone `{}`. To be able to receive its '
                              'notifications, start watching it with /zone_watch {}'
                              .format(zone_id, zone_id))

            # No longer bound to AFK rules
            # Nor lurk callouts
            for task in ['as_afk_kick', 'as_lurk']:
                try:
                    self.server.tasker.remove_task(self, [task])
                except KeyError:
                    pass

        def auth_mod(self, password, announce_to_officers=True):
            if self.is_mod:
                raise ClientError('Already logged in.')
            if password == self.server.config['modpass']:
                self.is_mod = True
                self.is_cm = False
                self.is_gm = False
                self.in_rp = False
            else:
                if announce_to_officers:
                    self.send_ooc_others('{} failed to login as a moderator.'.format(self.name), is_officer=True)
                raise ClientError('Invalid password.')

        def auth_cm(self, password, announce_to_officers=True):
            if self.is_cm:
                raise ClientError('Already logged in.')
            if password == self.server.config['cmpass']:
                self.is_cm = True
                self.is_mod = False
                self.is_gm = False
                self.in_rp = False
            else:
                if announce_to_officers:
                    self.send_ooc_others('{} failed to login as a community manager.'.format(self.name), is_officer=True)
                raise ClientError('Invalid password.')

        def auth_gm(self, password, announce_to_officers=True):
            if self.is_gm:
                raise ClientError('Already logged in.')

            # Obtain the daily gm pass (changes at midnight server time, gmpass1=Monday..)
            current_day = datetime.datetime.today().weekday()
            daily_gmpass = self.server.config['gmpass{}'.format((current_day % 7) + 1)]

            valid_passwords = [self.server.config['gmpass']]
            if daily_gmpass is not None:
                valid_passwords.append(daily_gmpass)

            if password in valid_passwords:
                if password == daily_gmpass:
                    g_or_daily = 'daily pass'
                else:
                    g_or_daily = 'global pass'
                if announce_to_officers:
                    self.send_ooc_others('{} logged in as a game master with the {}.'.format(self.name, g_or_daily), is_officer=True)
                self.is_gm = True
                self.is_mod = False
                self.is_cm = False
                self.in_rp = False
            else:
                if announce_to_officers:
                    self.send_ooc_others('{} failed to login as a game master.'.format(self.name), is_officer=True)
                raise ClientError('Invalid password.')

        def get_hdid(self):
            return self.hdid

        def get_ip(self):
            return self.ipid

        def get_ipreal(self):
            return self.transport.get_extra_info('peername')[0]

        def get_char_name(self, char_id=None):
            if char_id is None:
                char_id = self.char_id

            if char_id == -1:
                return self.server.config['spectator_name']
            if char_id is None:
                return 'SERVER_SELECT'
            return self.server.char_list[char_id]

        def get_showname_history(self):
            info = '== Showname history of client {} =='.format(self.id)

            if len(self.showname_history) == 0:
                info += '\r\nClient has not changed their showname since joining the server.'
            else:
                for log in self.showname_history:
                    info += '\r\n*{}'.format(log)
            return info

        def change_position(self, pos=''):
            if pos not in ('', 'def', 'pro', 'hld', 'hlp', 'jud', 'wit'):
                raise ClientError('Invalid position. '
                                  'Possible values: def, pro, hld, hlp, jud, wit.')
            self.pos = pos

        def set_mod_call_delay(self):
            self.mod_call_time = round(time.time() * 1000.0 + 30000)

        def can_call_mod(self):
            return (time.time() * 1000.0 - self.mod_call_time) > 0

        def get_multiclients(self):
            ipid = self.server.client_manager.get_targets(self, TargetType.IPID, self.ipid, False)
            hdid = self.server.client_manager.get_targets(self, TargetType.HDID, self.hdid, False)
            return list(set(ipid + hdid))

        def get_info(self, as_mod=False, as_cm=False, identifier=None):
            if identifier is None:
                identifier = self.id

            info = '== Client information of {} =='.format(identifier)
            ipid = self.ipid if as_mod or as_cm else "-"
            hdid = self.hdid if as_mod or as_cm else "-"
            info += '\n*CID: {}. IPID: {}. HDID: {}'.format(self.id, ipid, hdid)
            char_info = self.get_char_name()
            if self.char_folder and self.char_folder != char_info: # Indicate iniswap if needed
                char_info = '{} ({})'.format(char_info, self.char_folder)
            info += ('\n*Character name: {}. Showname: {}. OOC username: {}'
                     .format(char_info, self.showname, self.name))
            info += '\n*In area: {}-{}'.format(self.area.id, self.area.name)
            info += '\n*Last IC message: {}'.format(self.last_ic_message)
            info += '\n*Last OOC message: {}'.format(self.last_ooc_message)
            info += ('\n*Is GM? {}. Is CM? {}. Is mod? {}.'
                     .format(self.is_gm, self.is_cm, self.is_mod))
            info += ('\n*Is sneaking? {}. Is bleeding? {}. Is handicapped? {}'
                     .format(not self.is_visible, self.is_bleeding, self.is_movement_handicapped))
            info += ('\n*Is blinded? {}. Is deafened? {}. Is gagged? {}'
                     .format(self.is_blind, self.is_deaf, self.is_gagged))
            info += ('\n*Is transient? {}. Has autopass? {}. Clients open: {}'
                     .format(self.is_transient, self.autopass, len(self.get_multiclients())))
            info += '\n*Is muted? {}. Is OOC Muted? {}'.format(self.is_muted, self.is_ooc_muted)
            info += '\n*Following: {}'.format(self.following.id if self.following else "-")
            info += '\n*Followed by: {}'.format(", ".join([str(c.id) for c in self.followedby])
                                                if self.followedby else "-")
            info += '\n*Is Using: {0[0]} {0[1]}'.format(self.version)
            info += ('\n*Online for: {}. Last active: {}'
                     .format(Constants.time_elapsed(self.joined), self.last_active))
            return info

        @property
        def zone_watched(self):
            """
            Declarator for a public zone_watched attribute.
            """

            return self._zone_watched

        @zone_watched.setter
        def zone_watched(self, new_zone_value):
            """
            Set the zone_watched parameter to the given one.

            Parameters
            ----------
            new_zone_value: ZoneManager.Zone or None
                New zone the client is watching.

            Raises
            ------
            ClientError:
                If the client was not watching a zone and new_zone_value is None or,
                if the client was watching a zone and new_zone_value is not None.
            """

            if new_zone_value is None and self._zone_watched is None:
                raise ClientError('This client is already not watching a zone.')
            if new_zone_value is not None and self._zone_watched is not None:
                raise ClientError('This client is already watching a zone.')

            self._zone_watched = new_zone_value

        def __repr__(self):
            return ('C::{}:{}:{}:{}:{}:{}:{}'
                    .format(self.id, self.ipid, self.name, self.get_char_name(), self.showname,
                            self.is_staff(), self.area.id))

    def __init__(self, server, client_obj=None):
        if client_obj is None:
            self.client_obj = self.Client

        self.clients = set()
        self.server = server
        self.cur_id = [False] * self.server.config['playerlimit']
        self.client_obj = client_obj

    def new_client(self, transport, client_obj=None, my_protocol=None, ip=None):
        if ip is None:
            ip = transport.get_extra_info('peername')[0]
        ipid = self.server.get_ipid(ip)

        if client_obj is None:
            client_obj = self.Client

        cur_id = -1
        for i in range(self.server.config['playerlimit']):
            if not self.cur_id[i]:
                cur_id = i
                break
        c = client_obj(self.server, transport, cur_id, ipid, my_protocol=my_protocol)
        self.clients.add(c)

        # Check if server is full, and if so, send number of players and disconnect
        if cur_id == -1:
            c.send_command('PN', self.server.get_player_count(),
                           self.server.config['playerlimit'])
            c.disconnect()
            return c
        self.cur_id[cur_id] = True
        self.server.tasker.client_tasks[cur_id] = dict()
        return c

    def remove_client(self, client):
        # Clients who are following the now leaving client should no longer follow them
        if client.followedby:
            followedby_copy = client.followedby.copy()
            for c in followedby_copy:
                c.unfollow_user()

        # Clients who were being followed by the now leaving client should no longer have a pointer
        # indicating they are being followed by them
        if client.following:
            client.following.followedby.remove(client)

        if client.id >= 0: # Avoid having pre-clients do this (before they are granted a cID)
            self.cur_id[client.id] = False
            # Cancel client's pending tasks
            for task_id in self.server.tasker.client_tasks[client.id].keys():
                self.server.tasker.get_task(client, [task_id]).cancel()

        # If the client was part of a party, remove them from the party
        if client.party:
            client.party.remove_member(client)

        # If the client was watching a zone, remove them from the zone's watcher list, and check if
        # the zone is now empty.
        backup_zone = client.zone_watched

        if client.zone_watched:
            client.zone_watched.remove_watcher(client)
            client.send_ooc_others('(X) Client {} ({}) disconnected while watching your zone ({}).'
                                   .format(client.id, client.displayname, client.area.id),
                                   part_of=backup_zone.get_watchers())
            if not backup_zone.get_watchers():
                client.send_ooc_others('Zone `{}` was automatically deleted as no one was watching '
                                       'it anymore.'.format(backup_zone.get_id()), is_officer=True)

        # If the client was in an area part of a zone, notify all of its watchers, except if they
        # have been already notified. This would happen if a client is in an area part of zone A
        # but they are watching some different zone B instead.
        if client.area.in_zone and backup_zone != client.area.in_zone:
            client.send_ooc_others('(X) Client {} ({}) disconnected in your zone ({}).'
                                   .format(client.id, client.displayname, client.area.id),
                                   is_zstaff=True)

        self.clients.remove(client)

    def get_targets(self, client, key, value, local=False):
        #possible keys: ip, OOC, id, cname, ipid, hdid, showname
        areas = None
        if local:
            areas = [client.area]
        else:
            areas = client.server.area_manager.areas
        targets = []
        if key == TargetType.ALL:
            for nkey in range(7):
                targets += self.get_targets(client, nkey, value, local)
        for area in areas:
            for target in area.clients:
                if key == TargetType.IP:
                    if target.get_ipreal().lower().startswith(value.lower()):
                        targets.append(target)
                elif key == TargetType.OOC_NAME:
                    if target.name.lower().startswith(value.lower()):
                        targets.append(target)
                elif key == TargetType.CHAR_NAME:
                    if target.get_char_name().lower().startswith(value.lower()):
                        targets.append(target)
                elif key == TargetType.CHAR_FOLDER:
                    if target.char_folder.lower().startswith(value.lower()):
                        targets.append(target)
                elif key == TargetType.ID:
                    if target.id == value:
                        targets.append(target)
                elif key == TargetType.IPID:
                    if target.ipid == value:
                        targets.append(target)
                elif key == TargetType.HDID:
                    if target.hdid == value:
                        targets.append(target)
                elif key == TargetType.SHOWNAME:
                    if target.showname.lower().startswith(value.lower()):
                        targets.append(target)
        return targets

    def get_muted_clients(self):
        clients = []
        for client in self.clients:
            if client.is_muted:
                clients.append(client)
        return clients

    def get_ooc_muted_clients(self):
        clients = []
        for client in self.clients:
            if client.is_ooc_muted:
                clients.append(client)
        return clients

    def get_target_public(self, client, identifier, only_in_area=False):
        """
        If the first entry of `identifier` is an ID of some client, return that client.
        Otherwise, return the client in the same area as `client` such that one of the
        following is true:
            * Their character name starts with `identifier`
            * Their character they have iniedited to starts with `identifier`
            * Their custom showname starts with `identifier`
            * Their OOC name starts with `identifier`
        Note these criteria are public information for any client regardless of rank.
        If `client` is not a staff member, targets that are sneaking will be discarded if `client`
        is not sneaking or, if they are, they are not part of a party of the same party as the
        target. No output messages will include these discarded targets, even for error messages.

        Parameters
        ----------
        client: ClientManager.Client
            Client whose area will be considered when looking for targets
        identifier: str
            Identifier for target
        only_in_area: bool (optional)
            If search should be limited just to area for parameters guaranteed to be unique as well
            (such as client ID). By default false.

        Returns
        -------
        (ClientManager.Client, str, str)
            Client with an identifier that matches `identifier` as previously described.
            The match that was made, using as much from `identifier` as possible.
            The substring of `identifier` that was not used.

        Raises
        ------
        ClientError:
            If either no clients or more than one client matches the identifier.
        """

        split_identifier = identifier.split(' ')
        multiple_match_mes = ''
        valid_targets = list()

        def _discard_sneaked_if_needed(targets):
            try:
                party_sender = client.get_party()
            except PartyError:
                party_sender = None

            new_targets = set()
            for target in targets:
                if client.is_staff() or target.is_visible:
                    new_targets.add(target)
                # Only consider a sneaked target as valid if the following is true:
                # 1. Client is not visible
                # 2. Client and target are part of the same party
                elif (not client.is_visible and party_sender):
                    try:
                        party_target = target.get_party()
                    except PartyError:
                        party_target = None

                    if party_sender == party_target:
                        new_targets.add(target)
            return new_targets

        for word_number in range(len(split_identifier)):
            # As len(split_identifier) >= 1, this for loop is run at least once, so we can use
            # top-level variables defined here outside the for loop

            # Greedily try and find the smallest possible identifier that gets one unique target
            identity, rest = (' '.join(split_identifier[:word_number+1]),
                              ' '.join(split_identifier[word_number+1:]))
            # First pretend the identity is a client ID, which is unique
            if identity.isdigit():
                targets = set(self.get_targets(client, TargetType.ID, int(identity), only_in_area))
                targets = _discard_sneaked_if_needed(targets)
                if len(targets) == 1:
                    # Found unique match
                    valid_targets = targets
                    valid_match = identity
                    valid_rest = rest
                    break

            # Otherwise, other identifiers may not be unique, so consider all possibilities
            # Pretend the identity is a character name, iniswapped to folder, a showname or OOC name
            possibilities = [
                (TargetType.CHAR_NAME, lambda target: target.get_char_name()),
                (TargetType.CHAR_FOLDER, lambda target: target.char_folder),
                (TargetType.SHOWNAME, lambda target: target.showname),
                (TargetType.OOC_NAME, lambda target: target.name)]
            targets = set()

            # Match against everything
            for possibility in possibilities:
                id_type, id_value = possibility
                new_targets = set(self.get_targets(client, id_type, identity, True))
                new_targets = _discard_sneaked_if_needed(new_targets)
                if new_targets:
                    targets |= new_targets
                    matched = id_value(new_targets.pop())

            if not targets:
                # Covers both the case where no targets were found (at which case no targets will
                # be found later on)
                break
            if len(targets) == 1:
                # Covers the case where exactly one target is found. As the algorithm is meant to
                # produce a greedy result, the for loop will continue in case a larger selection of
                # `identifier` can be matched to a single target.
                valid_targets = targets
                valid_match = matched
                valid_rest = rest
            else:
                # Otherwise, our identity guess was not precise enough, so keep track of that
                # for later and continue with the for loop
                multiple_match_mes = 'Multiple targets match identifier `{}`'.format(identity)
                for target in sorted(list(targets), key=lambda c: c.id):
                    char = target.get_char_name()
                    if target.char_folder and target.char_folder != char: # Show iniswap if needed
                        char = '{}/{}'.format(char, target.char_folder)

                    multiple_match_mes += ('\r\n*[{}] {} ({}) (OOC: {})'
                                           .format(target.id, char, target.showname, target.name))

        if not valid_targets or len(valid_targets) > 1:
            # If was able to match more than one at some point, return that
            if multiple_match_mes:
                raise ClientError(multiple_match_mes)
            # Otherwise, show that no match was ever found
            raise ClientError('No targets with identifier `{}` found.'.format(identifier))

        # For `matched` to be undefined, no targets should have been matched, which would have
        # been caught before.
        return valid_targets.pop(), valid_match, valid_rest
