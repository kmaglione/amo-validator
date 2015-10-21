from __future__ import absolute_import, print_function, unicode_literals

import itertools
import re
import sys
from collections import Iterable
from math import isnan
from repr import Repr


# Pretty printers to make sure our object representions are modestly readable.
repr_data = Repr().repr
repr_hooks = Repr().repr

repr_data.im_self.maxlevel = 1
repr_data.im_self.maxother = 60
repr_hooks.im_self.maxlevel = 2


class SentinelType(object):
    """A singleton object which is used for nothing other than a sentinel
    value."""

    def __repr__(self):
        return '<Sentinel>'
Sentinel = SentinelType()


class LazyJSObjectType(object):
    """A singleton object which when used as a value, causes an empty
    JSObject to be created only when needed."""

    def __repr__(self):
        return '<LazyJSObject>'
LazyJSObject = LazyJSObjectType()


class UndefinedType(object):
    """A singleton representing the JavaScript `undefined` type."""

    def __repr__(self):
        return '[object undefined]'

    def __unicode__(self):
        return 'undefined'

    def __nonzero__(self):
        return False
Undefined = UndefinedType()


LITERAL_TYPES = (bool, int, float, long, basestring, type(None), UndefinedType)

# `unicode.isdigit` will return true for digits in some international
# numbering systems, which are not digits for our purposes.
isdigit = re.compile(r'^[0-9]+$').match
isnumber = re.compile(r'^[+-]?\.?[0-9]').match


class HookMetaclass(type):
    def __new__(mcls, name, bases, dict_):
        if Hook is None:
            # For the actual Hook class, just create the class as normal.
            return super(HookMetaclass, mcls).__new__(mcls, name, bases, dict_)

        result = Hooks((name,))
        for key, val in dict_.iteritems():
            hook = Hook.to_hook(val)

            if key in ('__call__', '__self__'):
                result.extend(hook)
            elif key == 'Meta':
                result.extend({attr: getattr(val, attr)
                               for attr in dir(val)
                               if attr != 'mro'})
            elif key != '__module__':
                result['properties'][key] = hook

        return result
Hook = None


class Hook(object):
    """A magical base class which will convert any object which inherits from
    it into a `Hooks` instance, based on its attributes.

    All attributes declared in the subclass are converted to hook properties.
    Each attribute may be one of:

      * A callable, which is converted into a `return` hook for that property.

      * A dict, which will be treated as a set of hooks for that property,
        as interpreted by `Hooks.hook`. A `Hooks` object is interpreted the
        same way as any other dict.

    Because a `Hook` subclass is converted to a `Hooks` dict, they may also
    be used to recursively define hook properties:

    class window(Hook):
        class document(Hook):
            write = {'on_call': "Don't do it. Just don't."}

    creates an `on_call` hook for `window.document.write`, which should
    hopefully knock some sense into the caller.

    Additionally, the following class methods can be used as decorators
    to define functions for the hooks of the same name:

      * getter
      * on_call
      * on_get
      * on_set
      * return_
      * scope_filter
      * value

    See the individual documentation strings of the above for usage examples.
    """

    __metaclass__ = HookMetaclass

    @classmethod
    def to_hook(cls, val):
        """Convert the given value to a hook dict, based on any decorators
        which have so far been applied to it."""
        if callable(val):
            return {'return': val}
        return val

    def _hook(name):
        def hook(func=None, **kw):
            """A decorator which creates a new `Hooks` instance, and adds a
            `{name}` hook for the decorated function. Said `Hooks` instance is
            then returned. This can be used to chain hook creation for the
            same property, as one might for an `@property` descriptor:

            @Hooks.{name}
            def thing(this, *args, **kw):
                do_stuff()

            @thing.other_hook
            def thing(this, *args, **kw):
                do_other_stuff()

            If keyword arguments are given, they are first added as hooks, and
            a new decorator is returned for `{name}` instead:

            @Hook.{name}(overwritable=True)
            def thing(this, *args, **kw):
                do_overwritable_things()
            """.format(name=name)

            hooks = Hooks()
            if kw:
                hooks.extend(kw)
                return getattr(hooks, name)

            hooks.add_hook(name, func)
            return hooks

        hook.__name__ = str(name)
        return staticmethod(hook)

    getter = _hook('getter')
    on_call = _hook('on_call')
    on_get = _hook('on_get')
    on_set = _hook('on_set')
    return_ = _hook('return_')
    scope_filter = _hook('scope_filter')
    value = _hook('value')


