from .structures import _TestSituation5Mc1Gc2
from .test_blood import _TestBlood

class TestBloodSmear_01_Basic(_TestBlood):
    @classmethod
    def setUpClass(cls):
        """
        Situation:
                 -------------
                |            |
                A0 -> A4 -> A5
               |
               ---> A6 -> A7(*)
        """

        super().setUpClass()
        cls.c1.ooc('/bloodtrail 0')
        cls.c0.move_area(4)
        cls.c0.move_area(5)
        cls.c0.move_area(0)
        cls.c0.move_area(6)
        cls.c0.move_area(7)

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c3.discard_all()

        cls.c1.ooc('/bloodtrail_list')
        cls.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}'
                   .format(cls.pre_mes,
                           cls.area0.id, cls.a0_name, cls.a4_name, cls.a5_name, cls.a6_name,
                           cls.area4.id, cls.a4_name, cls.a0_name, cls.a5_name,
                           cls.area5.id, cls.a5_name, cls.a0_name, cls.a4_name,
                           cls.area6.id, cls.a6_name, cls.a0_name, cls.a7_name,
                           cls.area7.id, cls.a7_name, cls.a6_name))
        cls.c1.assert_ooc(cls.mes, over=True)

    def test_01_wrongarguments(self):
        """
        Situation: Clients try to use /bloodtrail_clean incorrectly.
        """

        # Non-staff clean other areas
        self.c3.ooc('/bloodtrail_smear 7')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        # Invalid area names
        self.c2.ooc('/bloodtrail_smear Not an area name')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `Not an area name`.', over=True)
        self.c3.assert_no_ooc()
        self.c2.ooc('/bloodtrail_list')
        self.c2.assert_ooc(self.mes, over=True)

        self.c2.ooc('/bloodtrail_smear 100') # No area called 100, or with ID 100 in test scenario
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `100`.', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        # Not using ,\ for areas with , in their names ("Class Trial Room,\ 2")
        self.c2.ooc('/bloodtrail_smear Class Trial Room, 2, Test 4')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area `Class Trial Room`.', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

    def test_02_smearownarea(self):
        """
        Situation: C2 smears their own area using no arguments. C1 verifies smear later.
        Note that this doesn't affect existing trails leading to the area, but just the blood
        inside the area.
        """

        # Non-staff smear
        self.c3.ooc('/bloodtrail_smear')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.'
                           .format(self.c3_dname, 3, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trail in your area.'
                           .format(self.c3_dname, 3), over=True)
        self.c3.assert_ooc('You smeared the blood trail in your area.', over=True)

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}'
                   .format(self.pre_mes,
                           self.area0.id, self.a0_name, self.a4_name, self.a5_name, self.a6_name,
                           self.area4.id, self.a4_name, self.a0_name, self.a5_name, '(SMEARED)',
                           self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                           self.area6.id, self.a6_name, self.a0_name, self.a7_name,
                           self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

        # Staff smear
        self.area4.blood_smeared = False

        self.c2.ooc('/bloodtrail_smear')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.'
                           .format(self.c2_dname, 2, self.a4_name), over=True)
        self.c2.assert_ooc('You smeared the blood trail in your area.', over=True)
        self.c3.assert_ooc('{} smeared the blood trail in your area.'
                           .format(self.c2_dname), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

    def test_03_smearfail(self):
        """
        Situation: C2 attempts to smear smeared areas and non-staff C0 attempts to smear clean area.
        These two fail.
        """

        self.c2.ooc('/bloodtrail_smear')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Area {} already has its blood trails smeared.'.format(self.a4_name),
                           over=True)
        self.c3.assert_no_ooc()

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}'
                   .format(self.pre_mes,
                           self.area0.id, self.a0_name, self.a4_name, self.a5_name, self.a6_name,
                           self.area4.id, self.a4_name, self.a0_name, self.a5_name, '(SMEARED)',
                           self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                           self.area6.id, self.a6_name, self.a0_name, self.a7_name,
                           self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

        self.c3.move_area(2)
        self.c3.ooc('/bloodtrail_smear')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_ooc('You could not find any blood in the area.', over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        self.c3.move_area(4)

    def test_04_smearotherareas(self):
        """
        Situation: C1 smears multiple areas simultaneously.
        Assumption: a0_name < a6_name
        """

        self.c1.ooc('/bloodtrail_smear {}, {}'
                    .format(self.a0_name, self.area6.id))
        self.c1.assert_ooc('You smeared the blood trails in areas {} and {}.'
                           .format(self.a0_name, self.a6_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trails in areas {} and {}.'
                           .format(self.c1_dname, 1, self.a0_name, self.a6_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {} {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}'
                   .format(self.pre_mes,
                           0, self.a0_name, self.a4_name, self.a5_name, self.a6_name, '(SMEARED)',
                           self.area4.id, self.a4_name, self.a0_name, self.a5_name, '(SMEARED)',
                           self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                           self.area6.id, self.a6_name, self.a0_name, self.a7_name, '(SMEARED)',
                           self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

    def test_05_smearinbleeding(self):
        """
        Situation: C0 and C1 attempt to clean the area where bleeding C0 is. This succeeds... once.
        """

        self.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {} {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {} {}'
                   .format(self.pre_mes,
                           0, self.a0_name, self.a4_name, self.a5_name, self.a6_name, '(SMEARED)',
                           self.area4.id, self.a4_name, self.a0_name, self.a5_name, '(SMEARED)',
                           self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                           self.area6.id, self.a6_name, self.a0_name, self.a7_name, '(SMEARED)',
                           self.area7.id, self.a7_name, self.a6_name, '(SMEARED)'))

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You smeared the blood trail in your area.',
                           over=True)
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.'
                           .format(self.c0_dname, 0, self.a7_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.'
                           .format(self.c0_dname, 0, self.a7_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        self.c1.ooc('/bloodtrail_smear {}'.format(self.a7_name))
        self.c1.assert_ooc('Area {} already has its blood trails smeared.'
                           .format(self.a7_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

    def test_06_cleansmeared(self):
        """
        Situation: C2 and C0 attempt to clean area 6 and 7 respectively. C2 succeeds, C0 doesn't as
        they are still bleeding.
        """

        self.mes = ('{}'
                   '\r\n*({}) {}: {}, {}, {} {}'
                   '\r\n*({}) {}: {}, {} {}'
                   '\r\n*({}) {}: {}, {}'
                   '\r\n*({}) {}: {} {}'
                   .format(self.pre_mes,
                           0, self.a0_name, self.a4_name, self.a5_name, self.a6_name, '(SMEARED)',
                           self.area4.id, self.a4_name, self.a0_name, self.a5_name, '(SMEARED)',
                           self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                           self.area7.id, self.a7_name, self.a6_name, '(SMEARED)'))

        self.c1.ooc('/bloodtrail_clean {}'.format(self.a6_name))
        self.c1.assert_ooc('You cleaned the blood trail in area {}.'
                           .format(self.a6_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] cleaned the blood trail in area {}.'
                           .format(self.c1_dname, 1, self.a6_name), over=True)
        self.assertFalse(self.area6.blood_smeared)

class TestBloodSmear_02_NoLights(_TestSituation5Mc1Gc2):
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

    def test_01_nolightsbloodsmear_noblood(self):
        """
        Situation: C0 attempts to smear an area's blood with no blood.
        """

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You could not find any blood in the area.', over=True)
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area4.blood_smeared)

    def test_02_nolightsbloodsmear_yestrailnobleed(self):
        """
        Situation: C0 attempts to smear an area's blood with a trail and no bleeders. This
        succeeds... once.
        """

        self.area4.bleeds_to = {self.area0.name}

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You smeared the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.'
                           .format(self.c0_dname, 0, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trail in your area.'
                           .format(self.c0_dname, 0), over=True)
        self.c3.assert_no_ooc() # No message because no lights
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('Area {} already has its blood trails smeared.'
                           .format(self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

    def test_03_nolightsbloodsmear_yestrailyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood with a trail and a bleeder. Twice.
        """

        self.area4.blood_smeared = False
        self.c4.is_bleeding = True
        self.test_02_nolightsbloodsmear_yestrailnobleed()

class TestBloodSmear_03_Blind(_TestSituation5Mc1Gc2):
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

    def test_01_blindbloodsmear_noblood(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with no blood
        1. While lights are on
        2. While lights are off
        """

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You could not find any blood in the area.', over=True)
        self.c2.assert_no_ooc() # No poking fun
        self.c3.assert_no_ooc()
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area4.blood_smeared)

        self.c0.ooc('/lights off')
        self.c0.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You could not find any blood in the area.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertEqual(self.area4.bleeds_to, set())
        self.assertFalse(self.area4.blood_smeared)

    def test_02_blindbloodsmear_yestrailnobleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with blood trail and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.area4.bleeds_to = {self.area0.name}
        self.area4.lights = True
        self.area4.blood_smeared = False

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You smeared the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.' # Different area
                           .format(self.c0_dname, 0, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trail in your area.'
                           .format(self.c0_dname, 0), over=True)
        self.c3.assert_ooc('{} smeared the blood trail in your area.'
                           .format(self.c0_dname), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/lights off')
        self.c0.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.area4.blood_smeared = False

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('You smeared the blood trail in your area.', over=True)
        self.c1.assert_ooc('(X) {} [{}] smeared the blood trail in area {}.' # Different area
                           .format(self.c0_dname, 0, self.a4_name), over=True)
        self.c2.assert_ooc('(X) {} [{}] smeared the blood trail in your area.' # No lights
                           .format(self.c0_dname, 0), over=True)
        self.c3.assert_no_ooc() # No lights
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

        self.c0.ooc('/bloodtrail_smear')
        self.c0.assert_ooc('Area {} already has its blood trails smeared.'
                           .format(self.a4_name), over=True)
        self.assertEqual(self.area4.bleeds_to, {self.area0.name})
        self.assertTrue(self.area4.blood_smeared)

    def test_03_blindbloodsmear_yestrailyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with trail and bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = True
        self.test_02_blindbloodsmear_yestrailnobleed() # Exact same outcomes.

    def test_04_blindbloodsmear_yessmearnobleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with smears and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = False
        self.area4.blood_smeared = True
        self.test_02_blindbloodsmear_yestrailnobleed() # Exact same outcomes.

    def test_05_blindbloodsmear_yessmearyesbleed(self):
        """
        Situation: C0 attempts to clean an area's blood while blind with smears and no bleeding
        1. While lights are on
        2. While lights are off
        """

        self.c3.is_bleeding = True
        self.area4.blood_smeared = True
        self.test_02_blindbloodsmear_yestrailnobleed() # Exact same outcomes.
