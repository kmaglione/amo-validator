import os
import sys


def pytest_configure():
    path = os.path.abspath(os.path.basename(__file__))
    sys.path.insert(0, path)

    from validator import constants
    constants.IN_TESTS = True

    from validator import loader  # noqa
