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
Module that contains the base game with areas class.
"""

import functools

from server.exceptions import GameWithAreasError, GameError
from server.game_manager import _Game, GameManager


class GameWithAreas(_Game):
    """
    A game with areas is a game that manages and subscribes to its areas' updates.
    Any player of such a game must be in an area of the game. If a player of the game goes to an
    area not part of the game, they are removed automatically from the game. If an area is removed
    from the set of areas of the game, all players in that area are removed in some unspecified
    order.
    Each of these games may also impose a concurrent area membership limit, so that every area
    part of a game with areas is at most an area of that many games with areas managed by this
    games's manager.

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
    # _areas : set of AreaManager.Area
    #   Areas of the game.
    #
    # Invariants
    # ----------
    # 1. For each player of the game, they are in an area part of the game.
    # 2. The invariants from the parent class Game are satisfied.

    def __init__(self, server, manager, game_id, player_limit=None,
                 player_concurrent_limit=None, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None,
                 timer_limit=None, area_concurrent_limit=None,
                 playergroup_manager=None):
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
            If False, players without a character will not be allowed to join the game, and players
            that switch to something other than a character will be automatically removed from the
            game. If False, no such checks are made. A player without a character is considered
            one where player.has_character() returns False. Defaults to False.
        team_limit : int or None, optional
            If an int, it is the maximum number of teams the game supports. If None, it
            indicates the game has no team limit. Defaults to None.
        timer_limit : int or None, optional
            If an int, it is the maximum number of timers the game supports. If None, it
            indicates the game has no timer limit. Defaults to None.
        area_concurrent_limit : int or None, optional
            If an int, it is the maximum number of games with areas managed by `manager` that any
            area of this game may belong to, including this game. If None, it indicates
            that this game does not care about how many other game with areas managed by
            `manager` each of its areas belongs to. Defaults to 1 (an area may not be a part of
            another game managed by `manager` while being an area of this game).
        playergroup_manager : PlayerGroupManager, optional
            The internal playergroup manager of the game manager. Access to this value is
            limited exclusively to this __init__, and is only to initialize the internal
            player group of the game.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.
        GameWithAreasError.AreaHitGameConcurrentLimitError.
            If an area in `areas` has reached the concurrent area membership limit of any of the
            games it belongs to managed by this manager, or by virtue of adding this area it will
            violate this game's concurrent area membership limit.

        """

        self._areas = set()
        self._area_concurrent_limit = area_concurrent_limit

        super().__init__(server, manager, game_id, player_limit=player_limit,
                         player_concurrent_limit=player_concurrent_limit,
                         require_invitations=require_invitations,
                         require_players=require_players, require_leaders=require_leaders,
                         require_character=require_character,
                         team_limit=team_limit, timer_limit=timer_limit,
                         playergroup_manager=playergroup_manager)

        self.listener.subscribe(self._server.area_manager)
        self.listener.update_events({
            'area_client_left': self._on_area_client_left,
            'area_client_entered': self._on_area_client_entered,
            'area_client_inbound_ms_check': self._on_area_client_inbound_ms_check,
            'area_destroyed': self._on_area_destroyed,
            'areas_loaded': self._on_areas_loaded,
            })

    def add_player(self, user):
        """
        Make a user a player of the game. By default this player will not be a leader. It will
        also subscribe the game ot the player so it can listen to its updates.

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
        GameError.UserHitGameConcurrentLimitError
            If the player has reached any of the games it belongs to managed by this game's
            manager concurrent player membership limit, or by virtue of joining this game they
            will violate this game's concurrent player membership limit.
        GameError.GameIsFullError
            If the game reached its player limit.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError
        # Check user in area before doing the rest of the add player code.
        if user.area not in self._areas:
            raise GameWithAreasError.UserNotInAreaError

        super().add_player(user)  # Also calls _check_structure()

    def add_area(self, area):
        """
        Add an area to this game's set of areas.

        Parameters
        ----------
        area : AreaManager.Area
            Area to add.

        Raises
        ------
        GameError.GameIsUnmanagedError
            If the game was scheduled for deletion and thus does not accept any mutator
            public method calls.
        GameWithAreasError.AreaAlreadyInGameError
            If the area is already part of the game.
        GameWithAreasError.AreaHitGameConcurrentLimitError.
            If `area` has reached the concurrent area membership limit of any of the games it
            belongs to managed by this manager, or by virtue of adding this area it will violate
            this game's concurrent area membership limit.

        Returns
        -------
        None.

        """

        if self.is_unmanaged():
            raise GameError.GameIsUnmanagedError
        if area in self._areas:
            raise GameWithAreasError.AreaAlreadyInGameError

        self._areas.add(area)
        self.listener.subscribe(area)
        try:
            self._manager._add_area_to_mapping(area, self)
        except GameWithAreasError.AreaHitGameConcurrentLimitError as ex:
            self._areas.discard(area)
            self.listener.unsubscribe(area)
            raise ex

        self._check_structure()

    def remove_area(self, area):
        """
        Remove an area from this game's set of areas. If the area is already a part of the game, do
        nothing. If any player of the game is in this area, they are removed from the game. If the
        game has no areas remaining, it will be automatically destroyed.

        Parameters
        ----------
        area : AreaManager.Area
            Area to remove.

        Raises
        ------
        GameWithAreasError.AreaNotInGameError
            If the area is already not part of the game.

        Returns
        -------
        None.

        """

        # No legitimate call of remove_area can happen if the game is unmanaged as it has no areas
        # if self.is_unmanaged():
        #     raise GameError.GameIsUnmanagedError
        if area not in self._areas:
            raise GameWithAreasError.AreaNotInGameError

        # Implementation detail: we may not simply check if client.area == area. That is because it
        # may be the case a player was moved as a result of the area being destroyed, which is one
        # of the events that triggers this method. Moreover, as the change_area code in area reloads
        # does not trigger the publishers, we cannot necessarily assume that _on_area_client_left
        # will do our checks.
        # However, we can check ourselves manually: if a player of the game is in an area not
        # part of the game, remove them.
        # As area is in self._areas (by earlier check), we do not need to check
        faulty_players = self.get_players(cond=lambda client: client.area == area)
        for player in faulty_players:
            self.remove_player(player)
        # Remove area only after removing all players to prevent structural checks failing
        self._areas.discard(area)
        self.listener.unsubscribe(area)
        self._manager._remove_area_from_mapping(area, self)
        if not self._areas:
            self.destroy()

        self._check_structure()

    def has_area(self, area):
        """
        If the area is part of this game's set of areas, return True; otherwise, return False.

        Parameters
        ----------
        area : AreaManager.Area
            Area to check.

        Returns
        -------
        bool
            True if the area is part of the game's set of areas, False otherwise.

        """

        return area in self._areas

    def get_areas(self):
        """
        Return (a shallow copy of) the set of areas of this game.

        Returns
        -------
        set of AreaManager.Area
            Set of areas of the game.

        """

        return self._areas.copy()

    def get_area_concurrent_limit(self):
        """
        Return the concurrent area membership limit of this game.

        Returns
        -------
        int or None
            The concurrent area membership limit.

        """

        return self._area_concurrent_limit

    def get_users_in_areas(self):
        """
        Return all users in areas part of the game, even those that are not players of the game.

        Returns
        -------
        users : set of ClientManager.Client
            All users in areas part of the game.

        """

        clients = list()
        for area in self._areas:
            clients.extend(area.clients)
        return set(clients)

    def get_nonleader_users_in_areas(self):
        """
        Return all users in areas part of the game, even those that are not players of the game,
        such that they are not leaders of the game.

        Returns
        -------
        users : set of ClientManager.Client
            All users in areas part of the game that are not leaders of the game.

        """

        return {client for client in self.get_users_in_areas()
                if not (self.is_player(client) and self.is_leader(client))}

    def get_nonplayer_users_in_areas(self):
        """
        Return all users in areas part of the game that are not players of the game.

        Returns
        -------
        users : set of ClientManager.Client
            All users in areas part of the game that are not players of the game.

        """

        return {client for client in self.get_users_in_areas() if not self.is_player(client)}

    def destroy(self):
        """
        Mark this game as destroyed and notify its manager so that it is deleted.
        If the game is already destroyed, this function does nothing.

        This method is reentrant (it will do nothing though).

        Returns
        -------
        None.

        """

        # Remove areas too. This is done first so that structural checks can take place after
        # areas are removed.
        for area in self.get_areas():
            self.remove_area(area)
        super().destroy()  # Also calls _check_structure()

    def __str__(self):
        """
        Return a string representation of this game.

        Returns
        -------
        str
            Representation.

        """

        return (f"GameWithAreas::{self.get_id()}:"
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

        return (f'GameWithAreas(server, {self._manager.get_id()}, "{self.get_id()}", '
                f'player_limit={self._playergroup._player_limit}, '
                f'player_concurrent_limit={self.get_player_concurrent_limit()}, '
                f'require_players={self._playergroup._require_players}, '
                f'require_invitations={self._playergroup._require_invitations}, '
                f'require_leaders={self._playergroup._require_leaders}, '
                f'require_character={self._require_character}, '
                f'team_limit={self._team_manager.get_group_limit()}, '
                f'timer_limit={self._timer_manager.get_timer_limit()}, '
                f'areas={self.get_areas()}) || '
                f'players={self.get_players()}, '
                f'invitations={self.get_invitations()}, '
                f'leaders={self.get_leaders()}, '
                f'timers={self.get_timers()}, '
                f'teams={self.get_teams()}')

    def _on_area_client_left(self, area, client=None, new_area=None, old_displayname=None,
                             ignore_bleeding=False):
        """
        Default callback for game area signaling a client left.

        By default it removes the player from the game if their new area is not part of the game.

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

        print('Received LEFT', area, client, new_area, old_displayname, ignore_bleeding)
        if client in self.get_players() and new_area not in self._areas:
            self.remove_player(client)

        self._check_structure()

    def _on_area_client_entered(self, area, client=None, old_area=None, old_displayname=None,
                                ignore_bleeding=False):
        """
        Default callback for game area signaling a client entered.

        By default does nothing.

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

        print('Received ENTERED', area, client, old_area, old_displayname, ignore_bleeding)

        self._check_structure()

    def _on_area_client_inbound_ms_check(self, area, client=None, contents=None):
        """
        Default callback for game area signaling a client in the area sent an IC message. Unlike
        the ClientManager.Client callback for send_ic_check, this one is triggered regardless of
        whether the sender is part of the game or not. This is useful for example, to filter
        out messages sent by non-players.

        By default does nothing.

        Parameters
        ----------
        area : AreaManager.Area
            Area that signaled a client has entered.
        client : ClientManager.Client, optional
            The client that has send the IC message. The default is None.
        contents : dict of str to Any
            Arguments of the IC message as indicated in AOProtocol.

        Returns
        -------
        None.

        """

        print('User', client, 'in area', area, 'wants to check sent', contents)

        self._check_structure()

    def _on_area_destroyed(self, area):
        """
        Default callback for game area signaling it was destroyed.

        By default it calls self.remove_area(area).

        Parameters
        ----------
        area : AreaManager.Area
            Area that signaled it was destroyed.

        Returns
        -------
        None.

        """

        print('Received DESTRUCTION', area)
        self.remove_area(area)

        self._check_structure()

    def _on_areas_loaded(self, area_manager):
        """
        Default callback for server area manager signaling it loaded new areas.

        By default it calls self.destroy().

        Parameters
        ----------
        area_manager : AreaManager
            AreaManager that signaled the area loads

        Returns
        -------
        None.

        """

        self.destroy()

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        for player in self.get_players():
            err = (f'For game with areas {self}, expected that its player {player} was in an area '
                   f'part of the game, found they were in area {player.area} instead.')
            assert player.area in self._areas, err

        # 2.
        super()._check_structure()


class GameWithAreasManager(GameManager):
    """
    A game with areas manager is a game manager with dedicated area management functions.

    """

    # TODO: Enforce GameWithAreasManager to only take game with areas as games when calling
    # new_game, or when initialized. Also do it in check_structure()

    def __init__(self, server, game_limit=None, default_game_type=None,
                 available_id_producer=None):
        """
        Create a game with areas manager object.

        Parameters
        ----------
        server : TsuserverDR
            The server this game with areas manager belongs to.
        game_limit : int, optional
            The maximum number of games this manager can handle. Defaults to None (no limit).
        default_game_type : GameWithAreas, optional
            The default type of game this manager will create. Defaults to None (and then
            converted to GameWithAreas).
        available_id_producer : typing.types.FunctionType, optional
            Function to produce available game IDs. It will override the built-in class method
            get_available_game_id. Defaults to None (and then converted to the built-in
            get_available_game_id).

        """

        if default_game_type is None:
            default_game_type = GameWithAreas
        self._area_to_games = dict()

        super().__init__(server, game_limit=game_limit, default_game_type=default_game_type,
                         available_id_producer=available_id_producer)

    def new_game(self, game_type=None, creator=None, player_limit=None,
                 player_concurrent_limit=1, require_invitations=False, require_players=True,
                 require_leaders=True, require_character=False, team_limit=None, timer_limit=None,
                 areas=None, area_concurrent_limit=None):
        """
        Create a new game with areas managed by this manager.

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
        areas : set of AreaManager.Area, optional
            Areas the game starts with. Defaults to None (and converted to an empty set).
        area_concurrent_limit : int or None, optional
            If an int, it is the maximum number of games with areas managed by `manager` that any
            area of this game may belong to, including this game. If None, it indicates
            that this game does not care about how many other game with areas managed by
            `manager` each of its areas belongs to. Defaults to 1 (an area may not be a part of
            another game managed by `manager` while being an area of this game).

        Returns
        -------
        GameWithAreas
            The created game.

        Raises
        ------
        GameError.ManagerTooManyGamesError
            If the manager is already managing its maximum number of games.
        Any error from the created game's add_player(creator)
            If the game cannot add `creator` as a player if given one.

        """

        if game_type is None:
            game_type = self._default_game_type

        new_game_type = functools.partial(game_type,
                                          area_concurrent_limit=area_concurrent_limit)

        game = super().new_game(game_type=new_game_type, creator=None, player_limit=player_limit,
                                player_concurrent_limit=player_concurrent_limit,
                                require_invitations=require_invitations,
                                require_players=require_players,
                                require_leaders=require_leaders,
                                require_character=require_character,
                                team_limit=team_limit,
                                timer_limit=timer_limit)

        try:
            for area in areas:
                game.add_area(area)
        except GameError as ex:
            # Discard game
            self.delete_game(game)
            raise ex

        # Add creator manually. This is because adding it via .new_game will yield errors because
        # the areas are not added until the section before.
        try:
            if creator:
                game.add_player(creator)
        except GameError as ex:
            # Discard game
            self.delete_game(game)
            raise ex

        return game

    def get_games_in_area(self, area):
        """
        Return (a shallow copy of) the all games managed by this manager that contain the given
        area.

        Parameters
        ----------
        area : AreaManager.Area
            Area that all returned games must contain.

        Returns
        -------
        set of GameWithAreas
            Games that contain the given area.

        """

        try:
            return self._area_to_games[area].copy()
        except:
            return set()

    def _find_area_concurrent_limiting_game(self, area):
        """
        For area `area`, find a game with areas `most_restrictive_game` managed by this manager
        such that, if `area` were to be added to another game managed by this manager, they would
        violate `most_restrictive_game`'s concurrent area membership limit.
        If no such game exists (or the area is not an area of any game with areas managed by this
        manager), return None.
        If multiple such games exist, any one of them may be returned.

        Parameters
        ----------
        area : AreaManager.Area
            Area to test.

        Returns
        -------
        GameWithAreas or None
            Limiting game with areas as previously described if it exists, None otherwise.

        """

        games = self.get_games_in_area(area)
        if not games:
            return None

        # We only care about groups that establish a concurrent area membership limit
        games_with_limit = {game for game in games
                            if game.get_area_concurrent_limit() is not None}
        if not games_with_limit:
            return None

        # It just suffices to analyze the game with the smallest limit, because:
        # 1. If the area is part of at least as many games as this game's limit, this game
        # is an example game that can be returned.
        # 2. Otherwise, no other games exist due to the minimality condition.
        most_restrictive_game = min(games_with_limit,
                                    key=lambda game: game.get_area_concurrent_limit())
        if len(games) < most_restrictive_game.get_area_concurrent_limit():
            return None
        return most_restrictive_game

    def _add_area_to_mapping(self, area, game):
        """
        Update the area to game with areas mapping with the information that `area` was added to
        `game`.

        Parameters
        ----------
        area : ClientManager.Client
            Area that was added.
        game : GameWithAreas
            Game with areas that `area` was added to.

        Raises
        ------
        GameWithAreasError.AreaHitGameConcurrentLimitError.
            If `area` has reached the concurrent area membership limit of any of the games it
            belongs to managed by this manager, or by virtue of adding this area to `game` it
            will violate this game's concurrent area membership limit.

        Returns
        -------
        None.

        """

        if self._find_area_concurrent_limiting_game(area):
            raise GameWithAreasError.AreaHitGameConcurrentLimitError

        try:
            self._area_to_games[area].add(game)
        except KeyError:
            self._area_to_games[area] = {game}

    def _remove_area_from_mapping(self, area, game):
        """
        Update the area to game with areas mapping with the information that `area` was removed
        from `game`.
        If the area is already not associated with that game, or is not part of the mapping,
        this method will not do anything.

        Parameters
        ----------
        area : ClientManager.Client
            Area that was removed.
        game : GameWithAreas
            Game with areas that `area` was removed from.

        Returns
        -------
        None.

        """

        try:
            self._area_to_games[area].remove(game)
        except (KeyError, ValueError):
            return

        if not self._area_to_games[area]:
            self._area_to_games.pop(area)

    def _check_structure(self):
        """
        Assert that all invariants specified in the class description are maintained.

        Raises
        ------
        AssertionError
            If any of the invariants are not maintained.

        """

        # 1.
        for area in self._area_to_games:
            games = self._area_to_games[area]

            # a.
            err = (f'For game with areas manager {self}, expected that area {area} to only appear '
                   f'in the area to game with areas mapping if it was a area of any area '
                   f'game managed by this manager, but found it appeared while not belonging to '
                   f'any game with areas. || {self}')
            assert games, err

            for game in games:
                # b.
                err = (f'For game with areas manager {self}, expected that game with areas {game} '
                       f'that appears in the area to game with areas mapping for area {area} '
                       f'also appears in the game with areas ID to game with areas mapping, but '
                       f'found it did not. || {self}')
                assert game in self.get_games(), err

                # c.
                err = (f'For game with areas manager {self}, expected that area {area} in the area '
                       f'to game mapping be a area of its associated game {game}, but '
                       f'found that was not the case. || {self}')
                assert area in game.get_areas(), err

        # 2.
        for area in self._area_to_games:
            games = self._area_to_games[area]
            membership = len(games)

            for game in games:
                limit = game.get_area_concurrent_limit()

                if limit is None:
                    continue
                err = (f'For game with areas manager {self}, expected that area {area} in game '
                       f'{game} belonged to at most the concurrent area membership limit of '
                       f'that game of {limit} game{"s" if limit != 1 else ""}, found it '
                       f'belonged to {membership} game{"s" if membership != 1 else ""}. || {self}')
                assert membership <= limit

        # Last
        super()._check_structure()

    def __repr__(self):
        """
        Return a representation of this game with areas manager.

        Returns
        -------
        str
            Printable representation.

        """

        return (f"GameWithAreasManager(server, game_limit={self.get_game_limit()}, "
                f"|| "
                f"_area_to_games={self._area_to_games}, "
                f"id={hex(id(self))})")
