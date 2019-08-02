"""
Run a collection of unit and integration tests on TsuserverDR.
It does not create any active accessible servers, but instead just merely
simulates client connections and actions.
"""

import unittest

if __name__ == '__main__':
    TEST_SUITE = unittest.TestLoader().discover('.')
    unittest.TextTestRunner(verbosity=1).run(TEST_SUITE)
