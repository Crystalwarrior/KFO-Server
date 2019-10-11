from .structures import _TestSituation6Mc1Gc25

class _TestZoneChanger(_TestSituation6Mc1Gc25):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c0.move_area(4)
        cls.c1.move_area(4)
        cls.c2.move_area(5)
        cls.c3.move_area(5)
        cls.c4.move_area(6)
        cls.c5.move_area(7)

class TestZoneChanger_01_Zone(_TestZoneChanger):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZoneChanger_02_Add(_TestZoneChanger):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_add incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_add 16')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_add')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZoneChanger_03_Remove(_TestZoneChanger):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_remove incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_remove 16')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_remove')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

class TestZoneChanger_04_Delete(_TestZoneChanger):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /zone_delete incorrectly.
        """

        # Non-staff
        self.c0.ooc('/zone_delete 1000')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()

        # No parameters
        self.c1.ooc('/zone_delete')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('This command has 1 argument.', over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.c5.assert_no_packets()