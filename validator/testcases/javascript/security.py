"""Tests which relate to the overall security of the browser."""
from __future__ import absolute_import, print_function, unicode_literals

import re

from validator.errorbundler import merge_description
from ..regex.javascript import STRING_REGEXPS
from .bootstrapped import if_jetpack
from .jstypes import Global, Hook, Interfaces
from .preferences import BANNED_PREF_BRANCHES, BANNED_PREF_REGEXPS
from .xpcom import CONTRACT_ENTITIES


Interfaces.hook('nsIProcess', on_get={
    'warning':
        'The use of nsIProcess is potentially dangerous and requires '
        'careful review by an administrative reviewer.',
    'editors_only': True,
    'signing_help': 'Consider alternatives to directly launching '
                    'executables, such as loading a URL with an '
                    'appropriate external protocol handler, making '
                    'network requests to a local service, or using '
                    'the (as a last resort) `nsIFile.launch()` method '
                    'to open a file with the appropriate application.',
    'signing_severity': 'high'})

Global.hook(('**', 'launch'), on_call={
    'description': 'Use of the `nsIFile.launch()` method can be dangerous, '
                   'and requires careful review.',
    'editors_only': True})


@Interfaces.hook
class nsIProtocolProxyService(Hook):

    @Hook.on_call
    def registerFilter(this, args, callee):
        return {
            'description': (
                'Proxy filters can be used to direct arbitrary network '
                'traffic through remote servers, and may potentially '
                'be abused.',
                'Additionally, to prevent conflicts, the `applyFilter` '
                'method should always return its third argument in cases '
                'when it is not supplying a specific proxy.'),
            'signing_help':
                'Due to the potential for unintended effects, '
                'any add-on which uses this API must undergo '
                'manual code review for at least one submission.',
            'signing_severity': 'low',
        }


@Global.hook(('document', 'loadOverlay'), 'on_call')
def loadOverlay(this, args, callee):
    return not args[0].as_str().lower().startswith(('chrome:', 'resource:'))


Interfaces.hook('nsIDOMGeoGeolocation',
                on_get='Use of the geolocation API by add-ons requires '
                       'prompting users for consent.')


# Modules.

@Global.hook(('Components', 'utils', 'import'), 'return')
def check_import(this, args, callee):
    """Check Components.utils.import statements for dangerous modules."""

    if len(args) > 0:
        module = args[0].as_str()
        # Strip any query parameters.
        module = re.sub(r'\?.*', '', module)

        if module in DANGEROUS_MODULES:
            kw = merge_description(
                {'err_id': ('testcases_javascript', 'security', 'jsm_import'),
                 'warning': 'Potentially dangerous JSM imported.'},
                DANGEROUS_MODULES[module])
            this.traverser.warning(**kw)


DANGEROUS_MODULES = {}

DEPRECATED_SDK_MODULES = {
    'widget': {'warning': 'Use of deprecated SDK module',
               'description':
                   "The 'widget' module has been deprecated due to a number "
                   'of performance and usability issues, and has been '
                   'removed from the SDK as of Firefox 40. Please use the '
                   "'sdk/ui/button/action' or 'sdk/ui/button/toggle' module "
                   'instead. See '
                   'https://developer.mozilla.org/Add-ons/SDK/High-Level_APIs'
                   '/ui for more information.'},
}

LOW_LEVEL_SDK_MODULES = {
    'chrome',
    'deprecated/window-utils',
    'observer-service',
    'system/events',
    'tab/utils',
    'window-utils',
    'window/utils',
}


@Global.extend
class JetpackModule(Hook):

    @Hook.on_call(scope_filter=if_jetpack)
    def require(this, args, callee):
        """Test for unsafe uses of `require()` in SDK add-ons."""

        module = args[0].as_primitive()
        if not isinstance(module, basestring):
            return

        if module.startswith('sdk/'):
            module = module[len('sdk/'):]

        if module in LOW_LEVEL_SDK_MODULES:
            this.traverser.err.metadata['requires_chrome'] = True
            return {'warning': 'Use of low-level or non-SDK interface',
                    'description':
                        'Your add-on uses an interface which bypasses '
                        'the high-level protections of the add-on SDK. '
                        'This interface should be avoided, and its use '
                        'may significantly complicate your review '
                        'process.'}

        if module in DEPRECATED_SDK_MODULES:
            return merge_description(
                {'err_id': ('testcases_javascript', 'security', 'sdk_import'),
                 'warning': 'Deprecated SDK module imported'},
                DEPRECATED_SDK_MODULES[module])


