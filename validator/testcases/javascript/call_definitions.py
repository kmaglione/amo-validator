import math
import re

import actions
from .jstypes import JSArray

# Function prototypes should implement the following:
#  wrapper : The JSWrapper instace that is being called
#  arguments : A list of argument nodes; untraversed
#  traverser : The current traverser object


def xpcom_constructor(method, extend=False, mutate=False, pretraversed=False):
    """Returns a function which wraps an XPCOM class instantiation function."""

    def definition(wrapper, arguments, traverser):
        """Wraps an XPCOM class instantiation function."""

        if not arguments:
            return None

        traverser._debug('(XPCOM Encountered)')

        if not pretraversed:
            arguments = [traverser._traverse_node(x) for x in arguments]
        argz = arguments[0]

        if 'xpcom_map' not in argz.hooks:
            argz = traverser.wrap()
            argz.hooks = {'xpcom_map': lambda: {'value': {}}}

        traverser._debug('(Building XPCOM...)')

        inst = traverser._build_global(
            method, argz.hooks['xpcom_map']())
        inst.hooks['overwritable'] = True

        if extend or mutate:
            # FIXME: There should be a way to get this without
            # traversing the call chain twice.
            parent = actions.trace_member(traverser,
                                          wrapper['callee']['object'])

            if mutate and 'value' not in parent.hooks:
                # Assume that the parent object is a first class
                # wrapped native, and just copy our hooks to it.
                parent.hooks = inst.hooks

            if extend and mutate:
                if callable(parent.hooks['value']):
                    parent.hooks['value'] = \
                        parent.hooks['value'](t=traverser)

                parent.hooks['value'].update(inst.hooks['value'])
                return parent

            if extend:
                inst.hooks['value'].update(parent.hooks['value'])

            if mutate:
                parent.hooks = inst.hooks

        return inst
    definition.__name__ = 'xpcom_%s' % str(method)
    return definition


# Global object function definitions:
def string_global(wrapper, arguments, traverser):
    if not arguments:
        return traverser.wrap('')

    arg = traverser._traverse_node(arguments[0])
    return traverser.wrap(arg.as_str(), dirty=arg.dirty)


def array_global(wrapper, arguments, traverser):
    output = JSArray()
    if arguments:
        output.elements = [traverser._traverse_node(a) for a in arguments]
    return traverser.wrap(output)


def number_global(wrapper, arguments, traverser):
    if not arguments:
        return traverser.wrap(0)
    arg = traverser._traverse_node(arguments[0])
    return traverser.wrap(arg.as_float())


def boolean_global(wrapper, arguments, traverser):
    if not arguments:
        return traverser.wrap(False)
    arg = traverser._traverse_node(arguments[0])
    return traverser.wrap(arg.as_bool())


def python_wrap(func, args, nargs=False):
    """
    This is a helper function that wraps Python functions and exposes them to
    the JS engine. The first parameter should be the Python function to wrap.
    The second parameter should be a list of tuples. Each tuple should
    contain:

     1. The type of value to expect:
        - "string"
        - "num"
     2. A default value.
    """

    def _process_literal(type_, literal):
        if type_ == 'string':
            return literal.as_str()
        elif type_ == 'num':
            return literal.as_float()
        return literal.as_primitive()

    def wrap(wrapper, arguments, traverser):
        passed_args = [traverser._traverse_node(a) for a in arguments]

        params = []
        if not nargs:
            # Handle definite argument lists.
            for type_, def_value in args:
                if passed_args:
                    parg = passed_args[0]
                    passed_args = passed_args[1:]

                    passed_literal = _process_literal(type_, parg)
                    params.append(passed_literal)
                else:
                    params.append(def_value)
        else:
            # Handle dynamic argument lists.
            for arg in passed_args:
                params.append(_process_literal(args[0], arg))

        traverser._debug('Calling wrapped Python function with: (%s)' %
                         ', '.join(map(str, params)))
        try:
            output = func(*params)
        except (ValueError, TypeError, OverflowError):
            # If we cannot compute output, just return nothing.
            output = None

        return traverser.wrap(output)

    return wrap


def math_log(wrapper, arguments, traverser):
    """Return a better value than the standard python log function."""
    args = [traverser._traverse_node(a) for a in arguments]
    if not args:
        return traverser.wrap(0)

    arg = args[0].as_float()
    if arg == 0:
        return traverser.wrap(float('-inf'))

    if arg < 0:
        return traverser.wrap(None)

    return traverser.wrap(math.log(arg))


def math_random(wrapper, arguments, traverser):
    """Return a "random" value for Math.random()."""
    return traverser.wrap(0.5)


def math_round(wrapper, arguments, traverser):
    """Return a better value than the standard python round function."""
    args = [traverser._traverse_node(a) for a in arguments]
    if not args:
        return traverser.wrap(0)

    arg = args[0].as_float()
    # Prevent nasty infinity tracebacks.
    if abs(arg) == float('inf'):
        return args[0]

    # Python rounds away from zero, JS rounds "up".
    if arg < 0 and int(arg) != arg:
        arg += 0.0000000000000001
    arg = round(arg)
    return traverser.wrap(arg)


def open_in_chrome_context(uri, method, traverser):
    if not uri.is_clean_literal():
        traverser.err.notice(
            err_id=('js', 'instanceactions', '%s_nonliteral' % method),
            notice='`%s` called with non-literal parameter.' % method,
            description='Calling `%s` with variable parameters can result in '
                        'potential security vulnerabilities if the variable '
                        'contains a remote URI. Consider using `window.open` '
                        'with the `chrome=no` flag.' % method,
            filename=traverser.filename,
            line=traverser.line,
            column=traverser.position,
            context=traverser.context)

    remote_url = re.compile(r'^(https?|ftp|data):(//)?', re.I)
    uri = uri.as_str()
    if uri.startswith('//') or remote_url.match(uri):
        traverser.warning(
            err_id=('js', 'instanceactions', '%s_remote_uri' % method),
            warning='`%s` called with non-local URI.' % method,
            description='Calling `%s` with a non-local URI will result in the '
                        'dialog being opened with chrome privileges.' % method)
