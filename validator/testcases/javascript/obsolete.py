from __future__ import absolute_import, print_function, unicode_literals

from .jstypes import Hook, Interfaces


OBSOLETE_EXTENSION_MANAGER = {
    'on_get': 'This interface is part of the obsolete extension manager '
              'interface, which is not available in any remotely modern '
              'version of Firefox. It should not be referenced in any '
              'code.'}

Interfaces.hook({
    'nsIExtensionManager': OBSOLETE_EXTENSION_MANAGER,
    'nsIUpdateItem': OBSOLETE_EXTENSION_MANAGER,
    'nsIInstallLocation': OBSOLETE_EXTENSION_MANAGER,
    'nsIAddonInstallListener': OBSOLETE_EXTENSION_MANAGER,
    'nsIAddonUpdateCheckListener': OBSOLETE_EXTENSION_MANAGER,
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


@Interfaces.hook
class nsIJSON(Hook):
    encode = {'on_call': NSIJSON_DEPRECATED}
    decode = {'on_call': NSIJSON_DEPRECATED}


# nsIWebBrowserPersist

WEBBROWSERPERSIST_DEPRECATED = {
    'err_id': ('testcases_javascript_call_definititions',
               'webbrowserpersist'),
    'warning': 'nsIWebBrowserPersist should no longer be used',
    'description':
        'Most nsIWebBrowserPersist methods have been '
        'superseded by simpler methods in Downloads.jsm, namely '
        '`Downloads.fetch` and `Downloads.createDownload`. See '
        'http://mzl.la/downloads-jsm for more information.',
}


@Interfaces.hook
class nsIWebBrowserPersist(Hook):
    saveChannel = {'on_call': WEBBROWSERPERSIST_DEPRECATED}
    savePrivacyAwareURI = {'on_call': WEBBROWSERPERSIST_DEPRECATED}

    @Hook.on_call
    def saveURI(this, args, callee):
        """nsIWebBrowserPersist.saveURI requires a valid privacy context as
        of Firefox 19."""
        if len(args) >= 7:
            load_context = args[6]
            if load_context.as_primitive() is None:
                this.traverser.warning(
                    err_id=('testcases_javascript_call_definititions',
                            'webbrowserpersist_saveuri'),
                    warning=('saveURI should not be called with a null load '
                             'context'),
                    description=(
                        'While nsIWebBrowserPersist.saveURI accepts null '
                        'in place of a privacy context, this usage is '
                        'acceptable only when no appropriate load '
                        'context exists.'))

        return WEBBROWSERPERSIST_DEPRECATED


# nsITransferable

@Interfaces.hook
class nsITransferable(Hook):
    @Hook.on_call
    def init(this, args, callee):
        if args and not args[0].as_primitive():
            this.traverser.warning(
                err_id=('js_entity_values', 'nsITransferable', 'init'),
                warning=(
                    '`nsITransferable.init` should not be called with `null` '
                    'as its first argument'),
                description=(
                    'Calling `nsITransferable.init()` with a null first '
                    'argument has the potential to leak data across '
                    'private browsing mode sessions. `null` is  '
                    'appropriate only when reading data or writing data '
                    'which is not associated with a particular window.'))
