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

import time

from server import logger
from server.exceptions import ClientError, AreaError
from server.constants import Constants

class ClientChangeArea:
    def __init__(self, client):
        self.client = client

    def check_change_area(self, area, override_passages=False, override_effects=False,
                          more_unavail_chars=None):
        """
        Perform all checks that would prevent an area change.
        Right now there is, (in this order)
        * In target area already.
        * If existing handicap has not expired.
        * If moving while sneaking to lobby/private area.
        * If target area has some lock player has no perms for.
        * If target area is unreachable from the current one.
        * If no available characters in the new area.
        ** In this check a new character is selected if there is a character conflict too.
           However, the change is not performed in this portion of code.

        No send_oocs commands are meant to be put here, so as to avoid unnecessary
        notifications. Append any intended messages to the captured_messages list and then
        manually send them out outside this function.
        """
        clnt = self.client
        captured_messages = list()

        # Obvious check first
        if clnt.area == area:
            raise ClientError('User is already in target area.', code='ChArInArea')

        # Check if player has waited a non-zero movement delay
        if not clnt.is_staff() and clnt.is_movement_handicapped and not override_effects:
            start, length, name, _ = clnt.server.get_task_args(clnt, ['as_handicap'])
            _, remain_text = Constants.time_remaining(start, length)
            raise ClientError("You are still under the effects of movement handicap '{}'. "
                              "Please wait {} before changing areas."
                              .format(name, remain_text), code='ChArHandicap')

        # Check if trying to move to a lobby/private area while sneaking
        if area.lobby_area and not clnt.is_visible and not clnt.is_mod and not clnt.is_cm:
            raise ClientError('Lobby areas do not let non-authorized users remain sneaking. Please '
                              'change music, speak IC or ask a staff member to reveal you.',
                              code='ChArSneakLobby')
        if area.private_area and not clnt.is_visible:
            raise ClientError('Private areas do not let sneaked users in. Please change the '
                              'music, speak IC or ask a staff member to reveal you.',
                              code='ChArSneakPrivate')

        # Check if area has some sort of lock
        if not clnt.ipid in area.invite_list:
            if area.is_locked and not clnt.is_staff():
                raise ClientError('That area is locked.', code='ChArLocked')
            if area.is_gmlocked and not clnt.is_mod and not clnt.is_gm:
                raise ClientError('That area is gm-locked.', code='ChArGMLocked')
            if area.is_modlocked and not clnt.is_mod:
                raise ClientError('That area is mod-locked.', code='ChArModLocked')

        # Check if trying to reach an unreachable area
        if not (clnt.is_staff() or clnt.is_transient or override_passages or
                area.name in clnt.area.reachable_areas or '<ALL>' in clnt.area.reachable_areas):
            info = ('Selected area cannot be reached from your area without authorization. '
                    'Try one of the following areas instead: ')
            if clnt.area.reachable_areas == {clnt.area.name}:
                info += '\r\n*No areas available.'
            else:
                get_name = clnt.server.area_manager.get_area_by_name
                try:
                    sorted_areas = sorted(clnt.area.reachable_areas, key=lambda x: get_name(x).id)
                    for reachable_area in sorted_areas:
                        if reachable_area != clnt.area.name:
                            area_id = clnt.server.area_manager.get_area_by_name(reachable_area).id
                            info += '\r\n*({}) {}'.format(area_id, reachable_area)
                except AreaError:
                    #When would you ever execute this piece of code is beyond me, but meh
                    info += '\r\n<ALL>'
            raise ClientError(info, code='ChArUnreachable')

        # Check if current character is taken in the new area
        new_char_id = clnt.char_id
        if not area.is_char_available(clnt.char_id, allow_restricted=clnt.is_staff(),
                                      more_unavail_chars=more_unavail_chars):
            try:
                new_char_id = area.get_rand_avail_char_id(allow_restricted=clnt.is_staff(),
                                                          more_unavail_chars=more_unavail_chars)
            except AreaError:
                raise ClientError('No available characters in that area.',
                                  code='ChArNoCharacters')

        return new_char_id, captured_messages

    def notify_change_area(self, area, old_char, ignore_bleeding=False, just_me=False):
        """
        Send all OOC notifications that come from switching areas.
        Right now there is
        * Showname conflict if there is one, sent to player who's moving.
        * Lights off notification if no lights in new area, sent to player who's moving.
        * Traveling notifications:
        ** Autopass if turned on and lights on, sent to everyone else in the new area.
        ** Footsteps in if lights off in new area, sent to everyone else in the new area.
        ** Footsteps out if lights off in old area, sent to everyone else in the old area.
        * Blood notifications (accounting for lights and sneaking):
        ** Bleeding status of people in the area, sent to player who's moving
        ** Bleeding status of the person who's moved, sent to everyone else in the area
        ** Blood in area status, sent to player who's moving.

        If just_me is True, no notifications are sent to other players in the area.
        """
        self.notify_me(area, old_char, ignore_bleeding=ignore_bleeding)
        if not just_me:
            self.notify_others(area, old_char, ignore_bleeding=ignore_bleeding)

    def notify_me(self, area, old_char, ignore_bleeding=False):
        clnt = self.client

        # Code here assumes successful area change, so it will be sending client notifications
        old_area = clnt.area

        ###########
        # Check if someone in the new area has the same showname
        try: # Verify that showname is still valid
            clnt.change_showname(clnt.showname, target_area=area)
        except ValueError:
            clnt.send_ooc('Your showname {} was already used in this area so it has been cleared.'
                          .format(clnt.showname))
            clnt.change_showname('', target_area=area)
            logger.log_server('{} had their showname removed due it being used in the new area.'
                              .format(clnt.ipid), clnt)

        ###########
        # Check if the lights were turned off, and if so, let you know, if you are not blind
        if not area.lights:
            clnt.send_ooc('You enter a pitch dark room.', to_blind=False)

        if not ignore_bleeding and clnt.is_bleeding:
            # As these are sets, repetitions are automatically filtered out
            old_area.bleeds_to.add(area.name)
            area.bleeds_to.add(old_area.name)
            clnt.send_ooc('You are bleeding.')

        ###########
        # Check bleeding status
        self.notify_me_blood(area)

    def notify_me_blood(self, area, changed_visibility=True, changed_hearing=True):
        clnt = self.client
        changed_area = (clnt.area != area)

        ###########
        # If someone else is bleeding in the new area, notify the person moving
        bleeding_visible = [c for c in area.clients
                            if c.is_visible and c.is_bleeding and c != clnt]
        bleeding_sneaking = [c for c in area.clients
                             if not c.is_visible and c.is_bleeding and c != clnt]
        info = ''
        vis_info = ''
        sne_info = ''

        # To prepare message with players bleeding, one of these must be true:
        # 1. You are staff
        # 2. Lights are on and you are not blind
        # Otherwise, prepare faint drops of blood if you are not deaf.
        # Otherwise, just prepare 'smell' if lights turned off or you are blind

        if bleeding_visible:
            normal_visibility = changed_visibility and area.lights and not clnt.is_blind
            if clnt.is_staff() or normal_visibility:
                vis_info = ('{}You see {} {} bleeding'
                            .format('(X) ' if not normal_visibility else '',
                                    Constants.cjoin([c.get_char_name() for c in bleeding_visible]),
                                    'is' if len(bleeding_visible) == 1 else 'are'))
            elif not clnt.is_deaf and changed_hearing:
                vis_info = 'You hear faint drops of blood'
            elif clnt.is_blind and clnt.is_deaf and changed_area:
                vis_info = 'You smell blood'

        # To prepare message with sneaked bleeding, you must be staff.
        # Otherwise, prepare faint drops of blood if you are not deaf.
        # Otherwise, just prepare 'smell' if lights turned off or you are blind

        if bleeding_sneaking:
            if clnt.is_staff():
                sne_info = ('You see {} {} bleeding while sneaking'
                            .format(Constants.cjoin([c.get_char_name() for c in bleeding_sneaking]),
                                    'is' if len(bleeding_visible) == 1 else 'are'))
            elif not clnt.is_deaf and changed_hearing:
                    sne_info = 'You hear faint drops of blood'
            elif not area.lights or clnt.is_blind and changed_area:
                sne_info = 'You smell blood'

        # If there is visible info, merge it with sneak info if the following is true
        # 1. There is sneak info
        # 2. Sneak info is not 'You smell blood' (as that would be true anyway)
        # 3. It is not the same as the visible info (To avoid double 'hear faint drops')
        if vis_info:
            if sne_info and sne_info != 'You smell blood' and vis_info != sne_info:
                info = '{}, and {}'.format(info, sne_info.lower())
            else:
                info = vis_info
        else:
            info = sne_info

        if info:
            clnt.send_ooc(info + '.')

        ###########
        # If there are blood trails in the area, send notification if one of the following is true
        ## 1. You are staff
        ## 2. Lights are on and you are not blind.
        ## If the blood in the area is smeared, just indicate there is smeared blood for non-staff
        ## and the regular blood trail message with extra text for staff.
        # If neither is true, send 'smell' notification as long as the following is true:
        # 1. Lights turned off or you are blind
        # 2. A notification was not sent in the previous part

        normal_visibility = changed_visibility and area.lights and not clnt.is_blind
        if clnt.is_staff() or normal_visibility:
            start_connector = '(X) ' if not normal_visibility else ''
            smeared_connector = 'smeared ' if clnt.is_staff() and area.blood_smeared else ''

            if not clnt.is_staff() and area.blood_smeared:
                clnt.send_ooc('{}You spot some smeared blood in the area.'
                              .format(start_connector))
            elif area.bleeds_to == set([area.name]):
                clnt.send_ooc('{}You spot some {}blood in the area.'
                              .format(start_connector, smeared_connector))
            elif len(area.bleeds_to) > 1:
                bleed_to_areas = list(area.bleeds_to - set([area.name]))
                if clnt.is_staff() and area.blood_smeared:
                    start_connector = '(X) ' # Force staff indication

                info = ('{}You spot a {}blood trail leading to {}.'
                        .format(start_connector, smeared_connector,
                                Constants.cjoin(bleed_to_areas, the=True)))
                clnt.send_ooc(info)
        elif not clnt.is_staff() and (area.bleeds_to or area.blood_smeared) and changed_area:
            if not info:
                clnt.send_ooc('You smell blood.')

    def notify_others(self, area, old_char, ignore_bleeding=False):
        clnt = self.client

        # Code here assumes successful area change, so it will be sending client notifications
        old_area = clnt.area
        new_char = clnt.get_char_name()

        ###########
        # Assuming this is not a spectator...
        # If autopassing, send OOC messages, provided the lights are on. If lights are off,
        # send nerfed announcements regardless. Keep track of who is blind and/or deaf as well.

        if not clnt.char_id < 0 and clnt.is_visible:
            self.notify_others_moving(clnt, old_area,
                                      '{} has left to the {}'.format(old_char, area.name),
                                      'You hear footsteps going out of the room.')
            self.notify_others_moving(clnt, area,
                                      '{} has entered from the {}'.format(new_char, old_area.name),
                                      'You hear footsteps coming into the room.')

        if clnt.is_bleeding:
            old_area.bleeds_to.add(old_area.name)
            area.bleeds_to.add(area.name)

        if not ignore_bleeding and clnt.is_bleeding:
            self.notify_others_blood(clnt, area, new_char, status='arrived')
            self.notify_others_blood(clnt, old_area, old_char, status='left')

    def notify_others_moving(self, clnt, area, autopass_mes, blind_mes):
        staff = nbnd = ybnd = nbyd = '' # nbnd = notblindnotdeaf ybnd=yesblindnotdeaf

        # Autopass: at most footsteps if no lights
        # No autopass: at most footsteps if no lights
        # Blind: at most footsteps
        # Deaf: can hear autopass but not footsteps
        # No lights: at most footsteps

        if clnt.autopass:
            staff = autopass_mes
            nbnd = autopass_mes
            ybnd = blind_mes
            nbyd = autopass_mes
        if not area.lights:
            staff = blind_mes if not staff else '(X) {}'.format(autopass_mes) # Staff get autopass
            nbnd = blind_mes
            ybnd = blind_mes
            nbyd = ''

        clnt.send_ooc_others(staff, in_area=area, is_staff=True)
        clnt.send_ooc_others(nbnd, in_area=area, is_staff=False, to_blind=False, to_deaf=False)
        clnt.send_ooc_others(ybnd, in_area=area, is_staff=False, to_blind=True, to_deaf=False)
        clnt.send_ooc_others(nbyd, in_area=area, is_staff=False, to_blind=False, to_deaf=True)
        # Blind and deaf get nothing

    def notify_others_blood(self, clnt, area, char, status='stay', send_to_staff=True):
        # Assume clnt's bleeding status is worth announcing (for example, it changed, or lights on)
        # If bleeding, send reminder, and notify everyone in the area if not sneaking
        # (otherwise, just send vague message).

        if clnt.is_bleeding:
            area_had_bleeding = (len([c for c in area.clients if c.is_bleeding]) > 0)

            dsh = {True: 'You start hearing more drops of blood.',
                   False: 'You faintly start hearing drops of blood.'}
            dshs = {True: 'You start hearing and smelling more drops of blood.',
                    False: 'You faintly start hearing and smelling drops of blood.'}
            dss = {True: 'You start smelling more blood.',
                   False: 'You faintly start smelling blood.'}

            h_mes = dsh[area_had_bleeding] # hearing message
            s_mes = dss[area_had_bleeding] # smelling message
            hs_mes = dshs[area_had_bleeding] # hearing and smelling message
            vis_status = 'now'
        else:
            area_sole_bleeding = (len([c for c in area.clients if c.is_bleeding]) == 1)
            dsh = {True: 'You stop hearing drops of blood.',
                   False: 'You start hearing less drops of blood.'}
            dshs = {True: 'You stop hearing and smelling drops of blood.',
                    False: 'You start hearing and smelling less drops of blood.'}
            dss = {True: 'You stop smelling blood.',
                   False: 'You start smelling less blood.'}

            h_mes = dsh[area_sole_bleeding] # hearing message
            s_mes = dss[area_sole_bleeding] # smelling message
            hs_mes = dshs[area_sole_bleeding] # hearing and smelling message
            vis_status = 'no longer'

        ybyd_mes = hs_mes
        darkened = 'darkened ' if not area.lights else ''

        if status == 'stay':
            connector = 'is {}'.format(vis_status)
            pconnector = 'was {}'.format(vis_status)
        elif status == 'left':
            connector = 'leave the {}area while still'.format(darkened)
            pconnector = 'left the {}area while still'.format(darkened)
        elif status == 'arrived':
            connector = 'arrive to the {}area while'.format(darkened)
            pconnector = 'arrived to the {}area while'.format(darkened)

        if clnt.is_visible and area.lights:
            def_mes = 'You see {} {} bleeding.'.format(char, connector)
            ybnd_mes = h_mes
            nbyd_mes = def_mes
            staff_mes = def_mes
        elif not clnt.is_visible and area.lights:
            def_mes = h_mes
            ybnd_mes = hs_mes
            nbyd_mes = s_mes
            staff_mes = '(X) {} {} bleeding and sneaking.'.format(char, pconnector)
        elif clnt.is_visible and not area.lights:
            def_mes = hs_mes
            ybnd_mes = hs_mes
            nbyd_mes = s_mes
            staff_mes = '(X) {} {} bleeding.'.format(char, pconnector)
        elif not clnt.is_visible and not area.lights:
            def_mes = hs_mes
            ybnd_mes = hs_mes
            nbyd_mes = s_mes
            staff_mes = ('(X) {} {} bleeding and sneaking.'.format(char, pconnector))

        staff_mes = staff_mes.replace('no longer bleeding and sneaking.',
                                      'no longer bleeding, but is still sneaking.') # Ugly

        clnt.send_ooc_others(def_mes, is_staff=False, in_area=area, to_blind=False, to_deaf=False)
        clnt.send_ooc_others(ybnd_mes, is_staff=False, in_area=area, to_blind=True, to_deaf=False)
        clnt.send_ooc_others(nbyd_mes, is_staff=False, in_area=area, to_blind=False, to_deaf=True)
        clnt.send_ooc_others(ybyd_mes, is_staff=False, in_area=area, to_blind=True, to_deaf=True)
        if send_to_staff:
            clnt.send_ooc_others(staff_mes, is_staff=True, in_area=area)

    def change_area(self, area, override_all=False, override_passages=False,
                    override_effects=False, ignore_bleeding=False, ignore_followers=False,
                    ignore_checks=False, ignore_notifications=False, more_unavail_chars=None,
                    change_to=None, from_party=False):
        """
        PARAMETERS:
        *override_passages: ignore passages existing from the source area to the target area
        *override_effects: ignore current effects, such as movement handicaps
        *ignore_bleeding: not add blood to the area if the character is moving,
         such as from /area_kick or AFK kicks
        *ignore_followers: avoid sending the follow command to followers (e.g. using /follow)
        *restrict_characters: additional characters to mark as restricted, others than the one
         used in the area or area restricted.
        *override_all: perform the area change regarldess of area restrictions and send no
         RP related notifications (only useful for complete area reload). In particular,
         override_all being False performs all the checks and announces the area change in OOC.
        *ignore_checks: ignore the change area checks.
        *ignore_notifications: ignore the area notifications except character change.
        *more_unavail_chars: additional characters in the target area to mark as taken.
        *change_to: character to manually change to in the target area (requires ignore_checks
         to be True).
        *from_party: if the change area order is made assuming the character is in a party (in
         reality, it is just to serve as a base case because change_area is called recursively).
        """
        clnt = self.client

        if not override_all:
            # All the code that could raise errors goes here

            # If player is in a party, do special method instead of this
            if from_party:
                clnt.server.party_manager.move_party(clnt.party, clnt, area)
                return

            # It also returns the character name that the player ended up, if it changed.
            if not ignore_checks:
                new_cid, mes = clnt.check_change_area(area, override_passages=override_passages,
                                                      override_effects=override_effects,
                                                      more_unavail_chars=more_unavail_chars)
            else:
                if change_to:
                    new_cid, mes = change_to, list()
                else:
                    new_cid, mes = clnt.char_id, list()

            # Code after this line assumes that the area change will be successful
            # (but has not yet been performed)

            # Send client messages that could have been generated during the change area check
            for message in mes:
                clnt.send_ooc(message)

            # Perform the character switch if new area has a player with the current char
            # or the char is restricted there.
            old_char = clnt.get_char_name()
            if new_cid != clnt.char_id:
                clnt.change_character(new_cid, target_area=area)
                if old_char in area.restricted_chars:
                    clnt.send_ooc('Your character was restricted in your new area, switched '
                                  'to {}.'.format(clnt.get_char_name()))
                else:
                    clnt.send_ooc('Your character was taken in your new area, switched to {}.'
                                  .format(clnt.get_char_name()))

            if not ignore_notifications:
                clnt.send_ooc('Changed area to {}.[{}]'.format(area.name, area.status))
                logger.log_server('[{}]Changed area from {} ({}) to {} ({}).'
                                  .format(clnt.get_char_name(), clnt.area.name, clnt.area.id,
                                          area.name, area.id), clnt)
                #logger.log_rp('[{}]Changed area from {} ({}) to {} ({}).'
                #              .format(clnt.get_char_name(), old_area.name, old_area.id,
                #                      clnt.area.name, clnt.area.id), clnt)

                clnt.notify_change_area(area, old_char, ignore_bleeding=ignore_bleeding)

        clnt.area.remove_client(clnt)
        clnt.area = area
        area.new_client(clnt)

        clnt.send_command('HP', 1, clnt.area.hp_def)
        clnt.send_command('HP', 2, clnt.area.hp_pro)
        clnt.send_command('BN', clnt.area.background)
        clnt.send_command('LE', *clnt.area.get_evidence_list(clnt))

        if clnt.followedby and not ignore_followers and not override_all:
            for c in clnt.followedby:
                c.follow_area(area)

        clnt.reload_music_list() # Update music list to include new area's reachable areas
        clnt.server.create_task(clnt, ['as_afk_kick', area.afk_delay, area.afk_sendto])
        # Try and restart handicap if needed
        try:
            _, length, name, announce_if_over = clnt.server.get_task_args(clnt, ['as_handicap'])
        except (ValueError, KeyError):
            pass
        else:
            clnt.server.create_task(clnt, ['as_handicap', time.time(), length, name,
                                           announce_if_over])
