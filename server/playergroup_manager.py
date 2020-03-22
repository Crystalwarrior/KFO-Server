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
may require that it contains at least one member at all times (or else may be automatically
deleted), and may require that if it has at least one member, then that there is at least one
leader (or else one is automatically chosen between all members).

Each player group is managed by a player group manager. A player cannot be member of two or more
groups managed by the same manager simultaneously. Each manager may have a player group limit
(beyond which it will not manage any more groups).
"""

class PlayerGroupManager:
    """
    A mutable data type for a manager for the player groups in a server.
    Contains the player group object definition, as well as the server's player group list.

    Attributes
    ----------
    _server : TsuserverDR
        Server the player group manager belongs to.
    _playergroups : set of PlayerGroup
        Player groups this manager manages.
    _player_to_group : dict of ClientManager.Client to PlayerGroup
        Mapping of players to the player group managed by this manager they belong to.
    _playergroup_limit : int or None
        If an int, it is the maximum number of player groups this manager supports. If None, the
        manager may manage an arbitrary number of groups.

    Invariants
    ----------
    1. If `self._playergroup_limit` is an int, then `len(self._playergroups) <=
    self._playergroup_limit`.
    2. For every player group `group` in `self._playergroups`, `group._manager = self`.
    3. For every pair of distinct player groups `group1` and `group2` in `self._playergroups`:
        a. `group1._playergroup_id != group2._playergroup_id`.
        b. `group1._players` and `group2._players` are disjoint.
    4. `self._player_to_group.values()` is a subset of `self._playergroups`.
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
            If True, the group will disassemble automatically if it has no members.
        _require_leaders : bool
            If True and the group has no leaders but at least one member, it will randomly choose
            one member to be a leader.

        Invariants
        ----------
        1. If `_member_limit` is an int, then `len(_members) <= member_limit`.
        2. For every player in `_leaders`, they also belong in `_members`.
        3. If `_require_members` is True, then `len(_members) >= 1`.
        4. If `_require_leaders` is True and `len(_members) >= 1`, then `len(_leaders) >= 1`.

        """

        def __init__(self, server, manager, playergroup_id, member_limit=None, members=None,
                     leaders=None):
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
            members : set of ClientManager.Client
                Set of players that automatically start as members of the group. Its size must be
                less than member_limit if it is not None. Defaults to None (converted to an empty
                set, which means no members).
            leaders : set of ClientManager.Client
                Set of players that automatically start as leaders of the group. It must be a
                subset of members. Defaults to None (converted to an empty set, which means no
                leaders).

            Raises
            ------
            PlayerGroupError.PlayerAlreadyMemberError
                If any player in the group is part of a similar type group.

            """

            raise NotImplementedError

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

            raise NotImplementedError

        def get_members(self):
            """
            Return (a shallow copy of) the set of members of this player group.

            Returns
            -------
            set of ClientManager.Client
                The members of this player group.

            """

            raise NotImplementedError

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

            raise NotImplementedError

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

            raise NotImplementedError

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

            raise NotImplementedError

        def get_leaders(self):
            """
            Return (a shallow copy of) the set of leaders of this player group.

            Returns
            -------
            set of ClientManager.Client
                The leaders of this player group.

            """

            raise NotImplementedError

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

            raise NotImplementedError

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

            raise NotImplementedError

        def _check_structure(self):
            """
            Assert that all invariants specified in the class description are maintained.

            Raises
            ------
            AssertionError
                If any of the invariants are not maintained.

            """

            raise NotImplementedError

    def __init__(self, server, group_limit=None):
        """
        Create a player group manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this player group manager belongs to.
        group_limit : int, optional
            The maximum number of groups this manager can handle. The default is None.

        """

        raise NotImplementedError

    def assemble_group(self, creator=None, player_limit=None, require_members=True,
                       require_leaders=True):
        """
        Create a new player group managed by this manager.

        Parameters
        ----------
        creator : ClientManager.Client, optional
            The player who created this group. If set, they will also be added to the group if
            possible. The default is None.
        player_limit : int, optional
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

        raise NotImplementedError


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
        None.

        """

        raise NotImplementedError

    def get_managed_groups(self):
        """
        Return (a shallow copy of) the groups this manager manages.

        Returns
        -------
        set of PlayerGroup
            Player groups this manager manages.

        """

        raise NotImplementedError

    def get_group_of_player(self, player):
        """
        Return the player group managed by this manager player `player` belongs to.

        Raises
        ------
        PlayerGroupError.PlayerInNoGroupError:
            If the player does not belong in any player group managed by this manager.

        Returns
        -------
        PlayerGroup
            Player group the player belongs to.

        """

        raise NotImplementedError

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

        raise NotImplementedError

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

        raise NotImplementedError

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

        raise NotImplementedError

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        raise NotImplementedError
