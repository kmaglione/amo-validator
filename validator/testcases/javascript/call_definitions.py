import math
import re

import actions
import predefinedentities
from jstypes import JSArray, JSWrapper

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

        if not argz.is_global or 'xpcom_map' not in argz.value:
            argz = JSWrapper(traverser=traverser)
            argz.value = {'xpcom_map': lambda: {'value': {}}}

        traverser._debug('(Building XPCOM...)')

        inst = traverser._build_global(
            method, argz.value['xpcom_map']())
        inst.value['overwritable'] = True

        if extend or mutate:
            # FIXME: There should be a way to get this without
            # traversing the call chain twice.
            parent = actions.trace_member(traverser,
                                          wrapper['callee']['object'])

            if mutate and not (parent.is_global and
                               isinstance(parent.value, dict) and
                               'value' in parent.value):
                # Assume that the parent object is a first class
                # wrapped native
                parent.value = inst.value

                # FIXME: Only objects marked as global are processed
                # as XPCOM instances
                parent.is_global = True

            if isinstance(parent.value, dict):
                if extend and mutate:
                    if callable(parent.value['value']):
                        parent.value['value'] = \
                            parent.value['value'](t=traverser)

                    parent.value['value'].update(inst.value['value'])
                    return parent

                if extend:
                    inst.value['value'].update(parent.value['value'])

                if mutate:
                    parent.value = inst.value

        return inst
    definition.__name__ = 'xpcom_%s' % str(method)
    return definition


# Global object function definitions:
def string_global(wrapper, arguments, traverser):
    if not arguments:
        return JSWrapper('', traverser=traverser)
    arg = traverser._traverse_node(arguments[0])
    value = actions._get_as_str(arg.get_literal_value())
    return JSWrapper(value, traverser=traverser)


def array_global(wrapper, arguments, traverser):
    output = JSArray()
    if arguments:
        output.elements = [traverser._traverse_node(a) for a in arguments]
    return JSWrapper(output, traverser=traverser)


def number_global(wrapper, arguments, traverser):
    if not arguments:
        return JSWrapper(0, traverser=traverser)
    arg = traverser._traverse_node(arguments[0])
    try:
        value = float(arg.get_literal_value())
    except (ValueError, TypeError):
        return traverser._build_global(
                name='NaN',
                entity=predefinedentities.GLOBAL_ENTITIES[u'NaN'])
    return JSWrapper(value, traverser=traverser)


def boolean_global(wrapper, arguments, traverser):
    if not arguments:
        return JSWrapper(False, traverser=traverser)
    arg = traverser._traverse_node(arguments[0])
    return JSWrapper(bool(arg.get_literal_value()), traverser=traverser)


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
            return actions._get_as_str(literal)
        elif type_ == 'num':
            return actions._get_as_num(literal)
        return literal

    def wrap(wrapper, arguments, traverser):
        passed_args = [traverser._traverse_node(a) for a in arguments]

        params = []
        if not nargs:
            # Handle definite argument lists.
            for type_, def_value in args:
                if passed_args:
                    parg = passed_args[0]
                    passed_args = passed_args[1:]

                    passed_literal = parg.get_literal_value()
                    passed_literal = _process_literal(type_, passed_literal)
                    params.append(passed_literal)
                else:
                    params.append(def_value)
        else:
            # Handle dynamic argument lists.
            for arg in passed_args:
                literal = arg.get_literal_value()
                params.append(_process_literal(args[0], literal))

        traverser._debug('Calling wrapped Python function with: (%s)' %
                         ', '.join(map(str, params)))
        try:
            output = func(*params)
        except (ValueError, TypeError, OverflowError):
            # If we cannot compute output, just return nothing.
            output = None

        return JSWrapper(output, traverser=traverser)

    return wrap


def math_log(wrapper, arguments, traverser):
    """Return a better value than the standard python log function."""
    args = [traverser._traverse_node(a) for a in arguments]
    if not args:
        return JSWrapper(0, traverser=traverser)

    arg = actions._get_as_num(args[0].get_literal_value())
    if arg == 0:
        return JSWrapper(float('-inf'), traverser=traverser)

    if arg < 0:
        return JSWrapper(traverser=traverser)

    arg = math.log(arg)
    return JSWrapper(arg, traverser=traverser)


def math_random(wrapper, arguments, traverser):
    """Return a "random" value for Math.random()."""
    return JSWrapper(0.5, traverser=traverser)


def math_round(wrapper, arguments, traverser):
    """Return a better value than the standard python round function."""
    args = [traverser._traverse_node(a) for a in arguments]
    if not args:
        return JSWrapper(0, traverser=traverser)

    arg = actions._get_as_num(args[0].get_literal_value())
    # Prevent nasty infinity tracebacks.
    if abs(arg) == float('inf'):
        return args[0]

    # Python rounds away from zero, JS rounds "up".
    if arg < 0 and int(arg) != arg:
        arg += 0.0000000000000001
    arg = round(arg)
    return JSWrapper(arg, traverser=traverser)


def open_in_chrome_context(uri, method, traverser):
    if not uri.is_literal():
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
    uri = unicode(uri.get_literal_value())
    if uri.startswith('//') or remote_url.match(uri):
        traverser.warning(
            err_id=('js', 'instanceactions', '%s_remote_uri' % method),
            warning='`%s` called with non-local URI.' % method,
            description='Calling `%s` with a non-local URI will result in the '
                        'dialog being opened with chrome privileges.' % method)
