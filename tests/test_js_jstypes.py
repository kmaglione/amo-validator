from nose.tools import eq_

from .js_helper import _do_test_raw

from validator.errorbundler import ErrorBundle
from validator.testcases.javascript import jstypes, traverser


traverser = traverser.Traverser(ErrorBundle(), 'stdin')


def test_jsarray_output():
    """Test that the output function for JSArray doesn't bork."""

    ja = jstypes.JSArray(traverser=traverser)
    ja.elements = [None, None]
    repr(ja)  # Used to throw tracebacks.
    ja.get_literal_value()  # Also used to throw tracebacks.


def test_jsobject_output():
    """Test that the output function for JSObject doesn't bork."""

    jso = jstypes.JSObject(traverser=traverser)
    jso.data = {'first': None}
    repr(jso)  # Used to throw tracebacks


def test_jsobject_recursion():
    """Test that circular references don't cause recursion errors."""

    jso = traverser.wrap(jstypes.JSObject())
    jso2 = traverser.wrap(jstypes.JSObject())

    jso.value.data = {'first': jso2}
    jso2.value.data = {'second': jso}

    assert '<recursive-reference>' in repr(jso.value)


def test_jsliteral_regex():
    """
    Test that there aren't tracebacks from JSLiterals that perform raw binary
    operations.
    """
    assert not _do_test_raw("""
    var x = /foo/gi;
    var y = x + " ";
    var z = /bar/i + 0;
    """).failed()


def test_jsarray_contsructor():
    """
    Test for tracebacks that were caused by JSArray not calling it's parent's
    constructor.
    """
    assert not _do_test_raw("""
    var x = [];
    x.foo = "bar";
    x["zap"] = "foo";
    baz("zap" in x);
    """).failed()


def test_jsobject_computed_properties():
    """
    Tests that computed property names work as expected.
    """

    ID = ('testcases_javascript_instancetypes', 'set_on_event',
          'on*_str_assignment')

    err1 = _do_test_raw("""
        var foo = {};
        foo["onthing"] = "stuff";
    """)
    err2 = _do_test_raw("""
        var foo = {
            ["onthing"]: "stuff",
        };
    """)

    eq_(err1.warnings[0]['id'], ID)
    eq_(err2.warnings[0]['id'], ID)

    assert not _do_test_raw("""
        var foo = {
            [Symbol.iterator]: function* () {},
            ["foo" + bar]: "baz",
            [thing]: "quux",
        };
    """).failed()


def test_jsobject_get_wrap():
    """Test that JSObject always returns a JSWrapper."""

    x = traverser.wrap(jstypes.JSObject()).value
    x.data['foo'] = traverser.wrap('bar').value

    out = x.get('foo')
    assert isinstance(out, jstypes.JSWrapper)
    eq_(out.get_literal_value(), 'bar')


def test_jsarray_get_wrap():
    """Test that JSArray always returns a JSWrapper."""

    x = traverser.wrap(jstypes.JSArray()).value
    x.elements = [None, traverser.wrap('bar').value]

    out = x.get('1')
    assert isinstance(out, jstypes.JSWrapper)
    eq_(out.get_literal_value(), 'bar')
