from functools import partial
import math

from validator.decorator import post_init
from .call_definitions import python_wrap, xpcom_constructor
from .jstypes import JSWrapper, Undefined
from . import actions, call_definitions


# A list of identifiers and member values that may not be used.
BANNED_IDENTIFIERS = {
    u'newThread':
        'Creating threads from JavaScript is a common cause '
        'of crashes and is unsupported in recent versions of the platform',
    u'processNextEvent':
        'Spinning the event loop with processNextEvent is a common cause of '
        'deadlocks, crashes, and other errors due to unintended reentrancy. '
        'Please use asynchronous callbacks instead wherever possible',
}


def is_shared_scope(traverser, right=None, node_right=None):
    """Returns true if the traverser `t` is traversing code loaded into
    a shared scope, such as a browser window. Particularly used for
    detecting when global overwrite warnings should be issued."""

    # FIXME(Kris): This is not a great heuristic.
    return not (traverser.is_jsm or
                traverser.err.get_resource('em:bootstrap') == 'true')


INTERFACES = {
    u'nsISupports': {'value': {}},
}

INTERFACE_ENTITIES = {
    u'nsIXMLHttpRequest': {
        'xpcom_map': lambda: GLOBAL_ENTITIES['XMLHttpRequest']},

    u'nsIDOMGeoGeolocation': {
        'dangerous': 'Use of the geolocation API by add-ons requires '
                     'prompting users for consent.'},

}

CONTRACT_ENTITIES = {}


def build_quick_xpcom(method, interface, traverser, wrapper=False):
    """A shortcut to quickly build XPCOM objects on the fly."""
    extra = ()
    if isinstance(interface, (list, tuple)):
        interface, extra = interface[0], interface[1:]

    def interface_obj(iface):
        return traverser._build_global(
            name=method,
            entity={'xpcom_map':
                lambda: INTERFACES.get(iface, INTERFACES['nsISupports'])})

    constructor = xpcom_constructor(method, pretraversed=True)
    obj = constructor(None, [interface_obj(interface)], traverser)

    for iface in extra:
        # `xpcom_constructor` really needs to be cleaned up so we can avoid
        # this duplication.
        iface = interface_obj(iface)
        iface = traverser._build_global('QueryInterface',
                                        iface.hooks['xpcom_map']())

        obj.hooks = obj.hooks.copy()

        value = obj.hooks['value'].copy()
        value.update(iface.hooks['value'])

        obj.hooks.update(iface.hooks)
        obj.hooks['value'] = value

    if isinstance(obj, JSWrapper) and not wrapper:
        return obj.hooks
    return obj


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

CONTENT_DOCUMENT = {'value': lambda t: GLOBAL_ENTITIES[u'document']}

