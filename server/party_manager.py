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

from server.exceptions import PartyError

class PartyManager:
    class Party:
        def __init__(self, server, pid, area, playerlimit, leader):
            self.server = server
            self.pid = pid
            self.area = area
            self.playerlimit = playerlimit
            self.leader = leader

            self.members = set()

        def is_member(self, member):
            return member in self.members

        def add_member(self, member):
            if self.is_member(member):
                raise PartyError('The player is already part of this party.')
            if self.playerlimit and len(self.members) == self.playerlimit:
                raise PartyError('The party is full.')
            if member.party:
                raise PartyError('The player is part of another party.')

            self.members.add(member)
            member.party = self

        def remove_member(self, member):
            if not self.is_member(member):
                raise PartyError('The player is not part of this party.')

            self.members.remove(member)
            member.party = None

            # Check if empty party and if so, disband it
            if not self.members:
                self.server.client_manager.disband_party(self)
            # Otherwise, check if the manager left, and if so, choose a new one
            elif member == self.leader:
                new_leader = self.get_random_member()
                self.set_leader(new_leader)

        def get_members(self):
            if self.leader:
                return self.members.copy()-self.leader, self.leader
            return self.members.copy(), None

        def get_random_member(self):
            return random.choice(tuple(self.members))

        def set_leader(self, new_leader):
            if not self.is_member(new_leader):
                raise PartyError('The player is not part of this party.')
            self.leader = new_leader

        def remove_leader(self):
            self.leader = None

        def get_details(self):
            return self.area, self.playerlimit, self.leader

    def __init__(self, server):
        self.server = server
        self.parties = dict()
        self.pid_length = 5

    def new_party(self, creator, playerlimit=None, has_leader=True, add_creator=True):
        if creator.party:
            raise PartyError('The player is part of another party.')

        area = creator.area
        leader = creator if has_leader else None
        # Check if there are any party slots remaining
        if len(self.parties) == 10**self.pid_length - 10**(self.pid_length-1) + 1:
            raise PartyError('The server has reached its party limit.')

        # Generate a party ID
        while True:
            pid = random.randint(10**(self.pid_length-1), 10**self.pid_length)
            if pid not in self.parties:
                break

        party = self.Party(self.server, pid, area, playerlimit, leader)
        self.parties[pid] = party

        if add_creator:
            party.add_member(creator)

        return party

    def disband_party(self, party):
        pid = self.get_party_id(party)
        self.parties.remove(pid)
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
        elif isinstance(party, int):
            if party not in self.parties:
                raise PartyError('This party does not exist.')
            return party
        else:
            raise PartyError('Invalid party ID.')

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

        _, old_pl, old_leader = party.get_details()
        if old_leader and not party.is_member(old_leader):
            raise PartyError('Invalid party split: {} must be placed in the first party.'
                             .format(old_leader.id))
        if not members1 or not members2:
            raise PartyError('Invalid party split: One of the new parties would be empty.')

        self.disband_party(party)
        creator1 = old_leader if old_leader else random.choice(tuple(members1))
        creator2 = random.choice(tuple(members2))

        party1 = self.new_party(creator1, playerlimit=old_pl, has_leader=(old_leader is not None),
                                add_creator=False)
        party2 = self.new_party(creator2, playerlimit=old_pl, has_leader=(old_leader is not None),
                                add_creator=False)

        for member in members1:
            party1.add_member(member)
        for member in members2:
            party2.add_member(member)

