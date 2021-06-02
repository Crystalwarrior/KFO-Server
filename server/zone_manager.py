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
Module that contains the ZoneManager class, which itself contains the Zone subclass.

Zones group areas together such that it allows notifications to only propagate to areas in the zone,
as well as perform tasks only on the areas of the zone.
"""

from __future__ import annotations
import typing
from typing import Any, Set
if typing.TYPE_CHECKING:
    # Avoid circular referencing
    from server.area_manager import AreaManager
    from server.client_manager import ClientManager
    from server.tsuserver import TsuserverDR

from server.constants import Constants
from server.exceptions import ClientError, ZoneError
from server.subscriber import Listener

class ZoneManager:
    """
    A mutable data type for a manager for the zones in a server.
    Contains the Zone object definition, as well as the server's zone list.
    """

    class Zone:
        """
        A zone is a group of areas with some watchers who will receive notifications about events
        that occur in areas in the zone.
        """

        def __init__(self, server: TsuserverDR, zone_id: str, areas: Set[AreaManager.Area],
                     watchers: Set[ClientManager.Client]):
            """
            Initialization method for a zone.

            Parameters
            ----------
            server: TsuserverDR
                Server the zone belongs to
            zone_id: str
                Identifier of zone.
            areas: set of AreaManager.Area
                Set of areas the zone covers.
            watchers: set of ClientManager.Client
                Set of clients who are watching the zone.
            """

            self._server = server
            self._zone_id = zone_id
            self._areas = set()
            self._watchers = set()

            self._players = set()
            self._properties = dict()
            self._mode = ''

            self._is_deleted = False
            self.listener = Listener(self, {
                        'area_client_left_final': self._on_area_client_left_final,
                        'area_client_entered_final': self._on_area_client_entered_final,
                        'client_destroyed': self._on_client_destroyed,
                        })

            self._add_areas(areas)
            self._add_watchers(watchers)

        def add_area(self, area: AreaManager.Area):
            """
            Add an area to the zone area set if it was not there already.

            This also sets the zone of the given area to the current zone.

            Parameters
            ----------
            area: AreaManager.Area
                Area to add to the zone area set.
            """

            self.add_areas({area})

        def add_areas(self, areas: Set[AreaManager.Area]):
            """
            Add a set of areas to the zone area set if ALL areas were not part of a zone already.

            This also sets the zone of the given areas to the current zone.

            Parameters
            ----------
            areas: set of AreaManager.Area
                Areas to add to the zone area set.

            Raises
            ------
            ZoneError.AreaConflictError:
                If any of the given areas is already a part of some zone area set.
            """

            self._add_areas(areas)
            self._check_structure()

        def _add_areas(self, areas: Set[AreaManager.Area]):
            for area in areas:
                if area.in_zone:
                    raise ZoneError.AreaConflictError('Area {} is already part of zone {}.'
                                                      .format(area, area.in_zone))

            for area in areas:
                self._areas.add(area)
                self.listener.subscribe(area)
                area.in_zone = self
                for client in area.clients:
                    self._add_player(client)

        def get_areas(self) -> Set[AreaManager.Area]:
            """
            Return all of the zone's areas.

            Returns
            -------
            set of AreaManager.Area:
                All of the areas part of the zone.
            """

            return self._areas.copy()

        def is_area(self, area: AreaManager.Area) -> bool:
            """
            Return True if the area is part of the zone's area list, False otherwise.

            Parameters
            ----------
            area : AreaManager.Area
                Area to check.

            Returns
            -------
            bool
                True if the area is part of the zone's area list, False otherwise.
            """

            return area in self._areas

        def remove_area(self, area: AreaManager.Area):
            """
            Remove an area from the zone area set if it was there.

            This also sets the zone of the given area to None.

            Parameters
            ----------
            area: AreaManager.Area
                Area to remove from the zone area set.

            Raises
            ------
            KeyError:
                If the area is not part of the zone area set.
            """

            self._remove_area(area)
            self._check_structure()

        def _remove_area(self, area: AreaManager.Area):
            if area not in self._areas:
                raise ZoneError.AreaNotInZoneError('Area {} is not part of zone {}.'
                                                   .format(area, self))

            self._areas.remove(area)
            self._cleanup_removed_area(area)

            for client in area.clients:
                self._remove_player(client)

            # If no more areas, delete the zone
            if not self._areas:
                self._server.zone_manager.delete_zone(self._zone_id)

        def _cleanup_removed_area(self, area: AreaManager.Area):
            self.listener.unsubscribe(area)
            area.in_zone = None

        def get_id(self) -> str:
            """
            Return the zone ID.

            Returns
            -------
            str:
                The ID of the zone.
            """

            return self._zone_id

        def add_watcher(self, user: ClientManager.Client):
            """
            Add a user to the zone watcher set if it was not there already.

            This also sets the watched zone of the watcher to the current zone.

            Parameters
            ----------
            user: ClientManager.Client
                User to add to the zone watcher set.

            Raises
            ------
            ZoneError.WatcherConflictError:
                If the user is already watching some other zone
            """

            self.add_watchers({user})

        def add_watchers(self, users: Set[ClientManager.Client]):
            """
            Add a set of users to the zone watcher set if ALL users were not watching some
            zone already.

            This also sets the watched zone of the users to the current zone.

            Parameters
            ----------
            users: set of ClientManager.Client
                Users to add to the zone watcher set.

            Raises
            ------
            ZoneError.WatcherConflictError:
                If any of the given users is already watching some other zone
            """

            self._add_watchers(users)
            self._check_structure()

        def _add_watchers(self, users: Set[ClientManager.Client]):
            for user in users:
                if user.zone_watched:
                    raise ZoneError.WatcherConflictError('Watcher {} is already watching zone {}.'
                                                         .format(user, user.zone_watched))

            for user in users:
                self._watchers.add(user)
                user.zone_watched = self

        def get_watchers(self) -> Set[ClientManager.Client]:
            """
            Return all of the zone's watchers.

            Returns
            -------
            set of ClientManager.Client
                Watchers of the zone
            """

            return self._watchers.copy()

        def is_watcher(self, user: ClientManager.Client) -> bool:
            """
            Return True if the iser is part of the zone's watcher list, False otherwise.

            Parameters
            ----------
            user : ClientManager.Client
                User to check.

            Returns
            -------
            bool
                True if the user is part of the zone's watcher list, False otherwise.
            """

            return user in self._watchers

        def remove_watcher(self, user: ClientManager.Client):
            """
            Remove a user from the zone watcher set if it was there.

            This also sets the watched zone of the client to None.

            Parameters
            ----------
            user: ClientManager.Client
                User to remove from the zone watcher set.

            Raises
            ------
            ZoneError.WatcherNotInZoneError:
                If the user is not part of the zone watcher set.
            """

            self._remove_watcher(user)
            self._check_structure()

        def _remove_watcher(self, user: ClientManager.Client):
            if user not in self._watchers:
                raise ZoneError.WatcherNotInZoneError('Watcher {} is not watching zone {}.'
                                                      .format(user, self))

            self._watchers.remove(user)
            self._cleanup_removed_watcher(user)

            # If no more watchers nor players, delete the zone
            if not self._watchers and not self._players:
                self._server.zone_manager.delete_zone(self._zone_id)
                user.send_ooc('(X) Zone `{}` that you were in was automatically deleted as no one '
                              'was in an area part of it or was watching it anymore.'
                              .format(self._zone_id), is_staff=True)
                user.send_ooc_others('Zone `{}` was automatically deleted as no one was in an '
                                     'area part of it or was watching it anymore.'
                                     .format(self._zone_id), is_officer=True)

        def _cleanup_removed_watcher(self, user: ClientManager.Client):
            user.zone_watched = None

        def add_player(self, user: ClientManager.Client):
            """
            Add a user to the zone's player list.

            Parameters
            ----------
            user : ClientManager.Client
                User to add.

            Raises
            ------
            ZoneError.PlayerConflictError
                If the user is already a player of the zone.
            ZoneError.PlayerNotInZoneError
                If the user is in an area not part of the zone.
            """

            self._add_player(user)
            self._check_structure()

        def _add_player(self, user: ClientManager.Client):
            if user in self._players:
                raise ZoneError.PlayerConflictError('User is already a player in the zone.')
            if user.area not in self._areas:
                raise ZoneError.PlayerNotInZoneError('User is in an area not part of the zone.')

            self._players.add(user)
            self.listener.subscribe(user)

            user.send_gamemode(name=self.get_mode())

            if self.is_property('Handicap'):
                length, name, announce_if_over = self.get_property('Handicap')
                user.change_handicap(True, length=length, name=name,
                                     announce_if_over=announce_if_over)

            if self.is_property('Chat_tick_rate'):
                chat_tick_rate = self.get_property('Chat_tick_rate')
                user.send_chat_tick_rate(chat_tick_rate=chat_tick_rate)

        def get_players(self) -> Set[ClientManager.Client]:
            """
            Return the set of players in an area part of the current zone.

            Returns
            -------
            Set[ClientManager.Client]
                Set of players in an area part of the current zone.
            """

            return self._players.copy()

        def is_player(self, user: ClientManager.Client) -> bool:
            """
            Return True if the user is part of the zone's player list, False otherwise.

            Parameters
            ----------
            user : ClientManager.Client
                User to check.

            Returns
            -------
            bool
                True if the user is part of the zone's player list, False otherwise.
            """

            return user in self._players

        def remove_player(self, user: ClientManager.Client):
            """
            Remove a user from the zone player set if it was there.

            Parameters
            ----------
            user: ClientManager.Client
                User to remove from the zone player set.

            Raises
            ------
            ZoneError.PlayerNotInZoneError:
                If the user is not part of the zone watcher set.
            """

            self._remove_player(user)
            self._check_structure()

        def _remove_player(self, user: ClientManager.Client):
            if user not in self._players:
                raise ZoneError.PlayerNotInZoneError('User {} is not a player of zone {}.'
                                                      .format(user, self))

            self._players.remove(user)
            self._cleanup_removed_player(user)

            # If no more watchers nor players, delete the zone
            if not self._watchers and not self._players:
                self._server.zone_manager.delete_zone(self._zone_id)
                user.send_ooc('(X) Zone `{}` that you were in was automatically deleted as no one '
                              'was in an area part of it or was watching it anymore.'
                              .format(self._zone_id), is_staff=True)
                user.send_ooc_others('Zone `{}` was automatically deleted as no one was in an '
                                     'area part of it or was watching it anymore.'
                                     .format(self._zone_id), is_officer=True)

        def _cleanup_removed_player(self, player: ClientManager.Client):
            self.listener.unsubscribe(player)
            # Restore their gamemode if needed (if player moved to a new zone, this zone will
            # be in charge of updating the gamemode)
            if not player.area.in_zone or player.area.in_zone == self:
                player.send_gamemode(name='')

            # Remove handicap
            if self.is_property('Handicap'):
                # Avoid double notification
                try:
                    player.change_handicap(False)
                except ClientError:
                    # If the player no longer had a handicap, no need to do anything
                    # This can happen if /unhandicap was run with a client in an area part of
                    # a zone with a handicap
                    pass

            # Remove chat tick rate
            if self.is_property('Chat_tick_rate'):
                player.send_chat_tick_rate(chat_tick_rate=None)

        def set_mode(self, new_mode: str):
            """
            Set the mode of the zone.

            Parameters
            ----------
            new_mode : str
                New mode.

            Returns
            -------
            None.

            """

            self._mode = new_mode

            for area in self.get_areas():
                for client in area.clients:
                    client.send_gamemode(name=new_mode)

        def get_mode(self) -> str:
            """
            Get the mode of the zone.

            Returns
            -------
            str
                Mode of the zone.

            """

            return self._mode

        def set_property(self, property_name: str, property_value: Any):
            """
            Set a property of the zone.

            Parameters
            ----------
            property_name : str
                Name of the property.
            property_value : Any
                Value of the property.
            """

            self._properties[property_name] = property_value

        def get_property(self, property_name: str) -> Any:
            """
            Return a previously set property of the zone.

            Parameters
            ----------
            property_name : str
                Property to fetch.

            Returns
            -------
            Any
                Stored value of the property.

            Raises
            ------
            ZoneError.PropertyNotFoundError
                If no such property was set for the zone.
            """

            try:
                return self._properties[property_name]
            except KeyError:
                raise ZoneError.PropertyNotFoundError(property_name)

        def is_property(self, property_name: str) -> bool:
            """
            Return whether `property_name` is a set property of the zone.

            Parameters
            ----------
            property_name : str
                Property to decide.

            Returns
            -------
            bool
                True if it is a set property, False otherwise.
            """

            return property_name in self._properties

        def remove_property(self, property_name: str) -> Any:
            """
            Remove a previously set property of the zone.

            Parameters
            ----------
            property_name : str
                Property to remove.

            Returns
            -------
            Any
                Previously stored value of the property.

            Raises
            ------
            ZoneError.PropertyNotFoundError
                If the property to remove is already not a property.
            """

            try:
                return self._properties.pop(property_name)
            except KeyError:
                raise ZoneError.PropertyNotFoundError(property_name)

        def get_info(self) -> str:
            """
            Obtain the zone details (ID, areas, watchers) as a human readable string.

            Returns
            -------
            str:
                Zone details in human readable format.
            """

            # Format areas
            area_description = Constants.format_area_ranges(self._areas)

            # Obtain watchers
            watchers = sorted(self._watchers)
            if watchers:
                watcher_infos = ['[{}] {} ({})'
                                .format(c.id, c.displayname, c.area.id) for c in watchers]
                watcher_description = Constants.cjoin(watcher_infos)
            else:
                watcher_description = 'None'

            # Obtain players
            player_description = len(self._players)

            return ('Zone {}. Contains areas: {}. Is watched by: {}. Players in zone: {}.'
                    .format(self._zone_id, area_description, watcher_description,
                            player_description))

        def delete(self):
            """
            Delete the current zone.

            If the zone is already deleted, do nothing.
            """

            # Implementation detail: Do this check now to prevent infinite recursion
            if self.is_deleted():
                return

            self._is_deleted = True
            self._server.zone_manager.delete_zone(self._zone_id)

            for area in self._areas:
                self._cleanup_removed_area(area)
            for player in self._players:
                self._cleanup_removed_player(player)
            for watcher in self._watchers:
                self._cleanup_removed_watcher(watcher)

            return

        def is_deleted(self) -> bool:
            """
            Returns whether the zone was previously deleted.

            Returns
            -------
            bool
                True if the zone was previously deleted, False otherwise.
            """

            return self._is_deleted

        def _on_area_client_left_final(self, area, client=None, old_displayname=None,
                                    ignore_bleeding=False):
            """
            Default callback for zone signaling a client left. This is executed after all other
            actions related to moving the player to a new area have been executed: in particular,
            client.area holds the new area of the client.

            By default it removes the player from the zone if their new area is not part of the
            zone.

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

            """

            if client in self.get_players() and client.area not in self._areas:
                self._remove_player(client)

            self._check_structure()

        def _on_area_client_entered_final(self, area, client=None, old_area=None,
                                          old_displayname=None, ignore_bleeding=False):
            """
            Default callback for zone signaling a client entered.

            By default adds a user to the zone's player list.

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

            if client not in self.get_players():
                self._add_player(client)

            self._check_structure()

        def _on_client_destroyed(self, player):
            """
            Default callback for zone player signaling it was destroyed, for example, as a result
            of a disconnection.

            By default it only removes the player from the zone. If the zone is already deleted or
            the player is not in the zone, this callback does nothing.

            Parameters
            ----------
            player : ClientManager.Client
                Player that signaled it was destroyed.

            Returns
            -------
            None.

            """

            if self.is_deleted():
                return
            if player not in self.get_players():
                return
            self._remove_player(player)

            self._check_structure()

        def _check_structure(self):
            self._server.zone_manager._check_structure()

        def __repr__(self) -> str:
            """
            Return a debugging expression for the zone.

            Returns
            -------
            str:
                Zone details in debugging format.
            """

            return 'Z::{}:{}:{}'.format(self._zone_id, self._areas, self._watchers)

    def __init__(self, server: TsuserverDR):
        """
        Create a zone manager object.

        Parameters
        ----------
        server: TsuserverDR
            The server this zone manager belongs to.
        """

        self._server = server
        self._zones = dict()
        self._zone_limit = 10000

    def new_zone(self, areas: Set[AreaManager.Area], watchers: Set[ClientManager.Client]) -> str:
        """
        Create a zone with the given area set and given watchers set and return its ID.

        Parameters
        ----------
        areas: set of AreaManager.Area
            Set of areas the zone covers.
        watchers: set of ClientManager.Client
            Set of clients who are watching the zone.

        Returns
        -------
        str
            The ID of the zone just created.

        Raises
        ------
        ZoneError.AreaConflictError:
            If one of the areas of the new zone already belongs to some other zone.
        ZoneError.WatcherConflictError:
            If one of the watchers of the new zone is already watching some other zone.
        """

        zone_id = self._generate_id()
        conflict_areas = self.areas_in_some_zone(areas)
        if conflict_areas:
            if len(conflict_areas) == 1:
                message = 'Area {} already belongs in a zone.'.format(conflict_areas.pop())
            else:
                message = ('Areas {} already belong in a zone.'
                           .format(Constants.cjoin([area.id for area in conflict_areas])))
            raise ZoneError.AreaConflictError(message)

        conflict_watchers = self.watchers_in_some_zone(watchers)
        if conflict_watchers:
            if len(conflict_watchers) == 1:
                message = 'Watcher {} is already watching a zone.'.format(conflict_watchers.pop())
            else:
                message = ('Watchers {} are already watching a zone.'
                           .format(Constants.cjoin(conflict_watchers)))
            raise ZoneError.WatcherConflictError(message)

        zone = self.Zone(self._server, zone_id, areas, watchers)
        self._zones[zone_id] = zone
        self._check_structure()
        return zone_id

    def get_zones(self) -> Set[ZoneManager.Zone]:
        """
        Return all of the zones this manager is handling.

        Returns
        -------
        set of ZoneManager.Zone:
            All of the zones handled by this manager.
        """

        return self._zones.copy()

    def delete_zone(self, zone_id: str):
        """
        Delete a zone by its ID.

        Parameters
        ----------
        zone_id: str
            ID of zone to remove.

        Raises
        ------
        KeyError:
            If the zone ID is invalid.
        """

        zone = self._zones[zone_id]
        # Avoid infinite recursive calls
        if zone.is_deleted():
            return
        zone.delete()
        self._zones.pop(zone_id)

        self._check_structure()

    def get_zone(self, zone_tag) -> ZoneManager.Zone:
        """
        Get the zone object associated with the given tag.

        Parameters
        ----------
        zone_tag: ZoneManager.Zone OR string
            Zone object to return, or the ID of a zone.

        Returns
        -------
        ZoneManager.Zone:
            The given zone if zone_tag is a zone, or the zone whose ID matches zone_tag otherwise.

        Raises
        ------
        KeyError:
            If zone_tag is not a zone or zone identifier.
        """

        if isinstance(zone_tag, self.Zone):
            return zone_tag
        if isinstance(zone_tag, str):
            if zone_tag not in self._zones.keys():
                raise KeyError('{} is not a valid zone ID.'.format(zone_tag))
            return self._zones[zone_tag]
        raise KeyError('{} is not a valid zone tag.'.format(zone_tag))

    def get_zone_id(self, zone_tag) -> str:
        """
        Get the zone object associated with the given tag.

        Parameters
        ----------
        zone_tag: ZoneManager.Zone OR string
            Zone object whose ID is to be returned, or the ID of a zone.

        Returns
        -------
        ZoneManager.Zone:
            The given zone ID if zone_tag is a string, or the zone that matches zone_tag otherwise.

        Raises
        ------
        KeyError:
            If zone_tag is not a zone or zone identifier.
        """

        if isinstance(zone_tag, str):
            return zone_tag
        if isinstance(zone_tag, self.Zone):
            if zone_tag not in self._zones.values():
                raise KeyError('{} is not a zone in this server.'.format(zone_tag))
            return zone_tag.zone_id
        raise KeyError('{} is not a valid zone tag.'.format(zone_tag))

    def get_info(self) -> str:
        """
        List all zones in the server, as well as some of their properties.
        If there are no zones, return a special message instead.

        Returns
        -------
        str:
            All zones in the server.
        """

        if not self._zones:
            return 'There are no zones in this server.'

        message = '== Active zones =='
        for zone in self._zones.values():
            message += '\r\n*{}'.format(zone.get_info())
        return message

    def areas_in_some_zone(self, areas: Set[AreaManager.Area]) -> Set[AreaManager.Area]:
        """
        Return all of the areas among the given areas that are in a zone.

        Parameters
        ----------
        areas: set of AreaManager.Area
            Areas to check if they belong in a zone.

        Returns
        -------
        set of AreaManager.Area
            All the areas among the given areas that are in a zone.
        """

        return {area for area in areas if area.in_zone}

    def watchers_in_some_zone(self,
                              watchers: Set[ClientManager.Client]) -> Set[ClientManager.Client]:
        """
        Return all of the watchers among the given watchers that are watching a zone.

        Parameters
        ----------
        watchers: set of ClientManager.Client
            Watchers to check if they are watching a zone.

        Returns
        -------
        set of ClientManager.Client
            All the watchers among the given watchers that are watching a zone.
        """

        return {watcher for watcher in watchers if watcher.zone_watched}

    def _generate_id(self) -> str:
        """
        Helper method to generate a new zone ID based on the lowest available zone number.

        Returns
        -------
        str
            ID for the new zone.

        Raises
        ------
        ValueError:
            If there are no available names for the zone (server reached self._zone_limit zones).
        """

        for zone_number in range(self._zone_limit):
            new_zone_id = "z{}".format(zone_number)
            if new_zone_id not in self._zones:
                return new_zone_id

        raise ValueError('Server reached its zone limit.')

    def _check_structure(self):
        """
        Assert the following invariants:
            The server cap on zone number is enforced.
            For each each key in the manager'z zone set of keys:
                The key is associated to a zone whose ID matches the key.
            For each zone in the manager's zone set of values:
                No two zones have an area that belongs to their own area sets.
                Each area recognizes it being part of that zone.
                No two zones have a client that is watching them both.
                Each client properly recognizes it is watching that specific zone.
            For each area not in a zone, that it recognizes it is not part of a zone.
            For each client not watching a zone, that it recognizes it is not watching any zone.
        """

        areas_so_far = set()
        watchers_so_far = set()

        # 1.
        assert len(self._zones.keys()) < self._zone_limit, (
            'Expected the server cap of {} to be enforced, found the server linked to '
            '{} zones instead.'.format(self._zone_limit, len(self._zones.keys())))

        # 2.
        for zone_id, zone in self._zones.items():
            assert zone._zone_id == zone_id, (
                'Expected zone {} associated with ID {} to have the same ID, found it had ID '
                '{} instead.'.format(zone, zone_id, zone._zone_id))

        for zone in self._zones.values():
            # 3.
            conflicting_areas = [area for area in zone._areas if area in areas_so_far]
            assert not conflicting_areas, (
                'Expected no conflicting areas, but zone {} introduces repeated areas {}.'
                .format(zone, conflicting_areas))

            # 4.
            for area in zone._areas:
                assert area.in_zone == zone, (
                    'Expected area {} to recognize it being a part of zone {}, found it '
                    'recognized {} instead.'.format(area, zone, area.in_zone))
                areas_so_far.add(area)

            # 5.
            conflicting_watchers = [watch for watch in zone._watchers if watch in watchers_so_far]
            assert not conflicting_watchers, (
                'Expected no conflicting watchers, but zone {} introduces conflicting watchers '
                '{}.'.format(zone, conflicting_watchers))

            # 6.
            for watcher in zone._watchers:
                assert watcher.zone_watched == zone, (
                    'Expected watcher {} to recognize it is watching zone {}, found it '
                    'recognized {} instead.'.format(watcher, zone, watcher.zone_watched))
                watchers_so_far.add(watcher)

        # 7.
        for area in self._server.area_manager.areas:
            if area in areas_so_far:
                continue
            assert area.in_zone is None, (
                'Expected area {} not part of a zone to recognize it not being in a zone, '
                'found it recognized {} instead.'.format(area, area.in_zone))

        # 8.
        for watcher in self._server.get_clients():
            if watcher in watchers_so_far:
                continue
            assert watcher.zone_watched is None, (
                'Expected watcher {} to recognize that it is not watching a zone, found it '
                'recognized it watched {} instead.'.format(watcher, watcher.zone_watched))
