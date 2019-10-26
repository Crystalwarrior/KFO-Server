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
