from nose.tools import assert_raises

from tests.js_helper import TestCase, is_nan

from ..jstypes import JSArray, JSObject, Undefined
from ..traverser import Traverser


def assert_equivalent(a, b):
    """Assert that `a` is equivalent to `b`. The values are considered
    equivalent if either they are of the same type and either compare equal,
    or are both floats with NaN values."""
    assert (type(a) == type(b) or
            isinstance(a, basestring) and isinstance(b, basestring))
    assert a == b or is_nan(a) and is_nan(b)


class TestJSValue(TestCase):
    """Tests the functionality of the base-level JS Value type."""

    def setUp(self):
        super(TestJSValue, self).setUp()
        self.traverser = Traverser(self.err, filename='<stdin>')

    def wrap(self, val):
        return self.traverser.wrap(val).value

    def test_as_float(self):
        """Test that `.as_float()` correctly coerces values into floats."""

        def expect(orig, expected):
            """Coerce `orig` to a float, following JS rules, and assert that
            the result is equal to `expected`."""
            assert_equivalent(self.wrap(orig).as_float(), expected)

        with assert_raises(AssertionError):
            # Make sure we raise if the values are equal, but not of the same
            # type.
            expect(0, 0)

        # Values are always coerced to primitives prior to coercion to floats,
        # so only test valid return values of `.as_primitive()`

        # Numbers.
        expect(0, 0.)

        # Booleans.
        expect(False, 0.)
        expect(True, 1.)

        # `null`, `undefined`
        expect(None, 0.)
        expect(Undefined, float('nan'))

        # Strings.
        # White-space should first be stripped from a string, then
        # a null string should coerce to 0, a number-like string should
        # coerce to the appropriate float value, and everything else should
        # coerce to NaN.
        def string_expect(string, expected):
            expect(string, expected)
            expect(' {0} '.format(string), expected)
            expect('\r\n{0} \n'.format(string), expected)

        string_expect('', 0.)
        string_expect('1', 1.)
        string_expect('1.5', 1.5)
        string_expect('-1.5', -1.5)
        string_expect('+1.5', 1.5)

        string_expect('-', float('nan'))
        string_expect('+', float('nan'))

        string_expect('0xff', 255.)
        string_expect('-0xff', -255.)
        string_expect('+0xff', float('nan'))
        string_expect('0xff.ff', float('nan'))
        string_expect('0xfz', float('nan'))

        string_expect('0o70', 56.)
        string_expect('0o80', float('nan'))
        string_expect('-0o70', -56.)
        string_expect('+0o70', float('nan'))
        string_expect('0o70.70', float('nan'))

        string_expect('Infinity', float('inf'))
        string_expect('-Infinity', float('-inf'))

        string_expect('NaN', float('nan'))
        string_expect('foo', float('nan'))

    def test_as_int(self):
        """Test that `.as_int()` correctly coerces values into ints."""

        def expect(orig, expected):
            """Coerce `orig` to an int, following JS rules, and assert that
            the result is equal to `expected`."""
            assert_equivalent(self.wrap(orig).as_int(), expected)

        with assert_raises(AssertionError):
            # Make sure we raise if the values are equal, but not of the same
            # type.
            expect(0, 0.)

        # Values are coerced to float via `.as_float()` prior to being coerced
        # to an int, so only test valid outputs from `.as_float()`.
        expect(0., 0)
        expect(0.9, 0)
        expect(255, 255)
        expect(1.9, 1)
        expect(float('nan'), 0)
        expect(float('inf'), 0)
        expect(float('-inf'), 0)

    def test_as_bool(self):
        """Test that `.as_bool()` correctly coerces values into bools."""

        def expect(orig, expected):
            """Coerce `orig` to a bool, following JS rules, and assert that
            the result is equal to `expected`."""
            assert_equivalent(self.wrap(orig).as_bool(), expected)

        expect(True, True)
        expect(1, True)
        expect(12, True)
        expect(-12, True)
        expect(12., True)
        expect(-12., True)
        expect(float('inf'), True)
        expect(float('-inf'), True)
        expect(' ', True)
        expect('[object Object]', True)
        expect('0', True)
        expect('false', True)
        expect('NaN', True)

        expect(JSArray(), True)
        expect(JSObject(), True)

        expect(False, False)
        expect(+0, False)
        expect(-0, False)
        expect(+0.0, False)
        expect(-0.0, False)
        expect('', False)
        expect(None, False)
        expect(Undefined, False)
        expect(float('nan'), False)

    def test_as_str(self):
        """Test that `.as_str()` correctly coerces values into strings."""

        def expect(orig, expected):
            """Coerce `orig` to a string, following JS rules, and assert that
            the result is equal to `expected`."""
            assert_equivalent(self.wrap(orig).as_str(), expected)

        expect('foo', 'foo')

        expect(1.0, '1')
        expect(1, '1')
        expect(1.5, '1.5')

        expect(float('inf'), 'Infinity')
        expect(float('-inf'), '-Infinity')
        expect(float('nan'), 'NaN')

        expect(True, 'true')
        expect(False, 'false')

        expect(None, 'null')
        expect(Undefined, 'undefined')

        expect(JSObject(), u'[object Object]')
        expect([], u'')
        expect([1, 2], u'1,2')
        expect([1, JSObject()], u'1,[object Object]')

        # Make sure we don't explode when processing recursive arrays.
        ary = self.wrap([1, 2, 3])
        ary[1] = ary
        expect(ary, u'1,,3')
