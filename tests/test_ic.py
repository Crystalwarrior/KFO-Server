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
    def test_01_areaencapsulation(self):
        """
        Situation: Clients try to send messages
        """

        self.c1.sic('Hello world.')
        self.c0.assert_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c1.assert_ic('Hello world.', folder=self.c1_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c0.sic('Hello you.')
        self.c0.assert_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c1.assert_ic('Hello you.', folder=self.c0_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_no_ic()

        self.c3.sic('Hello world.')
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_no_ic()
        self.c3.assert_ic('Hello world.', folder=self.c3_cname, over=True)

    def test_02_movetoarea(self):
        """
        Situation: C3 moves to C0's area and says hi in IC.
        """

        self.c3.move_area(self.c0.area.id)

        self.c3.sic('Hi there')
        self.c0.assert_ic('Hi there', folder=self.c3_cname, over=True)
        self.c1.assert_ic('Hi there', folder=self.c3_cname, over=True)
        self.c2.assert_no_ic()
        self.c3.assert_ic('Hi there', folder=self.c3_cname, over=True)

        self.c2.sic('Anyone in here?')
        self.c0.assert_no_ic()
        self.c1.assert_no_ic()
        self.c2.assert_ic('Anyone in here?', folder=self.c2_cname, over=True)
        self.c3.assert_no_ic()

    def test_03_repeatedmessages(self):
        """
        Situation: C2 attempts to send the exact same message with the same character. While they
        still receive the MS packet, they don't actually show the message in IC.
        """

        self.c2.sic('Anyone in here?')
        self.c2.assert_packet('MS', None, over=True)
        self.c2.assert_no_ic()