from .structures import _TestSituation5Mc1Gc2

class _TestBloodTrail(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        """
        Situation:
                 -------------
                |            |
                A0 -> A4 -> A5
               |      |
               ---> A6 -> A7

        C0 in area 7, bleeding
        C1 in area 0, not bleeding
        C2 in area 7, bleeding
        C3 in area 6, bleeding
        C4 in area 0, not bleeding
        """

        super().setUpClass()
        cls.c2.move_area(4)

        cls.c1.ooc('/bloodtrail 0')
        cls.c0.move_area(4)
        cls.c0.move_area(5)
        cls.c0.move_area(0)
        cls.c0.move_area(6)
        cls.c0.move_area(7)

        cls.c1.ooc('/bloodtrail 2')
        cls.c2.move_area(6)
        cls.c2.move_area(7)

        cls.c1.ooc('/bloodtrail 3')
        cls.c3.move_area(6)

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c3.discard_all()
        cls.c4.discard_all()

        cls.blackout_background = cls.server.config['blackout_background']

class TestBloodNotifyExistTrail_01_Lights(_TestBloodTrail):
    def test_01_normalarrival(self):
        """
        Situation: C4 moves to:
        1. Area 6, where C3 is bleeding.
        2. Area 7, where C0 and C2 are bleeding.
        3. Area 4, where only blood trails exist
        4. Area 2, where there is nothing
        """

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You see {} is bleeding.'.format(self.c3_dname))
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You see {} and {} are bleeding.'
                           .format(*sorted([self.c0_dname, self.c2_dname])))
        self.c4.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a5_name, self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

    def test_02_blindarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind.
        C4 gets audio cues for areas 6, 7 (people bleeding) but not area 4 (no one bleeding)
        C4 gets smell cue for area 4 (trail with no one bleeding) but not areas 6, 7 (got before)
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

    def test_03_blinddeafarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind and deaf.
        C4 gets smell cue for area 4 (trail with no one bleeding) and areas 6, 7 (got before)
        nor 2 (no blood).
        """

        self.c2.ooc('/deafen 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

    def test_04_deafarrival(self):
        """
        Situation: Same as test_01, but C4 is now only deaf.
        C4 gets visual cues for all areas.
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You see {} is bleeding.'.format(self.c3_dname))
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You see {} and {} are bleeding.'
                           .format(*sorted([self.c0_dname, self.c2_dname])))
        self.c4.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a5_name, self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

class TestBloodNotifyExistTrail_02_NoLights(_TestBloodTrail):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.ooc('/lights off')
        cls.c3.ooc('/lights off')
        cls.c1.move_area(4)
        cls.c1.ooc('/lights off')
        cls.c1.move_area(2)
        cls.c1.ooc('/lights off')
        cls.c1.move_area(0)

        cls.c0.discard_all()
        cls.c1.discard_all()
        cls.c2.discard_all()
        cls.c3.discard_all()
        cls.c4.discard_all()

    def test_01_normalarrival(self):
        """
        Situation: C4 moves to:
        1. Area 6, where C3 is bleeding.
        2. Area 7, where C0 and C2 are bleeding.
        3. Area 4, where only blood trails exist
        4. Area 2, where there is nothing
        """

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.', over=True)

    def test_02_blindarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind.
        C4 gets audio cues for areas 6, 7 (people bleeding) but not area 4 (no one bleeding)
        C4 gets smell cue for area 4 (trail with no one bleeding) but not areas 6, 7 (got before)
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

    def test_03_blinddeafarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind and deaf.
        C4 gets smell cue for area 4 (trail with no one bleeding) and areas 6, 7 (got before)
        nor 2 (no blood).
        """

        self.c2.ooc('/deafen 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

    def test_04_deafarrival(self):
        """
        Situation: Same as test_01, but C4 is now only deaf.
        C4 gets visual cues for all areas.
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.', over=True)