class Hooks(dict):
    """Represents a set of hooks for a given object.

    Most hooks represent an operation that may be performed on an object or
    descriptor, such as being called as a function, or being set to a new
    value. These hooks are fired whenever a piece of analyzed code is detected
    as performing the given action. Other hooks may be arbitrary pieces of
    custom data, to be used by code analysis functions which need to track
    state.

    Standard hooks include:

    * on_call: Fires when the hooked object is called as a function. May be
    either a dict, which is reported as a warning via `ErrorBundle.report`
    whenever a function call is detected, or a function which accepts three
    arguments:

        - this: The `this` object the function was called with.
        - args: And `Args` object representing the arguments the function was
          called with.
        - callee: The function object itself, as reflected in JavaScript.

    If the function returns a dict, it is reported in the same way as a bare
    dict would be.

    * on_get: Fires when the given property is accessed. May be a bare dict,
    as with `on_call`, or a function which accepts three arguments:

        - this: The object the property is being read from.
        - value: The value stored in the slot for this property.
        - name: The name of the property being read. May be `None`.

    * on_set: Fires when the given property is set. May be a bare dict, as
    with `on_get`, or a function which accepts three arguments:

        - wrapper: The JSWrapper which represents the property's descriptor.
        - value: The value attempting to be stored in the property's slot.
        - name: The name of the property being written. May be `None`.

    * getter: Fires when the given property is read. Must be a function, which
    accepts three arguments:

        - this: The object the property is being read from.
        - name: The name of the property being read.
        - default: The value which would be returned if there were no getter.

    The value returned by this function is used as the result of the get
    operation. Note that properties with `getter` hooks are treated as
    read-only, and will emit a warning on any attempt to set.

    * return or return_: Fires when the given object is called as a function.
    Must be a function, which accepts the same arguments as `on_call`. The
    return value of this function is used as the return value of the call
    operation.

    * properties: A dict, containing hooks for each hooked sub-property of
    this object. Each key in this dict *must* be a `Hooks` instance.

    * inherit: A `set` containing the names of hooks which should be inherited
    by any property read from this object. If this set includes `inherit`
    itself, all included hooks will be inherited by any descendant of the
    hooked object.

    * scope_filter: A function which takes one argument, the current
    `Traverser` instance, and returns a boolean. If this hook is present, it
    is called before any hooks are applied to this object. If it returns
    false, *no* hooks will be applied to the object.

    This is primarily useful for filtering out definitions of global objects
    for scopes where they do not apply.

    * unwrapped: If true, this is an object from an unprivileged/untrusted
    scope without any X-ray wrappers protecting it.

    * scope: An arbitrary string representing the origin of the object. When
    set to 'content', the object is known to have come from a content window,
    which primarily has the effect of causing a dereference of
    `wrappedJSObject` to behave the same as a call to `Cu.waiveXrays`.

    * overwritable: If true, this property may be overwritten without
    triggering a warning. This is false by default for any object with
    hooks, unless it has an `on_set` hook. It is true by default for any
    object without hooks.
    """

    def __init__(self, path=()):
        self.path = path
        self.name = '.'.join(path)

        if self.name:
            self['name'] = self.name

        self['properties'] = {}

    def __getattr__(self, name):
        def wrapper(fn):
            self.add_hook(name, fn)
            return self
        wrapper.name = name
        return wrapper

    def add_hook(self, key, value):
        if key == 'return_':
            key = 'return'

        if key == 'properties':
            exists = not self.get('properties')
        else:
            exists = key not in self or key == 'name'

        assert exists, ('Hook for {0!r} already exists at `{1}`: {2!r}'
                        .format(key, self.name, self))

        self[key] = value

    def extend(self, hooks):
        for key, val in hooks.iteritems():
            if key == 'properties':
                self.hook(val)
            elif key != 'name':
                self.add_hook(key, val)
        return self

    def hook(self, path, *args, **entity):
        if isinstance(path, Hooks):
            return self.hook(path.name).extend(path)

        if isinstance(path, dict):
            assert not args or entity

            for key, val in path.iteritems():
                if isinstance(val, Hooks):
                    self.hook((key,)).extend(val)
                else:
                    self.hook((key,), **val)
            return

        if isinstance(path, basestring):
            path = path.split('.')

        target = self
        for ident in path:
            properties = target['properties']
            if ident not in properties:
                properties[ident] = Hooks(target.path + (ident,))

            target = properties[ident]
            assert isinstance(target, Hooks)

        for key, value in entity.iteritems():
            if isinstance(value, Hooks):
                target.hook(key).extend(value)
            else:
                target.add_hook(key, value)

        for arg in args:
            if isinstance(arg, dict):
                target.hook(arg)
            elif hasattr(Hooks, arg):
                return getattr(target, arg)
            else:
                def decorator(fn):
                    target.add_hook(arg, fn)
                    return fn
                return decorator

        return target


