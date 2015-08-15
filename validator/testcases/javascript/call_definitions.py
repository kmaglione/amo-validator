import math
import re

from .jstypes import JSArray

# Function prototypes should implement the following:
#  wrapper : The JSWrapper instace that is being called
#  arguments : A list of argument nodes; untraversed
#  traverser : The current traverser object


def xpcom_constructor(method, extend=False, mutate=False):
    """Returns a function which wraps an XPCOM class instantiation function."""

    def definition(this, args, callee):
        """Wraps an XPCOM class instantiation function."""

        if not args:
            return None

        traverser = this.traverser
        iface = args[0]

        if 'xpcom_map' not in iface.hooks:
            iface = traverser.wrap()
            iface.hooks = {'xpcom_map': lambda: {'value': {}}}

        inst = traverser._build_global(method, iface.hooks['xpcom_map']())
        inst.hooks['overwritable'] = True

        if extend or mutate:
            if mutate and 'value' not in this.hooks:
                # Assume that the parent object is a first class
                # wrapped native, and just copy our hooks to it.
                this.hooks = inst.hooks

            if extend and mutate:
                if callable(this.hooks['value']):
                    this.hooks['value'] = this.hooks['value'](this)

                this.hooks['value'].update(inst.hooks['value'])
                return this

            if extend:
                inst.hooks['value'].update(this.hooks['value'])

            if mutate:
                this.hooks = inst.hooks

        return inst
    definition.__name__ = 'xpcom_%s' % str(method)
    return definition


# Global object function definitions:
def string_global(this, args, callee):
    if not args:
        return this.traverser.wrap('')

    arg = args[0]
    return this.traverser.wrap(arg.as_str(), dirty=arg.dirty)


def array_global(this, args, callee):
    output = JSArray()
    output.elements = args
    return this.traverser.wrap(output)


def number_global(this, args, callee):
    if not args:
        return this.traverser.wrap(0)

    return this.traverser.wrap(args[0].as_float())


def boolean_global(this, args, callee):
    if not args:
        return this.traverser.wrap(False)
    return this.traverser.wrap(args[0].as_bool())


def python_wrap(func, arguments, nargs=False):
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

    def wrap(this, args, callee):
        params = []
        if not nargs:
            # Handle definite argument lists.
            for type_, def_value in arguments:
                if args:
                    parg = args.pop(0)

                    passed_literal = _process_literal(type_, parg)
                    params.append(passed_literal)
                else:
                    params.append(def_value)
        else:
            # Handle dynamic argument lists.
            for arg in args:
                params.append(_process_literal(arguments[0], arg))

        try:
            output = func(*params)
        except (ValueError, TypeError, OverflowError):
            # If we cannot compute output, just return nothing.
            output = None

        return this.traverser.wrap(output)

    return wrap


def math_log(this, args, callee):
    """Return a better value than the standard python log function."""
    traverser = this.traverser
    if not args:
        return traverser.wrap(0)

    arg = args[0].as_float()
    if arg == 0:
        return traverser.wrap(float('-inf'))

    if arg < 0:
        return traverser.wrap(None)

    return traverser.wrap(math.log(arg))


def math_random(this, args, callee):
    """Return a "random" value for Math.random()."""
    return this.traverser.wrap(0.5)


def math_round(this, args, callee):
    """Return a better value than the standard python round function."""
    if not args:
        return this.traverser.wrap(0)

    arg = args[0].as_float()
    # Prevent nasty infinity tracebacks.
    if abs(arg) == float('inf'):
        return args[0]

    # Python rounds away from zero, JS rounds "up".
    if arg < 0 and int(arg) != arg:
        arg += 0.0000000000000001
    arg = round(arg)
    return this.traverser.wrap(arg)


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
