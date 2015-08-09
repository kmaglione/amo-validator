"""Contains generic regular expression tests which run against the entire
contents of files."""
import os
import re

from validator.contextgenerator import ContextGenerator
from validator.decorator import define_post_init
from .base import RegexTestBase


class FileRegexTest(RegexTestBase):
    """Matches regular expressions in complete file texts, with filters
    for individual tests."""

    TEST_ID = ('testcases_regex', 'raw_file')

    # Extensions of files which are likely to contain JavaScript.
    JAVASCRIPT_EXTENSIONS = ('.js', '.jsm', '.htm', '.html', '.xhtml',
                             '.xul', '.xbl')

    DEFAULT_FILTER = {
        'is_javascript': True,
    }

    def test(self, string, err, filename, context=None):
        extension = os.path.splitext(filename)[1]
        filters = {'filename': filename,
                   'extension': extension,
                   'is_javascript': extension in self.JAVASCRIPT_EXTENSIONS,
                   'document': string}

        # Don't bother running tests unless some of our tests match the file.
        if any(self.check_filter(test, filters)
               for test in self.tests.itervalues()):

            if context is None:
                context = ContextGenerator(string)

            super(FileRegexTest, self).test(string, err=err, filters=filters,
                                            filename=filename, context=context)


def strip_whitespace(val):
    """Removes all white space from the given string or unicode value."""
    return re.sub(r'\s+', '', val)


FILE_REGEXPS = [
    # Access to Sync service modules which don't work well with extensions.
    (r'resource://services-sync',
     {'err_id': ('testcases_regex', 'file', 'sync-service'),
      'warning': 'Sync services objects are not intended to be re-used',
      'description': (
         'The Sync services objects are not intended to be re-used, and '
         'they often change in ways that break add-ons. It is strongly '
         'recommended that you do not rely on them.')}),

    # Modification of native object prototypes.
    # This really needs to be a code test, but that's surprisingly difficult
    # to achieve the way things are currently set up.
    (r'\b(?:String|Object|Number|Date|RegExp|Function|Boolean|Array|Iterator)'
     r'\.prototype(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*|\[[^\]]+\])\s*=',

     {'filter': lambda kw: (
         kw['is_javascript'] and not (kw['extension'] == '.jsm' or
                                      'EXPORTED_SYMBOLS' in kw['document'])),

      'err_id': ('testcases_regex', 'file', 'prototype-extension'),
      'warning': 'JavaScript native prototype extension',
      'description': 'Due to interoperability concerns, extensions may '
                     'not extend the prototypes of native objects when '
                     'running in a shared scope.'}),
]


@define_post_init
def file_tester():
    return FileRegexTest(FILE_REGEXPS)


def validate_file(*args, **kw):
    return file_tester.test(*args, **kw)
