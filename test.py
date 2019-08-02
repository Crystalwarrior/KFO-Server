"""
Run a collection of unit and integration tests on TsuserverDR.
It does not create any active accessible servers, but instead just merely
simulates client connections and actions.
"""

import unittest

if __name__ == '__main__':
    TEST_SUITE = unittest.TestLoader().discover('.')
    #unittest.TestResult(verbosity=1).run(TEST_SUITE)
    tester = unittest.TextTestRunner(verbosity=1, failfast=True)
    results = tester.run(TEST_SUITE)

    wrong = results.errors + results.failures
    if wrong:
        notification = 'TEST.PY FAILED'
        raise AssertionError(notification)