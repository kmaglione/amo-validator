from js_helper import _do_test_raw


def test_innerHTML():
    "Tests that the dev can't define event handlers in innerHTML."

    assert not _do_test_raw("""
    var x = foo();
    x.innerHTML = "<div></div>";
    """).failed()

    assert _do_test_raw("""
    var x = foo();
    x.innerHTML = "<div onclick=\\"foo\\"></div>";
    """).failed()

    assert _do_test_raw("""
    var x = foo();
    x.innerHTML = "x" + y + "z";
    """).failed()


def test_on_event():
    "Tests that on* properties are not assigned strings."

    assert not _do_test_raw("""
    var x = foo();
    x.fooclick = "bar";
    """).failed()

    assert _do_test_raw("""
    var x = foo();
    x.onclick = "bar";
    """).failed()
