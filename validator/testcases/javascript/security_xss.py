"""Security tests which deal with security barriers, code evaluation, markup
escaping, and so forth."""
from __future__ import absolute_import, print_function, unicode_literals

import re

from validator.constants import EVENT_ASSIGNMENT

from ..regex.generic import FILE_REGEXPS
from ..scripting import test_js_file
from .jstypes import Global, Hook, Interfaces, JSObject, Wildcards


Global.hook(
    ('netscape', 'security', 'PrivilegeManager', 'enablePrivilege'),
    on_call={
        'signing_help':
            'Any references to this API must be removed from your extension. '
            'Add-ons using this API will not be accepted for signing.',
        'signing_severity': 'high',
        'description':
            'enablePrivilege is extremely dangerous, and nearly always '
            'unnecessary. It should not be used under any circumstances.'})


# HTML.

# Template libraries.

UNSAFE_TEMPLATE_METHOD = (
    'The use of `{method}` can lead to unsafe remote code execution, and '
    'therefore must be done with great care, and only with sanitized data.')

for method in ('Handlebars.SafeString',
               # Angular.
               '$sce.trustAs',
               '$sce.trustAsHTML'):
    Global.hook(method.split('.'),
                on_call=UNSAFE_TEMPLATE_METHOD.format(method=method))

# Template escape sequences.
FILE_REGEXPS.extend(
    (re.escape(unsafe),
     {'filter': {
         'extension': ('.js', '.jsm', '.hbs', '.handlebars', '.mustache',
                       '.htm', '.html', '.xhtml', '.thtml', '.tmpl', '.tpl')},

      'err_id': ('testcases_regex', 'file', 'unsafe-template-escapes'),
      'warning': 'Potentially unsafe template escape sequence',
      'description':
         'The use of non-HTML-escaping template escape sequences is '
         'potentially dangerous and highly discouraged. Non-escaped '
         'HTML may only be used when properly sanitized, and in most '
         'cases safer escape sequences such as `{0}` must be used '
         'instead.'.format(safe)})

    for unsafe, safe in (('<%=', '<%-'),
                         ('{{{', '{{{{'),  # .format() changes to `{{`.
                         ('ng-bind-html-unsafe=', 'ng-bind-html'))
)

# innerHTML and friends.

JS_URL = re.compile(r"""\bhref\s*=\s*['"]\s*javascript:""")


def set_HTML(function, new_value, traverser):
    """Test that values being assigned to innerHTML and outerHTML are not
    dangerous."""

    if new_value.is_literal:
        literal_value = new_value.as_str()
        # Static string assignments

        HELP = ('Please avoid including JavaScript fragments in '
                'HTML stored in JavaScript strings. Event listeners '
                'should be added via `addEventListener` after the HTML '
                'has been injected.',
                'Injecting <script> nodes should be avoided when at all '
                'possible. If you cannot avoid loading a script directly '
                'into a content document, please consider doing so via '
                'the subscript loader (http://mzl.la/1VGxOPC) instead. '
                'If the subscript loader is not available, then the '
                'script nodes should be created using `createElement`, '
                'and should use a `src` attribute pointing to a '
                '`resource:` URL within your extension.')

        # Test for on* attributes and script tags.
        if EVENT_ASSIGNMENT.search(literal_value.lower()):
            traverser.warning(
                err_id=('testcases_javascript_instancetypes',
                        'set_%s' % function, 'event_assignment'),
                warning='Event handler assignment via %s' % function,
                description=('When assigning event handlers, %s '
                             'should never be used. Rather, use a '
                             'proper technique, like addEventListener.'
                             % function,
                             'Event handler code: %s'
                             % literal_value.encode('ascii', 'replace')),
                signing_help=HELP,
                signing_severity='medium')

        if '<script' in literal_value or JS_URL.search(literal_value):
            traverser.warning(
                err_id=('testcases_javascript_instancetypes',
                        'set_%s' % function, 'script_assignment'),
                warning='Scripts should not be created with `%s`'
                        % function,
                description='`%s` should not be used to add scripts to '
                            'pages via script tags or JavaScript URLs. '
                            'Instead, use event listeners and external '
                            'JavaScript.' % function,
                signing_help=HELP,
                signing_severity='medium')

    if new_value.is_clean_literal:
        # Everything checks out, but we still want to pass it through
        # the markup validator. Turn off strict mode so we don't get
        # warnings about malformed HTML.
        from validator.testcases.markup.markuptester import (
            MarkupParser)
        parser = MarkupParser(traverser.err, strict=False, debug=True)
        parser.process(traverser.filename, literal_value, 'html')

    else:
        # Variable assignments
        traverser.warning(
            err_id=('testcases_javascript_instancetypes', 'set_%s' % function,
                    'variable_assignment'),
            warning='Markup should not be passed to `%s` dynamically.'
                    % function,
            description='Due to both security and performance concerns, '
                        '%s may not be set using dynamic values which have '
                        'not been adequately sanitized. This can lead to '
                        'security issues or fairly serious performance '
                        'degradation.' % function)


