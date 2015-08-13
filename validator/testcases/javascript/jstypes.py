import itertools
import types
from collections import Iterable
from math import isnan

from validator.constants import JETPACK_URI_URL
import instanceproperties


class Sentinel:
    """An object which is used for nothing other than a sentinel value."""


class Undefined(object):
    """A singleton representing the JavaScript `undefined` type."""
    def __repr__(self):
        return '[object undefined]'

    def __str__(self):
        return 'undefined'

    def __nonzero__(self):
        return False
Undefined = Undefined()


class JSValue(object):
    """Base type for all JavaScript values."""

    def __init__(self, traverser=None):
        self.traverser = traverser

    def is_literal(self):
        return isinstance(self, JSLiteral)

    def typeof(self):
        """Result of the JavaScript `typeof` operator on our value."""
        return 'object'

    def as_primitive(self):
        """Return our value as a Python version of a JavaScript primitive
        type: unicode, float, or bool."""
        raise NotImplemented()

    def as_bool(self):
        """Return our value as a boolean."""
        if not self.is_literal():
            return True

        val = self.as_primitive()
        if isinstance(val, float) and isnan(val):
            return False

        # This is how JavaScript defines boolean coercion.
        return val not in (+0, -0, False, None, Undefined, '')

    def as_int(self):
        """Return our value as an int."""
        try:
            return int(self.as_float())
        except (ValueError, OverflowError):
            # Yes, JavaScript requires this.
            return 0

    def as_float(self):
        """Return our value as a float."""
        val = self.as_primitive()

        if isinstance(val, (int, float, bool)):
            return float(val)

        if val is None:
            return 0.

        # Everything else is treated as a string.
        if not isinstance(val, basestring):
            val = str(val)

        try:
            val = val.strip()

            if val.startswith(('0x', '-0x')):
                # Hex integer.
                return float(int(val, 16))

            if val.startswith(('0o', '-0o')):
                # Octal integer.
                return float(int(val, 8))

            if val == 'Infinity':
                return float('inf')
            elif val == '-Infinity':
                return float('-inf')

            if val == '':
                # Empty string is treated as 0.
                return 0.

            if val[0].isdigit() or val[0].startswith(('+', '-')):
                return float(val)
        except ValueError:
            # Anything conversion which would raise a ValueError in Python
            # is converted to NaN in JavaScript.
            pass

        return float('nan')

    def as_str(self):
        """Return our value as a string."""
        val = self.as_primitive()

        if isinstance(val, basestring):
            return val

        if isinstance(val, float):
            if isnan(val):
                return 'NaN'
            if val == float('inf'):
                return 'Infinity'
            if val == -float('inf'):
                return '-Infinity'

            if val == int(val):
                val = int(val)
        elif isinstance(val, bool):
            return 'true' if val else 'false'

        if val is None:
            return 'null'

        return str(val)


