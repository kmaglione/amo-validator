from nose.plugins.skip import SkipTest

from tests.helper import Contains, Exists, Matches, NonEmpty, RegexTestCase
from tests.js_helper import TestCase


class TestGeneric(TestCase):
    def test_nsIProcess(self):
        """Test that uses of nsIProcess are flagged."""

        for script in ('Ci.nsIProcess', 'Components.interfaces.nsIProcess',
                       'Cc[contract].createInstance(Ci.nsIProcess)'):
            self.setup_err()
            self.run_script(script)
            self.assert_warnings({
                'message': Contains('nsIProcess is potentially dangerous'),
                'signing_severity': 'high',
                'signing_help': Matches('alternatives to directly launching '
                                        'executables')})

    def test_proxy_filter(self):
        """Test that uses of proxy filters are flagged."""

        self.run_script("""
            Cc[thing].getService(Ci.nsIProtocolProxyService).registerFilter(
                filter);
        """)
        self.assert_warnings({
            'id': Contains('proxy_filter'),
            'description': Matches('direct arbitrary network traffic'),
            'signing_help': Matches('must undergo manual code review'),
            'signing_severity': 'low'})

'''
def check_import(a, t, e):
    """Check Components.utils.import statements for dangerous modules."""

    traverser = t.im_self
    traverse_node = t
    args = map(traverse_node, a)

    if len(args) > 0:
        module = actions._get_as_str(args[0])
        # Strip any query parameters.
        module = re.sub(r'\?.*', '', module)

        if module in DANGEROUS_MODULES:
            kw = merge_description(
                {'err_id': ('testcases_javascript', 'security', 'jsm_import'),
                 'warning': 'Potentially dangerous JSM imported.'},
                DANGEROUS_MODULES[module])
            traverser.warning(**kw)

add_global_entity((u'Components', u'utils', u'import'),
                  dangerous=check_import)
'''


'''
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


def check_require(a, t, e):
    """
    Tests for unsafe uses of `require()` in SDK add-ons.
    """

    args, traverse, err = a, t, e

    if not err.metadata.get('is_jetpack') and len(args):
        return

    module = traverse(args[0]).get_literal_value()
    if not isinstance(module, basestring):
        return

    if module.startswith('sdk/'):
        module = module[len('sdk/'):]

    if module in LOW_LEVEL_SDK_MODULES:
        err.metadata['requires_chrome'] = True
        return {'warning': 'Use of low-level or non-SDK interface',
                'description': 'Your add-on uses an interface which bypasses '
                               'the high-level protections of the add-on SDK. '
                               'This interface should be avoided, and its use '
                               'may significantly complicate your review '
                               'process.'}

    if module in DEPRECATED_SDK_MODULES:
        return merge_description(
            {'err_id': ('testcases_javascript', 'security', 'sdk_import'),
             'warning': 'Deprecated SDK module imported'},
            DEPRECATED_SDK_MODULES[module])

GLOBAL_ENTITIES.update({
    u'require': {'dangerous': check_require},
})
'''


class TestCertificates(TestCase):
    BASE_MESSAGE = {
        'id': ('javascript', 'predefinedentities', 'cert_db'),
        'description': Matches('Access to the X509 certificate '
                               'database'),
        'signing_help': Matches('avoid interacting with the '
                                'certificate and trust databases'),
        'signing_severity': 'high'}

    def test_cert_db_interfaces(self):
        """Test that use of the certificate DB interfaces raises a signing
        warning."""

        for iface in ('nsIX509CertDB', 'nsIX509CertDB2', 'nsIX509CertList',
                      'nsICertOverrideService'):
            self.setup_err()
            self.run_script('Cc[""].getService(Ci.{0});'.format(iface))
            self.assert_warnings(self.BASE_MESSAGE)

    def test_cert_db_contracts(self):
        """Test that access to the certificate DB contract IDs raises a signing
        warning."""
        for contract in ('@mozilla.org/security/x509certdb;1',
                         '@mozilla.org/security/x509certlist;1',
                         '@mozilla.org/security/certoverride;1'):
            self.setup_err()
            self.run_script('Cc["{0}"]'.format(contract))
            self.assert_warnings(self.BASE_MESSAGE)


class TestCTypes(TestCase):
    BASE_MESSAGE = {
        'id': ('testcases_javascript', 'security', 'ctypes'),
        'description': Matches('ctypes.*can lead to serious, and often '
                               'exploitable, errors'),
        'signing_help': Matches('avoid.*native binaries'),
        'signing_severity': 'high'}

    def test_ctypes_usage(self):
        """Test that use of the ctypes global triggers a signing warning."""

        self.run_script('ctypes.open("foo.so")')
        self.assert_warnings(self.BASE_MESSAGE)

    def test_ctypes_module(self):
        """Test that references to ctypes.jsm trigger a signing warning."""

        scripts = (
            'Cu.import("resource://gre/modules/ctypes.jsm?foo");',
            'Components.utils.import("resource:///modules/ctypes.jsm");',
        )

        for script in scripts:
            self.setup_err()
            self.run_script(script)
            self.assert_warnings(self.BASE_MESSAGE)


