from .structures import _TestSituation5Mc1Gc2

"""
This class is unable to test the timing for poison. It will just test that the poison is applied
and the output messages, not that poison effect is applied.
"""

class _TestPoisonCure(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c0.move_area(4)
        cls.c1.move_area(4)
        cls.c2.move_area(5)
        cls.c3.move_area(5)
        cls.c4.move_area(6)

    def assert_effects(self, expected_zones):
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

class TestPoisonCure_01_Poison(_TestPoisonCure):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /poison incorrectly.
        """

        # Not staff
        self.c0.ooc('/poison 1 bdg 10')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        # Invalid client ID
        self.c1.ooc('/poison bdg 0 10')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('`bdg` does not look like a valid client ID.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/poison 5 bdg 10')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('No targets found.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        # Invalid effect names (currently accepts b, d, or g)
        self.c1.ooc('/poison 0 bde 10')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Invalid effect letter `{}`.'.format('e'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/poison 0 dgbd 10')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Effect list cannot contained repeated characters.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_02_poison(self):
        """
        Situation: C1 poisons C0 with blindness. C2 gets notified.
        """

        self.c1.ooc('/poison 0 b 80')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Blindness: acts in 1:20.', over=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Blindness: acts in 1:20.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} poisoned {} with the following effects ({}): '
                           '\r\n*Blindness: acts in 1:20.'
                           .format(self.c1.name, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_03_multiplepoisons(self):
        """
        Situation: C1 poisons C0 with deafness and gagged in the same command. C2 gets notified.
        """

        self.c1.ooc('/poison 0 dg 20')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.', over=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.'
                           .format(self.c1.name, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_04_overridewithshorter(self):
        """
        Situation: C1 poisons C0 with deafness that triggers before the currently existing deafness
        effect. This effect gets overwritten. C2 gets notified as staff.
        """

        self.c1.ooc('/poison 0 d 10')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Deafness: now acts in 10 seconds.', over=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Deafness: now acts in 10 seconds.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: now acts in 10 seconds.'
                           .format(self.c1.name, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_05_cannotoverridewithlonger(self):
        """
        Situation: C1 poisons C0 with deafness that triggers after the currently existing deafness
        effect. This effect does NOT get overwritten. C2 gets notified.
        Note that due to timing limitations, the whole message cannot be checked (because it is
        supposed to print the remaining time of the shorter effect, and that timing cannot be
        guaranteed in a testing environment)
        """

        self.c1.ooc('/poison 0 d 20')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Deafness: still acts in ', over=True, allow_partial_match=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Deafness: still acts in '
                           .format(self.c0_dname), over=True, allow_partial_match=True)
        self.c2.assert_ooc('(X) {} poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: still acts in '
                           .format(self.c1.name, self.c0_dname, self.c1.area.id),
                           over=True, allow_partial_match=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_06_mixedoverriding(self):
        """
        Situation: C1 poisons C0 with a shorter blindness and longer gagged effect. The blindness
        timer gets overwritten, but the gagged one does not. C2 gets notified.
        """

        self.c1.ooc('/poison 0 bg 50') # 20 (gagged) < 50 (new) < 80 (blind)
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Blindness: now acts in 50 seconds.'
                           '\r\n*Gagged: still acts in ', over=True, allow_partial_match=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Blindness: now acts in 50 seconds.'
                           '\r\n*Gagged: still acts in '
                           .format(self.c0_dname), over=True, allow_partial_match=True)
        self.c2.assert_ooc('(X) {} poisoned {} with the following effects ({}): '
                           '\r\n*Blindness: now acts in 50 seconds.'
                           '\r\n*Gagged: still acts in '
                           .format(self.c1.name, self.c0_dname, self.c1.area.id),
                           over=True, allow_partial_match=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_07_selfpoison(self):
        """
        Situation: C2 poisons themselves. C1 gets notified.
        """

        self.c2.ooc('/poison 2 gd 30')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} poisoned themselves with the following effects ({}): '
                           '\r\n*Deafness: acts in 30 seconds.'
                           '\r\n*Gagged: acts in 30 seconds.'
                           .format(self.c2.name, self.c2.area.id), over=True)
        self.c2.assert_ooc('You poisoned yourself with the following effects: '
                           '\r\n*Deafness: acts in 30 seconds.'
                           '\r\n*Gagged: acts in 30 seconds.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
