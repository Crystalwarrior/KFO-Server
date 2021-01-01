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
Module that contains the trial manager and trial modules.

"""

import functools

from server.exceptions import TrialError, GameError
from server.game_manager import GameManager
from server.gamewithareas_manager import GameWithAreas, GameWithAreasManager
from server.trialminigame import TrialMinigame, TRIALMINIGAMES
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
    _on_client_inbound_ms_check
        Method to perform once a player of the trial wants to send an IC message.
    _on_client_inbound_ms
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
    # 3. The player to influence and player to focus maps contain exactly the IDs of all players
    # of the trial.
    # 4. For each influence and focus value in the player to influence and player to focus maps,
    # they are a value between 0 and 10 inclusive.
    # 5. The invariants from the parent class GameWithArea are satisfied.

    def __init__(self, server, manager, trial_id, player_limit=None, player_concurrent_limit=None,
                 require_invitations=False, require_players=True, require_leaders=True,
                 require_character=False, team_limit=None, timer_limit=None,
                 area_concurrent_limit=None, minigame_limit=1, playergroup_manager=None):
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
        player_concurrent_limit : int or None, optional
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
            If an int, it is the maximum number of timers the trial supports. If None, it
            indicates the trial has no timer limit. Defaults to None.
        area_concurrent_limit : int or None, optional
            If an int, it is the maximum number of trials managed by `manager` that any
            area of this trial may belong to, including this trial. If None, it indicates
            that this game does not care about how many other trials managed by
            `manager` each of its areas belongs to. Defaults to 1 (an area may not be a part of
            another trial managed by `manager` while being an area of this trial).
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

        self._player_to_influence = dict()
        self._player_to_focus = dict()
        self._min_influence = 0
        self._max_influence = 10
        self._min_focus = 0
        self._max_focus = 10
        self._manager = None  # This is set in the super().__init__

        self._client_timer_id = 0

        self._minigame_manager = GameWithAreasManager(
            server, game_limit=minigame_limit, default_game_type=TrialMinigame,
            available_id_producer=self.get_available_minigame_id)
        super().__init__(server, manager, trial_id, player_limit=player_limit,
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
        GameError.UserHitGameConcurrentLimitError
            If the player has reached any of the trials it belongs to managed by this trial's
            manager concurrent player membership limit, or by virtue of joining this trial they
            will violate this trial's concurrent player membership limit.
        GameError.GameIsFullError
            If the trial reached its player limit.

        """

        # By checking this early, self._player_to_influence will never be overwritten if the player
        # was already part of the trial (nor self._player_to_focus)
        if self.is_player(user):
            raise GameError.UserAlreadyPlayerError

        self._player_to_influence[user.id] = (self._max_influence, self._min_influence,
                                              self._max_influence)
        self._player_to_focus[user.id] = (self._max_focus, self._min_focus, self._max_focus)
        try:
            super().add_player(user)
        except GameError as ex:
            # Remove entries in player to influence and player to focus maps before reraising
            self._player_to_influence.pop(user.id)
            self._player_to_focus.pop(user.id)
            raise ex

        self.introduce_user(user)

    def introduce_user(self, user):
        """
        Broadcast information relevant for a user entering an area of the trial, namely current
        gamemode if needed.
        Note the user needs not be in the same area as the trial, nor be a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            User to introduce.

        Returns
        -------
        None.

        """

        if self.is_player(user):
            user.send_health(side=1, health=int(self._player_to_focus[user.id][0]))
            user.send_health(side=2, health=int(self._player_to_influence[user.id][0]))

        # If there are any minigames, let them set the splashes, gamemode and timers
        if self.get_minigames():
            return

        user.send_gamemode(name='trial')
        user.send_splash(name='testimony1')
        user.send_timer_pause(timer_id=self._client_timer_id)
        user.send_timer_set_time(timer_id=self._client_timer_id, new_time=0)
        user.send_timer_set_step_length(timer_id=self._client_timer_id,
                                        new_step_length=0)
        user.send_timer_set_firing_interval(timer_id=self._client_timer_id,
                                            new_firing_interval=0)

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

        if not self.is_player(user):
            raise GameError.UserNotPlayerError

        self._player_to_influence.pop(user.id)
        self._player_to_focus.pop(user.id)
        for game in self._minigame_manager.get_games():
            if user in game.get_players():
                game.remove_player(user)

        super().remove_player(user)

        self.dismiss_user(user)

        # # If the trial was destroyed because it lost all its players, warn server officers
        # if self.is_unmanaged():
        #     user.send_ooc('As you were the last member of your trial, it was automatically '
        #                   'destroyed.')
        #     user.send_ooc_others(f'(X) Trial {self.get_id()} was automatically destroyed as it '
        #                          f'lost all its players.', is_officer=True)

    def dismiss_user(self, user):
        """
        Broadcast information relevant for a user that has left the trial, namely clear out
        gamemode and health bars. Gamemode is only cleared if the user's new area is not part
        of the trial's areas.
        Note the user needs not be in the same area as the NSD, nor be a player of the NSD.
        If the trial has never had any players, this method does nothing.

        Parameters
        ----------
        user : ClientManager.Client
            User to introduce.

        Returns
        -------
        None.

        """

        if not self.has_ever_had_players():
            return

        # We use .new_area rather than .area as this function may have been called as a result
        # of the user moving, in which case .area still points to the user's old area.

        user.send_health(side=1, health=user.area.hp_pro)
        user.send_health(side=2, health=user.area.hp_def)

        # If the user is no longer in an area part of an area of the trial, clear out gamemode
        if user.new_area not in self.get_areas():
            user.send_gamemode(name='')

    def get_influence(self, user) -> float:
        """
        Get the current influence of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current influence of the player.

        """

        try:
            return self._player_to_influence[user.id][0]
        except KeyError:
            raise TrialError.UserNotPlayerError

    def set_influence(self, user, new_influence):
        """
        Set the influence of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Client to change.
        new_influence : float
            New influence.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.
        TrialError.InfluenceIsInvalidError
            If the new influence is below the trial minimum or above the trial maximum.

        Returns
        -------
        None.

        """

        if user not in self.get_players():
            raise TrialError.UserNotPlayerError
        _, min_influence, max_influence = self._player_to_influence[user.id]

        if not min_influence <= new_influence <= max_influence:
            raise TrialError.InfluenceIsInvalidError

        self._player_to_influence[user.id] = (new_influence, min_influence, max_influence)
        user.send_health(side=2, health=int(new_influence))

        # If the new influence is 0, warn all trial leaders
        if new_influence == 0:
            user.send_ooc('You ran out of influence!')
            user.send_ooc_others(f'(X) {user.displayname} ran out of influence!',
                                 pred=lambda c: c in self.get_leaders())
        self._check_structure()

    def change_influence_by(self, user, change_by):
        """
        Change the influence of a player by a certain value. If the new influence value goes
        below the trial minimum, it is set to the trial minimum. If instead it goes above the
        trial maximum, it is set to the trial maximum.

        Parameters
        ----------
        user : ClientManager.Client
            Client to change.
        change_by : float
            Amount to change influence by.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        None.

        """

        if user not in self.get_players():
            raise TrialError.UserNotPlayerError

        new_influence = self._player_to_influence[user.id][0] + change_by
        new_influence = max(self._min_influence, min(self._max_influence, new_influence))
        self.set_influence(user, new_influence)  # Also calls _check_structure()

    def get_min_influence(self, user) -> float:
        """
        Get the current minimum influence of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current minimum influence of the player.

        """

        try:
            return self._player_to_influence[user.id][1]
        except KeyError:
            raise TrialError.UserNotPlayerError

    def get_max_influence(self, user) -> float:
        """
        Get the current maximum influence of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current maximum influence of the player.

        """

        try:
            return self._player_to_influence[user.id][2]
        except KeyError:
            raise TrialError.UserNotPlayerError

    def get_focus(self, user) -> float:
        """
        Get the current focus of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current focus of the player.

        """

        try:
            return self._player_to_focus[user.id][0]
        except KeyError:
            raise TrialError.UserNotPlayerError

    def set_focus(self, user, new_focus):
        """
        Set the focus of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Client to change.
        new_focus : float
            New focus.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.
        TrialError.FocusIsInvalidError
            If the new focus is below the trial minimum or above the trial maximum.

        Returns
        -------
        None.

        """

        if user not in self.get_players():
            raise TrialError.UserNotPlayerError
        _, min_focus, max_focus = self._player_to_focus[user.id]

        if not min_focus <= new_focus <= max_focus:
            raise TrialError.FocusIsInvalidError

        self._player_to_focus[user.id] = (new_focus, min_focus, max_focus)
        user.send_health(side=1, health=int(new_focus))
        self._check_structure()

    def change_focus_by(self, user, change_by):
        """
        Change the focus of a player by a certain value. If the new focus value goes
        below the trial minimum, it is set to the trial minimum. If instead it goes above the
        trial maximum, it is set to the trial maximum.

        Parameters
        ----------
        user : ClientManager.Client
            Client to change.
        change_by : float
            Amount to change focus by.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        None.

        """

        if user not in self.get_players():
            raise TrialError.UserNotPlayerError

        new_focus = self._player_to_focus[user.id][0] + change_by
        new_focus = max(self._min_focus, min(self._max_focus, new_focus))
        self.set_focus(user, new_focus)  # Also calls _check_structure()

    def get_min_focus(self, user) -> float:
        """
        Get the current minimum focus of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current minimum focus of the player.

        """

        try:
            return self._player_to_focus[user.id][1]
        except KeyError:
            raise TrialError.UserNotPlayerError

    def get_max_focus(self, user) -> float:
        """
        Get the current maximum focus of a player of the trial.

        Parameters
        ----------
        user : ClientManager.Client
            Player to check.

        Raises
        ------
        TrialError.UserNotPlayerError
            If the user is not a player of the trial.

        Returns
        -------
        float
            Current maximum focus of the player.

        """

        try:
            return self._player_to_focus[user.id][2]
        except KeyError:
            raise TrialError.UserNotPlayerError

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
            If an int, it is the maximum number of timers the NSD will support. If None, it
            indicates the NSD will have no timer limit. Defaults to None.
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
        nsd_factory = functools.partial(NonStopDebate, trial=self,
                                        timer_start_value=timer_start_value)

        nsd = self._minigame_manager.new_game(game_type=nsd_factory,
                                              player_limit=player_limit,
                                              player_concurrent_limit=1,
                                              require_invitations=require_invitations,
                                              require_players=require_players,
                                              require_leaders=False,
                                              require_character=require_character,
                                              team_limit=team_limit, timer_limit=timer_limit,
                                              areas=areas)
        nsd.setup_timers()
        # Add creator manually. This is because otherwise the creator does not get access to
        # the timer info.
        try:
            if creator:
                nsd.add_player(creator)
        except GameError as ex:
            # Discard game
            self._minigame_manager.delete_game(nsd)
            raise ex

        if add_players:
            clients_to_add = {client for area in areas for client in area.clients}
            if creator:
                clients_to_add.discard(creator)
            for client in clients_to_add:
                try:
                    nsd.add_player(client)
                except GameError.UserNotPlayerError:
                    continue

        # Manually give packets to nonplayers
        for nonplayer in nsd.get_nonplayer_users_in_areas():
            nsd.introduce_user(nonplayer)

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

    def get_nsd_by_id(self, nsd_id) -> NonStopDebate:
        """
        If `nsd_id` is the ID of a nonstop debate managed by this trial, return that.

        Parameters
        ----------
        nsd_id : str
            ID of the nonstop debate this trial manages.

        Returns
        -------
        NonStopDebate
            The nonstop debate with that ID.

        Raises
        ------
        GameError.ManagerInvalidGameIDError
            If `nsd_id` is not the ID of a nonstop debate this game manages.

        """

        minigame = self.get_minigame_by_id(nsd_id)
        minigame_type = minigame.get_type()
        if minigame_type != TRIALMINIGAMES.NONSTOP_DEBATE:
            raise GameError.ManagerInvalidGameIDError(f'`{nsd_id}` is a minigame of type '
                                                      '{minigame_type}, not nonstop debate.')
        return minigame

    def get_available_minigame_id(self) -> str:
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

    def get_info(self) -> str:
        """
        Obtain a long description of the trial and its players.

        Returns
        -------
        str
            Description.

        """

        tid = self.get_id()
        leaders = self.get_leaders()
        regulars = self.get_regulars()

        num_members = len(leaders.union(regulars))
        group_texts = list()
        for group in (leaders, regulars):
            if not group:
                group_texts.append('\n*None')
                continue
            group_text = ''
            for player in group:
                player_text = f'{player.displayname} [{player.id}]: '
                influence = self.get_influence(player)
                min_influence = self.get_min_influence(player)
                max_influence = self.get_max_influence(player)
                focus = self.get_focus(player)
                min_focus = self.get_min_focus(player)
                max_focus = self.get_max_focus(player)
                player_text += f'I: {influence} (m: {min_influence}/M: {max_influence}); '
                player_text += f'F: {focus} (m: {min_focus}/M: {max_focus}); '
                player_text += f'A: {player.area.id}'
                group_text += f'\n*{player_text}'
            group_texts.append(group_text)

        leader_text, regular_text = group_texts
        area_ids = ', '.join(sorted({str(area.id) for area in self.get_areas()}))
        info = (f'Trial {tid} [{num_members}/-] ({area_ids}).'
                f'\nLeaders: {leader_text}'
                f'\nRegular members: {regular_text}')
        return info

    def destroy(self):
        """
        Mark this game as destroyed and notify its manager so that it is deleted.
        If the game is already destroyed, this function does nothing.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        # Store for later
        users = self.get_users_in_areas()

        # Remove minigames first. This is done first so as to enforce explicit destruction
        # (rather than rely on other methods).
        for game in self._minigame_manager.get_games():
            game.destroy()

        super().destroy()  # Also calls _check_structure()

        # Force every user in the former areas of the trial to be dismissed
        for user in users:
            self.dismiss_user(user)

    def end(self):
        """
        Destroy the trial and play the trial end splash animation to all users in the trial areas.

        Returns
        -------
        None.

        """

        users = self.get_users_in_areas()  # Store for later

        self.destroy()

        for user in users:
            user.send_splash(name='testimony2')

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

        if new_area in self.get_areas():
            return

        if client in self.get_players():
            client.send_ooc(f'You have left to an area not part of trial `{self.get_id()}` and '
                            f'thus were automatically removed from the trial.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your trial and thus was automatically '
                                   f'removed it ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

            nonplayers = self.get_nonplayer_users_in_areas()
            tid = self.get_id()

            self.remove_player(client)

            if self.is_unmanaged():
                client.send_ooc(f'Your trial `{tid}` was automatically '
                                f'deleted as it lost all its players.')
                client.send_ooc_others(f'(X) Trial `{tid}` was automatically '
                                       f'deleted as it lost all its players.',
                                       is_zstaff_flex=True, not_to=nonplayers)
                client.send_ooc_others('The trial you were watching was automatically deleted '
                                       'as it lost all its players.',
                                       is_zstaff_flex=False, part_of=nonplayers)
        else:
            client.send_ooc(f'You have left to an area not part of trial `{self.get_id()}`.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your trial ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())
            self.dismiss_user(client)

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
            if not self._require_character or client.has_character():
                if client.is_staff():
                    client.send_ooc(f'Join this trial with /trial_join {self.get_id()}')
                client.send_ooc_others(f'(X) Add {client.displayname} to your trial with '
                                       f'/trial_add {client.id}',
                                       pred=lambda c: c in self.get_leaders())
            else:
                if client.is_staff():
                    client.send_ooc(f'This trial requires you have a character to join. Join this '
                                    f'trial with /trial_join {self.get_id()} after choosing a '
                                    f'character.')
                client.send_ooc_others(f'(X) This trial requires players have a character to join. '
                                       f'Add {client.displayname} to your trial with '
                                       f'/trial_add {client.id} after they choose a character.',
                                       pred=lambda c: c in self.get_leaders())
            self.introduce_user(client)
        self._check_structure()

    def _on_client_change_character(self, player, old_char_id=None, new_char_id=None):
        """
        It checks if the player is now no longer having a character. If that is
        the case and the trial requires all players have characters, the player is automatically
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

        old_char = player.get_char_name(old_char_id)
        if self._require_character and not player.has_character():
            player.send_ooc('You were removed from your trial as it required its players to have '
                            'characters.')
            player.send_ooc_others(f'(X) Player {player.id} changed character from {old_char} to '
                                   f'a non-character and was removed from your trial.',
                                   pred=lambda c: c in self.get_leaders())

            nonplayers = self.get_nonplayer_users_in_areas()
            tid = self.get_id()

            self.remove_player(player)

            if self.is_unmanaged():
                player.send_ooc(f'Your trial `{tid}` was automatically '
                                f'deleted as it lost all its players.')
                player.send_ooc_others(f'(X) Trial `{tid}` was automatically '
                                       f'deleted as it lost all its players.',
                                       is_zstaff_flex=True, not_to=nonplayers)
                player.send_ooc_others('The trial you were watching was automatically deleted '
                                       'as it lost all its players.',
                                       is_zstaff_flex=False, part_of=nonplayers)
        else:
            player.send_ooc_others(f'(X) Player {player.id} changed character from {old_char} '
                                   f'to {player.get_char_name()} in your trial.',
                                   pred=lambda c: c in self.get_leaders())
        self._check_structure()

    def _on_client_destroyed(self, player):
        """
        Remove the player from the trial. If the trial is already unmanaged or
        the player is not in the game, this callback does nothing.

        Parameters
        ----------
        player : ClientManager.Client
            Player that signaled it was destroyed.

        Returns
        -------
        None.

        """

        if self.is_unmanaged():
            return
        if player not in self.get_players():
            return

        player.send_ooc_others(f'(X) Player {player.displayname} of your trial disconnected. '
                               f'({player.area.id})', pred=lambda c: c in self.get_leaders())
        nonplayers = self.get_nonplayer_users_in_areas()
        tid = self.get_id()

        self.remove_player(player)

        if self.is_unmanaged():
            # player.send_ooc(f'Your trial `{tid}` was automatically '
            #                 f'deleted as it lost all its players.')
            player.send_ooc_others(f'(X) Trial `{tid}` was automatically '
                                   f'deleted as it lost all its players.',
                                   is_zstaff_flex=True, not_to=nonplayers)
            player.send_ooc_others('The trial you were watching was automatically deleted '
                                   'as it lost all its players.',
                                   is_zstaff_flex=False, part_of=nonplayers)

        self._check_structure()

    def _on_areas_loaded(self, area_manager):
        """
        Destroy the trial and warn players and nonplayers in areas.

        Parameters
        ----------
        area_manager : AreaManager
            AreaManager that signaled the area list load.

        Returns
        -------
        None.

        """

        for nonplayer in self.get_nonleader_users_in_areas():
            nonplayer.send_ooc('The trial you were watching was deleted due to an area list load.')
        for player in self.get_players():
            player.send_ooc('Your trial was deleted due to an area list load.')

        self.destroy()

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
                f"{self.get_timers()}:"
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
                f'player_concurrent_limit={self.get_player_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager.get_group_limit()}, '
                f'timer_limit={self._timer_manager.get_timer_limit()}, || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_timers()}, '
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
        for player in self.get_players():
            err = (f'For trial {self}, expected that player {player} of the trial appeared in the '
                   f'player to influence map of the trial {self._player_to_influence}, found that '
                   f'was not the case.')
            assert player.id in self._player_to_influence, err

            err = (f'For trial {self}, expected that player {player} of the trial appeared in the '
                   f'player to focus map of the trial {self._player_to_focus}, found that '
                   f'was not the case.')
            assert player.id in self._player_to_focus, err

        player_ids = {player.id for player in self.get_players()}
        for player_id in self._player_to_influence:
            err = (f'For trial {self}, expected that player with ID {player_id} that appeared '
                   f'in the player to influence map of the trial {self._player_to_influence} was '
                   f'a player of the trial, found that was not the case.')
            assert player_id in player_ids, err

        for player_id in self._player_to_focus:
            err = (f'For trial {self}, expected that player with ID {player_id} that appeared '
                   f'in the player to focus map of the trial {self._player_to_focus} was '
                   f'a player of the trial, found that was not the case.')
            assert player_id in player_ids, err

        # 4.
        for (player_id, value) in self._player_to_influence.items():
            influences = self._player_to_influence[player_id]
            err = (f'For trial {self}, expected that the player with ID {player_id} had a '
                   f'3-tuple of current influence, min influence and max influence associated '
                   f'to it in the player to influence map, found it was {influences} instead.')
            assert isinstance(influences, tuple) and len(influences) == 3, err

            influence, min_influence, max_influence = self._player_to_influence[player_id]
            err = (f'For trial {self}, expected that the player with ID {player_id} had a '
                   f'3-tuple of floats associated to it in the player to influence map, found it '
                   f'was {influences} instead.')

            all_numbers = [isinstance(value, (int, float)) for value in influences]
            assert all(all_numbers), err

            err = (f'For trial {self}, expected that player with ID {player_id} had an influence '
                   f'value between {min_influence} and {max_influence} inclusive, '
                   f'found it was {influence} instead.')
            assert min_influence <= influence <= max_influence, err

        for (player_id, value) in self._player_to_focus.items():
            focuses = self._player_to_focus[player_id]
            err = (f'For trial {self}, expected that the player with ID {player_id} had a '
                   f'3-tuple of current focus, min focus and max focus associated '
                   f'to it in the player to focus map, found it was {focuses} instead.')
            assert isinstance(focuses, tuple) and len(focuses) == 3, err

            focus, min_focus, max_focus = self._player_to_focus[player_id]
            err = (f'For trial {self}, expected that the player with ID {player_id} had a '
                   f'3-tuple of floats associated to it in the player to focus map, found it '
                   f'was {focuses} instead.')

            all_numbers = [isinstance(value, (int, float)) for value in focuses]
            assert all(all_numbers), err

            err = (f'For trial {self}, expected that player with ID {player_id} had an focus '
                   f'value between {min_focus} and {max_focus} inclusive, '
                   f'found it was {focus} instead.')
            assert min_focus <= focus <= max_focus, err

        # 5.
        super()._check_structure()


