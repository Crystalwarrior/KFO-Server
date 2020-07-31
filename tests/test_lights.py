from .structures import _TestSituation4Mc12

class _TestLights(_TestSituation4Mc12):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.blackout_background = cls.server.config['blackout_background']

    def assert_lights(self, yes, no):
        self.assert_property(yes, no, 'A', lambda a: a.lights)

class TestLights_01_Basic(_TestLights):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /lights incorrectly.
        """

        self.c0.ooc('/lights')
        self.c0.assert_ooc('You must specify either on or off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.assert_lights(1, 0)

        self.c0.ooc('/lights Yes')
        self.c0.assert_ooc('Expected on or off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.assert_lights(1, 0)

        self.c0.ooc('/lights on off')
        self.c0.assert_ooc('Expected on or off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.assert_lights(1, 0)

        self.c0.ooc('/lights off')
        self.c0.assert_ooc('The background of this area is locked.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.assert_lights(1, 0)

        self.c1.make_gm()
        self.c1.ooc('/lights off')
        self.c1.assert_ooc('The background of this area is locked.', over=True)
        self.c0.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c1.make_mod()
        self.assert_lights(1, 0)

        self.area4.has_lights = False
        self.c3.ooc('/lights off')
        self.c3.assert_ooc('This area has no lights to turn off or on.', over=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.assert_lights(1, 0)

        self.area4.has_lights = True

    def test_02_normielightsoffon(self):
        """
        Situation: C0 moves to area 5. C3 turns lights off and on in area 5.
        C2 as staff gets notification of who did, while C0 does not. C1 gets no notifications as
        not in the same area.
        """

        self.c0.move_area(4)

        self.c3.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('(X) {} [{}] turned the lights off.'
                           .format(self.c3_dname, 3), over=True)
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        self.assert_lights(1, {self.area4})

        self.c3.ooc('/lights on')
        self.c0.assert_packet('BN', self.area4.background)
        self.c0.assert_ooc('The lights were turned on.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.area4.background)
        self.c2.assert_ooc('(X) {} [{}] turned the lights on.'
                           .format(self.c3_dname, 3), over=True)
        self.c3.assert_packet('BN', self.area4.background)
        self.c3.assert_ooc('You turned the lights on.', over=True)
        self.assert_lights(1, 0)

    def test_03_stafflightsoffon(self):
        """
        Situation: C2 (GM) turns lights off and on in area 5. C0 and C3 only get notifications of
        lights being turned off and on, not by whom.
        """

        self.c0.move_area(4)

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.', over=True)
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('The lights were turned off.', over=True)
        self.assert_lights(1, {self.area4})

        self.c2.ooc('/lights on')
        self.c0.assert_packet('BN', self.area4.background)
        self.c0.assert_ooc('The lights were turned on.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.area4.background)
        self.c2.assert_ooc('You turned the lights on.', over=True)
        self.c3.assert_packet('BN', self.area4.background)
        self.c3.assert_ooc('The lights were turned on.', over=True)
        self.assert_lights(1, 0)

    def test_04_cannotdoubleofforon(self):
        """
        Situation: C3 attempts to turn lights on/off when they are already on/off.
        """

        self.c3.ooc('/lights on')
        self.c3.assert_ooc('The lights are already turned on.', over=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.assert_lights(1, 0)

        self.c3.ooc('/lights off')
        self.c0.discard_all()
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()
        self.assert_lights(1, {self.area4})

        self.c3.ooc('/lights off')
        self.c3.assert_ooc('The lights are already turned off.', over=True)
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.assert_lights(1, {self.area4})

    def test_05_differentplayersswitching(self):
        """
        Situation: Different players change the lights in the same area.
        """

        self.c0.ooc('/lights on')
        self.c0.assert_packet('BN', self.area4.background)
        self.c0.assert_ooc('You turned the lights on.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.area4.background)
        self.c2.assert_ooc('(X) {} [{}] turned the lights on.'
                           .format(self.c0_dname, 0), over=True)
        self.c3.assert_packet('BN', self.area4.background)
        self.c3.assert_ooc('The lights were turned on.', over=True)
        self.assert_lights(1, 0)

        self.c2.ooc('/lights off')
        self.c0.assert_packet('BN', self.blackout_background)
        self.c0.assert_ooc('The lights were turned off.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.blackout_background)
        self.c2.assert_ooc('You turned the lights off.', over=True)
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('The lights were turned off.', over=True)
        self.assert_lights(1, {self.area4})

        self.c3.ooc('/lights on')
        self.c0.assert_packet('BN', self.area4.background)
        self.c0.assert_ooc('The lights were turned on.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_packet('BN', self.area4.background)
        self.c2.assert_ooc('(X) {} [{}] turned the lights on.'
                           .format(self.c3_dname, 3), over=True)
        self.c3.assert_packet('BN', self.area4.background)
        self.c3.assert_ooc('You turned the lights on.', over=True)
        self.assert_lights(1, 0)

    def test_06_lightswitchcrusade(self):
        """
        Situation: Same player turns the lights off and on in different areas in some order.
        """

        self.c3.move_area(5)
        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        self.assert_lights(1, {self.area5})

        self.c3.move_area(6)
        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        self.assert_lights(1, {self.area5, self.area6})

        self.c3.move_area(5)
        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area5.background)
        self.c3.assert_ooc('You turned the lights on.', over=True)
        self.assert_lights(1, {self.area6})

        self.c3.move_area(7)
        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You turned the lights off.', over=True)
        self.assert_lights(1, {self.area7, self.area6})

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area7.background)
        self.c3.assert_ooc('You turned the lights on.', over=True)
        self.assert_lights(1, {self.area6})

        self.c3.move_area(6)
        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.area6.background)
        self.c3.assert_ooc('You turned the lights on.', over=True)
        self.assert_lights(1, 0)

class TestLights_02_Miscellaneous(_TestLights):
    def test_01_blindlights(self):
        """
        Situation: Blind player attempts to turn off lights that are already turned off. They turn
        them on. Then they attempt the same with on lights.
        """

        self.c1.ooc('/blind 3')
        self.c3.move_area(6)
        self.c1.discard_all()
        self.c2.discard_all()
        self.c3.discard_all()

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You hear a flicker.', over=True)
        self.assert_lights(1, {self.area6})

        self.c3.ooc('/lights off')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You hear a flicker.', over=True)
        self.assert_lights(1, 0)

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You hear a flicker.', over=True)
        self.assert_lights(1, {self.area6})

        self.c3.ooc('/lights on')
        self.c3.assert_packet('BN', self.blackout_background)
        self.c3.assert_ooc('You hear a flicker.', over=True)
        self.assert_lights(1, 0)