class TestPreferences(TestCase):
    """Tests that security-related preferences are flagged correctly."""

    def test_security_prefs(self):
        """Test that preference branches flagged as security issues."""

        branches = ('app.update.',
                    'browser.addon-watch.',
                    'datareporting.',
                    'extensions.blocklist.',
                    'extensions.getAddons.',
                    'extensions.update.',
                    'security.')

        for branch in branches:
            self.setup_err()

            # Check that instances not at the start of the string aren't
            # flagged.
            self.run_script('foo("thing, stuff, bleh.{0}")'.format(branch))
            self.assert_silent()

            self.run_script('foo("{0}thing")'.format(branch))
            self.assert_warnings({
                'description': Matches('severe security implications'),
                'signing_help': Matches('by exception only'),
                'signing_severity': 'high'})

    def test_other_prefs(self):
        """Test that less security-sensitive preferences are flagged."""

        for branch in ('capability.policy.',
                       'extensions.checkCompatibility'):
            self.setup_err()
            self.run_script('foo("{0}bar")'.format(branch))
            self.assert_warnings({
                'message': Matches('unsafe preference branch')})


'''

BANNED_PREF_REGEXPS.extend([
    r'extensions\..*\.update\.(url|enabled|interval)',
])

'''

'''


# Marionette.

MARIONETTE_MESSAGE = {
    'warning': 'Marionette should not be accessed by extensions',
    'description': 'References to the Marionette service are not acceptable '
                   'in extensions. Please remove them.',
}

GLOBAL_ENTITIES.update({
    u'MarionetteComponent': {'dangerous_on_read': MARIONETTE_MESSAGE},
    u'MarionetteServer': {'dangerous_on_read': MARIONETTE_MESSAGE},
})

BANNED_PREF_BRANCHES.extend([
    (u'marionette.force-local', MARIONETTE_MESSAGE),
    (u'marionette.defaultPrefs.enabled', MARIONETTE_MESSAGE),
    (u'marionette.defaultPrefs.port', MARIONETTE_MESSAGE),
])

STRING_REGEXPS.extend([
    # References to the Marionette service.
    (('@mozilla.org/marionette;1',
      '{786a1369-dca5-4adc-8486-33d23c88010a}'), MARIONETTE_MESSAGE),
])

'''


'''


# Windows Registry.

REGISTRY_WRITE = {'dangerous': {
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
    'editors_only': True}}


def registry_key(write=False):
    """Represents a function which returns a registry key object."""
    res = {'return': lambda wrapper, arguments, traverser: (
        build_quick_xpcom('createInstance', 'nsIWindowMediator',
                          traverser, wrapper=True))}
    if write:
        res.update(REGISTRY_WRITE)

    return res

INTERFACES.update({
    'nsIWindowsRegKey': {'value': {u'create': REGISTRY_WRITE,
                                   u'createChild': registry_key(write=True),
                                   u'openChild': registry_key(),
                                   u'writeBinaryValue': REGISTRY_WRITE,
                                   u'writeInt64Value': REGISTRY_WRITE,
                                   u'writeIntValue': REGISTRY_WRITE,
                                   u'writeStringValue': REGISTRY_WRITE}},
})

INTERFACE_ENTITIES.update({
    u'nsIWindowsRegKey': {
        'dangerous': {
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
                           'and should be reviewed with special care.'}},
})
'''


'''

# Add-on Manager.

ADDON_INSTALL_METHOD = {
    'value': {},
    'dangerous': {
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
        'signing_severity': 'high'},
}

GLOBAL_ENTITIES.update({
    u'AddonManager': {
        'readonly': False,
        'value': {
            u'autoUpdateDefault': {'readonly': SECURITY_PREF_MESSAGE},
            u'checkUpdateSecurity': {'readonly': SECURITY_PREF_MESSAGE},
            u'checkUpdateSecurityDefault': {'readonly': SECURITY_PREF_MESSAGE},
            u'updateEnabled': {'readonly': SECURITY_PREF_MESSAGE},
            u'getInstallForFile': ADDON_INSTALL_METHOD,
            u'getInstallForURL': ADDON_INSTALL_METHOD,
            u'installAddonsFromWebpage': ADDON_INSTALL_METHOD}},
})
'''
