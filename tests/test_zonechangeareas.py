from .test_zonebasic import _TestZone

class TestZoneChangeArea_01_Add(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_add incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_add 16')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_add')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Multiple areas
        self.c1.ooc('/zone_add 1, 4')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_addonearea(self):
        """
        Situation: After creating a zone themselves, C1 adds another area.
        """

        self.c1.ooc('/zone 4, 6')
        self.c1.discard_all()
        self.assert_zones({'z0': {4, 5, 6}})

        self.c1.ooc('/zone_add 7')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have added area {} to your zone.'.format(7), over=True)
        self.c2.assert_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format('z0', 'z0'), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format('z0', 'z0'), over=True)
        self.assert_zones({'z0': {4, 5, 6, 7}})

    def test_03_adddisjointarea(self):
        """
        Situation: C1 adds an area that is disjoint from an existing area range in the zone.
        """

        self.c1.ooc('/zone_add 0')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have added area {} to your zone.'.format(0), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {0, 4, 5, 6, 7}})

    def test_04_nonwatcherscannotadd(self):
        """
        Situation: C5, who is not a watcher of zone z0, attempts to add an area... somewhere. This
        fails.
        """

        self.c5.ooc('/zone_add 1')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are not watching a zone.', over=True)

    def test_05_newwatcherscanadd(self):
        """
        Situation: C5 now watches z0 and adds an area. This now works and C1 is notified of it.
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c5.discard_all()

        self.c5.ooc('/zone_add 1')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has added area {} to your zone.'
                           .format(self.c5.displayname, 5, 1), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You have added area {} to your zone.'.format(1), over=True)
        self.assert_zones({'z0': {0, 1, 4, 5, 6, 7}})

    def test_06_addofanoterdoesnotmutate(self):
        """
        Situation: C2 creates a new zone and adds another area to it. z0's areas remain the same.
        """

        self.c2.ooc('/zone 2')
        self.c1.discard_all() # Discard mod notification for zone creation
        self.c2.discard_all()
        self.assert_zones({'z0': {0, 1, 4, 5, 6, 7}, 'z1': {2}})

        self.c2.ooc('/zone_add 3')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You have added area {} to your zone.'.format(3), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {0, 1, 4, 5, 6, 7}, 'z1': {2, 3}})

    def test_07_cannotaddareatosecondzone(self):
        """
        Situation: C2 attempts to add an area already in some other zone (z0). This fails.
        """

        self.c2.ooc('/zone_add 4')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Area {} already belongs to a zone.'.format(4), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {0, 1, 4, 5, 6, 7}, 'z1': {2, 3}})

class TestZoneChangeArea_02_Remove(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_remove incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_remove 16')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_remove')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_removearea(self):
        """
        Situation: C1 creates a zone with areas 4-7. They, then remove area 5 from the zone.
        """

        self.c1.ooc('/zone 4, 7')
        self.c1.discard_all()
        self.c2.discard_all() # c2 receives being in zone at zone creation notif
        self.c5.discard_all() # same as above
        self.assert_zones({'z0': {4, 5, 6, 7}})

        self.c1.ooc('/zone_remove 5')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed area {} from your zone.'.format(5), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4, 6, 7}})

    def test_03_noareasremoveszone(self):
        """
        Situation: C1 slowly removes all areas from their zone. After they remove the last one,
        the zone is automatically disposed of. This is notified to all watchers of the now defunct
        zone (including C5, who tagged along).
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c5.discard_all()

        self.c1.ooc('/zone_remove 4')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed area {} from your zone.'.format(4), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has removed area {} from your zone.'
                           .format(self.c1.displayname, 1, 4), over=True)
        self.assert_zones({'z0': {6, 7}})

        self.c1.ooc('/zone_remove 6')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed area {} from your zone.'.format(6), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has removed area {} from your zone.'
                           .format(self.c1.displayname, 1, 6), over=True)
        self.assert_zones({'z0': {7}})

        self.c1.ooc('/zone_remove 7')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed area {} from your zone.'.format(7))
        self.c1.assert_ooc('(X) As your zone no longer covers any areas, it has been deleted.',
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has removed area {} from your zone.'
                           .format(self.c1.displayname, 1, 7))
        self.c5.assert_ooc('(X) As your zone no longer covers any areas, it has been deleted.',
                           over=True)
        self.assert_zones(dict())

    def test_04_nonwatcherscannotremove(self):
        """
        Situation: C1 recreates zone z0. C5, who is not a watcher of zone z0, attempts to remove
        an area... somewhere. This fails.
        """

        self.c1.ooc('/zone 4, 7')
        self.c1.discard_all()
        self.c2.discard_all() # c2 receives being in zone at zone creation notif
        self.c5.discard_all() # same as above

        self.c5.ooc('/zone_remove 6')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You are not watching a zone.', over=True)

    def test_05_newwatcherscanremove(self):
        """
        Situation: C5 now watches z0 and removes an area. This now works and C1 is notified of it.
        """

        self.c5.ooc('/zone_watch z0')
        self.c1.discard_all()
        self.c5.discard_all()

        self.c5.ooc('/zone_remove 7')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has removed area {} from your zone.'
                           .format(self.c5.displayname, 5, 7), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You have removed area {} from your zone.'.format(7), over=True)
        self.assert_zones({'z0': {4, 5, 6}})

    def test_06_removeofanoterdoesnotmutate(self):
        """
        Situation: C2 creates a new zone and removes an area from it. z0's areas remain the same.
        """

        self.c2.ooc('/zone 2, 3')
        self.c1.discard_all() # Discard mod notification for zone creation
        self.c2.discard_all()
        self.assert_zones({'z0': {4, 5, 6}, 'z1': {2, 3}})

        self.c2.ooc('/zone_remove 3')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You have removed area {} from your zone.'.format(3), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4, 5, 6}, 'z1': {2}})

    def test_07_cannotremovewhatisnotthere(self):
        """
        Situation: C2 attempts to remove an area not part of their zone. This fails
        """

        self.c2.ooc('/zone_remove 4')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Area {} is not part of your zone.'.format(4), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4, 5, 6}, 'z1': {2}})
