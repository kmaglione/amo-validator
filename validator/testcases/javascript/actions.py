import re
from copy import deepcopy
from functools import partial, wraps

# Global import of predefinedentities will cause an import loop
import instanceactions
from validator.constants import (BUGZILLA_BUG, DESCRIPTION_TYPES, FENNEC_GUID,
                                 FIREFOX_GUID, MAX_STR_SIZE)
from validator.decorator import version_range
from validator.testcases.regex import validate_string
from jstypes import JSArray, JSContext, JSObject, JSWrapper, Undefined


NUMERIC_TYPES = (int, long, float, complex)


def clean_dirty(wrapper):
    """If the given wrapper is dirty, and has a string value, clean up repeated
    occurrences of '[object Object]."""
    if (wrapper.dirty and wrapper.is_literal() and
            isinstance(wrapper.as_primitive(), basestring)):
        wrapper.value.value = re.sub(r'(?:\[object Object]){2,}',
                                     '[object Object]', wrapper.value.value)


def operator(op):
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


class Operators(object):
    class __metaclass__(type):
        def __new__(mcls, name, bases, dict_):
            cls = type.__new__(mcls, name, bases, dict_)
            cls.OPERATORS = {method.operator: name
                             for name, method in dict_.iteritems()
                             if getattr(method, 'operator', None)}
            return cls

    def __init__(self, traverser):
        self.traverser = traverser

    def __getitem__(self, operator):
        return getattr(self, self.OPERATORS[operator])

    def __contains__(self, operator):
        return operator in self.OPERATORS


class BinaryOps(Operators):
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
        if left.typeof() == right.typeof():
            # The two values are of the same JS type. Use strict equality.
            return self.identical(left, right)

        # Because JavaScript:

        number = (int, float, bool)

        # `x` and `y` per the ECMAScript spec.
        x = left.as_primitive()
        y = right.as_primitive()

        if x in (None, Undefined) and y in (None, Undefined):
            return True

        if (isinstance(x, basestring) and isinstance(y, number) or
                isinstance(y, basestring) and isinstance(x, number)):
            # One string and one number. Coerce both to numbers.
            return left.as_float() == right.as_float()

        # Close enough.
        return (left.as_primitive() == right.as_primitive() or
                left.as_str() == right.as_str())

    @operator('!=')
    def not_equal(self, left, right):
        """Return true if values would not compare equal in JavaScript."""
        return not self.equal(left, right)

    @operator('===')
    def identical(self, left, right):
        """Return true if values would compare as identical in JavaScript."""
        if left.is_literal() and right.is_literal():
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
        # FIXME(Kris): Treat instanceof the same as `QueryInterface`
        return False


class UnaryOps(Operators):
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
        return value.typeof()

    @operator('delete')
    def delete(self, value):
        """Do nothing. Unary deletion is no longer supported in JavaScript,
        except for object keys (which are handled elsewhere)."""
        return Undefined


def _get_member_exp_property(traverser, node):
    """Return the string value of a member expression's property."""

    if node['property']['type'] == 'Identifier' and not node.get('computed'):
        return unicode(node['property']['name'])
    else:
        eval_exp = traverser.traverse(node['property'])
        return eval_exp.as_str()


def _expand_globals(traverser, node):
    """Expands a global object that has a lambda value."""

    if callable(node.hooks.get('value')):
        result = node.hooks['value'](traverser)

        if isinstance(result, dict):
            output = traverser._build_global('--', result)
        elif isinstance(result, JSWrapper):
            output = result
        else:
            output = traverser.wrap(result)

        output.hooks.setdefault('value', {})

        return output

    return node


