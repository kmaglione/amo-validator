from __future__ import absolute_import, print_function, unicode_literals

import re
from functools import partial, wraps
from weakref import WeakSet

from validator.constants import MAX_STR_SIZE

from ..regex import validate_string
from .jstypes import Args, JSArray, JSContext, JSObject, Undefined


def clean_dirty(value):
    """Given a dirty literal string, clean up repeated occurrences of
    '[object Object]."""
    return re.sub(r'(?:\[object Object]){2,}', '[object Object]', value)


def operator(op):
    """Mark the decorated function as a handler for the given operator, `op`.
    When applied to a method of an `Operators` subclass, the method is added
    to the operators dict for instances of the class:

        class BinOps(Operators):
            @operator('+')
            def add(self, a, b):
                pass

        bin_ops = BinOps()
        assert bin_ops['+'] is bin_ops.add
    """
    def decorator(fn):
        fn.operator = op
        return fn
    return decorator


def relational_operator(op):
    """Wrap an operator method so that its values are both of the correct
    primitive type for a relational comparison."""
    def decorator(fn):
        @operator(op)
        @wraps(fn)
        def wrapper(self, left, right):
            left, right = self.relational_values(left, right)
            return fn(self, left, right)
        return wrapper
    return decorator


def node_handler(fn):
    """Mark a method of an Operators subclass as a handler for the JavaScript
    parse node of the same name."""
    fn.operator = fn.__name__
    return fn


class Operators(dict):
    """Acts as a look-up table for arbitrary operators, mapping them to the
    appropriate instance methods. See @operator for more details."""

    class __metaclass__(type):
        def __new__(mcls, name, bases, dict_):
            cls = type.__new__(mcls, name, bases, dict_)
            cls.OPERATORS = {method.operator: name
                             for name, method in dict_.iteritems()
                             if getattr(method, 'operator', None)}
            return cls

    def __new__(cls, *args, **kw):
        self = super(Operators, cls).__new__(cls, *args, **kw)
        for op, method in cls.OPERATORS.iteritems():
            self[op] = getattr(self, method)
        return self

    def __init__(self, traverser):
        self.traverser = traverser


