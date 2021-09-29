# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-21 Chrezm/Iuvee <thechrezm@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
Run a collection of unit and integration tests on TsuserverDR.
It does not create any active accessible servers, but instead just merely
simulates client connections and actions.
"""

import sys
import unittest

class NoSkipLogTextTestResult(unittest.TextTestResult):
    # I dont want "s" in my log
    def addSkip(self, test, reason):
        super(unittest.TextTestResult, self).addSkip(test, reason)
        if self.showAll:
            self.stream.writeln("skipped {0!r}".format(reason))
        elif self.dots:
            self.stream.flush()

class NoSkipLogTextTestRunner(unittest.TextTestRunner):
    resultclass = NoSkipLogTextTestResult

if __name__ == '__main__':
    if len(sys.argv) > 1:
        pattern = sys.argv[1]
    else:
        pattern = 'test*.py'

    TEST_SUITE = unittest.TestLoader().discover('.', pattern=pattern)
    tester = NoSkipLogTextTestRunner(verbosity=1, failfast=True)
    results = tester.run(TEST_SUITE)

    wrong = results.errors + results.failures
    if wrong:
        notification = 'TEST.PY FAILED'
        raise AssertionError(notification)
