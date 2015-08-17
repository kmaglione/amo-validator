from __future__ import absolute_import, print_function, unicode_literals

from validator.constants import BUGZILLA_BUG

from ..regex.generic import FILE_REGEXPS
from .jstypes import Global, Hook, Interfaces


# SQL.

SYNCHRONOUS_SQL_DESCRIPTION = (
    'The use of synchronous SQL via the storage system leads to severe '
    'responsiveness issues, and should be avoided at all costs. Please '
    'use asynchronous SQL via Sqlite.jsm (http://mzl.la/sqlite-jsm) or '
    'the `executeAsync` method, or otherwise switch to a simpler database '
    'such as JSON files or IndexedDB.')


def check_dynamic_sql(this, args, callee):
    """Check for the use of non-static strings when creating/exeucting SQL
    statements."""

    if len(args) >= 1 and not args[0].is_clean_literal:
        this.traverser.warning(
            err_id=('js', 'instanceactions', 'executeSimpleSQL_dynamic'),
            warning='SQL statements should be static strings',
            description=('Dynamic SQL statement should be constucted via '
                         'static strings, in combination with dynamic '
                         'parameter binding via Sqlite.jsm wrappers '
                         '(http://mzl.la/sqlite-jsm) or '
                         '`createAsyncStatement` '
                         '(https://developer.mozilla.org/en-US/docs'
                         '/Storage#Binding_parameters)'))


@Global.hook('**', 'extend')
class MaybeDBConnection(Hook):

    def createStatement(this, args, callee):
        """Handle calls to `createStatement`, returning an object which emits
        warnings upon calls to `execute` and `executeStep` rather than
        `executeAsync`."""
        check_dynamic_sql(this, args, callee)

        return this.traverser.wrap().query_interface(
            'mozIStorageBaseStatement')

    @Hook.on_call
    def createAsyncStatement(this, args, callee):
        check_dynamic_sql(this, args, callee)

    @Hook.on_call
    def executeSimpleSQL(this, args, callee):
        """Handle calls to `executeSimpleSQL`, warning that asynchronous
        methods should be used instead. """

        check_dynamic_sql(this, args, callee)

        return {'err_id': ('js', 'instanceactions', 'executeSimpleSQL'),
                'warning': 'Synchronous SQL should not be used',
                'description': SYNCHRONOUS_SQL_DESCRIPTION}


@Interfaces.hook
class mozIStorageBaseStatement(Hook):
    execute = {'on_call': SYNCHRONOUS_SQL_DESCRIPTION}
    executeStep = {'on_call': SYNCHRONOUS_SQL_DESCRIPTION}


# XMLHttpRequest.

@Interfaces.hook
class nsIXMLHttpRequest(Hook):
    @Hook.on_call
    def open(this, args, callee):
        """Check that XMLHttpRequest.open is not called synchronously."""

        if len(args) >= 3 and not args[2].as_bool():
            return ('Synchronous HTTP requests can cause serious UI '
                    'performance problems, especially for users with '
                    'slow network connections.')


@Global.hook('XMLHttpRequest', 'return')
def XMLHttpRequest(this, args, callee):
    return this.traverser.wrap().query_interface('nsIXMLHttpRequest')


# Other.

Interfaces.hook(('nsIAccessibleRetrieval',),
                on_get=(
    'Using the nsIAccessibleRetrieval interface causes significant '
    'performance degradation in Gecko. It should only be used in '
    'accessibility-related add-ons.'))


Interfaces.hook(('nsIDNSService', 'resolve'),
                on_call={
    'warning': '`nsIDNSService.resolve()` should not be used.',
    'description': 'The `nsIDNSService.resolve` method performs a '
                   'synchronous DNS lookup, which will freeze the UI. This '
                   'can result in severe performance issues. '
                   '`nsIDNSService.asyncResolve()` should be used instead.'})


Interfaces.hook(('nsISound', 'play'),
                on_call={
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


# Prototype mutation.

WARN_PROTOTYPE_MUTATION = {
    'err_id': ('testcases_javascript', 'performance', 'prototype_mutation'),
    'warning': 'Mutating the prototypes of existing objects is deprecated',
    'description': ('Mutating the prototypes of objects using `__proto__` or '
                    '`Object.setPrototypeOf` causes severe performance '
                    'degradation, and is deprecated. You should instead use '
                    '`Object.create` to create a new object with the given '
                    'prototype.',
                    'See bug %s for more information.'
                    % BUGZILLA_BUG % 948227),
}

Global.hook(('Object', 'setPrototypeOf'), on_call=WARN_PROTOTYPE_MUTATION)


@Global.hook(('**', '__proto__'), 'on_set')
def set__proto__(this, value):
    if this.set_by != 'object literal':
        # Warn only if this is an assignment. Ignore if it's a property
        # present in an object literal.
        return WARN_PROTOTYPE_MUTATION


# Event loop.

Global.hook(('**', 'processNextEvent'),
            on_call=(
    'Spinning the event loop with processNextEvent is a common cause of '
    'deadlocks, crashes, and other errors due to unintended reentrancy. '
    'Please use asynchronous callbacks instead wherever possible'))
