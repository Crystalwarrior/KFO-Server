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
        def __init__(self, zone_ID, areas, watchers):
            """
            Initialization method for a zone.

            Parameters
            ----------
            zone_ID: string
                Identifier of zone.
            areas: set of AreaManager.Area
                Set of areas the zone covers.
            watchers: set of ClientManager.Client
                Set of clients who are watching the zone.
            """

            raise NotImplementedError

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
            KeyError:
                If the area is already a part of some zone area set, possibly not this one.
            """

            raise NotImplementedError

        def add_areas(self, areas):
            """
            Add a set of areas to the zone area set if ALL areas were not part of a zone already.

            This also sets the zone of the given areas to the current zone.

            Parameters
            ----------
            areas: set of AreaManager.Area
                Areas to add to the zone area set.

            Raises
            ------
            KeyError:
                If any of the given areas is already a part of some zone area set.
            """

            raise NotImplementedError

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

        def add_watcher(self, client):
            """
            Add a client to the zone watcher set if it was not there already.

            This also sets the watched zone of the client to the current zone.

            Parameters
            ----------
            client: ClientManager.Client
                Client to add to the zone watcher set.

            Raises
            ------
            KeyError:
                If the client is already watching some zone, possibly not this one.
            """

            raise NotImplementedError

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

    def __init__(self, server):
        """
        Create a zone manager object.

        Parameters
        ----------
        server: server.TsuserverDR
            The server this zone manager belongs to.
        """

        raise NotImplementedError

    def new_zone(self, areas, watchers):
        """
        Create a zone with the given area set and given watchers set.

        Parameters
        ----------
        areas: set of AreaManager.Area
            Set of areas the zone covers.
        watchers: set of ClientManager.Client
            Set of clients who are watching the zone.

        Raises
        ------
        ZoneError:
            If the server reached its maximum number of zones allowed.
        """

        raise NotImplementedError

    def remove_zone(self, zone_id):
        """
        Remove a zone by its ID.

        Parameters
        ----------
        zone_id: string
            ID of zone to remove.

        Raises
        ------
        ZoneError:
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
        ZoneError:
            If zone_tag is not a zone or zone identifier.
        """

        raise NotImplementedError

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
        ZoneError:
            If zone_tag is not a zone or zone identifier.
        """

        raise NotImplementedError

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
