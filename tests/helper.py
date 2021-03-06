from __future__ import unicode_literals

import collections
import itertools
import re
import sys
import pprint
import string

import pytest
from mock import sentinel

from validator.submain import populate_chrome_manifest
from validator.rdf import RDFParser
from validator.xpi import XPIManager
from validator.errorbundler import ErrorBundle
from validator.outputhandlers.shellcolors import OutputHandler
import validator.testcases.regex as regex


def pformat(obj, **kw):
    """A wrapper around `pprint.pformat` which adds extra indentation to
    each line."""
    return re.sub('^', '    ', pprint.pformat(obj, **kw), flags=re.M)


class Formatter(string.Formatter):
    """A custom formatter for our error messages, which supports pretty
    printing message values in a user-readable way."""

    def convert_field(self, value, conversion):
        if conversion == 'p':
            if isinstance(value, (list, tuple)):
                return '\n\n'.join(map(pformat, value))
            return pformat(value)

        return super(Formatter, self).convert_field(value, conversion)

format = Formatter().format


def _do_test(path, test, failure=True,
             require_install=False, set_type=0,
             listed=False, xpi_mode='r'):

    package_data = open(path, 'rb')
    package = XPIManager(package_data, mode=xpi_mode, name=path)
    err = ErrorBundle()
    if listed:
        err.save_resource('listed', True)

    # Populate in the dependencies.
    if set_type:
        err.detected_type = set_type
    if require_install:
        err.save_resource('has_install_rdf', True)
        rdf_data = package.read('install.rdf')
        install_rdf = RDFParser(err, rdf_data)
        err.save_resource('install_rdf', install_rdf)

    populate_chrome_manifest(err, package)

    test(err, package)

    print err.print_summary(verbose=True)

    if failure:
        assert err.failed()
    else:
        assert not err.failed()

    return err


class Matcher(object):
    def __init__(self, value=None):
        self.value = value

    def __eq__(self, other):
        return other is not sentinel.MISSING and self.eq(other)

    def __repr__(self):
        return '<%s(%r)>' % (self.__class__.__name__, self.value)


class Exists(Matcher):
    def eq(self, other):
        return other is not None


class NonEmpty(Matcher):
    def eq(self, other):
        return bool(other)


class Contains(Matcher):
    def eq(self, other):
        return self.value in other


class Matches(Matcher):
    def eq(self, other):
        if isinstance(other, (list, tuple)):
            return any(re.search(self.value, val)
                       for val in other)
        return bool(re.search(self.value, other))


