"""Security tests which deal with security barriers, code evaluation, markup
escaping, and so forth."""

import re
from functools import partial

from validator.constants import EVENT_ASSIGNMENT
from ..regex.generic import FILE_REGEXPS
from ..scripting import test_js_file
from .entity_values import register_entity
from .instanceactions import INSTANCE_DEFINITIONS
from .instanceproperties import OBJECT_DEFINITIONS
from .predefinedentities import hook_global


hook_global(
    (u'netscape', u'security', u'PrivilegeManager', u'enablePrivilege'),
    dangerous={
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
    hook_global(method.split('.'),
                dangerous=UNSAFE_TEMPLATE_METHOD.format(method=method))

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

    new_value = traverser.wrap(new_value)
    if new_value.is_literal():
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

    if new_value.is_clean_literal():
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


def insertAdjacentHTML(args, traverser, node, wrapper):
    """
    Perfrom the same tests on content inserted into the DOM via
    insertAdjacentHTML as we otherwise would for content inserted via the
    various innerHTML/outerHTML properties.
    """
    if not args or len(args) < 2:
        return

    content = traverser._traverse_node(args[1])
    set_HTML('insertAdjacentHTML', content, traverser)


INSTANCE_DEFINITIONS.update({
    'insertAdjacentHTML': insertAdjacentHTML,
})

OBJECT_DEFINITIONS.update({
    'innerHTML': {'set': partial(set_HTML, 'innerHTML')},
    'outerHTML': {'set': partial(set_HTML, 'outerHTML')},
})

DOC_WRITE_MSG = ('https://developer.mozilla.org/docs/XUL/School_tutorial/'
                 'DOM_Building_and_HTML_Insertion')


@register_entity('document.writeln')
@register_entity('document.write')
def document_write(traverser):
    def on_write(wrapper, arguments, traverser):
        traverser.warning(
            err_id=('js', 'document.write', 'evil'),
            warning='Use of `document.write` strongly discouraged.',
            description=('`document.write` will fail in many circumstances ',
                         'when used in extensions, and has potentially severe '
                         'security repercussions when used improperly. '
                         'Therefore, it should not be used. See %s for more '
                         'information.' % DOC_WRITE_MSG))
        if not arguments:
            return
        value = traverser._traverse_node(arguments[0])

        set_HTML('document.write()', value, traverser)

    return {'return': on_write}


# Export APIs.

FUNCTION_EXPORT_HELP = (
    'Given the potential security risks of exposing APIs to unprivileged '
    'code, extensions which use these APIs must undergo manual review for at '
    'least one submission. If you are not using these APIs to interact with '
    'content code, please consider alternatives, such as built-in '
    'message passing functionality.')

hook_global((u'Components', u'utils', u'cloneInto'),
            dangerous={
    'editors_only': True,
    'signing_help': FUNCTION_EXPORT_HELP,
    'signing_severity': 'low',
    'description': 'Can be used to expose privileged functionality to '
                   'unprivileged scopes. Care should be taken to ensure '
                   'that this is done safely.'})

hook_global((u'Components', u'utils', u'exportFunction'),
            dangerous={
    'editors_only': True,
    'signing_help': FUNCTION_EXPORT_HELP,
    'signing_severity': 'low',
    'description': 'Can be used to expose privileged functionality to '
                   'unprivileged scopes. Care should be taken to ensure '
                   'that this is done safely.'})


def set__exposedProps__(new_value, traverser):
    traverser.warning(
        err_id=('testcases_javascript_instanceproperties', '__exposedProps__'),
        warning='Use of deprecated __exposedProps__ declaration',
        description=(
            'The use of __exposedProps__ to expose objects to unprivileged '
            'scopes is dangerous, and has been deprecated. If objects '
            'must be exposed to unprivileged scopes, `cloneInto` or '
            '`exportFunction` should be used instead.'),
        signing_help='If you are using this API to expose APIs to content, '
                     'please use `Components.utils.cloneInto`, or '
                     '`Components.utils.exportFunction` '
                     '(http://mzl.la/1fvvgm9). If you are using it '
                     'for other purposes, please consider using a built-in '
                     'message passing interface instead. Extensions which '
                     'expose APIs to content will be required to go through '
                     'manual code review for at least one submission.',
        signing_severity='high')

OBJECT_DEFINITIONS.update({
    '__exposedProps__': {'set': set__exposedProps__},
})


# Unsafe wrapper use.

def js_unwrap(wrapper, arguments, traverser):
    """Return the unwrapped variant of an unwrapped JSObject."""
    if not arguments:
        traverser._debug('UNWRAP:NO ARGS')
        return

    with traverser._debug('UNWRAPPING OBJECT'):
        obj = traverser._traverse_node(arguments[0])

    # FIXME(kris): We should be returning a new (cached) object here, not
    # altering the original. Wrapping and unwrapping does not alter the
    # original object.
    obj.value.is_unwrapped = True

    return obj


def js_wrap(wrapper, arguments, traverser):
    """Return the wrapped variant of an unwrapped JSObject."""
    if not arguments:
        traverser._debug('WRAP:NO ARGS')
        return

    traverser._debug('WRAPPING OBJECT')
    obj = traverser._traverse_node(arguments[0])

    if len(arguments) > 1:
        traverser.warning(
            err_id=('testcases_js_xpcom', 'xpcnativewrapper', 'shallow'),
            warning='Shallow XPCOM wrappers should not be used',
            description='Shallow XPCOM wrappers are seldom necessary and '
                        'should not be used. Please use deep wrappers '
                        'instead.',
            signing_help='Extensions making use of shallow wrappers will not '
                         'be accepted for automated signing. Please remove '
                         'the second and subsequent arguments of any calls '
                         'to `XPCNativeWrapper`, as well as any code which '
                         'applies `XPCNativeWrapper` to properties obtained '
                         'from these shallowly wrapped objects.',
            signing_severity='high')
        # Do not mark shallow wrappers as not unwrapped.
        return obj

    # FIXME(kris): We should be returning a new (cached) object here, not
    # altering the original. Wrapping and unwrapping does not alter the
    # original object.
    obj.value.is_unwrapped = False

    return obj


hook_global((u'unsafeWindow',),
            dangerous='The use of unsafeWindow is insecure and should be '
                      'avoided whenever possible. Consider using a different '
                      'API if it is available in order to achieve similar '
                      'functionality.')

hook_global((u'XPCNativeWrapper',),
            return_=js_wrap)

hook_global((u'XPCNativeWrapper', u'unwrap'),
            return_=js_unwrap)

hook_global((u'Components', u'utils', u'waiveXrays'),
            return_=js_unwrap)

hook_global((u'Components', u'utils', u'unwaiveXrays'),
            return_=js_wrap)


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

hook_global((u'Components', u'utils', u'evalInSandbox'),
            dangerous={
                'editors_only': 'true',
                'signing_help': DANGEROUS_EVAL['signing_help'],
                'signing_severity': 'low'})

hook_global((u'eval',), dangerous=DANGEROUS_EVAL)
hook_global((u'Function',), dangerous=DANGEROUS_EVAL)


# And friends.

def set_contentScript(value, traverser):
    """Warns when values are assigned to the `contentScript` properties,
    which are essentially the same as calling `eval`."""

    if value.is_literal():
        content_script = value.as_str()

        test_js_file(traverser.err, traverser.filename, content_script,
                     line=traverser.line, context=traverser.context)

    if not value.is_clean_literal():
        traverser.warning(
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

OBJECT_DEFINITIONS.update({
    'contentScript': {'set': set_contentScript},
})


def call_settimeout(a, t, e):
    """
    Handler for setTimeout and setInterval. Should determine whether a[0]
    is a lambda function or a string. Strings are banned, lambda functions are
    ok. Since we can't do reliable type testing on other variables, we flag
    those, too.
    """

    if not a:
        return

    if a[0]['type'] in ('FunctionExpression', 'ArrowFunctionExpression'):
        return

    if t(a[0]).callable:
        return

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

hook_global((u'setTimeout',), dangerous=call_settimeout)
hook_global((u'setInterval',), dangerous=call_settimeout)
