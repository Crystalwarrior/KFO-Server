from .structures import _TestSituation4Mc12

class TestZZZNoDebug_01_Basic(_TestSituation4Mc12):
    def test_01_noprintpackets(self):
        """
        Situation: Make sure server does not print packets
        """

        self.assertFalse(self.server.print_packets,
                         'Expected the server not print packets, found it did.')

    def test_02_noexec(self):
        """
        Situation: Make sure server disallows /exec
        """

        # Disallowed from a non-logged in client
        self.c0.ooc('/exec 1+1')
        self.c0.assert_no_packets()

        # Disallowed for a mod
        self.c1.ooc('/exec Hi')
        self.c1.assert_no_packets()
