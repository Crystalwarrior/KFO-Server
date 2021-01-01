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

"""
Module that contains the PlayerGroupManager class and the PlayerGroup subclass.

"""

import random

from server.constants import Constants
from server.exceptions import PlayerGroupError

class PlayerGroup:
    """
    A mutable data type for player groups.

    Player groups are groups of users (called players) with an ID, where some players
    (possibly none) are leaders.

    Each player group may have a player limit (beyond which no new players may be added), may
    require that it never loses all its players as soon as it gets its first one (or else it
    is automatically deleted) and may require that if it has at least one player, then that
    there is at least one leader (or else one is automatically chosen between all players).
    Each of these groups may also impose a concurrent player membership limit, so that every user
    that is a player of it is at most a player of that many player groups managed by this
    group's manager.

    Once a group is scheduled for deletion, its manager will no longer recognize it as a group
    it is managing (it will unmanage it), so no further mutator public method calls would be
    allowed on the player group.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the player group belongs to.
    # _manager : PlayerGroupManager
    #     Manager for this player group.
    # _playergroup_id : str
    #     Identifier for this player group.
    # _player_limit : int or None.
    #     If an int, it is the maximum number of players the group supports. If None, the group
    #     may have an arbitrary number of players.
    # _player_concurrent_limit : int or None.
    #     If an int, it is the maximum number of player groups managed by the same manager as
    #     this group that any player part of this player group may belong to, including this
    #     player group. If None, no such restriction is considered.
    # _players : set of ClientManager.Client
    #     Players of the player group.
    # _leaders : set of ClientManager.Client
    #     Leaders of the player group.
    # _invitations : set of clientManager.Client
    #     Users invited to (but not part of of) the player group.
    # _require_players : bool
    #     If True, the group will disassemble automatically if it loses all its players (but it
    #     may start with no players).
    # _require_leaders : bool
    #     If True and the group has no leaders but at least one player, it will randomly choose
    #     one player to be a leader.
    # _ever_had_players : bool
    #    If True, at least once has a player been added successfully the the player group;
    #    otherwise False.
    # _unmanaged : bool
    #     If True, the manager this group claims is its manager no longer recognizes it is
    #     managing this group, thus no further mutator public method calls would be allowed.

    # Invariants
    # ----------
    # 1. Each player is a client of the server.
    # 2. `self._unmanaged` is False if and only if `self` is in
    #    `self._manager._id_to_group.values()`.
    # 3. If `self._unmanaged`, then `self._players`, `self._invitations`, `self._leaders` are
    #    all empty sets.
    # 4. For every player `player` in `self._players`, `self._manager._user_to_groups[player]`
    #    exists and contains `self`.
    # 5. If `self._player_limit` is not None, then `len(self._players) <= player_limit`.
    # 6. For every player in `self._leaders`, they also belong in `self._players`.
    # 7. If `len(self._players) >= 1`, then `self._ever_had_players is True`.
    # 8. If `self._require_players` is True, then `len(self._players) >= 1 or self._unmanaged`.
    # 9. If `self._require_leaders` is True and `len(self._players) >= 1`, then
    #    `len(self._leaders) >= 1`.
    # 10. `self._invitations` and `self._players` are disjoint sets.
    # 11. If `self._require_invitations` is False, then `self._invitations` is the empty set.

    def __init__(self, server, manager, playergroup_id, player_limit=None,
                 player_concurrent_limit=1, require_invitations=False, require_players=True,
                 require_leaders=True):
        """
        Create a new player group. A player group should not be created outside some manager code.

        Parameters
        ----------
        server : TsuserverDR
            Server the player group belongs to.
        manager : PlayerGroupManager
            Manager for this player group.
        playergroup_id : str
            Identifier of the player group.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the player group supports. If None,
            it indicates the player group has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of player groups managed by `manager` that any
            player of this group may belong to, including this group. If None, it indicates
            that this group does not care about how many other player groups managed by
            `manager` each of its players belongs to. Defaults to 1 (a player may not be in
            another group managed by `manager` while in this group).
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
        self._player_concurrent_limit = player_concurrent_limit
        self._require_invitations = require_invitations
        self._require_players = require_players
        self._require_leaders = require_leaders

        self._players = set()
        self._leaders = set()
        self._invitations = set()
        self._ever_had_players = False
        self._unmanaged = False

    def get_id(self):
        """
        Return the ID of this player group.

        Returns
        -------
        str
            The ID.

        """

        return self._playergroup_id

    def get_player_concurrent_limit(self):
        """
        Return the concurrent player membership limit of this player group.

        Returns
        -------
        int or None
            The concurrent player membership limit.

        """

        return self._player_concurrent_limit

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
        leader, unless the group has no leaders and the player group requires a leader.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the player group.

        Raises
        ------
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.UserNotInvitedError
            If the group requires players be invited to be added and the user is not invited.
        PlayerGroupError.UserAlreadyPlayerError
            If the user to add is already a user of the player group.
        PlayerGroupError.UserInAnotherGroupError
            If the player is already in another group managed by this manager.
        PlayerGroupError.GroupIsFullError
            If the group reached its player limit.
        PlayerGroupError.UserHitGroupConcurrentLimitError.
            If the player has reached any of the groups it belongs to managed by this player
            group's manager concurrent player membership limit, or by virtue of joining this group
            they will violate this group's concurrent player membership limit.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
        if self._require_invitations and user not in self._invitations:
            raise PlayerGroupError.UserNotInvitedError
        if user in self._players:
            raise PlayerGroupError.UserAlreadyPlayerError
        if self._player_limit is not None and len(self._players) >= self._player_limit:
            raise PlayerGroupError.GroupIsFullError
        if self._manager.find_player_concurrent_limiting_group(user):
            raise PlayerGroupError.UserHitGroupConcurrentLimitError
        groups_of_user = self._manager.get_groups_of_user(user)
        if len(groups_of_user) >= self._player_concurrent_limit:
            raise PlayerGroupError.UserHitGroupConcurrentLimitError

        self._ever_had_players = True
        self._players.add(user)
        self._manager._add_user_to_mapping(user, self)

        if self._require_invitations:
            self._invitations.remove(user)

        self._choose_leader_if_needed()

        self._manager._check_structure()

    def remove_player(self, user):
        """
        Make a user be no longer a player of this player group.

        If the group required that there it always had players and by calling this method the
        group had no more players, the group will automatically be scheduled for deletion.

        Parameters
        ----------
        user : ClientManager.Client
            User to remove.

        Raises
        ------
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.UserNotPlayerError
            If the user to remove is already not a player of this group.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
        if user not in self._players:
            raise PlayerGroupError.UserNotPlayerError

        self._players.remove(user)
        self._leaders.discard(user)
        self._manager._remove_user_from_mapping(user, self)

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
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.GroupDoesNotTakeInvitationsError
            If the group does not require users be invited to the player group.
        PlayerGroupError.UserAlreadyInvitedError
            If the player to invite is already invited to the player group.
        PlayerGroupError.UserAlreadyPlayerError
            If the player to invite is already a player of the player group.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
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
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.GroupDoesNotTakeInvitationsError
            If the group does not require users be invited to the player group.
        PlayerGroupError.UserNotInvitedError
            If the user to uninvite is already not invited to this group.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
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

    def get_regulars(self, cond=None):
        """
        Return (a shallow copy of) the set of players of this player group that are not leaders
        (regulars) and satisfy a condition if given.

        Parameters
        ----------
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that all regulars returned satisfy. Defaults to None (no checked
            conditions).

        Returns
        -------
        set of ClientManager.Client
            The (filtered) regulars of this player group.

        """

        if cond is None:
            cond = lambda c: True

        regulars = {player for player in self._players if player not in self._leaders}
        filtered_regulars = {regular for regular in regulars if cond(regular)}
        return filtered_regulars

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
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.UserNotPlayerError
            If the player to promote is not a player of this group.
        PlayerGroupError.UserAlreadyLeaderError
            If the player to promote is already a leader of this group.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
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
        PlayerGroupError.GroupIsUnmanagedError:
            If the group was scheduled for deletion and thus does not accept any mutator
            public method calls.
        PlayerGroupError.UserNotPlayerError
            If the player to demote is not a player of this group.
        PlayerGroupError.UserNotLeaderError
            If the player to demote is already not a leader of this group.

        """

        if self._unmanaged:
            raise PlayerGroupError.GroupIsUnmanagedError
        if user not in self._players:
            raise PlayerGroupError.UserNotPlayerError
        if user not in self._leaders:
            raise PlayerGroupError.UserNotLeaderError

        self._leaders.remove(user)
        # Check leadership requirement
        self._choose_leader_if_needed()
        self._manager._check_structure()

    def is_unmanaged(self):
        """
        Return True if this player group is unmanaged, False otherwise.

        Returns
        -------
        bool
            True if unmanaged, False otherwise.

        """

        return self._unmanaged

    def has_ever_had_players(self):
        """
        Return True if a player has ever been added to this player group, False otherwise.

        Returns
        -------
        bool
            True if the player group has ever had a player added, False otherwise.

        """

        return self._ever_had_players

    def destroy(self):
        """
        Mark this player group as destroyed and notify its manager so that it is deleted.
        If the player group is already destroyed, this function does nothing.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        # Implementation detail: To make this safely reentrant and allow this code to be ran
        # multiple times, we do the following:
        # At the very beginning we check if self._unmanaged is True.
        # * If yes, we abort execution of this method.
        # * If no, we continue execution and mark self._unmanaged as True
        # Thus there cannot be more than one call of destroy that is not immediately aborted.

        if self._unmanaged:
            return
        self._unmanaged = True

        try:
            self._manager.delete_group(self)
        except PlayerGroupError.ManagerDoesNotManageGroupError:
            pass

        # While only clearing internal variables here means that structural integrity won't be
        # maintained in time for the manager's structural checks, as the manager will no longer
        # list this player group as a group it manages, no structural checks will be performed
        # on this object anymore by outside entities, so this code is safe.

        self._players = set()
        self._invitations = set()
        self._leaders = set()

        return

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
        for player in self._players:
            err = (f'For group {self._playergroup_id}, expected that player {player} was a '
                   f'client of its server {self._server}, but found that was not the case. '
                   f'|| {self}')
            assert self._server.is_client(player), err

        # 2.
        err = (f'For group {self._playergroup_id} that is not unmanaged that also claims that '
               f'it is managed by manager {self._manager}, expected that it recognized that '
               f'it managed it, but found it did not. || {self}')
        if not self._unmanaged:
            assert self in self._manager.get_groups(), err

        err = (f'For group {self._playergroup_id} that is unmanaged that also claims that it '
               f'was managed by manager {self._manager}, expected that it recognized that '
               f'it did not manage it, but found it did. || {self}')
        if self._unmanaged:
            assert self not in self._manager.get_groups(), err

        # 3.
        if self._unmanaged:
            err = (f'For group {self._playergroup_id} that is unmanaged, expected that it had '
                   f'no players, but found it had these players: {self._players} || {self}')
            assert not self._players, err

            err = (f'For group {self._playergroup_id} that is unmanaged, expected that it had '
                   f'no invitations, but found it had these invitations: {self._invitations} '
                   f'|| {self}')
            assert not self._invitations, err

            err = (f'For group {self._playergroup_id} that is unmanaged, expected that it had '
                   f'no leaders, but found it had these leaders: {self._leaders} || {self}')
            assert not self._leaders, err

        # 4.
        for player in self._players:
            err = (f'For group {self._playergroup_id}, expected that its player {player} is '
                   f'properly recognized in the player to group mapping of the manager of the '
                   f'group {self._manager}, but found that was not the case. || {self}')
            assert (player in self._manager.get_users_in_groups()
                    and self in self._manager.get_groups_of_user(player)), err

        # 5.
        if self._player_limit is not None:
            err = (f'For group {self._playergroup_id}, expected that there were at most '
                   f'{self._player_limit} players, but found it had {len(self._players)} '
                   f'players. || {self}')
            assert len(self._players) <= self._player_limit, err

        # 6.
        for leader in self._leaders:
            err = (f'For group {self._playergroup_id}, expected that leader {leader} was a '
                   f'player of it too, but found it was not. || {self}')
            assert leader in self._players, err

        # 7.
        if self._players:
            err = (f'For group {self._playergroup_id}, expected it knew it ever had some '
                   f'players, but found it did not. || {self}')
            assert self._ever_had_players, err

        # 8.
        if self._require_players and self._ever_had_players:
            err = (f'For group {self._playergroup_id}, expected that it was scheduled for '
                   f'deletion after losing all its players, but found it was not. || {self}')
            assert self._players or self._unmanaged, err

        # 9.
        if self._require_leaders:
            err = (f'For group {self._playergroup_id} with some players, expected that there '
                   f'was a leader, but found it had none. || {self}')
            assert not self._players or self._leaders, err

        # 10.
        players_also_invited = self._players.intersection(self._invitations)
        err = (f'For group {self._playergroup_id}, expected that all users in the invitation '
               f'list of the group were not players, but found the following players who were '
               f'in the invitation list: {players_also_invited}. || {self}')
        assert not players_also_invited, err

        # 11.
        err = (f'For group {self._playergroup_id} that does not require invitations, expected '
               f'that no player was invited to the group, but found the following users who '
               f'were in the invitation list: {self._invitations}. || {self}')
        assert self._require_invitations or not self._invitations

    def __repr__(self):
        """
        Return a representation of this player group.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"PlayerGroup(server, {self._manager.get_id()}, '{self._playergroup_id}', "
                f"player_limit={self._player_limit}, "
                f"player_concurrent_limit={self._player_concurrent_limit}, "
                f"require_players={self._require_players}, "
                f"require_invitations={self._require_invitations}, "
                f"require_leaders={self._require_leaders}) "
                f"|| "
                f"players={self._players}, invitations={self._invitations}, "
                f"leaders={self._leaders}, unmanaged={self._unmanaged}"
                )

