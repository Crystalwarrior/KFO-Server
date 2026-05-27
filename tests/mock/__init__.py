"""Test utilities package.

Re-exports ``MockClient`` so tests can ``from tests.mock import MockClient``.
"""

from tests.mock.mockclient import MockClient

__all__ = ["MockClient"]
