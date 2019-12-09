from .test_ooc import _TestOOC

class TestGlobal_01_ToggleGlobal(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /toggle_global incorrectly.
        """

        # Pass arguments
        self.c0.ooc('/toggle_global e')
        self.c0.assert_ooc('This command has no arguments.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertFalse(self.c0.muted_global)
        self.assertFalse(self.c1.muted_global)
        self.assertFalse(self.c2.muted_global)
        self.assertFalse(self.c3.muted_global)

    def test_02_muteglobal(self):
        """
        Situation: C0 mutes global messages.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.muted_global)
        self.assertFalse(self.c1.muted_global)
        self.assertFalse(self.c2.muted_global)
        self.assertFalse(self.c3.muted_global)

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will now receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertFalse(self.c0.muted_global)
        self.assertFalse(self.c1.muted_global)
        self.assertFalse(self.c2.muted_global)
        self.assertFalse(self.c3.muted_global)

    def test_03_deprecatedname(self):
        """
        Situation: Client uses /toggleglobal (deprecated name). It works... for now.
        """

        self.c0.ooc('/toggleglobal')
        self.c0.assert_ooc('This command is deprecated and pending removal in 4.3. Please use '
                           '/toggle_global next time.')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertTrue(self.c0.muted_global)
        self.assertFalse(self.c1.muted_global)
        self.assertFalse(self.c2.muted_global)
        self.assertFalse(self.c3.muted_global)

        self.c0.ooc('/toggleglobal')
        self.c0.assert_ooc('This command is deprecated and pending removal in 4.3. Please use '
                           '/toggle_global next time.')
        self.c0.assert_ooc('You will now receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()
        self.assertFalse(self.c0.muted_global)
        self.assertFalse(self.c1.muted_global)
        self.assertFalse(self.c2.muted_global)
        self.assertFalse(self.c3.muted_global)

class TestGlobal_02_Announce(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /announce incorrectly.
        """

        # Not mod
        self.c0.ooc('/announce Hello.')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/announce Hello.')
        self.c2.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Empty message
        self.c1.ooc('/announce')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You cannot send an empty announcement.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendannouncement(self):
        """
        Situation: Mods send announcements to entire server, twice. Everyone receives them.
        """

        self.c2.make_mod()

        self.c1.ooc('/announce Hi')
        self.c0.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c1.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c2.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c3.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)

        self.c2.ooc('/announce Hi')
        self.c0.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c1.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c2.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c3.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)

        self.c2.ooc('/announce Bye')
        self.c0.assert_ooc('=== Announcement ===\r\nBye\r\n==================', over=True)
        self.c1.assert_ooc('=== Announcement ===\r\nBye\r\n==================', over=True)
        self.c2.assert_ooc('=== Announcement ===\r\nBye\r\n==================', over=True)
        self.c3.assert_ooc('=== Announcement ===\r\nBye\r\n==================', over=True)

    def test_03_announcewhilemutedglobal(self):
        """
        Situation: C0 and C1 mute globals. C1 can use /announce, C0 and C1 receive /announce.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/toggle_global')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You will no longer receive global messages.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/announce Hi')
        self.c0.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c1.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c2.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c3.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)

        self.c2.ooc('/announce Hi')
        self.c0.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c1.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c2.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)
        self.c3.assert_ooc('=== Announcement ===\r\nHi\r\n==================', over=True)

