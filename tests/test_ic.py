from .structures import _TestSituation4Mc1Gc2

class _TestIC(_TestSituation4Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(5)
        cls.c0_cname = cls.c0.get_char_name()
        cls.c1_cname = cls.c1.get_char_name()
        cls.c2_cname = cls.c2.get_char_name()
        cls.c3_cname = cls.c3.get_char_name()

class TestIC_01_Basic(_TestIC):
    def test_01_itworks(self):
        """
        Situation: Clients try to send messages/commands with invalid usernames.
        """
        self.c1.sic('Hello world.')
        self.c0.assert_received_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c1.assert_received_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Hello you.')
        self.c0.assert_received_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c1.assert_received_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c3.sic('Hello world.')
        self.c3.assert_received_ic('Hello world.', folder=self.c3_cname, over=True)
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_no_ic()