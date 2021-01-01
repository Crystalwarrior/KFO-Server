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

        client = self.client
        captured_messages = list()

        # Obvious check first
        if client.area == area:
            raise ClientError('User is already in target area.', code='ChArInArea')

        # Check if player has waited a non-zero movement delay
        if not client.is_staff() and client.is_movement_handicapped and not override_effects:
            start, length, name, _ = client.server.tasker.get_task_args(client, ['as_handicap'])
            _, remain_text = Constants.time_remaining(start, length)
            raise ClientError("You are still under the effects of movement handicap '{}'. "
                              "Please wait {} before changing areas."
                              .format(name, remain_text), code='ChArHandicap')

        # Check if trying to move to a lobby/private area while sneaking
        if area.lobby_area and not client.is_visible and not client.is_officer():
            raise ClientError('Lobby areas do not let non-authorized users remain sneaking. Please '
                              'change music, speak IC or ask a staff member to reveal you.',
                              code='ChArSneakLobby')
        if area.private_area and not client.is_visible:
            raise ClientError('Private areas do not let sneaked users in. Please change the '
                              'music, speak IC or ask a staff member to reveal you.',
                              code='ChArSneakPrivate')

        # Check if area has some sort of lock
        if client.ipid not in area.invite_list:
            if area.is_locked and not client.is_staff():
                raise ClientError('That area is locked.', code='ChArLocked')
            if area.is_gmlocked and not client.is_mod and not client.is_gm:
                raise ClientError('That area is gm-locked.', code='ChArGMLocked')
            if area.is_modlocked and not client.is_mod:
                raise ClientError('That area is mod-locked.', code='ChArModLocked')

        # Check if trying to reach an unreachable area
        if not (client.is_staff() or client.is_transient or override_passages or
                area.name in client.area.reachable_areas):
            raise ClientError('The passage to this area is locked.',
                              code='ChArUnreachable')
            """
            info = ('Selected area cannot be reached from your area without authorization. '
                    'Try one of the following areas instead: ')
            if client.area.visible_reachable_areas == {client.area.name}:
                info += '\r\n*No areas available.'
            else:
                get_name = client.server.area_manager.get_area_by_name
                try:
                    sorted_areas = sorted(client.area.visible_reachable_areas,
                                          key=lambda x: get_name(x).id)
                    for reachable_area in sorted_areas:
                        if reachable_area != client.area.name:
                            area_id = client.server.area_manager.get_area_by_name(reachable_area).id
                            info += '\r\n*({}) {}'.format(area_id, reachable_area)
                except AreaError:
                    # When would you ever execute this piece of code is beyond me, but meh
                    info += '\r\n<ALL>'
            raise ClientError(info, code='ChArUnreachable')
            """

        # Check if current character is taken in the new area
        new_char_id = client.char_id
        if not area.is_char_available(client.char_id, allow_restricted=client.is_staff(),
                                      more_unavail_chars=more_unavail_chars):
            try:
                new_char_id = area.get_rand_avail_char_id(allow_restricted=client.is_staff(),
                                                          more_unavail_chars=more_unavail_chars)
            except AreaError:
                raise ClientError('No available characters in that area.',
                                  code='ChArNoCharacters')

        return new_char_id, captured_messages

    def notify_change_area(self, area, old_dname, ignore_bleeding=False, just_me=False) -> bool:
        """
        Send all OOC notifications that come from switching areas.
        Right now there is
        * Zone entry/exit notifications
        ** Zone exit if player was in area in zone A and now moves to area not in zone A,
           sent to player who's moving and zone A watchers
        ** Zone entry if player was in area not in zone B and now moves to area in zone B,
           sent to player who's moving and zone B watchers
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

        Returns True if any RP related notifications are sent to the player who changed areas,
        False otherwise.

        """

        found_something = self.notify_me(area, old_dname, ignore_bleeding=ignore_bleeding)
        if not just_me:
            self.notify_others(area, old_dname, ignore_bleeding=ignore_bleeding)

        return found_something

    def notify_me(self, area, old_dname, ignore_bleeding=False) -> bool:
        client = self.client

        # Code here assumes successful area change, so it will be sending client notifications
        old_area = client.area

        ###########
        # Check if exiting a zone
        if old_area.in_zone and area.in_zone != old_area.in_zone:
            # If the new area is not part of a zone, send order to go back to original gamemode
            # If the area is part of a zone, that is covered in the next if
            if not area.in_zone:
                client.send_gamemode(name='')

            zone_id = old_area.in_zone.get_id()

            if client.is_staff() and client.zone_watched == old_area.in_zone:
                client.send_ooc('(X) You have left zone `{}`. To stop receiving its notifications, '
                                'stop watching it with /zone_unwatch'.format(zone_id))
            else:
                client.send_ooc('You have left zone `{}`.'.format(zone_id))


        # Check if entering a zone
        if area.in_zone and area.in_zone != old_area.in_zone:
            client.send_gamemode(name=area.in_zone.get_mode())
            zone_id = area.in_zone.get_id()

            if client.is_staff() and client.zone_watched != area.in_zone:
                client.send_ooc('(X) You have entered zone `{}`. To be able to receive its '
                                'notifications, start watching it with /zone_watch {}'
                                .format(zone_id, zone_id))
            else:
                client.send_ooc('You have entered zone `{}`.'.format(zone_id))

        # Check if someone in the new area has the same showname
        try: # Verify that showname is still valid
            client.change_showname(client.showname, target_area=area)
        except ValueError:
            client.send_ooc('Your showname `{}` was already used in this area, so it has been '
                            'removed.'.format(client.showname))
            client.send_ooc_others('(X) Client {} had their showname `{}` removed in your zone '
                                   'due to it conflicting with the showname of another player in '
                                   'the same area ({}).'
                                   .format(client.id, client.showname, area.id), is_zstaff=area)
            client.change_showname('', target_area=area)
            logger.log_server('{} had their showname removed due it being used in the new area.'
                              .format(client.ipid), client)

        ###########
        # Check if the lights were turned off, and if so, let you know, if you are not blind
        if not area.lights:
            client.send_ooc('You enter a pitch dark room.', to_blind=False)

        if not ignore_bleeding and client.is_bleeding:
            # As these are sets, repetitions are automatically filtered out
            old_area.bleeds_to.add(area.name)
            area.bleeds_to.add(old_area.name)
            client.send_ooc('You are bleeding.')

        found_something = self.notify_me_rp(area)
        return found_something

    def notify_me_rp(self, area, changed_visibility=True, changed_hearing=True) -> bool:
        ###########
        # Check bleeding status
        blood = self.notify_me_blood(area, changed_visibility=changed_visibility,
                                     changed_hearing=changed_hearing)

        ###########
        # Check for any player statuses
        statuses = self.notify_me_status(area, changed_visibility=changed_visibility,
                                         changed_hearing=changed_hearing)

        ###########
        # Check for the area being noteworthy
        area_noteworthy = self.notify_me_area_noteworthy(area,
                                                         changed_visibility=changed_visibility,
                                                         changed_hearing=changed_hearing)

        return blood or statuses or area_noteworthy

    def notify_me_blood(self, area, changed_visibility=True, changed_hearing=True) -> bool:
        client = self.client
        changed_area = (client.area != area)
        found_something = False

        ###########
        # If someone else is bleeding in the new area, notify the person moving
        bleeding_visible = [c for c in area.clients
                            if c.is_visible and c.is_bleeding and c != client]
        bleeding_sneaking = [c for c in area.clients
                             if not c.is_visible and c.is_bleeding and c != client]
        bleeding_info = ''
        vis_info = ''
        sne_info = ''

        # To prepare message with players bleeding, one of these must be true:
        # 1. You are staff
        # 2. Lights are on and you are not blind
        # Otherwise, prepare faint drops of blood if you are not deaf.
        # Otherwise, just prepare 'smell' if lights turned off or you are blind

        if bleeding_visible:
            normal_visibility = changed_visibility and area.lights and not client.is_blind
            if client.is_staff() or normal_visibility:
                vis_info = ('{}You see {} {} bleeding'
                            .format('(X) ' if not normal_visibility else '',
                                    Constants.cjoin([c.displayname for c in bleeding_visible]),
                                    'is' if len(bleeding_visible) == 1 else 'are'))
            elif not client.is_deaf and changed_hearing:
                vis_info = 'You hear faint drops of blood'
            elif client.is_blind and client.is_deaf and changed_area:
                vis_info = 'You smell blood'

        # To prepare message with sneaked bleeding, you must be staff.
        # Otherwise, prepare faint drops of blood if you are not deaf.
        # Otherwise, just prepare 'smell' if lights turned off or you are blind

        if bleeding_sneaking:
            if client.is_staff():
                sne_info = ('(X) You see {} {} bleeding while sneaking'
                            .format(Constants.cjoin([c.displayname for c in bleeding_sneaking]),
                                    'is' if len(bleeding_visible) == 1 else 'are'))
            elif not client.is_deaf and changed_hearing:
                sne_info = 'You hear faint drops of blood'
            elif not area.lights or client.is_blind and changed_area:
                sne_info = 'You smell blood'

        # If there is visible info, merge it with sneak info if the following is true
        # 1. There is sneak info
        # 2. Sneak info is not 'You smell blood' (as that would be true anyway)
        # 3. It is not the same as the visible info (To avoid double 'hear faint drops')
        if vis_info:
            if sne_info and sne_info != 'You smell blood' and vis_info != sne_info:
                if client.is_staff():
                    # This has (X) no matter what courtesy of sne_info
                    # Move (X) to the beginning of vis_info if needed
                    vis_info = f'(X) {vis_info}' if not vis_info.startswith('(X)') else vis_info
                    sne_info = sne_info.replace('(X) ', '', 1)
                sne_info = sne_info[0].lower() + sne_info[1:]
                bleeding_info = '{}, and {}'.format(vis_info, sne_info)
            else:
                bleeding_info = vis_info
        else:
            bleeding_info = sne_info

        if bleeding_info:
            client.send_ooc(bleeding_info + '.')
            found_something = True

        ###########
        # If there are blood trails in the area, send notification if one of the following is true
        ## 1. You are staff
        ## 2. Lights are on and you are not blind.
        ## If the blood in the area is smeared, just indicate there is smeared blood for non-staff
        ## and the regular blood trail message with extra text for staff.
        # If neither is true, send 'smell' notification as long as the following is true:
        # 1. Lights turned off or you are blind
        # 2. A notification was not sent in the previous part

        normal_visibility = changed_visibility and area.lights and not client.is_blind
        bloodtrail_info = ''
        if client.is_staff() or normal_visibility:
            start_connector = '(X) ' if not normal_visibility else ''
            smeared_connector = 'smeared ' if client.is_staff() and area.blood_smeared else ''

            if not client.is_staff() and area.blood_smeared:
                bloodtrail_info = ('{}You spot some smeared blood in the area.'
                                   .format(start_connector))
            elif area.bleeds_to == set([area.name]):
                bloodtrail_info = ('{}You spot some {}blood in the area.'
                                   .format(start_connector, smeared_connector))
            elif len(area.bleeds_to) > 1:
                bleed_to_areas = list(area.bleeds_to - set([area.name]))
                if client.is_staff() and area.blood_smeared:
                    start_connector = '(X) ' # Force staff indication

                bloodtrail_info = ('{}You spot a {}blood trail leading to {}.'
                                   .format(start_connector, smeared_connector,
                                           Constants.cjoin(bleed_to_areas, the=True)))
        elif not client.is_staff() and (area.bleeds_to or area.blood_smeared) and changed_area:
            if not bleeding_info:
                bloodtrail_info = 'You smell blood.'

        if bloodtrail_info:
            client.send_ooc(bloodtrail_info)
            found_something = True

        return found_something

    def notify_me_status(self, area, changed_visibility=True, changed_hearing=True) -> bool:
        client = self.client
        normal_visibility = changed_visibility and area.lights and not client.is_blind
        info = ''
        vis_info = ''
        sne_info = ''
        # While we always notify in OOC if someone has a custom status, we only ping IC if the
        # status has changed from the last time the player has seen it.
        # This prevents ping spam if two players with custom statuses move together.
        found_something = False

        status_visible = [c for c in area.clients if c.status and c != client and c.is_visible]
        status_sneaking = [c for c in area.clients if c.status and c != client and not c.is_visible]
        staff_privileged = not normal_visibility
        if status_visible:
            if client.is_staff() or normal_visibility:
                mark = '(X) ' if staff_privileged else ''
                players = Constants.cjoin([c.displayname for c in status_visible])
                verb = 'was' if len(status_visible) == 1 else 'were'
                vis_info = (f'{mark}You note something about {players} who {verb} in the area '
                            f'already')

                for player in status_visible:
                    remembered_status = client.remembered_statuses.get(player.id, '')
                    if player.status != remembered_status:
                        # Found someone whose status has changed
                        # Only for these situations do we want to ping
                        found_something = True
                    client.remembered_statuses[player.id] = player.status

            elif changed_visibility and not client.is_deaf:
                # Give nerfed notifications if the lights are out or the player is blind, but NOT
                # if the player is deaf.
                vis_info = 'You think something is unusual about someone in the area'

        # To prepare message with sneaked bleeding, you must be staff.
        # Otherwise, prepare faint drops of blood if you are not deaf.
        # Otherwise, just prepare 'smell' if lights turned off or you are blind

        if status_sneaking:
            if client.is_staff():
                players = Constants.cjoin([c.displayname for c in status_sneaking])
                verb = 'was' if len(status_sneaking) == 1 else 'were'
                sne_info = (f'(X) You note something about {players}, who {verb} in the area '
                            f'already and also sneaking')

        if vis_info and sne_info:
            # Remove marks and capital letters. Use 'count=1' explicitly to prevent more
            # replacements that could happen with player displaynames.
            # Then readd the mark manually (mark would have been present because sne_info)
            vis_info = vis_info[4:] if vis_info.startswith('(X)') else vis_info
            sne_info = sne_info.replace("(X) You", "you", 1)
            info = f'(X) {vis_info}, and {sne_info}'
        elif vis_info:
            info = vis_info
        elif sne_info:
            info = sne_info

        if info:
            client.send_ooc(info + '.')

        return found_something

    def notify_me_area_noteworthy(self, area, changed_visibility=True, changed_hearing=True) -> bool:
        if not area.noteworthy:
            return False

        # Regardless of area, changing visibiility or sightedness, ALWAYS send notification
        client = self.client
        client.send_ooc('Something in the area catches your attention.')
        return True

    def notify_others(self, area, old_dname, ignore_bleeding=False):
        client = self.client

        # Code here assumes successful area change, so it will be sending client notifications
        old_area = client.area
        new_dname = client.displayname

        ###########
        # Check if exiting a zone
        if old_area.in_zone and area.in_zone != old_area.in_zone:
            client.send_ooc_others('(X) {} [{}] has left your zone ({}->{}).'
                                   .format(old_dname, client.id, old_area.id, area.id),
                                   is_zstaff=old_area)

        # Check if entering a zone
        if area.in_zone and area.in_zone != old_area.in_zone:
            client.send_ooc_others('(X) {} [{}] has entered your zone ({}->{}).'
                                   .format(new_dname, client.id, old_area.id, area.id),
                                   is_zstaff=area)
            # Raise multiclienting warning to the watchers of the new zone if needed
            # Note that this implementation does not have an off-by-one error, as the incoming
            # client is technically still not in an area within the zone, so only one client being
            # in the zone is necessary and sufficient to correctly trigger the multiclienting
            # warning.
            if [c for c in client.get_multiclients() if c.area.in_zone == area.in_zone]:
                client.send_ooc_others('(X) Warning: Client {} is multiclienting in your zone. '
                                       'Do /multiclients {} to take a look.'
                                       .format(client.id, client.id), is_zstaff=area)

        # Assuming this is not a spectator...
        # If autopassing, send OOC messages

        if not client.char_id < 0:
            self.notify_others_moving(client, old_area,
                                      '{} has left to the {}.'.format(old_dname, area.name),
                                      'You hear footsteps going out of the room.')
            self.notify_others_moving(client, area,
                                      ('{} has entered from the {}.'
                                       .format(new_dname, old_area.name)),
                                      'You hear footsteps coming into the room.')

        ic_attention_others = False

        if client.is_bleeding:
            old_area.bleeds_to.add(old_area.name)
            area.bleeds_to.add(area.name)

        if not ignore_bleeding and client.is_bleeding:
            self.notify_others_blood(client, old_area, old_dname, status='left')
            self.notify_others_blood(client, area, new_dname, status='arrived')
            ic_attention_others = True

        if client.status:
            self.notify_others_status(client, area, new_dname, status='arrived')
            status_refreshed_clients = client.refresh_remembered_status(area=area)
        else:
            status_refreshed_clients = list() # Do not IC ping if client has no status

        area.broadcast_ic_attention(cond=lambda c: (ic_attention_others or
                                                    c in status_refreshed_clients))

    def notify_others_moving(self, client, area, autopass_mes, blind_mes):
        staff = nbnd = ybnd = nbyd = '' # nbnd = notblindnotdeaf ybnd=yesblindnotdeaf

        # Autopass: at most footsteps if no lights
        # No autopass: at most footsteps if no lights
        # Blind: at most footsteps
        # Deaf: can hear autopass but not footsteps
        # No lights: at most footsteps

        # Remove trailing periods and add it again. This helps prevent duplicate periods.
        autopass_mes = autopass_mes[:-1] if autopass_mes.endswith('.') else autopass_mes

        if client.autopass:
            staff = autopass_mes + '.'
            nbnd = autopass_mes + '.'
            ybnd = blind_mes
            nbyd = autopass_mes + '.'
        else:
            staff = '(X) {} (no autopass).'.format(autopass_mes)

        if not area.lights:
            staff = '(X) {} while the lights were out.'.format(autopass_mes)
            nbnd = blind_mes
            ybnd = blind_mes
            nbyd = ''
        if not client.is_visible: # This should be the last statement
            staff = '(X) {} while sneaking.'.format(autopass_mes)
            nbnd = ''
            ybnd = ''
            nbyd = ''

        if client.autopass:
            client.send_ooc_others(staff, in_area=area, is_zstaff_flex=True)
        else:
            client.send_ooc_others(staff, in_area=area, is_zstaff_flex=True,
                                   pred=lambda c: c.get_nonautopass_autopass)
            client.send_ooc_others(nbnd, in_area=area, is_zstaff_flex=True,
                                   pred=lambda c: not c.get_nonautopass_autopass)

        client.send_ooc_others(nbnd, in_area=area, is_zstaff_flex=False, to_blind=False,
                               to_deaf=False)
        client.send_ooc_others(ybnd, in_area=area, is_zstaff_flex=False, to_blind=True,
                               to_deaf=False)
        client.send_ooc_others(nbyd, in_area=area, is_zstaff_flex=False, to_blind=False,
                               to_deaf=True)
        # Blind and deaf get nothing

    def notify_others_blood(self, client, area, char, status='stay', send_to_staff=True):
        # Assume client's bleeding status is worth announcing (for example, it changed or lights on)
        # If bleeding, send reminder, and notify everyone in the area if not sneaking
        # (otherwise, just send vague message).
        others_bleeding = len([c for c in area.clients if c.is_bleeding and c != client])

        if client.is_bleeding and (status == 'stay' or status == 'arrived'):
            discriminant = (others_bleeding > 0) # Check if someone was bleeding already

            dsh = {True: 'You start hearing more drops of blood.',
                   False: 'You faintly start hearing drops of blood.'}
            dshs = {True: 'You start hearing and smelling more drops of blood.',
                    False: 'You faintly start hearing and smelling drops of blood.'}
            dss = {True: 'You start smelling more blood.',
                   False: 'You faintly start smelling blood.'}

            vis_status = 'now'
        elif ((client.is_bleeding and status == 'left')
              or (not client.is_bleeding and status == 'stay')):
            discriminant = (others_bleeding == 0) # Check if no one else in area was bleeding
            dsh = {True: 'You stop hearing drops of blood.',
                   False: 'You start hearing less drops of blood.'}
            dshs = {True: 'You stop hearing and smelling drops of blood.',
                    False: 'You start hearing and smelling less drops of blood.'}
            dss = {True: 'You stop smelling blood.',
                   False: 'You start smelling less blood.'}

            vis_status = 'no longer'
        else:
            # Case client is not bleeding and status is left or arrived (or anything but 'stay')
            # Boring cases for which the function should not be called
            raise KeyError('Invalid call of notify_others_blood with client {}. Bleeding: {}.'
                           'Status: {}'.format(client, client.is_bleeding, status))

        h_mes = dsh[discriminant] # hearing message
        s_mes = dss[discriminant] # smelling message
        hs_mes = dshs[discriminant] # hearing and smelling message
        ybyd = hs_mes
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

        if client.is_visible and area.lights:
            norm = 'You see {} {} bleeding.'.format(char, connector)
            ybnd = h_mes
            nbyd = norm
            staff = norm
        elif not client.is_visible and area.lights:
            norm = h_mes
            ybnd = hs_mes
            nbyd = s_mes
            staff = '(X) {} {} bleeding and sneaking.'.format(char, pconnector)
        elif client.is_visible and not area.lights:
            norm = hs_mes
            ybnd = hs_mes
            nbyd = s_mes
            staff = '(X) {} {} bleeding.'.format(char, pconnector)
        elif not client.is_visible and not area.lights:
            norm = hs_mes
            ybnd = hs_mes
            nbyd = s_mes
            staff = ('(X) {} {} bleeding and sneaking.'.format(char, pconnector))

        staff = staff.replace('no longer bleeding and sneaking.',
                              'no longer bleeding, but is still sneaking.') # Ugly

        client.send_ooc_others(norm, is_zstaff_flex=False, in_area=area, to_blind=False,
                               to_deaf=False)
        client.send_ooc_others(ybnd, is_zstaff_flex=False, in_area=area, to_blind=True,
                               to_deaf=False)
        client.send_ooc_others(nbyd, is_zstaff_flex=False, in_area=area, to_blind=False,
                               to_deaf=True)
        client.send_ooc_others(ybyd, is_zstaff_flex=False, in_area=area, to_blind=True,
                               to_deaf=True)
        if send_to_staff:
            client.send_ooc_others(staff, is_zstaff_flex=True, in_area=area)

    def notify_others_status(self, client, area, name, status='stay'):
        # Assume client's special status is worth announcing
        # If client has custom status, send reminder in OOC to everyone but those not staff,
        # blind and deaf simultaneously.

        norm_mes =  f'You note something about {name} {{}}'
        vague_mes = 'You think there is something odd about someone'
        staff_mes = f'(X) {name} [{client.id}] {{}} and has a custom status: {client.status}'

        if status == 'stay':
            norm_mes = norm_mes.format(' who was already here')
            vague_mes += ' who was already here.'
            staff_mes = staff_mes.format('was already here{}')
        elif status == 'arrived':
            norm_mes = norm_mes.format(' who has just arrived')
            vague_mes += ' who has just arrived.'
            staff_mes = staff_mes.format('has just arrived{}')
        else:
            # Case status is left or anything else
            # Boring cases for which the function should not be called
            raise KeyError('Invalid call of notify_others_status with client {}. Player status: {}.'
                           'Status: {}'.format(client, client.status, status))

        if client.is_visible and area.lights:
            norm = norm_mes
            ybnd = vague_mes
            nbyd = norm_mes
            staff = staff_mes.format('')
        elif not client.is_visible and area.lights:
            norm = vague_mes
            ybnd = vague_mes
            nbyd = vague_mes
            staff = staff_mes.format(' while sneaking')
        elif client.is_visible and not area.lights:
            norm = vague_mes
            ybnd = vague_mes
            nbyd = vague_mes
            staff = staff_mes.format('')
        else:
            norm = vague_mes
            ybnd = vague_mes
            nbyd = vague_mes
            staff = staff_mes.format(' while sneaking')

        client.send_ooc_others(norm, is_zstaff_flex=False, in_area=area, to_blind=False,
                               to_deaf=False)
        client.send_ooc_others(ybnd, is_zstaff_flex=False, in_area=area, to_blind=True,
                               to_deaf=False)
        client.send_ooc_others(nbyd, is_zstaff_flex=False, in_area=area, to_blind=False,
                               to_deaf=True)
        client.send_ooc_others(staff, is_zstaff_flex=True, in_area=area)

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

        client = self.client
        old_area = client.area
        found_something = False

        if not override_all:
            # All the code that could raise errors goes here

            # If player is in a party, do special method instead of this
            if from_party:
                client.server.party_manager.move_party(client.party, client, area)
                return

            # It also returns the character name that the player ended up, if it changed.
            if not ignore_checks:
                new_char_id, mes = client.check_change_area(area,
                                                            override_passages=override_passages,
                                                            override_effects=override_effects,
                                                            more_unavail_chars=more_unavail_chars)
            else:
                if change_to:
                    new_char_id, mes = change_to, list()
                else:
                    new_char_id, mes = client.char_id, list()

            # Code after this line assumes that the area change will be successful
            # (but has not yet been performed)
            client.new_area = area

            # Send client messages that could have been generated during the change area check
            for message in mes:
                client.send_ooc(message)

            # Perform the character switch if new area has a player with the current char
            # or the char is restricted there.
            old_char = client.get_char_name()
            old_dname = client.displayname
            if new_char_id != client.char_id:
                client.change_character(new_char_id, target_area=area, announce_zwatch=False)
                new_char = client.get_char_name()
                if old_char in area.restricted_chars:
                    client.send_ooc('Your character was restricted in your new area, switched '
                                    'to `{}`.'.format(new_char))
                    client.send_ooc_others('(X) Client {} had their character changed from `{}` to '
                                           '`{}` in your zone as their old character was '
                                           'restricted in their new area ({}).'
                                           .format(client.id, old_char, new_char, area.id),
                                           is_zstaff=area)
                else:
                    client.send_ooc('Your character was taken in your new area, switched to `{}`.'
                                    .format(client.get_char_name()))
                    client.send_ooc_others('(X) Client {} had their character changed from `{}` to '
                                           '`{}` in your zone as their old character was '
                                           'taken in their new area ({}).'
                                           .format(client.id, old_char, new_char, area.id),
                                           is_zstaff=area)

            if not ignore_notifications:
                client.send_ooc('Changed area to {}.[{}]'.format(area.name, area.status))
                logger.log_server('[{}]Changed area from {} ({}) to {} ({}).'
                                  .format(client.get_char_name(), old_area.name, old_area.id,
                                          area.name, area.id), client)
                #logger.log_rp('[{}]Changed area from {} ({}) to {} ({}).'
                #              .format(client.get_char_name(), old_area.name, old_area.id,
                #                      old_area.name, old_area.id), client)

                found_something = client.notify_change_area(area, old_dname,
                                                            ignore_bleeding=ignore_bleeding)

                old_area.publisher.publish('area_client_left', {
                    'client': client,
                    'new_area': area,
                    'old_displayname': old_dname,
                    'ignore_bleeding': ignore_bleeding,
                    })
                area.publisher.publish('area_client_entered', {
                    'client': client,
                    'old_area': old_area,
                    'old_displayname': old_dname,
                    'ignore_bleeding': ignore_bleeding,
                    })

        old_area.remove_client(client)
        client.area = area
        client.new_area = area  # Update again, as the above if may not have run
        area.new_client(client)

        client.send_health(side=1, health=client.area.hp_def)
        client.send_health(side=2, health=client.area.hp_pro)
        if client.is_blind:
            client.send_background(name=client.server.config['blackout_background'])
        else:
            client.send_background(name=client.area.background)
        client.send_evidence_list()
        client.send_ic_blankpost()

        if client.followedby and not ignore_followers and not override_all:
            for c in client.followedby:
                c.follow_area(area)

        if found_something:
            client.send_ic_attention()

        client.reload_music_list() # Update music list to include new area's reachable areas
        # If new area has lurk callout timer, reset it to that, provided it makes sense
        client.check_lurk()
        client.server.tasker.create_task(client, ['as_afk_kick', area.afk_delay, area.afk_sendto])
        # Try and restart handicap if needed
        try:
            _, length, name, announce_if_over = client.server.tasker.get_task_args(client,
                                                                                   ['as_handicap'])
        except (ValueError, KeyError):
            pass
        else:
            client.server.tasker.create_task(client,
                                             ['as_handicap', time.time(), length, name,
                                              announce_if_over])

        # For old area, check if there are no remaining clients, and if so, cancel any existing
        # lurk callout timer that may have been imposed on the area
        if not old_area.clients and old_area.lurk_length > 0:
            old_area.lurk_length = 0
            mes = ('(X) The lurk callout timer in area {} has been cancelled as there is no one '
                   'left there.'.format(old_area.name))
            client.send_ooc(mes, is_zstaff_flex=old_area)
            client.send_ooc_others(mes, is_zstaff_flex=old_area)

        if area.id not in client.remembered_locked_passages:
            client.remembered_locked_passages[area.id] = set()
