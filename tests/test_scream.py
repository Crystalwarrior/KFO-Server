from .test_ooc import _TestOOC

class TestScream_01_Scream(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /scream incorrectly.
        """

        # Empty message
        self.c1.ooc('/scream')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You cannot send an empty message.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_nonstaffscream(self):
        """
        Situation: C0 and C3, non-staff members, scream
        """

        # Assumptions
        # self.area0.scream_range = set([self.area1.name])    C0, C1 here
        # self.area4.scream_range = set()                     C2 here
        self.area5.scream_range = set([self.area0.name])    # C3 here

        # C0 (non-staff) screams
        self.c0.ooc('/scream Hi')
        self.c0.assert_ooc('You screamed "Hi".', ooc_over=True)
        self.c0.assert_ic('Hi', cid=0, pos=self.c0.pos, showname=self.c0.showname, over=True)
        self.c1.assert_ooc('(X) {} [{}] screamed "Hi" ({}).'
                           .format(self.c0_dname, 0, 0), ooc_over=True)
        self.c1.assert_ic('Hi', over=True)
        self.c2.assert_ooc('(X) {} [{}] screamed "Hi" ({}).'
                           .format(self.c0_dname, 0, 0), over=True)
        self.c2.assert_no_ic() # C2 is not in scream range
        self.c3.assert_no_packets() # C3 is not in scream range

        self.c3.ooc('/scream Hu')
        self.c0.assert_ooc('You heard {} scream nearby.'.format(self.c3_dname), ooc_over=True)
        self.c0.assert_ic('Hu', showname=self.c3.showname,
                          over=True) # C0 IS in scream range (compare to previous situation)
        self.c1.assert_ooc('(X) {} [{}] screamed "Hu" ({}).'
                           .format(self.c3_dname, 3, 5), ooc_over=True)
        self.c1.assert_ic('Hu', showname=self.c3.showname,
                          over=True) # C1 IS in scream range (compare to previous situation)
        self.c2.assert_ooc('(X) {} [{}] screamed "Hu" ({}).'
                           .format(self.c3_dname, 3, 5), over=True)
        self.c2.assert_no_ic() # C2 is not in scream range
        self.c3.assert_ooc('You screamed "Hu".', ooc_over=True)
        self.c3.assert_ic('Hu', cid=3, pos=self.c3.pos, showname=self.c3.showname, over=True)

    def test_03_staffscream(self):
        """
        Situation: C1 and C2, staff members, scream.
        """

        # C1 (staff) screams
        self.c1.ooc('/scream Ha')
        self.c0.assert_ooc('You heard {} scream nearby.'.format(self.c1_dname), ooc_over=True)
        self.c0.assert_ic('Ha', showname=self.c1.showname, over=True)
        self.c1.assert_ooc('You screamed "Ha".', ooc_over=True)
        self.c1.assert_ic('Ha', cid=1, pos=self.c1.pos, showname=self.c1.showname, over=True)
        self.c2.assert_ooc('(X) {} [{}] screamed "Ha" ({}).'.format(self.c1_dname, 1, 0),
                           over=True)
        self.c2.assert_no_ic() # C2 is not in scream range
        self.c3.assert_no_packets() # C3 is not in scream range

        # C2 (staff) screams
        self.c2.ooc('/scream He')
        self.c0.assert_no_packets() # C0 is not in scream range
        self.c1.assert_ooc('(X) {} [{}] screamed "He" ({}).'.format(self.c2_dname, 2, 4),
                           over=True)
        self.c1.assert_no_ic() # C1 is not in scream range
        self.c2.assert_ooc('You screamed "He".', ooc_over=True)
        self.c2.assert_ic('He', cid=2, pos=self.c2.pos, showname=self.c2.showname, over=True)
        self.c3.assert_no_packets() # C3 is not in scream range

    def test_04_screamwhilemutedglobal(self):
        """
        Situation: C0 and C1 mute globals. C1 cannot use /scream, C0 and C1 do not receive screams.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)

        self.c1.ooc('/toggle_global')
        self.c1.assert_ooc('You will no longer receive global messages.', over=True)

        self.c0.ooc('/scream I wanna scream')
        self.c0.assert_ooc('You have the global chat muted.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()

        self.c1.ooc('/scream and shout')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have the global chat muted.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()

        self.c3.ooc('/scream and let it all out')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('(X) {} [{}] screamed "and let it all out" ({}).'
                           .format(self.c3_dname, 3, 5), over=True)
        self.c3.assert_ooc('You screamed "and let it all out".', ooc_over=True)
        self.c3.assert_ic('and let it all out', cid=3, pos=self.c3.pos, showname=self.c3.showname,
                          over=True)