class TestGlobal_03_Global(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /g incorrectly.
        """

        # No arguments
        self.c0.ooc('/g')
        self.c0.assert_ooc('You cannot send an empty message.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendglobal(self):
        """
        Situation: C0-4 send correct globals. They all
        receive one another's globals, even if they are in different areas.
        """

        for (i, c) in enumerate(self.clients[:4]):
            c.ooc('/g Hello.')
            name = c.name
            area = c.area.id
            for x in self.clients[:4]:
                x.assert_ooc('Hello.', username='<dollar>G[{}][{}]'.format(area, name), over=True)

    def test_03_globalwhilemutedglobal(self):
        """
        Situation: C0 and C2 attempt to communicate through globals, but fail as C0 has muted them.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c0.ooc('/g Hello C2.')
        self.c0.assert_ooc('You have the global chat muted.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/g Hello C0.')
        name = self.c2.name
        area = self.c2.area.id
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('Hello C0.', username='<dollar>G[{}][{}]'.format(area, name), over=True)
        self.c2.assert_ooc('Hello C0.', username='<dollar>G[{}][{}]'.format(area, name), over=True)
        self.c3.assert_ooc('Hello C0.', username='<dollar>G[{}][{}]'.format(area, name), over=True)

class TestGlobal_04_GlobalMod(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /gm incorrectly.
        """

        # Not mod
        self.c0.ooc('/gm Hello.')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/gm Hello.')
        self.c2.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Empty message
        self.c1.ooc('/gm')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You cannot send an empty message.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendgm(self):
        """
        Situation: Mods send global mod messages to entire server, twice. Everyone receives them.
        C1 is in area 0. C2 is in area 4.
        """

        self.c2.make_mod()

        self.c1.ooc('/gm Hi')
        self.c0.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(0, self.c1.name)), over=True)
        self.c1.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(0, self.c1.name)), over=True)
        self.c2.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(0, self.c1.name)), over=True)
        self.c3.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(0, self.c1.name)), over=True)

        self.c2.ooc('/gm Hi')
        self.c0.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(4, self.c2.name)), over=True)
        self.c1.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(4, self.c2.name)), over=True)
        self.c2.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(4, self.c2.name)), over=True)
        self.c3.assert_ooc('Hi', username=('<dollar>G[{}][{}][M]'
                                           .format(4, self.c2.name)), over=True)

        self.c2.ooc('/gm Bye')
        self.c0.assert_ooc('Bye', username=('<dollar>G[{}][{}][M]'
                                            .format(4, self.c2.name)), over=True)
        self.c1.assert_ooc('Bye', username=('<dollar>G[{}][{}][M]'
                                            .format(4, self.c2.name)), over=True)
        self.c2.assert_ooc('Bye', username=('<dollar>G[{}][{}][M]'
                                            .format(4, self.c2.name)), over=True)
        self.c3.assert_ooc('Bye', username=('<dollar>G[{}][{}][M]'
                                            .format(4, self.c2.name)), over=True)

    def test_03_gmwhilemutedglobal(self):
        """
        Situation: C0 and C1 mute globals. C1 cannot use /gm, C0 and C1 do not receive /gm.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/toggle_global')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You will no longer receive global messages.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/gm Hello C2.')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You have the global chat muted.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/gm Welcome.')
        name = self.c2.name
        area = self.c2.area.id
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Welcome.', username=('<dollar>G[{}][{}][M]'
                                                 .format(area, name)), over=True)
        self.c3.assert_ooc('Welcome.', username=('<dollar>G[{}][{}][M]'
                                                 .format(area, name)), over=True)

class TestGlobal_05_LocalMod(_TestOOC):
    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /gm incorrectly.
        """

        # Not mod
        self.c0.ooc('/lm Hello.')
        self.c0.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/lm Hello.')
        self.c2.assert_ooc('You must be authorized to do that.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        # Empty message
        self.c1.ooc('/lm')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You cannot send an empty message.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

    def test_02_sendlm(self):
        """
        Situation: Mods send global mod messages to their area, twice.
        For C1's messages, C0 and C1 receive them (area 0)
        For C2's message, only C2 receives it (area 4)
        """

        self.c2.make_mod()

        self.c1.ooc('/lm Hi')
        self.c0.assert_ooc('Hi', username='<dollar>H[MOD][{}]'.format(self.c1_dname), over=True)
        self.c1.assert_ooc('Hi', username='<dollar>H[MOD][{}]'.format(self.c1_dname), over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/lm Hi')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Hi', username='<dollar>H[MOD][{}]'.format(self.c2_dname), over=True)
        self.c3.assert_no_ooc()

        self.c2.ooc('/lm Bye')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Bye', username='<dollar>H[MOD][{}]'.format(self.c2_dname), over=True)
        self.c3.assert_no_ooc()

    def test_03_lmwhilemutedglobal(self):
        """
        Situation: C0 and C1 mute globals. C1 can use /lm, C0 and C0 and C1 receive /lm.
        """

        self.c0.ooc('/toggle_global')
        self.c0.assert_ooc('You will no longer receive global messages.', over=True)
        self.c1.assert_no_ooc()
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/toggle_global')
        self.c0.assert_no_ooc()
        self.c1.assert_ooc('You will no longer receive global messages.', over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c1.ooc('/lm Hello C0.')
        self.c0.assert_ooc('Hello C0.', username=('<dollar>H[MOD][{}]'
                                                  .format(self.c1_dname)), over=True)
        self.c1.assert_ooc('Hello C0.', username=('<dollar>H[MOD][{}]'
                                                  .format(self.c1_dname)), over=True)
        self.c2.assert_no_ooc()
        self.c3.assert_no_ooc()

        self.c2.ooc('/lm Welcome.')
        self.c0.assert_no_ooc()
        self.c1.assert_no_ooc()
        self.c2.assert_ooc('Welcome.', username=('<dollar>H[MOD][{}]'
                                                  .format(self.c2_dname)), over=True)
        self.c3.assert_no_ooc()
