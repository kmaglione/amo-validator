from __future__ import absolute_import, print_function, unicode_literals

import mock
import pytest

from tests.js_helper import is_nan

from ..jstypes import JSArray, JSContext, JSLiteral, JSObject, Undefined
from .test_traverser import BaseTestTraverser


parametrize = pytest.mark.parametrize


def assert_equivalent(a, b):
    """Assert that `a` is equivalent to `b`. The values are considered
    equivalent if either they are of the same type and either compare equal,
    or are both floats with NaN values."""
    __tracebackhide__ = True

    assert (type(a) == type(b) or
            isinstance(a, basestring) and isinstance(b, basestring))
    assert a == b or is_nan(a) and is_nan(b)


class TestJSValueCoercion(BaseTestTraverser):
    """Tests the functionality of type coercion in the base-level JSValue
    type."""

    def test_assert_equivalent(self):
        """Test that the assert_equivalent function works as expected."""

        with pytest.raises(AssertionError):
            # Make sure we raise if the values are equal, but not of the same
            # type.
            assert_equivalent(0., 0)

        assert_equivalent(0, 0)
        assert_equivalent(b'foo', u'foo')
        assert_equivalent(float('inf'), float('inf'))
        assert_equivalent(float('nan'), float('nan'))

    @parametrize('orig,expected', (
        # Values are always coerced to primitives prior to coercion to floats,
        # so only test valid return values of `.as_primitive()`

        # Numbers.
        (0, 0.),

        # Booleans.
        (False, 0.),
        (True, 1.),

        # `null`, `undefined`
        (None, 0.),
        (Undefined, float('nan')),
    ))
    def test_as_float(self, orig, expected):
        """Test that `.as_float()` correctly coerces values into floats."""

        # Coerce `orig` to a float, following JS rules, and assert that
        # the result is equal to `expected`."""

        assert_equivalent(self.wrap(orig).as_float(), expected)

    @parametrize('orig,expected', (
        ('', 0.),
        ('1', 1.),
        ('1.5', 1.5),
        ('-1.5', -1.5),
        ('+1.5', 1.5),
        ('.5', .5),
        ('-.5', -.5),
        ('+.5', .5),

        ('-', float('nan')),
        ('+', float('nan')),

        ('0xff', 255.),
        ('0XfF', 255.),
        ('-0xff', -255.),
        ('+0xff', float('nan')),
        ('0xff.ff', float('nan')),
        ('0xfz', float('nan')),

        ('0o70', 56.),
        ('0O70', 56.),
        ('0o80', float('nan')),
        ('-0o70', -56.),
        ('+0o70', float('nan')),
        ('0o70.70', float('nan')),

        ('Infinity', float('inf')),
        ('-Infinity', float('-inf')),

        ('infinity', float('nan')),
        ('-infinity', float('nan')),

        ('NaN', float('nan')),
        ('foo', float('nan')),
    ))
    def test_str_as_float(self, orig, expected):
        """Test that `.as_float()` correctly coerces string values into
        floats."""

        def expect(orig, expected):
            """Coerce `orig` to a float, following JS rules, and assert that
            the result is equal to `expected`."""
            __tracebackhide__ = True
            assert_equivalent(self.wrap(orig).as_float(), expected)

        # White-space should first be stripped from a string, then
        # a null string should coerce to 0, a number-like string should
        # coerce to the appropriate float value, and everything else should
        # coerce to NaN.

        expect(orig, expected)
        expect(' {0} '.format(orig), expected)
        expect('\r\n{0} \n'.format(orig), expected)

    @parametrize('orig,expected', (
        # Values are coerced to float via `.as_float()` prior to being coerced
        # to an int, so only test valid outputs from `.as_float()`.
        (0., 0),
        (0.9, 0),
        (255, 255),
        (1.9, 1),

        (float('nan'), 0),
        (float('inf'), 0),
        (float('-inf'), 0),
    ))
    def test_as_int(self, orig, expected):
        """Test that `.as_int()` correctly coerces values into ints."""

        # Coerce `orig` to an int, following JS rules, and assert that
        # the result is equal to `expected`."""
        assert_equivalent(self.wrap(orig).as_int(), expected)

    @parametrize('orig,expected', (
        (True, True),
        (1, True),
        (12, True),
        (-12, True),
        (12., True),
        (-12., True),
        (float('inf'), True),
        (float('-inf'), True),
        (' ', True),
        ('[object Object]', True),
        ('0', True),
        ('false', True),
        ('NaN', True),

        (JSArray(), True),
        (JSObject(), True),

        (False, False),
        (+0, False),
        (-0, False),
        (+0.0, False),
        (-0.0, False),
        ('', False),

        (None, False),
        (Undefined, False),
        (float('nan'), False),
    ))
    def test_as_bool(self, orig, expected):
        """Test that `.as_bool()` correctly coerces values into bools."""

        # Coerce `orig` to a bool, following JS rules, and assert that
        # the result is equal to `expected`."""

        assert self.wrap(orig).as_bool() == expected

    @parametrize('orig,expected', (
        ('foo', 'foo'),

        (1.0, '1'),
        (1, '1'),
        (1.5, '1.5'),

        (float('inf'), 'Infinity'),
        (float('-inf'), '-Infinity'),
        (float('nan'), 'NaN'),

        (True, 'true'),
        (False, 'false'),

        (None, 'null'),
        (Undefined, 'undefined'),

        (JSObject(), '[object Object]'),
        ([], ''),
        ([1, 2], '1,2'),
        ([1, JSObject()], '1,[object Object]'),
    ))
    def test_as_str(self, orig, expected):
        """Test that `.as_str()` correctly coerces values into strings."""

        # Coerce `orig` to a string, following JS rules, and assert that
        # the result is equal to `expected`.

        assert_equivalent(self.wrap(orig).as_str(), expected)

    def test_recursive_arrays(self):
        """Make sure we don't explode when processing recursive arrays."""

        ary = self.wrap([1, 2, 3])
        ary[1] = ary

        assert ary.as_str() == '1,,3'