def trace_member(traverser, node, instantiate=False):
    'Traces a MemberExpression and returns the appropriate object'

    traverser._debug('TESTING>>%s' % node['type'])
    if node['type'] == 'MemberExpression':
        # x.y or x[y]
        # x = base
        base = trace_member(traverser, node['object'], instantiate)
        base = _expand_globals(traverser, base)

        identifier = _get_member_exp_property(traverser, node)

        # If we've got an XPCOM wildcard, return a copy of the entity.
        if 'xpcom_wildcard' in base.hooks:
            traverser._debug('MEMBER_EXP>>XPCOM_WILDCARD')

            from predefinedentities import CONTRACT_ENTITIES
            if identifier in CONTRACT_ENTITIES:
                kw = dict(err_id=('js', 'actions', 'dangerous_contract'),
                          warning='Dangerous XPCOM contract ID')
                kw.update(CONTRACT_ENTITIES[identifier])

                traverser.warning(**kw)

            base.hooks = base.hooks.copy()
            del base.hooks['xpcom_wildcard']
            return base

        test_identifier(traverser, identifier)

        traverser._debug('MEMBER_EXP>>PROPERTY: %s' % identifier)
        output = base.get(instantiate=instantiate, name=identifier)

        if base.hooks:
            # In the cases of XPCOM objects, methods generally
            # remain bound to their parent objects, even when called
            # indirectly.
            output.parent = base
        return output

    elif node['type'] == 'Identifier':
        traverser._debug('MEMBER_EXP>>ROOT:IDENTIFIER')
        test_identifier(traverser, node['name'])

        # If we're supposed to instantiate the object and it doesn't already
        # exist, instantitate the object.
        if instantiate and not traverser._is_defined(node['name']):
            output = traverser.wrap()
            traverser.contexts[0].set(node['name'], output)
        else:
            output = traverser._seek_variable(node['name'])

        return _expand_globals(traverser, output)
    else:
        traverser._debug('MEMBER_EXP>>ROOT:EXPRESSION')
        # It's an expression, so just try your damndest.
        return traverser.traverse(node)


def test_identifier(traverser, name):
    'Tests whether an identifier is banned'

    import predefinedentities
    if name in predefinedentities.BANNED_IDENTIFIERS:
        traverser.err.warning(
            err_id=('js', 'actions', 'banned_identifier'),
            warning='Banned or deprecated JavaScript Identifier',
            description=predefinedentities.BANNED_IDENTIFIERS[name],
            filename=traverser.filename,
            line=traverser.line,
            column=traverser.position,
            context=traverser.context)


def _function(traverser, node):
    'Prevents code duplication'
    # Oh? How is that, exactly?

    def wrap(traverser, node):
        me = JSObject(traverser=traverser)

        traverser.function_collection.append([])

        # Replace the current context with a prototypeable JS object.
        traverser._pop_context()
        me.type_ = 'default'  # Treat the function as a normal object.
        traverser._push_context(me)
        traverser._debug('THIS_PUSH')
        traverser.this_stack.append(me)  # Allow references to "this"

        # Declare parameters in the local scope
        params = []
        for param in node['params']:
            if param['type'] == 'Identifier':
                params.append(param['name'])
            elif param['type'] == 'ArrayPattern':
                for element in param['elements']:
                    # Array destructuring in function prototypes? LOL!
                    if element is None or element['type'] != 'Identifier':
                        continue
                    params.append(element['name'])

        local_context = traverser._peek_context(1)
        for param in params:
            var = traverser.wrap(dirty=True)

            # We can assume that the params are static because we don't care
            # about what calls the function. We want to know whether the
            # function solely returns static values. If so, it is a static
            # function.
            local_context.set(param, var)

        traverser.traverse(node['body'])

        # Since we need to manually manage the "this" stack, pop off that
        # context.
        traverser._debug('THIS_POP')
        traverser.this_stack.pop()

        # Call all of the function collection's members to traverse all of the
        # child functions.
        func_coll = traverser.function_collection.pop()
        for func in func_coll:
            func()

    # Put the function off for traversal at the end of the current block scope.
    traverser.function_collection[-1].append(partial(wrap, traverser, node))

    return traverser.wrap(callable=True, dirty=True)


