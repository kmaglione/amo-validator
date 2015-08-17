import pytest

from .js_helper import TestCase, _do_test_raw

from validator.errorbundler import ErrorBundle
from validator.testcases.javascript import traverser


traverser = traverser.Traverser(ErrorBundle(), 'stdin')


def test_array_destructuring():
    """
    Make sure that multi-level and prototype array destructuring don't cause
    tracebacks.
    """
    assert not _do_test_raw("""
    [a, b, c, d] = [1, 2, 3, 4];
    [] = bar();
    """).failed()

    assert not _do_test_raw("""
    function foo(x, y, [a, b, c], z) {
        bar();
    }
    """).failed()


def test_get_as_num():
    """Test that _get_as_num performs as expected."""

    def test(input, output):
        assert traverser.wrap(input).as_float() == output

    yield test, 1, 1
    yield test, 1.0, 1.0
    yield test, '1', 1
    yield test, '1.0', 1.0
    yield test, None, 0
    yield test, '0xF', 15
    yield test, True, 1
    yield test, False, 0


def test_spidermonkey_warning():
    """
    Test that stderr warnings in Spidermonkey do not trip runtime errors.
    """
    # The following is attempting to store the octal "999999999999" in x, but
    # this is an invalid octal obviously. We need to "use strict" here because
    # the latest versions of spidermonkey simply accept that as a base 10
    # number, despite the "0" prefix.
    # We need spidermonkey to choke on this code, and this test makes sure that
    # when spidermonkey does, it doesn't break the validator.
    assert _do_test_raw("""
    "use strict";
    var x = 0999999999999;
    """).failed()


@pytest.mark.parametrize('block', (
    'function foo() { %s; }',
    'function foo() { %s; yield 1; }',
    'function foo() { yield %s; }',
    'var foo = function () { %s; }',
    'var foo = function () { %s; yield 1; }',
    'function* foo() { %s; }',
    'var foo = function* () { %s; }',
    'var foo = function () %s',
    'var foo = () => %s',
    'var foo = () => { %s }',
    'if (true) { %s }',
    'if (true) ; else { %s }',
    'while (true) { %s }',
    'do { %s } while (true)',
    'do {} while (%s)',

    'for (;;) { %s }',

    'for (x=%s;;) {}',
    'for (let x=%s;;) {}',
    'for (var x=%s;;) {}',
    'for (const x=%s;;) {}',

    'for (let x=foo;;) { %s }',
    'for (var x=foo;;) { %s }',

    'for (; %s;) {}',
    'for (;; %s) {}',

    'for (let x in y) { %s }',
    'for (let x of y) { %s }',
    'for (let x in (%s)) {}',
    'for (let x of (%s)) {}',

    '[%s for (x in thing)]',
    '[%s for (x in thing) if (stuff)]',
    '[x for (x in %s)]',
    '[x for (x in %s) if (stuff)]',
    '[x for (y in q) for (x in %s)]',
    '[x for (y in q) for (x in %s) if (stuff)]',
    '[x for (x in thing) if (%s)]',

    '[for (x of thing) %s]',
    '[for (x of thing) if (stuff) %s]',
    '[for (x of %s) x]',
    '[for (x of %s) if (stuff) x]',
    '[for (x of %s) for (y of q) x]',
    '[for (x of %s) for (y of q) if (stuff) x]',
    '[for (x of thing) if (%s) x]',

    'try { %s } catch (e) {}',
    'try {} catch (e) { %s }',
    'try {} finally { %s }',
    'try {} catch (e if %s) {}',
    'try {} catch (e if x) {} catch (e) { %s }',

    'switch (%s) {default:}',
    'switch (x) {case %s: 0;}',
    'switch (x) {case y: %s;}',
    'switch (x) {case z: ; case y: x; %s;}',
    'switch (x) {case z: ; default: %s;}',

    '(%s, x, y)',
    '(x, %s, y)',
    '(x, y, %s)',

    'with (x) {%s}',
    'with (%s) {}',

    'let x = %s',
    'var x = %s',
    'const x = %s',
))
def test_blocks_evaluated(block):
    """
    Tests that blocks of code are actually evaluated under normal
    circumstances.
    """

    ID = ('javascript', 'dangerous_global', 'eval')

    EVIL = 'eval(evilStuff)'

    err = _do_test_raw(block % EVIL)
    assert err.message_count == 1, \
        'Missing expected failure for block: %s' % block
    assert err.warnings[0]['id'] == ID


class TestTemplateString(TestCase):
    WARNING = {'id': ('testcases_chromemanifest', 'test_resourcemodules',
                      'resource_modules')}

    def test_template_string(self):
        """Tests that plain template strings trigger warnings like normal
        strings."""

        self.run_script('`JavaScript-global-property`')
        self.assert_failed(with_warnings=[self.WARNING])

    def test_template_complex_string(self):
        """Tests that complex template strings trigger warnings like normal
        strings."""

        self.run_script("`JavaS${'cript-'}glob${'al-pro'}perty`")
        self.assert_failed(with_warnings=[self.WARNING])

    def test_tagged_template_string(self):
        """Tests that tagged template strings are treated as calls."""

        warning = {'id': ('testcases_javascript_instanceactions',
                          '_call_expression', 'called_createelement')}

        assert not _do_test_raw("""
            d.createElement(); "script";
            d.createElement; "script";
        """).failed()

        self.run_script("""
            d.createElement`script`
        """)
        self.assert_failed(with_warnings=[warning])
