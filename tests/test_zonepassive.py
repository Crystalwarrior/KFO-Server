from .structures import _TestSituation6Mc1Gc25

class _TestZonePassive(_TestSituation6Mc1Gc25):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c0.move_area(4)
        cls.c1.move_area(4)
        cls.c2.move_area(5)
        cls.c3.move_area(5)
        cls.c4.move_area(6)
        cls.c5.move_area(7)

class TestZonePassive_01_Global(_TestZonePassive):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_global incorrectly.
        """

        # No message
        self.c0.ooc('/zone_global')
        self.c0.assert_ooc('You cannot send an empty message.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

    def test_99_alias(self):
        """
        Situation: Clients attempt to use /zg, the alias of /zone_global.
        """

class TestZonePassive_02_List(_TestZonePassive):
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

class TestZonePassive_03_Unwatch(_TestZonePassive):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_unwatch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_unwatch')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # Parameters
        self.c1.ooc('/zone_unwatch 1000')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has no arguments.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZonePassive_04_Watch(_TestZonePassive):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_watch incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_watch 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_watch')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()