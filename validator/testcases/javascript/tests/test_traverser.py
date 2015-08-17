from __future__ import absolute_import, print_function, unicode_literals

from contextlib import contextmanager

import mock
import pytest

from tests.js_helper import TestCase

from ..traverser import Location, Traverser


class BaseTestTraverser(TestCase):
    """Tests the functionality of the base-level JS Value type."""

    def setup_method(self, method):
        super(BaseTestTraverser, self).setup_method(method)
        self.traverser = Traverser(self.err, filename='<stdin>')

    def wrap(self, val):
        return self.traverser.wrap(val).value


class TestTraverser(BaseTestTraverser):

    def get_nodes(self, node_type, traversed):
        """Return a list of trees of semi-legitimate nodes, each with at least
        one node of the type `node_type` somewhere within it. If `traversed`
        is true, each node will have a `__traversed` property."""

        if traversed:
            traversed = '__traversed'

        NODE = {'type': node_type, traversed: True}

        return (
            NODE,
            {'type': 'Program', 'body': NODE, '__traversed': True},
            {'type': 'Program', '__traversed': True,
             'body': {
                 'type': 'BlockStatement', '__traversed': True,
                 'thing': {'stuff': {'meh': NODE}}}},
            {'type': 'CallExpression', '__traversed': True,
             'arguments': [{'type': 'BlockStatement', '__traversed': True,
                            'thing': NODE}]},
        )

    def push_context(self, *args, **kw):
        """Push a context onto the context stack via
        `traverser.node_handlers.push_context`."""

        return self.traverser.node_handlers.push_context(*args, **kw)

    @contextmanager
    def patch_identifier(self):
        """Patch the Identifier node handler, and return a context manager
        which yields the mock handler."""

        Identifier = mock.Mock()
        with mock.patch.dict(self.traverser.node_handlers,
                             Identifier=Identifier):
            yield Identifier

    def test_check_node_unknown(self):
        """Test that `check_node` raises errors when nodes of unknown types
        exist in arbitrary places."""

        for node in self.get_nodes('FooBar', traversed=True):
            with pytest.raises(AssertionError):
                self.traverser.check_node(node)

    def test_check_node_untraversed(self):
        """Test that `check_node` raises errors when untraversed nodes
        exist in arbitrary places."""

        for node in self.get_nodes('BlockStatement', traversed=False):
            with pytest.raises(AssertionError):
                self.traverser.check_node(node)

    def test_check_node_all_ok(self):
        """Test that `check_node` raises no errors when all seems well."""

        for node in self.get_nodes('BlockStatement', traversed=True):
            self.traverser.check_node(node)

    def test_double_traverse(self):
        """Test that an attempt to traverse the same node twice results in
        a failed assertion."""

        node = {'type': 'DebuggerStatement'}

        self.traverser.traverse(node)
        with pytest.raises(AssertionError):
            self.traverser.traverse(node)

    def test_traverse_none(self):
        """Test that an attempt to traverse `None` rather than a node dict
        does not result in an error."""

        self.traverser.traverse(None)

    def test_traverse_keywords(self):
        """Test that keywords passed to `traverse` are passed to the node
        handler method."""

        with self.patch_identifier() as Identifier:
            node = {'type': 'Identifier'}
            self.traverser.traverse(node, foo='bar')

            Identifier.assert_called_with(node, foo='bar')

    def test_traverse_handler(self):
        """Test that `traverse` calls the correct handler when called with
        a bare node."""

        node = {'type': 'Identifier'}

        with self.patch_identifier() as Identifier:
            self.traverser.traverse(node)

            assert '__traversed' in node
            Identifier.assert_called_once_with(node)

    def test_traverse_child(self):
        """Test that, when called with a second argument, the child node at
        the given key is traversed rather than the node itself."""

        node = {'type': 'Identifier',
                'foo': {'type': 'Identifier'}}

        with self.patch_identifier() as Identifier:
            self.traverser.traverse(node, 'foo')

            assert '__traversed' not in node
            assert '__traversed' in node['foo']

            Identifier.assert_called_once_with(node['foo'])

    def test_traverse_location(self):
        """Test that the location is set when a node is traversed."""

        with mock.patch.object(self.traverser, 'set_location') as set_loc:
            node = {'type': 'DebuggerStatement'}
            self.traverser.traverse(node)

            set_loc.assert_called_with(node)

    def test_set_location(self):
        """Test that `set_location` sets the current location to the location
        in a node."""

        node = {'loc': {'start': {'line': 42, 'column': 73}}}
        node_2 = {'loc': {'start': {'line': 41, 'column': 74}}}

        self.traverser.set_location(node)

        loc = Location(self.traverser.filename, 42, 73)
        assert self.traverser.location == loc
        assert self.traverser.line == 42
        assert self.traverser.position == 73

        # Calling with a node without any location does not change the
        # current location.
        self.traverser.set_location({})
        assert self.traverser.location == loc

        self.traverser.set_location({'loc': None})
        assert self.traverser.location == loc

        self.traverser.set_location(node_2)
        assert self.traverser.location == Location(self.traverser.filename,
                                                   41, 74)

    def test_run_cleanup(self):
        """Test that the global context's cleanup function is called at the
        end of the `run` method."""

        with mock.patch.object(self.traverser.global_, 'cleanup') as cleanup:
            self.traverser.run({'type': 'DebuggerStatement'})
            assert cleanup.called

    def test_run_check_node(self):
        """Test that `run` calls `check_node` on the given node if our error
        bundle has a `debug_level` set."""

        with mock.patch.object(self.traverser, 'check_node') as check_node:
            node = {'type': 'DebuggerStatement'}

            self.traverser.err.debug_level = 1
            self.traverser.run(node)

            check_node.assert_called_with(node)

    def test_run_no_check_node(self):
        """Test that `run` does not `check_node` on the given node if our error
        bundle has no `debug_level` set."""

        with mock.patch.object(self.traverser, 'check_node') as check_node:
            node = {'type': 'DebuggerStatement'}

            self.traverser.err.debug_level = 0
            self.traverser.run(node)

            assert not check_node.called

    def test_find_scope(self):
        """Test that the `find_scope` method behaves as expected."""

        find_scope = self.traverser.find_scope

        with self.push_context('default'):
            with self.push_context('block'):
                with self.push_context('block') as block_b:
                    with self.push_context('default') as top:
                        assert find_scope('block') is block_b
                        assert find_scope('default') is top
                        assert find_scope('foo') is self.traverser.global_

    def test_find_get_variable(self):
        """Test that the `find_variable` and `get_variable` methods work as
        expected."""

        find_variable = self.traverser.find_variable
        get_variable = self.traverser.get_variable

        global_ = self.traverser.global_

        # For each scope on the stack, shadow one variable from the scope
        # above, and declare two new variables (one of which will be
        # shadowed). Then, at the top of the stack, check that each variable
        # is pinned to the correct scope.

        global_.set('g_a', 'a')
        global_.set('g_b', 'b')

        with self.push_context('default') as func:
            func.set('g_b', 'func_b')

            func.set('f_a', 'a')
            func.set('f_b', 'b')

            with self.push_context('block') as block_a:
                block_a.set('f_b', 'block_b')

                block_a.set('b_a', 'a')
                block_a.set('b_b', 'b')

                with self.push_context('block') as block_b:
                    block_b.set('b_b', 'block_b')

                    block_b.set('bb_a', 'a')

                    assert find_variable('bb_a') is block_b
                    assert get_variable('bb_a').as_str() == 'a'

                    assert find_variable('b_b') is block_b
                    assert get_variable('b_b').as_str() == 'block_b'

                    assert find_variable('b_a') is block_a
                    assert get_variable('b_a').as_str() == 'a'

                    assert find_variable('f_b') is block_a
                    assert get_variable('f_b').as_str() == 'block_b'

                    assert find_variable('g_b') is func
                    assert get_variable('g_b').as_str() == 'func_b'

                    assert find_variable('f_a') is func
                    assert get_variable('f_a').as_str() == 'a'

                    assert find_variable('g_a') is global_
                    assert get_variable('g_a').as_str() == 'a'

                    # Undeclared variables end up on the global too.
                    assert find_variable('foo_thing') is global_

                    # However, if they don't exist when we try to get their,
                    # wrapper, we raise a KeyError unless `instantiate` is
                    # passed.
                    with pytest.raises(KeyError):
                        get_variable('foo_thing', instantiate=False)

                    get_variable('foo_thing', instantiate=True)

                    # It exists now, so no error.
                    get_variable('foo_thing', instantiate=False)