# Hooks for all global scopes.
Global = Hooks()

# Hooks for XPCOM interfaces.
Interfaces = Hooks()

Global.hook(('Components', 'interfaces'))['properties'] = (
    Interfaces['properties'])

# Hooks which apply to *all* objects.
Wildcards = Global.hook('**')


WILDCARDS = Wildcards['properties']

INTERFACES = Interfaces['properties']


class Args(list):
    """A list subclass for function arguments which returns a wrapper for
    `undefined`, as would a JavaScript arguments object, when an argument
    does not exist."""

    def __init__(self, traverser, args):
        super(Args, self).__init__(args)
        self.traverser = traverser

    def __getitem__(self, index):
        if index >= len(self):
            return self.traverser.wrap(Undefined, const=True)

        return super(Args, self).__getitem__(index)


class Hookable(object):
    __slots__ = 'hooks', 'traverser'

    hook_messages = {'on_call': 'Potentially dangerous function call',
                     'on_get': 'Attempt to access sensitive property',
                     'on_set': 'Attempt to set sensitive property'}

    def fire_hooks(self, hook, *args, **kw):
        """Fire all hooks for the given hook name on this object. Any extra
        arguments are passed directly to the hook function. If the hook is
        callable, and it returns a truthy value, that value is passed to
        `traverser.report`. If the hook is not callable, its value is used
        as if it were a hook function's return value."""
        if hook in self.hooks:
            if callable(self.hooks[hook]):
                result = self.hooks[hook](*args, **kw)
            else:
                result = self.hooks[hook]

            if result not in (None, False):
                name = self.hooks.get('name',
                                      getattr(self, 'name', 'generic'))

                self.traverser.report(
                    {'err_id': ('jstypes', 'hook_{0}'.format(hook), name),
                     'warning': self.hook_messages[hook]},
                    result)

    def add_hooks(self, hooks):
        """Add hooks to this object. Any hooks in the 'properties' dict are
        merged with hooks in this object's 'properties' dict. Any other
        top-level hooks are simply replaced."""
        self.merge_hooks(self.hooks, hooks, self.traverser)

    def inherit_hooks(self, hooks):
        """Copy any hooks marked as inheritable from a parent object."""
        inherited = hooks.get('inherit')
        if inherited:
            self.add_hooks({hook: hooks[hook]
                            for hook in hooks.viewkeys() & inherited})

    @staticmethod
    def merge_hooks(base, new, traverser):
        if 'properties' in new:
            props = base.setdefault('properties', {})

            props.update((key, hook)
                         for key, hook in new['properties'].iteritems()
                         if ('scope_filter' not in hook or
                             hook['scope_filter'](traverser)))

        if 'inherit' in new:
            inherited = base.setdefault('inherit', set())
            inherited |= new['inherit']

        base.update((key, new[key])
                    for key in new.viewkeys() - {'inherit', 'properties'})


