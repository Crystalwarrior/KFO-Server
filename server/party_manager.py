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

import random

from server.exceptions import AreaError, ClientError, PartyError

class PartyManager:
    class Party:
        #tc=True means the target called the party function to do something on themselves
        def __init__(self, server, pid, area, player_limit, leaders):
            self.server = server
            self.pid = pid
            self.area = area
            self.player_limit = player_limit
            self.leaders = leaders
            self.members = set()
            self.invite_list = set()

        def is_member(self, member, tc=False):
            return member in self.members

        def add_member(self, member, tc=False):
            if self.is_member(member):
                raise PartyError(self._f('The player is already part of this party.', tc=tc))
            if self.player_limit and len(self.members) == self.player_limit:
                raise PartyError(self._f('The party is full.', tc=tc))
            if member.party:
                raise PartyError(self._f('The player is part of another party.', tc=tc))
            if not self.is_invited(member):
                raise PartyError(self._f('The player is not part of the party invite list.', tc=tc))

            self.members.add(member)
            self.invite_list.remove(member)
            member.party = self

        def remove_member(self, member, tc=False):
            if not self.is_member(member):
                raise PartyError(self._f('The player is not part of this party.', tc=tc))

            self.members.remove(member)
            member.party = None

            # Check if empty party and if so, disband it
            if not self.members:
                self.server.party_manager.disband_party(self)
            # Otherwise, check if the manager left, and if so, choose a new one
            elif not self.leaders:
                new_leader = self.get_random_member()
                self.add_leader(new_leader)

        def get_members(self, tc=False, uninclude=None):
            if uninclude is None:
                uninclude = set()

            return self.members - uninclude

        def get_members_leaders(self, tc=False, uninclude=None):
            if uninclude is None:
                uninclude = set()

            members = self.members - uninclude
            leaders = self.leaders - uninclude

            return members - leaders, leaders

        def get_random_member(self, cond=None):
            if cond is None:
                cond = lambda c: True

            filtered_members = [x for x in self.members if cond(x)]
            return random.choice(filtered_members)

        def get_id(self, tc=False):
            return self.pid

        def add_invite(self, member, tc=False):
            if member in self.invite_list:
                raise PartyError('This player is already in the party invite list.')
            if member in self.members:
                raise PartyError('This player is already a member of this party.')
            self.invite_list.add(member)

        def remove_invite(self, member, tc=False):
            if member not in self.invite_list:
                raise PartyError('This player is not in the party invite list.')
            self.invite_list.remove(member)

        def is_invited(self, member, tc=False):
            return member in self.invite_list

        def add_leader(self, new_leader, tc=False):
            if not self.is_member(new_leader):
                raise PartyError(self._f('The player is not part of the party.', tc=tc))
            if new_leader in self.leaders:
                raise PartyError(self._f('The player is already a leader of the party.', tc=tc))

            self.leaders.add(new_leader)

        def remove_leader(self, leader, tc=False):
            if not self.is_member(leader):
                raise PartyError(self._f('The player is not part of the party.', tc=tc))
            if leader not in self.leaders:
                raise PartyError(self._f('The player is not leader of the party.', tc=tc))

            self.leaders.remove(leader)

        def is_leader(self, member, tc=False):
            return member in self.leaders

        def get_leaders(self, tc=False, uninclude=None):
            if uninclude is None:
                uninclude = set()

            return self.leaders-uninclude

        def get_details(self, tc=False):
            return self.area, self.player_limit, self.leaders

        @staticmethod
        def _f(text, tc=False):
            if tc:
                text = text.replace('The player is', 'You are')
            return text

    def __init__(self, server):
        self.server = server
        self.parties = dict()
        self.pid_length = 5

    def new_party(self, creator, player_limit=None, has_leader=True, add_creator=True, tc=False):
        if creator.party and add_creator:
            raise PartyError(self._f('The player is part of another party.', tc=tc))

        area = creator.area
        leader = {creator} if has_leader and add_creator else set()
        # Check if there are any party slots remaining
        if len(self.parties) == 10**self.pid_length - 10**(self.pid_length-1) + 1:
            raise PartyError('The server has reached its party limit.')

        # Generate a party ID
        while True:
            pid = random.randint(10**(self.pid_length-1), 10**self.pid_length)
            if pid not in self.parties:
                break

        party = self.Party(self.server, pid, area, player_limit, leader)
        self.parties[pid] = party

        if add_creator:
            party.add_invite(creator)
            party.add_member(creator)

        return party

    def disband_party(self, party):
        pid = self.get_party_id(party)
        party = self.parties.pop(pid)
        for member in party.members:
            member.party = None
        return pid, party.members.copy()

    def get_party(self, party):
        pid = self.get_party_id(party)
        return self.parties[pid]

    def get_party_id(self, party):
        if isinstance(party, PartyManager.Party):
            if party.pid not in self.parties:
                raise PartyError('This party does not exist.')
            return party.pid
        if isinstance(party, str):
            if party.isdigit():
                if int(party) not in self.parties:
                    raise PartyError('This party does not exist.')
                return int(party)
        if isinstance(party, int):
            if party not in self.parties:
                raise PartyError('This party does not exist.')
            return party
        raise PartyError('Invalid party ID.')

    def move_party(self, party, initiator, new_area):
        ini_name = initiator.get_char_name() # Backup in case initiator's char changes.
        movers = self.check_move_party(party, initiator, new_area)
        moving, staying = movers[True], movers[False]

        if not moving and staying:
            raise PartyError('No one was able to move.')
        if moving and not staying:
            # Everyone moves case
            for (member, new_char) in moving.items():
                if member is initiator:
                    mes = 'You started moving your party.'
                else:
                    mes = '{} started moving your party.'.format(ini_name)
                member.send_host_message(mes)
                member.change_area(new_area, ignore_checks=True, change_to=new_char)
        else:
            # Some people move, some stay behind case
            """
            If initiator is not sneaking
            1. Visible who moved
            2. Visible who stayed as they were not allowed
            3. Sneaked who stayed
            Party ID is assigned to the formed party that contains initiator

            If initiator is sneaking
            1. Sneaked who moved
            2. Sneaked who stayed as they were not allowed
            3. Visible who stayed (keeps party ID)
            """
            split = list()
            s = lambda x: set(split[x].keys())

            if initiator.is_visible:
                split.append({c: i for c, i in moving.items()}) # Guaranteed non-empty
                split.append({c: i for c, i in staying.items() if c.is_visible})
                split.append({c: i for c, i in staying.items() if not c.is_visible})

                og_party_id = 1 if initiator in staying else 0

                # Note that split[og_party_id] is guaranteed to be non-empty
                # and so is split[1-og_party_id].union(split[2])
                # Just think about the cases og_party_id = 0 and og_party_id = 1 and
                # it will all make sense

                non_og_party = self.fork_party(party, s(og_party_id), s(1-og_party_id).union(s(2)))
                if split[1-og_party_id] and split[2]:
                    self.fork_party(non_og_party, s(1-og_party_id), s(2))

                for (member, new_char) in split[0].items():
                    if initiator == member:
                        msg = 'You started moving your party.'
                    else:
                        msg = '{} started moving your party.'.format(ini_name)
                    member.send_host_message(msg)
                    member.change_area(new_area, ignore_checks=True, change_to=new_char)
                for (member, _) in split[1].items():
                    if initiator == member:
                        msg = 'You started moving your party but you were unable to move.'
                    else:
                        msg = ('{} started moving your party but you were unable to move.'
                               .format(ini_name))
                    member.send_host_message(msg)
                for (member, _) in split[2].items():
                    msg = 'Your party started moving so you decided to break away from them.'
                    msg += (' The ones who were left behind formed a new party {}.'
                            .format(member.get_party().get_id()))
                    member.send_host_message(msg)

            else:
                # Case initiator is sneaking
                split.append({c: i for c, i in moving.items()}) # Guaranteed non-empty
                split.append({c: i for c, i in staying.items() if not c.is_visible})
                split.append({c: i for c, i in staying.items() if c.is_visible})

                og_party_id = 2 if split[2] else 1

                # Note that split[og_party_id] is guaranteed to be non-empty
                # and so is split[2-og_party_id].union(split[2])
                # Just think about the cases og_party_id = 0 and og_party_id = 1 and
                # it will all make sense

                non_og_party = self.fork_party(party, s(og_party_id), s(3-og_party_id).union(s(0)))
                if split[3-og_party_id] and split[0]:
                    self.fork_party(non_og_party, s(3-og_party_id), s(0))

                for (member, new_char) in split[0].items():
                    if initiator == member:
                        msg = 'You started moving the sneaked members of your party.'
                    else:
                        msg = '{} started moving the sneaked members of your party.'.format(ini_name)
                    member.send_host_message(msg)
                    member.change_area(new_area, ignore_checks=True, change_to=new_char)
                for (member, _) in split[1].items():
                    if initiator == member:
                        msg = ('You started moving the sneaked members of your party but you were '
                               'unable to move.')
                    else:
                        msg = ('{} started moving the sneaked members of your party but you were '
                               'unable to move.'.format(ini_name))
                    member.send_host_message(msg)
                for (member, _) in split[2].items():
                    # Deliberately empty, do not announce anything to these people
                    pass

    def check_move_party(self, party, initiator, new_area):
        """
        * If existing handicap has not expired.
        * If moving while sneaking to lobby/private area.
        * If target area has some lock player has no perms for.
        * If target area is unreachable from the current one.
        * If target area contains a character from the current party.
        * If character of member is restricted in the target area

        LIGHTS
        1. No one moves
        2. Should be no
        3. Party disbands
        4. No one moves
        5. Affected user switches
        6. Party disbands
        """
        new_chars = set()
        movers = {True: dict(), False: dict()}

        # Assumes that players will only attempt to move if their sneak status matches that of the
        # initiator.
        for member in party.members:
            error = None

            # Player will only attempt to move under any of these two conditions
            # * Player and initiator are not sneaking
            # * Player and initiator are both sneaking
            if initiator.is_visible:
                attempt_move = member.is_visible
            else:
                attempt_move = not initiator.is_visible

            if attempt_move:
                try:
                    is_restricted = (member.get_char_name() in new_area.restricted_chars)
                    if is_restricted and not member.is_staff():
                        error = AreaError('', code='ChArRestrictedChar')

                    new_char_id, _ = member.check_change_area(new_area, more_unavail_chars=new_chars)
                    new_chars.add(new_char_id)
                except (ClientError, AreaError) as ex:
                    error = ex
            else:
                new_char_id = member.char_id

            if error:
                if error.code in ['ChArHandicap', 'ChArSneakLobby', 'ChArSneakPrivate',
                                  'ChArUnreachable', 'ChrNoAvailableCharacters']:
                    member.send_host_message(error.message)
                    culprit = member.get_char_name() if member != initiator else 'yourself'
                    raise ClientError('Unable to move the party due to {}.'.format(culprit))

                if error.code in ['ChArLocked', 'ChArGMLocked', 'ChArModLocked',
                                  'ChArRestrictedChar', 'ChArInArea']:
                    movers[False][member] = new_char_id
                elif error.code is not None:
                    raise error
                else:
                    movers[True][member] = new_char_id
            else:
                movers[attempt_move][member] = new_char_id

        return movers

    def fork_party(self, party, remainers, leavers):
        # Put a Brexit joke here
        # Jerm70: Because we needed to split the Brexit vote to stop the damn plebs from leaving

        party = self.get_party(party) # Assert that it is a party
        common = remainers.intersection(leavers)
        if common:
            raise PartyError('Invalid party split: {} would belong in two parties.'
                             .format(', '.join([c.id for c in common])))
        orphaned = party.members - (remainers.union(leavers))
        if orphaned:
            raise PartyError('Invalid party split: {} would be left out of the parties.'
                             .format(', '.join([c.id for c in orphaned])))

        _, old_pl, old_leaders = party.get_details()
        if not remainers or not leavers:
            raise PartyError('Invalid party split: One of the new parties would be empty.')

        leave_creator = random.choice(tuple(leavers))

        leave_party = self.new_party(leave_creator, player_limit=old_pl,
                                     has_leader=(old_leaders is not None), add_creator=False)
        print(leavers)
        for member in leavers:
            party.remove_member(member)
            leave_party.add_invite(member)
            leave_party.add_member(member)
            if member in old_leaders:
                leave_party.add_leader(member)

        return leave_party

    def split_party(self, party, members1, members2):
        party = self.get_party(party) # Assert that it is a party
        common = members1.intersection(members2)
        if common:
            raise PartyError('Invalid party split: {} would belong in two parties.'
                             .format(', '.join([c.id for c in common])))
        orphaned = party.members - (members1.union(members2))
        if orphaned:
            raise PartyError('Invalid party split: {} would be left out of the parties.'
                             .format(', '.join([c.id for c in orphaned])))

        _, old_pl, old_leaders = party.get_details()
        if not members1 or not members2:
            raise PartyError('Invalid party split: One of the new parties would be empty.')

        self.disband_party(party)
        creator1 = random.choice(tuple(members1))
        creator2 = random.choice(tuple(members2))

        party1 = self.new_party(creator1, player_limit=old_pl, has_leader=(old_leaders is not None),
                                add_creator=False)
        party2 = self.new_party(creator2, player_limit=old_pl, has_leader=(old_leaders is not None),
                                add_creator=False)

        for member in members1:
            party1.add_invite(member)
            party1.add_member(member)
            if member in old_leaders:
                party1.add_leader(member)

        for member in members2:
            party2.add_invite(member)
            party2.add_member(member)
            if member in old_leaders:
                party2.add_leader(member)

    @staticmethod
    def _f(text, tc=False):
        if tc:
            text = text.replace('The player is', 'You are')
        return text
