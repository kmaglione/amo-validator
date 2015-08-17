from __future__ import absolute_import, print_function, unicode_literals

from validator.decorator import post_init

from .jstypes import Global, Interfaces


# Create a hook for the base interface, just so that it explicitly exists.
Interfaces.hook('nsISupports')


# Services provided by the Services.jsm Services object.
SERVICES = {
    'appinfo': ('nsIXULAppInfo', 'nsIXULRuntime'),
    'appShell': 'nsIAppShellService',
    'blocklist': 'nsIBlocklistService',
    'cache': 'nsICacheService',
    'cache2': 'nsICacheStorageService',
    'clipboard': 'nsIClipboard',
    'console': 'nsIConsoleService',
    'contentPrefs': 'nsIContentPrefService',
    'cookies': ('nsICookieManager', 'nsICookieManager2', 'nsICookieService'),
    'dirsvc': ('nsIDirectoryService', 'nsIProperties'),
    'DOMRequest': 'nsIDOMRequestService',
    'domStorageManager': 'nsIDOMStorageManager',
    'downloads': 'nsIDownloadManager',
    'droppedLinkHandler': 'nsIDroppedLinkHandler',
    'eTLD': 'nsIEffectiveTLDService',
    'focus': 'nsIFocusManager',
    'io': ('nsIIOService', 'nsIIOService2'),
    'locale': 'nsILocaleService',
    'logins': 'nsILoginManager',
    'obs': 'nsIObserverService',
    'perms': 'nsIPermissionManager',
    'prefs': ('nsIPrefBranch2', 'nsIPrefService', 'nsIPrefBranch'),
    'prompt': 'nsIPromptService',
    'scriptloader': 'mozIJSSubScriptLoader',
    'scriptSecurityManager': 'nsIScriptSecurityManager',
    'search': 'nsIBrowserSearchService',
    'startup': 'nsIAppStartup',
    'storage': 'mozIStorageService',
    'strings': 'nsIStringBundleService',
    'sysinfo': 'nsIPropertyBag2',
    'telemetry': 'nsITelemetry',
    'tm': 'nsIThreadManager',
    'uriFixup': 'nsIURIFixup',
    'urlFormatter': 'nsIURLFormatter',
    'vc': 'nsIVersionComparator',
    'wm': 'nsIWindowMediator',
    'ww': 'nsIWindowWatcher',
}

Global.hook('Services')['properties'] = SERVICES


@post_init
def finalize_services():
    """Initialize the `Services` global based on the service definitions in
    SERVICES."""

    def get_service(interfaces):
        if not isinstance(interfaces, (list, tuple)):
            interfaces = interfaces,

        def value(traverser):
            return traverser.wrap().query_interface(*interfaces)
        return value

    for name, interfaces in SERVICES.items():
        SERVICES[name] = {'value': get_service(interfaces)}


# Common XPCOM shortcuts.

Global.hook(
    'Cc', overwritable=True,
    value=lambda traverser: traverser.global_['Components']['classes'])

Global.hook(
    'Ci', overwritable=True,
    value=lambda traverser: traverser.global_['Components']['interfaces'])

Global.hook(
    'Cu', overwritable=True,
    value=lambda traverser: traverser.global_['Components']['utils'])


# XPCOM base methods.

# `getInterface` really only needs to be handled for nsIInterfaceRequestor
# intarfaces, but as it's fair for code to assume that that
# interface has already been queried and methods with this name
# are unlikely to behave differently, we just process it for all
# objects.

@Global.hook(('**', 'getInterface'), 'return')
@Global.hook(('Components', 'classes', '*', 'getService'), 'return')
@Global.hook(('Components', 'classes', '*', 'createInstance'), 'return')
def createInstance(this, args, callee):
    return this.traverser.wrap().query_interface(args[0])


@Global.hook(('**', 'QueryInterface'), 'return')
def QueryInterface(this, args, callee):
    return this.query_interface(args[0])


# Contracts.

CONTRACT_ENTITIES = {}


@Global.hook(('Components', 'classes', '*'), 'on_get')
def check_contract(this, default, name=None):
    """Check properties of `Components.classes` against the list of dangerous
    contract IDs, and emit a warning if any are accessed."""

    if name in CONTRACT_ENTITIES:
        this.traverser.report(
            {'err_id': ('js', 'actions', 'dangerous_contract'),
             'warning': 'Dangerous XPCOM contract ID'},
            CONTRACT_ENTITIES[name])


@post_init
def finalize_interfaces():
    """Do some final post-processing of any interface defined in
    `Components.interfaces`, in particular, setting a canonical name,
    and adding an `interface` key for use by `query_interface`."""

    for interface, hooks in Interfaces['properties'].iteritems():
        hooks['interface'] = hooks
        hooks['interface']['interface_name'] = interface