def _define_function(traverser, node):
    me = _function(traverser, node)
    traverser._peek_context(2).set(node['id']['name'], me)
    return me


def _func_expr(traverser, node):
    'Represents a lambda function'

    return _function(traverser, node)


def _define_with(traverser, node):
    'Handles `with` statements'

    object_ = traverser.traverse(node['object'])
    if isinstance(object_, JSWrapper) and isinstance(object_.value, JSObject):
        traverser.contexts[-1] = object_.value
        traverser.contexts.append(JSContext('block'))
    return


def _define_var(traverser, node):
    'Creates a local context variable'

    traverser._debug('VARIABLE_DECLARATION')
    traverser.debug_level += 1

    declarations = (node['declarations'] if 'declarations' in node
                    else node['head'])

    kind = node.get('kind', 'let')
    for declaration in declarations:

        # It could be deconstruction of variables :(
        if declaration['id']['type'] == 'ArrayPattern':

            vars = []
            for element in declaration['id']['elements']:
                # NOTE : Multi-level array destructuring sucks. Maybe implement
                # it someday if you're bored, but it's so rarely used and it's
                # so utterly complex, there's probably no need to ever code it
                # up.
                if element is None or element['type'] != 'Identifier':
                    vars.append(None)
                    continue
                vars.append(element['name'])

            # The variables are not initialized
            if declaration['init'] is None:
                # Simple instantiation; no initialization
                for var in vars:
                    if not var:
                        continue
                    traverser._declare_variable(var, None)

            # The variables are declared inline
            elif declaration['init']['type'] == 'ArrayPattern':
                # TODO : Test to make sure len(values) == len(vars)
                for value in declaration['init']['elements']:
                    if vars[0]:
                        traverser._declare_variable(
                            vars[0], traverser.traverse(value))
                    vars = vars[1:]  # Pop off the first value

            # It's being assigned by a JSArray (presumably)
            elif declaration['init']['type'] == 'ArrayExpression':

                assigner = traverser.traverse(declaration['init'])
                for value in assigner.value.elements:
                    if vars[0]:
                        traverser._declare_variable(vars[0], value)
                    vars = vars[1:]

        elif declaration['id']['type'] == 'ObjectPattern':

            init = traverser.traverse(declaration['init'])

            def _proc_objpattern(init_obj, properties):
                for prop in properties:
                    # Get the name of the init obj's member
                    if prop['key']['type'] == 'Literal':
                        prop_name = prop['key']['value']
                    elif prop['key']['type'] == 'Identifier':
                        prop_name = prop['key']['name']
                    else:
                        continue

                    if prop['value']['type'] == 'Identifier':
                        traverser._declare_variable(
                            prop['value']['name'], init_obj.get(prop_name))

                    elif prop['value']['type'] == 'ObjectPattern':
                        _proc_objpattern(init_obj.get(prop_name),
                                         prop['value']['properties'])

            if init is not None:
                _proc_objpattern(init_obj=init,
                                 properties=declaration['id']['properties'])

        else:
            var_name = declaration['id']['name']
            traverser._debug('NAME>>%s' % var_name)

            var_value = traverser.traverse(declaration['init'])
            traverser._debug('VALUE>>%r' % var_value)

            if not isinstance(var_value, JSWrapper):
                var = traverser.wrap(var_value, const=kind == 'const')
            else:
                var = var_value
                var.const = kind == 'const'

            traverser._declare_variable(var_name, var, type_=kind)

    if 'body' in node:
        traverser.traverse(node['body'])

    traverser.debug_level -= 1

    # The "Declarations" branch contains custom elements.
    return True