class TestBloodNotifyExistTrail_03_SwitchLights(TestBloodNotifyExistTrail_02_NoLights):
    def test_01_normalarrival(self):
        """
        Situation: C4 moves to:
        1. Area 6, where C3 is bleeding.
        2. Area 7, where C0 and C2 are bleeding.
        3. Area 4, where only blood trails exist
        4. Area 2, where there is nothing
        """

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area6.background)
        self.c3.assert_ooc('You turned the lights on.')
        self.c3.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c3.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.area6.background)
        self.c4.assert_ooc('The lights were turned on.')
        self.c4.assert_ooc('You see {} is bleeding.'.format(self.c3_dname))
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        # self.c3.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('The lights were turned off.', over=True)

        ###
        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.area7.background)
        self.c0.assert_ooc('The lights were turned on.')
        self.c0.assert_ooc('You see {} is bleeding.'.format(self.c2_dname))
        self.c0.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c0.assert_ic('(Something catches your attention)', over=True)
        self.c2.assert_packet('BN', self.area7.background)
        self.c2.assert_ooc('You turned the lights on.')
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_dname))
        self.c2.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c2.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.area7.background)
        self.c4.assert_ooc('The lights were turned on.')
        self.c4.assert_ooc('You see {} and {} are bleeding.'
                           .format(*sorted([self.c0_dname, self.c2_dname])))
        self.c4.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        # self.c0.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.')
        self.c2.assert_ooc('(X) You see {} is bleeding.'.format(self.c0_dname)) # STAFF!
        self.c2.assert_ooc('(X) You spot a blood trail leading to the {}.' # STAFF!
                           .format(self.a6_name), over=True)
        # self.c2.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('The lights were turned off.', over=True)

        ###
        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.area4.background)
        self.c4.assert_ooc('You turned the lights on.')
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a5_name, self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You turned the lights off.', over=True)
        # self.c3.assert_ooc('You smell blood.', over=True) # NO, DIDNT CHANGE SMELLING

        ###
        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.area2.background)
        self.c4.assert_ooc('You turned the lights on.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You turned the lights off.', over=True)

    def test_02_blindarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind.
        C4 gets audio cues for areas 6, 7 (people bleeding) but not area 4 (no one bleeding)
        C4 gets smell cue for area 4 (trail with no one bleeding) but not areas 6, 7 (got before)
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area6.background)
        self.c3.assert_ooc('You turned the lights on.')
        self.c3.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c3.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        # self.c3.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

        ###
        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You hear faint drops of blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.area7.background)
        self.c0.assert_ooc('The lights were turned on.')
        self.c0.assert_ooc('You see {} is bleeding.'.format(self.c2_dname))
        self.c0.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c0.assert_ic('(Something catches your attention)', over=True)
        self.c2.assert_packet('BN', self.area7.background)
        self.c2.assert_ooc('You turned the lights on.')
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_dname))
        self.c2.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c2.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)
        self.c4.assert_no_ic() # Blind gets no IC

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        # self.c0.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.')
        self.c2.assert_ooc('(X) You see {} is bleeding.'.format(self.c0_dname)) # STAFF!
        self.c2.assert_ooc('(X) You spot a blood trail leading to the {}.' # STAFF!
                           .format(self.a6_name), over=True)
        # self.c2.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

        ###
        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)
        # self.c3.assert_ooc('You smell blood.', over=True) # NO, DIDNT CHANGE SMELLING

        ###
        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You hear a flicker.', over=True)

    def test_03_blinddeafarrival(self):
        """
        Situation: Same as test_01, but C4 is now blind and deaf.
        C4 gets smell cue for area 4 (trail with no one bleeding) and areas 6, 7 (got before)
        nor 2 (no blood).
        """

        self.c2.ooc('/deafen 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area6.background)
        self.c3.assert_ooc('You turned the lights on.')
        self.c3.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c3.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.blackout_background, over=True)

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        # self.c3.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background, over=True)

        ###
        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.area7.background)
        self.c0.assert_ooc('The lights were turned on.')
        self.c0.assert_ooc('You see {} is bleeding.'.format(self.c2_dname))
        self.c0.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c0.assert_ic('(Something catches your attention)', over=True)
        self.c2.assert_packet('BN', self.area7.background)
        self.c2.assert_ooc('You turned the lights on.')
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_dname))
        self.c2.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c2.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.blackout_background, over=True)

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        # self.c0.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.')
        self.c2.assert_ooc('(X) You see {} is bleeding.'.format(self.c0_dname)) # STAFF!
        self.c2.assert_ooc('(X) You spot a blood trail leading to the {}.' # STAFF!
                           .format(self.a6_name), over=True)
        # self.c2.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background, over=True)

        ###
        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You feel a light switch was flipped.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You feel a light switch was flipped.', over=True)
        # self.c3.assert_ooc('You smell blood.', over=True) # NO, DIDNT CHANGE SMELLING

        ###
        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_no_ooc()

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You feel a light switch was flipped.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You feel a light switch was flipped.', over=True)

    def test_04_deafarrival(self):
        """
        Situation: Same as test_01, but C4 is now only deaf.
        C4 gets visual cues for all areas.
        """

        self.c2.ooc('/blind 4')
        self.c1.discard_all()
        self.c2.discard_all()
        self.c4.discard_all()

        self.c4.move_area(6, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area6.background)
        self.c3.assert_ooc('You turned the lights on.')
        self.c3.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c3.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.area6.background)
        self.c4.assert_ooc('The lights were turned on.')
        self.c4.assert_ooc('You see {} is bleeding.'.format(self.c3_dname))
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a4_name, self.a7_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        # self.c3.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('The lights were turned off.', over=True)

        ###
        self.c4.move_area(7, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.area7.background)
        self.c0.assert_ooc('The lights were turned on.')
        self.c0.assert_ooc('You see {} is bleeding.'.format(self.c2_dname))
        self.c0.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c0.assert_ic('(Something catches your attention)', over=True)
        self.c2.assert_packet('BN', self.area7.background)
        self.c2.assert_ooc('You turned the lights on.')
        self.c2.assert_ooc('You see {} is bleeding.'.format(self.c0_dname))
        self.c2.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c2.assert_ic('(Something catches your attention)', over=True)
        self.c4.assert_packet('BN', self.area7.background)
        self.c4.assert_ooc('The lights were turned on.')
        self.c4.assert_ooc('You see {} and {} are bleeding.'
                           .format(*sorted([self.c0_dname, self.c2_dname])))
        self.c4.assert_ooc('You spot a blood trail leading to the {}.'
                           .format(self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        # self.c0.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.')
        self.c2.assert_ooc('(X) You see {} is bleeding.'.format(self.c0_dname)) # STAFF!
        self.c2.assert_ooc('(X) You spot a blood trail leading to the {}.' # STAFF!
                           .format(self.a6_name), over=True)
        # self.c2.assert_ooc('You hear faint drops of blood.', over=True) # NO, DIDNT CHANGE HEARING
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('The lights were turned off.', over=True)

        ###
        self.c4.move_area(4, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.')
        self.c4.assert_ooc('You smell blood.', ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.area4.background)
        self.c4.assert_ooc('You turned the lights on.')
        self.c4.assert_ooc('You spot a blood trail leading to the {}, the {} and the {}.'
                           .format(self.a0_name, self.a5_name, self.a6_name), ooc_over=True)
        self.c4.assert_ic('(Something catches your attention)', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You turned the lights off.', over=True)
        # self.c4.assert_ooc('You smell blood.', over=True) # NO, DIDNT CHANGE SMELLING

        ###
        self.c4.move_area(2, discard_trivial=True)
        self.c4.assert_ooc('You enter a pitch dark room.', over=True)

        self.c4.ooc('/lights on')
        self.c4.assert_packet('BN', self.area2.background)
        self.c4.assert_ooc('You turned the lights on.', over=True)

        self.c4.ooc('/lights off')
        self.c4.assert_packet('BN', self.blackout_background)
        self.c4.assert_ooc('You turned the lights off.', over=True)
