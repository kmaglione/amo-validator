from nose.tools import eq_

from .js_helper import _do_test_raw

from validator.errorbundler import ErrorBundle
from validator.testcases.javascript import traverser
from validator.testcases.javascript.jstypes import JSArray, JSObject, JSWrapper


traverser = traverser.Traverser(ErrorBundle(), 'stdin')


def test_jsarray_output():
    """Test that the output function for JSArray doesn't bork."""

    ja = JSArray(traverser=traverser)
    ja.elements = [None, None]
    repr(ja)  # Used to throw tracebacks.
    ja.as_primitive()  # Also used to throw tracebacks.


def test_jsobject_output():
    """Test that the output function for JSObject doesn't bork."""

    jso = JSObject(traverser=traverser)
    jso.data = {'first': None}
    repr(jso)  # Used to throw tracebacks


def test_jsobject_recursion():
    """Test that circular references don't cause recursion errors."""

    jso = traverser.wrap(JSObject())
    jso2 = traverser.wrap(JSObject())

    jso.value.data = {'first': jso2}
    jso2.value.data = {'second': jso}

    # Just make sure we don't spin into an infinite loop.
    repr(jso.value)


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

    ID = ('jstypes', 'hook_on_set', '**.__exposedProps__')

    err1 = _do_test_raw("""
        var foo = {};
        foo["__exposedProps__"] = "stuff";
    """)
    err2 = _do_test_raw("""
        var foo = {
            ["__exposedProps__"]: "stuff",
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

    x = traverser.wrap(JSObject()).value
    x['foo'] = traverser.wrap('bar').value

    out = x.get('foo')
    assert isinstance(out, JSWrapper)
    assert out.lvalue
    eq_(out.as_primitive(), 'bar')


def test_jsarray_get_wrap():
    """Test that JSArray always returns a JSWrapper."""

    x = JSArray([None, traverser.wrap('bar').value],
                traverser=traverser)

    out = x.get('1')
    assert isinstance(out, JSWrapper)
    eq_(out.as_primitive(), 'bar')