def _define_obj(traverser, node):
    'Creates a local context object'

    obj = JSObject()
    wrapper = traverser.wrap(obj)

    for prop in node['properties']:
        if prop['type'] == 'PrototypeMutation':
            var_name = 'prototype'
        else:
            key = prop['key']
            if key['type'] == 'Literal':
                var_name = key['value']
            elif isinstance(key['name'], basestring):
                var_name = key['name']
            else:
                if 'property' in key['name']:
                    name = key['name']
                else:
                    name = {'property': key['name']}
                var_name = _get_member_exp_property(traverser, name)

        var_value = traverser.traverse(prop['value'])
        obj.set(var_name, var_value)

        # TODO: Observe "kind"
    return wrapper


def _define_array(traverser, node):
    """Instantiate an array object from the parse tree."""
    return JSArray(map(traverser.traverse, node['elements']),
                   traverser=traverser)


def _define_template_strings(traverser, node):
    """Instantiate an array of raw and cooked template strings."""
    cooked = JSArray(map(traverser.traverse, node['cooked']),
                     traverser=traverser)

    cooked['raw'] = JSArray(map(traverser.traverse, node['raw']),
                            traverser=traverser)

    return cooked


def _define_template(traverser, node):
    """Instantiate a template literal."""
    elements = map(traverser.traverse, node['elements'])

    return reduce(partial(_binary_op, '+', traverser=traverser), elements)


def _define_literal(traverser, node):
    """
    Convert a literal node in the parse tree to its corresponding
    interpreted value.
    """
    value = node['value']
    if isinstance(value, dict):
        return traverser.wrap(dirty=True)

    wrapper = traverser.wrap(value)
    if isinstance(value, basestring):
        test_literal(traverser, wrapper)
    return wrapper


def test_literal(traverser, wrapper):
    """
    Test the value of a literal, in particular only a string literal at the
    moment, against possibly dangerous patterns.
    """
    validate_string(wrapper.as_primitive(), traverser=traverser,
                    wrapper=wrapper)


def _call_expression(traverser, node):
    args = node['arguments']
    for arg in args:
        traverser.traverse(arg, source='arguments')

    member = traverser.traverse(node['callee'])

    if (traverser.filename.startswith('defaults/preferences/') and
        ('name' not in node['callee'] or
         node['callee']['name'] not in (u'pref', u'user_pref'))):

        traverser.err.warning(
            err_id=('testcases_javascript_actions',
                    '_call_expression',
                    'complex_prefs_defaults_code'),
            warning='Complex code should not appear in preference defaults '
                    'files',
            description="Calls to functions other than 'pref' and 'user_pref' "
                        'should not appear in defaults/preferences/ files.',
            filename=traverser.filename,
            line=traverser.line,
            column=traverser.position,
            context=traverser.context)

    if callable(member.hooks.get('dangerous', None)):
        result = member.hooks['dangerous'](a=args, t=traverser.traverse,
                                           e=traverser.err)
        name = member.hooks.get('name', '')

        if result and name:
            kwargs = {
                'err_id': ('testcases_javascript_actions', '_call_expression',
                           'called_dangerous_global'),
                'warning': '`%s` called in potentially dangerous manner' %
                           member.hooks['name'],
                'description':
                    'The global `%s` function was called using a set '
                    'of dangerous parameters. Calls of this nature '
                    'are deprecated.' % member.hooks['name']}

            if isinstance(result, DESCRIPTION_TYPES):
                kwargs['description'] = result
            elif isinstance(result, dict):
                kwargs.update(result)

            traverser.warning(**kwargs)

    elif (node['callee']['type'] == 'MemberExpression' and
          node['callee']['property']['type'] == 'Identifier'):

        # If we can identify the function being called on any member of any
        # instance, we can use that to either generate an output value or test
        # for additional conditions.
        identifier_name = node['callee']['property']['name']
        if identifier_name in instanceactions.INSTANCE_DEFINITIONS:
            result = instanceactions.INSTANCE_DEFINITIONS[identifier_name](
                        args, traverser, node, wrapper=member)
            return result

    if 'return' in member.hooks:
        if 'object' in node['callee']:
            member.parent = trace_member(traverser, node['callee']['object'])

        return member.hooks['return'](wrapper=member, arguments=args,
                                      traverser=traverser)

    return traverser.wrap(dirty=True)


