from nose.tools import eq_

from validator.constants import MAX_STR_SIZE

from js_helper import _do_test, _do_test_raw, _get_var

def test_basic_concatenation():
    'Tests that contexts work and that basic concat ops are executed properly'

    err = _do_test('tests/resources/javascript/basicstrings.js')
    assert err.message_count == 0

    assert _get_var(err, 'x') == 'foo'
    assert _get_var(err, 'y') == 'bar'
    assert _get_var(err, 'z') == 'foobar'
    assert _get_var(err, 'a') == '5'
    assert _get_var(err, 'b') == '6'
    assert _get_var(err, 'c') == '56'
    assert _get_var(err, 'd') == 1
    assert _get_var(err, 'e') == 30
    assert _get_var(err, 'f') == 5


def test_augconcat():
    'Tests augmented concatenation operators'

    err = _do_test_raw("""
    var x = "foo";
    x += "bar";
    """)
    assert not err.message_count
    eq_(_get_var(err, 'x'), 'foobar')

    err = _do_test_raw("""
    var x = {"xyz":"foo"};
    x["xyz"] += "bar";
    """)
    assert not err.message_count

    xyz_val = err.final_context.data['x'].get('xyz').as_primitive()
    assert xyz_val == 'foobar'


def test_typecasting():
    'Tests that strings are treated as numbers when necessary'

    err = _do_test('tests/resources/javascript/strings_typecasting.js')
    assert err.message_count == 0

    assert _get_var(err, 'x') == '44'
    assert _get_var(err, 'y') == 16


def test_max_str_size_aug_assig():
    """Test that the max string size is enforced for augmented assignment."""

    # Create a string and max out its size.
    err = _do_test_raw("""
    var x = "%s";
    x += x;
    x += x;
    """ % ('x' * (MAX_STR_SIZE / 2)))
    eq_(len(_get_var(err, 'x')), MAX_STR_SIZE)


def test_max_str_size_binop():
    """Test that the max string size is enforced for binary operators."""

    # Create a string and max out its size.
    err = _do_test_raw("""
    var x = "%s";
    x = x + x;
    x = x + x;
    """ % ('x' * (MAX_STR_SIZE / 2)))
    eq_(len(_get_var(err, 'x')), MAX_STR_SIZE)
