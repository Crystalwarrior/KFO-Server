from .structures import _TestSituation5Mc1Gc2

"""
This class is unable to test the timing for poison (it could, but it would make the test cases run
a lot longer). It will just test that the poison is applied and the output messages, not that
poison effect is applied.
It is able however to test that cure is applied, as the test does not have a time aspect.
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

        # Wrong number of arguments
        self.c1.ooc('/poison 1')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 3 arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/poison b d g 0 10')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 3 arguments.', over=True)
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

        self.c1.ooc('/poison 0 dgbD 10')
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
        self.c2.assert_ooc('(X) {} [{}] poisoned {} with the following effects ({}): '
                           '\r\n*Blindness: acts in 1:20.'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_03_multiplepoisons(self):
        """
        Situation: C1 poisons C0 with deafness and gagged in the same command. C2 gets notified.
        """

        self.c1.ooc('/poison 0 Dg 20')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.', over=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} [{}] poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: acts in 20 seconds.'
                           '\r\n*Gagged: acts in 20 seconds.'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_04_overridewithshorter(self):
        """
        Situation: C1 poisons C0 with deafness that triggers before the currently existing deafness
        effect. This effect gets overwritten. C2 gets notified as staff.
        """

        self.c1.ooc('/poison 0 D 10')
        self.c0.assert_ooc('You were poisoned. The following effects will apply shortly: '
                           '\r\n*Deafness: now acts in 10 seconds.', over=True)
        self.c1.assert_ooc('You poisoned {} with the following effects: '
                           '\r\n*Deafness: now acts in 10 seconds.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} [{}] poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: now acts in 10 seconds.'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
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
        self.c2.assert_ooc('(X) {} [{}] poisoned {} with the following effects ({}): '
                           '\r\n*Deafness: still acts in '
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id),
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
        self.c2.assert_ooc('(X) {} [{}] poisoned {} with the following effects ({}): '
                           '\r\n*Blindness: now acts in 50 seconds.'
                           '\r\n*Gagged: still acts in '
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id),
                           over=True, allow_partial_match=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_07_selfpoison(self):
        """
        Situation: C2 poisons themselves. C1 gets notified.
        """

        self.c2.ooc('/poison 2 Gd 30')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('(X) {} [{}] poisoned themselves with the following effects ({}): '
                           '\r\n*Deafness: acts in 30 seconds.'
                           '\r\n*Gagged: acts in 30 seconds.'
                           .format(self.c2_dname, 2, self.c2.area.id), over=True)
        self.c2.assert_ooc('You poisoned yourself with the following effects: '
                           '\r\n*Deafness: acts in 30 seconds.'
                           '\r\n*Gagged: acts in 30 seconds.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

class TestPoisonCure_02_Cure(_TestPoisonCure):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /cure incorrectly.
        """

        # Not staff
        self.c0.ooc('/cure 1 bdg')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        # Wrong number of arguments
        self.c1.ooc('/cure 1')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 2 arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/cure 1 b D')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 2 arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        # Invalid client ID
        self.c1.ooc('/cure bdg 0')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('`bdg` does not look like a valid client ID.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/cure 5 bdg')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('No targets found.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        # Invalid effect names (currently accepts b, d, or g)
        self.c1.ooc('/cure 0 bde')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Invalid effect letter `{}`.'.format('e'), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/cure 0 dgbd')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Effect list cannot contained repeated characters.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/cure 0 dgbD')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Effect list cannot contained repeated characters.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_02_cure(self):
        """
        Situation: C1 poisons C0 with blindness. C1 then cures C0 of blindness. C2 is notified.
        """

        self.c1.ooc('/poison 0 b 10')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/cure 0 b')
        self.c0.assert_ooc('You were cured of the effect `Blindness`.', ooc_over=True)
        # Changing blindness sends you the background, even if not needed
        self.c0.assert_packet('BN', None, over=True)
        self.c1.assert_ooc('You cured {} of the effect `Blindness`.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} [{}] cured {} of the effect `Blindness` ({}).'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assertFalse(self.c0.is_blind)
        self.assertFalse(self.c0.is_deaf)
        self.assertFalse(self.c0.is_gagged)
        self.assertFalse(self.c0.is_blind)

    def test_03_multiplecures(self):
        """
        Situation: C1 cures C0 of deafness and gagged, where C0 was not poisoned or under the
        influence of either. C2 gets notified.
        """

        self.assertFalse(self.c0.is_blind)
        self.c1.ooc('/cure 0 Gd')
        self.c0.assert_ooc('You were cured of the effect `Deafness`.')
        self.c0.assert_ooc('You were cured of the effect `Gagged`.', over=True)
        self.c1.assert_ooc('You cured {} of the effect `Deafness`.'
                           .format(self.c0_dname))
        self.c1.assert_ooc('You cured {} of the effect `Gagged`.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} [{}] cured {} of the effect `Deafness` ({}).'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id))
        self.c2.assert_ooc('(X) {} [{}] cured {} of the effect `Gagged` ({}).'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assertFalse(self.c0.is_blind)
        self.assertFalse(self.c0.is_deaf)
        self.assertFalse(self.c0.is_gagged)

    def test_04_cureremoveseffect(self):
        """
        Situation: C0 is made blind, deafened and gagged manually. C1 cures C0 of deafness and
        gagged but not blind. C2 gets notified.
        """

        self.c0.is_blind = True
        self.c0.is_deaf = True
        self.c0.is_gagged = True

        self.c1.ooc('/cure 0 dg')
        self.c0.assert_ooc('You were cured of the effect `Deafness`.')
        self.c0.assert_ooc('You were cured of the effect `Gagged`.', over=True)
        self.c1.assert_ooc('You cured {} of the effect `Deafness`.'
                           .format(self.c0_dname))
        self.c1.assert_ooc('You cured {} of the effect `Gagged`.'
                           .format(self.c0_dname), over=True)
        self.c2.assert_ooc('(X) {} [{}] cured {} of the effect `Deafness` ({}).'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id))
        self.c2.assert_ooc('(X) {} [{}] cured {} of the effect `Gagged` ({}).'
                           .format(self.c1_dname, 1, self.c0_dname, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assertTrue(self.c0.is_blind)
        self.assertFalse(self.c0.is_deaf)
        self.assertFalse(self.c0.is_gagged)

    def test_05_cureself(self):
        """
        Situation: C1 is made blind, deafened and gagged manually. C1 cures themselves of deafness
        and blindness but not gagged. C2 gets notified.
        """

        self.c1.is_blind = True
        self.c1.is_deaf = True
        self.c1.is_gagged = True

        self.c1.ooc('/cure 1 BD')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You cured yourself of the effect `Blindness`.')
        # Changing blindness sends you the background
        self.c1.assert_packet('BN', None)
        self.c1.assert_ooc('You cured yourself of the effect `Deafness`.', over=True)
        self.c2.assert_ooc('(X) {} [{}] cured themselves of the effect `Blindness` ({}).'
                           .format(self.c1_dname, 1, self.c1.area.id))
        self.c2.assert_ooc('(X) {} [{}] cured themselves of the effect `Deafness` ({}).'
                           .format(self.c1_dname, 1, self.c1.area.id), over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.assertFalse(self.c1.is_blind)
        self.assertFalse(self.c1.is_deaf)
        self.assertTrue(self.c1.is_gagged)
