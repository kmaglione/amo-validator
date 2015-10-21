import fnmatch
import re

from validator import decorator
from validator.contextgenerator import ContextGenerator
from validator.constants import PACKAGE_LANGPACK

BAD_LINK = '(href|src)=["\'](?!chrome:\/\/)(([a-z]*:)?\/\/|data:)'


@decorator.register_test(tier=2, expected_type=PACKAGE_LANGPACK)
def test_langpack_manifest(err, xpi_package=None):
    """Tests the chrome.manifest files in the package for
    compliance with the standard language pack entries."""

    # Don't even both with the test(s) if there's no chrome.manifest.
    chrome = err.get_resource('chrome.manifest')
    if not chrome:
        return

    for entry in chrome.entries:
        type_ = entry['type']
        # Test to make sure that the entry's type is valid
        if type_ not in ('locale', 'override', 'manifest'):
            err.warning(('testcases_langpack',
                         'test_langpack_manifest',
                         'invalid_subject'),
                        'Invalid chrome.manifest entry type',
                        ['chrome.manifest files in language packs are only '
                         'allowed to contain items that are prefixed with '
                         "'locale', 'manifest', or 'override'. Other values "
                         'are not allowed.',
                         'Invalid type: %s' % type_],
                        filename=entry['filename'],
                        line=entry['line'],
                        context=entry['context'])

        if type_ == 'override':
            source = entry['args'][0]
            dest = entry['args'][1]

            pattern = 'chrome://*/locale/*'

            if not fnmatch.fnmatch(dest, pattern) or \
               not fnmatch.fnmatch(source, pattern):
                err.warning(('testcases_langpack',
                             'test_langpack_manifest',
                             'invalid_override'),
                            'Invalid chrome.manifest override value',
                            "'override' entry does not match '%s'" % pattern,
                            filename=entry['filename'],
                            line=entry['line'],
                            context=entry['context'])


# This function is called by content.py
def test_unsafe_html(err, filename, data):
    'Tests for unsafe HTML tags in language pack files.'

    context = ContextGenerator(data)

    unsafe_pttrn = re.compile('<(script|embed|object)', re.I)

    match = unsafe_pttrn.search(data)
    if match:
        line = context.get_line(match.start())
        err.warning(('testcases_langpack',
                     'test_unsafe_html',
                     'unsafe_content_html'),
                    'Unsafe HTML found in language pack files.',
                    'Language packs are not allowed to contain scripts, '
                    'embeds, or other executable code in the language '
                    'definition files.',
                    filename,
                    line=line,
                    context=context)

    remote_pttrn = re.compile(BAD_LINK, re.I)

    match = remote_pttrn.search(data)
    if match:
        line = context.get_line(match.start())
        err.warning(('testcases_langpack',
                     'test_unsafe_html',
                     'unsafe_content_link'),
                    'Unsafe remote resource found in language pack.',
                    'Language packs are not allowed to contain references to '
                    'remote resources.',
                    filename,
                    line=line,
                    context=context)
