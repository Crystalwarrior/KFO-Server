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

from server.exceptions import GameError, PlayerGroupError, SteptimerError
from server.playergroup_manager import PlayerGroupManager
from server.steptimer_manager import SteptimerManager

"""
Module that contains the GameManager class, which itself contains the Game subclass.

Games are player groups that maintain first-in-first-out queues of arbitrary many TsuserverDR
packets to send to its players.

Each game is managed by a game manager, which iself are player group managers.
"""

class GameManager(PlayerGroupManager):

    class Game():
        def __init__(self, server, manager, game_id, player_limit=None,
                     require_invitations=False, require_players=True, require_leaders=True,
                     team_limit=None, timer_limit=None):
            self._init_ready = False
            self._team_manager = PlayerGroupManager(server, playergroup_limit=team_limit)
            self._timer_manager = SteptimerManager(server, steptimer_limit=timer_limit)
            self._game = PlayerGroupManager.PlayerGroup(server, manager, game_id,
                                                        player_limit=player_limit,
                                                        require_invitations=require_invitations,
                                                        require_players=require_players,
                                                        require_leaders=require_leaders)
            self._init_ready = True

        def get_id(self):
            """
            Return the ID of this game.

            Returns
            -------
            str
                The ID.

            """

            return self._game.get_id()

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

            return self._game.get_players(cond=cond)

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

            return self._game.is_player(user)

        def add_player(self, user):
            """
            Make a user a player of the game. By default this player will not be a leader.

            Parameters
            ----------
            user : ClientManager.Client
                User to add to the game.

            Raises
            ------
            GameError.UserNotInvitedError
                If the game requires players be invited to be added and the user is not invited.
            GameError.UserAlreadyPlayerError
                If the user to add is already a user of the game.
            GameError.UserInAnotherGameError
                If the player is already in another game managed by this manager.
            GameError.GroupIsFullError
                If the game reached its playership limit.

            """

            try:
                self._game.add_player(user)
            except PlayerGroupError.UserNotInvitedError as exception:
                raise GameError.UserNotInvitedError from exception
            except PlayerGroupError.UserAlreadyPlayerError as exception:
                raise GameError.UserAlreadyPlayerError from exception
            except PlayerGroupError.UserInAnotherGroupError as exception:
                raise GameError.UserInAnotherGameError from exception
            except PlayerGroupError.GroupIsFullError as exception:
                raise GameError.GameIsFullError from exception

        def remove_player(self, user):
            """
            Make a user be no longer a player of this game.

            Parameters
            ----------
            user : ClientManager.Client
                User to remove.

            Raises
            ------
            GameError.UserNotPlayerError
                If the user to remove is already not a player of this game.

            """

            try:
                self._game.remove_player(user)
            except PlayerGroupError.UserNotPlayerError as exc:
                raise GameError.UserNotPlayerError from exc

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

            return self._game.get_invitations(cond=None)

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
                return self._game.is_invited(user)
            except PlayerGroupError.UserAlreadyPlayerError as exception:
                raise GameError.UserAlreadyPlayerError from exception

        def add_invitation(self, user):
            """
            Mark a user as invited to this game.

            Parameters
            ----------
            user : ClientManager.Client
                User to invite to the game.

            Raises
            ------
            GameError.GameDoesNotTakeInvitationsError
                If the game does not require users be invited to the game.
            GameError.UserAlreadyInvitedError
                If the player to invite is already invited to the game.
            GameError.UserAlreadyPlayerError
                If the player to invite is already a player of the game.

            """

            try:
                self._game.add_invitation(user)
            except PlayerGroupError.GroupDoesNotTakeInvitationsError as exception:
                raise GameError.GameDoesNotTakeInvitationsError from exception
            except PlayerGroupError.UserAlreadyInvitedError as exception:
                raise GameError.UserAlreadyInvitedError from exception
            except PlayerGroupError.UserAlreadyPlayerError as exception:
                raise GameError.UserAlreadyPlayerError from exception

        def remove_invitation(self, user):
            """
            Mark a user as no longer invited to this game (uninvite).

            Parameters
            ----------
            user : ClientManager.Client
                User to uninvite.

            Raises
            ------
            GameError.GameDoesNotTakeInvitationsError
                If the game does not require users be invited to the game.
            GameError.UserNotInvitedError
                If the user to uninvite is already not invited to this game.

            """

            try:
                self._game.remove_invitation(user)
            except PlayerGroupError.GroupDoesNotTakeInvitationsError as exception:
                raise GameError.GameDoesNotTakeInvitationsError from exception
            except PlayerGroupError.UserNotInvitedError as exception:
                raise GameError.UserNotInvitedError from exception

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

            return self._game.get_leaders(cond=cond)

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
                return self._game.is_leader(user)
            except PlayerGroupError.UserNotPlayerError as exception:
                raise GameError.UserNotPlayerError from exception

        def add_leader(self, user):
            """
            Set a user as leader of this game (promote to leader).

            Parameters
            ----------
            user : ClientManager.Client
                Player to promote to leader.

            Raises
            ------
            GameError.UserNotPlayerError
                If the player to promote is not a player of this game.
            GameError.UserAlreadyLeaderError
                If the player to promote is already a leader of this game.

            """

            try:
                self._game.add_leader(user)
            except PlayerGroupError.UserNotPlayerError as exception:
                raise GameError.UserNotPlayerError from exception
            except PlayerGroupError.UserAlreadyLeaderError as exception:
                raise GameError.UserAlreadyLeaderError from exception

        def remove_leader(self, user):
            """
            Make a user no longer leader of this game (demote).

            Parameters
            ----------
            user : ClientManager.Client
                User to demote.

            Raises
            ------
            GameError.UserNotPlayerError
                If the player to demote is not a player of this game.
            GameError.UserNotLeaderError
                If the player to demote is already not a leader of this game.

            """

            try:
                self._game.remove_leader(user)
            except PlayerGroupError.UserNotPlayerError as exception:
                raise GameError.UserNotPlayerError from exception
            except PlayerGroupError.UserNotLeaderError as exception:
                raise GameError.UserNotLeaderError from exception

        def new_steptimer(self, steptimer_type=None, start_timer_value=None, timestep_length=None,
                          firing_interval=None, min_timer_value=None, max_timer_value=None):
            """
            Create a new steptimer with given parameters managed by this game.

            Parameters
            ----------
            steptimer_type : SteptimerManager.Steptimer, optional
                Class of steptimer that will be produced. Defaults to None (and converted to
                SteptimerManager.Steptimer)
            start_timer_value : float, optional
                Number of seconds the apparent timer the steptimer will initially have. Defaults
                to None (will use the default from `steptimer_type`).
            timestep_length : float, optional
                Number of seconds that tick from the apparent timer every step. Must be a non-
                negative number at least `min_timer_value` and `max_timer_value`. Defaults to
                None (will use the default from `steptimer_type`).
            firing_interval : float, optional
                Number of seconds that must elapse for the apparent timer to tick. Defaults to None
                (and converted to abs(timestep_length))
            min_timer_value : float, optional
                Minimum value the apparent timer may take. If the timer ticks below this, it will
                end automatically. It must be a non-negative number. Defaults to None (will use the
                default from `steptimer_type`.)
            max_timer_value : float, optional
                Maximum value the apparent timer may take. If the timer ticks above this, it will
                end automatically. Defaults to None (will use the default from `steptimer_type`).

            Returns
            -------
            SteptimerManager.Steptimer
                The created steptimer.

            Raises
            ------
            GameError.GameTooManyTimersError
                If the game is already managing its maximum number of steptimers.

            """

            try:
                return self._timer_manager.new_steptimer(steptimer_type=steptimer_type,
                                                         start_timer_value=start_timer_value,
                                                         timestep_length=timestep_length,
                                                         firing_interval=firing_interval,
                                                         min_timer_value=min_timer_value,
                                                         max_timer_value=max_timer_value)
            except SteptimerError.ManagerTooManySteptimersError as exception:
                raise GameError.GameTooManyTimersError from exception

        def delete_steptimer(self, steptimer):
            """
            Delete a steptimer managed by this game, terminating it first if needed.

            Parameters
            ----------
            steptimer : SteptimerManager.Steptimer
                The steptimer to delete.

            Returns
            -------
            str
                The ID of the steptimer that was deleted.

            Raises
            ------
            GameError.GameDoesNotManageSteptimerError
                If the game does not manage the target steptimer.

            """

            try:
                return self._timer_manager.delete_steptimer(steptimer)
            except SteptimerError.ManagerDoesNotManageSteptimerError as exception:
                raise GameError.GameDoesNotManageSteptimerError from exception

        def get_managed_steptimers(self):
            """
            Return (a shallow copy of) the steptimers this game manages.

            Returns
            -------
            set of SteptimerManager.Steptimer
                Steptimers this game manages.

            """

            return self._timer_manager.get_managed_steptimers()

        def get_steptimer(self, steptimer_tag):
            """
            If `steptimer_tag` is a steptimer managed by this game, return it.
            If it is a string and the ID of a steptimer managed by this game, return that steptimer.

            Parameters
            ----------
            steptimer_tag: SteptimerManager.Steptimer or str
                Steptimer this game manages.

            Returns
            -------
            SteptimerManager.Steptimer
                The steptimer that matches the given tag.

            Raises
            ------
            GameError.GameDoesNotManageSteptimerError:
                If `steptimer_tag` is a steptimer this game does not manage.
            GameError.GameInvalidTimerIDError:
                If `steptimer_tag` is a str and it is not the ID of a steptimer this game manages.

            """

            try:
                return self._timer_manager.get_steptimer_id(steptimer_tag)
            except SteptimerError.ManagerDoesNotManageSteptimerError as exception:
                raise GameError.GameDoesNotManageSteptimerError from exception
            except SteptimerError.ManagerInvalidIDError as exception:
                raise GameError.GameInvalidTimerIDError from exception

        def get_steptimer_id(self, steptimer_tag):
            """
            If `steptimer_tag` is the ID of a steptimer managed by this game, return it.
            If it is a steptimer managed by this game, return its ID.

            Parameters
            ----------
            steptimer_tag : SteptimerManager.Steptimer or str
                Steptimer this game manages.

            Returns
            -------
            str
                The ID of the steptimer that matches the given tag.

            Raises
            ------
            GameError.GameDoesNotManageSteptimerError:
                If `steptimer_tag` is a steptimer this game does not manage.
            GameError.GameInvalidTimerIDError:
                If `steptimer_tag` is a str and it is not the ID of a steptimer this game manages.

            """

            try:
                return self._timer_manager.get_steptimer_id(steptimer_tag)
            except SteptimerError.ManagerDoesNotManageSteptimerError as exception:
                raise GameError.GameDoesNotManageSteptimerError from exception
            except SteptimerError.ManagerInvalidIDError as exception:
                raise GameError.GameInvalidTimerIDError from exception

        def __str__(self):
            return (f"Game::"
                    f"{self._team_manager._id_to_group}:{self._team_manager._player_to_group}:"
                    f"{self._timer_manager._id_to_steptimer}:"
                    f"{self._game_.playergroup_id}:{self._game._players}:{self._game._leaders}")

        def __repr__(self):
            return (f"GameManager.Game(server, manager, '{self._game._playergroup_id}', "
                    f"player_limit={self._game._player_limit}, "
                    f"require_invitations={self._game._require_invitations}, "
                    f"require_players={self._game._require_players}, "
                    f"require_leaders={self._game._require_leaders}, "
                    f"team_limit={self._team_manager._playergroup_limit}, "
                    F"timer_limit={self._timer_manager._steptimer_limit})")

    """
    class Game(PlayerGroupManager.PlayerGroup, SteptimerManager, PlayerGroupManager):
        def __init__(self, server, manager, game_id, member_limit=None,
                     require_invitations=False, require_members=True, require_leaders=True,
                     team_limit=None, timer_limit=None):
            self._init_ready = False
            PlayerGroupManager.__init__(self, server, playergroup_limit=team_limit)
            SteptimerManager.__init__(self, server, steptimer_limit=timer_limit)
            PlayerGroupManager.PlayerGroup.__init__(self, server, manager, game_id,
                                                    member_limit=member_limit,
                                                    require_invitations=require_invitations,
                                                    require_members=require_members,
                                                    require_leaders=require_leaders)
            self._init_ready = True

        get_group()

        def _check_structure(self):
            if not self._init_ready:
                return
            PlayerGroupManager._check_structure()
            SteptimerManager._check_structure()
            PlayerGroupManager.PlayerGroup._check_structure()

        def __str__(self):
            return (f"Game::"
                    f"{self._id_to_group}:{self._player_to_group}:"
                    f"{self._id_to_steptimer}:"
                    f"{self._playergroup_id}:{self._members}:{self._leaders}")

        def __repr__(self):
            return (f"GameManager.Game(server, manager, '{self._playergroup_id}', "
                    f"member_limit={self._member_limit}, require_members={self._require_members}, "
                    f"require_leaders={self._require_leaders}, "
                    f"team_limit={self._playergroup_limit}, "
                    F"timer_limit={self._steptimer_limit})")
    """

    def _check_structure(self):
        super()._check_structure()
