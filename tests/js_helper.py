from __future__ import unicode_literals

import sys
from math import isnan

from . import helper
from .helper import MockXPI
from validator.errorbundler import ErrorBundle
from validator.outputhandlers.shellcolors import OutputHandler
import validator.testcases.content
import validator.testcases.scripting


def is_nan(val):
    """Return true if `val` is a float with a NaN value."""
    return isinstance(val, float) and isnan(val)


def _do_test(path):
    'Performs a test on a JS file'

    script = open(path).read()
    return _do_test_raw(script, path)


def _do_test_raw(script, path='foo.js', bootstrap=False, ignore_pollution=True,
                 detected_type=None, jetpack=False, instant=True):
    """Perform a test on a JS file."""

    err = ErrorBundle(instant=instant)
    if jetpack:
        err.metadata['is_jetpack'] = True

    err.handler = OutputHandler(sys.stdout, True)
    err.supported_versions = {}
    if bootstrap:
        err.save_resource('em:bootstrap', True)
    if detected_type:
        err.detected_type = detected_type

    validator.testcases.content._process_file(
        err, MockXPI(), path, script, path.lower(), not ignore_pollution)
    if err.final_context is not None:
        print 'CONTEXT', repr(err.final_context.keys())

    return err


def _do_real_test_raw(script, path='foo.js', versions=None, detected_type=None,
                      metadata=None, resources=None, jetpack=False):
    """Perform a JS test using a non-mock bundler."""

    err = ErrorBundle(for_appversions=versions or {})
    if detected_type:
        err.detected_type = detected_type
    if metadata is not None:
        err.metadata = metadata
    if resources is not None:
        err.resources = resources
    if jetpack:
        err.metadata['is_jetpack'] = True

    validator.testcases.content._process_file(err, MockXPI(), path, script,
                                              path.lower())
    return err


def _get_var(err, name):
    return err.final_context.data[name].as_primitive()


def _do_test_scope(script, vars):
    """Test the final scope of a script against a set of variables."""
    scope = _do_test_raw(script)
    for var, value in vars.items():
        print 'Testing %s' % var
        var_val = _get_var(scope, var)
        if is_nan(value):
            assert is_nan(var_val)
            continue
        if isinstance(var_val, float):
            var_val *= 100000
            var_val = round(var_val)
            var_val /= 100000

        assert var_val == value


class TestCase(helper.TestCase):
    """A TestCase object with specialized functions for JS testing."""

    def setup_method(self, method):
        self.file_path = 'foo.js'
        self.final_context = None
        super(TestCase, self).setup_method(method)

    def run_script_from_file(self, path):
        """
        Run the standard set of JS engine tests on a script found at the
        location in `path`.
        """
        with open(path) as script_file:
            return self.run_script(script_file.read())

    def run_script(self, script, expose_pollution=False, bootstrap=False):
        """
        Run the standard set of JS engine tests on the script passed via
        `script`.
        """
        if self.err.supported_versions is None:
            self.err.supported_versions = {}
        if bootstrap:
            self.err.save_resource('em:bootstrap', 'true')

        if '\n' in script:
            dashes = '-' * 30
            print (' {dashes} Running Script {dashes}\n'
                   '{script}\n'
                   ' {dashes} -------------- {dashes}'.format(**locals()))
        else:
            print 'Running script: `{0}`'.format(script)

        validator.testcases.content._process_file(self.err, MockXPI(),
                                                  self.file_path, script,
                                                  self.file_path.lower(),
                                                  expose_pollution)
        if self.err.final_context is not None:
            print 'CONTEXT', repr(self.err.final_context.keys())
            self.final_context = self.err.final_context

    def get_wrapper(self, name):
        """Return the wrapper of a variable from the final script context."""
        __tracebackhide__ = True

        assert name in self.final_context.data, (
            'Expected variable %r not in final context' % name)
        return self.final_context.data[name]

    def get_value(self, name):
        """Return the wrapper of a variable from the final script context."""
        __tracebackhide__ = True

        return self.get_wrapper(name).value

    def get_var(self, name):
        """
        Return the value of a variable from the final script context.
        """
        __tracebackhide__ = True

        return self.get_wrapper(name).as_primitive()

    def assert_var_eq(self, name, value):
        """
        Assert that the value of a variable from the final script context
        contains the value specified.
        """
        assert self.get_var(name) == value
