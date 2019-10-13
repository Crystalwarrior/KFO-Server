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

    def test_02_noargument(self):
        """
        Situation: After creating an area themselves, C1 adds another area
        """
        return

        self.c1.ooc('/zone 4, 6')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have created zone {} containing just area {}.'
                           .format('z0', 4), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4}})

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