class JSValue(object):
    """Base type for all JavaScript values."""

    class __metaclass__(type):
        def __instancecheck__(cls, obj):
            """Allow `isinstance` checks on JSWrapper objects to match the
            JSValue objects they're wrapping."""

            if type.__instancecheck__(JSWrapper, obj):
                return isinstance(obj.value, cls)

            return type.__instancecheck__(cls, obj)

    typeof_map = {
        bool: 'boolean',
        int: 'number',
        long: 'number',
        float: 'number',
        str: 'string',
        unicode: 'string',
        type(None): 'object',
        type(Undefined): 'undefined',
    }

    is_literal = False

    def __init__(self, traverser=None, hooks=None, callable=False):
        self.hooks = {} if hooks is None else hooks.copy()
        self.callable = callable or ('return' in self.hooks or
                                     'on_call' in self.hooks)
        self.traverser = traverser

    dirty = False

    def __eq__(self, other):
        # Use strict comparison, even if we look like a list or dict.
        return self is other

    def copy(self, *args, **kw):
        new = self.__class__(*args, traverser=self.traverser,
                             hooks=self.hooks, **kw)
        new.callable = self.callable
        return new

    @property
    def is_clean_literal(self):
        """Return true if the content is a primitive type with a known
        alue."""
        return not self.dirty and self.is_literal

    @property
    def value(self):
        """Return ourself. Allows wrappers and `JSValue`s to be used
        interchangeably."""
        return self

    @property
    def typeof(self):
        """Result of the JavaScript `typeof` operator on our value."""
        if self.callable:
            return 'function'
        return 'object'

    def as_primitive(self):
        """Return our value as a Python version of a JavaScript primitive
        type: unicode, float, or bool."""
        raise NotImplemented

    def as_bool(self):
        """Return our value as a boolean."""
        if not self.is_literal:
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

        if isinstance(val, (int, long, float, bool)):
            try:
                return float(val)
            except OverflowError:
                return float('nan')

        if val is None:
            return 0.

        # Everything else is treated as a string.
        if not isinstance(val, basestring):
            val = unicode(val)

        try:
            # Values are always stripped of leading and trailing whitespace
            # before explicit coercion.
            val = val.strip()

            if val == 'Infinity':
                return float('inf')
            elif val == '-Infinity':
                return float('-inf')

            val = val.lower()

            # Oddly enough, values beginning with '+0x...' and '+0o...' are
            # not accepted as numbers.
            if val.startswith(('0x', '-0x')):
                # Hex integer.
                return float(int(val, 16))

            if val.startswith(('0o', '-0o')):
                # Octal integer.
                return float(int(val, 8))

            if val == '':
                # Empty string is treated as 0.
                return 0.

            if isnumber(val):
                return float(val)
        except (ValueError, OverflowError):
            # Any conversion which would raise a ValueError in Python
            # is converted to NaN in JavaScript.
            pass

        return float('nan')

    def as_identifier(self):
        """Return our value as a string, to be used in identifier look-ups."""
        return self.as_str()

    def as_str(self):
        """Return our value as a unicode string."""
        val = self.as_primitive()

        if isinstance(val, basestring):
            return unicode(val)

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

        return unicode(val)

    def add_hooks(self, hooks):
        """Wrap `Hookable.add_hooks` to update our `callable` property if we
        have a hook that suggests we're a function."""

        super(JSValue, self).add_hooks(hooks)
        if 'return' in self.hooks or 'on_call' in self.hooks:
            self.callable = True


