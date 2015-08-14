from ..regex.generic import FILE_REGEXPS
from .instanceactions import INSTANCE_DEFINITIONS
from .predefinedentities import build_quick_xpcom, hook_global, hook_interface


# SQL.

SYNCHRONOUS_SQL_DESCRIPTION = (
    'The use of synchronous SQL via the storage system leads to severe '
    'responsiveness issues, and should be avoided at all costs. Please '
    'use asynchronous SQL via Sqlite.jsm (http://mzl.la/sqlite-jsm) or '
    'the `executeAsync` method, or otherwise switch to a simpler database '
    'such as JSON files or IndexedDB.')


def _check_dynamic_sql(args, traverser, node=None, wrapper=None):
    """
    Check for the use of non-static strings when creating/exeucting SQL
    statements.
    """

    simple_args = map(traverser._traverse_node, args)
    if len(args) >= 1 and not simple_args[0].is_clean_literal():
        traverser.warning(
            err_id=('js', 'instanceactions', 'executeSimpleSQL_dynamic'),
            warning='SQL statements should be static strings',
            description=('Dynamic SQL statement should be constucted via '
                         'static strings, in combination with dynamic '
                         'parameter binding via Sqlite.jsm wrappers '
                         '(http://mzl.la/sqlite-jsm) or '
                         '`createAsyncStatement` '
                         '(https://developer.mozilla.org/en-US/docs'
                         '/Storage#Binding_parameters)'))


def createStatement(args, traverser, node, wrapper):
    """
    Handle calls to `createStatement`, returning an object which emits
    warnings upon calls to `execute` and `executeStep` rather than
    `executeAsync`.
    """
    _check_dynamic_sql(args, traverser)
    return build_quick_xpcom('createInstance', 'mozIStorageBaseStatement',
                             traverser, wrapper=True)


def executeSimpleSQL(args, traverser, node, wrapper):
    """
    Handle calls to `executeSimpleSQL`, warning that asynchronous methods
    should be used instead.
    """
    _check_dynamic_sql(args, traverser)
    traverser.warning(
        err_id=('js', 'instanceactions', 'executeSimpleSQL'),
        warning='Synchronous SQL should not be used',
        description=SYNCHRONOUS_SQL_DESCRIPTION)


INSTANCE_DEFINITIONS.update({
    'createAsyncStatement': _check_dynamic_sql,
    'createStatement': createStatement,
    'executeSimpleSQL': executeSimpleSQL,
})

hook_interface(('mozIStorageBaseStatement', 'execute'),
               dangerous=SYNCHRONOUS_SQL_DESCRIPTION)
hook_interface(('mozIStorageBaseStatement', 'executeStep'),
               dangerous=SYNCHRONOUS_SQL_DESCRIPTION)


# XMLHttpRequest.

def xhr_open(a, t, e):
    """Check that XMLHttpRequest.open is not called synchronously."""

    args = map(t, a)
    if len(args) >= 3 and not args[2].get_literal_value():
        return ('Synchronous HTTP requests can cause serious UI '
                'performance problems, especially for users with '
                'slow network connections.')

hook_global(('XMLHttpRequest', 'open'), dangerous=xhr_open)


# Other.

hook_interface(('nsIAccessibleRetrieval',),
               dangerous=(
    'Using the nsIAccessibleRetrieval interface causes significant '
    'performance degradation in Gecko. It should only be used in '
    'accessibility-related add-ons.'))


hook_interface(('nsIDNSService', 'resolve'),
               dangerous={
    'err_id': ('testcases_javascript_entity_values', 'nsIDNSServiceResolve'),
    'warning': '`nsIDNSService.resolve()` should not be used.',
    'description': 'The `nsIDNSService.resolve` method performs a '
                   'synchronous DNS lookup, which will freeze the UI. This '
                   'can result in severe performance issues. '
                   '`nsIDNSService.asyncResolve()` should be used instead.'})


hook_interface(('nsISound', 'play'),
               dangerous={
    'err_id': ('testcases_javascript_entity_values', 'nsISound_play'),
    'warning': '`nsISound.play` should not be used.',
    'description': 'The `nsISound.play` function is synchronous, and thus '
                   'freezes the interface while the sound is playing. It '
                   'should be avoided in favor of the HTML5 audio APIs.'})


FILE_REGEXPS.extend([
    # Use of deprecated DOM mutation events.
    (r'\b(?:on)?(?:%s)\b' % '|'.join((
        'DOMAttrModified', 'DOMAttributeNameChanged',
        'DOMCharacterDataModified', 'DOMElementNameChanged',
        'DOMNodeInserted', 'DOMNodeInsertedIntoDocument',
        'DOMNodeRemoved', 'DOMNodeRemovedFromDocument',
        'DOMSubtreeModified')),

     {'err_id': ('testcases_regex', 'file', 'mutation-events'),
      'warning': 'DOM mutation events are deprecated',
      'description': 'DOM mutation events officially deprecated, due '
                     'to their severe performance impact, and should not '
                     'be used. Please use MutationObserver '
                     'objects, or other triggers which do not involve '
                     'directly checking the DOM.'}),

    # Use of mouse events with potential performance impacts.
    (r'\b(?:on)?mouse(?:move|over|out)\b',
     {'err_id': ('testcases_regex', 'file', 'mouse-events'),
      'warning': 'Mouse events may cause performance issues.',
      'description': (
         'The use of `mousemove`, `mouseover`, and `mouseout` is '
         'discouraged. These events are dispatched with high frequency '
         'and can cause severe performance issues.')}),
])
