from .structures import _TestSituation5Mc1Gc2

class _TestCharacters(_TestSituation5Mc1Gc2):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c2.move_area(4)
        cls.c3.move_area(4)
        cls.link1 = 'https://www.google.com'
        cls.link2 = 'https://www.example.com'

class TestCharacters_01_Files_Set(_TestCharacters):
    """
    Tests for /files_set.
    """

    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /files_set incorrectly.
        """

        # All uses of files_set are valid

    def test_02_nonemptyargument(self):
        """
        Situation: C0, who is not iniswapped and has no files set at the moment, uses /files_set
        with link1.
        """

        self.c0.ooc('/files_set {}'.format(self.link1))
        self.c0.assert_ooc('You have set the download link for the files of `{}` to {}'
                           .format(self.c0_dname, self.link1))
        self.c0.assert_ooc('Let others access them with /files {}'.format(0), over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

    def test_03_someoneelsenonemptyargument(self):
        """
        Situation: C1, who is not iniswapped and has no files set at the moment, uses /files_set
        with link2.
        """

        self.c1.ooc('/files_set {}'.format(self.link2))
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have set the download link for the files of `{}` to {}'
                           .format(self.c1_dname, self.link2))
        self.c1.assert_ooc('Let others access them with /files {}'.format(1), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual([self.c1_dname, self.link2], self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

    def test_04_resetsamenonemptyassomeneelse(self):
        """
        Situation: C0, who is not iniswapped and has files set at the moment, uses /files_set with
        link1, the same as C1.
        """

        self.c0.ooc('/files_set {}'.format(self.link1))
        self.c0.assert_ooc('You have set the download link for the files of `{}` to {}'
                           .format(self.c0_dname, self.link1))
        self.c0.assert_ooc('Let others access them with /files {}'.format(0), over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual([self.c1_dname, self.link2], self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

    def test_05_emptyargument(self):
        """
        Situation: C1 runs /files_set with no link, which clears their files download link.
        """

        self.c1.ooc('/files_set')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('You have removed the download link for the files of `{}`.'
                           .format(self.c1_dname), over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

    def test_06_iniswappedsetsfiles(self):
        """
        Situation: C4 iniswaps to Spam_HD and sets their files download link to link2.
        """

        self.c4.char_folder = 'Spam_HD'

        self.c4.ooc('/files_set {}'.format(self.link2))
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You have set the download link for the files of `{}` to {}'
                           .format(self.c4.char_folder, self.link2))
        self.c4.assert_ooc('Let others access them with /files {}'.format(4), over=True)
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual([self.c4.char_folder, self.link2], self.c4.files)

    def test_07_iniswappedremoves(self):
        """
        Situation: C4, who is iniswapped to Spam_HD, removes their download link.
        """

        self.c4.ooc('/files_set')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You have removed the download link for the files of `{}`.'
                           .format('Spam_HD'), over=True)
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

    def test_08_nofilesremoves(self):
        """
        Situation: C2, who has never run /files_set, and C4, who just ran /files_set to remove
        their download links. Both fail.
        """

        self.c2.ooc('/files_set')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You have not provided a download link for your files.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

        self.c4.ooc('/files_set')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_ooc('You have not provided a download link for your files.', over=True)
        self.assertEqual([self.c0_dname, self.link1], self.c0.files)
        self.assertEqual(None, self.c1.files)
        self.assertEqual(None, self.c2.files)
        self.assertEqual(None, self.c3.files)
        self.assertEqual(None, self.c4.files)

class TestCharacters_02_Files(_TestCharacters):
    """
    Tests for /files
    """

    def test_01_wrongarguments(self):
        """
        Situation: Clients attempt to use /files incorrectly.
        """

        # Invalid client ID
        self.c0.ooc('/files -1')
        self.c0.assert_ooc('No targets with identifier `-1` found.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_02_filesforplayerwithfiles(self):
        """
        Situation: C1 sets custom files. C0 obtains them.
        """

        self.c1.ooc('/files_set {}'.format(self.link1))
        self.c1.discard_all()

        self.c0.ooc('/files 1')
        self.c0.assert_ooc('Files set by client 1 for `{}`: {}'
                           .format(self.c1_dname, self.link1))
        self.c0.assert_ooc('Links are spoopy. Exercise caution when opening external links.',
                           over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()

    def test_03_filesetterchangesfilesandiniswap(self):
        """
        Situation: C1 changes characters, and iniswaps. C0 when doing /files 1 still obtains old
        link.
        """

        self.c1.old_char_folder = self.c1.char_folder
        self.c1.ooc('/switch {}'.format(self.server.config['spectator_name']))
        self.c1.discard_all()
        self.c1.char_folder = 'Spam_HD'

        self.c0.ooc('/files 1')
        self.c0.assert_ooc('Files set by client 1 for `{}`: {}'
                           .format(self.c1.old_char_folder, self.link1))
        self.c0.assert_ooc('Links are spoopy. Exercise caution when opening external links.',
                           over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()

    def test_04_filesforplayerwithnofiles(self):
        """
        Situation: C2 attempts to obtain files for C3, who has never set files.
        C1 removes their files, then C0 attempts to obtain C1's files.
        Both fail.
        """

        self.c2.ooc('/files 3')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('Client 3 has not provided a download link for their files.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c1.ooc('/files_set')
        self.c1.discard_all()

        self.c0.ooc('/files 1')
        self.c0.assert_ooc('Client 1 has not provided a download link for their files.', over=True)
        self.c1.assert_no_packets()
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

    def test_05_selffiles(self):
        """
        Situation: C1 does /files to obtain their own files. This succeeds.
        C2, who has no files, does /files to obtain their own files. This fails.
        """

        self.c1.ooc('/files_set {}'.format(self.link1))
        self.c1.discard_all()

        self.c1.ooc('/files')
        self.c0.assert_no_packets()
        self.c1.assert_ooc('Files set by yourself for `{}`: {}'
                           .format(self.c1.char_folder, self.link1))
        self.c1.assert_ooc('Links are spoopy. Exercise caution when opening external links.',
                           over=True)
        self.c2.assert_no_packets()
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()

        self.c2.ooc('/files')
        self.c0.assert_no_packets()
        self.c1.assert_no_packets()
        self.c2.assert_ooc('You have not provided a download link for your files.', over=True)
        self.c3.assert_no_packets()
        self.c4.assert_no_packets()


