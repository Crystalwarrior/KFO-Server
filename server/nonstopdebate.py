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
Module that contains the nonstop debate game.

"""

import functools
import time

from enum import Enum, auto

from server.exceptions import ClientError, NonStopDebateError
from server import logger
from server.trialminigame import TrialMinigame, TRIALMINIGAMES


class NSDMode(Enum):
    """
    Modes for a nonstop debate.
    """

    PRERECORDING = auto()
    RECORDING = auto()
    LOOPING = auto()
    INTERMISSION = auto()
    INTERMISSION_POSTBREAK = auto()
    INTERMISSION_TIMERANOUT = auto()


class NonStopDebate(TrialMinigame):
    """
    A nonstop debate is a trial game based in its Danganronpa counterpart.

    Attributes
    ----------
    listener : Listener
        Standard listener of the game.

    Callback Methods
    ----------------
    _on_area_client_left
        Method to perform once a client left an area of the game.
    _on_area_client_entered
        Method to perform once a client entered an area of the game.
    _on_area_destroyed
        Method to perform once an area of the game is marked for destruction.
    _on_client_send_ic_check
        Method to perform once a player of the game wants to send an IC message.
    _on_client_send_ic
        Method to perform once a player of the game sends an IC message.
    _on_client_change_character
        Method to perform once a player of the game has changed character.
    _on_client_destroyed
        Method to perform once a player of the game is destroyed.

    """

    # (Private) Attributes
    # --------------------
    # _mode : NSDMode
    #   Current mode of the NSD.
    # _messages : List of Dict of str to Any
    #   Recorded messages to loop
    #
    # Invariants
    # ----------
    # 1. The invariants from the parent class TrialMinigame are satisfied.

    def __init__(self, server, manager, NSD_id, player_limit=None,
                 concurrent_limit=None, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None,
                 timer_limit=None, areas=None, trial=None, timer_start_value=300,
                 playergroup_manager=None):
        """
        Create a new nonstop debate (NSD) game. An NSD should not be fully initialized anywhere
        else other than some manager code, as otherwise the manager will not recognize the NSD.

        Parameters
        ----------
        server : TsuserverDR
            Server the NSD belongs to.
        manager : GameManager
            Manager for this NSD.
        NSD_id : str
            Identifier of the NSD.
        player_limit : int or None, optional
            If an int, it is the maximum number of players the NSD supports. If None, it
            indicates the NSD has no player limit. Defaults to None.
        concurrent_limit : int or None, optional
            If an int, it is the maximum number of games managed by `manager` that any
            player of this NSD may belong to, including this NSD. If None, it indicates
            that this NSD does not care about how many other games managed by `manager` each
            of its players belongs to. Defaults to None.
        require_invitation : bool, optional
            If True, players can only be added to the NSD if they were previously invited. If
            False, no checking for invitations is performed. Defaults to False.
        require_players : bool, optional
            If True, if at any point the NSD has no players left, the NSD will
            automatically be deleted. If False, no such automatic deletion will happen.
            Defaults to True.
        require_leaders : bool, optional
            If True, if at any point the NSD has no leaders left, the NSD will choose a
            leader among any remaining players left; if no players are left, the next player
            added will be made leader. If False, no such automatic assignment will happen.
            Defaults to True.
        require_character : bool, optional
            If False, players without a character will not be allowed to join the NSD, and players
            that switch to something other than a character will be automatically removed from the
            NSD. If False, no such checks are made. A player without a character is considered
            one where player.has_character() returns False. Defaults to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the NSD supports. If None, it
            indicates the NSD has no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of timers the NSD supports. If None, it
            indicates the NSD has no timer limit. Defaults to None.
        areas : set of AreaManager.Area, optional
            Areas the NSD starts with. Defaults to None.
        trial : TrialManager.Trial, optional
            Trial the nonstop debate is a part of. Defaults to None.
        timer_start_value : float, optional
            In seconds, the length of time the main timer of this nonstop debate will have at the
            start. It must be a positive number. Defaults to 300 (5 minutes).
        playergroup_manager : PlayerGroupManager, optional
            The internal playergroup manager of the game manager. Access to this value is
            limited exclusively to this __init__, and is only to initialize the internal
            player group of the NSD.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of NSDs.

        """

        self._mode = NSDMode.PRERECORDING
        self._preintermission_mode = NSDMode.PRERECORDING
        self._messages = list()
        self._message_index = -1

        super().__init__(server, manager, NSD_id, player_limit=player_limit,
                         concurrent_limit=concurrent_limit, require_invitations=require_invitations,
                         require_players=require_players, require_leaders=require_leaders,
                         require_character=require_character, team_limit=team_limit,
                         timer_limit=timer_limit, areas=areas,
                         trial=trial, playergroup_manager=playergroup_manager)

        self._timer = None
        self._message_timer = None
        self._player_refresh_timer = None

        self._timer_start_value = timer_start_value
        self._message_refresh_rate = 7
        self._client_timer_id = 0
        self._breaker = None

    def get_type(self) -> TRIALMINIGAMES:
        """
        Return the type of the minigame (NonStopDebate).

        Returns
        -------
        TRIALMINIGAMES
            Type of minigame.

        """

        return TRIALMINIGAMES.NONSTOP_DEBATE

    def get_mode(self):
        """
        Return the current mode of the nonstop debate.

        Returns
        -------
        NSDMode
            Current mode.

        """

        return self._mode

    def set_prerecording(self):
        """
        Set the NSD to be in prerecording mode (equivalent to recording but before the first
        message is sent, so timer is not unpaused).

        Raises
        ------
        NonStopDebateError.NSDAlreadyInModeError
            If the nonstop debate is already in recording mode.

        Returns
        -------
        None.

        """

        if self._mode == NSDMode.PRERECORDING:
            raise NonStopDebateError.NSDAlreadyInModeError('Nonstop debate is already in this '
                                                           'mode.')
        if self._mode not in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK]:
            raise NonStopDebateError.NSDNotInModeError('You may not set your nonstop debate to be '
                                                       'prerecording at this moment.')

        self._mode = NSDMode.PRERECORDING
        self._preintermission_mode = NSDMode.PRERECORDING

        for user in self.get_users_in_areas():
            user.send_command('GM', 'nsd')
            self._update_player_timer(user)

    def _set_recording(self):
        """
        Set the NSD to be in recording mode.

        Raises
        ------
        NonStopDebateError.NSDAlreadyInModeError
            If the nonstop debate is already in recording mode.

        Returns
        -------
        None.

        """

        if self._mode != NSDMode.PRERECORDING:
            raise RuntimeError(f'Should not have made it here for nsd {self}: {self._mode}')

        self._mode = NSDMode.RECORDING
        self._preintermission_mode = NSDMode.RECORDING
        if self._timer:
            self._timer.unpause()
        self._player_refresh_timer.unpause()
        for user in self.get_users_in_areas():
            user.send_command('GM', 'nsd')
            user.send_command('TR', self._client_timer_id)
            self._update_player_timer(user)

    def set_intermission(self, blankpost=True):
        """
        Set the NSD to be in intermission mode. This will pause the NSD timer, terminate the
        current message timer and order all players to pause their timers and switch to a
        trial gamemode.

        Parameters
        ----------
        blankpost : bool, optional
            If True, it will send a blank system IC message to every player so that they clear
            their screens.

        Raises
        ------
        NonStopDebateError.NSDAlreadyInModeError
            If the nonstop debate is already in intermission mode.
        NonStopDebateError.NSDNotInModeError
            If the nonstop debate is in prerecording mode.

        Returns
        -------
        None.

        """

        if self._mode in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK,
                          NSDMode.INTERMISSION_TIMERANOUT]:
            raise NonStopDebateError.NSDAlreadyInModeError('Nonstop debate is already in this '
                                                           'mode.')
        if self._mode == NSDMode.PRERECORDING:
            raise NonStopDebateError.NSDNotInModeError

        self._mode = NSDMode.INTERMISSION

        if self._timer and not self._timer.paused() and not self._timer.terminated():
            self._timer.pause()
        if self._message_timer and not self._message_timer.paused():
            self._message_timer.pause()
        if self._player_refresh_timer and not self._player_refresh_timer.paused():
            self._player_refresh_timer.pause()

        for user in self.get_users_in_areas():
            user.send_command('TP', self._client_timer_id)
            if blankpost:
                user.send_ic_blankpost()  # Blankpost

        def _variant():
            for user in self.get_users_in_areas():
                user.send_command('GM', 'trial')

        # Delay gamemode switch order by just a bit. This prevents a concurrency issue where
        # clients are unable to start playing the shout animation in time for them to be able
        # to properly delay it.
        variant_timer = self.new_timer(start_value=0, max_value=0.1)
        variant_timer._on_max_end = _variant
        variant_timer.start()

    def _set_intermission_postbreak(self, breaker, blankpost=True):
        self.set_intermission(blankpost=blankpost)
        self._mode = NSDMode.INTERMISSION_POSTBREAK
        self._breaker = breaker

    def _set_intermission_timeranout(self, blankpost=True):
        self.set_intermission(blankpost=blankpost)
        self._mode = NSDMode.INTERMISSION_TIMERANOUT

        for player in self.get_players():
            player.send_ooc('Time ran out for your debate!')
        for leader in self.get_leaders():
            leader.send_ooc('Type /nsd_end to end the debate.')

    def set_looping(self):
        """
        Set the NSD to be in looping mode. This will unpause the NSD timer, order all players
        to switch to an NSD gamemode and resume their timer, display the first message in the loop
        and set up a message timer so the messages transition automatically.

        Raises
        ------
        NonStopDebateError.NSDAlreadyInModeError
            If the nonstop debate is already in looping mode.
        NonStopDebateError.NSDNotInModeError
            If the nonstop debate is not in regular or post-break intermission mode.

        Returns
        -------
        None.

        """

        if self._mode == NSDMode.LOOPING:
            raise NonStopDebateError.NSDAlreadyInModeError('Nonstop debate is already in this '
                                                           'mode.')
        if self._mode not in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK]:
            raise NonStopDebateError.NSDNotInModeError

        self._mode = NSDMode.LOOPING
        self._preintermission_mode = NSDMode.LOOPING
        self._message_index = -1

        if self._timer:
            self._timer.unpause()
        self._player_refresh_timer.unpause()
        self._message_timer.unpause()

        for user in self.get_users_in_areas():
            user.send_command('GM', 'nsd')
            user.send_command('TR', self._client_timer_id)
        self._display_next_message()

    def resume(self) -> NSDMode:
        if self._mode not in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK]:
            raise NonStopDebateError.NSDNotInModeError
        if self._preintermission_mode in [NSDMode.PRERECORDING, NSDMode.RECORDING]:
            self.set_prerecording()
            return NSDMode.PRERECORDING
        if self._preintermission_mode == NSDMode.LOOPING:
            self.set_looping()
            return NSDMode.LOOPING
        raise RuntimeError(f'Should not have made it here for NSD {self}: '
                           f'{self._preintermission_mode}')

    def add_player(self, user):
        """
        Make a user a player of the game. By default this player will not be a leader. It will
        also subscribe the game ot the player so it can listen to its updates.

        It will also send a gamemode change order to the new player that aligns with the current
        mode of the NSD.

        Parameters
        ----------
        user : ClientManager.Client
            User to add to the game. They must be in an area part of the game.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameWithAreasError.UserNotInAreaError
            If the user is not in an area part of the game.
        GameError.UserHasNoCharacterError
            If the user has no character but the game requires that all players have characters.
        GameError.UserNotInvitedError
            If the game requires players be invited to be added and the user is not invited.
        GameError.UserAlreadyPlayerError
            If the user to add is already a user of the game.
        GameError.UserHitConcurrentLimitError
            If the player has reached any of the games it belongs to managed by this game's
            manager concurrent membership limit, or by virtue of joining this game they
            will violate this game's concurrent membership limit.
        GameError.GameIsFullError
            If the game reached its player limit.

        """

        print('NSD adding', user)
        super().add_player(user)

        if not self._timer:
            self._setup_timers()
        self._update_player_timer(user)
        if self._timer and self._timer.paused():
            user.send_command('TP', self._client_timer_id)

        if self._mode in [NSDMode.LOOPING, NSDMode.RECORDING, NSDMode.PRERECORDING]:
            user.send_command('GM', 'nsd')
            user.send_command('RT', 'testimony4')
        elif self._mode in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK,
                            NSDMode.INTERMISSION_TIMERANOUT]:
            user.send_command('GM', 'trial')
        else:
            raise RuntimeError(f'Unrecognized mode {self._mode}')

    def remove_player(self, user):
        """
        Make a user be no longer a player of this game. If they were part of a team managed by
        this game, they will also be removed from said team. It will also unsubscribe the game
        from the player so it will no longer listen to its updates. It will also send an order to
        the player to go back to its default theme gamemode.

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

        super().remove_player(user)
        user.send_command('GM', 'trial')

    def accept_break(self) -> bool:
        """
        Accepts a break and increases the breaker's influence by 0.5, provided they are still a
        player of the NSD and connected to the server. Regardless, this also destroys the nonstop
        debate.

        Raises
        ------
        NonStopDebateError.NSDNotInModeError
            If the nonstop debate is not in postbreak intermission mode.

        Returns
        -------
        bool
            True if the breaker was a player of the NSD and is connected to the server, False
            otherwise.

        """

        if not self._mode == NSDMode.INTERMISSION_POSTBREAK:
            raise NonStopDebateError.NSDNotInModeError

        is_player = self._server.is_client(self._breaker) and self.is_player(self._breaker)
        if is_player:
            self._breaker.send_ooc('Your break was accepted and you recovered 0.5 influence.')
            self.get_trial().change_influence_by(self._breaker, 0.5)

        self.destroy()
        return is_player

    def reject_break(self) -> bool:
        """
        Rejects a break, and decreases the breaker's influence by 1, provided they are still a
        player of the NSD and connected to the server. This puts the debate in standard
        intermission mode.

        Raises
        ------
        NonStopDebateError.NSDNotInModeError
            If the nonstop debate is not in postbreak intermission mode.

        Returns
        -------
        bool
            True if the breaker was a player of the NSD and is connected to the server, False
            otherwise.

        """

        if not self._mode == NSDMode.INTERMISSION_POSTBREAK:
            raise NonStopDebateError.NSDNotInModeError

        is_player = self._server.is_client(self._breaker) and self.is_player(self._breaker)
        if is_player:
            self._breaker.send_ooc('Your break was rejected and you lost 1 influence.')
            self.get_trial().change_influence_by(self._breaker, -1)

        self._mode = NSDMode.INTERMISSION
        self._breaker = None

        return is_player

    def destroy(self):
        """
        Mark this game as destroyed and notify its manager so that it is deleted.
        If the game is already destroyed, this function does nothing.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        # First, send order to pause and zero timer for all users. This is needed because it is
        # possible to destroy an NSD while the timer is still running, and not handling this would
        # mean the client timer will still be running.

        for user in self.get_users_in_areas():
            user.send_command('TST', self._client_timer_id, 0)
            user.send_command('TP', self._client_timer_id)

        # Then carry on
        super().destroy()

    def _setup_timers(self):
        """
        Setup the internal timers.

        Returns
        -------
        None.

        """

        PLAYER_REFRESH_RATE = 5
        self._player_refresh_timer = self.new_timer(start_value=0, max_value=PLAYER_REFRESH_RATE,
                                                    auto_restart=True)
        def _refresh():
            print(time.time())
            for user in self.get_users_in_areas():
                self._update_player_timer(user)

        self._player_refresh_timer._on_max_end = _refresh

        self._message_timer = self.new_timer(start_value=0, max_value=self._message_refresh_rate,
                                             auto_restart=True)
        self._message_timer._on_max_end = self._display_next_message

        if self._timer_start_value > 0:
            self._timer = self.new_timer(start_value=self._timer_start_value,
                                         tick_rate=-1, min_value=0)
            self._timer._on_min_end = functools.partial(
                self._set_intermission_timeranout, blankpost=True)

    def _update_player_timer(self, player):
        if not self._timer:
            player.send_command('TST', self._client_timer_id, 0)
            player.send_command('TSS', self._client_timer_id, 0)
            player.send_command('TSF', self._client_timer_id, 0)
        else:
            player.send_command('TST', self._client_timer_id,
                                round(self._timer.get()*1000))
            player.send_command('TSS', self._client_timer_id,
                                round(-0.016*1000))
            player.send_command('TSF', self._client_timer_id,
                                round(0.016*1000))

    def _on_area_client_send_ic_check(self, area, client=None, contents=None):
        """
        Check if any of the following situations occur:
        * If the user is not part of the nonstop debate.

        If none of the above is true, allow the IC message as is.

        Parameters
        ----------
        area : AreaManager.Area
            Area of the user that wants to send the IC message.
        client : ClientManager.Client
            Client that wants to send the IC message (possibly not a player of the nonstop debate).
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Raises
        ------
        ClientError
            If any of the above disquaLifying situations is true.

        Returns
        -------
        None.

        """

        if not self.is_player(client):
            raise ClientError('You are not a player of this nonstop debate.')

    def _on_client_send_ic_check(self, player, contents=None):
        """
        Check if any of the following situations occur:
        * If they want to send a message with a bullet other than consent/counter at any point.
        * If they want to send a message with a bullet before any messages were recorded.
        * If they want to send a message with a bullet during intermission mode.
        * If they want to send a message without a bullet during looping mode.

        If none of the above is true, allow the IC message as is.

        Parameters
        ----------
        player : ClientManager.Client
            Player that wants to send the IC message.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Raises
        ------
        ClientError
            If any of the above disquaLifying situations is true.

        Returns
        -------
        None.

        """

        # Trying to do anything other than counter/consent
        if contents['button'] not in {0, 1, 2, 7, 8}:
            raise ClientError('You may not perform that action during a nonstop debate.')
        # Before a message was even sent
        if contents['button'] in {1, 2, 7, 8} and self._message_index == -1:
            raise ClientError('You may not use a bullet now.')
        # Trying to bullet during intermission
        if contents['button'] != 0 and self._mode in [NSDMode.INTERMISSION,
                                                      NSDMode.INTERMISSION_POSTBREAK,
                                                      NSDMode.INTERMISSION_TIMERANOUT]:
            raise ClientError('You may not use a bullet now.')
        # Trying to talk during looping mode
        if contents['button'] == 0 and self._mode == NSDMode.LOOPING:
            raise ClientError('You may not speak now except if using a bullet.')
        # For perjury
        if contents['button'] == 8:
            func = lambda c: 8 if c in {player}.union(self.get_leaders()) else 7
            contents['PER_CLIENT_button'] = func

    def _on_client_send_ic(self, player, contents=None):
        """
        Add message of player to record of messages.

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

        if self._mode == NSDMode.PRERECORDING:
            self._set_recording()

        # Not an elif!
        if self._mode == NSDMode.RECORDING:
            # Check if player bulleted during recording mode, and whether it makes sense to do that
            if contents['button'] > 0:
                self._break_loop(player, contents)
            else:
                self._add_message(player, contents=contents)
        elif self._mode in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK,
                            NSDMode.INTERMISSION_TIMERANOUT]:
            # Nothing particular
            pass
        elif self._mode == NSDMode.LOOPING:
            # NSD already verified the IC message should go through
            # This is a break!
            self._break_loop(player, contents)
        else:
            raise RuntimeError(f'Unrecognized mode {self._mode}')

    def _on_area_client_left(self, area, client=None, new_area=None, old_displayname=None,
                             ignore_bleeding=False):
        """
        If a player left to an area not part of the NSD, remove the player and warn them and
        the leaders of the NSD.

        If a non-plyer left to an area not part of the NSD, warn them and the leaders of the
        NSD.

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

        was_leader = self.is_leader(client) if self.is_player(client) else False
        if client in self.get_players():
            client.send_ooc(f'You have left to an area not part of NSD '
                            f'`{self.get_id()}` and thus were automatically removed from the '
                            f'NSD.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to '
                                   f'an area not part of your NSD and thus was '
                                   f'automatically removed from it ({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())

            self.remove_player(client)
            if self.is_unmanaged():
                if was_leader:
                    client.send_ooc(f'Your NSD `{self.get_id()}` was automatically '
                                    f'deleted as it lost all its players.')
                client.send_ooc_others(f'(X) NSD `{self.get_id()}` was automatically '
                                       f'deleted as it lost all its players.',
                                       is_zstaff_flex=True)
        else:
            client.send_ooc(f'You have left to an area not part of NSD '
                            f'`{self.get_id()}`.')
            client.send_ooc_others(f'(X) Player {old_displayname} [{client.id}] has left to an '
                                   f'area not part of your NSD '
                                   f'({area.id}->{new_area.id}).',
                                   pred=lambda c: c in self.get_leaders())
            client.send_command('GM', '')

        self._check_structure()

    def _on_area_client_entered(self, area, client=None, old_area=None, old_displayname=None,
                                ignore_bleeding=False):
        """
        If a non-player entered, warn them and the leaders of the NSD.

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

        if old_area in self.get_areas():
            return

        if client not in self.get_players():
            client.send_ooc(f'You have entered an area part of NSD `{self.get_id()}`.')
            if client.is_staff():
                client.send_ooc(f'Join this NSD with /nsd_join {self.get_id()}')
            client.send_ooc_others(f'(X) Non-player {client.displayname} [{client.id}] has entered '
                                   f'an area part of your NSD '
                                   f'({old_area.id}->{area.id}).',
                                   pred=lambda c: c in self.get_leaders())
            client.send_ooc_others(f'(X) Add {client.displayname} to your NSD with '
                                   f'/nsd_add {client.id}')

            if self._mode in [NSDMode.LOOPING, NSDMode.RECORDING, NSDMode.PRERECORDING]:
                client.send_command('GM', 'nsd')
            elif self._mode in [NSDMode.INTERMISSION, NSDMode.INTERMISSION_POSTBREAK,
                                NSDMode.INTERMISSION_TIMERANOUT]:
                client.send_command('GM', 'trial')
            else:
                raise RuntimeError(f'Unrecognized mode {self._mode}')

    def _add_message(self, player, contents=None):
        """
        Add a message to the log of messages of the NSD. If the NSD timer is paused, it will also
        resume the timer.

        Parameters
        ----------
        player : ClientManager.Client
            Player who spoke.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Returns
        -------
        None.

        """

        self._messages.append([player, contents])
        self._message_index += 1
        if self._timer and self._timer.paused():
            self._timer.unpause()
            for user in self.get_users_in_areas():
                user.send_command('TR', self._client_timer_id)

    def _display_next_message(self):
        """
        If there are still messages pending in the next NSD loop, send the next one to every player.
        Otherwise, enter intermission mode.

        Returns
        -------
        None.

        """

        # -1 avoids fencepost error
        if self._message_index < len(self._messages)-1:
            self._message_index += 1
            sender, contents = self._messages[self._message_index]
            for user in self.get_users_in_areas():
                user.send_ic(params=contents, sender=sender)
            logger.log_server('[IC][{}][{}][NSD]{}'
                  .format(sender.area.id, sender.get_char_name(), contents['msg']), sender)
        else:
            self.set_intermission()

    def _break_loop(self, player, contents):
        """
        Handle 'break' logic. It will send OOC messages to the breaker and the leaders of the NSD
        indicating of this event, and set the NSD mode to intermission with a 3 second delay.

        Parameters
        ----------
        player : ClientManager.Client
            Player who 'broke'.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Returns
        -------
        None.

        """

        bullet_actions = {
            1: 'consented with',
            2: 'countered',
            # 3: 'argued',
            # 4: 'mc'd',
            # 5: 'got it',
            # 6: 'cut',
            7: 'countered',
            8: 'committed perjury by countering',
            }
        regular_bullet_actions = bullet_actions.copy()
        regular_bullet_actions[8] = 'countered'

        broken_player, broken_ic = self._messages[self._message_index]
        action = bullet_actions[contents['button']]
        regular_action = regular_bullet_actions[contents['button']]

        player.send_ooc(f"You {action} {broken_player.displayname}'s statement "
                        f"`{broken_ic['text']}`")
        for leader in self.get_leaders():
            leader.send_ooc(f"{player.displayname} {action} {broken_player.displayname}'s "
                            f"statement `{broken_ic['text']}`")
            leader.send_ooc("Type /nsd_accept to accept the break and end the debate, "
                            "/nsd_reject to reject the break and penalize the breaker, "
                            "/nsd_resume to resume the debate where it was, and "
                            "/nsd_end to end the debate.")
        for regular in self.get_regulars():
            regular.send_ooc(f"{player.displayname} {regular_action} "
                             f"{broken_player.displayname}'s statement "
                             f"`{broken_ic['text']}`")
        self._set_intermission_postbreak(player, blankpost=False)

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        super()._check_structure()

    def __str__(self):
        """
        Return a string representation of this nonstop debate.

        Returns
        -------
        str
            Representation.

        """

        return (f"NonStopDebate::{self.get_id()}:{self.get_trial()}"
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

        return (f'NonStopDebate(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'player_limit={self._playergroup._player_limit}, '
                f'concurrent_limit={self.get_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager.get_group_limit()}, '
                f'timer_limit={self._timer_manager.get_timer_limit()}, '
                f'areas={self.get_areas()}, '
                f'trial={self.get_trial().get_id()}) || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_timers()}, '
                f'teams={self.get_teams()}')