class JSObject(JSValue):
    """
    Mimics a JS object (function) and is capable of serving as an active
    context to enable static analysis of `with` statements.
    """

    def __init__(self, data=None, **kw):
        super(JSObject, self).__init__(**kw)

        self.type_ = 'object'  # For use when an object is pushed as a context.
        self.data = {}
        if data is not None:
            self.data.update(data)

    is_unwrapped = False
    recursing = False

    @property
    def _value(self):
        return self.data

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def __contains__(self, key):
        return key in self.data

    def __iter__(self):
        return iter(self.data)

    def contains(self, value):
        """Return true if `value` is a key in this object. Should return the
        same result as the JavaScript `in` operator."""
        return value.as_str() in self.data

    def keys(self):
        return list(iter(self))

    def __nonzero__(self):
        return True

    def get(self, name, instantiate=False):
        'Returns the value associated with a property name'
        name = unicode(name)
        output = None

        if name == 'wrappedJSObject':
            clone = JSObject()
            clone.is_unwrapped = True
            clone.data = self.data
            return self.traverser.wrap(clone)

        if name in self.data:
            output = self.data[name]
            if callable(output):
                output = output()
        elif instantiate:
            output = self.traverser.wrap(JSObject(), dirty=True)
            self.set(name, output)

        modifier = instanceproperties.get_operation('get', name)
        if modifier:
            modifier(self.traverser)

        if output is None:
            return self.traverser.wrap(JSObject(), dirty=True)
        if not isinstance(output, JSWrapper):
            output = self.traverser.wrap(output)
        return output

    def get_literal_value(self):
        return self.as_primitive()

    def as_primitive(self):
        return u'[object Object]'

    def set(self, name, value):
        modifier = instanceproperties.get_operation('set', name)
        if modifier:
            modified_value = modifier(value, self.traverser)
            if modified_value is not None:
                value = modified_value

        if self.is_unwrapped:
            self.traverser.warning(
                err_id=('testcases_javascript_jstypes', 'JSObject_set',
                        'unwrapped_js_object'),
                warning="Assignment of unwrapped JS Object's properties.",
                description='Improper use of unwrapped JS objects can '
                            'result in serious security vulnerabilities. '
                            'Please reconsider your use of unwrapped '
                            'JS objects.',
                signing_help='Please avoid assigning to properties of '
                             'unwrapped objects from unprivileged scopes, '
                             'unless you are using an export API '
                             '(http://mzl.la/1fvvgm9) to expose API '
                             'functions to content scopes. '
                             'In this case, however, please note that '
                             'your add-on will be required to undergo '
                             'manual code review for at least one '
                             'submission.',
                signing_severity='high')

        self.data[name] = value

    def has_var(self, name):
        name = unicode(name)
        return name in self.data

    def repr_keywords(self):
        return {'unwrapped': self.is_unwrapped}

    def __repr__(self):
        if self.recursing:
            return u'<recursive-reference>'

        self.recursing = True
        try:
            extra = u''.join(u', {0}={1!r}'.format(key, value)
                             for key, value in self.repr_keywords().items())

            return u'<jstypes.{class_name}({value!r}{keywords})>'.format(
                class_name=self.__class__.__name__, value=self._value,
                keywords=extra)
        finally:
            self.recursing = False


class JSContext(JSObject):
    """A variable context"""

    def __init__(self, context_type, **kw):
        super(JSContext, self).__init__(**kw)
        self.type_ = context_type