class TestJSWrapperPassThrough(BaseTestTraverser):

    def setup_method(self, method):
        super(TestJSWrapperPassThrough, self).setup_method(method)

        self.value = mock.MagicMock(spec=JSObject())
        self.wrapper = self.traverser.wrap(self.value)

    def test_getitem(self):
        """Test that getitem requests are passed through to the wrapped
        value."""

        self.wrapper['foo']
        self.value.__getitem__.assert_called_once_with('foo')

    def test_setitem(self):
        """Test that setitem requests are passed through to the wrapped
        value."""

        self.wrapper['foo'] = 'bar'
        self.value.__setitem__.assert_called_once_with('foo', 'bar')

    def test_contains(self):
        """Test that contains requests are passed through to the wrapped
        value."""

        'foo' in self.wrapper
        self.value.__contains__.assert_called_once_with('foo')

    def test_iter(self):
        """Test that iter requests are passed through to the wrapped value."""

        iter(self.wrapper)
        self.value.__iter__.assert_called_once_with()

    @parametrize('method', ('keys', 'get', 'as_int'))
    def test_generic_attr(self, method):
        """Test that non-special-cased attribute reads are passed through to
        the wrapped value."""

        getattr(self.wrapper, method)('foo-thing')
        getattr(self.value, method).assert_called_once_with('foo-thing')


class TestJSWrapper(BaseTestTraverser):

    @parametrize('value', (42,
                           42L,
                           42.,
                           True,
                           b'42',
                           u'42',
                           None,
                           Undefined))
    def test_wrap_literal(self, value):
        """Test that literal values are wrapped in `JSLiteral` instances."""

        val = self.wrap(value)
        assert isinstance(val, JSLiteral)
        assert val.as_primitive() is value

    @parametrize('type_', (list, tuple))
    def test_wrap_list(self, type_):
        """Test that a list or tuple is wrapped in a JSArray, with the expected
        element values."""

        value = [42, 12, 'hello.']
        array = self.wrap(type_(value))

        assert isinstance(array, JSArray)
        assert value == [array[idx].as_primitive() for idx in array]

    def test_wrap_dict(self):
        """Test that a dict is wrapped in a JSObject with the expected
        properties."""

        obj = {'qua?': 42,
               'Inigo': 'Montoya'}

        val = self.wrap(obj)

        # Make sure this is a base `JSObject` instance, and not a subclass.
        assert type(val) is JSObject  # noqa

        assert obj == {key: val[key].as_primitive() for key in val}

    def test_wrap_wrapper(self):
        """Test that re-wrapping a JSWrapper results in the correct
        behavior."""

        wrapper = self.traverser.wrap(42, dirty='florg')
        wrapped = self.traverser.wrap(wrapper)

        assert wrapped.value is wrapper.value
        assert wrapped.dirty is wrapper.dirty

    @parametrize('constructor', (JSArray,
                                 JSContext,
                                 JSLiteral,
                                 JSObject,
                                 type(b'Foo', (JSObject,), {})))
    def test_wrap_jsvalue(self, constructor):
        """Test that wrapping a JSValue instance results in that instance being
        wrapped directly."""

        val = constructor()
        assert val.traverser is None

        wrapper = self.traverser.wrap(val)
        assert wrapper.value is val
        assert wrapper.value.traverser is self.traverser


class TestJSLiteral(BaseTestTraverser):

    @parametrize('value,typeof', ((1.2, 'number'),
                                  (12, 'number'),
                                  (12L, 'number'),
                                  (b'12', 'string'),
                                  (u'12', 'string'),
                                  (True, 'boolean'),
                                  (None, 'object'),
                                  (Undefined, 'undefined')))
    def test_typeof(self, value, typeof):
        """Test that `typeof` returns the correct type."""

        assert self.wrap(value).typeof == typeof


class TestJSObject(BaseTestTraverser):

    def test_typeof(self):
        """Test that `typeof` returns 'object' for non-callable objects."""

        assert JSObject().typeof == 'object'

    def test_typeof_function(self):
        """Test that `typeof` returns 'function' for callable objects."""

        assert JSObject(callable=True).typeof == 'function'


class TestJSArray(BaseTestTraverser):

    def test_typeof(self):
        """Test that `typeof` returns 'object'."""

        assert JSArray().typeof == 'object'
