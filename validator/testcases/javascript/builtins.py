from __future__ import absolute_import, print_function, unicode_literals

import math
import re
import urllib
from functools import wraps

from .jstypes import Global, Hook, JSArray, Undefined


@Global.hook('encodeURI', 'return')
def encodeURI(this, args, callee):
    return (urllib.quote(args[0].as_str().encode('utf-8'))
            .decode('utf-8'))


@Global.hook('escape', 'return')
@Global.hook('encodeURIComponent', 'return')
def encodeURIComponent(this, args, callee):
    return (urllib.quote_plus(args[0].as_str().encode('utf-8'))
            .decode('utf-8'))


@Global.hook('decodeURI', 'return')
def decodeURI(this, args, callee):
    return (urllib.unquote(args[0].as_str().encode('utf-8'))
            .decode('utf-8', errors='replace'))


@Global.hook('unescape', 'return')
@Global.hook('decodeURIComponent', 'return')
def decodeURIComponent(this, args, callee):
    return (urllib.unquote_plus(args[0].as_str().encode('utf-8'))
            .decode('utf-8', errors='replace'))


# Primitives:

# Belongs in `Function.prototype`, as soon as we have support.
@Global.hook(('**', 'bind'), 'return')
def bind(this, args, callee):
    if this.callable:
        return this


# Prototypes of built-in types.

def readonly_if_shared(this, value, name=None):
    """Emit a warning when the prototype of a built-in object is altered
    or extended while running in a shared scope.

    Currently, this only applies to scripts which we can reliably detect
    as overlays, via chrome.manifest and XUL overlay files. However,
    scripts are commonly loaded into shared scopes by other means, so this
    is somewhat less than ideal."""

    if this.traverser.pollutable:
        return {'err_id': 'prototype-extension',
                'warning': 'JavaScript native prototype extension',
                'description':
                    'Due to interoperability concerns, extensions may '
                    'not extend the prototypes of native objects when '
                    'running in a shared scope.'}

for constructor in ('Array',
                    'Boolean',
                    'Date',
                    'File',
                    'Function',
                    'Number',
                    'Object',
                    'RegExp',
                    'String'):
    Global.hook((constructor, 'prototype'), on_set=readonly_if_shared)
    Global.hook((constructor, 'prototype', '*'), on_set=readonly_if_shared)


def math_fun(fn):
    """Wrap math functions to return NaN on error, as JavaScript would, rather
    than raise a ValueError, as Python would."""

    @wraps(fn)
    def wrapper(this, args, callee):
        try:
            return fn(args)
        except (ValueError, OverflowError):
            return float('nan')
    return wrapper


@Global.extend
class Builtins(Hook):

    Infinity = {'value': lambda traverser: float('inf'), 'const': True}
    NaN = {'value': lambda traverser: float('nan'), 'const': True}

    undefined = {'value': lambda traverser: Undefined, 'const': True}
    null = {'value': lambda traverser: None, 'const': True}

    def Array(this, args, callee):
        # This is wrong.
        return JSArray(args, traverser=this.traverser)

    def Boolean(this, args, callee):
        return args[0].as_bool()

    class Number(Hook):
        def __call__(this, args, callee):
            return args[0].as_float() if args else 0

        POSITIVE_INFINITY = {'value': lambda traverser: float('inf')}
        NEGATIVE_INFINITY = {'value': lambda traverser: float('-inf')}

    def String(this, args, callee):
        return args[0].as_str()

    def isNaN(this, args, callee):
        return math.isnan(args[0].as_float())

    def isFinite(this, args, callee):
        arg = args[0].as_float()
        return not (math.isnan(arg) or math.isinf(arg))

    @math_fun
    def parseInt(args):
        arg = args[0].as_str().strip().lower()
        base = args[1].as_int()

        # JavaScript.
        if arg.startswith(('0x', '-0x', '+0x')):
            res = re.match('[+-]?0x[0-9a-f]+', arg)
            if res:
                if base in (0, 16):
                    return int(res.group(0), 16)
                return 0
            return float('nan')

        res = re.match('[+-]?\d+', arg)
        if res:
            return int(res.group(0), base)

        return float('nan')

    @math_fun
    def parseFloat(args):
        arg = args[0].as_str().strip()
        res = re.match('([+-]?)(\d+(\.\d*)?|Infinity)', arg)

        if res:
            if res.group(2) == 'Infinity':
                return float(res.group(1) + 'inf')

            return float(res.group(0))

        return float('nan')


@Global.hook
class Math(Hook):
    PI = {'value': lambda traverser: math.pi}

    E = {'value': lambda traverser: math.e}

    LN2 = {'value': lambda traverser: math.log(2)}

    LN10 = {'value': lambda traverser: math.log(10)}

    LOG2E = {'value': lambda traverser: math.log(math.e, 2)}

    LOG10E = {'value': lambda traverser: math.log10(math.e)}

    SQRT2 = {'value': lambda traverser: math.sqrt(2)}

    SQRT1_2 = {'value': lambda traverser: math.sqrt(1/2)}

    def random(this, args, callee):
        # Meh.
        return 0.5

    @math_fun
    def sin(args):
        return math.sin(args[0].as_float())

    @math_fun
    def cos(args):
        return math.cos(args[0].as_float())

    @math_fun
    def tan(args):
        return math.tan(args[0].as_float())

    @math_fun
    def asin(args):
        return math.asin(args[0].as_float())

    @math_fun
    def acos(args):
        return math.acos(args[0].as_float())

    @math_fun
    def atan(args):
        return math.atan(args[0].as_float())

    @math_fun
    def atan2(args):
        return math.atan2(args[0].as_float(), args[1].as_float())

    @math_fun
    def exp(args):
        return math.exp(args[0].as_float())

    @math_fun
    def pow(args):
        return math.pow(args[0].as_float(), args[1].as_float())

    @math_fun
    def sqrt(args):
        return math.sqrt(args[0].as_float())

    @math_fun
    def floor(args):
        return math.floor(args[0].as_float())

    @math_fun
    def ceil(args):
        return math.ceil(args[0].as_float())

    @math_fun
    def abs(args):
        return abs(args[0].as_float())

    @math_fun
    def min(args):
        return min(arg.as_float() for arg in args)

    @math_fun
    def max(args):
        return max(arg.as_float() for arg in args)

    @math_fun
    def round(args):
        """Wrap the `round` built-in to mimic JavaScript's rounding behavior
        or negative numbers."""
        arg = args[0].as_float()

        if arg < 0 and not arg.is_integer() and arg % 0.5 == 0:
            # Round up for negative values exactly divisible by 0.5.
            return arg + 0.5

        return round(arg)

    @math_fun
    def log(args):
        """Wrap the `math.log` built-in to mimic JavaScript's rounding behavior
        or the value 0."""
        arg = args[0].as_float()

        if arg == 0:
            return float('-inf')
        return math.log(arg)