class JSWrapper(object):
    """Wraps a JS value and handles contextual functions for it."""

    def __init__(self, value=Sentinel, const=False, dirty=False, lazy=False,
                 hooks=None, traverser=None, callable=False, setter=None):

        assert traverser is not None

        self.const = const
        self.traverser = traverser
        self.value = None  # Instantiate the placeholder value
        self.dirty = False  # Also not yet...

        self.hooks = hooks.copy() if hooks else {}

        if 'literal' in self.hooks:
            value = self.hooks['literal'](traverser)

        # Used for predetermining set operations
        self.setter = setter

        if value is Sentinel:
            # No value -> empty object.
            value = JSObject()

        self.set_value(value, overwrite_const=True)

        self.dirty = dirty or self.dirty
        self.lazy = lazy
        self.callable = callable

    def is_callable(self):
        return self.callable or ('return' in self.hooks and
                                 'value' not in self.hooks)

    # Proxies for JSValue methods:
    def typeof(self):
        if self.is_callable():
            # Ugh.
            return 'function'
        return self.value.typeof()

    def as_primitive(self):
        return self.value.as_primitive()

    def as_bool(self):
        return self.value.as_bool()

    def as_int(self):
        return self.value.as_int()

    def as_float(self):
        return self.value.as_float()

    def as_str(self):
        return self.value.as_str()

    def set_value(self, value, overwrite_const=False):
        """Assigns a value to the wrapper"""

        traverser = self.traverser

        if self.const and not overwrite_const:
            traverser.warning(
                err_id=('testcases_javascript_traverser',
                        'JSWrapper_set_value', 'const_overwrite'),
                warning='Overwritten constant value',
                description='A variable declared as constant has been '
                            'overwritten in some JS code.')

        # Process any setter/modifier
        if self.setter:
            value = self.setter(value, traverser) or value or None

        if value is not None and value == self.value:
            return self

        # We want to obey the permissions of global objects
        from predefinedentities import is_shared_scope

        if (not self.hooks.get('overwriteable', True) and
                is_shared_scope(traverser)):
            traverser.warning(
                err_id=('testcases_javascript_jstypes', 'JSWrapper_set_value',
                        'global_overwrite'),
                warning='Global overwrite',
                description='An attempt to overwrite a global variable was '
                            'made in some JS code.')
            return self

        if callable(value):
            value = value(traverser)

        if isinstance(value, JSValue):
            pass
        elif (isinstance(value, (bool, int, float, long, basestring)) or
                value in (None, Undefined)):
            self.inspect_literal(value)
            value = JSLiteral(value, traverser=self.traverser)
        # If the value being assigned is a wrapper as well, copy it in
        elif isinstance(value, JSWrapper):
            self.value = value.value
            self.lazy = value.lazy
            self.dirty = value.dirty
            self.hooks = value.hooks
            # const does not carry over on reassignment
            return self
        elif isinstance(value, Iterable):
            value = JSArray(value, traverser=self.traverser)
        elif isinstance(value, dict):
            self.hooks = value
            value = JSObject()

        value.traverser = self.traverser
        self.value = value
        return self

    def get(self, name, instantiate=False):
        """Retrieve a property from the variable."""

        traverser = self.traverser

        value = self.value
        hooks = self.hooks
        dirty = value is None

        # FIXME: <IS_GLOBAL>
        if self.hooks:
            if 'value' not in hooks:
                output = traverser.wrap(JSObject(), hooks={'value': {}})

                for key in ('dangerous', 'readonly', 'name'):
                    if key in self.hooks:
                        output.hooks[key] = self.hooks[key]
                return output

            def _evaluate_lambdas(node):
                if callable(node):
                    return _evaluate_lambdas(node(t=traverser))
                else:
                    return node

            value_val = hooks['value']
            value_val = _evaluate_lambdas(value_val)

            if isinstance(value_val, dict):
                if name in value_val:
                    value_val = _evaluate_lambdas(value_val[name])
                    output = traverser._build_global(name=name,
                                                     entity=value_val)
                    return output
            else:
                value = value_val

        # Process any getters that are present for the current property.
        modifier = instanceproperties.get_operation('get', name)
        if modifier:
            modifier(traverser)

        output = None
        if isinstance(value, JSObject):
            output = value.get(name, instantiate=instantiate)

        if not isinstance(output, JSWrapper):
            if output is None:
                output = traverser.wrap(dirty=True)
            else:
                output = traverser.wrap(output, dirty=dirty)

        # If we can predetermine the setter for the wrapper, we can save a ton
        # of lookbehinds in the future. This greatly simplifies the
        # MemberExpression support.
        setter = instanceproperties.get_operation('set', name)
        if setter:
            output.setter = setter
        return output

    def del_value(self, member):
        """The member `member` will be deleted from the value of the wrapper"""
        if self.hooks:
            self.traverser.warning(
                err_id=('testcases_js_jstypes', 'del_value',
                        'global_member_deletion'),
                warning='Global member deletion',
                description='Members of global object may not be deleted.')

        elif isinstance(self.value, JSObject):
            if member in self.value.data:
                del self.value.data[member]

    def contains(self, value):
        """Return true if `value` is a key in our value. Should return the
        same result as the JavaScript `in` operator."""

        return self.value.contains(value)

    def is_literal(self):
        """Returns whether the content is a literal"""
        return isinstance(self.value, JSLiteral)

    def get_literal_value(self):
        """Returns the literal value of the wrapper"""
        return self.value.as_primitive()

    def __repr__(self):
        keywords = []
        for keyword in ('dirty', 'callable', 'hooks'):
            keywords.append('{key}={value!r}'.format(
                key=keyword, value=getattr(self, keyword)))

        return u'<jstypes.{class_name}({value!r}, {keywords})>'.format(
            class_name=self.__class__.__name__, value=self.value,
            keywords=', '.join(keywords))

    def inspect_literal(self, value):
        """
        Inspect the value of a literal to see whether it contains a flagged
        value.
        """

        # Don't do any processing if we can't return an error.
        if not self.traverser:
            return

        if isinstance(value, types.StringTypes):
            if ('is_jetpack' in self.traverser.err.metadata and
                    value.startswith('resource://') and
                    '-data/' in value):
                # Since Jetpack files are ignored, this should not be scanning
                # anything inside the jetpack directories.
                self.traverser.warning(
                    err_id=('javascript_js_jstypes', 'jswrapper',
                            'jetpack_abs_uri'),
                    warning='Absolute URIs in Jetpack 1.4 are disallowed',
                    description=('As of Jetpack 1.4, absolute URIs are no '
                                 'longer allowed within add-ons.',
                                 'See %s for more information.'
                                 % JETPACK_URI_URL),
                    compatibility_type='error')

    def __unicode__(self):
        """Returns a textual version of the object."""
        return unicode(self.as_str())


