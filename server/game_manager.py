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
Module that contains the GameManager class, which itself contains the Game and Team subclasses.

Games maintain a PlayerGroup-like structure and methods, but also allow the creation of teams with
thier players. Teams are proper PlayerGroups, and no player of a game can be part of two teams
managed by the same game. Players of a game need not be part of a team managed by the game, but a
team can only have players of the game as players of the team. Removing a player from a game
also removes them from their team if they were in any.

Games also maintain a SteptimerManager-like structure, allowing the creation of stpetimers
managed by the game.

Each game is managed by a game manager, which iself is a player group manager. Unless specified
otherwise in the games, a player may be part of two or more games managed by the same game manager.
"""

from server.exceptions import GameError, PlayerGroupError, SteptimerError
from server.playergroup_manager import PlayerGroupManager
from server.steptimer_manager import SteptimerManager

class GameManager(PlayerGroupManager):
    class Team(PlayerGroupManager.PlayerGroup):
        def __init__(self, server, manager, playergroup_id, player_limit=None,
                     concurrent_limit=None, require_invitations=False, require_players=True,
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
            game : GameManager.Game
                Game of this player group.
            player_limit : int or None, optional
                If an int, it is the maximum number of players the player group supports. If None,
                it indicates the player group has no player limit. Defaults to None.
            concurrent_limit : int or None, optional
                If an int, it is the maximum number of player groups managed by `manager` that any
                player of this group may belong to, including this group. If None, it indicates
                that this group does not care about how many other player groups managed by
                `manager` each of its players belongs to. It is always overwritten by 1 (a player
                may not be in another group managed by `manager` while in this group).
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

            super().__init__(server, manager, playergroup_id, player_limit=player_limit,
                             concurrent_limit=1, # Teams shall only allow 1 concurrent membership
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
                group's manager concurrent membership limit, or by virtue of joining this group
                will violate this group's concurrent membership limit.
            PlayerGroupError.UserNotPlayerError
                If the user to add is not a player of the game.

            """

            if not self._game.is_player(user):
                raise PlayerGroupError.UserNotPlayerError

            super().add_player(user)

    class Game():
        def __init__(self, server, manager, game_id, player_limit=None,
                     concurrent_limit=None, require_invitations=False, require_players=True,
                     require_leaders=True, team_limit=None, timer_limit=None):
            """
            Create a new game.

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
            concurrent_limit : int or None, optional
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
            team_limit : int or None, optional
                If an int, it is the maximum number of teams the game supports. If None, it
                indicates the game has no team limit. Defaults to None.
            timer_limit : int or None, optional
                If an int, it is the maximum number of steptimers the game supports. If None, it
                indicates the game has no steptimer limit. Defaults to None.
            """

            self._init_ready = False
            self._team_manager = PlayerGroupManager(server, playergroup_limit=team_limit,
                                                    playergroup_type=GameManager.Team)
            self._timer_manager = SteptimerManager(server, steptimer_limit=timer_limit)
            self._game = PlayerGroupManager.PlayerGroup(server, manager, game_id,
                                                        player_limit=player_limit,
                                                        concurrent_limit=concurrent_limit,
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
            GameError.UserHitGameConcurrentLimitError
                If the player has reached any of the games it belongs to managed by this game's
                manager concurrent membership limit, or by virtue of joining this game they
                will violate this game's concurrent membership limit.
            GameError.GroupIsFullError
                If the game reached its playership limit.

            """

            try:
                self._game.add_player(user)
            except PlayerGroupError.UserNotInvitedError as exception:
                raise GameError.UserNotInvitedError from exception
            except PlayerGroupError.UserAlreadyPlayerError as exception:
                raise GameError.UserAlreadyPlayerError from exception
            except PlayerGroupError.UserHitGroupConcurrentLimitError as exception:
                raise GameError.UserHitGameConcurrentLimitError from exception
            except PlayerGroupError.GroupIsFullError as exception:
                raise GameError.GameIsFullError from exception

        def remove_player(self, user):
            """
            Make a user be no longer a player of this game. If they were part of a team managed by
            this game, they will also be removed from said team.

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
                team = self.get_team_of_user(user)
            except GameError.UserInNoTeamError:
                pass
            else:
                team.remove_player(user)

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

            return self._game.get_invitations(cond=cond)

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
            except SteptimerError.ManagerInvalidSteptimerIDError as exception:
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
            except SteptimerError.ManagerInvalidSteptimerIDError as exception:
                raise GameError.GameInvalidTimerIDError from exception

        def new_team(self, team_type=None, creator=None, player_limit=None,
                     require_invitations=False, require_players=True, require_leaders=True):
            """
            Create a new team managed by this game.

            Parameters
            ----------
            team_type : GameManager.Team
                Class of team that will be produced. Defaults to None (and converted to the
                default team created by games, namely, GameManager.Team).
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
            GameManager.Team
                The created team.

            Raises
            ------
            GameError.GameTooManyTeamsError
                If the game is already managing its maximum number of teams.
            GameError.UserInAnotherTeamError
                If `creator` is not None and already part of a team managed by this game.

            """

            if team_type is None:
                team_type = GameManager.Team

            try:
                team = self._team_manager.new_group(playergroup_type=team_type, creator=creator,
                                                    player_limit=player_limit,
                                                    concurrent_limit=1,
                                                    require_invitations=require_invitations,
                                                    require_players=require_players,
                                                    require_leaders=require_leaders)
                team._game = self._game
                return team
            except PlayerGroupError.ManagerTooManyGroupsError as exception:
                raise GameError.GameTooManyTeamsError from exception
            except PlayerGroupError.UserHitGroupConcurrentLimitError as exception:
                raise GameError.UserInAnotherTeamError from exception

        def delete_team(self, team):
            """
            Delete a team managed by this game, so all its players no longer belong to any team.

            Parameters
            ----------
            team : GameManager.Team
                The team to delete.

            Returns
            -------
            (str, set of ClientManager.Client)
                The ID and players of the team that was deleted.

            Raises
            ------
            GameError.GameDoesNotManageTeamError
                If the game does not manage the target team.

            """

            try:
                self._team_manager.delete_group(team)
            except PlayerGroupError.ManagerDoesNotManageGroupError as exception:
                raise GameError.GameDoesNotManageTeamError from exception

        def get_managed_teams(self):
            """
            Return (a shallow copy of) the teams this game manages.

            Returns
            -------
            set of GameManager.Team
                Teams this game manages.

            """

            return set(self._team_manager._id_to_group.values())

        def get_team_of_user(self, user):
            """
            Return the team managed by this game user `user` is a player of.

            Parameters
            ----------
            user : ClientManager.Client
                User whose team will be returned.

            Returns
            -------
            GameManager.Team
                Team the player belongs to.

            Raises
            ------
            GameError.UserInNoTeamError:
                If the player does not belong in any team managed by this game.

            """

            try:
                return self._team_manager.get_groups_of_user(user).pop()
            except PlayerGroupError.UserInNoGroupError as exception:
                raise GameError.UserInNoTeamError from exception

        def get_team(self, team_tag):
            """
            If `team_tag` is a team managed by this game, return it.
            If it is a string and the ID of a team managed by this game, return that.

            Parameters
            ----------
            team_tag : GameManager.Team or str
                Team this game manages.

            Returns
            -------
            GameManager.Team
                The team that matches the given tag.

            Raises
            ------
            GameError.GameDoesNotManageTeamError:
                If `team_tag` is a team this game does not manage.
            GameError.GameInvalidTeamIDError:
                If `team_tag` is a str and it is not the ID of a team this game manages.

            """

            try:
                return self._team_manager.get_group(team_tag)
            except PlayerGroupError.ManagerDoesNotManageGroupError as exception:
                raise GameError.GameDoesNotManageTeamError from exception
            except PlayerGroupError.ManagerInvalidGroupIDError as exception:
                raise GameError.GameInvalidTeamIDError from exception

        def get_team_id(self, team_tag):
            """
            If `team_tag` is the ID of a team managed by this game, return it.
            If it is a team managed by this game, return its ID.

            Parameters
            ----------
            team_tag : PlayerGroup or str
                Team this game manages.

            Returns
            -------
            str
                The ID of the team that matches the given tag.

            Raises
            ------
            GameError.GameDoesNotManageTeamError:
                If `team_tag` is a team this game does not manage.
            GameError.GameInvalidTeamIDError:
                If `team_tag` is a str and it is not the ID of a team this game manages.

            """

            try:
                return self._team_manager.get_group_id(team_tag)
            except PlayerGroupError.ManagerDoesNotManageGroupError as exception:
                raise GameError.GameDoesNotManageTeamError from exception
            except PlayerGroupError.ManagerInvalidGroupIDError as exception:
                raise GameError.GameInvalidTeamIDError from exception

        def __str__(self):
            return (f"Game::"
                    f"{self._team_manager._id_to_group}:{self._team_manager._user_to_groups}:"
                    f"{self._timer_manager._id_to_steptimer}:"
                    f"{self._game._playergroup_id}:{self._game._players}:{self._game._leaders}")

        def __repr__(self):
            """
            Return a representation of this game.

            Returns
            -------
            str
                Printable representation.

            """
            return (f"GameManager.Game(server, manager, '{self._game._playergroup_id}', "
                    f"concurrent_limit={self._game._concurrent_limit}, "
                    f"player_limit={self._game._player_limit}, players={self._game._players}, "
                    f"invitations={self._game._invitations}, leaders={self._game._leaders}, "
                    f"require_players={self._game._require_players}, "
                    f"require_invitations={self._game._require_invitations}, "
                    f"require_leaders={self._game._require_leaders}, "
                    f"team_limit={self._team_manager._playergroup_limit}, "
                    F"timer_limit={self._timer_manager._steptimer_limit})")

    def _check_structure(self):
        super()._check_structure()