class BinaryOps(Operators):
    """A look-up table for JavaScript binary operator handlers."""

    def relational_values(self, left, right):
        """Converts two JS values to the primitive types that JavaScript
        would use for relational operators."""
        if (isinstance(left.as_primitive(), basestring) and
                isinstance(right.as_primitive(), basestring)):
            # If both values are strings, we compare them as strings.
            return left.as_str(), right.as_str()

        # Otherwise, we compare them as numbers.
        return left.as_float(), right.as_float()

    @operator('==')
    def equal(self, left, right):
        """Return true if values would compare equal in JavaScript."""
        if left.typeof == right.typeof:
            # The two values are of the same JS type. Use strict equality.
            return self.identical(left, right)

        # Because JavaScript:

        # `x` and `y` per the ECMAScript spec.
        x = left.as_primitive()
        y = right.as_primitive()

        if x == y or x in (None, Undefined) and y in (None, Undefined):
            return True

        number = (int, long, float, bool)
        if (isinstance(x, basestring) and isinstance(y, number) or
                isinstance(y, basestring) and isinstance(x, number)):
            # One string and one number. Coerce both to numbers.
            return left.as_float() == right.as_float()

        # Close enough.
        return left.as_str() == right.as_str()

    @operator('!=')
    def not_equal(self, left, right):
        """Return true if values would not compare equal in JavaScript."""
        return not self.equal(left, right)

    @operator('===')
    def identical(self, left, right):
        """Return true if values would compare as identical in JavaScript."""
        if left.is_literal and right.is_literal:
            return left.as_primitive() == right.as_primitive()

        return left.value is right.value

    @operator('!==')
    def not_identical(self, left, right):
        """Return true if values would not compare as identical in
        JavaScript."""
        return not self.identical(left, right)

    @relational_operator('>')
    def greater(self, left, right):
        """Return true if `left` would compare greater than `right` in
        JavaScript."""
        return left > right

    @relational_operator('<')
    def less(self, left, right):
        """Return true if `left` would compare less than `right` in
        JavaScript."""
        return left < right

    @relational_operator('>=')
    def gte(self, left, right):
        """Return true if `left` would compare grater than or equal to `right`
        in JavaScript."""
        return left >= right

    @relational_operator('<=')
    def lte(self, left, right):
        """Return true if `left` would less grater than or equal to `right`
        in JavaScript."""
        return left <= right

    @operator('<<')
    def left_shift(self, left, right):
        """Arithmetically bit-shift `left`, `right` places to the left."""
        return left.as_int() << (right.as_int() & 0x7fffffff)

    @operator('>>')
    def right_shift(self, left, right):
        """Arithmetically bit-shift `left`, `right` places to the right."""
        return left.as_int() >> (right.as_int() & 0x7fffffff)

    @operator('>>>')
    def logical_right_shift(self, left, right):
        """Logically bit-shift `left`, `right` places to the right."""
        # This is wrong.
        return abs(left.as_int()) >> (right.as_int() & 0x7fffffff)

    @operator('+')
    def add(self, left, right):
        """Add `left` to `right`, with JavaScript-compatible coersions."""
        if (isinstance(left.as_primitive(), basestring) or
                isinstance(right.as_primitive(), basestring)):
            # If either value, when coerced to a primitive, is a string,
            # the operation becomes a string addition operation.
            return left.as_str() + right.as_str()

        return left.as_float() + right.as_float()

    @operator('-')
    def sub(self, left, right):
        """Subtract `left` from `right`."""
        return left.as_float() - right.as_float()

    @operator('*')
    def multiply(self, left, right):
        """Multiply `left` by `right`."""
        return left.as_float() * right.as_float()

    @operator('/')
    def divide(self, left, right):
        """Divide `left` by `right`."""
        try:
            return left.as_float() / right.as_float()
        except ZeroDivisionError:
            # JavaScript treats this as positive or negative Infinity.
            return left.as_float() * float('inf')

    @operator('%')
    def modulo(self, left, right):
        """Return `left` modulo `right`."""
        try:
            return left.as_float() % right.as_float()
        except ZeroDivisionError:
            # JavaScript treats this as NaN
            return float('nan')

    @operator('&')
    def bin_and(self, left, right):
        """Coerce both values to integers and return their binary AND."""
        return left.as_int() & right.as_int()

    @operator('|')
    def bin_or(self, left, right):
        """Coerce both values to integers and return their binary OR."""
        return left.as_int() | right.as_int()

    @operator('^')
    def bin_xor(self, left, right):
        """Coerce both values to integers and return their binary XOR."""
        return left.as_int() ^ right.as_int()

    @operator('in')
    def in_(self, left, right):
        """Return true if `right` is an object and contains `left`."""
        return right.contains(left)

    @operator('instanceof')
    def instanceof(self, left, right):
        """Return true if `left` is an instance of `right`."""
        left.query_interface(right)
        return False


class UnaryOps(Operators):
    """A look-up table for JavaScript unary operator handlers."""

    @operator('-')
    def minus(self, value):
        """Coerce value to a number and return its negative."""
        return -1 * value.as_float()

    @operator('+')
    def plus(self, value):
        """Return value coerced to a number."""
        return value.as_float()

    @operator('!')
    def not_(self, value):
        """Coerce value to a boolean and return its inverse."""
        return not value.as_bool()

    @operator('~')
    def neg(self, value):
        """Coerce value to an integer and return its 1's complement inverse."""
        return ~value.as_int()

    @operator('void')
    def void(self, value):
        """Return `undefined`."""
        return Undefined

    @operator('typeof')
    def typeof(self, value):
        """Return the JavaScript type of `value`."""
        return value.typeof

    @operator('delete')
    def delete(self, wrapper):
        """Set a wrapper's value to `undefined`, but do not delete it"""
        # If we actually delete the wrapper, we can't check its values
        # across branches. Just set its value to undefined.
        wrapper.set_value(Undefined, set_by='delete operator')
        return Undefined


class ObjectKeys(Operators):
    """A look-up table for JavaScript parse nodes used to specify key names
    in object literals. See `NodeHandlers.ObjectExpression` for usage."""

    @node_handler
    def Identifier(self, node):
        """Handle a property name specified as an identifier, which is coerced
        into a literal:

            var obj = {identifier: "value"};
        """

        return node['name']

    @node_handler
    def Literal(self, node):
        """Handle a property name defined as a literal:

            var obj = {"literal": "value", 42: value};
        """

        return node['value']

    @node_handler
    def ComputedName(self, node):
        """Handle a property name computed from an arbitrary JavaScript
        expression:

            var obj = {[computed_name]: "value"};
        """
        return self.traverser.traverse(node, 'name').as_identifier()