class TestCase(object):
    # Message IDs which are expected to have no context.
    NO_CONTEXT_WHITELIST = {
        ('fake', 'test', 'message'),
        ('foo', 'bar', 'quux'),
        ('testcases_content', 'packed_js', 'too_much_js'),
    }

    def setup_method(self, method):
        self.is_jetpack = False
        self.is_bootstrapped = False
        self.detected_type = None
        self.listed = True
        self._skip_sanity_check = False
        self.setup_err()

    def setup_err(self, for_appversions=None, instant=False):
        """
        Instantiate the error bundle object. Use the `instant` parameter to
        have it output errors as they're generated. `for_appversions` may be
        set to target the test cases at a specific Gecko version range.

        An existing error bundle will be overwritten with a fresh one that has
        the state that the test case was setup with.
        """
        self.err = ErrorBundle(instant=instant,
                               for_appversions=for_appversions or {},
                               listed=self.listed)
        self.err.handler = OutputHandler(sys.stdout, True)

        if self.is_jetpack:
            self.err.metadata['is_jetpack'] = True
        if self.is_bootstrapped:
            self.err.save_resource('em:bootstrap', True)
        if self.detected_type is not None:
            self.err.detected_Type = self.detected_type

    def all_messages(self):
        """Iterates over all messages in our error bundle."""
        return itertools.chain(self.err.notices, self.err.warnings,
                               self.err.errors)

    def check_sanity(self):
        """Checks the sanity of our error bundle. At the moment, this means
        making sure that all messages have context information."""

        if self._skip_sanity_check:
            return

        for msg in self.all_messages():
            if msg['id'] in self.NO_CONTEXT_WHITELIST:
                continue

            assert msg['file'], format('Message missing file:\n\n{!p}', msg)

            assert msg['line'], format('Message missing line:\n\n{!p}', msg)

            assert msg['context'], format('Message missing context:\n\n{!p}',
                                          msg)

    def skip_sanity_check(self):
        """Skip the usual sanity checks. Probably not for a good reason."""
        self._skip_sanity_check = True

    def assert_failed(self, with_errors=False, with_warnings=None):
        """
        Asserts that the error bundle has registered a failure. If
        `with_warnings` is any true value, or `None`, a warning is
        considered a failure.

        `with_warnings` or `with_errors` may be any of the following:

        * True: Messages of this type must be present.
        * False: Messages of this type must not be present.
        * None: Messages of this type may or may not be present.
        * Iterable of dicts: For dict returned by the iterator, at least
        one message must have a matching item for every key/value pair in the
        dict.
        """
        __tracebackhide__ = True

        assert self.err.failed(
            fail_on_warnings=with_warnings or with_warnings is None), \
            'Test did not fail; failure was expected.'

        def test_messages(type_, expected):
            __tracebackhide__ = True

            messages = getattr(self.err, type_)

            if isinstance(expected, collections.Iterable):
                self.match_messages(messages, expected)
            elif expected:
                assert messages, 'Expected %s.' % type_
            elif expected is not None:
                assert not messages, format(
                    'Tests found unexpected {0}: {1!p}', type_, messages)

        test_messages('errors', with_errors)
        test_messages('warnings', with_warnings)

        self.check_sanity()

    def message_keys(self, messages, keys):
        """Return a new dict containing only the keys in `keys`, for each
        message in `messages`."""
        return [{key: msg[key]
                 for key in msg.viewkeys() & keys}
                for msg in messages]

    def match_messages(self, messages, expected_messages, exhaustive=False,
                       expect_match=True):
        """Check that every message dict in `expected_messages` has a matching
        message in `messages`.

        If `exhaustive` is true, each expected message must match only
        one reported message, and no other messages may be present."""
        __tracebackhide__ = True

        # Make a copy we can destructively alter.
        orig_messages = messages
        messages = list(messages)

        def match_message(message, expected):
            """Return true if every item in the `expected` dict has a matching
            item in `message`."""
            return all(message.get(key, sentinel.MISSING) == value
                       for key, value in expected.iteritems())

        def find_message(expected):
            """Return true if any message in messages has all of the key/value
            pairs in props."""
            matched = [msg for msg in messages
                       if match_message(msg, expected)]

            for msg in matched:
                messages.remove(msg)
            return matched

        if expect_match:
            for expected in expected_messages:
                if not find_message(expected):
                    results = self.message_keys(orig_messages,
                                                expected.viewkeys())

                    pytest.fail(
                        format('Expected a message matching:\n\n{0!p}\n\n'
                               'but only got:\n\n{1!p}', expected, results))
        else:
            for expected in expected_messages:
                found = find_message(expected)
                if found:
                    results = self.message_keys(found, expected.viewkeys())

                    pytest.fail(
                        format('Expected no message matching:\n\n{0!p}\n\n'
                               'but got:\n\n{1!p}', expected, results))

        if exhaustive:
            assert not messages

    def assert_warnings(self, *warnings, **kw):
        """Check that a matching warning exists for each dict argument."""
        __tracebackhide__ = True

        if not warnings:
            raise TypeError('Expected at least one argument')

        exhaustive = kw.pop('exuahstive', False)

        self.match_messages(self.err.warnings, warnings, exhaustive=exhaustive)
        self.check_sanity()

    def assert_no_warnings(self, *warnings):
        """Check that a matching warning does not for any dict argument."""
        __tracebackhide__ = True

        if not warnings:
            raise TypeError('Expected at least one argument')

        self.match_messages(self.err.warnings, warnings, expect_match=False)
        self.check_sanity()

    def assert_notices(self):
        """Assert that notices have been generated during the validation
        process."""
        __tracebackhide__ = True

        assert self.err.notices, 'Notices were expected.'
        self.check_sanity()

    def assert_passes(self, warnings_pass=False):
        """Assert that no errors have been raised. If `warnings_pass` is True,
        also assert that there are no warnings.

        """
        __tracebackhide__ = True

        if not self.failed(fail_on_warnings=not warnings_pass):
            if warnings_pass:
                pytest.fail('Expected test to pass with warnings, but it did '
                            'not.')
            else:
                pytest.fail('Expected test to pass, but it did not.')

        self.check_sanity()

    def assert_silent(self):
        """
        Assert that no messages (errors, warnings, or notices) have been
        raised.
        """
        __tracebackhide__ = True

        for attr in 'errors', 'warnings', 'notices':
            messages = getattr(self.err, attr)
            if messages:
                pytest.fail(
                    format('Expected no {0}, but got these:\n\n{1!p}',
                           attr, messages))

        if any(self.err.compat_summary.values()):
            pytest.fail('Expected no compatibility summary values, '
                        'got these:\n\n{0}'
                        .format(pformat(self.err.compat_summary)))

    def assert_got_errid(self, errid):
        """
        Assert that a message with the given errid has been generated during
        the validation process.
        """
        __tracebackhide__ = True

        assert any(msg['id'] == errid for msg in
                   (self.err.errors + self.err.warnings + self.err.notices)), (
                       '%s was expected, but it was not found.' % repr(errid))
        self.check_sanity()


class RegexTestCase(TestCase):
    """
    A helper class to provide functions useful for performing tests against
    regex test scenarios.
    """

    def run_regex(self, input, is_js=None, filename=None):
        """Run the standard regex tests for non-JavaScript input."""
        if is_js:
            input = "'use strict';\n%s" % input
            regex.run_regex_tests(input, self.err, filename or 'foo.js')
        else:
            input = '<input onclick="%s" />' % input
            regex.run_regex_tests(input, self.err, filename or 'foo.html')

    def run_js_regex(self, input, filename='foo.js'):
        """Run the standard regex tests for JavaScript input."""
        regex.run_regex_tests(input, self.err, filename)


class MockZipFile:

    def namelist(self):
        return []


class MockXPI:

    def __init__(self, data=None, subpackage=False):
        if not data:
            data = {}
        self.zf = MockZipFile()
        self.data = data
        self.subpackage = subpackage
        self.filename = 'mock_xpi.xpi'

    def test(self):
        return True

    def info(self, name):
        return {'name_lower': name.lower(),
                'extension': name.lower().split('.')[-1]}

    def __iter__(self):
        def i():
            for name in self.data.keys():
                yield name
        return i()

    def __contains__(self, name):
        return name in self.data

    def read(self, name):
        return open(self.data[name]).read()


# Ugh.
class OtherMockXPI(object):

    def __init__(self, resources):
        self.resources = resources

    def read(self, name):
        if isinstance(self.resources[name], bool):
            return ''
        return self.resources[name]

    def __iter__(self):
        for name in self.resources.keys():
            yield name

    def __contains__(self, name):
        return name in self.resources


def chrome_manifest(string):
    """Returns a mock ChromeManifest object for the given string."""
    from validator.chromemanifest import ChromeManifest

    xpi = OtherMockXPI({
        'chrome.manifest': string
    })
    return ChromeManifest(xpi, 'chrome.manifest')
