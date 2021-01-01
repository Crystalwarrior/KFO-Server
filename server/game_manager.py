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
Module that contains the GameManager class, which itself contains the Game and Team subclasses.

Games maintain a PlayerGroup-like structure and methods, but also allow the creation of teams with
thier players. Teams are proper PlayerGroups, and no player of a game can be part of two teams
managed by the same game. Players of a game need not be part of a team managed by the game, but a
team can only have players of the game as players of the team. Removing a player from a game
also removes them from their team if they were in any.

Games also maintain a TimerManager-like structure, allowing the creation of timers
managed by the game.

Each game is managed by a game manager, which itself maintains a PlayerGroupManager-like structure.
Unless specified otherwise in the games, a player may be part of two or more games managed by the
same game manager.

"""

from server.constants import Constants
from server.exceptions import GameError, PlayerGroupError, TimerError
from server.playergroup_manager import PlayerGroup, PlayerGroupManager
from server.timer_manager import TimerManager
from server.subscriber import Listener

class _Team(PlayerGroup):
    """
    Teams are player groups with a fixed concurrent player membership limit of 1.
    """

    # (Private) Attributes
    # --------------------
    # _game : _Game
    #     Game this team is a part of.

    def __init__(self, server, manager, playergroup_id, player_limit=None,
                 player_concurrent_limit=None, require_invitations=False, require_players=True,
                 require_leaders=True):
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
        game : _Game
            Game of this player group.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the player group supports. If None,
            it indicates the player group has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of player groups managed by `manager` that any
            player of this group may belong to, including this group. If None, it indicates
            that this group does not care about how many other player groups managed by
            `manager` each of its players belongs to. It is always overwritten by 1 (a player
            may not be in another group managed by `manager` while in this group).
        require_invitations : bool, optional
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

        super().__init__(server, manager, playergroup_id, player_limit=player_limit,
                         player_concurrent_limit=1, # Teams allow 1 concurrent player membership
                         require_invitations=require_invitations,
                         require_players=require_players, require_leaders=require_leaders)
        self._game = None

    def add_player(self, user):
        """
        Make a user a player of the player group. By default this player will not be a
        leader.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the player group.
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that the player to add must satisfy. If the user fails this condition,
            they will not be added. Defaults to None (no checked conditions).

        Raises
        ------
        PlayerGroupError.UserNotInvitedError
            If the group requires players be invited to be added and the user is not invited.
        PlayerGroupError.UserAlreadyPlayerError
            If the user to add is already a user of the player group.
        PlayerGroupError.GroupIsFullError
            If the group reached its player limit.
        PlayerGroupError.UserHitGroupConcurrentLimitError.
            If the player has reached any of the groups it belongs to managed by this player
            group's manager concurrent player membership limit, or by virtue of joining this group
            will violate this group's concurrent player membership limit.
        PlayerGroupError.UserNotPlayerError
            If the user to add is not a player of the game.

        """

        if not self._game.is_player(user):
            raise PlayerGroupError.UserNotPlayerError

        super().add_player(user)


class _Game():
    """
    A mutable data type for games.

    Games are groups of users (called players) with an ID, that may also manage some timers
    and teams.

    Some players of the game (possibly none) may become leaders. A player that is not a leader
    is called regular. Each game may have a player limit (beyond which no new players may be added),
    may require that it never loses all its players as soon as it gets its first one (or else it
    is automatically deleted) and may require that if it has at least one player, then that there
    is at least one leader (or else one is automatically chosen between all players). Each of these
    games may also impose a concurrent player membership limit, so that every user that is a player
    of it is at most of that many games managed by this game's manager. Each game may also
    require all its players have characters when trying to join the game, as well as remove any
    player that switches to a non-character.

    Each of the timers a game manages are timer_manager.Timers.

    For each managed team, its players must also be players of this game.

    Once a game is scheduled for deletion, its manager will no longer recognize it as a game
    it is managing (it will unmanage it), so no further mutator public method calls would be
    allowed on the game.

    Each game also has a standard listener. By default the game subscribes to all its players'
    updates.

    Attributes
    ----------
    listener : Listener
        Standard listener of the game.

    Callback Methods
    ----------------
    _on_client_inbound_ms_check
        Method to perform once a player of the game wants to send an IC message.
    _on_client_inbound_ms
        Method to perform once a player of the game sends an IC message.
    _on_client_change_character
        Method to perform once a player of the game has changed character.
    _on_client_destroyed
        Method to perform once a player of the game is destroyed.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the game belongs to.
    # _manager : GameManager
    #     Manager for this game.
    # _game_id : str
    #     Identifier for this game.
    # _require_character : bool
    #   If False, players without a character will not be allowed to join the game, and players
    #   that switch to something other than a character will be automatically removed from the
    #   game. If False, no such checks are made.
    # _team_manager : PlayerGroupManager
    #     Internal manager that handles the teams of the game.
    # _timer_manager: TimerManager
    #     Internal manager that handles the timers of the game.
    # _playergroup: PlayerGroup
    #     Internal playergroup that implements the player features of the game.

    # Invariants
    # ----------
    # 1. All players part of a team managed by this game are players of the game.
    # 2. `self._unmanaged == self._playergroup._unmanaged`.
    # 3. For each player of the game, the game is subscribed to it.
    # 4. If the game requires its players have characters, all its players do have characters.
    # 5. Each internal structure satisfies its invariants.

    def __init__(self, server, manager, game_id, player_limit=None,
                 player_concurrent_limit=None, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None,
                 timer_limit=None, playergroup_manager=None):
        """
        Create a new game. A game should not be fully initialized anywhere else other than
        some manager code, as otherwise the manager will not recognize the game.

        Parameters
        ----------
        server : TsuserverDR
            Server the game belongs to.
        manager : GameManager
            Manager for this game.
        game_id : str
            Identifier of the game.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the game supports. If None, it
            indicates the game has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of games managed by `manager` that any
            player of this game may belong to, including this game. If None, it indicates
            that this game does not care about how many other games managed by `manager` each
            of its players belongs to. Defaults to None.
        require_invitation : bool, optional
            If True, players can only be added to the game if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the game has no players left, the game will
            automatically be deleted. If False, no such automatic deletion will happen.
            Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the game has no leaders left, the game will choose a
            leader among any remaining players left; if no players are left, the next player
            added will be made leader. If False, no such automatic assignment will happen.
            Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the game, and
            players that switch to something other than a character will be automatically
            removed from the game. If False, no such checks are made. A player without a
            character is considered one where player.has_character() returns False. Defaults to
            False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the game supports. If None, it
            indicates the game has no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of timers the game supports. If None, it
            indicates the game has no timer limit. Defaults to None.
        playergroup_manager : PlayerGroupManager, optional
            The internal playergroup manager of the game manager. Access to this value is
            limited exclusively to this __init__, and is only to initialize the internal
            player group of the game.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.

        """

        self._server = server
        self._manager = manager
        self._game_id = game_id
        self._require_character = require_character
        self._unmanaged = False

        self._team_manager = PlayerGroupManager(server, playergroup_limit=team_limit,
                                                default_playergroup_type=_Team)
        self._timer_manager = TimerManager(server, timer_limit=timer_limit)
        # Creator is to be added in the manager
        try:
            group = playergroup_manager.new_group(creator=None,
                                                  player_limit=player_limit,
                                                  player_concurrent_limit=player_concurrent_limit,
                                                  require_invitations=require_invitations,
                                                  require_players=require_players,
                                                  require_leaders=require_leaders)
        except PlayerGroupError.ManagerTooManyGroupsError:
            raise GameError.ManagerTooManyGamesError

        self._playergroup = group

        # Implementation detail: the callbacks of the internal objects of the game are (to be)
        # ignored.
        self.listener = Listener(self, {
            'client_inbound_ms': self._on_client_inbound_ms,
            'client_inbound_ms_check': self._on_client_inbound_ms_check,
            'client_change_character': self._on_client_change_character,
            'client_destroyed': self._on_client_destroyed,
            })


    def get_id(self):
        """
        Return the ID of this game.

        Returns
        -------
        str
            The ID.

        """

        # Development note: This is NOT the ID of the internal player group, but the ID of the
        # game itself. To facilitate your life, these two should be made the same.
        return self._game_id

    def get_player_concurrent_limit(self):
        """
        Return the concurrent player membership limit of this game.

        Returns
        -------
        int or None
            The concurrent player membership limit.

        """

        return self._playergroup.get_player_concurrent_limit()

    def get_players(self, cond=None):
        """
        Return (a shallow copy of) the set of players of this game that satisfy a condition
        if given.

        Parameters
        ----------
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that all players returned satisfy. Defaults to None (no checked
            conditions).

        Returns
        -------
        set of ClientManager.Client
            The (filtered) players of this game.

        """

        return self._playergroup.get_players(cond=cond)

    def is_player(self, user):
        """
        Decide if a user is a player of the game.

        Parameters
        ----------
        user : ClientManager.Client
            User to test.

        Returns
        -------
        bool
            True if the user is a player, False otherwise.

        """

        return self._playergroup.is_player(user)

    def add_player(self, user):
        """
        Make a user a player of the game. By default this player will not be a leader. It will
        also subscribe the game ot the player so it can listen to its updates.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the game.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.UserHasNoCharacterError
            If the user has no character but the game requires that all players have characters.
        GameError.UserNotInvitedError
            If the game requires players be invited to be added and the user is not invited.
        GameError.UserAlreadyPlayerError
            If the user to add is already a user of the game.
        GameError.UserHitGameConcurrentLimitError
            If the player has reached any of the games it belongs to managed by this game's
            manager concurrent player membership limit, or by virtue of joining this game they
            will violate this game's concurrent player membership limit.
        GameError.GameIsFullError
            If the game reached its player limit.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError
        # If the game demands the player has a character, check that too
        if self._require_character and not user.has_character():
            raise GameError.UserHasNoCharacterError

        try:
            self._playergroup.add_player(user)
        except PlayerGroupError.UserNotInvitedError:
            raise GameError.UserNotInvitedError
        except PlayerGroupError.UserAlreadyPlayerError:
            raise GameError.UserAlreadyPlayerError
        except PlayerGroupError.UserHitGroupConcurrentLimitError:
            raise GameError.UserHitGameConcurrentLimitError
        except PlayerGroupError.GroupIsFullError:
            raise GameError.GameIsFullError

        self.listener.subscribe(user)
        self._manager._check_structure()

    def remove_player(self, user):
        """
        Make a user be no longer a player of this game. If they were part of a team managed by
        this game, they will also be removed from said team. It will also unsubscribe the game
        from the player so it will no longer listen to its updates.

        If the game required that there it always had players and by calling this method the
        game had no more players, the game will automatically be scheduled for deletion.

        Parameters
        ----------
        user : ClientManager.Client
            User to remove.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.UserNotPlayerError
            If the user to remove is already not a player of this game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        if not self._playergroup.is_player(user):
            raise GameError.UserNotPlayerError

        user_teams = self.get_teams_of_user(user)
        for team in user_teams:
            team.remove_player(user)

        try:
            self._playergroup.remove_player(user)
        except PlayerGroupError.UserNotPlayerError:
            # Should not have made it here as we already asserted the user is a player
            raise RuntimeError(self)

        self.listener.unsubscribe(user)

        # Detect if the internal player group was scheduled for deletion
        if self._playergroup.is_unmanaged():
            self.destroy()

        self._manager._check_structure()

    def get_invitations(self, cond=None):
        """
        Return (a shallow copy of) the set of invited users of this game that satisfy a
        condition if given.

        Parameters
        ----------
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that all invited users returned satisfy. Defaults to None (no checked
            conditions).

        Returns
        -------
        set of ClientManager.Client
            The (filtered) invited users of this game.

        """

        return self._playergroup.get_invitations(cond=cond)

    def is_invited(self, user):
        """
        Decide if a user is invited to the game.

        Parameters
        ----------
        user : ClientManager.Client
            User to test.

        Raises
        ------
        GameError.UserAlreadyPlayerError
            If the user is a player of this game.

        Returns
        -------
        bool
            True if the user is invited, False otherwise.

        """

        try:
            return self._playergroup.is_invited(user)
        except PlayerGroupError.UserAlreadyPlayerError:
            raise GameError.UserAlreadyPlayerError

    def add_invitation(self, user):
        """
        Mark a user as invited to this game.

        Parameters
        ----------
        user : ClientManager.Client
            User to invite to the game.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.GameDoesNotTakeInvitationsError
            If the game does not require users be invited to the game.
        GameError.UserAlreadyInvitedError
            If the player to invite is already invited to the game.
        GameError.UserAlreadyPlayerError
            If the player to invite is already a player of the game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            self._playergroup.add_invitation(user)
        except PlayerGroupError.GroupDoesNotTakeInvitationsError:
            raise GameError.GameDoesNotTakeInvitationsError
        except PlayerGroupError.UserAlreadyInvitedError:
            raise GameError.UserAlreadyInvitedError
        except PlayerGroupError.UserAlreadyPlayerError:
            raise GameError.UserAlreadyPlayerError

        self._manager._check_structure()

    def remove_invitation(self, user):
        """
        Mark a user as no longer invited to this game (uninvite).

        Parameters
        ----------
        user : ClientManager.Client
            User to uninvite.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.GameDoesNotTakeInvitationsError
            If the game does not require users be invited to the game.
        GameError.UserNotInvitedError
            If the user to uninvite is already not invited to this game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            self._playergroup.remove_invitation(user)
        except PlayerGroupError.GroupDoesNotTakeInvitationsError:
            raise GameError.GameDoesNotTakeInvitationsError
        except PlayerGroupError.UserNotInvitedError:
            raise GameError.UserNotInvitedError

        self._manager._check_structure()

    def get_leaders(self, cond=None):
        """
        Return (a shallow copy of) the set of leaders of this game that satisfy a condition
        if given.

        Parameters
        ----------
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that all leaders returned satisfy. Defaults to None (no checked
            conditions).

        Returns
        -------
        set of ClientManager.Client
            The (filtered) leaders of this game.

        """

        return self._playergroup.get_leaders(cond=cond)

    def get_regulars(self, cond=None):
        """
        Return (a shallow copy of) the set of players of this game that are regulars and satisfy
        a condition if given.

        Parameters
        ----------
        cond : types.LambdaType: ClientManager.Client -> bool, optional
            Condition that all regulars returned satisfy. Defaults to None (no checked
            conditions).

        Returns
        -------
        set of ClientManager.Client
            The (filtered) regulars of this game.

        """
        return self._playergroup.get_regulars(cond=cond)

    def is_leader(self, user):
        """
        Decide if a user is a leader of the game.

        Parameters
        ----------
        user : ClientManager.Client
            User to test.

        Raises
        ------
        GameError.UserNotPlayerError
            If the player to test is not a player of this game.

        Returns
        -------
        bool
            True if the player is a user, False otherwise.

        """

        try:
            return self._playergroup.is_leader(user)
        except PlayerGroupError.UserNotPlayerError:
            raise GameError.UserNotPlayerError

    def add_leader(self, user):
        """
        Set a user as leader of this game (promote to leader).

        Parameters
        ----------
        user : ClientManager.Client
            Player to promote to leader.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.UserNotPlayerError
            If the player to promote is not a player of this game.
        GameError.UserAlreadyLeaderError
            If the player to promote is already a leader of this game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            self._playergroup.add_leader(user)
        except PlayerGroupError.UserNotPlayerError:
            raise GameError.UserNotPlayerError
        except PlayerGroupError.UserAlreadyLeaderError:
            raise GameError.UserAlreadyLeaderError

        self._manager._check_structure()

    def remove_leader(self, user):
        """
        Make a user no longer leader of this game (demote).

        Parameters
        ----------
        user : ClientManager.Client
            User to demote.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.UserNotPlayerError
            If the player to demote is not a player of this game.
        GameError.UserNotLeaderError
            If the player to demote is already not a leader of this game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            self._playergroup.remove_leader(user)
        except PlayerGroupError.UserNotPlayerError:
            raise GameError.UserNotPlayerError
        except PlayerGroupError.UserNotLeaderError:
            raise GameError.UserNotLeaderError

        self._manager._check_structure()

    def new_timer(self, timer_type=None, start_value=None, tick_rate=1,
                  min_value=None, max_value=None, auto_restart=False, auto_destroy=True):
        """
        Create a new timer with given parameters managed by this game.

        Parameters
        ----------
        timer_type : TimerManager.Timer, optional
            Class of timer that will be produced. Defaults to None (and converted to
            TimerManager.Timer)
        start_value : float, optional
            Number of seconds the apparent timer the timer will initially have. Defaults
            to None (will use the default from `timer_type`).
        tick_rate : float, optional
            Starting rate in timer seconds/IRL seconds at which the timer will tick. Defaults to
            None (will use the default from `timer_type`).
        min_value : float, optional
            Minimum value the apparent timer may take. If the timer ticks below this, it will
            end automatically. It must be a non-negative number. Defaults to None (will use the
            default from `timer_type`.)
        max_value : float, optional
            Maximum value the apparent timer may take. If the timer ticks above this, it will
            end automatically. Defaults to None (will use the default from `timer_type`).
        auto_restart : bool, optional
            If True, the timer will reset without terminating back to its max value if the tick rate
            was non-negative and the timer went below its min value, or back to its max value if
            the tick rate was negative and the timer went above its max value. If False, the
            timer will terminate once either of the two conditions is satisfied without restarting.
            Defaults to False.
        auto_destroy : bool, optional
            If True, the game will automatically delete the timer once it is terminated by it
            ticking out or manual termination. If False, no such automatic deletion will take place.
            Defaults to True.

        Returns
        -------
        TimerManager.Timer
            The created timer.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.GameTooManyTimersError
            If the game is already managing its maximum number of timers.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            timer = self._timer_manager.new_timer(timer_type=timer_type,
                                                  start_value=start_value,
                                                  tick_rate=tick_rate,
                                                  min_value=min_value,
                                                  max_value=max_value,
                                                  auto_restart=auto_restart,
                                                  auto_destroy=auto_destroy)
        except TimerError.ManagerTooManyTimersError:
            raise GameError.GameTooManyTimersError

        self._manager._check_structure()
        return timer

    def delete_timer(self, timer):
        """
        Delete a timer managed by this game, terminating it first if needed.

        Parameters
        ----------
        timer : TimerManager.Timer
            The timer to delete.

        Returns
        -------
        str
            The ID of the timer that was deleted.

        Raises
        ------
        GameError.GameDoesNotManageTimerError
            If the game does not manage the target timer.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            timer_id = self._timer_manager.delete_timer(timer)
        except TimerError.ManagerDoesNotManageTimerError:
            raise GameError.GameDoesNotManageTimerError

        self._manager._check_structure()
        return timer_id

    def get_timers(self):
        """
        Return (a shallow copy of) the timers this game manages.

        Returns
        -------
        set of TimerManager.Timer
            Timers this game manages.

        """

        return self._timer_manager.get_timers()

    def get_timer_by_id(self, timer_id):
        """
        If `timer_tag` is the ID of a timer managed by this game, return that timer.

        Parameters
        ----------
        timer_id: str
            ID of timer this game manages.

        Returns
        -------
        TimerManager.Timer
            The timer whose ID matches the given ID.

        Raises
        ------
        GameError.GameInvalidTimerIDError:
            If `timer_tag` is a str and it is not the ID of a timer this game manages.

        """

        try:
            return self._timer_manager.get_timer_by_id(timer_id)
        except TimerError.ManagerInvalidTimerIDError:
            raise GameError.GameInvalidTimerIDError

    def get_timer_ids(self):
        """
        Return (a shallow copy of) the IDs of all timers managed by this game.

        Returns
        -------
        set of str
            The ID of the timer that matches the given tag.

        """

        return self._timer_manager.get_timer_ids()

    def new_team(self, team_type=None, creator=None, player_limit=None,
                 require_invitations=False, require_players=True, require_leaders=True):
        """
        Create a new team managed by this game.

        Parameters
        ----------
        team_type : _Team
            Class of team that will be produced. Defaults to None (and converted to the
            default team created by games, namely, _Team).
        creator : ClientManager.Client, optional
            The player who created this team. If set, they will also be added to the team if
            possible. The creator must be a player of this game. Defaults to None.
        player_limit : int, optional
            The maximum number of players the team may have. Defaults to None (no limit).
        require_invitations : bool, optional
            If True, users can only be added to the team if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the team has no players left, the team will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the team has no leaders left, the team will choose a
            leader among any remaining players left; if no players are left, the next player
            added will be made leader. If False, no such automatic assignment will happen.
            Defaults to True.

        Returns
        -------
        _Team
            The created team.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.GameTooManyTeamsError
            If the game is already managing its maximum number of teams.
        GameError.UserInAnotherTeamError
            If `creator` is not None and already part of a team managed by this game.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        if team_type is None:
            team_type = _Team

        try:
            team = self._team_manager.new_group(playergroup_type=team_type, creator=creator,
                                                player_limit=player_limit,
                                                player_concurrent_limit=1,
                                                require_invitations=require_invitations,
                                                require_players=require_players,
                                                require_leaders=require_leaders)
        except PlayerGroupError.ManagerTooManyGroupsError:
            raise GameError.GameTooManyTeamsError
        except PlayerGroupError.UserHitGroupConcurrentLimitError:
            raise GameError.UserInAnotherTeamError
        team._game = self._playergroup
        return team

    def delete_team(self, team):
        """
        Delete a team managed by this game.

        Parameters
        ----------
        team : _Team
            The team to delete.

        Returns
        -------
        (str, set of ClientManager.Client)
            The ID and players of the team that was deleted.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameError.GameDoesNotManageTeamError
            If the game does not manage the target team.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError

        try:
            self._team_manager.delete_group(team)
        except PlayerGroupError.ManagerDoesNotManageGroupError:
            raise GameError.GameDoesNotManageTeamError

    def manages_team(self, team):
        """
        Return True if the team is managed by this game, False otherwise.

        Parameters
        ----------
        team : _Team
            The team to check.

        Returns
        -------
        bool
            True if the game manages this team, False otherwise.

        """

        return self._team_manager.manages_group(team)

    def get_teams(self):
        """
        Return (a shallow copy of) the teams this game manages.

        Returns
        -------
        set of _Team
            Teams this game manages.

        """

        return self._team_manager.get_groups().copy()

    def get_team_by_id(self, team_id):
        """
        If `team_id` is the ID of a team managed by this manager, return the team.

        Parameters
        ----------
        team_id : str
            ID of the team this game manages.

        Returns
        -------
        _Team
            The team that matches the given ID.

        Raises
        ------
        GameError.GameInvalidTeamIDError:
            If `team_id` is not the ID of a team this game manages.

        """

        try:
            return self._team_manager.get_group_by_id(team_id)
        except PlayerGroupError.ManagerInvalidGroupIDError:
            raise GameError.GameInvalidTeamIDError

    def get_team_limit(self):
        """
        Return the team limit of this game.

        Returns
        -------
        int
            Team limit.

        """

        return self._team_manager.get_group_limit()

    def get_team_ids(self):
        """
        Return (a shallow copy of) the IDs of all teams managed by this game.

        Returns
        -------
        set of str
            The IDs of all managed teams.

        """

        return self._team_manager.get_group_ids().copy()

    def get_teams_of_user(self, user):
        """
        Return (a shallow copy of) the teams managed by this game user `user` is a
        player of. If the user is part of no such team, an empty set is returned.

        Parameters
        ----------
        user : ClientManager.Client
            User whose teams will be returned.

        Returns
        -------
        set of _Team
            Teams the player belongs to.

        """

        return self._team_manager.get_groups_of_user(user).copy()

    def get_users_in_team(self):
        """
        Return (a shallow copy of) all the users that are part of some team managed by
        this manager.

        Returns
        -------
        set of ClientManager.Client
            Users in some managed team.

        """

        return self._team_manager.get_users_in_groups().copy()

    def get_available_team_id(self):
        """
        Get a team ID that no other team managed by this team has.

        Returns
        -------
        str
            A unique player group ID.

        Raises
        ------
        GameError.GameTooManyTeamsError
            If the game is already managing its maximum number of teams.

        """

        try:
            return self._team_manager.get_available_group_id()
        except PlayerGroupError.ManagerTooManyGroupsError:
            return GameError.GameTooManyTeamsError

    def is_unmanaged(self):
        """
        Return True if this game is unmanaged, False otherwise.

        Returns
        -------
        bool
            True if unmanaged, False otherwise.

        """

        return self._playergroup.is_unmanaged()

    def destroy(self):
        """
        Mark this game as destroyed and notify its manager so that it is deleted.
        If the game is already destroyed, this function does nothing.
        A game marked for destruction will delete all of its timers, teams, remove all its
        players and unsubscribe it from updates of its former players.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        if self._unmanaged:
            return
        self._unmanaged = True

        for timer in self._timer_manager.get_timers():
            self._timer_manager.delete_timer(timer)
        for team in self._team_manager.get_groups():
            team.destroy()

        # Players (and subscriptions to them) are handled in the manager's delete code.
        try:
            self._manager.delete_game(self)
        except GameError.ManagerDoesNotManageGameError:
            # Should only happen if .destroy() was called from a delete_game
            # At this point it is safe not to call delete_game
            pass

        self._check_structure()

    def has_ever_had_players(self):
        """
        Return True if a player has ever been added to this game, False otherwise.

        Returns
        -------
        bool
            True if the game has ever had a player added, False otherwise.

        """

        return self._playergroup.has_ever_had_players()

    def _on_client_inbound_ms_check(self, player, contents=None):
        """
        Default callback for game player signaling it wants to check if sending an IC message
        is appropriate. The IC arguments can be passed by reference, so this also serves as an
        opportunity to modify the IC message if neeeded.

        To indicate a message should not be sent, some TsuserverException can be raised. The
        message of the exception will be sent to the client.

        Parameters
        ----------
        player : ClientManager.Client
            Player that wants to send the IC message.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Returns
        -------
        None.

        """

        print('Player', player, 'wants to check sent', contents)

    def _on_client_inbound_ms(self, player, contents=None):
        """
        Default callback for game player signaling it has sent an IC message.

        By default does nothing.

        Parameters
        ----------
        player : ClientManager.Client
            Player that signaled it has sent an IC message.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Returns
        -------
        None.

        """

        print('Player', player, 'sent', contents)

    def _on_client_change_character(self, player, old_char_id=None, new_char_id=None):
        """
        Default callback for game player signaling it has changed character.

        By default it only checks if the player is now no longer having a character. If that is
        the case and the game requires all players have characters, the player is automatically
        removed.

        Parameters
        ----------
        player : ClientManager.Client
            Player that signaled it has changed character.
        old_char_id : int, optional
            Previous character ID. The default is None.
        new_char_id : int, optional
            New character ID. The default is None.

        Returns
        -------
        None.

        """

        print('Player', player, 'changed character from', old_char_id, 'to', new_char_id)
        if self._require_character and not player.has_character():
            self.remove_player(player)

        self._check_structure()

    def _on_client_destroyed(self, player):
        """
        Default callback for game player signaling it was destroyed, for example, as a result
        of a disconnection.

        By default it only removes the player from the game. If the game is already unmanaged or
        the player is not in the game, this callback does nothing.

        Parameters
        ----------
        player : ClientManager.Client
            Player that signaled it was destroyed.

        Returns
        -------
        None.

        """

        print('Player', player, 'was destroyed', self)
        if self.is_unmanaged():
            return
        if player not in self.get_players():
            return
        self.remove_player(player)

        self._check_structure()

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        team_players = self._team_manager.get_users_in_groups()
        game_players = self._playergroup.get_players()
        team_not_in_game = {player for player in team_players if player not in game_players}
        err = (f'For game {self}, expected that every player in the set {team_players} of all '
               f'players in a team managed by the game is in the set {game_players} of players '
               f'of the game, found the following players that did not satisfy this: '
               f'{team_not_in_game}')
        assert team_players.issubset(game_players), err

        # 2.
        internal_unmanaged = self._playergroup.is_unmanaged()
        self_unmanaged = self.is_unmanaged()

        err = (f'For game {self}, expected that both itself and its internal player group '
               f'were either both unmanaged or both not unmanaged, found that itself was '
               f'{"" if self_unmanaged else "not"}unmanaged but its playergroup was '
               f'{"" if internal_unmanaged else "not"}unmanaged.')
        assert internal_unmanaged == self_unmanaged, err

        # 3.
        listener_parents = {obj.get_parent() for obj in self.listener.get_subscriptions()}
        for player in self.get_players():
            err = (f'For game {self}, expected that its player {player} was among its '
                   f'subscriptions {listener_parents} found it was not.')
            assert player in listener_parents, err

        # 4.
        if self._require_character:
            for player in self.get_players():
                err = (f'For game with areas {self} that expected all its players had '
                       f'characters, found player {player} did not have a character.')
                assert player.has_character(), err

        # 4.
        self._playergroup._check_structure()
        self._timer_manager._check_structure()
        self._team_manager._check_structure()

    def __str__(self):
        """
        Return a string representation of this game.

        Returns
        -------
        str
            Representation.

        """

        return (f"Game::{self.get_id()}:"
                f"{self.get_players()}:{self.get_leaders()}:{self.get_invitations()}"
                f"{self.get_timers()}:"
                f"{self.get_teams()}")

    def __repr__(self):
        """
        Return a representation of this game.

        Returns
        -------
        str
            Printable representation.

        """

        return (f'_Game(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'player_limit={self._playergroup._player_limit}, '
                f'player_concurrent_limit={self.get_player_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager.get_group_limit()}, '
                f'timer_limit={self._timer_manager.get_timer_limit()} || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_timers()}, '
                f'teams={self.get_teams()})')

class GameManager:
    """
    A mutable data type for a manager for games.

    Each game is managed by a game manager. Only this manager is allowed to execute any public
    methods on them. Each manager may also have a game limit (beyond which it will not manage any
    more groups).

    Contains methods for creating and deleting games, as well as some observer methods.

    """

    # (Private) Attributes
    # --------------------
    # _server : TsuserverDR
    #     Server the game manager belongs to.
    # _default_game_type : _Game or functools.partial
    #     The type of game this game manager will create by default when ordered to create a new
    #     one.
    # _playergroup_manager : PlayerGroupManager
    #     Internal player group manager that handles all game functions.
    # _id_to_game : dict of str to _Game
    #     Mapping of game IDs to games that this manager manages.

    # Invariants
    # ----------
    # 1. `self._playergroup_manager.get_group_ids()` and `self._id_to_game.keys()` are equal.
    # 2. For each pair `(game_id, game)` in `self._id_to_game.items()`:
    #     a. `game.get_id() == game_id`.


    def __init__(self, server, game_limit=None, default_game_type=None,
                 available_id_producer=None):
        """
        Create a game manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this game manager belongs to.
        game_limit : int, optional
            The maximum number of games this manager can handle. Defaults to None (no limit).
        default_game_type : _Game, optional
            The default type of game this manager will create. Defaults to None (and then
            converted to Game).
        available_id_producer : typing.types.FunctionType, optional
            Function to produce available game IDs. It will override the built-in class method
            get_available_game_id. Defaults to None (and then converted to the built-in
            get_available_game_id).

        """

        if default_game_type is None:
            default_game_type = _Game
        if available_id_producer is None:
            available_id_producer = self.get_available_game_id
        self.get_available_game_id = available_id_producer

        self._server = server
        self._playergroup_manager = PlayerGroupManager(server, playergroup_limit=game_limit,
                                                       available_id_producer=available_id_producer)
        self._default_game_type = default_game_type
        self._id_to_game = dict()

    def new_game(self, game_type=None, creator=None, player_limit=None,
                 player_concurrent_limit=1, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None, timer_limit=None):
        """
        Create a new game managed by this manager.

        Parameters
        ----------
        game_type : _Game or functools.partial
            Class of game that will be produced. Defaults to None (and converted to the default
            game created by this game manager).
        creator : ClientManager.Client, optional
            The player who created this game. If set, they will also be added to the game.
            Defaults to None.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the game supports. If None, it
            indicates the game has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of games managed by `self` that any player
            of this game to create may belong to, including this game to create. If None, it
            indicates that this game does not care about how many other games managed by `self`
            each of its players belongs to. Defaults to 1 (a player may not be in another game
            managed by `self` while in this game).
        require_invitations : bool, optional
            If True, users can only be added to the game if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the game loses all its players, the game will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the game has no leaders left, the game will choose a leader
            among any remaining players left; if no players are left, the next player added will
            be made leader. If False, no such automatic assignment will happen. Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the game, and players
            that switch to something other than a character will be automatically removed from the
            game. If False, no such checks are made. A player without a character is considered
            one where player.has_character() returns False. Defaults to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the game will support. If None, it
            indicates the game will have no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of timers the game will support. If None, it
            indicates the game will have no timer limit. Defaults to None.

        Returns
        -------
        _Game
            The created game.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.
        Any error from the created game's add_player(creator)
            If the game cannot add `creator` as a player if given one.

        """

        game_id = self.get_available_game_id()
        def_args = (
            self._server,
            self,
            game_id,
            )

        def_kwargs = {
            'player_limit': player_limit,
            'player_concurrent_limit': player_concurrent_limit,
            'require_invitations': require_invitations,
            'require_players': require_players,
            'require_leaders': require_leaders,
            'require_character': require_character,
            'team_limit': team_limit,
            'timer_limit': timer_limit,
            'playergroup_manager': self._playergroup_manager,
            }

        new_game_type = Constants.make_partial_from(game_type, self._default_game_type,
                                                    *def_args, **def_kwargs)

        # Implementation detail
        # PlayerGroupError.ManagerTooManyGroupsError cannot be thrown as we overrode the only
        # method in there that could have thrown that with something that throws
        # GameError.ManagerTooManyGamesError
        game = new_game_type()
        self._id_to_game[game_id] = game

        # Add creator manually. This is because adding it via .new_group will not make it run
        # the add_player code of the game, but only of the internal player group.
        try:
            if creator:
                game.add_player(creator)
        except GameError as ex:
            # Discard game
            self.delete_game(game)
            raise ex

        self._check_structure()
        return game

    def delete_game(self, game):
        """
        Delete a game managed by this manager, so all its players no longer belong to this game,
        and return the ID and set of players of the former game.

        Parameters
        ----------
        game : _Game
            The game to delete.

        Returns
        -------
        (str, set of ClientManager.Client)
            The ID and players of the game that was deleted.

        Raises
        ------
        GameError.ManagerDoesNotManageGameError
            If the manager does not manage the target game.

        """

        # We have to retrieve the internal playergroup of the game
        # We can take advantage of the fact the internal playergroup and the game itself both
        # have the same ID by design.

        game_id = game.get_id()
        if game_id not in self._id_to_game:
            raise GameError.ManagerDoesNotManageGameError

        game = self._id_to_game.pop(game_id)
        game.destroy()

        try:
            playergroup = self._playergroup_manager.get_group_by_id(game_id)
            playergroup_id, players = self._playergroup_manager.delete_group(playergroup)
        except PlayerGroupError.ManagerInvalidGroupIDError:
            # This code will only run if this code came as a result of .destroy() on the
            # original game doing some work already (namely updating the playergroup manager) and
            # a previous call to destroy the playergroup (say, by it losing all its players
            # automatically). In this case, the group ID is trivial and there are no players
            # (as the group was already destroyed).
            playergroup_id, players = game_id, set()

        for player in players:
            game.listener.unsubscribe(player)

        self._check_structure()
        return playergroup_id, players

    def manages_game(self, game):
        """
        Return True if the game is managed by this manager, False otherwise.

        Parameters
        ----------
        game : _Game
            The player group to check.

        Returns
        -------
        bool
            True if the manager manages this game, False otherwise.

        """

        return game in self._id_to_game.values()

    def get_games(self):
        """
        Return (a shallow copy of) the games this manager manages.

        Returns
        -------
        set of _Game
            Games this manager manages.

        """

        return set(self._id_to_game.values())

    def get_game_by_id(self, game_id) -> _Game:
        """
        If `game_id` is the ID of a game managed by this manager, return that.

        Parameters
        ----------
        game_id : str
            ID of the game this manager manages.

        Returns
        -------
        _Game
            The game with that ID.

        Raises
        ------
        GameError.ManagerInvalidGameIDError
            If `game_id` is not the ID of a game this manager manages.

        """

        try:
            return self._id_to_game[game_id]
        except KeyError:
            raise GameError.ManagerInvalidGameIDError

    def get_game_limit(self):
        """
        Return the game limit of this manager.

        Returns
        -------
        int
            Game limit.

        """

        return self._playergroup_manager.get_group_limit()

    def get_game_ids(self):
        """
        Return (a shallow copy of) the IDs of all games managed by this manager.

        Returns
        -------
        set of str
            The IDs of all managed games.

        """

        return set(self._id_to_game.keys())

    def get_games_of_user(self, user):
        """
        Return (a shallow copy of) the games managed by this manager user `user` is a
        player of. If the user is part of no such game, an empty set is returned.

        Parameters
        ----------
        user : ClientManager.Client
            User whose games will be returned.

        Returns
        -------
        set of _Game
            Games the player belongs to.

        """

        playergroups = self._playergroup_manager.get_groups_of_user(user)
        playergroup_ids = {playergroup.get_id() for playergroup in playergroups}
        games = {self._id_to_game[playergroup_id] for playergroup_id in playergroup_ids}
        return games

    def get_users_in_games(self):
        """
        Return (a shallow copy of) all the users that are part of some game managed by this
        manager.

        Returns
        -------
        set of ClientManager.Client
            Users in some managed game.

        """

        return self._playergroup_manager.get_users_in_groups().copy()

    def get_available_game_id(self):
        """
        Get a game ID that no other game managed by this manager has.

        Returns
        -------
        str
            A unique game ID.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.

        """

        game_number = 0
        game_limit = self.get_game_limit()
        while game_limit is None or game_number < game_limit:
            new_game_id = "g{}".format(game_number)
            if new_game_id not in self.get_game_ids():
                return new_game_id
            game_number += 1
        raise GameError.ManagerTooManyGamesError

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

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        proper_ids = self._playergroup_manager.get_group_ids()
        my_ids = set(self._id_to_game.keys())

        err = (f'For game manager {self}, expected the set of proper game IDs {proper_ids} and '
               f'its game IDs {my_ids} to be the same, found they were not.')
        assert proper_ids == my_ids, err

        # 2.
        for (my_id, game) in self._id_to_game.items():
            proper_id = game.get_id()
            err = (f'For game manager {self}, expected the proper game ID {proper_id} of game '
                   f'{game} and the one the manager appointed for it to be the same, found they '
                   f'were not.')
            assert proper_id == my_id, err

        # 3.
        for game in self._id_to_game.values():
            game._check_structure()

    def __repr__(self):
        """
        Return a representation of this game manager.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"GameManager(server, game_limit={self.get_game_limit()}, "
                f"default_game_type={self._default_game_type}, "
                f"|| "
                f"_id_to_game={self._id_to_game}, "
                f"id={self.get_id()})")
