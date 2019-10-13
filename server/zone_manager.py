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

from server.exceptions import AreaError, ClientError, ZoneError

class ZoneManager:
    """
    Create a new manager for the zones in a server.
    Contains the Zone object definition, as well as the server's zone list.
    """

    class Zone:
        def __init__(self, server, zone_id, areas, watchers):
            """
            Initialization method for a zone.

            Parameters
            ----------
            server: tsuserver.TsuserverDR
                Server the zone belongs to
            zone_id: string
                Identifier of zone.
            areas: set of AreaManager.Area
                Set of areas the zone covers.
            watchers: set of ClientManager.Client
                Set of clients who are watching the zone.
            """

            self.server = server
            self.zone_id = zone_id
            self.areas = set()
            self.watchers = set()

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

            Raises
            ------
            ValueError:
                If the area is already a part of some zone area set, possibly not this one.
            """

            raise NotImplementedError

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
            ValueError:
                If any of the given areas is already a part of some zone area set.
            """

            for area in areas:
                if area in self.areas:
                    raise ValueError('Area {} is already part of zone {}.'.format(area, self))
                if area.in_zone:
                    raise ValueError('Area {} is already part of zone {}.'
                                     .format(area, area.in_zone))

            for area in areas:
                self.areas.add(area)
                area.in_zone = self

            if check_structure:
                self.server.zone_manager._check_structure()

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

            raise NotImplementedError

        def add_watcher(self, watcher):
            """
            Add a watcher to the zone watcher set if it was not there already.

            This also sets the watched zone of the watcher to the current zone.

            Parameters
            ----------
            watcher: ClientManager.Client
                Client to add to the zone watcher set.

            Raises
            ------
            ValueError:
                If the watcher is already watching some zone, possibly not this one.
            """

            raise NotImplementedError

        def add_watchers(self, watchers, check_structure=True):
            """
            Add a set of watchers to the zone watcher set if ALL watchers were not watching some
            zone already.

            This also sets the watched zone of the watchers to the current zone.

            Parameters
            ----------
            watcher: set of ClientManager.Client
                Clients to add to the zone watcher set.
            check_structure: boolean, optional
                If set to False, the manager will skip the structural integrity test.

            Raises
            ------
            ValueError:
                If any of the given watchers is already watching some other zone
            """

            for watcher in watchers:
                if watcher in self.watchers:
                    raise ValueError('Watcher {} is already watching zone {}.'.format(watcher, self))
                if watcher.zone_watched:
                    raise ValueError('Watcher {} is already watching zone {}.'
                                    .format(watcher, watcher.zone_watched))

            for watcher in watchers:
                self.watchers.add(watcher)
                watcher.zone_watched = self

            if check_structure:
                self.server.zone_manager._check_structure()

        def remove_watcher(self, client):
            """
            Remove a client from the zone watcher set if it was there.

            This also sets the watched zone of the client to None.

            Parameters
            ----------
            client: ClientManager.Client
                Client to remove from the zone watcher set.

            Raises
            ------
            KeyError:
                If the client is not part of the zone watcher set.
            """

            raise NotImplementedError

        def __repr__(self):
            return 'Z::{}:{}:{}'.format(self.zone_id, self.areas, self.watchers)

    def __init__(self, server):
        """
        Create a zone manager object.

        Parameters
        ----------
        server: server.TsuserverDR
            The server this zone manager belongs to.
        """

        self.server = server
        self.zones = dict()
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
        """

        zone_id = self._generate_id()
        zone = self.Zone(self.server, zone_id, areas, watchers)
        self.zones[zone_id] = zone
        self._check_structure()
        return zone_id

    def remove_zone(self, zone_id):
        """
        Remove a zone by its ID.

        Parameters
        ----------
        zone_id: string
            ID of zone to remove.

        Raises
        ------
        KeyError:
            If the zone ID is invalid.
        """

        raise NotImplementedError

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
            if zone_tag not in self.zones.keys():
                raise KeyError('{} is not a valid zone ID.'.format(zone_tag))
            return self.zones[zone_tag]
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
            if zone_tag not in self.zones.values():
                raise KeyError('{} is not a zone in this server.'.format(zone_tag))
            return zone_tag.zone_id
        raise KeyError('{} is not a valid zone tag.'.format(zone_tag))

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

        raise NotImplementedError

    def _generate_id(self):
        """
        Helper method to generate a new zone ID.

        Returns
        -------
        str
            ID for the new zone

        Raises
        ------
        ValueError:
            If there are no available names for the zone (server reached self._zone_limit zones)
        """

        size = len(self.zones.keys())
        if size == self._zone_limit:
            raise ValueError('Server reached its zone limit.')

        return "z{}".format(size)

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
        assert len(self.zones.keys()) < self._zone_limit, (
                'Expected the server cap of {} to be enforced, found the server linked to '
                '{} zones instead.'.format(self._zone_limit, len(self.zones.keys())))

        # 2.
        for zone_id, zone in self.zones.items():
            assert zone.zone_id == zone_id, (
                    'Expected zone {} associated with ID {} to have the same ID, found it had ID '
                    '{} instead.'.format(zone, zone_id, zone.zone_id))

        for zone in self.zones.values():
            # 3.
            conflicting_areas = [area for area in zone.areas if area in areas_so_far]
            assert not conflicting_areas, (
                    'Expected no conflicting areas, but zone {} introduces repeated areas {}.'
                    .format(zone, conflicting_areas))

            # 4.
            for area in zone.areas:
                assert area.in_zone == zone, (
                        'Expected area {} to recognize it being a part of zone {}, found it '
                        'recognized {} instead.'.format(area, zone, area.in_zone))
                areas_so_far.add(area)

            # 5.
            conflicting_watchers = [watch for watch in zone.watchers if watch in watchers_so_far]
            assert not conflicting_watchers, (
                    'Expected no conflicting watchers, but zone {} introduces conflicting watchers '
                    '{}.'.format(zone, conflicting_watchers))

            # 6.
            for watcher in zone.watchers:
                assert watcher.zone_watched == zone, (
                        'Expected watcher {} to recognize it is watching zone {}, found it '
                        'recognized {} instead.'.format(watcher, zone, watcher.zone_watched))
                watchers_so_far.add(watcher)

        # 7.
        for area in self.server.area_manager.areas:
            if area in areas_so_far:
                continue
            assert area.in_zone is None, (
                    'Expected area {} not part of a zone to recognize it not being in a zone, '
                    'found it recognized {} instead'.format(area, area.in_zone))

        # 8.
        for watcher in self.server.client_manager.clients:
            if watcher in watchers_so_far:
                continue
            assert watcher.zone_watched is None, (
                    'Expected watcher {} to recognize that it is not watching a zone, found it '
                    'recognized it watched {} instead.'.format(watcher, watcher.zone_watched))