class TrialManager(GameWithAreasManager):
    """
    A trial manager is a game with areas manager with dedicated trial management functions.

    """

    # TODO: Enforce GameWithAreasManager to only take game with areas as games when calling
    # new_game, or when initialized. Also do it in check_structure()

    def new_trial(self, creator=None, player_limit=None, player_concurrent_limit=1,
                  add_players=False, require_invitations=False, require_players=True,
                  require_character=False, team_limit=None, timer_limit=None,
                  area_concurrent_limit=1) -> _Trial:
        """
        Create a new trial managed by this manager. Overriden default parameters include:
        * A trial does not require leaders.
        * A trial adds only the creator's area if given a creator, or no area otherwise.

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
            If an int, it is the maximum number of timers the trial will support. If None, it
            indicates the trial will have no timer limit. Defaults to None.
        area_concurrent_limit : int or None, optional
            If an int, it is the maximum number of trials managed by `manager` that any
            area of the created trial may belong to, including the created trial. If None, it
            indicates that this trial does not care about how many other trials managed by
            `manager` each of its areas belongs to. Defaults to 1 (an area may not be a part of
            another trials managed by `manager` while being an area of this trials).

        Returns
        -------
        _Trial
            The created trial.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of minigames.
        Any error from the created trial's add_player(creator)
            If the trial cannot add `creator` to the trial if given one.

        """

        areas = {creator.area} if creator else set()
        trial_factory = functools.partial(_Trial)
        trial = self.new_game(game_type=trial_factory, creator=creator,
                              player_limit=player_limit,
                              player_concurrent_limit=player_concurrent_limit,
                              require_invitations=require_invitations,
                              require_players=require_players,
                              require_leaders=False,
                              require_character=require_character,
                              team_limit=team_limit, timer_limit=timer_limit,
                              areas=areas, area_concurrent_limit=area_concurrent_limit)

        if add_players:
            clients_to_add = {client for area in areas for client in area.clients}
            if creator:
                clients_to_add.discard(creator)
            for client in clients_to_add:
                try:
                    trial.add_player(client)
                except GameError as ex:
                    trial.destroy()
                    raise ex

        # Manually give packets to nonplayers
        for nonplayer in trial.get_nonplayer_users_in_areas():
            trial.introduce_user(nonplayer)

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
