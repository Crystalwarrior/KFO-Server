from .structures import _TestSituation4Mc12

class _TestBlood(_TestSituation4Mc12):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.pre_mes = '== Blood trails in this server =='

    def assert_bleeding(self, yes, no):
        if yes == 0:
            yes = set()
        if no == 0:
            no = set()

        if yes == 1:
            yes = {client for client in self.server.client_manager.clients if client not in no}
        if no == 1:
            no = {client for client in self.server.client_manager.clients if client not in yes}

        for client in yes:
            self.assertTrue(client.is_bleeding, client)
        for client in no:
            self.assertFalse(client.is_bleeding, client)

class TestBlood_01_Basic(_TestBlood):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /bloodtrail incorrectly.
        """

        # Insufficient permissions
        self.c0.ooc('/bloodtrail 1')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

        # Empty
        self.c1.ooc('/bloodtrail')
        self.c1.assert_ooc('Expected client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

        # Wrong client ID
        self.c1.ooc('/bloodtrail aa bb')
        self.c1.assert_ooc('aa bb does not look like a valid client ID.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

    def test_02_bleedunbleedc0(self):
        """
        Situation: C1 cuts C0. C2 (in another area) then uncuts them.
        """

        self.c1.ooc('/bloodtrail 0')
        self.c0.assert_ooc('You are now bleeding.', over=True)
        self.c1.assert_ooc('{} is now bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c2.assert_ooc('{} is now bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c3.assert_no_ooc()
        self.assert_bleeding({self.c0}, 1)

        self.c1.ooc('/bloodtrail 0')
        self.c0.assert_ooc('You are no longer bleeding.', over=True)
        self.c1.assert_ooc('{} is no longer bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c2.assert_ooc('{} is no longer bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

    def test_03_bleedstaffandself(self):
        """
        Situation: C1 cuts C2 (GM) and themselves.
        """

        self.c1.ooc('/bloodtrail 2')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('{} is now bleeding ({}).'.format(self.c2_cname, 4), over=True)
        self.c2.assert_ooc('You are now bleeding.', over=True)
        self.c3.assert_ooc('You see {} is now bleeding.'.format(self.c2_cname), over=True)
        self.assert_bleeding({self.c2}, 1)

        self.c1.ooc('/bloodtrail 1')
        self.c0.assert_ooc('You see {} is now bleeding.'.format(self.c1_cname), over=True)
        self.c1.assert_ooc('You are now bleeding.', over=True)
        self.c2.assert_ooc('{} is now bleeding ({}).'.format(self.c1_cname, 0), over=True)
        self.c3.assert_no_ooc()
        self.assert_bleeding({self.c1, self.c2}, 1)

    def test_04_unbleedstaffandself(self):
        """
        Situation: C2 uncuts C1 (mod) and themselves.
        """

        self.c2.ooc('/bloodtrail 1')
        self.c0.assert_ooc('You see {} is no longer bleeding.'.format(self.c1_cname), over=True)
        self.c1.assert_ooc('You are no longer bleeding.', over=True)
        self.c2.assert_ooc('{} is no longer bleeding ({}).'.format(self.c1_cname, 0), over=True)
        self.c3.assert_no_ooc()
        self.assert_bleeding({self.c2}, 1)

        self.c2.ooc('/bloodtrail 2')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('{} is no longer bleeding ({}).'.format(self.c2_cname, 4), over=True)
        self.c2.assert_ooc('You are no longer bleeding.', over=True)
        self.c3.assert_ooc('You see {} is no longer bleeding.'.format(self.c2_cname), over=True)
        self.assert_bleeding(0, 1)

class TestBlood_02_Effect(_TestBlood):
    def test_01_seebleedingjustonarrival(self):
        """
        Situation: C1 sets C0 to be bleeding. C2 moves to their area and is notified of bleeding,
        then leaves to a different area and is notified of nothing.
        """

        self.c1.ooc('/bloodtrail 0')
        self.c0.assert_ooc('You are now bleeding.', over=True)
        self.c1.assert_ooc('{} is now bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c2.assert_ooc('{} is now bleeding ({}).'.format(self.c0_cname, 0), over=True)
        self.c3.assert_no_ooc()
        self.assert_bleeding({self.c0}, 1)

        self.c2.move_area(0, discard_trivial=True)
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_cname))
        self.c2.assert_ooc('You spot some blood in the area.', over=True)

        self.c2.move_area(6, discard_trivial=True)
        self.c2.assert_no_ooc()

    def test_02_notifybleedingondepartureandarrival(self):
        """
        Situation: C0 moves to area 5. Players in area 0 (just C1) are notified.
        C0 then moves to area 6, where C2 is. Players in area 5 (no one) and 6 (C2) are notified.
        """

        self.c0.move_area(5)
        self.c1.assert_ooc('You see {} leave the area while still bleeding.'.format(self.c0_cname),
                           over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c0.move_area(6)
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('You see {} arrive to the area while bleeding.'.format(self.c0_cname),
                           over=True)
        self.c3.assert_no_ooc()

    def test_03_bloodtrail(self):
        """
        Situation: C1 moves to area 5 then 6 and notices the blood trails.
        A0->A5->A6

        Assumption: area0.name sorted alphabetically before area6.name
        """

        self.c1.move_area(5, discard_trivial=True)
        self.c1.assert_ooc('You spot a blood trail leading to the {} and the {}.'
                           .format(self.a0_name, self.a6_name), over=True)

        self.c1.move_area(6, discard_trivial=True)
        self.c1.assert_ooc('You see {} is bleeding.'.format(self.c0_cname))
        self.c1.assert_ooc('You spot a blood trail leading to the {}.'.format(self.a5_name),
                           over=True)

    def test_04_bleedonbloodtrail(self):
        """
        Situation: C0 moves back to area 5, C1 follows them. C1 gets the same blood trail message
        as before.
        """

        self.c0.move_area(5)
        self.c1.assert_ooc('You see {} leave the area while still bleeding.'.format(self.c0_cname),
                           over=True)
        self.c2.assert_ooc('You see {} leave the area while still bleeding.'.format(self.c0_cname),
                           over=True)

class TestBlood_03_List(_TestBlood):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /bloodtrail_list incorrectly.
        """

        # Insufficient permissions
        self.c0.ooc('/bloodtrail_list')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

        # Non-empty
        self.c1.ooc('/bloodtrail_list 3')
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

        # No blood
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('No areas have blood.', over=True)
        self.c0.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assert_bleeding(0, 1)

    def test_02_unconnectedblood(self):
        """
        Situation: C0 is cut. Trail is unconnected pool of blood, so just show that.
        """

        self.c1.ooc('/bloodtrail 0')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('{}\r\n*({}) {}: {}'
                           .format(self.pre_mes,
                                   self.area0.id, self.a0_name, self.a0_name),
                           over=True)

    def test_03_bloodtrailsimple(self):
        """
        Situation: C0 moves, so blood is connected across areas. Reflect that.
        A0 -> A4
        """

        self.c0.move_area(4)
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('{}'
                           '\r\n*({}) {}: {}'
                           '\r\n*({}) {}: {}'
                           .format(self.pre_mes,
                                   self.area0.id, self.a0_name, self.a4_name,
                                   self.area4.id, self.a4_name, self.a0_name), over=True)

    def test_04_bloodtrailpath(self):
        """
        Situation: C0 moves again, so middle area has two destinations. Reflect that.
        A0 -> A4 -> A5
        Assumption: a0_name sorted before a5_name
        """

        self.c0.move_area(5)
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('{}'
                           '\r\n*({}) {}: {}'
                           '\r\n*({}) {}: {}, {}'
                           '\r\n*({}) {}: {}'
                           .format(self.pre_mes,
                                   self.area0.id, self.a0_name, self.a4_name,
                                   self.area4.id, self.a4_name, self.a0_name, self.a5_name,
                                   self.area5.id, self.a5_name, self.a4_name), over=True)

    def test_05_bloodtrailloop(self):
        """
        Situation: C0 moves back to previous area, blood trail list is unaffected.
        C0 then moves to new area, blood trail list changes.
        A0 -> A4 -> A5
               |
               ---> A6
        Assumption: a0_name < a5_name < a6_name
        """

        self.c0.move_area(4)
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('{}'
                           '\r\n*({}) {}: {}'
                           '\r\n*({}) {}: {}, {}'
                           '\r\n*({}) {}: {}'
                           .format(self.pre_mes,
                                   self.area0.id, self.a0_name, self.a4_name,
                                   self.area4.id, self.a4_name, self.a0_name, self.a5_name,
                                   self.area5.id, self.a5_name, self.a4_name), over=True)

        self.c0.move_area(6)
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c1.ooc('/bloodtrail_list')
        mes = ('{}'
               '\r\n*({}) {}: {}'
               '\r\n*({}) {}: {}, {}, {}'
               '\r\n*({}) {}: {}'
               '\r\n*({}) {}: {}'
               .format(self.pre_mes,
                       self.area0.id, self.a0_name, self.a4_name,
                       self.area4.id, self.a4_name, self.a0_name, self.a5_name, self.a6_name,
                       self.area5.id, self.a5_name, self.a4_name,
                       self.area6.id, self.a6_name, self.a4_name))
        self.c1.assert_ooc(mes, over=True)

