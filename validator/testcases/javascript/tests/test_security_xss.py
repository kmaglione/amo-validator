from __future__ import absolute_import, print_function, unicode_literals

import itertools

import pytest

from tests.helper import Contains, Exists, Matches, NonEmpty, RegexTestCase
from tests.js_helper import TestCase


parametrize = pytest.mark.parametrize


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
            self.run_script('{method}(foo);'.format(**locals()))
            self.assert_warnings({
                'description': Contains('unsafe remote code execution')})

    def test_unsafe_tags(self):
        """Test that unsafe template escape sequences are flagged."""

        EXTENSIONS = ('.js', '.jsm', '.hbs', '.handlebars', '.mustache',
                      '.htm', '.html', '.xhtml', '.thtml', '.tmpl', '.tpl')

        for unsafe, safe, end in (('ng-bind-html-unsafe=', 'ng-bind-html', ''),
                                  ('<%=', '<%-', '%>'),
                                  ('{{{', '{{', '}}}')):
            for extension in EXTENSIONS:
                self.setup_err()
                self.run_js_regex('{0} xss {1}'.format(unsafe, end),
                                  filename='foo%s' % extension)

                self.assert_warnings(
                    {'description': Contains('`%s`' % safe),
                     'id': Contains('unsafe-template-escapes')})


class BaseTestHTML(TestCase):
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

    @parametrize('fragment', ('<script></script>',
                              '<script type="text/javascript"></script>'))
    def test_innerHTML_script(self, fragment):
        """Test that innerHTML assignments containing <script> nodes are
        flagged."""

        self.set_html("'{0}'".format(fragment))

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


class TestInnerHTML(BaseTestHTML):
    method = 'innerHTML'
    code_pattern = 'foo.innerHTML = {html};'


class TestOuterHTML(BaseTestHTML):
    method = 'outerHTML'
    code_pattern = 'foo.outerHTML = {html};'