def _readonly_top(traverser, right, node_right):
    """Handle the readonly callback for window.top."""
    traverser.notice(
        err_id=('testcases_javascript_actions',
                '_readonly_top'),
        notice='window.top is a reserved variable',
        description='The `top` global variable is reserved and cannot be '
                    'assigned any values starting with Gecko 6. Review your '
                    'code for any uses of the `top` global, and refer to '
                    '%s for more information.' % BUGZILLA_BUG % 654137,
        for_appversions={FIREFOX_GUID: version_range('firefox',
                                                     '6.0a1', '7.0a1'),
                         FENNEC_GUID: version_range('fennec',
                                                    '6.0a1', '7.0a1')},
        compatibility_type='warning',
        tier=5)


def _expression(traverser, node):
    """
    This is a helper method that allows node definitions to point at
    `traverse` without needing a reference to a traverser.
    """
    return traverser.traverse(node['expression'])


def _get_this(traverser, node):
    'Returns the `this` object'
    if not traverser.this_stack:
        from predefinedentities import GLOBAL_ENTITIES
        return traverser._build_global('window', GLOBAL_ENTITIES[u'window'])
    return traverser.this_stack[-1]


def _new(traverser, node):
    'Returns a new copy of a node.'

    args = node['arguments']
    if isinstance(args, list):
        for arg in args:
            traverser.traverse(arg, source='arguments')
    else:
        traverser.traverse(args)

    elem = traverser.traverse(node['callee'])
    if not isinstance(elem, JSWrapper):
        elem = traverser.wrap(elem)

    if elem.hooks:
        traverser._debug('Making overwritable')
        elem.hooks = deepcopy(elem.hooks)
        elem.hooks['overwritable'] = True
    return elem


def _ident(traverser, node):
    'Initiates an object lookup on the traverser based on an identifier token'

    name = node['name']

    # Ban bits like "newThread"
    test_identifier(traverser, name)

    if traverser._is_defined(name):
        return traverser._seek_variable(name)

    return traverser.wrap(dirty=True)


