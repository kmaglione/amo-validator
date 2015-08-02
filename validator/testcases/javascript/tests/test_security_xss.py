import pytest

from tests.helper import Contains, Exists, Matches, NonEmpty, RegexTestCase
from tests.js_helper import TestCase


class TestGeneric(TestCase):
    def test_enablePrivilege(self):
        """Test that the deprecated enablePrivilege API is flagged."""

        self.run_script("""
            netscape.security.PrivilegeManager.enablePrivilege();
        """)
        self.assert_warnings({'signing_help': NonEmpty(),
                              'signing_severity': 'high',
                              'description': Contains('enablePrivilege')})


class TestTemplates(TestCase, RegexTestCase):
    """Tests for various template-library-related security issues."""

    def test_mark_safe(self):
        """Test that the mark-safe methods for various template libraries
        are flagged."""

        for method in ['Handlebars.SafeString',
                       '$sce.trustAs',
                       '$sce.trustAsHTML']:
            self.setup_err()
            self.run_script('%s(foo);' % method)
            self.assert_warnings({
                'description': Contains('unsafe remote code execution')})

    def test_unsafe_tags(self):
        """Test that unsafe template escape sequences are flagged."""

        EXTENSIONS = ('.js', '.jsm', '.hbs', '.handlebars', '.mustache',
                      '.htm', '.html', '.xhtml', '.thtml', '.tmpl', '.tpl')

        for unsafe, safe, end in (('<%=', '<%-', '%>'),
                                  ('{{{', '{{', '}}}'),
                                  ('ng-bind-html-unsafe=', 'ng-bind-html',
                                   '')):
            for extension in EXTENSIONS:
                self.setup_err()
                self.run_js_regex('{0} xss {1}'
                                  .format(unsafe, end),
                                  filename='foo%s' % extension)

                self.assert_warnings(
                    {'description': Contains('`%s`' % safe),
                     'id': Contains('unsafe-template-escapes')})


class BaseTestHTML(object):
    """Tests for various HTML-related security issues."""

    def set_html(self, html):
        """Run a script fragment assigning the given string via
        insertAdjacentHTML."""

        self.run_script(self.code_pattern.format(html=html))

    def test_innerHTML_event(self):
        """Test that innerHTML assignments containing event listeners
        are flagged."""

        self.set_html(""" '<a onclick="doStuff()">Hello.</a>' """)

        self.assert_warnings(
            {'id': (Exists(), 'set_%s' % self.method, 'event_assignment'),
             'message': Contains('Event handler'),
             'description': Matches('addEventListener'),
             'signing_help': Matches('avoid including JavaScript'),
             'signing_severity': 'medium'})

    def test_innerHTML_script(self):
        """Test that innerHTML assignments containing <script> nodes are
        flagged."""

        for fragment in '<script>', '<script type="text/javascript">':
            self.setup_err()
            self.set_html("'%s</script>'" % fragment)

            self.assert_warnings(
                {'id': (Exists(), 'set_%s' % self.method, 'script_assignment'),
                 'message': Contains('Scripts'),
                 'description': Matches('should not be used'),
                 'signing_help': Matches('avoid including JavaScript'),
                 'signing_severity': 'medium'})

    # TODO: Test that anything else is passed to the markup tester.

    def test_innerhtml_dynamic(self):
        """Test that dynamic values assigned to innerHTML are flagged."""

        self.set_html('foo')

        self.assert_warnings(
            {'id': (Exists(), 'set_%s' % self.method, 'variable_assignment'),
             'message': Matches('Markup should not.*dynamically'),
             'description': Matches('not been adequately sanitized')})


class TestInnerHTML(BaseTestHTML, TestCase):
    method = 'innerHTML'
    code_pattern = 'foo.innerHTML = {html};'


class TestOuterHTML(BaseTestHTML, TestCase):
    method = 'outerHTML'
    code_pattern = 'foo.outerHTML = {html};'


class TestInsertAdjacentHTML(BaseTestHTML, TestCase):
    method = 'insertAdjacentHTML'
    code_pattern = 'foo.insertAdjacentHTML("beforebegin", {html});'


class TestDocumentWrite(BaseTestHTML, TestCase):
    method = 'document.write()'
    code_pattern = 'document.write({html});'

    def test_document_write(self):
        """Test that any use of `document.write` usses a warning that it's
        deprecated."""

        self.set_html('foo')
        self.assert_warnings({
            'id': ('js', 'document.write', 'evil'),
            'message': Matches('document\.write.*strongly discouraged'),
            'description': Matches('should not be used')})


class TestDocumentWriteLN(TestDocumentWrite):
    method = 'document.write()'
    code_pattern = 'document.writeln({html});'


