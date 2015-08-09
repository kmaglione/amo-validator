"""Contains regular expression tests for compatibility runs."""
from validator.constants import BUGZILLA_BUG

from .generic import FileRegexTest


def get_compat_tests(err):
    """Return an appropriate compatibility tester for the given
    ErrorBundle."""

    if 'compat_regex_tests' not in err.resources:
        err.resources['compat_regex_tests'] = CompatRegexTest(
            err, COMPAT_REGEXPS)

    return err.resources['compat_regex_tests']


class CompatRegexTest(FileRegexTest):
    """Matches compatibility test regular expressions against the entire text
    files. Limits the tests it performs based on the application versions
    supported by a given ErrorBundle."""

    TEST_ID = ('testcases_regex', 'compat')

    def __init__(self, err, tests):
        patterns = self.get_patterns(err, tests)
        super(CompatRegexTest, self).__init__(patterns)

    def get_patterns(self, err, tests):
        """Return pattern-test pairs for each test set that matches the
        compatiblity range of our error bundle."""

        for compat_version, patterns in tests:
            if err.supports_version(compat_version):
                for key, pattern in patterns:
                    pattern.setdefault('for_appversions', compat_version)
                    pattern.setdefault('compatibility_type', 'error')
                    pattern.setdefault('tier', 5)
                    yield key, pattern


class CheapCompatBugPatternTests(object):
    def __init__(self, app_version_name, patterns):
        self.app_version_name = app_version_name
        self.patterns = patterns

    def __iter__(self):
        for pattern, bug in self.patterns.iteritems():
            yield (pattern,
                   {'warning': 'Flagged pattern matched: {0}'.format(pattern),
                    'description': (
                        'Code matching this pattern has been flagged as '
                        'compatibility issue for {app_version}. See {bug} for '
                        'more information.'.format(
                            app_version=self.app_version_name,
                            bug=BUGZILLA_BUG % bug))})


# Patterns are added to this list by other modules.
COMPAT_REGEXPS = []
