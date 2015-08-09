"""Contains regular expression tests which run against the parsed contents
of JavaScript string literals."""
import re

from validator.decorator import define_post_init

from .base import RegexTestBase


class JSRegexTest(RegexTestBase):
    """Matches regular expressions in JavaScript string literals."""

    TEST_ID = ('testcases_regex', 'string')

    def report_match(self, test, traverser, wrapper=None, **kw):
        msg = super(JSRegexTest, self).report_match(test, err=traverser, **kw)

        # Save the message to the JSValue of the string we're testing, so
        # later tests against the same string have access to it.
        if wrapper:
            wrapper.value.messages.append(msg)


def munge_filename(name):
    """Mangle a filename into a regular expression which will match that
    exact filename.

    Filenames ending in `/*` will also match sub-paths, in a platform-agnostic
    manner."""
    if name.endswith('/*'):
        return r'%s(?:[/\\].*)?' % re.escape(name[:-2])
    return re.escape(name)


# Filenames in the profile directory which should not be touched by add-ons.
PROFILE_FILENAMES = (
    'SiteSecurityServiceState.txt',
    'addons.json',
    'addons.sqlite',
    'blocklist.xml',
    'cert8.db',
    'compatibility.ini',
    'compreg.dat',
    'content-prefs.sqlite',
    'cookies.sqlite',
    'directoryLinks.json',
    'extensions.ini',
    'extensions.json',
    'extensions.sqlite',
    'formhistory.sqlite',
    'healthreport.sqlite',
    'httpDataUsage.dat',
    'key3.db',
    'localstore.rdf',
    'logins.json',
    'permissions.sqlite',
    'places.sqlite',
    'places.sqlite-shm',
    'places.sqlite-wal',
    'pluginreg.dat',
    'prefs.js',
    'safebrowsing/*',
    'search-metadata.json',
    'search.json',
    'search.sqlite',
    'searchplugins/*',
    'secmod.db',
    'sessionCheckpoints.json',
    'sessionstore.js',
    'signons.sqlite',
    'startupCache/*',
    'urlclassifier.pset',
    'urlclassifier3.sqlite',
    'urlclassifierkey3.txt',
    'user.js',
    'webappsstore.sqlite',
    'xpti.dat',
    'xulstore.json')
# These tests have proved too generic, and will need fine tuning:
#   "healthreport/*",
#   "storage/*",
#   "webapps/*",


STRING_REGEXPS = [
    # Unsafe files in the profile directory.
    (r'(?:^|[/\\])(?:%s)$' % '|'.join(map(munge_filename, PROFILE_FILENAMES)),
     {'err_id': ('testcases_regex', 'string', 'profile_filenames'),
      'warning': 'Reference to critical user profile data',
      'description': 'Critical files in the user profile should not be '
                     'directly accessed by add-ons. In many cases, an '
                     'equivalent API is available and should be used '
                     'instead.',
      'signing_help': 'Please avoid touching files in the user profile '
                      'which do not belong to your add-on. If the effects '
                      'that you are trying to achieve cannot be replicated '
                      'with a built-in API, we strongly encourage you to '
                      'remove this functionality.',
      'signing_severity': 'low'}),

    # References to the obsolete extension manager API.
    (('@mozilla.org/extensions/manager;1', 'em-action-requested'),
     {'warning': 'Obsolete Extension Manager API',
      'description': 'The old Extension Manager API is not available in any '
                     'remotely modern version of Firefox and should not be '
                     'referenced in any code.'}),
]


@define_post_init
def string_tester():
    return JSRegexTest(STRING_REGEXPS)


def validate_string(*args, **kw):
    return string_tester.test(*args, **kw)
