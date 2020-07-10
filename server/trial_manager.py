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
Module that contains the trial manager and trial modules.

"""

import functools

from server.exceptions import TrialError, GameError
from server.game_manager import GameManager
from server.gamewithareas import GameWithAreas
from server.trialminigame import TrialMinigame
from server.nonstopdebate import NonStopDebate

class _Trial(GameWithAreas):
    """
    A trial is a game with areas that can manage 'trial minigames', which are the following
    trial games (server.trialminigame):
    * Non-Stop Debates (server.nonstopdebate).

    While multiple minigames may be going on at the same time, no player may be part of two
    minigames simultaneously.

    Attributes
    ----------
    listener : Listener
        Standard listener of the trial.

    Callback Methods
    ----------------
    _on_area_client_left
        Method to perform once a client left an area of the trial.
    _on_area_client_entered
        Method to perform once a client entered an area of the trial.
    _on_area_destroyed
        Method to perform once an area of the trial is marked for destruction.
    _on_client_send_ic_check
        Method to perform once a player of the trial wants to send an IC message.
    _on_client_send_ic
        Method to perform once a player of the trial sends an IC message.
    _on_client_change_character
        Method to perform once a player of the trial has changed character.
    _on_client_destroyed
        Method to perform once a player of the trial is destroyed.

    """

    # (Private) Attributes
    # --------------------
    # _minigame_manager : GameManager
    #   Manager for all games of the trial.
    #
    # Invariants
    # ----------
    # 1. For each player of a minigame of this trial, they are also a player of the trial.
    # 2. For each area of a minigame of this trial, they are also an area of the trial.
    # 3. The invariants from the parent class GameWithArea are satisfied.

    def __init__(self, server, manager, trial_id, player_limit=None, concurrent_limit=None,
                 require_invitations=False, require_players=True, require_leaders=True,
                 require_character=False, team_limit=None, timer_limit=None,
                 areas=None, minigame_limit=1, playergroup_manager=None):
        """
        Create a new trial. A trial should not be fully initialized anywhere else other than
        some manager code, as otherwise the manager will not recognize the trial.

        Parameters
        ----------
        server : TsuserverDR
            Server the trial belongs to.
        manager : TrialManager
            Manager for this trial.
        trial_id : str
            Identifier of the trial.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the trial supports. If None, it
            indicates the trial has no player limit. Defaults to None.
        concurrent_limit : int or None, optional
            If an int, it is the maximum number of trials managed by `manager` that any
            player of this trial may belong to, including this trial. If None, it indicates
            that this trial does not care about how many other trials managed by `manager` each
            of its players belongs to. Defaults to None.
        require_invitation : bool, optional
            If True, players can only be added to the trial if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the trial has no players left, the trial will
            automatically be deleted. If False, no such automatic deletion will happen.
            Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the trial has no leaders left, the trial will choose a
            leader among any remaining players left; if no players are left, the next player
            added will be made leader. If False, no such automatic assignment will happen.
            Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the trial, and
            players that switch to something other than a character will be automatically
            removed from the trial. If False, no such checks are made. A player without a
            character is considered one where player.has_character() returns False. Defaults
            to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the trial supports. If None, it
            indicates the trial has no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of steptimers the trial supports. If None, it
            indicates the trial has no steptimer limit. Defaults to None.
        areas : set of AreaManager.Area, optional
            Areas the trial starts with.
        minigame_limit : int or None, optional
            If an int, it is the maximum number of minigames the trial may have simultaneously.
            If None, it indicates the trial has no minigame limit. Defaults to 1.
        playergroup_manager : PlayerGroupManager, optional
            The internal playergroup manager of the trial manager. Access to this value is
            limited exclusively to this __init__, and is only to initialize the internal
            player group of the trial.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.

        """

        self._minigame_manager = GameManager(server, game_limit=minigame_limit,
                                             default_game_type=TrialMinigame,
                                             available_id_producer=self.get_available_minigame_id)
        super().__init__(server, manager, trial_id, player_limit=player_limit,
                         concurrent_limit=concurrent_limit,
                         require_invitations=require_invitations,
                         require_players=require_players,
                         require_leaders=require_leaders,
                         require_character=require_character,
                         team_limit=team_limit, timer_limit=timer_limit,
                         areas=areas, playergroup_manager=playergroup_manager)

    def add_player(self, user):
        """
        Make a user a player of the trial. By default this player will not be a leader. It will
        also subscribe the trial ot the player so it can listen to its updates.

        Newly added players will be ordered to switch to a 'trial' vasriant.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the trial. They must be in an area part of the trial.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the trial was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameWithAreasError.UserNotInAreaError
            If the user is not in an area part of the trial.
        GameError.UserHasNoCharacterError
            If the user has no character but the trial requires that all players have
            characters.
        GameError.UserNotInvitedError
            If the trial requires players be invited to be added and the user is not invited.
        GameError.UserAlreadyPlayerError
            If the user to add is already a user of the trial.
        GameError.UserHitConcurrentLimitError
            If the player has reached any of the trials it belongs to managed by this trial's
            manager concurrent membership limit, or by virtue of joining this trial they
            will violate this trial's concurrent membership limit.
        GameError.GameIsFullError
            If the trial reached its player limit.

        """

        super().add_player(user)
        user.send_command('VA', 'trial')

    def remove_player(self, user):
        """
        Make a user be no longer a player of this trial. If they were part of a team managed by
        this trial, they will also be removed from said team. It will also unsubscribe the game
        from the player so it will no longer listen to its updates, and remove them from any
        minigames them may have been a part.

        If the game required that there it always had players and by calling this method the
        game had no more players, the game will automatically be scheduled for deletion. A similar
        check will be performed for each minigame the user may have belonged to.

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

        for game in self._minigame_manager.get_games():
            if user in game.get_players():
                game.remove_player(user)

        super().remove_player(user)
        user.send_command('VA', '')

    def new_nsd(self, creator=None, player_limit=None, add_players=False,
                require_invitations=False, require_players=True,
                require_character=False, team_limit=None, timer_limit=None,
                timer_start_value=300) -> NonStopDebate:
        """
        Create a new NSD managed by this trial. Overriden default parameters include:
        * An NSD does not require leaders.

        Parameters
        ----------
        creator : ClientManager.Client, optional
            The player who created this NSD. If set, they will also be added to the NSD.
            Defaults to None.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the NSD supports. If None, it
            indicates the NSD has no player limit. Defaults to None.
        require_invitations : bool, optional
            If True, users can only be added to the NSD if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the NSD loses all its players, the NSD will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the NSD, and
            players that switch to something other than a character will be automatically
            removed from the NSD. If False, no such checks are made. A player without a
            character is considered one where player.has_character() returns False. Defaults
            to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the NSD will support. If None, it
            indicates the NSD will have no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of steptimers the NSD will support. If None, it
            indicates the NSD will have no steptimer limit. Defaults to None.
        timer_start_value : float, optional
            In seconds, the length of time the main timer of this non-stop debate will have at the
            start. It must be a positive number. Defaults to 300 (5 minutes).

        Returns
        -------
        NonStopDebate
            The created NSD.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of minigames.
        Any error from the created NSD's add_player(creator)
            If the NSD cannot add `creator` to the NSD if given one.

        """

        areas = {creator.area} if creator else set()
        nsd_factory = functools.partial(NonStopDebate, areas=areas, trial=self,
                                        timer_start_value=timer_start_value)

        nsd = self._minigame_manager.new_game(game_type=nsd_factory, creator=creator,
                                              player_limit=player_limit,
                                              concurrent_limit=1,
                                              require_invitations=require_invitations,
                                              require_players=require_players,
                                              require_leaders=False,
                                              require_character=require_character,
                                              team_limit=team_limit, timer_limit=timer_limit)

        if add_players:
            clients_to_add = {client for area in areas for client in area.clients}
            if creator:
                clients_to_add.discard(creator)
            for client in clients_to_add:
                try:
                    nsd.add_player(client)
                except GameError.UserNotPlayerError:
                    continue

        return nsd

    def get_nsd_of_user(self, user) -> NonStopDebate:
        """
        Get the NSD the user is in.

        Parameters
        ----------
        user : ClientManager.Client
            User to check.

        Raises
        ------
        TrialError.UserNotInMinigameError
            If the user is not in an NSD managed by this trial.

        Returns
        -------
        NonStopDebate
            NSD of the user.

        """

        games = self._minigame_manager.get_games_of_user(user)
        nsds = {game for game in games if isinstance(game, NonStopDebate)}
        if not nsds:
            raise TrialError.UserNotInMinigameError
        if len(nsds) > 1:
            raise RuntimeError(nsds)
        return next(iter(nsds))

    def get_minigames(self):
        """
        Return the minigames of this trial.

        Returns
        -------
        set of TrialMinigame
            Trial minigames of this trial.

        """

        return self._minigame_manager.get_games().copy()


    def get_minigame_by_id(self, minigame_id) -> TrialMinigame:
        """
        If `minigame_id` is the ID of a minigame managed by this trial, return that.

        Parameters
        ----------
        minigame_id : str
            ID of the minigame this trial manages.

        Returns
        -------
        TrialMinigame
            The minigame with that ID.

        Raises
        ------
        GameError.ManagerInvalidGameIDError
            If `minigame_id` is not the ID of a minigame this game manages.

        """

        return self._minigame_manager.get_game_by_id(minigame_id)

    def get_available_minigame_id(self):
        """
        Get a minigame ID that no other minigame managed by this manager has.

        Returns
        -------
        str
            A unique minigame ID.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.

        """

        game_number = 0
        game_limit = self._minigame_manager.get_game_limit()
        while game_limit is None or game_number < game_limit:
            new_game_id = "{}g{}".format(self.get_id(), game_number)
            if new_game_id not in self._minigame_manager.get_game_ids():
                return new_game_id
            game_number += 1
        raise GameError.ManagerTooManyGamesError

    def _on_area_client_left(self, area, client=None, new_area=None, old_displayname=None,
                             ignore_bleeding=False):
        """
        If a player left to an area not part of the trial, remove the player and warn them and
        the leaders of the trial.

        If a non-plyer left to an area not part of the trial, warn them and the leaders of the
        trial.

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
            client.send_ooc(f'You have left to an area not part of trial `{self.get_id()}` and '
                            f'thus were automatically removed from the trial.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your trial and thus was automatically '
                                   f'removed it ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

            self.remove_player(client)

            if self.is_unmanaged():
                if was_leader:
                    client.send_ooc(f'Your trial `{self.get_id()}` was automatically '
                                    f'deleted as it lost all its players.')
                client.send_ooc_others(f'(X) Trial `{self.get_id()}` was automatically '
                                       f'deleted as it lost all its players.',
                                       is_zstaff_flex=True)

        elif new_area not in self.get_areas():
            client.send_ooc(f'You have left to an area not part of trial `{self.get_id()}`.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your trial ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

        self._check_structure()

    def _on_area_client_entered(self, area, client=None, old_area=None, old_displayname=None,
                                ignore_bleeding=False):
        """
        If a non-player entered, warn them and the leaders of the trial.

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
            client.send_ooc(f'You have entered an area part of trial `{self.get_id()}`.')
            client.send_ooc_others(f'(X) Non-player {client.displayname} [{client.id}] has entered '
                                   f'an area part of your trial ({old_area.id}->{area.id}).',
                                   pred=lambda c: c in self.get_leaders())

        self._check_structure()

    def __str__(self):
        """
        Return a string representation of this trial.

        Returns
        -------
        str
            Representation.

        """

        return (f"Trial::{self.get_id()}:"
                f"{self.get_players()}:{self.get_leaders()}:{self.get_invitations()}"
                f"{self.get_steptimers()}:"
                f"{self.get_teams()}:"
                f"{self.get_areas()}:"
                f"{self.get_minigames()}")

    def __repr__(self):
        """
        Return a representation of this trial.

        Returns
        -------
        str
            Printable representation.

        """

        return (f'Trial(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'player_limit={self._playergroup._player_limit}, '
                f'concurrent_limit={self.get_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager._playergroup_limit}, '
                f'timer_limit={self._timer_manager._steptimer_limit}, || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_steptimers()}, '
                f'teams={self.get_teams()}, '
                f'areas={self.get_areas()}), '
                f'minigames={self.get_minigames()}')

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        for game in self.get_minigames():
            for player in game.get_players():
                err = (f'For trial {self}, expected that player {player} of its minigame '
                       f'{game} was a player of the trial, found that was not the case.')
                assert player in self.get_players(), err

        # 2.
        for game in self.get_minigames():
            for area in game.get_areas():
                err = (f'For trial {self}, expected that area {area} of its minigame '
                       f'{game} was an area of the trial, found that was not the case.')
                assert area in self.get_areas(), err

        # 3.
        super()._check_structure()

