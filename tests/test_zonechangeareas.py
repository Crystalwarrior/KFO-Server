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
        Situation: After creating a zone themselves, C1 adds another area
        """

        self.c1.ooc('/zone 4, 6')
        self.c1.discard_all()
        self.assert_zones({'z0': {4, 5, 6}})

        self.c1.ooc('/zone_add 7')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have added area {} to your zone.'.format(7), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
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
        self.c1.assert_ooc('(X) {} has added area {} to your zone.'.format(self.c5.name, 1),
                           over=True)
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

class TestZoneChangeArea_03_Delete(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_delete incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_delete 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()