class TestExportAPIs(TestCase):
    def test_function_export(self):
        """Test that the use of function export APIs raises signing
        warnings."""

        for method in 'cloneInto', 'exportFunction':
            self.setup_err()
            self.run_script('Components.utils.{0}(thing)'.format(method))

            self.assert_warnings({
                'description': Matches('expose privileged functionality'),
                'signing_help': Matches('exposing APIs to unprivileged code'),
                'signing_severity': 'low'})

    def test_exposed_props(self):
        """Test that assignment to __exposedProps__ raises signing warnings."""

        self.run_script('obj.__exposedProps__ = {};')
        self.assert_warnings({
            'id': Contains('__exposedProps__'),
            'message': Contains('deprecated'),
            'description': Matches('`cloneInto` or `exportFunction`'),
            'signing_help': Matches('expose APIs'),
            'signing_severity': 'high'})

        # Test that just getting the property is not flagged.
        self.setup_err()
        self.run_script('var foo = obj.__exposedProps__;')
        self.assert_silent()

    def test_shallow_wrappers(self):
        """Test that the use of shallow wrappers results in a signing
        warning."""

        self.run_script('XPCNativeWrapper(foo, "bar");')

        self.assert_warnings({
            'id': (Exists(), 'xpcnativewrapper', 'shallow'),
            'message': Contains('Shallow XPCOM wrappers'),
            'description': Matches('Shallow XPCOM'),
            'signing_help': Matches('second and subsequent arguments'),
            'signing_severity': 'high'})

    def test_unwrap(self):
        """Test that unwrapping objects results in the appropriate flags."""

        for method in ('Cu.waiveXrays({0})', 'XPCNativeWrapper.unwrap({0})',
                       '{0}.wrappedJSObject'):

            self.setup_err()

            # Global.
            self.run_script('var foo = ' + method.format('content'))
            if 'wrappedJSObject' not in method:
                # FIXME: This special case should not be needed.
                # This is broken.
                assert self.get_wrapper('foo').value.get('is_unwrapped')

            # Other random object.
            self.run_script('var bar = ' + method.format('thing'))
            assert self.get_wrapper('bar').value.is_unwrapped

    # FIXME: Test wrap, and add better tests for unwrap, once the
    # wrapping/unwrapping code has been fixed.

    def test_unsafeWindow(self):
        """Test that access to `unsafeWindow` is flagged."""

        self.run_script('var foo = unsafeWindow.bar;')
        self.assert_warnings({
            'description': Matches('unsafeWindow is insecure')})


class TestEval(TestCase):
    """Tests that unsafe uses of eval and similar functions are flagged."""

    BASE_MESSAGE = {
        'id': ('javascript', 'dangerous_global', 'eval'),
        'description': Matches('Evaluation of strings as code'),
        'signing_help': Matches('avoid evaluating strings'),
        'signing_severity': 'high'}

    def check_eval_literal(self, pattern):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        CODE = """'XPCNativeWrapper(foo, "bar")'"""

        scripts = (pattern.format(code=CODE),
                   'var fooThing = {code}; {0}'.format(
                       pattern.format(code='fooThing'),
                       code=CODE))

        for script in scripts:
            self.setup_err()
            self.run_script(script)
            self.assert_warnings({
                'id': (Exists(), 'xpcnativewrapper', 'shallow')})

    def test_eval(self):
        """Test that any use of eval results in a warning."""

        for pattern in 'eval({0})', 'Function({0})', 'Function("foo", {0})':
            for arg in '"foo"', 'foo':
                self.setup_err()
                self.run_script(pattern.format(arg))
                self.assert_warnings(self.BASE_MESSAGE)

    @pytest.mark.xfail(reason='Not implemented')
    def test_eval_literal(self):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        for pattern in ('eval({code})', 'Function({code})',
                        'Function("foo", {code})'):
            self.check_eval_literal(pattern)

    def test_setTimeout_function(self):
        """Test that setTimeout and setInterval called with function arguments
        is silent."""

        functions = ('function() {}',
                     'function x() {}',
                     'function* () {}',
                     'function* x() {}',
                     '() => {}',
                     '() => 1')

        functions += tuple('(%s).bind(foo, bar)' % func
                           for func in functions)

        declarations = (tuple('var x = %s;' % func
                              for func in functions) +
                        tuple('let x = %s;' % func
                              for func in functions) +
                        ('function x() {}',
                         'function* x() {}'))

        for setTimeout in 'setTimeout', 'setInterval':
            for func in functions:
                self.setup_err()
                self.run_script('{0}({1}, 100)'.format(setTimeout, func))
                self.assert_silent()

            for decl in declarations:
                self.setup_err()
                self.run_script('{0}; {1}(x, 100)'.format(decl, setTimeout))
                self.assert_silent()

    @pytest.mark.xfail(reason='Not implemented')
    def test_setTimeout_literal(self):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        for pattern in 'setTimeout({code}, 100)', 'setInterval({code}, 100)':
            self.check_eval_literal(pattern)

    def test_setTimeout_dynamic(self):
        """Test that running setTimeout or setInterval with a dynamic,
        non-function value results in the appropriate warning."""

        for pattern in 'setTimeout({code}, 100)', 'setInterval({code}, 100)':
            self.setup_err()
            self.run_script(pattern.format(code='foo'))

            self.assert_warnings(dict(
                self.BASE_MESSAGE,
                description=Matches('function expressions as their first arg'),
                signing_help=Matches('do not ever call.*string arguments')))

    def test_contentScript_literal(self):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        # FIXME: These messages are currently missing the appropriate
        # context.
        self.skip_sanity_check()

        for pattern in ('foo({{contentScript: {code}}})',
                        'x.contentScript = {code};'):
            self.check_eval_literal(pattern)

    def test_contentScript_dynamic(self):
        """Test that assigning a dynamic value to a content script results
        in a warning."""

        for code in ('foo({contentScript: foo})', 'x.contentScript = foo;'):
            self.setup_err()
            self.run_script(code)
            self.assert_warnings({
                'id': (Exists(), 'contentScript', 'set_non_literal'),
                'message': '`contentScript` properties should not be used',
                'description': Matches('dynamic values is dangerous and '
                                       'error-prone'),
                'signing_help': Matches('do not use'),
                'signing_severity': 'high'})
