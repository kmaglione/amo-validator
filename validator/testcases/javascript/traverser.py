from collections import defaultdict
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
POLLUTION_EXCEPTIONS = set(['Cc', 'Ci', 'Cu', ])


class Traverser(object):
    """Traverses the AST Tree and determines problems with a chunk of JS."""

    def __init__(self, err, filename, start_line=0, context=None,
                 is_jsm=False):
        self.err = err
        self.is_jsm = is_jsm

        self.contexts = []
        self.block_contexts = []
        self.filename = filename
        self.start_line = start_line
        self.polluted = False
        self.line = 1  # Line number
        self.position = 0  # Column number
        self.context = context

        self.unary_ops = actions.UnaryOps(self)
        self.binary_ops = actions.BinaryOps(self)

        # Can use the `this` object
        self.can_use_this = False
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

        # If we're running tests, save a copy of the global context for
        # inspection.
        if constants.IN_TESTS:
            self.err.final_context = self.contexts[0]

        if self.pollutable:
            # Ignore anything in the components/ directory
            if POLLUTION_COMPONENTS_PATH.match(self.filename):
                return

            # This performs the namespace pollution test.
            global_context_size = sum(
                1 for name in self.contexts[0].data if
                name not in POLLUTION_EXCEPTIONS)

            if (global_context_size > 3 and not self.is_jsm and
                    'is_jetpack' not in self.err.metadata and
                    self.err.get_resource('em:bootstrap') != 'true'):
                self.err.warning(
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
                        'List of entities: %s'
                        % ', '.join(self.contexts[0].data.keys())),
                    filename=self.filename)

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
            return self.wrap(dirty=True)

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

            return self.wrap(dirty=True)

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

        # WithStatements declare two blocks: one for the block and one for
        # the object that's being withed. We need both because of `let`s.
        if node['type'] == 'WithStatement':
            self._pop_context()
        if pushed_context:
            self._pop_context()

        # If there is an action and the action returned a value, it should be
        # returned to the node traversal that initiated this node's traversal.
        if node_def.returns and action_result is not None:
            return action_result

        return self.wrap(dirty=True)

    def push_context(self, node):
        if node.dynamic:
            self._push_context()
            return True
        elif node.is_block:
            self._push_block_context()
            return True

    def _push_block_context(self):
        'Adds a block context to the current interpretation frame'
        self.contexts.append(JSContext('block', traverser=self))

    def _push_context(self, default=None):
        'Adds a variable context to the current interpretation frame'

        if default is None:
            default = JSContext('default', traverser=self)
        self.contexts.append(default)

    def _pop_context(self):
        'Adds a variable context to the current interpretation frame'

        assert len(self.contexts) > 1
        self.contexts.pop()

    def _peek_context(self, depth=1):
        """Returns the most recent context. Note that this should NOT be used
        for variable lookups."""

        return self.contexts[len(self.contexts) - depth]

    def _seek_variable(self, variable):
        'Returns the value of a variable that has been declared in a context'

        # Look for the variable in the local contexts first
        local_variable = self._seek_local_variable(variable)
        if local_variable is not None:
            return local_variable

        # Seek in globals for the variable instead.
        if self._is_global(variable):
            return self._build_global(variable, GLOBAL_ENTITIES[variable])

        self.debug('SEEK_GLOBAL>>FAILED')
        # If we can't find a variable, we always return a dummy object.
        return self.wrap()

    def _is_defined(self, variable):
        return variable in GLOBAL_ENTITIES or self._is_local_variable(variable)

    def _is_local_variable(self, variable):
        """Return whether a variable is defined in the current scope."""
        return any(ctx.has_var(variable) for ctx in self.contexts)

    def _seek_local_variable(self, variable):
        # Loop through each context in reverse order looking for the defined
        # variable.
        for context in reversed(self.contexts):
            # If it has the variable, return it.
            if context.has_var(variable):
                self.debug('SEEK>>FOUND')
                return context.get(variable)

    def _is_global(self, name):
        'Returns whether a name is a global entity'
        return not self._is_local_variable(name) and name in GLOBAL_ENTITIES

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

    def _declare_variable(self, name, value, type_='var'):
        context = None
        if type_ in ('var', 'const', ):
            for ctxt in reversed(self.contexts):
                if ctxt.context_type == 'default':
                    context = ctxt
                    break
        elif type_ == 'let':
            context = self.contexts[-1]
        elif type_ == 'glob':
            # Look down through the lexical scope. If the variable being
            # assigned is present in one of those objects, use that as the
            # target context.
            for ctx in reversed(self.contexts[1:]):
                if ctx.has_var(name):
                    context = ctx
                    break

        if not context:
            context = self.contexts[0]

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