class TestBlood_04_Set(_TestBlood):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /bloodtrail_set incorrectly.
        """

        # Non-staff clean other areas
        self.c3.ooc('/bloodtrail_set 7')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('No areas have blood.', over=True)

        # Invalid area names
        self.c2.ooc('/bloodtrail_set Not an area name')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area Not an area name', over=True)
        self.c3.assert_no_ooc()
        self.c2.ooc('/bloodtrail_list')
        self.c2.assert_ooc('No areas have blood.', over=True)

        self.c2.ooc('/bloodtrail_set 100') # No area called 100, or with ID 100 in test scenario
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area 100', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('No areas have blood.', over=True)

        # Not using ,\ for areas with , in their names ("Class Trial Room,\ 2")
        self.c2.ooc('/bloodtrail_set Class Trial Room, 2, Test 4')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area Class Trial Room', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc('No areas have blood.', over=True)

    def test_02_noarguments(self):
        """
        Situation: C2 sets its area to have a single pool of blood.
        """

        self.c2.ooc('/bloodtrail_set')
        self.c1.assert_ooc('{} set the blood trail in area {} to be an unconnected pool of blood.'
                           .format(self.c2.name, self.a4_name), over=True)
        self.c2.assert_ooc('Set the blood trail in this area to be an unconnected pool of blood.',
                           over=True)
        self.c3.assert_ooc('The blood trail in this area was set to be an unconnected pool of '
                           'blood.', over=True)

        self.c1.ooc('/bloodtrail_list')
        mes = ('{}'
               '\r\n*({}) {}: {}'
               .format(self.pre_mes,
                       self.area4.id, self.a4_name, self.a4_name))
        self.c1.assert_ooc(mes, over=True)

    def test_03_areaarguments(self):
        """
        Situation: C2 now sets its area to be bleeding to areas 5 and 7.
        """

        self.c2.ooc('/bloodtrail_set {}, {}'.format(self.area5.id, self.a7_name))
        x = 'go to the {}, the {} and the {}'.format(self.a4_name, self.a5_name, self.a7_name)
        self.c1.assert_ooc('{} set the blood trail in area {} to {}.'
                           .format(self.c2.name, self.a4_name, x), over=True)
        self.c2.assert_ooc('Set the blood trail in this area to {}.'
                           .format(x), over=True)
        self.c3.assert_ooc('The blood trail in this area was set to {}.'.format(x), over=True)

class TestBlood_05_Clean(_TestBlood):
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
        self.c3.ooc('/bloodtrail_clean 7')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        # Invalid area names
        self.c2.ooc('/bloodtrail_clean Not an area name')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area Not an area name', over=True)
        self.c3.assert_no_ooc()
        self.c2.ooc('/bloodtrail_list')
        self.c2.assert_ooc(self.mes, over=True)

        self.c2.ooc('/bloodtrail_clean 100') # No area called 100, or with ID 100 in test scenario
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area 100', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        # Not using ,\ for areas with , in their names ("Class Trial Room,\ 2")
        self.c2.ooc('/bloodtrail_clean Class Trial Room, 2, Test 4')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Could not parse area Class Trial Room', over=True)
        self.c3.assert_no_ooc()
        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

    def test_02_cleanownarea(self):
        """
        Situation: C2 cleans their own area using no arguments. C1 verifies cleanup later.
        Note that this doesn't affect existing trails leading to the area, but just the blood
        inside the area.
        """

        self.c2.ooc('/bloodtrail_clean')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('{} cleaned the blood trail in area {}.'
                           .format(self.c2.name, self.a4_name), over=True)
        self.c2.assert_ooc('You cleaned the blood trail in the current area.'
                           .format(self.a4_name), over=True)
        self.c3.assert_ooc('The blood trail in your area was cleaned.'
                           .format(self.c3_cname, self.a4_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}'
                    '\r\n*({}) {}: {}, {}, {}'
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}'
                    .format(self.pre_mes,
                            self.area0.id, self.a0_name, self.a4_name, self.a5_name, self.a6_name,
                            self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                            self.area6.id, self.a6_name, self.a0_name, self.a7_name,
                            self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

    def test_03_cleanthecleaned(self):
        """
        Situation: C2 attempts to clean clean areas. This fails.
        """

        self.c2.ooc('/bloodtrail_clean')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('There is no blood in area {}.'.format(self.a4_name), over=True)
        self.c3.assert_no_ooc()

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}' # Python why are you like this
                    '\r\n*({}) {}: {}, {}, {}'
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}'
                    .format(self.pre_mes,
                            self.area0.id, self.a0_name, self.a4_name, self.a5_name, self.a6_name,
                            self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                            self.area6.id, self.a6_name, self.a0_name, self.a7_name,
                            self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

        self.c2.ooc('/bloodtrail_clean 2')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('There is no blood in area {}.'.format(self.a2_name), over=True)
        self.c3.assert_no_ooc()

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

    def test_04_cleanotherareas(self):
        """
        Situation: C1 cleans multiple areas simultaneously.
        Assumption: a0_name < a6_name
        """

        self.c1.ooc('/bloodtrail_clean {}, {}'
                    .format(self.a0_name, self.area6.id))
        self.c1.assert_ooc('You cleaned the blood trails in areas {}, {}.'
                           .format(self.a0_name, self.a6_name), over=True)
        self.c2.assert_ooc('{} cleaned the blood trails in areas {}, {}.'
                           .format(self.c1.name, self.a0_name, self.a6_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.mes = ('{}' # Python why are you like this
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}'
                    .format(self.pre_mes,
                            self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                            self.area7.id, self.a7_name, self.a6_name))
        self.c1.assert_ooc(self.mes, over=True)

    def test_05_cleaninbleeding(self):
        """
        Situation: C0 and C1 attempt to clean the area where bleeding C0 is. This fails.
        """

        self.mes = ('{}' # Python why are you like this
                    '\r\n*({}) {}: {}, {}'
                    '\r\n*({}) {}: {}'
                    .format(self.pre_mes,
                            self.area5.id, self.a5_name, self.a0_name, self.a4_name,
                            self.area7.id, self.a7_name, self.a6_name))

        self.c0.ooc('/bloodtrail_clean')
        self.c0.assert_ooc('You tried to clean the place up, but the blood just keeps coming.',
                           over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

        self.c1.ooc('/bloodtrail_clean {}'.format(self.a7_name))
        self.c1.assert_ooc('{} in area {} is still bleeding, so the area cannot be cleaned.'
                           .format(self.c0_cname, self.a7_name), over=True)

        self.c1.ooc('/bloodtrail_list')
        self.c1.assert_ooc(self.mes, over=True)