# Certificates.

DANGEROUS_CERT_DB = {
    'err_id': ('javascript', 'predefinedentities', 'cert_db'),
    'description': 'Access to the X509 certificate '
                   'database is potentially dangerous '
                   'and requires careful review by an '
                   'administrative reviewer.',
    'editors_only': True,
    'signing_help': 'Please avoid interacting with the certificate and trust '
                    'databases if at all possible. Any add-ons which interact '
                    'with these databases must undergo manual code review '
                    'prior to signing.',
    'signing_severity': 'high',
}

for interface in ('nsIX509CertDB', 'nsIX509CertDB2', 'nsIX509CertList',
                  'nsICertOverrideService'):
    Interfaces.hook(interface, on_get=DANGEROUS_CERT_DB)

CONTRACT_ENTITIES.update({
    contract: DANGEROUS_CERT_DB
    for contract in ('@mozilla.org/security/x509certdb;1',
                     '@mozilla.org/security/x509certlist;1',
                     '@mozilla.org/security/certoverride;1')})

# JS ctypes.

CTYPES_DANGEROUS = {
    'err_id': ('testcases_javascript', 'security', 'ctypes'),
    'description': (
        'Insufficiently meticulous use of ctypes can lead to serious, '
        'and often exploitable, errors. The use of bundled binary code, '
        'or access to system libraries, may allow for add-ons to '
        'perform unsafe operations. All ctypes use must be carefully '
        'reviewed by a qualified reviewer.'),
    'editors_only': True,
    'signing_help': ('Please try to avoid interacting with or bundling '
                     'native binaries whenever possible. If you are '
                     'bundling binaries for performance reasons, please '
                     'consider alternatives such as Emscripten '
                     '(http://mzl.la/1KrSUh2), JavaScript typed arrays '
                     '(http://mzl.la/1Iw02sr), and Worker threads '
                     '(http://mzl.la/1OGfAcc).',
                     'Any code which makes use of the `ctypes` API '
                     'must undergo manual code review for at least one '
                     'submission.'),
    'signing_severity': 'high'}

Global.hook('ctypes', on_get=CTYPES_DANGEROUS)

DANGEROUS_MODULES.update({
    'resource://gre/modules/ctypes.jsm': CTYPES_DANGEROUS,
    'resource:///modules/ctypes.jsm': CTYPES_DANGEROUS,
})


# Preferences.

SECURITY_PREF_MESSAGE = {
    'description':
        'Changing this preference may have severe security implications, and '
        'is forbidden under most circumstances.',
    'editors_only': True,
    'signing_help': ('Extensions which alter these settings are allowed '
                     'within the Firefox add-on ecosystem by exception '
                     'only, and under extremely limited circumstances.',
                     'Please remove any reference to these preference names '
                     'from your add-on.'),
    'signing_severity': 'high',
}

BANNED_PREF_BRANCHES.extend([
    # Security and update preferences
    ('app.update.', SECURITY_PREF_MESSAGE),
    ('browser.addon-watch.', SECURITY_PREF_MESSAGE),
    ('capability.policy.', None),
    ('datareporting.', SECURITY_PREF_MESSAGE),

    ('extensions.blocklist.', SECURITY_PREF_MESSAGE),
    ('extensions.checkCompatibility', None),
    ('extensions.getAddons.', SECURITY_PREF_MESSAGE),
    ('extensions.update.', SECURITY_PREF_MESSAGE),

    # Let's see if we can get away with this...
    # Changing any preference in this branch should result in a
    # warning. However, this substring may turn out to be too
    # generic, and lead to spurious warnings, in which case we'll
    # have to single out sub-branches.
    ('security.', SECURITY_PREF_MESSAGE),
])

BANNED_PREF_REGEXPS.extend([
    r'extensions\..*\.update\.(url|enabled|interval)',
])