DOC_WRITE_MSG = ('https://developer.mozilla.org/docs/XUL/School_tutorial/'
                 'DOM_Building_and_HTML_Insertion')


@Global.hook(('document', 'write'), 'on_call')
@Global.hook(('document', 'writeln'), 'on_call')
def document_write(this, args, callee):
    this.traverser.warning(
        err_id=('js', 'document.write', 'evil'),
        warning='Use of `document.write` strongly discouraged.',
        description=('`document.write` will fail in many circumstances '
                     'when used in extensions, and has potentially severe '
                     'security repercussions when used improperly. '
                     'Therefore, it should not be used. See %s for more '
                     'information.' % DOC_WRITE_MSG))
    if not args:
        return
    set_HTML('document.write()', args[0], this.traverser)


# Direct element creation.

WARN_CREATE_SCRIPT = {
    'err_id': ('testcases_javascript_instanceactions', '_call_expression',
               'called_createelement'),
    'warning': 'createElement() used to create script tag',
    'description': 'Dynamic creation of script nodes can be unsafe if '
                   'contents are not static or are otherwise unsafe, '
                   'or if `src` is remote.',
    'signing_help': 'Please avoid using <script> tags to load scripts. '
                    'For potential alternatives, please see '
                    'https://developer.mozilla.org/en-US/Add-ons/'
                    'Overlay_Extensions/XUL_School/'
                    'Appendix_D:_Loading_Scripts',
    'signing_severity': 'medium',
}


WARN_CREATE_UNKNOWN = {
    'err_id': ('testcases_javascript_instanceactions', '_call_expression',
               'createelement_variable'),
    'warning': 'Variable element type being created',
    'description': ('createElement or createElementNS were used with a '
                    'variable rather than a raw string. Literal values '
                    'should be used when taking advantage of the element '
                    'creation functions.',
                    "E.g.: createElement('foo') rather than "
                    'createElement(el_type)'),
}


# Event attributes.

# Special-cased in jstypes.py
@Global.hook(('**', 'on*'), 'on_set')
def set_on_event(this, value, name=None):
    """Ensure that on* properties are not assigned string values."""

    if value.is_literal and isinstance(value.as_primitive(), basestring):
        this.traverser.warning(
            err_id=('testcases_javascript_instancetypes', 'set_on_event',
                    'on*_str_assignment'),
            warning='on* property being assigned string',
            description='Event handlers in JavaScript should not be '
                        'assigned by setting an on* property to a '
                        'string of JS code. Rather, consider using '
                        'addEventListener.',
            signing_help='Please add event listeners using the '
                         '`addEventListener` API. If the property you are '
                         'assigning to is not an event listener, please '
                         'consider renaming it, if at all possible.',
            signing_severity='medium')

    elif isinstance(value, JSObject) and 'handleEvent' in value:
        this.traverser.warning(
            err_id=('js', 'on*', 'handleEvent'),
            warning='`handleEvent` no longer implemented in Gecko 18.',
            description='As of Gecko 18, objects with `handleEvent` methods '
                        'may no longer be assigned to `on*` properties. Doing '
                        'so will be equivalent to assigning `null` to the '
                        'property.')