class JSObject(JSValue, Hookable):
    """
    Mimics a JS object (function) and is capable of serving as an active
    context to enable static analysis of `with` statements.
    """

    def __init__(self, data=None, name=None, **kw):
        super(JSObject, self).__init__(**kw)

        self.data = {}
        if data is not None:
            for key, val in data.iteritems():
                val = self.traverser.wrap(val)
                wrapper = self.traverser.wrap(val, name=key, parent=self,
                                              lvalue=True, const=val.const,
                                              inferred=val.inferred)
                self.data[key] = wrapper

    # A context type, as would appear in a JSContext object, for use when an
    # object is the target of a `with` statement, and therefore used as a
    # context.
    context_type = 'object'

    recursing = False
    name = '<unknown>'

    def copy(self, *args, **kw):
        """Create a copy of this object, including any properties, flags,
        and hooks."""
        return super(JSObject, self).copy(*args, data=self.data, **kw)

    @property
    def _value(self):
        """Return the "native" value of this object, for use by __repr__."""
        return self.data

    def __getitem__(self, key):
        """Return the l-value `JSWrapper` for the given property on the
        JavaScript object we represent."""
        return self.get(key)

    def __setitem__(self, key, value):
        """Set the given property to the given value on the JavaScript object
        we represent."""
        self.set(key, value)

    def __contains__(self, key):
        """Return true if we have a known property with the given key."""
        return key in self.data or self.has_builtin(key)

    def __iter__(self):
        return iter(self.data)

    def __nonzero__(self):
        """Always treat JSObject instances as truthy, even though they behave
        as iterables."""
        return True

    def contains(self, value):
        """Return true if `value` is a key in this object. Should return the
        same result as the JavaScript `in` operator."""
        return value.as_identifier() in self

    def keys(self):
        return list(iter(self))

    def query_interface(self, *interfaces):
        """Mimic the XPCOM QueryInterface method. Given either an interface
        name, or an interface object from `Components.interfaces`, add
        hooks for that interface to our object, and return `self`."""

        for interface in interfaces:
            if isinstance(interface, basestring):
                hooks = INTERFACES.get(interface, {})
            else:
                hooks = interface.value.hooks

            if 'interface' in hooks:
                hooks = hooks['interface']
                self.add_hooks(hooks)

                self.hooks.setdefault('interfaces', [])
                self.hooks['interfaces'].append(hooks['interface_name'])

        return self

    def call(self, this, args):
        """Call the JavaScript function this JSObject represents, dispatching
        any `on_call` hooks, and returning the value returned by our `return`
        hook."""
        self.fire_hooks('on_call', this, args, callee=self)

        if 'return' in self.hooks:
            res = self.hooks['return'](this, args, callee=self)

            if not isinstance(res, JSValue):
                dirty = any(arg.dirty for arg in args)
                res = self.traverser.wrap(res, dirty=dirty)
        else:
            res = self.traverser.wrap(dirty='CallReturn')

        # Inherited hooks are also inherited by values returned by
        # method calls.
        res.inherit_hooks(self.hooks)
        return res

    def has_builtin(self, name):
        """Return true if we have hooks for the property `name`."""
        props = self.hooks.get('properties')
        return (props and (name in props or '*' in props) or
                isinstance(name, basestring) and name.startswith('on') or
                name in WILDCARDS)

    def get_builtin(self, name):
        """Create and return a wrapper for the built-in type in the property
        `name`."""

        wrapper = self.traverser.wrap(name=name, parent=self, lvalue=True)

        # Add global wildcard hooks.
        if name in WILDCARDS:
            wrapper.add_hooks(WILDCARDS[name])

        # Special case for event listener attributes. (Ick.)
        if isinstance(name, basestring) and name.startswith('on'):
            wrapper.add_hooks(WILDCARDS['on*'])

        props = self.hooks.get('properties')
        if props:
            if name in props:
                wrapper.add_hooks(props[name])

                # By default, any hooked object that doesn't specify an
                # `overwritable` flag triggers a warning when written.
                # Properties with an `on_set` hook are an exception,
                # since they're either meant to be assigned to, or will
                # dispatch a more specific warning.
                if 'on_set' not in wrapper.hooks:
                    wrapper.hooks.setdefault('overwritable', False)

            # `*` acts as a local wildcard, matching any property name
            # directly under the object it's hooking.
            if '*' in props:
                wrapper.add_hooks(props['*'])

        self.data[name] = wrapper
        return wrapper

    def _get(self, name, instantiate, **kw):
        """Return the wrapper for the property at `name`."""

        if name in self.data:
            output = self.data[name]
        else:
            # Does not already exist. Create a new descriptor if we're
            # expected to.

            if self.has_builtin(name):
                output = self.get_builtin(name)
            elif instantiate:
                output = self.traverser.wrap(name=name, parent=self,
                                             lvalue=True, inferred=True, **kw)
                self.data[name] = output
            else:
                raise KeyError()

            # Copy down any inherited hooks.
            output.inherit_hooks(self.hooks)

        assert isinstance(output, JSWrapper)
        return output

    def get(self, name, instantiate=True, skip_hooks=False, **kw):
        """Return the wrapper for the property `name`. Unless `skip_hooks`
        is false, any `on_get` hooks for the property will be fired. If
        the property does not already exist, and `instantiate` is true,
        it will be instantiated, and marked as an inferred value."""

        try:
            output = self._get(name, instantiate, **kw)
        except KeyError:
            if instantiate:
                raise
            return None

        if not skip_hooks:
            output.fire_hooks('on_get', self, output, name=name)

        if 'getter' in output.hooks:
            result = output.hooks['getter'](self, name, default=output)
            # Return a non-writable wrapper for this value. Ideally, we should
            # support setter hooks, or over-writable properties with getters,
            # and return special proxy wrappers. But that's a topic for the
            # future.
            return self.traverser.wrap(result, const=True)

        return output

    def set(self, name, value, const=False, set_by='<unknown>'):
        """Set the value of the property `name` to `value`, and return its
        wrapper."""
        wrapper = self._get(name, instantiate=True, const=const)
        wrapper.set_value(value, set_by=set_by)

        return wrapper

    def as_primitive(self):
        """Return our value as a Python version of a JavaScript primitive
        type: unicode, float, or bool."""

        return '[object Object]'

    def repr_keywords(self):
        """Return constructor keywords and values for display in `__repr__`
        output."""
        return {'unwrapped': self.hooks.get('unwrapped', False),
                'callable': self.callable,
                'hooks': repr_hooks(self.hooks)}

    def __repr__(self):
        if self.recursing:
            return '<recursive-reference>'

        self.recursing = True
        try:
            extra = ''.join(', {0}={1}'.format(key, value)
                            for key, value in self.repr_keywords().items())

            return '<{class_name}({value}{keywords})>'.format(
                class_name=self.__class__.__name__,
                value=repr_data(self._value),
                keywords=extra)
        finally:
            self.recursing = False