class PlayerGroupManager:
    """
    A mutable data type for a manager for player groups.

    Each player group is managed by a player group manager. Only this manager is allowed to execute
    any public methods on them. Each manager may also have a player group limit (beyond which it
    will not manage any more groups).

    Contains the player group object definition, methods for creating and deleting them, as well as
    some observer methods.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the player group manager belongs to.
    # _playergroup_limit : int or None
    #     If an int, it is the maximum number of player groups this manager supports. If None, the
    #     manager may manage an arbitrary number of groups.
    # _default_playergroup_type : PlayerGroup or functools.partial
    #     The type of player groups this player group manager will create by default when ordered
    #     to create a new one.
    # _user_to_groups : dict of ClientManager.Client to set of PlayerGroup
    #     Mapping of users to the player groups managed by this manager they belong to.
    # _id_to_group : dict of str to PlayerGroup
    #     Mapping of player group IDs to player groups that this manager manages.

    # Invariants
    # ----------
    # 1. If `self._playergroup_limit` is an int, then `len(self._id_to_group) <=
    #    self._playergroup_limit`.
    # 2. For every player group `(playergroup_id, playergroup)` in `self._id_to_group.items()`:
    #     a. `playergroup._playergroup_id == playergroup_id`.
    #     b. `playergroup._players` is a subset of `self._user_to_groups.keys()`.
    #     c. `playergroup.is_unmanaged()` is False.
    # 3. For all pairs of distinct groups `group1` and `group2` in `self._id_to_group.values()`:
    #     a. `group1._playergroup_id != group2._playergroup_id`.
    # 4. For every player `player` in `self._user_to_groups.keys()`:
    #     a. `self._user_to_groups[player]` is a non-empty set.
    #     b. `self._user_to_groups[player]` is a subset of `self._id_to_group.values()`.
    #     c. For every group `group` in `self._user_to_groups[player]`, `player` belongs to `group`.
    # 5. For every player `player` in `self._user_to_groups.keys()`:
    #     a. For every group `group` in `self._user_to_groups[player]`:
    #           1. `group` has no player concurrent membership limit, or it is at least the length
    #               of `self._user_to_groups[player]`.
    # 6. Each player group it manages also satisfies its structural invariants.

    def __init__(self, server, playergroup_limit=None, default_playergroup_type=None,
                 available_id_producer=None):
        """
        Create a player group manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this player group manager belongs to.
        playergroup_limit : int, optional
            The maximum number of groups this manager can handle. Defaults to None (no limit).
        playergroup_type : PlayerGroup, optional
            The default type of player group this manager will create. Defaults to None (and then
            converted to PlayerGroup).
        available_id_producer : typing.types.FunctionType, optional
            Function to produce available group IDs. It will override the built-in class method
            get_available_group_id. Defaults to None (and then converted to the built-in
            get_available_group_id).

        """

        if default_playergroup_type is None:
            default_playergroup_type = PlayerGroup
        if available_id_producer is None:
            available_id_producer = self.get_available_group_id
        self.get_available_group_id = available_id_producer

        self._server = server
        self._default_playergroup_type = default_playergroup_type
        self._playergroup_limit = playergroup_limit
        self._id_to_group = dict()
        self._user_to_groups = dict()

        self._check_structure()

    def new_group(self, playergroup_type=None, creator=None, player_limit=None,
                  player_concurrent_limit=1, require_invitations=False, require_players=True,
                  require_leaders=True):
        """
        Create a new player group managed by this manager.

        Parameters
        ----------
        playergroup_type : PlayerGroup
            Class of player group that will be produced. Defaults to None (and converted to the
            default player group created by this player group manager).
        creator : ClientManager.Client, optional
            The player who created this group. If set, they will also be added to the group.
            Defaults to None.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the player group supports. If None, it
            indicates the player group has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of player groups managed by `self` that any player
            of this group to create may belong to, including this group to create. If None, it
            indicates that this group does not care about how many other player groups managed by
            `self` each of its players belongs to. Defaults to 1 (a player may not be in
            another group managed by `self` while in this new group).
        require_invitations : bool, optional
            If True, users can only be added to the group if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the group loses all its players, the group will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the group has no leaders left, the group will choose a leader
            among any remaining players left; if no players are left, the next player added will
            be made leader. If False, no such automatic assignment will happen. Defaults to True.

        Returns
        -------
        PlayerGroup
            The created player group.

        Raises
        ------
        PlayerGroupError.ManagerTooManyGroupsError
            If the manager is already managing its maximum number of groups.
        PlayerGroupError.UserHitGroupConcurrentLimitError.
            If `creator` has reached the concurrent player membership limit of any of the groups it
            belongs to managed by this manager, or by virtue of joining this group the creator
            they will violate this group's concurrent player membership limit.

        """

        if self._playergroup_limit is not None:
            if len(self._id_to_group) >= self._playergroup_limit:
                raise PlayerGroupError.ManagerTooManyGroupsError
        if creator:
            # Check if adding the creator to this new group would cause any concurrent
            # membership limits being reached.
            if self.find_player_concurrent_limiting_group(creator):
                raise PlayerGroupError.UserHitGroupConcurrentLimitError
            groups_of_user = self._user_to_groups.get(creator, None)
            if groups_of_user is not None and len(groups_of_user) >= player_concurrent_limit:
                raise PlayerGroupError.UserHitGroupConcurrentLimitError

        # At this point, we are committed to creating this player group.
        # Generate a playergroup ID and the new group

        def_args = (
            self._server,
            self,
            self.get_available_group_id(),
            )
        def_kwargs = {
            'player_limit': player_limit,
            'player_concurrent_limit': player_concurrent_limit,
            'require_invitations': require_invitations,
            'require_players': require_players,
            'require_leaders': require_leaders,
            }

        new_playergroup_type = Constants.make_partial_from(playergroup_type,
                                                           self._default_playergroup_type,
                                                           *def_args, **def_kwargs)
        playergroup = new_playergroup_type()
        playergroup_id = playergroup.get_id()
        self._id_to_group[playergroup_id] = playergroup

        if creator:
            playergroup.add_player(creator)

        self._check_structure()
        return playergroup

    def delete_group(self, playergroup):
        """
        Delete a player group managed by this manager, so all its players no longer belong to this
        player group.

        Parameters
        ----------
        playergroup : PlayerGroup
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

        if not self.manages_group(playergroup):
            raise PlayerGroupError.ManagerDoesNotManageGroupError

        playergroup_id = playergroup.get_id()
        self._id_to_group.pop(playergroup_id)

        former_players = playergroup.get_players()

        for player in former_players:
            self._user_to_groups[player].remove(playergroup)
            if not self._user_to_groups[player]:
                self._user_to_groups.pop(player)

        playergroup.destroy()

        self._check_structure()
        return playergroup_id, former_players

    def manages_group(self, playergroup):
        """
        Return True if the player group is managed by this manager, False otherwise.

        Parameters
        ----------
        playergroup : PlayerGroup
            The player group to check.

        Returns
        -------
        bool
            True if the manager manages this player group, False otherwise.

        """

        return playergroup in self._id_to_group.values()

    def get_groups(self):
        """
        Return (a shallow copy of) the groups this manager manages.

        Returns
        -------
        set of PlayerGroup
            Player groups this manager manages.

        """

        return set(self._id_to_group.values())

    def get_group_by_id(self, playergroup_id):
        """
        If `playergroup_id` is the ID of a player group managed by this manager, return the group.

        Parameters
        ----------
        playergroup_id : str
            ID of the player group this manager manages.

        Returns
        -------
        PlayerGroup
            The player group that matches the given tag.

        Raises
        ------
        PlayerGroupError.ManagerInvalidGroupIDError:
            If `playergroup_id` is not the ID of a group this manager manages.

        """

        try:
            return self._id_to_group[playergroup_id]
        except KeyError:
            raise PlayerGroupError.ManagerInvalidGroupIDError

    def get_group_limit(self):
        """
        Return the player group limit of this manager.

        Returns
        -------
        int
            Player group limit.

        """

        return self._playergroup_limit

    def get_group_ids(self):
        """
        Return (a shallow copy of) the IDs of all player groups managed by this manager.

        Returns
        -------
        set of str
            The IDs of all managed player groups.

        """

        return set(self._id_to_group.keys())

    def get_groups_of_user(self, user):
        """
        Return (a shallow copy of) the player groups managed by this manager user `user` is a
        player of. If the user is part of no such player group, an empty set is returned.

        Parameters
        ----------
        user : ClientManager.Client
            User whose player groups will be returned.

        Returns
        -------
        set of PlayerGroup
            Player groups the player belongs to.

        """

        try:
            return self._user_to_groups[user].copy()
        except KeyError:
            return set()

    def get_users_in_groups(self):
        """
        Return (a shallow copy of) all the users that are part of some player group managed by
        this manager.

        Returns
        -------
        set of ClientManager.Client
            Users in some managed player group.

        """

        return set(self._user_to_groups.keys())

    def get_available_group_id(self):
        """
        Get a player group ID that no other player group managed by this manager has.

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
        while self.get_group_limit() is None or group_number < self.get_group_limit():
            new_group_id = "pg{}".format(group_number)
            if new_group_id not in self._id_to_group.keys():
                return new_group_id
            group_number += 1
        raise PlayerGroupError.ManagerTooManyGroupsError

    def get_id(self):
        """
        Return the ID of this manager. This ID is guaranteed to be unique among
        simultaneously existing managers.

        Returns
        -------
        str
            ID.

        """

        return hex(id(self))

    def find_player_concurrent_limiting_group(self, user):
        """
        For user `user`, find a player group `most_restrictive_group` managed by this manager such
        that, if `user` were to join another player group managed by this manager, they would
        violate `most_restrictive_group`'s concurrent player membership limit.
        If no such group exists (or the player is not member of any player group managed by this
        manager), return None.
        If multiple such groups exist, any one of them may be returned.

        Parameters
        ----------
        user : ClientManager.Client
            User to test.

        Returns
        -------
        PlayerGroup or None
            Limiting player group as previously described if it exists, None otherwise.

        """

        groups = self.get_groups_of_user(user)
        if not groups:
            return None

        # We only care about groups that establish a concurrent player membership limit
        groups_with_limit = {group for group in groups
                             if group.get_player_concurrent_limit() is not None}
        if not groups_with_limit:
            return None

        # It just suffices to analyze the group with the smallest limit, because:
        # 1. If the player is member of at least as many groups as this group's limit, this group
        # is an example group that can be returned.
        # 2. Otherwise, no other groups exist due to the minimality condition.
        most_restrictive_group = min(groups_with_limit,
                                     key=lambda group: group.get_player_concurrent_limit())
        if len(groups) < most_restrictive_group.get_player_concurrent_limit():
            return None
        return most_restrictive_group

    def _add_user_to_mapping(self, user, group):
        """
        Update the user to player groups mapping with the information that `user` was added to
        `group`.

        Parameters
        ----------
        user : ClientManager.Client
            User that was added.
        group : PlayerGroup
            Player group that `user` was added to.

        Returns
        -------
        None.

        """

        try:
            self._user_to_groups[user].add(group)
        except KeyError:
            self._user_to_groups[user] = {group}

    def _remove_user_from_mapping(self, user, group):
        """
        Update the user to player groups mapping with the information that `user` was removed from
        `group`.

        Parameters
        ----------
        user : ClientManager.Client
            User that was removed.
        group : PlayerGroup
            Player group that `user` was removed from.

        Returns
        -------
        None.

        """
        self._user_to_groups[user].remove(group)
        if not self._user_to_groups[user]:
            self._user_to_groups.pop(user)

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
            err = (f'For player group manager {self}, expected that player group {playergroup} '
                   f'that appears in the ID to player group mapping has the same ID as in the '
                   f'mapping, but found it did not.')
            assert playergroup.get_id() == playergroup_id, err

            # 2b.
            unrecognized = {player for player in playergroup.get_players()
                            if player not in self._user_to_groups.keys()}
            err = (f'For player group manager {self}, expected that the players of player group '
                   f'{playergroup} were also recognized as players in the user to group mapping '
                   f'of the manager, but found these unrecognized players: {unrecognized}. ')
            assert not unrecognized, err

            # 2c.
            err = (f'For player group manager {self}, expected that managed player group '
                   f'{playergroup} recognized that it was not unmanaged, but found it did.')
            assert not playergroup.is_unmanaged(), err

        # 3.
        for playergroup1 in self._id_to_group.values():
            for playergroup2 in self._id_to_group.values():
                if playergroup1 == playergroup2:
                    continue

                # 3a.
                err = (f'For player group manager {self}, expected that its two managed groups '
                       f'{playergroup1}, {playergroup2} had unique player group IDs, but found '
                       f'they did not. || {self}')
                assert playergroup1.get_id() != playergroup2.get_id(), err

        # 4.
        for user in self._user_to_groups:
            playergroups = self._user_to_groups[user]

            # a.
            err = (f'For player group manager {self}, expected that user {user} to only appear '
                   f'in the user to player groups mapping if it was a player of any player '
                   f'group managed by this manager, but found it appeared while not belonging to '
                   f'any player group. || {self}')
            assert playergroups, err

            for group in playergroups:
                # b.
                err = (f'For player group manager {self}, expected that player group {group} '
                       f'that appears in the user to player group mapping for user {user} '
                       f'also appears in the player group ID to player group mapping, but found '
                       f'it did not. || {self}')
                assert group in self._id_to_group.values(), err

                # c.
                err = (f'For player group manager {self}, expected that user {user} in the user '
                       f'to group mapping be a player of its associated group {group}, but '
                       f'found that was not the case. || {self}')
                assert user in group.get_players(), err

        # 5.
        for user in self._user_to_groups:
            playergroups = self._user_to_groups[user]
            membership = len(playergroups)

            for group in playergroups:
                limit = group.get_player_concurrent_limit()

                if limit is None:
                    continue
                err = (f'For player group manager {self}, expected that user {user} in group '
                       f'{group} belonged to at most the concurrent player membership limit of '
                       f'that group of {limit} group{"s" if limit != 1 else ""}, found they '
                       f'belonged to {membership} group{"s" if membership != 1 else ""}. || {self}')
                assert membership <= limit

        # Last.
        for playergroup in self._id_to_group.values():
            playergroup._check_structure()

    def __repr__(self):
        """
        Return a representation of this player group manager.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"PlayerGroupManager(server, playergroup_limit={self._playergroup_limit}, "
                f"default_playergroup_type={self._default_playergroup_type}, "
                f"|| "
                f"_user_to_groups={self._user_to_groups}, "
                f"_id_to_group={self._id_to_group}, "
                f"id={hex(id(self))})")