# GLOBAL_ENTITIES is also representative of the `window` object.
GLOBAL_ENTITIES = {
    u'window': {'value': lambda t: {'value': GLOBAL_ENTITIES}},
    u'null': {'literal': lambda t: JSWrapper(None, traverser=t)},
    u'Cc': {'readonly': False,
            'value':
                lambda t: GLOBAL_ENTITIES['Components']['value']['classes']},
    u'Ci': {'readonly': False,
            'value':
                lambda t: GLOBAL_ENTITIES['Components']['value']['interfaces']},
    u'Cu': {'readonly': False,
            'value':
                lambda t: GLOBAL_ENTITIES['Components']['value']['utils']},

    # From Services.jsm.
    u'Services': {'value': SERVICES},

    u'document':
        {'value':
             {u'title':
                  {'overwriteable': True,
                   'readonly': False},
              u'defaultView':
                  {'value': lambda t: {'value': GLOBAL_ENTITIES}},
              u'loadOverlay':
                  {'dangerous':
                       lambda a, t, e:
                           not a or not t(a[0]).as_str().lower()
                               .startswith(('chrome:', 'resource:'))}}},

    u'encodeURI': {'readonly': True},
    u'decodeURI': {'readonly': True},
    u'encodeURIComponent': {'readonly': True},
    u'decodeURIComponent': {'readonly': True},
    u'escape': {'readonly': True},
    u'unescape': {'readonly': True},
    u'isFinite': {'readonly': True},
    u'isNaN': {'readonly': True},
    u'parseFloat': {'readonly': True},
    u'parseInt': {'readonly': True},

    u'Object':
        {'value':
             {u'prototype': {'readonly': is_shared_scope},
              u'constructor':  # Just an experiment for now
                  {'value': lambda t: GLOBAL_ENTITIES['Function']}}},
    u'String':
        {'value':
             {u'prototype': {'readonly': is_shared_scope}},
         'return': call_definitions.string_global},
    u'Array':
        {'value':
             {u'prototype': {'readonly': is_shared_scope}},
         'return': call_definitions.array_global},
    u'Number':
        {'value':
             {u'prototype':
                  {'readonly': is_shared_scope},
              u'POSITIVE_INFINITY':
                  {'value': lambda t: JSWrapper(float('inf'), traverser=t)},
              u'NEGATIVE_INFINITY':
                  {'value': lambda t: JSWrapper(float('-inf'), traverser=t)}},
         'return': call_definitions.number_global},
    u'Boolean':
        {'value':
             {u'prototype': {'readonly': is_shared_scope}},
         'return': call_definitions.boolean_global},
    u'RegExp': {'value': {u'prototype': {'readonly': is_shared_scope}}},
    u'Date': {'value': {u'prototype': {'readonly': is_shared_scope}}},
    u'File': {'value': {u'prototype': {'readonly': is_shared_scope}}},

    u'Math':
        {'value':
             {u'PI':
                  {'value': lambda t: JSWrapper(math.pi, traverser=t)},
              u'E':
                  {'value': lambda t: JSWrapper(math.e, traverser=t)},
              u'LN2':
                  {'value': lambda t: JSWrapper(math.log(2), traverser=t)},
              u'LN10':
                  {'value': lambda t: JSWrapper(math.log(10), traverser=t)},
              u'LOG2E':
                  {'value': lambda t: JSWrapper(math.log(math.e, 2),
                                                traverser=t)},
              u'LOG10E':
                  {'value': lambda t: JSWrapper(math.log10(math.e),
                                                traverser=t)},
              u'SQRT2':
                  {'value': lambda t: JSWrapper(math.sqrt(2), traverser=t)},
              u'SQRT1_2':
                  {'value': lambda t: JSWrapper(math.sqrt(1/2), traverser=t)},
              u'abs':
                  {'return': python_wrap(abs, [('num', 0)])},
              u'acos':
                  {'return': python_wrap(math.acos, [('num', 0)])},
              u'asin':
                  {'return': python_wrap(math.asin, [('num', 0)])},
              u'atan':
                  {'return': python_wrap(math.atan, [('num', 0)])},
              u'atan2':
                  {'return': python_wrap(math.atan2, [('num', 0),
                                                      ('num', 1)])},
              u'ceil':
                  {'return': python_wrap(math.ceil, [('num', 0)])},
              u'cos':
                  {'return': python_wrap(math.cos, [('num', 0)])},
              u'exp':
                  {'return': python_wrap(math.exp, [('num', 0)])},
              u'floor':
                  {'return': python_wrap(math.floor, [('num', 0)])},
              u'log':
                  {'return': call_definitions.math_log},
              u'max':
                  {'return': python_wrap(max, [('num', 0)], nargs=True)},
              u'min':
                  {'return': python_wrap(min, [('num', 0)], nargs=True)},
              u'pow':
                  {'return': python_wrap(math.pow, [('num', 0),
                                                    ('num', 0)])},
              u'random': # Random always returns 0.5 in our fantasy land.
                  {'return': call_definitions.math_random},
              u'round':
                  {'return': call_definitions.math_round},
              u'sin':
                  {'return': python_wrap(math.sin, [('num', 0)])},
              u'sqrt':
                  {'return': python_wrap(math.sqrt, [('num', 1)])},
              u'tan':
                  {'return': python_wrap(math.tan, [('num', 0)])},
                  }},

    u'navigator':
        {'value': {u'wifi': {'dangerous': True},
                   u'geolocation': {'dangerous': True}}},

    u'Components':
        {'dangerous_on_read':
             lambda t, e: bool(e.metadata.get('is_jetpack')),
         'value':
             {u'classes':
                  {'xpcom_wildcard': True,
                   'value':
                       {u'createInstance':
                           {'return': xpcom_constructor('createInstance')},
                        u'getService':
                           {'return': xpcom_constructor('getService')}}},
              u'interfaces': {'value': INTERFACE_ENTITIES}}},

    # Global properties are inherently read-only, though this formalizes it.
    u'Infinity':
        {'value': lambda t: JSWrapper(float('inf'), traverser=t)},
    u'NaN': {'readonly': True, 'literal': lambda t: float('nan')},
    u'undefined': {'readonly': True, 'literal': lambda t: Undefined},

    u'innerHeight': {'readonly': False},
    u'innerWidth': {'readonly': False},
    u'width': {'readonly': False},
    u'height': {'readonly': False},
    u'top': {'readonly': actions._readonly_top},

    u'content':
        {'value':
             {u'document': CONTENT_DOCUMENT}},
    u'contentWindow':
        {'value':
             lambda t: {'value': GLOBAL_ENTITIES}},
    u'_content': {'value': lambda t: GLOBAL_ENTITIES[u'content']},
    u'gBrowser':
        {'value':
             {u'contentDocument':
                  {'value': CONTENT_DOCUMENT},
              u'contentWindow':
                  {'value':
                       lambda t: {'value': GLOBAL_ENTITIES}},
              u'selectedTab':
                  {'readonly': False}}},
    u'opener':
        {'value':
             lambda t: {'value': GLOBAL_ENTITIES}},
}


def hook_global(path, object_=GLOBAL_ENTITIES, **entity):
    value = object_
    for ident in path:
        dct = value.setdefault(ident, {})
        value = dct.setdefault('value', {})

    for key, value in entity.iteritems():
        if key == 'return_':
            key = 'return'

        if key == 'value':
            exists = dct['value'] != {}
        else:
            exists = key in dct

        assert not exists, ('Global entity already exists at `{0}`: {1!r}'
                            .format('.'.join(path), dct))

        dct[key] = value


def hook_interface(path, **entity):
    hook_global(path, object_=INTERFACES, **entity)


@post_init
def do_post_init():
    for interface in INTERFACES:
        def construct(interface):
            def wrap():
                return INTERFACES[interface]
            return wrap

        entity = INTERFACE_ENTITIES.setdefault(interface, {})
        entity['xpcom_map'] = construct(interface)

    for key, value in SERVICES.items():
        SERVICES[key] = {'value': partial(build_quick_xpcom,
                                          'getService', value)}
