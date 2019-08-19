from .structures import _TestSituation5Mc1Gc2

class TestBloodClean_01_NoLights(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c0.move_area(4)
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.c0.ooc('/lights off')

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c3.discard_all()

    def test_01_nolightsbloodclean_noblood(self):
        """
        Situation: C0 attempts to clean an area's blood with no blood.
        """

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in the area, unaware that there '
                           'was no blood to begin with.'.format(self.c0_cname), over=True)
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area4.blood_smeared)

    def test_02_nolightsbloodclean_yestrailnobleed(self):
        """
        Situation: C0 attempts to clean an area's blood with a trail and no bleeders. Twice.
        """

        self.area4.bleeds_to = {self.area0.name}

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

    def test_03_nolightsbloodclean_yestrailyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood with a trail and a bleeder. Twice.
        """

        self.area4.blood_smeared = False
        self.c4.is_bleeding = True
        self.test_02_nolightsbloodclean_yestrailnobleed()

class TestBloodClean_02_Blind(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c1.ooc('/blind 0')
        cls.c0.move_area(4)
        cls.c2.move_area(4)
        cls.c3.move_area(4)

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c3.discard_all()

    def test_01_blindbloodclean_noblood(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with no blood
        1. While lights are on
        2. While lights are off
        """

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c2.assert_ooc('{} tried to clean the blood trail in the area, unaware that there was '
                           'no blood to begin with.'.format(self.c0_cname), over=True)
        self.c3.assert_ooc('{} tried to clean the blood trail in the area, unaware that there was '
                           'no blood to begin with.'.format(self.c0_cname), over=True)
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area5.blood_smeared)

        self.c0.ooc('/lights off')
        self.c0.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in the area, unaware that there '
                           'was no blood to begin with.'.format(self.c0_cname), over=True)
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area5.blood_smeared)

    def test_02_blindbloodclean_yestrailnobleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with blood trail and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.area4.bleeds_to = {self.area0.name}
        self.area4.lights = True

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c1.assert_ooc('{} tried to clean the blood trail in area {}, but as they could not '
                           'see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c2.assert_ooc('{} tried to clean the blood trail in area {}, but as they could not '
                           'see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c3.assert_ooc('{} tried to clean the blood trail in the area, but only managed to '
                           'smear it all over the place.'
                           .format(self.c0_cname), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/lights off')
        self.c0.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.area4.blood_smeared = False

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You cleaned the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} tried to clean the blood trail in area {}, but as they could '
                           'not see, they only managed to smear it all over the place.'
                           .format(self.c0_cname, self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

    def test_03_blindbloodclean_yestrailyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with trail and bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = True
        self.test_02_blindbloodclean_yestrailnobleed() # Exact same outcomes.

    def test_04_blindbloodclean_yessmearnobleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with smears and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = False
        self.area4.blood_smeared = True
        self.test_02_blindbloodclean_yestrailnobleed() # Exact same outcomes.

    def test_05_blindbloodclean_yessmearyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with smears and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = True
        self.area4.blood_smeared = True
        self.test_02_blindbloodclean_yestrailnobleed() # Exact same outcomes.