# Security barriers:

# Export APIs.

FUNCTION_EXPORT_HELP = (
    'Given the potential security risks of exposing APIs to unprivileged '
    'code, extensions which use these APIs must undergo manual review for at '
    'least one submission. If you are not using these APIs to interact with '
    'content code, please consider alternatives, such as built-in '
    'message passing functionality.')


@Global.hook
class Components(Hook):
    class utils(Hook):
        @Hook.on_call
        def cloneInto(this, args, callee):
            return {
                'editors_only': True,
                'signing_help': FUNCTION_EXPORT_HELP,
                'signing_severity': 'low',
                'description':
                    'Can be used to expose privileged functionality to '
                    'unprivileged scopes. Care should be taken to ensure '
                    'that this is done safely.',
            }

        @Hook.on_call
        def exportFunction(this, args, callee):
            return {
                'editors_only': True,
                'signing_help': FUNCTION_EXPORT_HELP,
                'signing_severity': 'low',
                'description':
                    'Can be used to expose privileged functionality to '
                    'unprivileged scopes. Care should be taken to ensure '
                    'that this is done safely.',
            }


Global.hook(('**', '__exposedProps__'),
            on_set={
    'warning': 'Use of deprecated __exposedProps__ declaration',
    'description': (
        'The use of __exposedProps__ to expose objects to unprivileged '
        'scopes is dangerous, and has been deprecated. If objects '
        'must be exposed to unprivileged scopes, `cloneInto` or '
        '`exportFunction` should be used instead.'),
    'signing_help': 'If you are using this API to expose APIs to content, '
                    'please use `Components.utils.cloneInto`, or '
                    '`Components.utils.exportFunction` '
                    '(http://mzl.la/1fvvgm9). If you are using it '
                    'for other purposes, please consider using a built-in '
                    'message passing interface instead. Extensions which '
                    'expose APIs to content will be required to go through '
                    'manual code review for at least one submission.',
    'signing_severity': 'high'})


# Unsafe wrapper use.

@Global.hook(('XPCNativeWrapper', 'unwrap'), 'return')
@Global.hook(('Components', 'utils', 'waiveXrays'), 'return')
def js_unwrap(this, args, callee=None):
    """Return the unwrapped variant of an unwrapped JSObject."""
    if args:
        # FIXME(Kris): Unwrapping and then rewrapping should always result in
        # the same object, even many levels deep.
        obj = args[0].copy()
        obj.add_hooks({'unwrapped': True, 'inherit': {'unwrapped',
                                                      'inherit'}})

        return obj


@Global.hook(('XPCNativeWrapper',), 'return')
@Global.hook(('Components', 'utils', 'unwaiveXrays'), 'return')
def js_wrap(this, args, callee=None):
    """Return the wrapped variant of an unwrapped JSObject."""
    if len(args) > 1:
        this.traverser.warning(
            err_id=('testcases_js_xpcom', 'xpcnativewrapper', 'shallow'),
            warning='Shallow XPCOM wrappers should not be used',
            description='Shallow XPCOM wrappers are never necessary and '
                        'should not be used. Please use standard, deep '
                        'wrappers instead.',
            signing_help='Extensions making use of shallow wrappers will not '
                         'be accepted for automated signing. Please remove '
                         'the second and subsequent arguments of any calls '
                         'to `XPCNativeWrapper`, as well as any code which '
                         'applies `XPCNativeWrapper` to properties obtained '
                         'from these shallowly wrapped objects.',
            signing_severity='high')

        # Do not mark shallow wrappers as not unwrapped.
        return args[0]

    if args:
        # FIXME(Kris): Unwrapping and then rewrapping should always result in
        # the same object, even many levels deep.
        obj = args[0].copy()
        obj.add_hooks({'unwrapped': False, 'inherit': {'unwrapped',
                                                       'inherit'}})

        return obj


@Global.hook('unsafeWindow', 'getter',
             on_get='The use of unsafeWindow is insecure and should be '
                    'avoided whenever possible. Consider using a different '
                    'API if it is available in order to achieve similar '
                    'functionality.')
