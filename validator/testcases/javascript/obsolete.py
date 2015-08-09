from validator.constants import BUGZILLA_BUG
from .instanceproperties import OBJECT_DEFINITIONS
from .predefinedentities import INTERFACES, hook_interface


OBSOLETE_EXTENSION_MANAGER = {
    'value': {},
    'dangerous': 'This interface is part of the obsolete extension manager '
                 'interface, which is not available in any remotely modern '
                 'version of Firefox. It should not be referenced in any '
                 'code.'}

INTERFACES.update({
    u'nsIExtensionManager': OBSOLETE_EXTENSION_MANAGER,
    u'nsIUpdateItem': OBSOLETE_EXTENSION_MANAGER,
    u'nsIInstallLocation': OBSOLETE_EXTENSION_MANAGER,
    u'nsIAddonInstallListener': OBSOLETE_EXTENSION_MANAGER,
    u'nsIAddonUpdateCheckListener': OBSOLETE_EXTENSION_MANAGER,
})

# nsIJSON

NSIJSON_DEPRECATED = {
    'err_id': ('testcases_javascript_calldefinitions', 'nsIJSON', 'deprec'),
    'warning': 'Deprecated nsIJSON methods in use.',
    'description':
        'The `encode` and `decode` methods in nsIJSON have been '
        'deprecated since Gecko 7. You should use the methods in the '
        'global JSON object instead. See '
        'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference'
        '/Global_Objects/JSON for more information.'}

hook_interface(('nsIJSON', 'encode'),
               dangerous=NSIJSON_DEPRECATED)
hook_interface(('nsIJSON', 'decode'),
               dangerous=NSIJSON_DEPRECATED)


# nsIWebBrowserPersist

def webbrowserpersist(wrapper, arguments, traverser):
    """
    Most nsIWebBrowserPersist should no longer be used, in favor of the new
    Downloads.jsm interfaces.
    """
    traverser.warning(
        err_id=('testcases_javascript_call_definititions',
                'webbrowserpersist'),
        warning='nsIWebBrowserPersist should no longer be used',
        description=('Most nsIWebBrowserPersist methods have been '
                     'superseded by simpler methods in Downloads.jsm, namely '
                     '`Downloads.fetch` and `Downloads.createDownload`. See '
                     'http://mzl.la/downloads-jsm for more information.'))


def webbrowserpersist_saveuri(wrapper, arguments, traverser):
    """
    nsIWebBrowserPersist.saveURI requires a valid privacy context as
    of Firefox 19
    """
    if len(arguments) >= 7:
        load_context = traverser._traverse_node(arguments[6])
        if load_context.get_literal_value() is None:
            traverser.warning(
                err_id=('testcases_javascript_call_definititions',
                        'webbrowserpersist_saveuri'),
                warning=('saveURI should not be called with a null load '
                         'context'),
                description=('While nsIWebBrowserPersist.saveURI accepts null '
                             'in place of a privacy context, this usage is '
                             'acceptable only when no appropriate load '
                             'context exists.'))

    webbrowserpersist(wrapper, arguments, traverser)


hook_interface(('nsIWebBrowserPersist', 'saveChannel'),
               return_=webbrowserpersist)

hook_interface(('nsIWebBrowserPersist', 'savePrivacyAwareURI'),
               return_=webbrowserpersist)

hook_interface(('nsIWebBrowserPersist', 'saveURI'),
               return_=webbrowserpersist_saveuri)


# __proto__


def set__proto__(new_value, traverser):
    traverser.warning(
        err_id=('testcases_javascript_instanceproperties', '__proto__'),
        warning='Using __proto__ or setPrototypeOf to set a prototype is now '
                'deprecated.',
        description='Use of __proto__ or setPrototypeOf to set a prototype '
                    'causes severe performance degredation, and is '
                    'deprecated. You should use Object.create instead. '
                    'See bug %s for more information.' % BUGZILLA_BUG % 948227)


OBJECT_DEFINITIONS.update({
    '__proto__': {'set': set__proto__},
})
