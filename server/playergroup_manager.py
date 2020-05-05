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

Player groups are groups of users (called players) with an ID, where some players (possibly none)
are leaders. Each player group may have a player limit (beyond which no new players may be added),
may require that it never loses all its players (or else may be automatically deleted, but may
start with no players) and may require that if it has at least one player, then that there is at
least one leader (or else one is automatically chosen between all player).

Each player group is managed by a player group manager. A user cannot be a player of two or more
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
    _playergroup_limit : int or None
        If an int, it is the maximum number of player groups this manager supports. If None, the
        manager may manage an arbitrary number of groups.
    _playergroup_type : PlayerGroupManager.PlayerGroup
        The type of player groups this player group manager will create by default when ordered to
        create a new one.
    _user_to_group : dict of ClientManager.Client to PlayerGroupManager.PlayerGroup
        Mapping of users to the player group managed by this manager they belong to.
    _id_to_group : dict of str to PlayerGroupManager.PlayerGroup
        Mapping of player group IDs to player groups that this manager manages.

    Invariants
    ----------
    1. If `self._playergroup_limit` is an int, then `len(self._id_to_group) <=
       self._playergroup_limit`.
    2. For every player group `(playergroup_id, playergroup)` in `self._id_to_group.items()`
        a. `playergroup._manager = self`.
        b. `playergroup._playergroup_id = playergroup_id`.
    3. For every pair of distinct player groups `group1` and `group2` in `self._id_to_group`:
        a. `group1._playergroup_id != group2._playergroup_id`.
        b. `group1._players` and `group2._players` are disjoint.
    4. `self._user_to_group.values()` is a subset of `self._id_to_group.values()`.
    5. For every player `player` in `self._user_to_group.keys()`, it belongs to the group
       `self._user_to_group[player]`.

    """

    class PlayerGroup:
        """
        A mutable data type for player groups.
        Player groups are groups of users (called players), where some of them (possibly none)
        are leaders.

        Attributes
        ----------
        _server : TsuserverDR
            Server the player group belongs to.
        _manager : PlayerGroupManager
            Manager for this player group.
        _playergroup_id : str
            Identifier for this player group.
        _player_limit : int or None.
            If an int, it is the maximum number of players the group supports. If None, the group
            may have an arbitrary number of players.
        _players : set of ClientManager.Client
            Players of the player group.
        _leaders : set of ClientManager.Client
            Leaders of the player group.
        _invitations : set of clientManager.Client
            Users invited to (but not part of of) the player group.
        _require_players : bool
            If True, the group will disassemble automatically if it loses all its players (but it
            may start with no players).
        _require_leaders : bool
            If True and the group has no leaders but at least one player, it will randomly choose
            one player to be a leader.

        Invariants
        ----------
        1. `self` is in `self._manager._id_to_group.values()`.
        2. For every player `player` in `self._players`,
           `self._manager._user_to_group[player] == self`
        3. If `self._player_limit` is not None, then `len(self._players) <= player_limit`.
        4. For every player in `self._leaders`, they also belong in `self._players`.
        5. If `len(self._players) >= 1`, then `self._ever_had_players == True`.
        6. If `self._require_players` is True, then `len(self._players) >= 1`.
        7. If `self._require_leaders` is True and `len(self._players) >= 1`, then
           `len(self._leaders) >= 1`.
        8. `self._invitations` and `self._players` are disjoint sets.

        """

        def __init__(self, server, manager, playergroup_id, player_limit=None,
                     require_invitations=False, require_players=True, require_leaders=True):
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
            player_limit : int, optional.
                Maximum number of players the group supports. Defaults to None (no limit).
            require_invitation : bool, optional
                If True, players can only be added to the group if they were previously invited. If
                False, no checking for invitations is performed. Defaults to False.
            require_players : bool, optional
                If True, if at any point the group has no players left, the group will
                automatically be deleted. If False, no such automatic deletion will happen.
                Defaults to True.
            require_leaders : bool, optional
                If True, if at any point the group has no leaders left, the group will choose a
                leader among any remaining players left; if no players are left, the next player
                added will be made leader. If False, no such automatic assignment will happen.
                Defaults to True.

            """

            self._server = server
            self._manager = manager
            self._playergroup_id = playergroup_id
            self._player_limit = player_limit
            self._require_invitations = require_invitations
            self._require_players = require_players
            self._require_leaders = require_leaders

            self._players = set()
            self._leaders = set()
            self._invitations = set()
            self._ever_had_players = False

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

        def get_players(self, cond=None):
            """
            Return (a shallow copy of) the set of players of this player group that satisfy a
            condition if given.

            Parameters
            ----------
            cond : types.LambdaType: ClientManager.Client -> bool, optional
                Condition that all players returned satisfy. Defaults to None (no checked
                conditions).

            Returns
            -------
            set of ClientManager.Client
                The (filtered) players of this player group.

            """

            if cond is None:
                cond = lambda c: True

            filtered_players = {player for player in self._players if cond(player)}
            return filtered_players

        def is_player(self, user):
            """
            Decide if a user is a player of the player group.

            Parameters
            ----------
            user : ClientManager.Client
                User to test.

            Returns
            -------
            bool
                True if the user is a player, False otherwise.

            """

            return user in self._players

        def add_player(self, user):
            """
            Make a user a player of the player group. By default this player will not be a
            leader.

            Parameters
            ----------
            user : ClientManager.Client
                User to add to the player group.

            Raises
            ------
            PlayerGroupError.UserNotInvitedError
                If the group requires players be invited to be added and the user is not invited.
            PlayerGroupError.UserAlreadyPlayerError
                If the user to add is already a user of the player group.
            PlayerGroupError.UserInAnotherGroupError
                If the player is already in another group managed by this manager.
            PlayerGroupError.GroupIsFullError
                If the group reached its player limit.

            """

            if self._require_invitations and user not in self._invitations:
                raise PlayerGroupError.UserNotInvitedError
            if user in self._players:
                raise PlayerGroupError.UserAlreadyPlayerError
            if user in self._manager._user_to_group:
                raise PlayerGroupError.UserInAnotherGroupError
            if self._player_limit is not None and len(self._players) >= self._player_limit:
                raise PlayerGroupError.GroupIsFullError

            self._ever_had_players = True
            self._players.add(user)
            self._manager._user_to_group[user] = self
            if self._require_invitations:
                self._invitations.remove(user)

            self._choose_leader_if_needed()

            self._manager._check_structure()

        def remove_player(self, user):
            """
            Make a user be no longer a player of this player group.

            Parameters
            ----------
            user : ClientManager.Client
                User to remove.

            Raises
            ------
            PlayerGroupError.UserNotPlayerError
                If the user to remove is already not a player of this group.

            """

            if user not in self._players:
                raise PlayerGroupError.UserNotPlayerError

            self._players.remove(user)
            self._leaders.discard(user)
            self._manager._user_to_group.pop(user)

            # Check updated leadership requirement
            self._choose_leader_if_needed()
            # Check if no players, and disassemble if appropriate
            if self._require_players and not self._players:
                self._manager.delete_group(self)

            self._manager._check_structure()

        def get_invitations(self, cond=None):
            """
            Return (a shallow copy of) the set of invited users of this player group that satisfy
            a condition if given.

            Parameters
            ----------
            cond : types.LambdaType: ClientManager.Client -> bool, optional
                Condition that all invited users returned satisfy. Defaults to None (no checked
                conditions).

            Returns
            -------
            set of ClientManager.Client
                The (filtered) invited users of this player group.

            """

            if cond is None:
                cond = lambda c: True

            filtered_invited = {invited for invited in self._invitations if cond(invited)}
            return filtered_invited

        def is_invited(self, user):
            """
            Decide if a user is invited to the player group.

            Parameters
            ----------
            user : ClientManager.Client
                User to test.

            Raises
            ------
            PlayerGroupError.UserAlreadyPlayerError
                If the user is a player of this group.

            Returns
            -------
            bool
                True if the user is invited, False otherwise.

            """

            if user in self._players:
                raise PlayerGroupError.UserAlreadyPlayerError

            return user in self._invitations

        def add_invitation(self, user):
            """
            Mark a user as invited to this player group.

            Parameters
            ----------
            user : ClientManager.Client
                User to invite to the player group.

            Raises
            ------
            PlayerGroupError.GroupDoesNotTakeInvitationsError
                If the group does not require users be invited to the player group.
            PlayerGroupError.UserAlreadyInvitedError
                If the player to invite is already invited to the player group.
            PlayerGroupError.UserAlreadyPlayerError
                If the player to invite is already a player of the player group.

            """

            if not self._require_invitations: # By design check if invitations are required first
                raise PlayerGroupError.GroupDoesNotTakeInvitationsError
            if user in self._invitations:
                raise PlayerGroupError.UserAlreadyInvitedError
            if user in self._players:
                raise PlayerGroupError.UserAlreadyPlayerError

            self._invitations.add(user)

            self._manager._check_structure()

        def remove_invitation(self, user):
            """
            Mark a user as no longer invited to this player group (uninvite).

            Parameters
            ----------
            user : ClientManager.Client
                User to uninvite.

            Raises
            ------
            PlayerGroupError.GroupDoesNotTakeInvitationsError
                If the group does not require users be invited to the player group.
            PlayerGroupError.UserNotInvitedError
                If the user to uninvite is already not invited to this group.

            """

            if not self._require_invitations: # By design check if invitations are required first
                raise PlayerGroupError.GroupDoesNotTakeInvitationsError
            if user not in self._invitations:
                raise PlayerGroupError.UserNotInvitedError

            self._invitations.remove(user)

            self._manager._check_structure()

        def get_leaders(self, cond=None):
            """
            Return (a shallow copy of) the set of leaders of this player group that satisfy a
            condition if given.

            Parameters
            ----------
            cond : types.LambdaType: ClientManager.Client -> bool, optional
                Condition that all leaders returned satisfy. Defaults to None (no checked
                conditions).

            Returns
            -------
            set of ClientManager.Client
                The (filtered) leaders of this player group.

            """

            if cond is None:
                cond = lambda c: True

            filtered_leaders = {leader for leader in self._leaders if cond(leader)}
            return filtered_leaders

        def is_leader(self, user):
            """
            Decide if a user is a leader of the player group.

            Parameters
            ----------
            user : ClientManager.Client
                User to test.

            Raises
            ------
            PlayerGroupError.UserNotPlayerError
                If the player to test is not a player of this group.

            Returns
            -------
            bool
                True if the player is a user, False otherwise.

            """

            if user not in self._players:
                raise PlayerGroupError.UserNotPlayerError

            return user in self._leaders

        def add_leader(self, user):
            """
            Set a user as leader of this group (promote to leader).

            Parameters
            ----------
            user : ClientManager.Client
                Player to promote to leader.

            Raises
            ------
            PlayerGroupError.UserNotPlayerError
                If the player to promote is not a player of this group.
            PlayerGroupError.UserAlreadyLeaderError
                If the player to promote is already a leader of this group.

            """

            if user not in self._players:
                raise PlayerGroupError.UserNotPlayerError
            if user in self._leaders:
                raise PlayerGroupError.UserAlreadyLeaderError

            self._leaders.add(user)
            self._manager._check_structure()

        def remove_leader(self, user):
            """
            Make a user no longer leader of this group (demote).

            Parameters
            ----------
            user : ClientManager.Client
                User to demote.

            Raises
            ------
            PlayerGroupError.UserNotPlayerError
                If the player to demote is not a player of this group.
            PlayerGroupError.UserNotLeaderError
                If the player to demote is already not a leader of this group.

            """

            if user not in self._players:
                raise PlayerGroupError.UserNotPlayerError
            if user not in self._leaders:
                raise PlayerGroupError.UserNotLeaderError

            self._leaders.remove(user)
            # Check leadership requirement
            self._choose_leader_if_needed()
            self._manager._check_structure()

        def _choose_leader_if_needed(self):
            """
            If the player group requires that the group always have a leader if there is at least
            one player, one leader will randomly be chosen among all players. If this condition is
            already true, no new leaders are chosen.
            """

            if not self._require_leaders:
                return
            if self._leaders:
                return
            if not self._players:
                return

            new_leader = random.choice(list(self.get_players()))
            self.add_leader(new_leader)

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
            for player in self._players:
                err = (f'For group {self._playergroup_id}, expected that its player {player} is '
                       f'properly recognized in the player to group mapping of the manager of the '
                       f'group {self._manager}, but found that was not the case. || {self}')
                assert (player in self._manager._user_to_group.keys()
                        and self._manager._user_to_group[player] == self), err

            # 3.
            if self._player_limit is not None:
                err = (f'For group {self._playergroup_id}, expected that there were at most '
                       f'{self._player_limit} players, but found it had {len(self._players)} '
                       f'players. || {self}')
                assert len(self._players) <= self._player_limit, err

            # 4.
            for leader in self._leaders:
                err = (f'For group {self._playergroup_id}, expected that leader {leader} was a '
                       f'player of it too, but found it was not. || {self}')
                assert leader in self._players, err

            # 5.
            if self._players:
                err = (f'For group {self._playergroup_id}, expected it knew it ever had some '
                       f'players, but found it did not. || {self}')
                assert self._ever_had_players, err

            # 6.
            if self._require_players and self._ever_had_players:
                err = (f'For group {self._playergroup_id}, expected that it was automatically '
                       f'deleted after losing all its players, but found it was not. || {self}')
                assert self._players, err

            # 7.
            if self._require_leaders:
                err = (f'For group {self._playergroup_id} with some players, expected that there '
                       f'was a leader, but found it had none. || {self}')
                assert not self._players or self._leaders, err

            # 8.
            players_also_invited = self._players.intersection(self._invitations)
            err = (f'For group {self._playergroup_id}, expected that all users in the invitation '
                   'list of the group were not players, but found the following players who were '
                   'in the invitation list: {players_also_invited}. || {self}')
            assert not players_also_invited, err

        def __repr__(self):
            """
            Return a printable representation of this player group.

            Returns
            -------
            str
                Printable representation.

            """

            return (f"PlayerGroupManager.PlayerGroup(server, manager, '{self._playergroup_id}', "
                    f"player_limit={self._player_limit}, players={self._players}, "
                    f"leaders={self._leaders}, require_players={self._require_players}, "
                    f"require_leaders={self._require_leaders})")

    def __init__(self, server, playergroup_limit=None, playergroup_type=None):
        """
        Create a player group manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this player group manager belongs to.
        playergroup_type : PlayerGroupManager.PlayerGroup, optional
            The default type of player group this manager will create. Defaults to None (and then
            converted to self.PlayerGroup).
        playergroup_limit : int, optional
            The maximum number of groups this manager can handle. Defaults to None (no limit).
        """

        if playergroup_type is None:
            playergroup_type = self.PlayerGroup

        self._server = server
        self._playergroup_type = playergroup_type
        self._playergroup_limit = playergroup_limit
        self._id_to_group = dict()
        self._user_to_group = dict()

        self._check_structure()

    def new_group(self, playergroup_type=None, creator=None, player_limit=None,
                  require_invitations=False, require_players=True, require_leaders=True):
        """
        Create a new player group managed by this manager.

        Parameters
        ----------
        group_type : PlayerGroupManager.PlayerGroup
            Class of player group that will be produced. Defaults to None (and converted to the
            default player group created by this player group).
        creator : ClientManager.Client, optional
            The player who created this group. If set, they will also be added to the group if
            possible. Defaults to None.
        player_limit : int, optional
            The maximum number of players the group may have. Defaults to None (no limit).
        require_invitations : bool, optional
            If True, users can only be added to the group if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the group has no players left, the group will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the group has no leaders left, the group will choose a leader
            among any remaining players left; if no players are left, the next player added will
            be made leader. If False, no such automatic assignment will happen. Defaults to True.

        Returns
        -------
        PlayerGroupManager.PlayerGroup
            The created player group.

        Raises
        ------
        PlayerGroupError.ManagerTooManyGroupsError
            If the manager is already managing its maximum number of groups.
        PlayerGroupError.UserInAnotherGroupError
            If `creator` is not None and already part of a group managed by this manager.

        """

        if self._playergroup_limit is not None:
            if len(self._id_to_group) >= self._playergroup_limit:
                raise PlayerGroupError.ManagerTooManyGroupsError
        if creator and creator in self._user_to_group.keys():
            raise PlayerGroupError.UserInAnotherGroupError

        if playergroup_type is None:
            playergroup_type = self.PlayerGroup

        # Generate a playergroup ID and the new group
        playergroup_id = self._make_new_group_id()
        playergroup = playergroup_type(self._server, self, playergroup_id,
                                       player_limit=player_limit,
                                       require_invitations=require_invitations,
                                       require_players=require_players,
                                       require_leaders=require_leaders)
        self._id_to_group[playergroup_id] = playergroup

        if creator:
            playergroup.add_player(creator)

        playergroup._choose_leader_if_needed()

        self._check_structure()
        return playergroup

    def delete_group(self, playergroup):
        """
        Delete a player group managed by this manager, so all its players no longer belong to any
        player group.

        Parameters
        ----------
        playergroup : PlayerGroupManager.PlayerGroup
            The player group to delete.

        Returns
        -------
        (str, set of ClientManager.Client)
            The ID and players of the player group that was deleted.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError
            If the manager does not manage the target player group.

        """

        playergroup_id = self.get_group_id(playergroup) # Assert player group is managed by manager
        self._id_to_group.pop(playergroup_id)
        for player in playergroup._players:
            self._user_to_group.pop(player)

        self._check_structure()
        return playergroup_id, playergroup._players.copy()

    def get_managed_groups(self):
        """
        Return (a shallow copy of) the groups this manager manages.

        Returns
        -------
        set of PlayerGroupManager.PlayerGroup
            Player groups this manager manages.

        """

        return set(self._id_to_group.values())

    def get_group_of_user(self, user):
        """
        Return the player group managed by this manager user `user` is a player of.

        Parameters
        ----------
        user : ClientManager.Client
            User whose player group will be returned.

        Returns
        -------
        PlayerGroupManager.PlayerGroup
            Player group the player belongs to.

        Raises
        ------
        PlayerGroupError.UserInNoGroupError:
            If the player does not belong in any player group managed by this manager.

        """

        try:
            return self._user_to_group[user]
        except KeyError:
            raise PlayerGroupError.UserInNoGroupError

    def get_group(self, playergroup_tag):
        """
        If `playergroup_tag` is a player group managed by this manager, return it.
        If it is a string and the ID of a player group managed by this manager, return that.

        Parameters
        ----------
        playergroup_tag : PlayerGroupManager.PlayerGroup or str
            Player group this manager manages.

        Returns
        -------
        PlayerGroupManager.PlayerGroup
            The player group that matches the given tag.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError:
            If `playergroup_tag` is a group this manager does not manage.
        PlayerGroupError.ManagerInvalidGroupIDError:
            If `playergroup_tag` is a str and it is not the ID of a group this manager manages.

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
                raise PlayerGroupError.ManagerInvalidGroupIDError

        # Every other case
        raise PlayerGroupError.ManagerInvalidGroupIDError

    def get_group_id(self, playergroup_tag):
        """
        If `playergroup_tag` is the ID of a group managed by this manager, return it.
        If it is a player group managed by this manager, return its ID.

        Parameters
        ----------
        playergroup_tag : PlayerGroupManager.PlayerGroup or str
            Player group this manager manages.

        Returns
        -------
        str
            The ID of the player group that matches the given tag.

        Raises
        ------
        PlayerGroupError.ManagerDoesNotManageGroupError:
            If `playergroup_tag` is a group this manager does not manage.
        PlayerGroupError.ManagerInvalidGroupIDError:
            If `playergroup_tag` is a str and it is not the ID of a group this manager manages.

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
                raise PlayerGroupError.ManagerInvalidGroupIDError

        # Every other case
        raise PlayerGroupError.ManagerInvalidGroupIDError

    def _make_new_group_id(self):
        """
        Generate a player group ID that no other player group managed by this manager has.

        Returns
        -------
        str
            A unique player group ID.

        Raises
        ------
        PlayerGroupError.ManagerTooManyGroupsError
            If the manager is already managing its maximum number of groups.

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
                   f'{len(self._id_to_group)} player groups. || {self}')
            assert len(self._id_to_group) <= self._playergroup_limit, err

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
                       f'{playergroup1}, {playergroup2} had unique player group IDs, but found '
                       f'they did not. || {self}')
                assert playergroup1._playergroup_id != playergroup2._playergroup_id, err

                # 3b.
                err = (f'For player group manager {self}, expected that its two managed groups '
                       f'{playergroup1}, {playergroup2} had disjoint player sets, but found they '
                       f'did not. || {self}')
                assert not playergroup1._players.intersection(playergroup2._players), err

        # 4.
        for playergroup in self._user_to_group.values():
            err = (f'For player group manager {self}, expected that player group {playergroup} '
                   f'that appears in the player to player group mapping also appears in the player '
                   f'group ID to player group mapping, but found it did not. || {self}')
            assert playergroup in self._id_to_group.values(), err

        # 5.
        for (user, playergroup) in self._user_to_group.items():
            err = (f'For player group manager {self}, expected that user {user} in the player '
                   f'to group mapping be a player of its associated group {playergroup}, but found '
                   f'that was not the case. || {self}')
            assert user in playergroup._players, err

        # Last.
        for playergroup in self._id_to_group.values():
            playergroup._check_structure()
