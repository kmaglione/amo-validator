from collections import defaultdict
from itertools import islice
import re
import sys
import types

from validator import constants
from validator.constants import DESCRIPTION_TYPES

from . import actions
from .jstypes import JSContext, JSObject, JSWrapper, Sentinel
from .nodedefinitions import DEFINITIONS
from .predefinedentities import GLOBAL_ENTITIES


DEBUG = False
IN_TESTS = False
IGNORE_POLLUTION = False
POLLUTION_COMPONENTS_PATH = re.compile(r'/?components/.*\.jsm?')


class Traverser(object):
    """Traverses the AST Tree and determines problems with a chunk of JS."""

    def __init__(self, err, filename, start_line=0, context=None, is_jsm=False,
                 pollutable=False):
        self.err = err
        self.is_jsm = is_jsm

        self.contexts = []
        self.filename = filename
        self.start_line = start_line
        self.polluted = False
        self.line = 1  # Line number
        self.position = 0  # Column number
        self.context = context

        self.pollutable = pollutable

        self.unary_ops = actions.UnaryOps(self)
        self.binary_ops = actions.BinaryOps(self)

        self.this_stack = []

        # For ordering of function traversal.
        self.function_collection = []

        # For debugging
        self.debug_level = 0

        class DebugLevel(object):
            def __enter__(self_):
                self.debug_level += 1

            def __exit__(self_, type, value, traceback):
                self.debug_level -= 1
        self._debug_level = DebugLevel()

        self._push_context()

    def debug(self, data, indent=0, **kw):
        """Write a message to the console if debugging is enabled."""
        if DEBUG:
            if kw:
                output = data.format(**kw)
            elif isinstance(data, (JSObject, JSWrapper)):
                output = repr(data)
            else:
                output = unicode(data)

            indent = self.debug_level + indent
            fill = (u'\u00b7 ' * ((indent + 1) / 2))[:indent]

            print (u'[{self.line:02}:{self.position:02}] '
                   u'{fill}{output}'.format(
                       self=self, fill=fill, output=output).encode('utf-8'))

        return self._debug_level

    def run(self, data):
        try:
            self.function_collection.append([])
            self.traverse(data)

            func_coll = self.function_collection.pop()
            for func in func_coll:
                func()
        except Exception:
            self.system_error(exc_info=sys.exc_info())
            return

        assert len(self.contexts) == 1
        assert len(self.function_collection) == 0

        # If we're running tests, save a copy of the global context for
        # inspection.
        if constants.IN_TESTS:
            self.err.final_context = self.contexts[0]

        if self.pollutable:
            context = self.contexts[0]
            pollution = [var for var, wrapper in context.data.iteritems()
                         if not (var in GLOBAL_ENTITIES or wrapper.inferred)]

            if len(pollution) > 3:
                for name in pollution:
                    location = context[name].location
                    self.warning(
                        err_id=('testcases_javascript_traverser', 'run',
                                'namespace_pollution'),
                        warning='JavaScript namespace pollution',
                        description=(
                            'Your add-on contains a large number of global '
                            'variables, which may conflict with other '
                            'add-ons. For more information, see '
                            'http://blog.mozilla.com/addons/2009/01/16/'
                            'firefox-extensions-global-namespace-pollution/'
                            ', or use JavaScript modules.',
                            'Variable name: %s' % name),
                        filename=location[0],
                        line=location[1],
                        position=location[2])

    def wrap(self, value=Sentinel, **kw):
        """Wraps the given value in a JSWrapper and JSValue, as appropriate,
        with the given keyword args passed through to JSWrapper."""

        if isinstance(value, JSWrapper):
            assert value.traverser is self
            return value

        return JSWrapper(value, traverser=self, **kw)

    def traverse(self, node, branch=None, source=None):
        parent = node
        if branch:
            node = node[branch]

        if node is None:
            return self.wrap(dirty='TraverseNone')

        if isinstance(node, types.StringTypes):
            return self.wrap(node)

        # Simple caching to prevent re-traversal
        if '__traversal' not in node:
            # Extract location information if it's available
            if node.get('loc'):
                start = node['loc']['start']
                self.line = self.start_line + start['line']
                self.position = start['column']

            if branch and 'type' in parent:
                self.debug('TRAVERSE {parent[type]} -> {branch}:{node[type]}',
                           node=node, parent=parent, branch=branch)
            else:
                self.debug('TRAVERSE {node[type]}', node=node)

            self.debug_level += 1
            result = self.wrap(self._traverse(node, source))
            result.parse_node = node
            self.debug_level -= 1
            node['__traversal'] = result

        return node['__traversal']

    def _traverse(self, node, source=None):
        if node.get('type') not in DEFINITIONS:
            if node.get('type'):
                key = 'unknown_node_types'
                if key not in self.err.metadata:
                    self.err.metadata[key] = defaultdict(int)

                self.err.metadata[key][node['type']] += 1

            return self.wrap(dirty='TraverseUnknown')

        # Extract properties about the node that we're traversing
        node_def = DEFINITIONS[node['type']]

        # If we're supposed to establish a context, do it now
        pushed_context = self.push_context(node_def)

        # An action allows the traverser to make intelligent decisions
        # based on the function of the code, rather than just the content.
        # If an action is availble, run it and store the output.
        action_result = None
        if node_def.action:
            action_result = node_def.action(self, node)
            # Special case, for immediate literals, define a source
            # property. Used for determining when literals are passed
            # directly as arguments.
            if node['type'] == 'Literal':
                action_result.value.source = source

        if action_result is None:
            # Use the node definition to determine and subsequently
            # traverse each of the branches.
            for branch in node_def.branches:
                if branch in node:
                    if isinstance(node[branch], list):
                        map(self.traverse, node[branch])
                    else:
                        self.traverse(node, branch)

        if pushed_context:
            self._pop_context()

        # If there is an action and the action returned a value, it should be
        # returned to the node traversal that initiated this node's traversal.
        if node_def.returns:
            if action_result is not None:
                return action_result
            return self.wrap(dirty='NoReturn')

        return self.wrap(dirty='TraverseDefault')

    def push_context(self, node):
        if node.dynamic:
            self._push_context()
            return True
        elif node.is_block:
            self._push_context(context_type='block')
            return True

    def _push_context(self, context=None, context_type='default'):
        """Push a lexical context onto the scope stack."""

        if context is None:
            context = JSContext(context_type, traverser=self)
        self.contexts.append(context)

    def _pop_context(self):
        'Adds a variable context to the current interpretation frame'

        assert len(self.contexts) > 1
        self.contexts.pop()

    def is_global(self, name):
        'Returns whether a name is a global entity'
        return name in GLOBAL_ENTITIES and not self.find_variable(name)

    def _build_global(self, name, entity):
        'Builds an object based on an entity from the predefined entity list'

        entity.setdefault('name', name)

        # Build out the wrapper object from the global definition.
        result = self.wrap(hooks=entity)
        result = actions._expand_globals(self, result)

        if 'dangerous' in entity and not callable(entity['dangerous']):
            # If it's callable, it will be processed later.
            dangerous = entity['dangerous']
        else:
            dangerous = entity.get('dangerous_on_read')
            if callable(dangerous):
                dangerous = dangerous(result)

        if dangerous:
            kwargs = dict(
                err_id=('js', 'traverser', 'dangerous_global'),
                warning='Access to the `%s` global' % name,
                description='Access to the `%s` property is '
                            'deprecated for security or '
                            'other reasons.' % name)

            if isinstance(dangerous, DESCRIPTION_TYPES):
                kwargs['description'] = dangerous
            elif isinstance(dangerous, dict):
                kwargs.update(dangerous)

            self.warning(**kwargs)

        return result

    def find_scope(self, scope_type, starting_at=0):
        """Find the closest scope of the given type."""
        for scope in islice(reversed(self.contexts), starting_at, None):
            if scope.context_type == scope_type:
                return scope
        return self.contexts[0]

    def find_variable(self, identifier, scope_type=None, starting_at=0):
        """Find the variable with the given identifier in the nearest
        scope. If `scope_type` is given, the nearest scope of that type is
        returned unless the variable is found in a nearer scope of a different
        type."""
        for scope in islice(reversed(self.contexts), starting_at, None):
            if scope.context_type == scope_type or scope.has_var(identifier):
                return scope

        if scope_type:
            return self.contexts[0]

    def get_variable(self, identifier, instantiate):
        """Return the wrapper for the variable with the given identifier,
        in the nearest scope in which it exists. If it desn't exist, a dirty
        wrapper is returned."""

        scope = self.find_variable(identifier, scope_type='global')
        if identifier in scope:
            return scope.get(identifier)

        if identifier in GLOBAL_ENTITIES:
            return self._build_global(identifier, GLOBAL_ENTITIES[identifier])

        return scope.get(identifier, instantiate=instantiate)

    def declare_variable(self, name, value, type_='var'):
        if type_ in ('var', 'const', ):
            context = self.find_scope('default')
        elif type_ == 'let':
            context = self.find_scope('block')
        else:
            assert type_ == 'global'
            # Look down through the lexical scope. If the variable being
            # assigned is present in one of those objects, use that as the
            # target context.
            context = self.find_variable(name, scope_type='global')

        context.set(name, value)
        return value

    def _err_kwargs(self, kwargs):
        err_kwargs = {
            'filename': self.filename,
            'line': self.line,
            'column': self.position,
            'context': self.context,
        }
        err_kwargs.update(kwargs)
        return err_kwargs

    def report(self, *args, **kwargs):
        return self.err.report(self._err_kwargs({}),
                               *args, **kwargs)

    def error(self, **kwargs):
        err_kwargs = self._err_kwargs(kwargs)
        return self.err.error(**err_kwargs)

    def warning(self, **kwargs):
        err_kwargs = self._err_kwargs(kwargs)
        return self.err.warning(**err_kwargs)

    def notice(self, **kwargs):
        err_kwargs = self._err_kwargs(kwargs)
        return self.err.notice(**err_kwargs)

    def system_error(self, **kwargs):
        err_kwargs = self._err_kwargs(kwargs)
        return self.err.system_error(**err_kwargs)
