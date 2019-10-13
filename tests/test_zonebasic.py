from .structures import _TestSituation6Mc1Gc25

class _TestZone(_TestSituation6Mc1Gc25):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c0.move_area(4)
        cls.c1.move_area(4)
        cls.c2.move_area(5)
        cls.c3.move_area(5)
        cls.c4.move_area(6)
        cls.c5.move_area(7)
        cls.zm = cls.server.zone_manager

    def assert_zones(self, expected_zones):
        """
        Assert that the set of zone IDs matches exactly to the server's zone manager's zones
        """

        self.assertEqual(len(expected_zones), len(self.zm.get_zones()))
        for (expected_zone_id, expected_zone_areas) in expected_zones.items():
            self.assertTrue(expected_zone_id in self.zm.get_zones().keys())

            actual_zone = self.zm.get_zone(expected_zone_id)
            self.assertEquals(expected_zone_id, actual_zone.get_id())

            actual_zone_areas = {area.id for area in actual_zone.get_areas()}
            self.assertEquals(expected_zone_areas, actual_zone_areas)

class TestZoneBasic_01_Zone(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # Invalid name
        self.c1.ooc('/zone Notanareaname')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Could not parse area `Notanareaname`.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # Non-existant area
        self.c2.ooc('/zone 100') # No area called 100, or with ID 100 in test scenario
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Could not parse area `100`.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        self.c2.ooc('/zone {}, 101'.format(self.a0_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Could not parse area `101`.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # Not using commas to separate
        self.c2.ooc('/zone {} {}'.format(2, 5))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Could not parse area `2 5`.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # Not using ,\ for areas with , in their names (self.a2_name = "Class Trial Room,\ 2")
        self.c2.ooc('/zone {}, {}'.format(self.a2_name, self.a7_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Expected at most two area names.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        self.c2.ooc('/zone {}'.format(self.a2_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Could not parse area `Class Trial Room`.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # End area < Start area
        self.c2.ooc('/zone {}, {}'.format(5, 2))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('The ID of the first area must be lower than the ID of the second area.',
                           over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

        # Range has too many areas
        self.c2.ooc('/zone {}, {}, {}'.format(1, 3, 7))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Expected at most two area names.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones(dict())

    def test_02_noargument(self):
        """
        Situation: C1 creates a zone for their own area.
        """

        self.c1.ooc('/zone')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have created zone `{}` containing just area {}.'
                           .format('z0', 4), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4}})

    def test_03_oneargument(self):
        """
        Situation: C2 creates a zone for another area
        """

        self.c2.ooc('/zone {}'.format(self.a3_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You have created zone `{}` containing just area {}.'
                           .format('z1', 3), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4}, 'z1': {3}})

    def test_04_twoarguments(self):
        """
        Situation: C5 creates a zone for an area range
        """

        self.c5.ooc('/zone {}, {}'.format(self.a5_name, self.a7_name))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You have created zone `{}` containing areas {} through {}.'
                           .format('z2', 5, 7), over=True)
        self.assert_zones({'z0': {4}, 'z1': {3}, 'z2': {5, 6, 7}})

    def test_05_notwozonesforwatcher(self):
        """
        Situation: C5 attempts to create a zone for another area range while still watching their
        old zone. This fails.
        """

        self.c5.ooc('/zone {}'.format(0))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You cannot create a zone while watching another.', over=True)
        self.assert_zones({'z0': {4}, 'z1': {3}, 'z2': {5, 6, 7}})

    def test_06_nooverlappingzones(self):
        """
        Situation: C3 (who is made mod for this test case), attempts to create a zone that would
        conflict with an existing zone (z1). This fails.
        """

        self.c3.make_mod()

        self.c3.ooc('/zone {}, {}'.format(self.a1_name, self.a3_name)) # Area 3 is in z1, bad
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_ooc('Some of the areas of your new zone are already part of some other '
                           'zone.', over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZoneBasic_02_Global(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_global incorrectly.
        """

        # No message
        self.c0.ooc('/zone_global')
        self.c0.assert_ooc('You cannot send an empty message.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_99_alias(self):
        """
        Situation: Clients attempt to use /zg, the alias of /zone_global.
        """

        pass

class TestZoneBasic_03_List(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_list incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_list')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Parameters
        self.c1.ooc('/zone_list abc')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_nozones(self):
        """
        Situation: C1 gets the zone list when there are no zones.
        """

        self.c1.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('There are no zones in this server.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_03_onezonetrivialrange(self):
        """
        Situation: C2 creates a zone that has just one area. C1 gets the zone list.
        """

        self.c2.ooc('/zone 1')
        self.c2.discard_all()

        self.c1.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1', '{} ({})'.format(self.c2_dname, self.c2.area.id)),
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_04_twozonesnontrivialrange(self):
        """
        Situation: C5 creates a zone that has more than one area. C1 gets the zone list.
        """

        self.c5.ooc('/zone 2, 4')
        self.c5.discard_all()

        self.c1.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1', '{} ({})'.format(self.c2_dname, self.c2.area.id),
                                   'z1', '2-4', '{} ({})'.format(self.c5_dname, self.c5.area.id)),
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_05_threezonesdisjointrange(self):
        """
        Situation: C4 (who is made mod) creates a zone with a disjoint range. C1 gets the zone list.
        """

        pass