class TestInsertAdjacentHTML(BaseTestHTML):
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

    @parametrize('method', ('cloneInto', 'exportFunction'))
    def test_function_export(self, method):
        """Test that the use of function export APIs raises signing
        warnings."""

        self.run_script('Components.utils.{0}(thing)'.format(method))

        self.assert_warnings({
            'description': Matches('expose privileged functionality'),
            'signing_help': Matches('exposing APIs to unprivileged code'),
            'signing_severity': 'low'})

    def test_exposed_props(self):
        """Test that assignment to __exposedProps__ raises signing warnings."""

        self.run_script('obj.__exposedProps__ = {};')
        self.assert_warnings({
            'id': Contains('**.__exposedProps__'),
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

    @parametrize('fragment', ('Cu.waiveXrays(object)',
                              'XPCNativeWrapper.unwrap(object)'))
    @parametrize('object_', ('content',  # A content window.
                             'content.document',
                             'foo_thing'))  # Some unknown thing.
    def test_unwrap(self, fragment, object_):
        """Test that unwrapping objects results in the appropriate flags."""

        self.run_script('var object = {object};'
                        'var foo = {unwrap};'
                        'var bar = foo.baz;'
                        .format(object=object_, unwrap=fragment))

        assert self.get_value('foo').hooks['unwrapped']
        assert self.get_value('bar').hooks['unwrapped']
        assert not self.get_value('object').hooks.get('unwrapped')

    @parametrize('object_,unwrapped', (
        ('content', True),
        ('content.foo', True),
        ('gBrowser.contentWindow', True),
        ('gBrowser.contentDocument', True),
        ('foo_thing', False),
        ('foo.thing', False),
    ))
    def test_unwrap_wrappedJSObject(self, object_, unwrapped):
        """Test that wrappedJSObject unwraps only when expected."""

        self.run_script('var object = {obj};'
                        'var foo = object.wrappedJSObject;'
                        'var bar = foo.baaz;'
                        'var baz = foo.bazz.xyz.quux;'
                        .format(obj=object_))

        assert self.get_value('foo').hooks.get('unwrapped', False) == unwrapped
        assert self.get_value('bar').hooks.get('unwrapped', False) == unwrapped
        assert self.get_value('baz').hooks.get('unwrapped', False) == unwrapped
        assert not self.get_value('object').hooks.get('unwrapped')

    @parametrize('fragment', ('Cu.unwaiveXrays(object)',
                              'XPCNativeWrapper(object)'))
    def test_wrap(self, fragment):
        """Test that wrapping objects has the appropriate results."""

        self.run_script('var foo = content;'
                        'var object = Cu.waiveXrays(foo);'
                        'var bar = {wrap};'
                        .format(wrap=fragment))

        assert self.get_value('object').hooks['unwrapped']
        assert not self.get_value('foo').hooks.get('unwrapped')
        assert not self.get_value('bar').hooks.get('unwrapped')

        for var in 'foo', 'object', 'bar':
            # Make sure all of the objects still have the expected hooks.
            assert 'document' in self.get_value(var).hooks['properties']

    def test_unsafeWindow(self):
        """Test that access to `unsafeWindow` is flagged."""

        self.run_script('var foo = unsafeWindow.bar;')
        self.assert_warnings({
            'description': Matches('unsafeWindow is insecure')})

    @pytest.fixture(params=('Cu.waiveXrays({object})',
                            'XPCNativeWrapper.unwrap({object})',
                            '{object}.wrappedJSObject'))
    def unwrap(self, request):
        return request.param

    @parametrize('script', ('unwrapped.x = y;',
                            'unwrapped.x.y.z = q;',
                            'var q = unwrapped.r; q.s.t = p;'))
    def test_unwrapped_assignment(self, unwrap, script):
        """Test that assignment to properties of unwrapped objects is
        flagged."""

        unwrapped = unwrap.format(object='content')

        self.run_script('var unwrapped = {unwrapped}; {script}'
                        .format(unwrapped=unwrapped, script=script))

        self.assert_warnings({
            'id': ('testcases_javascript_jstypes', 'JSObject_set',
                   'unwrapped_js_object'),
            'message': Contains('Assignment to unwrapped'),
        })

    @parametrize('script', ('unwrapped.x',
                            'unwrapped.x.y.z',
                            'var q = unwrapped.r; q.s.t;',
                            'var q = unwrapped; q = r;'))
    def test_unwrapped_non_assignment(self, unwrap, script):
        """Test that access to unwrapped properties without assignment does
        not trigger warnings."""

        unwrapped = unwrap.format(object='content')

        self.run_script('var unwrapped = {unwrapped}; {script}'
                        .format(unwrapped=unwrapped, script=script))

        self.assert_silent()


class TestEval(TestCase):
    """Tests that unsafe uses of eval and similar functions are flagged."""

    BASE_MESSAGE = {
        'id': ('javascript', 'dangerous_global', 'eval'),
        'description': Matches('Evaluation of strings as code'),
        'signing_help': Matches('avoid evaluating strings'),
        'signing_severity': 'high'}

    @pytest.fixture(params=('eval({code})',
                            'Function({code})',
                            'Function("foo", {code})'))
    def eval_pattern(self, request):
        return request.param

    def check_eval_literal(self, pattern):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        CODE = """'XPCNativeWrapper(foo, "bar")'"""

        scripts = (
            # Call eval directly.
            pattern.format(code=CODE),

            # Save to a variable first.
            ('var fooThing = {code}; '.format(code=CODE) +
             pattern.format(code='fooThing')),
        )

        for script in scripts:
            self.setup_err()
            self.run_script(script)
            self.assert_warnings({
                'id': (Exists(), 'xpcnativewrapper', 'shallow')})

    @parametrize('arg', ('"foo"', 'foo'))
    def test_eval(self, eval_pattern, arg):
        """Test that any use of eval results in a warning."""

        self.run_script(eval_pattern.format(code=arg))
        self.assert_warnings(self.BASE_MESSAGE)

    def test_eval_literal(self, eval_pattern):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        self.check_eval_literal(eval_pattern)

    # The branching factor for these will make your head spin. And it doesn't
    # even tests things declared in branches. Complete coverage is fine, and
    # all, but this is perhaps going a bit overboard. And underboard.

    @pytest.fixture(params=('setTimeout({code}, 100)',
                            'setInterval({code}, 100)'))
    def setTimeout_pattern(self, request):
        """Yields several variants of `setTimeout` and `setInterval`, each with
        a `{code}` format string replacement for its first parameter."""
        return request.param

    callables = [pattern.format(callable=callable)
                 for callable, pattern in itertools.product(
                     ('function() {}',
                      'function x() {}',
                      'function* () {}',
                      'function* x() {}',
                      '() => {}',
                      '() => 1',
                      'declared_function',
                      'declared_generator'),

                     ('({callable})',
                      '({callable}).bind()'))]

    @pytest.fixture(params=callables)
    def function_ish(self, request):
        """Yields a number of callable expression types, along with their
        counterparts returned by `.bind()`."""
        return request.param

    def test_setTimeout_function(self, setTimeout_pattern, function_ish):
        """Test that setTimeout and setInterval called with function arguments
        is silent."""

        base_script = '''
            function declared_function() {}
            function* declared_generator() {}
        '''

        self.run_script(base_script +
                        setTimeout_pattern.format(code=function_ish))
        self.assert_silent()

    @parametrize('declare', ('var thing = {callable};',
                             'const thing = {callable};',
                             'thing = {callable};',
                             'let thing = {callable};'))
    def test_setTimeout_var_function(self, setTimeout_pattern, function_ish,
                                     declare):

        base_script = '''
            function declared_function() {}
            function* declared_generator() {}
        '''
        declaration = declare.format(callable=function_ish)

        self.run_script(base_script + declaration +
                        setTimeout_pattern.format(code='thing'))

        self.assert_silent()

    def test_setTimeout_literal(self, setTimeout_pattern):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        self.check_eval_literal(setTimeout_pattern)

    def test_setTimeout_dynamic(self, setTimeout_pattern):
        """Test that running setTimeout or setInterval with a dynamic,
        non-function value results in the appropriate warning."""

        self.run_script(setTimeout_pattern.format(code='foo'))

        self.assert_warnings(dict(
            self.BASE_MESSAGE,
            description=Matches('function expressions as their first arg'),
            signing_help=Matches('do not ever call.*string arguments')))

    @parametrize('pattern', ('foo({{contentScript: {code}}})',
                             'x.contentScript = {code};'))
    def test_contentScript_literal(self, pattern):
        """Test that evaluating a literal results in the appropriate warnings
        for the literal's contents."""

        # FIXME: These messages are currently missing the appropriate
        # context.
        self.skip_sanity_check()

        self.check_eval_literal(pattern)

    @parametrize('code', ('foo({contentScript: foo})',
                          'x.contentScript = foo;'))
    def test_contentScript_dynamic(self, code):
        """Test that assigning a dynamic value to a content script results
        in a warning."""

        self.run_script(code)
        self.assert_warnings({
            'id': (Exists(), 'contentScript', 'set_non_literal'),
            'message': '`contentScript` properties should not be used',
            'description': Matches('dynamic values is dangerous and '
                                   'error-prone'),
            'signing_help': Matches('do not use'),
            'signing_severity': 'high'})
