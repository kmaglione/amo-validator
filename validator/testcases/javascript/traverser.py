from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import sys
from collections import defaultdict, namedtuple
from functools import partial

from validator import constants

from . import actions
from .jstypes import (Global, JSContext, JSObject, JSValue, JSWrapper,
                      LazyJSObject)


log = logging.getLogger('amo.validator')

DEBUG = False
IGNORE_POLLUTION = False

Location = namedtuple('Location', ('file', 'line', 'column'))


class Traverser(object):
    """Traverses the AST Tree and determines problems with a chunk of JS."""

    def __init__(self, err, filename, start_line=1, start_column=0,
                 context=None, is_jsm=False, pollutable=False):
        self.err = err
        self.is_jsm = is_jsm

        self.filename = filename
        self.start_location = Location(filename, start_line-1, start_column)
        self.polluted = False
        self.context = context

        self.pollutable = pollutable

        self.global_ = JSContext(traverser=self)
        self.global_.add_hooks(hooks=Global)

        self.contexts = [self.global_]

        self.block_scope = None
        self.subscript_scopes = set()
        self.import_scopes = set()

        self.node_handlers = actions.NodeHandlers(self)

        self.this_stack = []

        # Stack depth for presenting debug logging.
        self.debug_level = 0

        class DebugLevel(object):
            def __enter__(self_):
                self.debug_level += 1

            def __exit__(self_, type, value, traceback):
                self.debug_level -= 1
        self._debug_level = DebugLevel()

    _location = {'line': 1, 'column': 0}

    @property
    def location(self):
        return self.get_location(self._location)

    def get_location(self, loc):
        """Extracts a Location tuple from the given parse node location
        dict."""
        line = loc['line']
        column = loc['column']

        if line == 1:
            column += self.start_location.column
        line += self.start_location.line

        return Location(self.filename, line, column)

    def set_location(self, node):
        """Set the current location to the location of the given parse node,
        if it has one."""
        if node.get('loc'):
            self._location = node['loc']['start']

    # Deprecated compatibility wrappers around the `location` property.
    @property
    def line(self):
        return self.location[1]

    @property
    def position(self):
        return self.location[2]

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
            fill = ('\u00b7 ' * ((indent + 1) / 2))[:indent]

            print('[{loc.line:02}:{loc.column:02}] '  # noqa
                  '{fill}{output}'.format(
                      loc=self.location, fill=fill,
                      output=output).encode('utf-8'))

        return self._debug_level

    def check_block_scope(self, scope):
        """Check bindings in the top-level block scope for suspicious
        patterns."""

        WARNING = ('Since bug 1202902, variables declared at the top-level '
                   'using `let` or `const` are attached to a top-level block '
                   'scope, rather than to the global. Please use `var` '
                   'instead.')

        IGNORE_KEYS = {'Cc', 'Ci', 'Cu', 'Cr', 'Loader', 'Services', 'require'}

        let_map = self.err.resources.setdefault(
            'toplevel_lets', defaultdict(partial(defaultdict, set)))

        scope_name = os.path.basename(self.filename)

        for key in scope:
            wrapper = scope.get(key, skip_hooks=True)

            if self.pollutable:
                self.warning(
                    err_id=('top_block_scope', 'declaration', 'shared'),
                    warning='Top-level block declaration in a shared scope',
                    description=('Since bug 1202902, variables declared with '
                                 '`let` or `const` at the top-level now go '
                                 'into a per-script block scope. If you are '
                                 'depending on these variables being '
                                 'available to other scripts in the same '
                                 'document, please use `var` instead.'),
                    context_data={'identifier': key,
                                  'declared': wrapper.location},
                    location=wrapper.location)

            if key in IGNORE_KEYS or self.global_.has_builtin(key):
                continue

            exported_symbols = (scope.get('EXPORTED_SYMBOLS', False) or
                                self.global_.get('EXPORTED_SYMBOLS', False))

            let_map['subscript_scopes'][key].add((scope_name, wrapper))
            let_map['global'][key].add((scope_name, wrapper))
            if exported_symbols:
                let_map['import_scopes'][key].add((scope_name, wrapper))

            if key in self.global_:
                other = self.global_.get(key, skip_hooks=True)

                self.warning(
                    err_id=('top_block_scope', 'declaration', 'shadow'),
                    warning='Global variable shadowed by block scoped '
                            'declaration',
                    description=('A block-scoped declaration of `{var}` '
                                 'shadows a global variable of the same name.'
                                 .format(var=key),
                                 WARNING),
                    context_data={'identifier': key,
                                  'declared': wrapper.location,
                                  'masking': other.location},
                    location=wrapper.location)

        loose_vars = self.err.resources.setdefault('loose_vars',
                                                   defaultdict(set))

        for key in self.global_:
            wrapper = scope.get(key, skip_hooks=True)
            if wrapper.inferred:
                loose_vars[key].add(('global', scope_name, wrapper))

        for scope_set in ('subscript_scopes', 'import_scopes'):
            for scope_name, scope in getattr(self, scope_set):
                for key in scope:
                    wrapper = scope.get(key, skip_hooks=True)
                    if wrapper.inferred:
                        loose_vars[key].add((scope_set, scope_name, wrapper))

    def run(self, data):
        """Traverse the entire parse tree from the given root node."""

        try:
            self.traverse(data)

            self.contexts[0].cleanup()

            if self.err.debug_level:
                self.check_node(data)
        except Exception:
            self.system_error(exc_info=sys.exc_info())
            return

        if self.block_scope:
            self.check_block_scope(self.block_scope)

        assert len(self.contexts) == 1

        # If we're running tests, save a copy of the global context for
        # inspection.
        if constants.IN_TESTS:
            self.err.final_context = self.contexts[0]

        if self.pollutable:
            context = self.contexts[0]
            pollution = [var for var, wrapper in context.data.iteritems()
                         # Any object with hooks, we can assume already
                         # exists. Any wrapper with the inferred flag exists
                         # because it was accessed, but not assigned to.
                         if not (wrapper.hooks or wrapper.inferred)]

            if len(pollution) > 3:
                for name in pollution:
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
                        location=context[name].location)

    def check_node(self, node):
        """Recursively check all nodes in the given parse tree, and ensure
        that all node types are known, and all known node types have been
        traversed."""

        if not isinstance(node, dict):
            return

        if node.get('type') not in (None, 'Literal', 'Identifier',
                                    'ComputedName'):
            self.set_location(node)
            assert node['type'] in self.node_handlers
            assert '__traversed' in node

        for child in node.itervalues():
            if isinstance(child, dict):
                self.check_node(child)
            elif isinstance(child, list):
                for elem in child:
                    self.check_node(elem)

    def wrap(self, value=LazyJSObject, **kw):
        """Wraps the given value in a JSWrapper and JSValue, as appropriate,
        with the given keyword args passed through to JSWrapper."""

        if not kw and isinstance(value, JSWrapper):
            assert value.traverser is self
            return value

        return JSWrapper(value, traverser=self, **kw)

    def traverse(self, node, branch=None, **kw):
        """Traverse the given node, based on the handler definitions in
        `node_handlers`, updating the current `location` when possible. If
        `branch` is given, it must be a string, and the child node at the
        given key is traversed instead. This is primarily useful to improve
        debugging output.

        Any additional keyword arguments are passed directly to the node
        handler function.

        Performs some sanity checking prior to traversal:

          * Ensures that the node has not already been traversed.
          * Logs an exception if the given node type is not known to us.
          * If `err.debug_level` is non-zero, and the given node type is not
            known to us, outputs an error to our error bundle.
        """

        parent = node
        if branch:
            node = node[branch]

        if node is None:
            return

        if branch and 'type' in parent:
            self.debug('TRAVERSE {parent[type]} -> {branch}:{node[type]}',
                       node=node, parent=parent, branch=branch)
        else:
            self.debug('TRAVERSE {node[type]}', node=node)

        assert '__traversed' not in node
        node['__traversed'] = True

        self.set_location(node)

        try:
            handler = self.node_handlers[node['type']]
        except KeyError:
            if self.err.debug_level:
                self.error(err_id=('traverser', 'traverse', 'unknown_node'),
                           error='Unknown node type: {[type]}'.format(node))

            log.exception('Unknown node type: {[type]}'.format(node))
            key = 'unknown_node_types'
            self.err.metadata.setdefault(key, defaultdict(int))
            self.err.metadata[key][node['type']] += 1
        else:
            with self._debug_level:
                result = handler(node, **kw)
                if isinstance(result, (JSWrapper, JSValue)):
                    result.parse_node = node
                return result

    def find_scope(self, scope_type):
        """Find the scope of the given type nearest to the top of the context
        stack."""

        for scope in reversed(self.contexts):
            if scope.context_type == scope_type:
                return scope
        return self.contexts[0]

    def find_variable(self, identifier):
        """Find the variable with the given identifier in the nearest scope
        to the top of the context stack in which it is bound."""
        for scope in reversed(self.contexts):
            if identifier in scope:
                return scope

        return self.contexts[0]

    def get_variable(self, identifier, instantiate=True):
        """Return the wrapper for the variable with the given identifier,
        in the nearest scope in which it exists. If it doesn't exist, a dirty
        wrapper is returned."""

        scope = self.find_variable(identifier)
        if identifier in scope:
            return scope.get(identifier)

        return scope.get(identifier, instantiate=instantiate)

    def _err_kwargs(self, kwargs):
        err_kwargs = {
            'location': self.location,
            'context': self.context,
        }
        err_kwargs.update(kwargs)
        return err_kwargs

    # Wrappers around the same-named reporting methods of our error bundle,
    # which automatically set the location of the message to the location
    # of the node currently being traversed.

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
