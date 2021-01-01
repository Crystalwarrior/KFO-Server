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
Module that contains the trial minigame class.

"""

import enum

from server.exceptions import GameError, GameWithAreasError
from server.gamewithareas_manager import GameWithAreas


class TRIALMINIGAMES(enum.Enum):
    """
    All supported trial minigames.
    """

    NONSTOP_DEBATE = enum.auto()


class TrialMinigame(GameWithAreas):
    """
    A trial minigame is a game with areas that is part of a trial. Any players of the minigame
    must be players of the trial, and any areas of the minigame must be areas of the trial.

    Attributes
    ----------
    listener : Listener
        Standard listener of the minigame.

    Callback Methods
    ----------------
    _on_area_client_left
        Method to perform once a client left an area of the minigame.
    _on_area_client_entered
        Method to perform once a client entered an area of the minigame.
    _on_area_destroyed
        Method to perform once an area of the minigame is marked for destruction.
    _on_client_inbound_ms_check
        Method to perform once a player of the minigame wants to send an IC message.
    _on_client_inbound_ms
        Method to perform once a player of the minigame sends an IC message.
    _on_client_change_character
        Method to perform once a player of the minigame has changed character.
    _on_client_destroyed
        Method to perform once a player of the minigame is destroyed.

    """

    # (Private) Attributes
    # --------------------
    # _trial : TrialManager.Trial
    #   Trial of the minigame
    #
    # Invariants
    # ----------
    # 1. The invariants from the parent class TrialMinigame are satisfied.

    def __init__(self, server, manager, minigame_id, player_limit=None,
                 player_concurrent_limit=None, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None, timer_limit=None,
                 area_concurrent_limit=1, trial=None, playergroup_manager=None):
        """
        Create a trial minigame. A trial minigame should not be fully initialized anywhere
        else other than some manager code, as otherwise the manager will not recognize the minigame.

        Parameters
        ----------
        server : TsuserverDR
            Server the trial minigame belongs to.
        manager : GameManager
            Manager for this trial minigame.
        minigame_id : str
            Identifier of the trial minigame.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the trial minigame supports. If None, it
            indicates the trial minigame has no player limit. Defaults to None.
        player_concurrent_limit : int or None, optional
            If an int, it is the maximum number of games managed by `manager` that any
            player of this trial minigame may belong to, including this trial minigame. If None, it
            indicates that this trial minigame does not care about how many other games managed by
            `manager` each of its players belongs to. Defaults to None.
        require_invitation : bool, optional
            If True, players can only be added to the trial minigame if they were previously
            invited. If False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the trial minigame has no players left, the trial minigame will
            automatically be deleted. If False, no such automatic deletion will happen.
            Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the trial minigame has no leaders left, the trial minigame will
            choose a leader among any remaining players left; if no players are left, the next
            player added will be made leader. If False, no such automatic assignment will happen.
            Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the trial minigame,
            and players that switch to something other than a character will be automatically
            removed from the trial minigame. If False, no such checks are made. A player without a
            character is considered one where player.has_character() returns False. Defaults to
            False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the trial minigame supports. If None, it
            indicates the trial minigame has no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of timers the trial minigame supports. If None,
            it indicates the trial minigame has no timer limit. Defaults to None.
        area_concurrent_limit : int or None, optional
            If an int, it is the maximum number of trials managed by `manager` that any
            area of this trial may belong to, including this trial. If None, it indicates
            that this game does not care about how many other trials managed by
            `manager` each of its areas belongs to. Defaults to 1 (an area may not be a part of
            another trial managed by `manager` while being an area of this trial).
        trial : TrialManager.Trial, optional
            Trial the non-stop debate is a part of.
        playergroup_manager : PlayerGroupManager, optional
            The internal playergroup manager of the game manager. Access to this value is
            limited exclusively to this __init__, and is only to initialize the internal
            player group of the trial minigame.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of trial minigames.

        """

        self._trial = trial
        super().__init__(server, manager, minigame_id, player_limit=player_limit,
                         player_concurrent_limit=player_concurrent_limit,
                         require_invitations=require_invitations,
                         require_players=require_players,
                         require_leaders=require_leaders,
                         require_character=require_character,
                         team_limit=team_limit, timer_limit=timer_limit,
                         area_concurrent_limit=area_concurrent_limit,
                         playergroup_manager=playergroup_manager)

    def add_player(self, user):
        """
        Make a user a player of the trial. By default this player will not be a leader. It will
        also subscribe the game ot the player so it can listen to its updates.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the game. They must be in an area part of the game.

        Raises
        ------
        GameError.UserNotPlayerError
            If the user is not a player of the trial.
        GameError.GameIsUnmanagedError
            If the minigame was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameWithAreasError.UserNotInAreaError
            If the user is not in an area part of the minigame.
        GameError.UserHasNoCharacterError
            If the user has no character but the minigame requires that all players have characters.
        GameError.UserNotInvitedError
            If the minigame requires players be invited to be added and the user is not invited.
        GameError.UserAlreadyPlayerError
            If the user to add is already a user of the minigame.
        GameError.UserHitGameConcurrentLimitError
            If the player has reached any of the games it belongs to managed by this minigame's
            manager concurrent player membership limit, or by virtue of joining this minigame they
            will violate this game's concurrent player membership limit.
        GameError.GameIsFullError
            If the minigame reached its player limit.

        """

        if not self._trial.is_player(user):
            raise GameError.UserNotPlayerError

        super().add_player(user)

    def add_area(self, area):
        """
        Add an area to this minigame's set of areas.

        Parameters
        ----------
        area : AreaManager.Area
            Area to add.

        Raises
        ------
        GameWithAreasError.AreaNotInGameError
            If the area is not part of the trial of the minigame.
        GameError.GameIsUnmanagedError
            If the minigame was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameWithAreasError.AreaAlreadyInGameError
            If the area is already part of the minigame.
        GameWithAreasError.AreaHitGameConcurrentLimitError.
            If `area` has reached the concurrent area membership limit of any of the games it
            belongs to managed by this manager, or by virtue of adding this area it will violate
            this game's concurrent area membership limit.

        Returns
        -------
        None.

        """

        if not self._trial.has_area(area):
            raise GameWithAreasError.AreaNotInGameError

        super().add_area(area)

    def get_trial(self):
        """
        Return the trial of the game.

        Returns
        -------
        TrialManager.Trial
            Trial of the minigame.

        """

        return self._trial

    def get_type(self) -> TRIALMINIGAMES:
        """
        Return the type of the minigame.

        Returns
        -------
        TRIALMINIGAMES
            Type of minigame.

        """

        # Should be overriden in child class.
        raise NotImplementedError

    def destroy(self):
        """
        Mark this game as destroyed and notify its manager so that it is deleted.
        If the game is already destroyed, this function does nothing.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        # Keep track of areas for later
        areas = self.get_areas()

        # Then carry on
        super().destroy()

        # Force every user in the former areas of the minigame to switch to trial gamemode
        for area in areas:
            for user in area.clients:
                user.send_gamemode(name='trial')

    def _on_area_client_left(self, area, client=None, new_area=None, old_displayname=None,
                             ignore_bleeding=False):
        """
        If a player left to an area not part of the minigame, remove the player and warn them and
        the leaders of the minigame.

        If a non-plyer left to an area not part of the minigame, warn them and the leaders of the
        minigame.

        Parameters
        ----------
        area : AreaManager.Area
            Area that signaled a client has left.
        client : ClientManager.Client, optional
            The client that has left. The default is None.
        new_area : AreaManager.Area
            The new area the client has gone to. The default is None.
        old_displayname : str, optional
            The old displayed name of the client before they changed area. This will typically
            change only if the client's character or showname are taken. The default is None.
        ignore_bleeding : bool, optional
            If the code should ignore actions regarding bleeding. The default is False.

        Returns
        -------
        None.

        """

        was_leader = self.is_leader(client) if self.is_player(client) else False
        if client in self.get_players() and new_area not in self.get_areas():
            client.send_ooc(f'You have left to an area not part of trial minigame '
                            f'`{self.get_id()}` and thus were automatically removed from the '
                            f'minigame.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your trial minigame and thus was '
                                   f'automatically removed from it ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

            self.remove_player(client)
            if self.is_unmanaged():
                if was_leader:
                    client.send_ooc(f'Your trial minigame `{self.get_id()}` was automatically '
                                    f'deleted as it lost all its players.')
                client.send_ooc_others(f'(X) Trial minigame `{self.get_id()}` was automatically '
                                       f'deleted as it lost all its players.',
                                       is_zstaff_flex=True)

        elif new_area not in self.get_areas():
            client.send_ooc(f'You have left to an area not part of trial minigame '
                            f'`{self.get_id()}`.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to an '
                                   f'area not part of your trial minigame '
                                   f'({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

        self._check_structure()

    def _on_area_client_entered(self, area, client=None, old_area=None, old_displayname=None,
                                ignore_bleeding=False):
        """
        If a non-player entered, warn them and the leaders of the trial minigame.

        Parameters
        ----------
        area : AreaManager.Area
            Area that signaled a client has entered.
        client : ClientManager.Client, optional
            The client that has entered. The default is None.
        old_area : AreaManager.Area
            The old area the client has come from. The default is None.
        old_displayname : str, optional
            The old displayed name of the client before they changed area. This will typically
            change only if the client's character or showname are taken. The default is None.
        ignore_bleeding : bool, optional
            If the code should ignore actions regarding bleeding. The default is False.

        Returns
        -------
        None.

        """

        if client not in self.get_players() and old_area not in self.get_areas():
            client.send_ooc(f'You have entered an area part of trial minigame `{self.get_id()}`.')
            client.send_ooc_others(f'(X) Non-player {client.displayname} [{client.id}] has entered '
                                   f'an area part of your trial minigame '
                                   f'({old_area.id}->{area.id}).',
                                   pred=lambda c: c in self.get_leaders())

    def __str__(self):
        """
        Return a string representation of this minigame.

        Returns
        -------
        str
            Representation.

        """

        return (f"TrialMinigame::{self.get_id()}:{self.get_trial()}"
                f"{self.get_players()}:{self.get_leaders()}:{self.get_invitations()}"
                f"{self.get_timers()}:"
                f"{self.get_teams()}:"
                f"{self.get_areas()}")

    def __repr__(self):
        """
        Return a representation of this game.

        Returns
        -------
        str
            Printable representation.

        """

        return (f'TrialMinigame(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'player_limit={self._playergroup._player_limit}, '
                f'player_concurrent_limit={self.get_player_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager.get_group_limit()}, '
                f'timer_limit={self._timer_manager.get_timer_limit()}, '
                f'areas={self.get_areas()}, '
                f'trial={self.get_trial()}) || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_timers()}, '
                f'teams={self.get_teams()}')