class JSContext(JSObject):
    """A lexical scope context which holds local and global variables."""

    def __init__(self, context_type='default', **kw):
        super(JSContext, self).__init__(**kw)
        self.context_type = context_type
        self.hooks.setdefault('properties', {})
        self.cleanups = []

    def cleanup(self):
        """Call any stored cleanup functions when this context is popped off
        of the scope stack."""

        for func in self.cleanups:
            func()
        del self.cleanups

    def __contains__(self, key):
        """Return true if this context contains any explicitly created
        properties or hooks for the given key.

        Unlike other objects which derive from `JSObject`, this ignores
        wildcard properties. For scope contexts, those are generally
        unimportant, and ignoring them is a significant performance win."""

        return key in self.data or key in self.hooks['properties']

    def repr_keywords(self):
        """Return constructor keywords and values for display in `__repr__`
        output."""
        return dict(super(JSContext, self).repr_keywords(),
                    context_type=self.context_type)


class JSLiteral(JSObject):
    """A JavaScript primitive value."""

    is_literal = True

    def __init__(self, value=None, **kw):
        super(JSLiteral, self).__init__(**kw)
        self._value = value
        self.messages = []

    _value = None

    @property
    def typeof(self):
        """Result of the JavaScript `typeof` operator on our value."""
        return self.typeof_map.get(type(self._value), 'object')

    def __unicode__(self):
        return self.as_str()

    def as_primitive(self):
        """Return our value as a Python version of a JavaScript primitive
        type: unicode, float, or bool."""
        return self._value

    def repr_keywords(self):
        """Return constructor keywords and values for display in `__repr__`
        output."""
        return dict(super(JSLiteral, self).repr_keywords(),
                    messages=self.messages)


class JSArray(JSObject):
    """A class that represents both a JS Array and a JS list."""

    def __init__(self, elements=None, **kw):
        super(JSArray, self).__init__(**kw)
        if elements is not None:
            self.elements = [self.traverser.wrap(elem, lvalue=True)
                             for elem in elements]
        else:
            self.elements = []

    def copy(self, *args, **kw):
        """Create a copy of this array, including any array elements, object
        properties, flags, and hooks."""
        return super(JSArray, self).copy(*args, elements=self.elements, **kw)

    @property
    def _value(self):
        """Return the "native" value of this object, for use by __repr__."""
        return self.elements

    def __len__(self):
        return len(self.elements)

    def __contains__(self, key):
        """Return true if the given key is an integer, and within our allocated
        array bounds, or is otherwise a known object property."""
        if (isinstance(key, float) and key.is_integer() or
                isinstance(key, (int, long))):
            return 0 <= key < len(self.elements)

        return super(JSArray, self).__contains__(key)

    def __iter__(self):
        return itertools.chain(range(0, len(self.elements)),
                               super(JSArray, self).__iter__())

    def contains(self, value):
        """Return true if `value` is an element in this Array, or a property
        of this Object. Should return the same result as the JavaScript `in`
        operator."""

        if isdigit(value.as_str()):
            return value.as_int() in self
        return value.as_identifier() in self

    def get(self, name, instantiate=True, **kw):
        """Wrap `JSObject.get` to handle integer properties, which come from
        our `elements` list rather than our `data` dict, and the special
        `length` property, which always returns the length of `elements`.
        """

        if name == 'length':
            # TODO: We currently simply ignore writes to this property.
            # In the future, we should probably handle them in some way.
            return self.traverser.wrap(len(self.elements), lvalue=True)

        if (isinstance(name, (int, long)) or
                isinstance(name, float) and name.is_integer() or
                isinstance(name, basestring) and isdigit(name)):
            index = long(name)
            try:
                output = self.elements[index]
                if output is not None:
                    return output
            except IndexError:
                pass

            return self.set(index, Undefined)

        return super(JSArray, self).get(name, instantiate, **kw)

    def set(self, name, value, **kw):
        """Wrap `JSObject.set` to handle integer properties, which are stored
        in our `elements` list rather than our `data` dict, and the special
        `length` property, which changes the length of our `elements` list."""

        try:
            index = int(name)
        except ValueError:
            index = None

        if index is not None and 0 <= index <= 10000:
            while len(self.elements) <= index:
                self.elements.append(None)

            value = self.traverser.wrap(value, lvalue=True)
            self.elements[index] = value
            return value
        else:
            if name == 'length':
                return self.get(name)

            return super(JSArray, self).set(name, value, **kw)

    def as_primitive(self):
        """Return a comma-separated string representation of each of our
        elements."""

        if self.recursing:
            return ''

        self.recursing = True
        try:
            return ','.join(elem.as_str() if elem is not None else ''
                            for elem in self.elements)
        finally:
            self.recursing = False


