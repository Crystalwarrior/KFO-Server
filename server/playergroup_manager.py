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

"""
Module that contains the PlayerGroupManager class, which itself contains the PlayerGroup subclass.

Player groups are groups of players (called members) with an ID, where some players (possibly none)
are leaders. Each player group may have a member limit (beyond which no new players may be added),
may require that it never loses all its members (or else may be automatically deleted, but may
start with no members) and may require that if it has at least one member, then that there is at
least one leader (or else one is automatically chosen between all members).

Each player group is managed by a player group manager. A player cannot be member of two or more
groups managed by the same manager simultaneously. Each manager may have a player group limit
(beyond which it will not manage any more groups).
"""

import random

from server.exceptions import PlayerGroupError

class PlayerGroupManager:
    """
    A mutable data type for a manager for the player groups in a server.
    Contains the player group object definition, as well as the server's player group list.

    Attributes
    ----------
    _server : TsuserverDR
        Server the player group manager belongs to.
    _player_to_group : dict of ClientManager.Client to PlayerGroupManager.PlayerGroup
        Mapping of players to the player group managed by this manager they belong to.
    _id_to_group : dict of str to PlayerGroupManager.PlayerGroup
        Mapping of player group IDs to player groups that this manager manages.
    _playergroup_limit : int or None
        If an int, it is the maximum number of player groups this manager supports. If None, the
        manager may manage an arbitrary number of groups.

    Invariants
    ----------
    1. If `self._playergroup_limit` is an int, then `len(self._playergroups) <=
       self._playergroup_limit`.
    2. For every player group `(playergroup_id, playergroup)` in `self._id_to_group.items()`
        a. `playergroup._manager = self`.
        b. `playergroup._playergroup_id = playergroup_id`.
    3. For every pair of distinct player groups `group1` and `group2` in `self._playergroups`:
        a. `group1._playergroup_id != group2._playergroup_id`.
        b. `group1._members` and `group2._members` are disjoint.
    4. `self._player_to_group.values()` is a subset of `self._id_to_group.values()`.
    5. For every player `player` in `self._player_to_group.keys()`, it belongs to the group
       `self._player_to_group[player]`.

    """

    class PlayerGroup:
        """
        A mutable data type for player groups.
        Player groups are groups of players (called members), where some of them (possibly none)
        are leaders.

        Attributes
        ----------
        _server : TsuserverDR
            Server the player group belongs to.
        _manager : PlayerGroupManager
            Manager for this player group.
        _playergroup_id : str
            Identifier for this player group.
        _member_limit : int or None.
            If an int, it is the maximum number of players the group supports. If None, the group
            may have an arbitrary number of players.
        _members : set of ClientManager.Client
            Members of the player group.
        _leaders : set of ClientManager.Client
            Leaders of the player group.
        _require_members : bool
            If True, the group will disassemble automatically if it loses all its members (but it
            may start with no members).
        _require_leaders : bool
            If True and the group has no leaders but at least one member, it will randomly choose
            one member to be a leader.

        Invariants
        ----------
        1. `self` is in `self._manager._id_to_group.values()`.
        2. For every player `player` in `self._members`,
           `self._manager._player_to_group[player] == self`
        3. If `self._member_limit` is not None, then `len(self._members) <= member_limit`.
        4. For every player in `self._leaders`, they also belong in `self._members`.
        5. If `len(self._members) >= 1`, then `self._ever_had_members == True`.
        6. If `self._require_members` is True, then `len(self._members) >= 1`.
        7. If `self._require_leaders` is True and `len(self._members) >= 1`, then
           `len(self._leaders) >= 1`.

        """

        def __init__(self, server, manager, playergroup_id, member_limit=None, members=None,
                     leaders=None, require_members=True, require_leaders=True):
            """
            Create a new player group.

            Parameters
            ----------
            server : TsuserverDR
                Server the player group belongs to.
            manager : PlayerGroupManager
                Manager for this player group.
            playergroup_id : str
                Identifier of the player group.
            member_limit : int, optional.
                Maximum number of players the group supports. Defaults to None (no limit).
            require_members : bool, optional
                If True, if at any point the group has no members left, the group will
                automatically be disassembled. If False, no such automatic deletion will happen.
                Defaults to True.
            require_leaders : bool, optional
                If True, if at any point the group has no leaders left, the group will choose a
                leader among any remaining members left; if no members are left, the next member
                added will be made leader. If False, no such automatic assignment will happen.
                Defaults to True.

            Raises
            ------
            PlayerGroupError.GroupIsEmptyError
                If the group has no members but `require_members` is True.
            PlayerGroupError.PlayerAlreadyMemberError
                If any player in the group is part of another group managed by this manager.

            """

            self._server = server
            self._manager = manager
            self._playergroup_id = playergroup_id
            self._member_limit = member_limit
            self._require_members = require_members
            self._require_leaders = require_leaders

            self._members = set()
            self._leaders = set()
            self._ever_had_members = False

            self._manager._check_structure()

        def get_id(self):
            """
            Return the ID of this player group.

            Returns
            -------
            str
                The ID.

            """

            return self._playergroup_id

        def get_members(self, cond=None):
            """
            Return (a shallow copy of) the set of members of this player group that satisfy a condition if given.

            Parameters
            ----------
            cond : types.LambdaType: ClientManager.Client -> bool, optional
                Condition that all members returned satisfy. Defaults to None (no checked conditions).

            Returns
            -------
            set of ClientManager.Client
                The (filtered) members of this player group.

            """

            if cond is None:
                cond = lambda c: True

            filtered_members = {member for member in self._members if cond(member)}
            return filtered_members

        def is_member(self, player):
            """
            Decide if a player is a member of the player group.

            Parameters
            ----------
            player : ClientManager.Client
                Player to test.

            Returns
            -------
            bool
                True if the player is a member, False otherwise.

            """

            return player in self._members

        def add_member(self, player):
            """
            Make a player a member of the player group. By default this player will not be a
            leader.

            Parameters
            ----------
            player : ClientManager.Client
                Player to add to the player group.

            Raises
            ------
            PlayerGroupError.PlayerAlreadyMemberError
                If the player to add is already a member of the player group.
            PlayerGroupError.PlayerInAnotherGroupError
                If the player is already in another group managed by this manager.

            """

            if player in self._members:
                raise PlayerGroupError.PlayerAlreadyMemberError
            if player in self._manager._player_to_group:
                raise PlayerGroupError.PlayerInAnotherGroupError
            if self._member_limit is not None and len(self._members) >= self._member_limit:
                raise PlayerGroupError.GroupIsFullError

            self._ever_had_members = True
            self._members.add(player)
            self._manager._player_to_group[player] = self
            self._choose_leader_if_needed()

            self._manager._check_structure()

        def remove_member(self, player):
            """
            Make a player be no longer a member of this player group.

            Parameters
            ----------
            player : ClientManager.Client
                Player to remove.

            Raises
            ------
            PlayerGroupError.PlayerNotMemberError
                If the player to remove is already not a member of this group.

            """

            if player not in self._members:
                raise PlayerGroupError.PlayerNotMemberError

            self._members.remove(player)
            self._leaders.discard(player)
            self._manager._player_to_group.pop(player)

            # Check updated leadership requirement
            self._choose_leader_if_needed()
            # Check if no members, and disassemble if appropriate
            if self._require_members and not self._members:
                self._manager.disassemble_group(self)

            self._manager._check_structure()

        def get_leaders(self, cond=None):
            """
            Return (a shallow copy of) the set of leaders of this player group that satisfy a condition if given.

            Parameters
            ----------
            cond : types.LambdaType: ClientManager.Client -> bool, optional
                Condition that all leaders returned satisfy. Defaults to None (no checked conditions).

            Returns
            -------
            set of ClientManager.Client
                The (filtered) leaders of this player group.

            """

            if cond is None:
                cond = lambda c: True

            filtered_leaders = {leader for leader in self._leaders if cond(leader)}
            return filtered_leaders

        def is_leader(self, player):
            """
            Decide if a player is a leader of the player group.

            Parameters
            ----------
            player : ClientManager.Client
                Player to test.

            Raises
            ------
            PlayerGroupError.PlayerNotMemberError
                If the player to promote is not a member of this group.

            Returns
            -------
            bool
                True if the player is a leader, False otherwise.

            """

            if player not in self._members:
                raise PlayerGroupError.PlayerNotMemberError

            return player in self._leaders

        def promote_leader(self, player):
            """
            Set a member as leader of this group.

            Parameters
            ----------
            player : ClientManager.Client
                Player to promote to leader.

            Raises
            ------
            PlayerGroupError.PlayerNotMemberError
                If the player to promote is not a member of this group.

            PlayerGroupError.PlayerAlreadyLeaderError
                If the player to promote is already a leader of this group.

            """

            if player not in self._members:
                raise PlayerGroupError.PlayerNotMemberError
            if player in self._leaders:
                raise PlayerGroupError.PlayerAlreadyLeaderError

            self._leaders.add(player)
            self._manager._check_structure()

        def demote_leader(self, player):
            """
            Make a member no longer leader of this group.

            Parameters
            ----------
            player : ClientManager.Client
                Player to make no longer leader.

            Raises
            ------
            PlayerGroupError.PlayerNotMemberError
                If the player to promote is not a member of this group.

            PlayerGroupError.PlayerNotLeaderError
                If the player to promote is already not a leader of this group.

            """

            if player not in self._members:
                raise PlayerGroupError.PlayerNotMemberError
            if player not in self._leaders:
                raise PlayerGroupError.PlayerNotLeaderError

            self._leaders.remove(player)
            # Check leadership requirement
            self._choose_leader_if_needed()
            self._manager._check_structure()

        def _choose_leader_if_needed(self):
            """
            If the player group requires that the group always have a leader if there is at least
            one member, one leader will randomly be chosen among all members. If this condition is
            already true, no new leaders are chosen.
            """

            if not self._require_leaders:
                return
            if self._leaders:
                return
            if not self._members:
                return

            new_leader = random.choice(list(self.get_members()))
            self.promote_leader(new_leader)

        def _check_structure(self):
            """
            Assert that all invariants specified in the class description are maintained.

            Raises
            ------
            AssertionError
                If any of the invariants are not maintained.

            """

            # 1.
            err = (f'For group {self._playergroup_id} that claims that it is managed by manager '
                   f'{self._manager}, expected that it recognized that it managed it, but found it '
                   f'did not. || {self}')
            assert self in self._manager._id_to_group.values(), err

            # 2.
            for player in self._members:
                err = (f'For group {self._playergroup_id}, expected that its member {player} is '
                       f'properly recognized in the player to group mapping of the manager of the '
                       f'group {self._manager}, but found that was not the case. || {self}')
                assert (player in self._manager._player_to_group.keys()
                        and self._manager._player_to_group[player] == self), err

            # 3.
            if self._member_limit is not None:
                err = (f'For group {self._playergroup_id}, expected that there were at most '
                       f'{self._member_limit} members, but found it had {len(self._members)} '
                       f'members. || {self}')
                assert len(self._members) <= self._member_limit, err

            # 4.
            for leader in self._leaders:
                err = (f'For group {self._playergroup_id}, expected that leader {leader} was a '
                       f'member of it too, but found it was not. || {self}')
                assert leader in self._members, err

            # 5.
            if self._members:
                err = (f'For group {self._playergroup_id}, expected it knew it ever had some '
                       f'members, but found it did not. || {self}')
                assert self._ever_had_members, err

            # 6.
            if self._require_members and self._ever_had_members:
                err = (f'For group {self._playergroup_id}, expected that it was automatically '
                       f'deleted for losing all its members, but found it was not. || {self}')
                assert self._members, err

            # 7.
            if self._require_leaders:
                err = (f'For group {self._playergroup_id} with some members, expected that there '
                       f'was a leader, but found it had no leaders. || {self}')
                assert not self._members or self._leaders, err

        def __repr__(self):
            """
            Return a printable representation of this player group.

            Returns
            -------
            str
                Printable representation.

            """

            return (f"PlayerGroupManager.PlayerGroup(server, manager, '{self._playergroup_id}', "
                    f"member_limit={self._member_limit}, members={self._members}, "
                    f"leaders={self._leaders}, require_members={self._require_members}, "
                    f"require_leaders={self._require_leaders})")

    def __init__(self, server, playergroup_limit=None):
        """
        Create a player group manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this player group manager belongs to.
        playergroup_limit : int, optional
            The maximum number of groups this manager can handle. The default is None.

        """

        self._server = server
        self._playergroup_limit = playergroup_limit
        self._id_to_group = dict()
        self._player_to_group = dict()

        self._check_structure()

    def assemble_group(self, creator=None, member_limit=None, require_members=True,
                       require_leaders=True):
        """
        Create a new player group managed by this manager.

        Parameters
        ----------
        creator : ClientManager.Client, optional
            The player who created this group. If set, they will also be added to the group if
            possible. The default is None.
        member_limit : int, optional
            The maximum number of players the group may have. The default is None (no limit).
        require_members : bool, optional
            If True, if at any point the group has no members left, the group will automatically
            be disassembled. If False, no such automatic deletion will happen. The default is True.
        require_leaders : bool, optional
            If True, if at any point the group has no leaders left, the group will choose a leader
            among any remaining members left; if no members are left, the next member added will
            be made leader. If False, no such automatic assignment will happen. The default is
            True.

        Raises
        ------
        PlayerGroupError.PlayerInAnotherGroupError
            If `creator` is not None and already part of a group managed by this manager.

        Returns
        -------
        PlayerGroup
            The created player group.

        """

        if self._playergroup_limit is not None:
            if len(self._id_to_group) >= self._playergroup_limit:
                raise PlayerGroupError.ManagerTooManyGroupsError
        if creator and creator in self._player_to_group.keys():
            raise PlayerGroupError.PlayerInAnotherGroupError

        # Generate a playergroup ID and the new group
        playergroup_id = self.make_new_group_id()
        playergroup = self.PlayerGroup(self._server, self, playergroup_id,
                                       member_limit=member_limit,
                                       require_members=require_members,
                                       require_leaders=require_leaders)
        self._id_to_group[playergroup_id] = playergroup
        if creator:
            playergroup.add_member(creator)
        playergroup._choose_leader_if_needed()

        self._check_structure()
        return playergroup

    def disassemble_group(self, playergroup):
        """
        Disband a player group managed by this manager, so all its members no longer belong to any
        player group.

        Parameters
        ----------
        playergroup : PlayerGroup
            The player group to disband.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError
            If the manager does not manage the target player group

        Returns
        -------
        (str, set of ClientManager.Client)
            The ID and members of the playergroup that was disbanded.

        """

        playergroup_id = self.get_group_id(playergroup) # Assert player group is managed by manager
        self._id_to_group.pop(playergroup_id)
        for member in playergroup._members:
            self._player_to_group.pop(member)

        self._check_structure()
        return playergroup_id, playergroup._members.copy()

    def get_managed_groups(self):
        """
        Return (a shallow copy of) the groups this manager manages.

        Returns
        -------
        set of PlayerGroup
            Player groups this manager manages.

        """

        return set(self._id_to_group.values())

    def get_group_of_player(self, player):
        """
        Return the player group managed by this manager player `player` belongs to.

        Parameters
        ----------
        player : ClientManager.Client
            Player whose player group will be returned.

        Raises
        ------
        PlayerGroupError.PlayerInNoGroupError:
            If the player does not belong in any player group managed by this manager.

        Returns
        -------
        PlayerGroup
            Player group the player belongs to.

        """

        try:
            return self._id_to_group[player]
        except KeyError:
            raise PlayerGroupError.PlayerInNoGroupError

    def get_group(self, playergroup_tag):
        """
        If `playergroup_tag` is a player group managed by this manager, return it.
        If it is a string and the ID of a player group managed by this manager, return that.

        Parameters
        ----------
        playergroup_tag : PlayerGroup or str
            Player group this manager manages.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError:
            If `playergroup_tag` is a group this manager does not manage.
        PlayerGroupError.ManagerInvalidIDError:
            If `playergroup_tag` is a str and it is not the ID of a group this manager manages.

        Returns
        -------
        PlayerGroup
            The player group that matches the given tag.

        """

        # Case Player Group
        if isinstance(playergroup_tag, self.PlayerGroup):
            if playergroup_tag not in self._id_to_group.values():
                raise PlayerGroupError.ManagerDoesNotManageGroupError
            return playergroup_tag

        # Case Player Group ID
        if isinstance(playergroup_tag, str):
            try:
                return self._id_to_group[playergroup_tag]
            except KeyError:
                raise PlayerGroupError.ManagerInvalidIDError

        # Every other case
        raise PlayerGroupError.ManagerInvalidIDError

    def get_group_id(self, playergroup_tag):
        """
        If `playergroup_tag` is the ID of a group managed by this manager, return it.
        If it is a player group managed by this manager, return its ID.

        Parameters
        ----------
        playergroup_tag : PlayerGroup or str
            Player group this manager manages.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError:
            If `playergroup_tag` is a group this manager does not manage.
        PlayerGroupError.ManagerInvalidIDError:
            If `playergroup_tag` is a str and it is not the ID of a group this manager manages.

        Returns
        -------
        PlayerGroup
            The ID of the player group that matches the given tag.

        """

        # Case Player Group
        if isinstance(playergroup_tag, self.PlayerGroup):
            if playergroup_tag not in self._id_to_group.values():
                raise PlayerGroupError.ManagerDoesNotManageGroupError
            return playergroup_tag._playergroup_id

        # Case Player Group ID
        if isinstance(playergroup_tag, str):
            try:
                return self._id_to_group[playergroup_tag]._playergroup_id
            except KeyError:
                raise PlayerGroupError.ManagerInvalidIDError

        # Every other case
        raise PlayerGroupError.ManagerInvalidIDError

    def make_new_group_id(self):
        """
        Generate a player group ID that no other player group managed by this manager has.

        Raises
        ------
        PlayerGroupError.ManagerTooManyGroupsError
            If the manager is already managing its maximum number of groups.

        Returns
        -------
        str
            A unique player group ID.

        """

        group_number = 0
        while self._playergroup_limit is None or group_number < self._playergroup_limit:
            new_group_id = "pg{}".format(group_number)
            if new_group_id not in self._id_to_group.keys():
                return new_group_id
            group_number += 1
        else:
            raise PlayerGroupError.ManagerTooManyGroupsError

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        if self._playergroup_limit is not None:
            err = (f'For player group manager {self}, expected that it managed at most '
                   f'{self._playergroup_limit} player groups, but found it managed '
                   f'{len(self._id_to_groups.keys())} player groups. || {self}')
            assert len(self._members) <= self._member_limit, err

        # 2.
        for (playergroup_id, playergroup) in self._id_to_group.items():
            # 2a.
            err = (f'For player group manager {self}, expected that its managed group '
                   f'{playergroup} recognized that it was managed by it, but found it did not. '
                   f'|| {self}')
            assert playergroup._manager == self, err

            # 2b.
            err = (f'For player group manager {self}, expected that player group {playergroup} '
                   f'that appears in the ID to player group mapping has the same ID as in the '
                   f'mapping, but found it did not. || {self}')
            assert playergroup._playergroup_id == playergroup_id, err

        # 3.
        for playergroup1 in self._id_to_group.values():
            for playergroup2 in self._id_to_group.values():
                if playergroup1 == playergroup2:
                    continue

                # 3a.
                err = (f'For player group manager {self}, expected that its two managed groups '
                       f'{playergroup1}, {playergroup2} had unique player group IDS, but found '
                       f'they did not. || {self}')
                assert playergroup1._playergroup_id != playergroup2._playergroup_id, err

                # 3b.
                err = (f'For player group manager {self}, expected that its two managed groups '
                       f'{playergroup1}, {playergroup2} had disjoint member sets, but found they '
                       f'did not. || {self}')
                assert not playergroup1._members.intersection(playergroup2._members), err

        # 4.
        for playergroup in self._player_to_group.values():
            err = (f'For player group manager {self}, expected that player group {playergroup} '
                   f'that appears in the player to player group mapping also appears in the player '
                   f'group ID to player group mapping, but found it did not. || {self}')
            assert playergroup in self._id_to_group.values(), err

        # 5.
        for (player, playergroup) in self._player_to_group.items():
            err = (f'For player group manager {self}, expected that player {player} in the player '
                   f'to group mapping be a member of its associated group {playergroup}, but found '
                   f'that was not the case. || {self}')
            assert player in playergroup._members, err

        # Last.
        for playergroup in self._id_to_group.values():
            playergroup._check_structure()