def _expr_assignment(traverser, node):
    """Evaluate an AssignmentExpression node."""

    traverser._debug('ASSIGNMENT_EXPRESSION')

    with traverser._debug('ASSIGNMENT>>PARSING RIGHT'):
        right = traverser.traverse(node['right'])

    operator = node['operator']

    # Treat direct assignment different than augmented assignment.
    if operator == '=':
        from predefinedentities import GLOBAL_ENTITIES, is_shared_scope

        global_overwrite = False
        readonly_value = is_shared_scope(traverser)

        node_left = node['left']
        traverser._debug('ASSIGNMENT:DIRECT(%s)' % node_left['type'])

        if node_left['type'] == 'Identifier':
            # Identifiers just need the ID name and a value to push.
            # Raise a global overwrite issue if the identifier is global.
            global_overwrite = traverser._is_global(node_left['name'])

            # Get the readonly attribute and store its value if is global.
            if global_overwrite:
                global_dict = GLOBAL_ENTITIES[node_left['name']]
                if 'readonly' in global_dict:
                    readonly_value = global_dict['readonly']

            traverser._declare_variable(node_left['name'], right, type_='glob')
        elif node_left['type'] == 'MemberExpression':
            member_obj = trace_member(traverser, node_left['object'],
                                      instantiate=True)

            global_overwrite = (member_obj.hooks and
                                not member_obj.hooks.get('overwritable'))

            member_property = _get_member_exp_property(traverser, node_left)
            traverser._debug('ASSIGNMENT:MEMBER_PROPERTY(%s)'
                             % member_property)
            traverser._debug('ASSIGNMENT:GLOB_OV::%s' % global_overwrite)

            if isinstance(member_obj.value, JSObject):
                member_obj.value.set(member_property, right)

            if 'value' in member_obj.hooks:
                hooks = _expand_globals(traverser, member_obj).hooks

                value_hook = hooks['value'].get(member_property)
                if value_hook:
                    # If we have hooks for this property, test whether it can
                    # be safely overwritten.
                    if 'readonly' in value_hook:
                        global_overwrite = True
                        readonly_value = value_hook['readonly']

        traverser._debug('ASSIGNMENT:DIRECT:GLOB_OVERWRITE %s' %
                         global_overwrite)
        traverser._debug('ASSIGNMENT:DIRECT:READONLY %r' %
                         readonly_value)

        if callable(readonly_value):
            readonly_value = readonly_value(traverser, right, node['right'])

        if readonly_value and global_overwrite:

            kwargs = dict(
                err_id=('testcases_javascript_actions',
                        '_expr_assignment',
                        'global_overwrite'),
                warning='Global variable overwrite',
                description='An attempt was made to overwrite a global '
                            'variable in some JavaScript code.')

            if isinstance(readonly_value, DESCRIPTION_TYPES):
                kwargs['description'] = readonly_value
            elif isinstance(readonly_value, dict):
                kwargs.update(readonly_value)

            traverser.warning(**kwargs)

        return right

    with traverser._debug('ASSIGNMENT>>PARSING LEFT'):
        left = traverser.traverse(node['left'])

    assert operator[-1] == '='
    wrapper = _binary_op(operator[:-1], left, right, traverser)

    with traverser._debug('ASSIGNMENT::New value >> %s' % wrapper):
        left.set_value(wrapper)

    return left


def _expr_binary(traverser, node):
    'Evaluates a BinaryExpression node.'

    traverser.debug_level += 1

    # Select the proper operator.
    operator = node['operator']
    traverser._debug('BIN_OPERATOR>>%s' % operator)

    # Traverse the left half of the binary expression.
    with traverser._debug('BIN_EXP>>l-value'):
        if (node['left']['type'] == 'BinaryExpression' and
                '__traversal' not in node['left']):
            # Process the left branch of the binary expression directly. This
            # keeps the recursion cap in line and speeds up processing of
            # large chains of binary expressions.
            left = _expr_binary(traverser, node['left'])
            node['left']['__traversal'] = left
        else:
            left = traverser.traverse(node['left'])

    # Traverse the right half of the binary expression.
    with traverser._debug('BIN_EXP>>r-value'):
        if (operator == 'instanceof' and
                node['right']['type'] == 'Identifier' and
                node['right']['name'] == 'Function'):
            # We make an exception for instanceof's r-value if it's a
            # dangerous global, specifically Function.
            return traverser.wrap(True)
        else:
            right = traverser.traverse(node['right'])
            traverser._debug('Is dirty? %r' % right.dirty, 1)

    return _binary_op(operator, left, right, traverser)


def _binary_op(operator, left, right, traverser):
    """Perform a binary operation on two pre-traversed nodes."""

    value = traverser.binary_ops[operator](left, right)

    if isinstance(value, basestring):
        value = value[:MAX_STR_SIZE]

    wrapper = traverser.wrap(value, dirty=left.dirty or right.dirty)
    clean_dirty(wrapper)

    # Test the newly-created literal for dangerous values.
    # This may cause duplicate warnings for strings which
    # already match a dangerous value prior to concatenation.
    if not wrapper.dirty and isinstance(value, basestring):
        test_literal(traverser, wrapper)

    return wrapper


def _expr_unary(traverser, node):
    """Evaluate a UnaryExpression node."""

    operator = node['operator']
    wrapper = traverser.traverse(node['argument'])

    value = traverser.unary_ops[operator](wrapper)
    return traverser.wrap(value, dirty=wrapper.dirty)