class JSWrapper(Hookable):
    """Acts as a mutable descriptor for an arbitrary JavaScript value,
    particularly those which act as L-values. Handles `on_set` hooks, and
    overwrite warnings for constant and other non-mutable properties."""

    __slots__ = ('__weakref__',
                 '_has_value',
                 '_location',
                 '_value',
                 'const',
                 'dirty',
                 'hooks',
                 'inferred',
                 'lvalue',
                 'name',
                 'parent',
                 'parse_node',
                 'set_by')

    def __init__(self, value=LazyJSObject, const=False, dirty=None, hooks=None,
                 parent=None, name='<unknown>', traverser=None, lvalue=False,
                 inferred=False):

        assert traverser is not None
        self.traverser = traverser

        self._location = traverser._location

        self._has_value = False
        self._value = value
        self.set_by = None

        self.hooks = hooks.copy() if hooks is not None else {}

        self.const = const
        # True if the existence of a property was inferred, because it was
        # accessed, rather than it being explicitly declared or assigned.
        self.inferred = inferred
        self.dirty = dirty if dirty is not None else (inferred and 'Inferred')
        self.lvalue = lvalue
        self.parent = parent
        self.name = name

    def __getattr__(self, name):
        """Proxy any reads from any unknown attributes to the JSValue object
        that we're wrapping."""

        if name in self.__slots__:
            # Don't proxy any attribute we're expected to define on ourselves,
            # even if we haven't done so yet.
            raise AttributeError()

        assert name != 'value'
        return getattr(self.value, name)

    @property
    def location(self):
        """Return the source location at which this wrapper was created."""
        return self.traverser.get_location(self._location)

    def as_primitive(self):
        """Return our value as a primitive, appending a special string to it
        if the wrapper is dirty."""
        val = self.value.as_primitive()
        if self.dirty and isinstance(val, basestring):
            return self.as_str()
        return val

    def as_str(self):
        """Return our value as a string, appending a special string to it if
        the wrapper is dirty."""
        val = self.value.as_str()
        if self.dirty:
            # For dirty values, append the value's unique ID, to prevent
            # different dirty values from matching the same object properties,
            # or comparing equal.
            return '{value}<dirty:{id:x}>'.format(
                value=val, id=id(self.value))
        return val

    def as_identifier(self):
        """Return our value as an identifier, appending a special string to it
        if the wrapper is dirty."""
        if self.dirty:
            return self.as_str()
        return self.value.as_identifier()

    def wrap_value(self, value):
        """Wrap a value with the appropriate JSValue type. Or unwrap it if it's
        already a JSWrapper."""
        if isinstance(value, JSWrapper):
            # Temporary special case until values have a `dirty` flag.
            if value.dirty:
                self.dirty = True
            return value.value

        try:
            init = self.value_initializers[type(value)]
        except KeyError:
            # Fall-backs for unexpected sub/superclasses.
            if isinstance(value, JSWrapper):
                init = self.value_initializers[JSWrapper]
            elif isinstance(value, JSValue):
                init = self.value_initializers[JSValue]
            elif isinstance(value, Iterable):
                init = self.value_initializers[list]
            else:
                raise ValueError()

        result = init(value, traverser=self.traverser)
        result.traverser = self.traverser
        assert not isinstance(result, JSWrapper)
        return result

    @property
    def value(self):
        """Lazily initialize any initial value we were instantiated with
        to an appropriate JSValue instance, and return that value."""
        try:
            if not self._has_value:
                # Lazily initialize any value we were passed in our
                # constructor, or cons a new empty JSObject if we weren't
                # given a value.
                value = self._value

                if 'value' in self.hooks:
                    value = self.hooks['value'](self.traverser)

                self._value = self.wrap_value(value)
                if self.dirty:
                    self._value.dirty = self.dirty
                self._has_value = True

                if self.hooks:
                    self._value.add_hooks(self.hooks)

                if (self.parent and
                        {'return', 'on_call'} & self._value.hooks.viewkeys()):
                    if getattr(self._value, 'parent', None) is None:
                        # In the cases of XPCOM objects, methods generally
                        # remain bound to their parent objects, even when
                        # called indirectly. Store our parent, for the sake of
                        # those methods.
                        self._value.parent = self.parent

            return self._value
        except Exception:
            # Python will eat these exceptions and fall back to __getattr__
            # if we don't manually do something about them here.
            self.traverser.system_error(exc_info=sys.exc_info())

    @value.setter
    def value(self, val):
        """Store the given value, triggering any hooks as necessary."""
        try:
            self.set_value(val)
        except Exception:
            # Python will eat these exceptions if we don't manually do
            # something about them here.
            self.traverser.system_error(exc_info=sys.exc_info())

    def set_value(self, value, set_by='<unknown>'):
        """Assign a value to the wrapper, triggering hooks as necessary."""

        if self.dirty == 'Inferred':
            self.dirty = False
        self.inferred = False

        if self.const:
            if (self._has_value or self._value is not LazyJSObject or
                    'value' in self.hooks or 'getter' in self.hooks):
                # This wrapper is flagged as non-writable.
                # If it's from a const declaration, we're safe accepting the
                # first write to the descriptor, since `const` declarations
                # are required to include an initializer value.
                # Any other wrapper marked const was created internally, and
                # should have been given an initial value, or include hooks
                # for lazy value initialization or getters.
                self.traverser.warning(
                    err_id=('testcases_javascript_traverser',
                            'JSWrapper_set_value', 'const_overwrite'),
                    warning='Constant value overwrite',
                    description='Values declared as constant may not be '
                                'overwritten.')
                return self.value

        self.set_by = set_by

        try:
            # Add ourselves to the list of wrappers changed in the current
            # conditional branch, so we can be marked as dirty when it exits.
            self.traverser.wrappers.add(self)
        except AttributeError:
            # If we're not currently in a conditional scope, there will be
            # no `wrappers` attribute, so ignore this error.
            pass

        # Wrap our value in the appropriate JSValue type and call any
        # applicable write hooks.
        value = self.wrap_value(value)
        value.traverser = self.traverser

        if self.hooks:
            value.add_hooks(self.hooks)

        if 'on_set' in self.hooks:
            self.fire_hooks('on_set', self, value)

        if not self.hooks.get('overwritable', True):
            # If the value is explicitly not overwritable, warn, but save
            # save the new value anyway, and copy over any hooks from the
            # old value.
            self.traverser.warning(
                err_id=('testcases_javascript_jstypes',
                        'JSWrapper_set_value', 'global_overwrite'),
                warning='Global overwrite',
                description='An attempt to overwrite a global variable '
                            'was made in some JS code.')

            value.add_hooks(self.value.hooks)

        if self.hooks.get('unwrapped'):
            self.traverser.warning(
                err_id=('testcases_javascript_jstypes', 'JSObject_set',
                        'unwrapped_js_object'),
                warning='Assignment to unwrapped object properties',
                description='Assigning to properties of content objects '
                            'without X-ray wrappers can lead to serious '
                            'security vulnerabilities. Please avoid waiving '
                            'X-ray wrappers whenever possible.',
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

        self._value = value
        self._has_value = True
        return value

    @property
    def is_clean_literal(self):
        """Return whether the content is known literal."""
        return not self.dirty and self.is_literal

    def add_hooks(self, hooks):
        """Wrap `Hookable.add_hooks` to add hooks to both the wrapper and the
        wrapped value, if our value has already been initialized."""
        if self._has_value:
            self.value.add_hooks(hooks)
        super(JSWrapper, self).add_hooks(hooks)

    def __repr__(self):
        keywords = []
        for keyword in ('dirty', 'hooks', 'inferred'):
            keywords.append('{key}={value}'.format(
                key=keyword,
                value=repr_hooks(getattr(self, keyword))))

        return '<{class_name}({value!r}, {keywords})>'.format(
            class_name=self.__class__.__name__,
            value=self.value,
            keywords=', '.join(keywords))

    def __unicode__(self):
        return unicode(self.as_str())

    # Wrappers around methods from our value. __getattr__ is not sufficient
    # for these.
    def __getitem__(self, key):
        return self.value.__getitem__(key)

    def __setitem__(self, key, value):
        return self.value.__setitem__(key, value)

    def __contains__(self, key):
        return self.value.__contains__(key)

    def __iter__(self):
        return self.value.__iter__()

    def __len__(self):
        return self.value.__len__()

    def __nonzero__(self):
        """Always treat JSWrapper instances as truthy, even though they behave
        as iterables."""
        return True

# A map of initializers for values of the given types. Used to wrap Python
# values in the correct type of `JSValue` when stored in a `JSWrapper`.
JSWrapper.value_initializers = {
    int: JSLiteral,
    long: JSLiteral,
    float: JSLiteral,
    bool: JSLiteral,
    str: JSLiteral,
    unicode: JSLiteral,
    type(None): JSLiteral,
    type(Undefined): JSLiteral,
    list: JSArray,
    tuple: JSArray,
    dict: JSObject,
    type(LazyJSObject): lambda sentinel, traverser: JSObject(),
    # Minor optimization. These will be caught by `instanceof` if this
    # lookup fails.
    JSArray: lambda value, traverser: value,
    JSContext: lambda value, traverser: value,
    JSLiteral: lambda value, traverser: value,
    JSValue: lambda value, traverser: value,
    JSObject: lambda value, traverser: value,
    JSWrapper: lambda wrapper, traverser: wrapper.value,
}
