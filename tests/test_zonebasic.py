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

        # Prevent multiclienting warning in tests
        cls.c0.hdid = '0'
        cls.c1.hdid = '1'
        cls.c2.hdid = '2'
        cls.c3.hdid = '3'
        cls.c4.hdid = '4'
        cls.c5.hdid = '5'

        cls.c0.ipid = 0
        cls.c1.ipid = 1
        cls.c2.ipid = 2
        cls.c3.ipid = 3
        cls.c4.ipid = 4
        cls.c5.ipid = 5

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

        self.zm._check_structure() # Remove later

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
        self.c2.assert_no_packets() # GM does not receive zone creation notification
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4}})

    def test_03_oneargument(self):
        """
        Situation: C2 creates a zone for another area. C1 as mod gets notification.
        """

        self.c2.ooc('/zone {}'.format(self.a3_name))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has created zone `{}` containing just area {} ({}).'
                           .format(self.c2_dname, 2, 'z1', 3, self.c2.area.id), over=True)
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
        self.c1.assert_ooc('(X) {} [{}] has created zone `{}` containing areas {} through {} ({}).'
                           .format(self.c5_dname, 5, 'z2', 5, 7, self.c5.area.id), over=True)
        self.c2.assert_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format('z2', 'z2'), over=True)
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
        conflict with an existing zone (z2). This fails.
        """

        self.c3.make_mod(over=False)
        self.c3.assert_ooc('(X) You are in an area part of zone `{}`. To be able to receive its '
                           'notifications, start watching it with /zone_watch {}'
                           .format('z2', 'z2'), over=True)

        self.c3.ooc('/zone {}, {}'.format(self.a1_name, self.a3_name)) # Area 5 is in z2, bad
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_ooc('Some of the areas of your new zone are already part of some other '
                           'zone.', over=True)
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
        self.assert_zones({'z0': {4}, 'z1': {3}, 'z2': {5, 6, 7}})

class TestZoneBasic_02_List(_TestZone):
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
        self.c1.discard_all() # Discard mod notification
        self.c2.discard_all()

        self.c1.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1', '[{}] {} ({})'
                                   .format(2, self.c2_dname, self.c2.area.id)),
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_04_twozonesnontrivialrange(self):
        """
        Situation: C5 creates a zone that has more than one area. C1 gets the zone list.
        """

        self.c5.ooc('/zone 2, 4')
        self.c1.discard_all() # Discard mod notification
        self.c5.discard_all()

        self.c1.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1',
                                   '[{}] {} ({})'.format(2, self.c2_dname, self.c2.area.id),
                                   'z1', '2-4',
                                   '[{}] {} ({})'.format(5, self.c5_dname, self.c5.area.id)),
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_05_threezonesdisjointrange(self):
        """
        Situation: C4 (who is made mod) creates a zone with a disjoint range. C1 gets the zone list.
        """

        self.c4.make_mod()
        self.c4.ooc('/zone 0')
        self.c4.ooc('/zone_add 5')
        self.c1.discard_all() # Discard mod notification
        self.c2.discard_all() # Discard logged in while area added to zone notif
        self.c4.discard_all()

        self.c4.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1',
                                   '[{}] {} ({})'.format(2, self.c2_dname, self.c2.area.id),
                                   'z1', '2-4',
                                   '[{}] {} ({})'.format(5, self.c5_dname, self.c5.area.id),
                                   'z2', '0 and 5',
                                   '[{}] {} ({})'.format(4, self.c4_dname, self.c4.area.id)),
                           over=True)
        self.c5.assert_no_packets()

    def test_06_moredisjointness(self):
        """
        Situation: C4 adds another area disjoint to both areas in their previously disjoint zone.
        """

        self.c4.ooc('/zone_add 7')
        self.c4.discard_all()
        self.c5.discard_all() # Discard logged in while area added to zone notif

        self.c4.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1',
                                   '[{}] {} ({})'.format(2, self.c2_dname, self.c2.area.id),
                                   'z1', '2-4',
                                   '[{}] {} ({})'.format(5, self.c5_dname, self.c5.area.id),
                                   'z2', '0, 5 and 7',
                                   '[{}] {} ({})'.format(4, self.c4_dname, self.c4.area.id)),
                           over=True)
        self.c5.assert_no_packets()

    def test_07_disjointnessisunified(self):
        """
        Situation: C4 adds an area that removes some of the previously existing disjointness.
        """

        self.c4.ooc('/zone_add 6')
        self.c4.discard_all()

        self.c4.ooc('/zone_list')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('== Active zones =='
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           '\r\n*Zone {}. Contains areas: {}. Is watched by: {}.'
                           .format('z0', '1',
                                   '[{}] {} ({})'.format(2, self.c2_dname, self.c2.area.id),
                                   'z1', '2-4',
                                   '[{}] {} ({})'.format(5, self.c5_dname, self.c5.area.id),
                                   'z2', '0 and 5-7',
                                   '[{}] {} ({})'.format(4, self.c4_dname, self.c4.area.id)),
                           over=True)
        self.c5.assert_no_packets()

class TestZoneBasic_03_Delete(_TestZone):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_delete incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_delete')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Passing parameters as not CM or Mod
        self.c5.ooc('/zone_delete 10000')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('You must be authorized to use a zone name with this command.',
                           over=True)

        # Zone that does not exist
        # This was a bug as late as 4.2.0-post2 (it raised an uncaught KeyError)
        self.c1.ooc('/zone_delete zoneThatDoesNotExist')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('`zoneThatDoesNotExist` is not a valid zone ID.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_02_deletezone(self):
        """
        Situation: C1 creates a zone, and then deletes it.
        """

        self.c1.ooc('/zone 0, 5')
        self.c1.discard_all()
        self.c2.discard_all() # would receive being in zone notification

        self.c1.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have deleted your zone.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.assert_zones(dict())

    def test_03_anywatchercandelete(self):
        """
        Situation: C1 creates a zone, C2 watches it, then deletes it.
        """

        self.c5.ooc('/zone')
        self.c1.discard_all()
        self.c5.discard_all()
        self.c2.ooc('/zone_watch z0')
        self.c2.discard_all()
        self.c5.discard_all()

        self.c2.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has deleted zone `{}`.'
                           .format(self.c2_dname, 2, 'z0'), over=True)
        self.c2.assert_ooc('You have deleted your zone.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_ooc('(X) {} [{}] has deleted your zone.'
                           .format(self.c2_dname, 2), over=True)

        self.assert_zones(dict())

    def test_04_nonwatcherscannotdelete(self):
        """
        Situation: C1 creates a zone, and C2 who is not watching it attempts to delete it. This
        fails.
        """

        self.c1.ooc('/zone 4')
        self.c1.discard_all()

        self.c2.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You are not watching a zone.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        self.assert_zones({'z0': {4}})

    def test_05_deletionheredoesnotaffectzonethere(self):
        """
        Situation: C2 now creates another zone. C2 deletes their zone. C1's zone still stands.
        """

        self.c2.ooc('/zone 5')
        self.c1.discard_all()
        self.c2.discard_all()

        self.c2.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has deleted zone `{}`.'
                           .format(self.c2_dname, 2, 'z1'), over=True)
        self.c2.assert_ooc('You have deleted your zone.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assert_zones({'z0': {4}})

    def test_06_deletezonewitharg(self):
        """
        Situation: C3 (who is made a mod) deletes C1's zone via using the zone name. C1, C3 and C4
        (who is made CM) are notified.
        """

        self.c3.make_mod()
        self.c4.make_cm()

        self.c3.ooc('/zone_delete {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has deleted your zone.'
                           .format(self.c3_dname, 3), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_ooc('You have deleted zone `{}`.'.format('z0'), over=True)
        self.c4.assert_ooc('(X) {} [{}] has deleted zone `{}`.'
                           .format(self.c3_dname, 3, 'z0'), over=True)
        self.c5.assert_no_packets()

    def test_07_twozonesdeletez0createzone(self):
        """
        Situation: C3 creates a zone z0, C4 creates a zone z1. C1 deletes z0. C3 attempts to create
        a new zone again. This zone should have ID z0, despite there being another zone z1, because
        z0 is the earliest available ID.
        This was a bug in the release version of 4.2.0 (it raised an uncaught AssertionError)
        """

        self.c3.ooc('/zone 0, 5')
        self.c4.ooc('/zone 6, 7')

        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.c4.discard_all()
        self.c5.discard_all()

        self.c1.ooc('/zone_delete {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have deleted zone `{}`.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_ooc('(X) {} [{}] has deleted your zone.'
                           .format(self.c1_dname, 1), over=True)
        self.c4.assert_ooc('(X) {} [{}] has deleted zone `{}`.'
                           .format(self.c1_dname, 1, 'z0'), over=True)
        self.c5.assert_no_packets()

        self.c3.ooc('/zone 0, 5')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] has created zone `{}` containing areas {} through {} ({}).'
                           .format(self.c3_dname, 3, 'z0', 0, 5, self.c3.area.id))
        self.c1.assert_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format('z0', 'z0'), over=True)
        self.c2.assert_ooc('(X) Your area has been made part of zone `{}`. To be able to receive '
                           'its notifications, start watching it with /zone_watch {}'
                           .format('z0', 'z0'), over=True)
        self.c3.assert_ooc('You have created zone `{}` containing areas {} through {}.'
                           .format('z0', 0, 5), over=True)
        self.c4.assert_ooc('(X) {} [{}] has created zone `{}` containing areas {} through {} ({}).'
                           .format(self.c3_dname, 3, 'z0', 0, 5, self.c3.area.id), over=True)
        self.c5.assert_no_packets()

    def test_08_attemptdeleteinvalidzone(self):
        """
        Situation: C1 deletes zone z0. They then attempt to delete zone z0 again. This fails.
        This was a bug as late as 4.2.0-post2 (it raised an uncaught KeyError)
        """

        self.c1.ooc('/zone_delete {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have deleted zone `{}`.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_ooc('(X) {} [{}] has deleted your zone.'
                           .format(self.c1_dname, 1), over=True)
        self.c4.assert_ooc('(X) {} [{}] has deleted zone `{}`.'
                           .format(self.c1_dname, 1, 'z0'), over=True)
        self.c5.assert_no_packets()

        self.c1.ooc('/zone_delete {}'.format('z0'))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('`{}` is not a valid zone ID.'.format('z0'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()
