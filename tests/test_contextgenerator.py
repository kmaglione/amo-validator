from nose.tools import eq_
from validator.contextgenerator import ContextGenerator


def test_load_data():
    """Test that data is loaded properly into the CG."""

    d = """abc
    def
    ghi"""
    c = ContextGenerator(d)
    print c.data
    assert len(c.data) == 3

    # Through inductive reasoning, we can assert that every other line
    # is imported properly
    assert c.data[0].strip() == 'abc'
    assert c.data[1].strip() == 'def'


def test_get_context():
    """Test that contexts are generated properly."""

    d = open('tests/resources/contextgenerator/data.txt').read()
    c = ContextGenerator(d)
    print c.data

    c_start = c.get_context(line=1, column=0)
    c_end = c.get_context(line=11, column=0)
    print c_start
    print c_end
    # Contexts are always length 3
    assert len(c_start) == 3
    assert c_start[0] == None
    assert len(c_end) == 3
    assert c_end[2] == None

    assert c_start[1] == '0123456789'
    assert c_end[0] == '9012345678'
    assert c_end[1] == ''

    c_mid = c.get_context(line=5)
    assert len(c_mid) == 3
    assert c_mid[0] == '3456789012'
    assert c_mid[2] == '5678901234'
    print c_mid


def test_get_context_trimming():
    """
    Test that contexts are generated properly when lines are >140 characters.
    """

    d = open('tests/resources/contextgenerator/longdata.txt').read()
    c = ContextGenerator(d)
    print c.data

    trimmed = c.get_context(line=2, column=89)
    proper_lengths = (140, 148, 140)
    print trimmed
    print [len(x) for x in trimmed]

    for i in range(3):
        eq_(len(trimmed[i]), proper_lengths[i])


def test_get_context_trimming_inverse():
    """
    Tests that surrounding lines are trimmed properly; the error line is
    ignored if it is less than 140 characters.
    """

    d = open('tests/resources/contextgenerator/longdata.txt').read()
    c = ContextGenerator(d)
    print c.data

    trimmed = c.get_context(line=6, column=0)
    print trimmed

    assert trimmed[1] == 'This line should be entirely visible.'
    assert trimmed[0][0] != 'X'
    assert trimmed[2][-1] != 'X'


def test_get_line():
    """Test that the context generator returns the proper line."""

    d = open('tests/resources/contextgenerator/data.txt').read()
    c = ContextGenerator(d)

    assert c.get_line(30) == 3
    assert c.get_line(11) == 2
    assert c.get_line(10000) is None


def test_leading_whitespace():
    """Test that leading whitespace is trimmed properly."""

    def run(data, expectation, line=2):
        # Strip blank lines.
        data = '\n'.join(filter(None, data.split('\n')))
        # Get the context and assert its equality.
        c = ContextGenerator(data)
        eq_(c.get_context(line), expectation)

    run(' One space\n'
        '  Two spaces\n'
        '   Three spaces',
        ('One space', ' Two spaces', '  Three spaces'))
    run('\n  \n   ',
        ('', '', ''))
    run('  Two\n'
        ' One\n'
        '   Three',
        (' Two', 'One', '  Three'))
    run('None\n'
        ' One\n'
        ' One',
        ('None', ' One', ' One'))
