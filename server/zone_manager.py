# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
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

from server.constants import Constants
from server.exceptions import ZoneError

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

        def __init__(self, server, zone_id, areas, watchers):
            """
            Initialization method for a zone.

            Parameters
            ----------
            server: TsuserverDR
                Server the zone belongs to
            zone_id: string
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

            self.add_areas(areas, check_structure=False)
            self.add_watchers(watchers, check_structure=False)

        def add_area(self, area):
            """
            Add an area to the zone area set if it was not there already.

            This also sets the zone of the given area to the current zone.

            Parameters
            ----------
            area: AreaManager.Area
                Area to add to the zone area set.
            """

            self.add_areas({area})

        def add_areas(self, areas, check_structure=True):
            """
            Add a set of areas to the zone area set if ALL areas were not part of a zone already.

            This also sets the zone of the given areas to the current zone.

            Parameters
            ----------
            areas: set of AreaManager.Area
                Areas to add to the zone area set.
            check_structure: boolean, optional
                If set to False, the manager will skip the structural integrity test.

            Raises
            ------
            ZoneError.AreaConflictError:
                If any of the given areas is already a part of some zone area set.
            """

            for area in areas:
                if area.in_zone:
                    raise ZoneError.AreaConflictError('Area {} is already part of zone {}.'
                                                      .format(area, area.in_zone))

            for area in areas:
                self._areas.add(area)
                area.in_zone = self

            if check_structure:
                self._server.zone_manager._check_structure()

        def get_areas(self):
            """
            Return all of the zone's areas.

            Returns
            -------
            set of AreaManager.Area:
                All of the areas part of the zone.
            """

            return self._areas.copy()

        def remove_area(self, area):
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

            if area not in self._areas:
                raise ZoneError.AreaNotInZoneError('Area {} is not part of zone {}.'
                                                   .format(area, self))

            self._areas.remove(area)
            area.in_zone = None

            # If no more areas, delete the zone
            if not self._areas:
                self._server.zone_manager.delete_zone(self._zone_id)
            self._server.zone_manager._check_structure()

        def get_id(self):
            """
            Return the zone ID.

            Returns
            -------
            str:
                The ID of the zone.
            """

            return self._zone_id

        def add_watcher(self, watcher):
            """
            Add a watcher to the zone watcher set if it was not there already.

            This also sets the watched zone of the watcher to the current zone.

            Parameters
            ----------
            watcher: ClientManager.Client
                Client to add to the zone watcher set.
            """

            self.add_watchers({watcher})

        def add_watchers(self, watchers, check_structure=True):
            """
            Add a set of watchers to the zone watcher set if ALL watchers were not watching some
            zone already.

            This also sets the watched zone of the watchers to the current zone.

            Parameters
            ----------
            watcher: set of ClientManager.Client
                Watchers to add to the zone watcher set.
            check_structure: boolean, optional
                If set to False, the manager will skip the structural integrity test.

            Raises
            ------
            ZoneError.WatcherConflictError:
                If any of the given watchers is already watching some other zone
            """

            for watcher in watchers:
                if watcher.zone_watched:
                    raise ZoneError.WatcherConflictError('Watcher {} is already watching zone {}.'
                                                         .format(watcher, watcher.zone_watched))

            for watcher in watchers:
                self._watchers.add(watcher)
                watcher.zone_watched = self

            if check_structure:
                self._server.zone_manager._check_structure()

        def get_watchers(self):
            """
            Return all of the zone's watchers.

            Returns
            -------
            set of ClientManager.Client
                Watchers of the zone
            """

            return self._watchers.copy()

        def remove_watcher(self, watcher):
            """
            Remove a client from the zone watcher set if it was there.

            This also sets the watched zone of the client to None.

            Parameters
            ----------
            watcher: ClientManager.Client
                Watcher to remove from the zone watcher set.

            Raises
            ------
            ZoneError.WatcherNotInZoneError:
                If the watcher is not part of the zone watcher set.
            """

            if watcher not in self._watchers:
                raise ZoneError.WatcherNotInZoneError('Watcher {} is not watching zone {}.'
                                                      .format(watcher, self))

            self._watchers.remove(watcher)
            watcher.zone_watched = None

            # If no more watchers, delete the zone
            if not self._watchers:
                self._server.zone_manager.delete_zone(self._zone_id)
            self._server.zone_manager._check_structure()

        def get_info(self):
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
            watchers = sorted(self._watchers, key=lambda c: c.id)
            watcher_infos = ['[{}] {} ({})'
                             .format(c.id, c.displayname, c.area.id) for c in watchers]
            watcher_description = Constants.cjoin(watcher_infos)

            return ('Zone {}. Contains areas: {}. Is watched by: {}.'
                    .format(self._zone_id, area_description, watcher_description))

        def __repr__(self):
            """
            Return a debugging expression for the zone.

            Returns
            -------
            str:
                Zone details in debugging format.
            """

            return 'Z::{}:{}:{}'.format(self._zone_id, self._areas, self._watchers)

    def __init__(self, server):
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

    def new_zone(self, areas, watchers):
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

    def get_zones(self):
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

        zone = self._zones.pop(zone_id)
        for area in zone._areas:
            area.in_zone = None
        for watcher in zone._watchers:
            watcher.zone_watched = None

        self._check_structure()

    def get_zone(self, zone_tag):
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

    def get_zone_id(self, zone_tag):
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

    def get_info(self):
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

    def areas_in_some_zone(self, areas):
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

    def watchers_in_some_zone(self, watchers):
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
        for watcher in self._server.client_manager.clients:
            if watcher in watchers_so_far:
                continue
            assert watcher.zone_watched is None, (
                'Expected watcher {} to recognize that it is not watching a zone, found it '
                'recognized it watched {} instead.'.format(watcher, watcher.zone_watched))