class TrialManager(GameManager):
    """
    A trial manager is a game manager with dedicated trial management functions.

    """

    def new_trial(self, creator=None, player_limit=None, concurrent_limit=1, add_players=False,
                  require_invitations=False, require_players=True,
                  require_character=False, team_limit=None, timer_limit=None) -> _Trial:
        """
        Create a new trial managed by this manager. Overriden default parameters include:
        * A trial does not require leaders.

        Parameters
        ----------
        creator : ClientManager.Client, optional
            The player who created this trial. If set, they will also be added to the trial.
            Defaults to None.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the trial supports. If None, it
            indicates the trial has no player limit. Defaults to None.
        require_invitations : bool, optional
            If True, users can only be added to the trial if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the trial loses all its players, the trial will automatically
            be deleted. If False, no such automatic deletion will happen. Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the trial, and
            players that switch to something other than a character will be automatically
            removed from the trial. If False, no such checks are made. A player without a
            character is considered one where player.has_character() returns False. Defaults
            to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the trial will support. If None, it
            indicates the trial will have no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of steptimers the trial will support. If None, it
            indicates the trial will have no steptimer limit. Defaults to None.

        Returns
        -------
        NonStopDebate
            The created trial.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of minigames.
        Any error from the created trial's add_player(creator)
            If the trial cannot add `creator` to the trial if given one.

        """

        areas = {creator.area} if creator else set()
        trial_factory = functools.partial(_Trial, areas=areas, require_character=True)
        trial = self.new_game(game_type=trial_factory, creator=creator,
                              player_limit=player_limit,
                              concurrent_limit=concurrent_limit,
                              require_invitations=require_invitations,
                              require_players=require_players,
                              require_leaders=False,
                              require_character=require_character,
                              team_limit=team_limit, timer_limit=timer_limit)

        if add_players:
            clients_to_add = {client for area in areas for client in area.clients}
            if creator:
                clients_to_add.discard(creator)
            for client in clients_to_add:
                trial.add_player(client)

        return trial

    def get_trial_of_user(self, user) -> _Trial:
        """
        Get the trial the user is in.

        Parameters
        ----------
        user : ClientManager.Client
            User to check.

        Raises
        ------
        GameError.UserNotPlayerError
            If the user is not in a trial managed by this manager.

        Returns
        -------
        TrialManager.Trial
            Trial of the user.

        """

        games = self.get_games_of_user(user)
        trials = {game for game in games if isinstance(game, _Trial)}
        if not trials:
            raise GameError.UserNotPlayerError
        if len(trials) > 1:
            raise RuntimeError(trials)
        return next(iter(trials))

    def get_available_game_id(self):
        """
        Get a trial ID that no other trial managed by this manager has.

        Returns
        -------
        str
            A unique trial ID.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.

        """

        game_number = 0
        game_limit = self.get_game_limit()
        while game_limit is None or game_number < game_limit:
            new_game_id = "trial{}".format(game_number)
            if new_game_id not in self.get_game_ids():
                return new_game_id
            game_number += 1
        raise GameError.ManagerTooManyGamesError

    def __repr__(self):
        """
        Return a representation of this trial manager.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"TrialManager(server, game_limit={self.get_game_limit()}, "
                f"|| "
                f"_trials={self.get_games()}, "
                f"id={hex(id(self))})")