def get_unsafeWindow(this, name, default):
    return js_unwrap(this, [this.traverser.global_['window']])


@Global.hook(('**', 'wrappedJSObject'), 'getter')
def get_wrappedJSObject(this, name, default):
    if this.hooks.get('scope') == 'content':
        # Only unwrap based on wrappedJSObject property access if we're fairly
        # certain the object comes from an unprivileged scope.
        return js_unwrap(this, [this.traverser.wrap(this)])

    return this.value


# Wildcard properties that look like they might be for DOM Elements.

@Wildcards.extend
class MaybeElement(Hook):

    # HTML insertion.

    @Hook.on_call
    def insertAdjacentHTML(this, args, callee):
        """
        Perfrom the same tests on content inserted into the DOM via
        insertAdjacentHTML as we otherwise would for content inserted via the
        various innerHTML/outerHTML properties.
        """
        if not args or len(args) < 2:
            return

        set_HTML('insertAdjacentHTML', args[1], this.traverser)

    @Hook.on_set
    def innerHTML(this, value, name=None):
        set_HTML('innerHTML', value, this.traverser)

    @Hook.on_set
    def outerHTML(this, value, name=None):
        set_HTML('outerHTML', value, this.traverser)

    # Direct element creation.

    @Hook.on_call
    def createElement(this, args, callee):
        if args:
            name = args[0]
            if name.as_str().lower() == 'script':
                return WARN_CREATE_SCRIPT
            elif not name.is_clean_literal:
                return WARN_CREATE_UNKNOWN

    @Hook.on_call
    def createElementNS(this, args, callee):
        if len(args) >= 2:
            name = args[1]
            if 'script' in name.as_str().lower():
                return WARN_CREATE_SCRIPT
            elif not name.is_clean_literal:
                return WARN_CREATE_UNKNOWN

    # Event listener attributes.

    @Hook.on_call
    def setAttribute(this, args, callee):
        """Check for attempts to set event listener attributes."""

        if not args:
            return

        name = args[0]
        if name.as_str().lower().startswith('on'):
            this.traverser.warning(
                err_id=('testcases_javascript_instanceactions', 'setAttribute',
                        'setting_on*'),
                warning='on* attribute being set using setAttribute',
                description=(
                    'To prevent vulnerabilities, event handlers (like '
                    "'onclick' and 'onhover') should always be defined "
                    'using addEventListener.'),
                signing_help=(
                    'Please use `addEventListener` any place you might '
                    'otherwise create event listener attributes. Event '
                    'listener attributes will not be accepted in add-ons '
                    'submitted for automated signing in any instance '
                    'where they may be reasonably avoided.'),
                signing_severity='medium')

    # Untrusted event listeners.

    @Hook.on_call
    def addEventListener(this, args, callee):
        """Handle calls to addEventListener and make sure that the
        fourth argument is falsy."""

        if len(args) > 3 and args[3].as_bool():
            this.traverser.notice(
                err_id=('js', 'instanceactions', 'addEventListener_fourth'),
                notice=(
                    '`addEventListener` called with truthy fourth argument.'),
                description=(
                    'When called with a truthy forth argument, listeners '
                    'can be triggered potentially unsafely by untrusted '
                    'code. This requires careful review.'))


# Unsafe window creation.

def open_in_chrome_context(uri, method, traverser):
    if not uri.is_clean_literal:
        traverser.notice(
            err_id=('js', 'instanceactions', '%s_nonliteral' % method),
            notice='`%s` called with non-literal parameter.' % method,
            description='Calling `%s` with variable parameters can result in '
                        'potential security vulnerabilities if the variable '
                        'contains a remote URI. Consider using `window.open` '
                        'with the `chrome=no` flag.' % method)

    remote_url = re.compile(r'^(https?|ftp|data):(//)?', re.I)
    uri = uri.as_str()
    if uri.startswith('//') or remote_url.match(uri):
        traverser.warning(
            err_id=('js', 'instanceactions', '%s_remote_uri' % method),
            warning='`%s` called with non-local URI.' % method,
            description='Calling `%s` with a non-local URI will result in the '
                        'dialog being opened with chrome privileges.' % method)