class JSLiteral(JSObject):
    """Represents a literal JavaScript value."""

    def __init__(self, value=None, **kw):
        super(JSLiteral, self).__init__(**kw)
        self.value = value
        self.source = None
        self.messages = []

    def set_value(self, value):
        self.value = value

    @property
    def _value(self):
        return self.value

    def typeof(self):
        """Result of the JavaScript `typeof` operator on our value."""
        val = self.as_primitive()

        if isinstance(val, bool):
            return 'boolean'
        elif isinstance(val, (int, long, float)):
            return 'number'
        elif isinstance(val, basestring):
            return 'string'
        elif val is Undefined:
            return 'undefined'
        elif val is None:
            return 'object'
        return 'object'

    def __str__(self):
        return self.as_str()

    def as_primitive(self):
        """Return our value as a Python version of a JavaScript primitive
        type: unicode, float, or bool."""
        return self.value

    def repr_keywords(self):
        return dict(super(JSLiteral, self).repr_keywords(),
                    source=self.source)


class JSArray(JSObject):
    """A class that represents both a JS Array and a JS list."""

    def __init__(self, elements=None, **kw):
        super(JSArray, self).__init__(**kw)
        if elements is not None:
            self.elements = map(self.traverser.wrap, elements)
        else:
            self.elements = []

    @property
    def _value(self):
        return self.elements

    def __len__(self):
        return len(self.elements)

    def __contains__(self, key):
        return (isinstance(key, int) and 0 <= key < len(self.elements) or
                super(JSArray, self).__contains__(key))

    def __iter__(self):
        return itertools.chain(range(0, len(self.elements)),
                               super(JSArray, self).__iter__())

    def contains(self, value):
        """Return true if `value` is an element in this Array, or a property
        of this Object. Should return the same result as the JavaScript `in`
        operator."""

        if value.as_str().isdigit():
            return value.as_int() in self
        return value.as_str() in self

    def get(self, name, instantiate=False):
        if name == 'length':
            return len(self.elements)

        try:
            if isinstance(name, (int, long, float)) or name.isdigit():
                output = self.elements[int(name)]

                if not isinstance(output, JSWrapper):
                    output = self.traverser.wrap(output)
                return output
        except (ValueError, IndexError, KeyError):
            pass

        return super(JSArray, self).get(name, instantiate)

    def as_primitive(self):
        """Return a comma-separated string representation of each of our
        elements."""

        if self.recursing:
            return u''

        self.recursing = True
        try:
            return u','.join(elem.as_str() if elem is not None else u''
                             for elem in self.elements)
        finally:
            self.recursing = False

    def set(self, index, value):
        try:
            index = int(index)
            # Ignore floating point indexes
            if index != float(index) or index < 0:
                return super(JSArray, self).set(index, value)
        except ValueError:
            return super(JSArray, self).set(index, value)

        if len(self.elements) > index:
            self.elements[index] = self.traverser.wrap(value)
        else:
            # Max out the array size at 100000
            index = min(index, 100000)
            # Assigning to an index higher than the top of the list pads the
            # list with nulls
            while len(self.elements) < index:
                self.elements.append(None)
            self.elements.append(self.traverser.wrap(value))
