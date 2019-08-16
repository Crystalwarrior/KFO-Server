from .structures import _TestSituation4Mc12

class _TestBlood(_TestSituation4Mc12):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)

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
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_cname), ooc_over=True)

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
                           .format(self.area0.name, self.area6.name), over=True)

        self.c1.move_area(6, discard_trivial=True)
        self.c1.assert_ooc('You see {} is bleeding.'.format(self.c0_cname))
        self.c1.assert_ooc('You spot a blood trail leading to the {}.'.format(self.area5.name),
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