@Global.hook(('**', 'openDialog'), 'on_call')
def openDialog(this, args, callee):
    """Raise an error if the first argument is a remote URL."""
    if args:
        open_in_chrome_context(args[0], 'openDialog', this.traverser)


@Interfaces.hook(('nsIWindowWatcher', 'openWindow'), 'on_call')
def nsIWindowWatcher_openWindow(this, args, callee):
    if args:
        open_in_chrome_context(args[0], 'nsIWindowWatcher.openWindow',
                               this.traverser)


# Eval.

DANGEROUS_EVAL = {
    'err_id': ('javascript', 'dangerous_global', 'eval'),
    'description': ('Evaluation of strings as code can lead to security '
                    'vulnerabilities and performance issues, even in the '
                    'most innocuous of circumstances. Please avoid using ',
                    '`eval` and the `Function` constructor when at all '
                    'possible.',
                    'Alternatives are available for most use cases. See '
                    'https://developer.mozilla.org/en-US/Add-ons/'
                    'Overlay_Extensions/XUL_School/'
                    'Appendix_C:_Avoid_using_eval_in_Add-ons '
                    'for more information.'),
    'signing_help':
        'Please try to avoid evaluating strings as code wherever possible. '
        'Read over the linked document for suggested alternatives. '
        'If you are referencing the `Function` constructor without calling '
        'it, and cannot avoid continuing to do so, consider alternatives '
        'such as calling `Object.getPrototypeOf` on an existing function '
        'object.',
    'signing_severity': 'high'}

Global.hook(('Components', 'utils', 'evalInSandbox'),
            on_call={
                'editors_only': 'true',
                'signing_help': DANGEROUS_EVAL['signing_help'],
                'signing_severity': 'low'})


def check_eval(value):
    """If the given value is a literal, validates it as a script."""

    if value.is_literal:
        traverser = value.traverser

        test_js_file(traverser.err, traverser.filename, value.as_str(),
                     line=traverser.line, column=traverser.position,
                     context=traverser.context)


@Global.hook('eval', 'on_call')
def eval(this, args, callee):
    if args:
        check_eval(args[0])

    return DANGEROUS_EVAL


@Global.hook('Function', 'on_call')
def Function(this, args, callee):
    if args:
        check_eval(args[-1])

    return DANGEROUS_EVAL


# And friends.


@Global.hook(('**', 'contentScript'), 'on_set')
def set_contentScript(this, value):
    """Warns when values are assigned to the `contentScript` properties,
    which are essentially the same as calling `eval`."""

    check_eval(value)

    if not value.is_clean_literal:
        this.traverser.warning(
            err_id=('testcases_javascript_instanceproperties',
                    'contentScript', 'set_non_literal'),
            warning='`contentScript` properties should not be used',
            description='Creating content scripts from dynamic values '
                        'is dangerous and error-prone. Please use a separate '
                        'JavaScript file, along with the '
                        '`contentScriptFile` property instead.',
            signing_help='Please do not use the `contentScript` property '
                         'in any add-ons submitted for automated signing.',
            signing_severity='high')


@Global.hook('setTimeout', 'on_call')
@Global.hook('setInterval', 'on_call')
def setTimeout(this, args, callee):
    """
    Handler for setTimeout and setInterval. Should determine whether a[0]
    is a lambda function or a string. Strings are banned, lambda functions are
    ok. Since we can't do reliable type testing on other variables, we flag
    those, too.
    """

    if not args:
        return

    if args[0].callable:
        return

    check_eval(args[0])

    return {'err_id': ('javascript', 'dangerous_global', 'eval'),
            'description':
                'In order to prevent vulnerabilities, the `setTimeout` '
                'and `setInterval` functions should be called only with '
                'function expressions as their first argument.',
            'signing_help': (
                'Please do not ever call `setTimeout` or `setInterval` with '
                'string arguments. If you are passing a function which is '
                'not being correctly detected as such, please consider '
                'passing a closure or arrow function, which in turn calls '
                'the original function.'),
            'signing_severity': 'high'}