# Marionette.

MARIONETTE_MESSAGE = {
    'warning': 'Marionette should not be accessed by extensions',
    'description': 'References to the Marionette service are not acceptable '
                   'in extensions. Please remove them.',
}

Global.hook('MarionetteComponent', on_get=MARIONETTE_MESSAGE)
Global.hook('MarionetteServer', on_get=MARIONETTE_MESSAGE)

BANNED_PREF_BRANCHES.extend([
    ('marionette.force-local', MARIONETTE_MESSAGE),
    ('marionette.defaultPrefs.enabled', MARIONETTE_MESSAGE),
    ('marionette.defaultPrefs.port', MARIONETTE_MESSAGE),
])

STRING_REGEXPS.extend([
    # References to the Marionette service.
    (('@mozilla.org/marionette;1',
      '{786a1369-dca5-4adc-8486-33d23c88010a}'), MARIONETTE_MESSAGE),
])


# Windows Registry.

REGISTRY_WRITE = {
    'err_id': ('testcases_javascript_actions',
               'windows_registry',
               'write'),
    'warning': 'Writes to the registry may be dangerous',
    'description': 'Writing to the registry can have many system-level '
                   'consequences and requires careful review.',
    'signing_help': (
        'Please store any settings relevant to your add-on within the '
        'current Firefox profile, ideally using the preferences service.'
        'If you are intentionally changing system settings, consider '
        'searching for a Firefox API which has a similar effect. If no such '
        'API exists, we strongly discourage making any changes which affect '
        'the system outside of the browser.'),
    'signing_severity': 'medium',
    'editors_only': True,
}


@Interfaces.hook
class nsIWindowsRegKey(Hook):
    class Meta:
        on_get = {
            'signing_help':
                'The information stored in many standard registry '
                'keys is available via built-in Firefox APIs, '
                'such as `Services.sysinfo`, `Services.dirsvc`, '
                'and the environment service '
                '(http://mzl.la/1OGgCF3). We strongly discourage '
                'extensions from reading registry information '
                'which is not available via other Firefox APIs.',
            'signing_severity': 'low',
            'editors_only': True,
            'description': 'Access to the registry is potentially dangerous, '
                           'and should be reviewed with special care.'}

    create = {'on_get': REGISTRY_WRITE}
    writeBinaryValue = {'on_get': REGISTRY_WRITE}
    writeInt64Value = {'on_get': REGISTRY_WRITE}
    writeIntValue = {'on_get': REGISTRY_WRITE}
    writeStringValue = {'on_get': REGISTRY_WRITE}

    @Hook.return_(on_get=REGISTRY_WRITE)
    def createChild(this, args, callee):
        return this.traverser.wrap().query_interface('nsIWindowsRegKey')

    def openChild(this, args, callee):
        return this.traverser.wrap().query_interface('nsIWindowsRegKey')


# Add-on Manager.

ADDON_INSTALL_METHOD = {
    'description': (
        'Add-ons may install other add-ons only by user consent. Any '
        'such installations must be carefully reviewed to ensure '
        'their safety.'),
    'editors_only': True,
    'signing_help': (
        'Rather than directly install other add-ons, you should offer '
        'users the opportunity to install them via the normal web install '
        'process, using an install link or button connected to the '
        '`InstallTrigger` API: '
        'https://developer.mozilla.org/en-US/docs/Web/API/InstallTrigger',
        'Updates to existing add-ons should be provided via the '
        'install.rdf `updateURL` mechanism.'),
    'signing_severity': 'high',
}


@Global.hook
class AddonManager(Hook):

    autoUpdateDefault = {'on_set': SECURITY_PREF_MESSAGE}
    checkUpdateSecurity = {'on_set': SECURITY_PREF_MESSAGE}
    checkUpdateSecurityDefault = {'on_set': SECURITY_PREF_MESSAGE}
    updateEnabled = {'on_set': SECURITY_PREF_MESSAGE}

    getInstallForFile = {'on_call': ADDON_INSTALL_METHOD}
    getInstallForURL = {'on_call': ADDON_INSTALL_METHOD}
    installAddonsFromWebpage = {'on_call': ADDON_INSTALL_METHOD}