class NodeHandlers(Operators):
    """A look-up table for all JavaScript parse nodes, excluding those which
    are handled specially. This is the core of our tree-walker, and is
    responsible for handling every node in the parse tree.

    Each handler must traverse all child nodes for the node it is handling,
    adding and removing the correct entries to/from the context stack as it
    does so."""

    def __init__(self, traverser):
        super(NodeHandlers, self).__init__(traverser)

        self.binary_ops = BinaryOps(traverser)
        self.unary_ops = UnaryOps(traverser)
        self.object_keys = ObjectKeys(traverser)

        self.traverse = traverser.traverse
        self.find_scope = traverser.find_scope

        self.ONE = self.traverser.wrap(1).value

        traverser.conditionals = []

        class Conditional(WeakSet):
            def cleanup(self):
                for wrapper in self:
                    wrapper.dirty = 'ConditionalScopePop'

                try:
                    traverser.wrappers = traverser.conditionals[-2]
                except IndexError:
                    del traverser.wrappers
        self.Conditional = Conditional

        class PopContext(object):
            """A context manager to pop the top entry from the context stack
            on exit, and perform any cleanup that context requires if there
            are no duplicates elsewhere in the stack."""

            def __init__(self, stack):
                self.stack = stack

            def __enter__(self):
                return self.stack[-1]

            def __exit__(self, type_, value, traceback):
                context = self.stack[-1]

                # Thanks to the magic of `with` statements, we might
                # have the same context in the stack multiple times.
                if context not in self.stack[:-1]:
                    if hasattr(context, 'cleanup'):
                        context.cleanup()

                self.stack.pop()

        class PopConditional(PopContext):
            """A context manager to pop the top entry from the conditional
            stack on exit. This is exactly the same as `PopContext`, but
            performs cleanup regardless of whether there are duplicate entries
            for the element being popped."""

            def __exit__(self, type_, value, traceback):
                # The duplicate check above is non-trivially expensive,
                # since sets will be compared by values, rather than strict
                # identity.
                self.stack[-1].cleanup()
                self.stack.pop()

        self._context_manager = PopContext(traverser.contexts)
        self._conditional_manager = PopConditional(traverser.conditionals)

    def assign_value(self, left, right, set_by='<unknown>'):
        """Handle an assignment operation where the left-hand-side may be
        either a simple L-value wrapper or a destructuring pattern."""

        if isinstance(left, list):
            # Array destructuring pattern.
            for i, item in enumerate(left):
                self.assign_value(item, right[i], set_by=set_by)
        elif isinstance(left, dict):
            # Object destructuring pattern.
            for key, item in left.iteritems():
                self.assign_value(item, right[key], set_by=set_by)
        elif left is not None:
            # Set the current location to the location of the wrapper
            # we're currently assigning to, rather than the end of the
            # current value.
            self.traverser.set_location(left.parse_node)

            left.set_value(right, set_by=set_by)

    def binary_op(self, operator, left, right):
        """Perform a binary operation on two values."""

        if operator in ('==', '===', '!=', '!==', 'delete'):
            # Special case: equality operators compare wrapper values, since
            # they may annotate their coerced values to effect equality
            # comparisons when they're dirty. Other operators need to operate
            # on non-annotated values, for the moment, so that we don't get
            # multiple <dirty> indicators in the final result.
            #
            # The delete operator needs to operate on a wrapper, since it
            # changes its value.
            value = self.binary_ops[operator](left, right)
        else:
            value = self.binary_ops[operator](left.value, right.value)

        dirty = left.dirty or right.dirty
        if isinstance(value, basestring):
            value = value[:MAX_STR_SIZE]
            if dirty:
                value = clean_dirty(value)

        wrapper = self.traverser.wrap(value, dirty=dirty)

        # Test the newly-created literal for dangerous values.
        # This may cause duplicate warnings for strings which
        # already match a dangerous value prior to concatenation.
        if not dirty and isinstance(value, basestring):
            self.test_literal(value, wrapper)

        return wrapper

    def test_literal(self, string, wrapper):
        """
        Test the value of a literal, in particular only a string literal at the
        moment, against possibly dangerous patterns.
        """
        if string != '[object Object]':
            validate_string(string, traverser=self.traverser, wrapper=wrapper)

    def push_context(self, context):
        """Push a context onto the stack, and return a context manager which
        will pop it upon exit. `context` may be either a `JSObject` value,
        which will be pushed onto the stack directly, or a string, in which
        case a context of that type will be created."""

        if isinstance(context, basestring):
            context = JSContext(context_type=context,
                                traverser=self.traverser)

        self.traverser.contexts.append(context)
        return self._context_manager

    def push_conditional(self):
        """Push a conditional scope onto the stack, and return a context
        manager which will pop it upon exit. When the scope is popped,
        any wrappers which changed value while it was on the stack will
        be marked as dirty."""

        self.traverser.wrappers = self.Conditional()
        self.traverser.conditionals.append(self.traverser.wrappers)

        return self._conditional_manager

    @node_handler
    def EmptyStatement(self, node):
        """An empty statement, such as an empty line with a trailing
        semicolon."""

    @node_handler
    def DebuggerStatement(self, node):
        """A `debugger` statement."""

    @node_handler
    def Program(self, node):
        """Node representing the entire body of a script."""
        for elem in node['body']:
            self.traverse(elem)

    @node_handler
    def BlockStatement(self, node):
        """A block statement `{ ... }`, including its body."""
        with self.push_context('block'):
            for elem in node['body']:
                self.traverse(elem)

    @node_handler
    def ExpressionStatement(self, node):
        """An arbitrary expression, which has a value."""
        return self.traverse(node, 'expression')

    @node_handler
    def IfStatement(self, node):
        """An `if` statement, including its test, and a possible else
        statement."""

        self.traverse(node, 'test')

        with self.push_conditional():
            # The body of the if statement.
            self.traverse(node, 'consequent')

        with self.push_conditional():
            # Any else statement that comes after.
            self.traverse(node, 'alternate')

    @node_handler
    def LabeledStatement(self, node):
        """A label for a loop statement, and the loop itself."""
        self.traverse(node, 'body')

    @node_handler
    def BreakStatement(self, node):
        """A `break` statement."""

    @node_handler
    def ContinueStatement(self, node):
        """A `continue` statement."""

    @node_handler
    def WithStatement(self, node):
        """A `with` statement, including the expression which evaluates to the
        context object, and the body of the statement."""

        object_ = self.traverse(node, 'object')

        with self.push_context(object_.value):
            self.traverse(node, 'body')

    @node_handler
    def SwitchStatement(self, node):
        """A switch statement, including the expression which evaluates to the
        discriminant value, and the body containg the `case` statements."""

        self.traverse(node, 'discriminant')
        with self.push_context('block'):
            for case in node['cases']:
                self.traverse(case)

    @node_handler
    def SwitchCase(self, node):
        """A `case` statement, including the expression which evaluates to the
        test value, and any consequent statements."""

        with self.push_conditional():
            self.traverse(node, 'test')
            for expr in node['consequent']:
                self.traverse(expr)

    @node_handler
    def ReturnStatement(self, node):
        """A `return` statement."""

    @node_handler
    def ThrowStatement(self, node):
        """A `throw` statement, inclusing its argument."""
        self.traverse(node, 'argument')

    @node_handler
    def TryStatement(self, node):
        """A try statement, including its `catch` handler, guards, and
        finalizer."""

        with self.push_conditional():
            self.traverse(node, 'block')

        for handler in node['guardedHandlers']:
            self.traverse(handler)

        self.traverse(node, 'handler')

        with self.push_conditional():
            self.traverse(node, 'finalizer')

    @node_handler
    def CatchClause(self, node):
        """A catch clause for a try block, including a block-scoped parameter
        name, a possible guard, and a body."""

        with self.push_conditional():
            with self.push_context('block'):
                self.traverse(node, 'param', declare='let')
                self.traverse(node, 'guard')
                self.traverse(node, 'body')

    @node_handler
    def WhileStatement(self, node):
        """A `while` statement, including the test and body."""

        with self.push_conditional():
            self.traverse(node, 'test')
            self.traverse(node, 'body')

    @node_handler
    def DoWhileStatement(self, node):
        """A `while` statement, including the test and body."""

        with self.push_conditional():
            self.traverse(node, 'body')
            self.traverse(node, 'test')

    @node_handler
    def ForStatement(self, node):
        """A C-style `for` statement, including the initializer, test, and
        update statements, as well as the body."""

        self.traverse(node, 'init')

        with self.push_conditional():
            self.traverse(node, 'test')
            self.traverse(node, 'body')
            self.traverse(node, 'update')

    @node_handler
    def ForInStatement(self, node):
        """A for-in statement, including the variable left-hand-side, the
        iterator target right-hand-side, and the body."""

        self.traverse(node, 'left', declare='global')
        self.traverse(node, 'right')
        with self.push_conditional():
            self.traverse(node, 'body')

    @node_handler
    def ForOfStatement(self, node):
        """A for-of statement, including the variable left-hand-side, the
        iterator target right-hand-side, and the body."""

        self.traverse(node, 'left', declare='global')
        self.traverse(node, 'right')
        with self.push_conditional():
            self.traverse(node, 'body')

    @node_handler
    def VariableDeclaration(self, node, declare=None):
        """A variable declaration statement, one of `var`, `let`, or `const`,
        including sub-VariableDeclarator statements containing individual
        declarations."""

        for declaration in node['declarations']:
            self.traverse(declaration, declare=node['kind'])

    @node_handler
    def VariableDeclarator(self, node, declare):
        """A variable declaration within a `var`/`let`/`const` statement."""

        left = self.traverse(node, 'id', declare=declare)

        if node['init']:
            right = self.traverse(node, 'init')

            self.assign_value(left, right,
                              set_by='{0} declaration'.format(declare))

    @node_handler
    def LetStatement(self, node):
        """A `let` block, including a head with individual declarations,
        and a block body into which the declarations are scoped. Creates
        an implicit block for the declared variables, and generally an explicit
        block for the body."""

        with self.push_context('block'):
            for declaration in node['head']:
                self.traverse(declaration, declare='let')

            self.traverse(node, 'body')

    @node_handler
    def ThisExpression(self, node):
        """A `this` expression."""

        try:
            return self.traverser.this_stack[-1]
        except IndexError:
            return self.traverser.contexts[0]

    @node_handler
    def ArrayExpression(self, node):
        """An array literal."""

        return JSArray(map(self.traverse, node['elements']),
                       traverser=self.traverser)

    @node_handler
    def ArrayPattern(self, node, declare=None):
        """A destructuring array pattern. Essentially an array expresson,
        but as an L-value."""

        return [self.traverse(element, declare=declare)
                for element in node['elements']]

    @node_handler
    def PrototypeMutation(self, node, **kw):
        """Assignment to the `__proto__` property."""

        return '__proto__', self.traverse(node, 'value', **kw)

    @node_handler
    def Property(self, node, **kw):
        """An object property. `"key": value`"""

        key = node['key']
        name = self.object_keys[key['type']](key)

        return name, self.traverse(node, 'value', **kw)

    @node_handler
    def ObjectExpression(self, node):
        """An object literal."""

        result = JSObject(traverser=self.traverser)

        for prop in node['properties']:
            name, val = self.traverse(prop)

            # Set the current location to the location of property we're
            # currently assigning to, rather than the end of the current
            # value.
            self.traverser.set_location(prop)

            result.set(name, val, set_by='object literal')

        return result

    @node_handler
    def ObjectPattern(self, node, declare=None):
        """A destructuring object pattern. Essentially an object expresson,
        but as an L-value."""

        result = {}

        for prop in node['properties']:
            name, val = self.traverse(prop, declare=declare)
            result[name] = val

        return result

    @node_handler
    def SpreadExpression(self, node, declare=None):
        """A spread expression. Essentially the inverse or a "rest" argument:
        `[a, b, c, ...rest]`."""

        # For now, just return the value. This is incorrect, but the
        # expression may be any iterable, and we can't handle generators
        # reliably. In the future, we should ideally handle at least the
        # common case where the target is an array.
        return self.traverse(node, 'expression')

    @node_handler
    def CallSiteObject(self, node):
        """A magical node for dealing with template strings.

        `fo\ro ${bar} b\0az` ->
        array = ["fo\ro", " b\0az"]
        array.raw = ["fo\\ro", " b\\0az"]
        """

        cooked = JSArray(node['cooked'], traverser=self.traverser)
        cooked['raw'] = JSArray(node['raw'], traverser=self.traverser)

        return cooked

    @node_handler
    def TemplateLiteral(self, node):
        """Another magical node for dealing with template strings.

        `foo ${bar} baz` ->
        TemplateLiteral:["foo ", bar, " baz"] ->
        ["foo ", bar, " baz"].join("")
        """

        elements = map(self.traverse, node['elements'])

        return reduce(partial(self.binary_op, '+'), elements)

    @node_handler
    def TaggedTemplate(self, node):
        """Yet another magical node for handling template strings. Causes
        the function on the left-hand-side to be called with arguments
        describing the template string on the right."""

        return self.CallExpression(node)

    @node_handler
    def FunctionDeclaration(self, node):
        """A function declaration:

            function foo() { return 42; }
        """

        wrapper = self.traverse(node, 'id', declare='var')
        wrapper.set_value(self.FunctionExpression(node),
                          set_by='function declaration')

    @node_handler
    def FunctionExpression(self, node):
        """A function expression `(function () { return 42 })`."""

        traverser = self.traverser

        # Basta seemed to think that it's necessary to put off traversing
        # all functions until the end of the current scope. *shrug*
        scope = traverser.find_scope(scope_type='function')

        @scope.cleanups.append
        def traverse_function():
            with self.push_conditional():
                with self.push_context('function'):
                    if node['id']:
                        # The function name, which should be bound within
                        # its scope.
                        wrapper = self.Identifier(node['id'], declare='var')
                        wrapper.set_value(value, set_by='function name')

                    for param in node['params']:
                        self.traverse(param, declare='var')

                    for default in node['defaults']:
                        # Default argument values.
                        self.traverse(default)

                    if node['rest']:
                        # A "rest" param: `function (a, b, c, ...rest)`
                        self.traverse(node, 'rest', declare='var')

                    traverser.this_stack.append(traverser.wrap(const=True))
                    try:
                        self.traverse(node, 'body')
                    finally:
                        traverser.this_stack.pop()

        name = ''
        if node['id']:
            name = node['id']['name']

        value = JSObject(callable=True, name=name, traverser=self.traverser)
        return value

    @node_handler
    def ArrowFunctionExpression(self, node):
        """An arrow function expression `() => 42`."""

        # This isn't *quite* accurate...
        return self.FunctionExpression(node)

    @node_handler
    def SequenceExpression(self, node):
        """A sequence of expressions: `(1, 2, 3)`"""

        result = None
        for expression in node['expressions']:
            result = self.traverse(expression)

        return result

    @node_handler
    def UnaryExpression(self, node):
        """A unary operator, and a value to which it applies."""

        operator = node['operator']
        value = self.traverse(node, 'argument')

        return self.traverser.wrap(self.unary_ops[operator](value),
                                   dirty=value.dirty)

    @node_handler
    def BinaryExpression(self, node):
        """A binary expression, including a expressions which evaluate to
        a left-hand-side and a right-hand-side, and an operator which
        combines them."""

        left = self.traverse(node, 'left')
        right = self.traverse(node, 'right')

        return self.binary_op(node['operator'], left, right)

    @node_handler
    def AssignmentExpression(self, node):
        """A binary assignment expression, including a expressions which
        evaluate to a left-hand-side and a right-hand-side, and an operator
        which defines which operation to perform against both values prior
        to assignment."""

        operator = node['operator']
        assert operator[-1] == '='

        left = self.traverse(node, 'left')
        right = self.traverse(node, 'right')

        if operator == '=':
            # In this case, `left` could be a destructuring expression, rather
            # than simply a wrapper.
            self.assign_value(left, right, set_by='bare assignment')
        else:
            left.set_value(self.binary_op(operator[:-1], left, right),
                           set_by='augmented assignment')

        return left

    @node_handler
    def UpdateExpression(self, node):
        """Pre/post increment/decrement operator: `foo++`, `--bar`"""

        operator = node['operator']
        wrapper = self.traverse(node, 'argument')

        old_value = wrapper.value
        wrapper.set_value(self.binary_ops[operator[0]](wrapper, self.ONE),
                          set_by='update expression')

        return wrapper.value if node['prefix'] else old_value

    @node_handler
    def LogicalExpression(self, node):
        """Logical AND or OR operator: `foo && bar || baz`"""

        operator = node['operator']
        left = self.traverse(node, 'left')
        right = self.traverse(node, 'right')

        if operator == '&&':
            result = right if left.as_bool() else left
        elif operator == '||':
            result = left if left.as_bool() else right
        else:
            raise ValueError()

        dirty = left.dirty or right.dirty
        if dirty:
            return self.traverser.wrap(result, dirty=dirty)
        return result

    @node_handler
    def ConditionalExpression(self, node):
        """A ternary operator, including a test, a consequent branch,
        and an alternate branch. `<test> ? <consequent> : <alternate>`."""

        test = self.traverse(node, 'test')
        with self.push_conditional():
            left = self.traverse(node, 'consequent')
        with self.push_conditional():
            right = self.traverse(node, 'alternate')

        result = left if test.as_bool() else right

        if test.dirty:
            return self.traverser.wrap(result, dirty=test.dirty)

        return result

    @node_handler
    def NewExpression(self, node):
        """A constructor call: `new Foo(bar)`."""

        args = Args(self.traverser, (self.traverse(arg)
                                     for arg in node['arguments']))

        callee = self.traverse(node, 'callee')
        this = self.traverser.wrap()  # Fix me.

        result = callee.call(this, args)
        if result.is_literal:
            return this  # Meh.

        return result

    @node_handler
    def CallExpression(self, node):
        """A function call, sans constructor: `Foo(bar)`."""

        args = Args(self.traverser, (self.traverse(arg)
                                     for arg in node['arguments']))

        callee = self.traverse(node, 'callee')
        this = self.traverser.wrap(getattr(callee, 'parent', None))

        return callee.call(this, args)

    @node_handler
    def Identifier(self, node, declare=None):
        """Represents an identifier, in any number of contexts. If `declare`
        is not None, our context is a declaration of some sort, so create
        the variable in the nearest context of the given type."""

        name = unicode(node['name'])
        if declare is None:
            return self.traverser.get_variable(name)

        if declare == 'var':
            result = self.find_scope('function').get(name, instantiate=True)

        elif declare == 'const':
            result = self.find_scope('function').get(name, instantiate=True,
                                                     const=True)
        elif declare == 'let':
            result = self.find_scope('block').get(name)

        elif declare == 'global':
            result = self.traverser.get_variable(name)

        else:
            raise ValueError('Unrecognized identifier declaration scope: {0}'
                             .format(declare))

        result.inferred = False
        return result

    @node_handler
    def MemberExpression(self, node, declare=None):
        """A member expression `<object>.<property>."""
        obj = self.traverse(node, 'object')

        if node['computed']:
            prop = self.traverse(node, 'property').as_identifier()
        else:
            prop = node['property']['name']

        return obj[prop]

    @node_handler
    def YieldExpression(self, node):
        """A `yield` expression, including any argument."""
        self.traverse(node, 'argument')

        return self.traverser.wrap(Undefined, dirty='Yield')

    @node_handler
    def ComprehensionExpression(self, node):
        """An array comprehension expression. `[x for (y in z)]`"""

        for block in node['blocks']:
            self.traverse(block)

        self.traverse(node, 'filter')

        with self.push_conditional():
            self.traverse(node, 'body')

        return JSArray(traverser=self.traverser)

    @node_handler
    def GeneratorExpression(self, node):
        """A generator expression. `(x for (y in z))`"""

        for block in node['blocks']:
            self.traverse(block)

        self.traverse(node, 'filter')

        with self.push_conditional():
            self.traverse(node, 'body')

        return self.traverser.wrap(dirty='Generator')

    @node_handler
    def ComprehensionBlock(self, node):
        """A `for-of` or `for-in` block in a comprehension or generator
        expression."""

        self.traverse(node, 'left')
        self.traverse(node, 'right')

    @node_handler
    def ComprehensionIf(self, node):
        """An `if` block in a comprehension or generator expression."""

        self.traverse(node, 'test')

    @node_handler
    def Literal(self, node):
        """A literal value: `42`, `true`, `"foo bar"`."""

        value = node['value']
        wrapper = self.traverser.wrap(value)

        if isinstance(value, basestring):
            self.test_literal(value, wrapper)
        return wrapper
