"""
Various tests related to validation for automated signing.
"""

import pytest

from .helper import RegexTestCase
from .js_helper import TestCase

from validator.errorbundler import maybe_tuple
from validator.testcases.javascript.preferences import PREFERENCE_ERROR_ID


parametrize = pytest.mark.parametrize


class TestSearchService(TestCase):
    """Tests that warnings related to the search service trigger warnings."""

    WARNING = {'id': ('testcases_javascript_actions', 'search_service',
                      'changes')}

    @pytest.fixture(params=('Cc[""].getService(Ci.nsIBrowserSearchService)',
                            'Services.search'))
    def search_service(self, request):
        return request.param

    @parametrize('method', ('addEngine', 'addEngineWithDetails',
                            'removeEngine', 'moveEngine'))
    def test_method(self, search_service, method):
        """Tests that setting changes trigger warnings."""

        warning = dict(self.WARNING, signing_severity='medium')

        self.run_script("""{object}.{method}(foo, bar, baz);"""
                        .format(object=search_service, method=method))

        self.assert_warnings(warning)

    @parametrize('prop', ('currentEngine', 'defaultEngine'))
    def test_property(self, search_service, prop):
        """Tests that setting changes trigger warnings."""

        warning = dict(self.WARNING, signing_severity='high')

        self.run_script("""{object}.{prop} = foo;"""
                        .format(object=search_service, prop=prop))

        self.assert_warnings(warning)


class TestOtherStuff(TestCase):
    @parametrize('method', ('create', 'createChild', 'writeBinaryValue',
                            'writeInt64Value', 'writeIntValue',
                            'writeStringValue'))
    def test_registry_write(self, method):
        """Tests that Windows registry writes trigger warnings."""

        warnings = ({'id': ('testcases_javascript_actions', 'windows_registry',
                            'write'),
                     'signing_severity': 'medium'},)

        self.run_script("""
            Cc[""].createInstance(Ci.nsIWindowsRegKey).%s(foo, bar);
        """ % method)

        self.assert_failed(with_warnings=warnings)

    def test_evalInSandbox(self):
        """Tests that evalInSandbox causes signing warnings."""

        self.run_script("""
            Cu.evalInSandbox("foobar()", sandbox);
        """)
        self.assert_failed(with_warnings=[{'signing_severity': 'low'}])


class TestPrefs(TestCase):
    @parametrize('pref,severity',
                 (('browser.newtab.url', 'high'),
                  ('browser.newtabpage.enabled', 'high'),
                  ('browser.search.defaultenginename', 'high'),
                  ('browser.startup.homepage', 'high'),
                  ('keyword.URL', 'high'),
                  ('keyword.enabled', 'high'),

                  ('app.update.*', 'high'),
                  ('browser.addon-watch.*', 'high'),
                  ('datareporting.', 'high'),
                  ('extensions.blocklist.*', 'high'),
                  ('extensions.getAddons.*', 'high'),
                  ('extensions.update.*', 'high'),

                  ('security.*', 'high'),

                  ('network.proxy.*', 'low'),
                  ('network.http.*', 'low'),
                  ('network.websocket.*', 'low')))
    def test_pref_branches(self, pref, severity):
        """Test that writes to potentially dangerous preferences are
        flagged."""
        warnings = [
            {'message': 'Attempt to set a dangerous preference',
             'signing_severity': severity}]

        self.run_script("""
            Services.prefs.setCharPref('%s', '42');
        """ % pref)
        self.assert_failed(with_warnings=warnings)

    @parametrize('script', (
        """Services.prefs.getBranch("browser.star")
                   .setCharPref("tup.homepage", "http://evil.com");""",

        """let set = Services.prefs.getBranch("browser.star").setCharPref;
           set("tup.homepage", "http://evil.com");""",
    ))
    def test_pref_composed_branches(self, script):
        """
        Tests that preference warnings still happen when branches are composed
        via `getBranch`.
        """

        self.run_script(script)
        self.assert_warnings({
            'message': 'Attempt to set a dangerous preference',
            'signing_severity': 'high'
        })

    CALL_WARNING = {'id': ('testcases_javascript_actions',
                           '_call_expression', 'called_set_preference')}

    LITERAL_WARNING = {'id': PREFERENCE_ERROR_ID}

    SUMMARY = {'trivial': 0,
               'low': 0,
               'medium': 0,
               'high': 1}

    @pytest.fixture(params=('Services.prefs.setCharPref', 'Preferences.set'))
    def set_pref(self, request):
        return request.param

    @pytest.fixture(params=('Services.prefs.getCharPref', 'Preferences.get'))
    def get_pref(self, request):
        return request.param

    def test_bare_string_literals(self):
        """Test that flagged preferences are reported when used in bare
        strings not passed to preferences functions."""

        self.run_script('frob("browser.startup.homepage");')

        self.assert_warnings(self.LITERAL_WARNING, exhaustive=True)
        assert self.err.signing_summary == self.SUMMARY

    def test_pref_literals_reported_once(self, set_pref):
        """Test that warnings for preference literals are reported only
        once when a literal is passed directly to a pref setting method."""

        self.run_script('{set_pref}("browser.startup.homepage", "");'
                        .format(set_pref=set_pref))

        self.assert_warnings(self.CALL_WARNING, exhaustive=True)
        assert self.err.signing_summary == self.SUMMARY

    def test_pref_literals_reported_twice(self, set_pref):
        """Test that warnings for preference literals are reported only
        both for the literal and for the function call when first stored
        to a variable and then passed to a pref setting method."""

        self.run_script('let bsh = "browser.startup.homepage";'
                        '{set_pref}(bsh, "");'
                        .format(set_pref=set_pref))

        summary = dict(self.SUMMARY, high=2)

        self.assert_warnings(self.LITERAL_WARNING, self.CALL_WARNING,
                             exhaustive=True)

        assert self.err.signing_summary == summary

    def test_get_preference_calls_ignored(self, get_pref):
        """Tests that string literals provably used only to read, but not
        write, preferences do not cause warnings."""

        # Literal passed directly pref get call.
        self.run_script('let thing = {get_pref}("browser.startup.homepage");'
                        .format(get_pref=get_pref))

        self.assert_silent()

    def test_get_preference_calls_not_ignored(self, get_pref):
        """Tests that string literals not *provably* used only to read, but not
        write, preferences *do* cause warnings."""

        self.run_script('let bsh = "browser.sta" + "rtup.homepage";'
                        'let thing = {get_pref}(bsh);'
                        .format(get_pref=get_pref))

        self.assert_warnings(self.LITERAL_WARNING, exhaustive=True)

    def test_pref_help_added_to_bare_strings(self):
        """Test that a help messages about passing literals directly to
        APIs is added only to bare strings."""

        self.run_script("""
            'browser.startup.homepage';
            Preferences.set('browser.startup.homepage');
        """)

        warnings = self.err.warnings
        self.assert_warnings({'id': PREFERENCE_ERROR_ID},
                             {'id': ('testcases_javascript_actions',
                                     '_call_expression',
                                     'called_set_preference')},
                             exhaustive=True)

        # Check that descriptions and help are the same, except for
        # an added message in the bare string.
        for key in 'description', 'signing_help':
            val1 = maybe_tuple(warnings[0][key])
            val2 = maybe_tuple(warnings[1][key])

            assert val2 == val1[:len(val2)]

            # And that the added message is what we expect.
            assert 'Preferences.get' in val1[-1]


class TestMoreOtherStuff(TestCase, RegexTestCase):
    @parametrize('path', (r'addons.json',
                          r'addons" + ".json',
                          r'safebrowsing',
                          r'safebrowsing\\foo.bar',
                          r'safebrowsing/foo.bar'))
    @parametrize('script', ('"{path}"', '"/{path}"', '"\\{path}"'))
    def test_profile_filenames(self, path, script):
        """
        Test that references to critical files in the user profile cause
        warnings.
        """

        self.run_script(script.format(path=path))
        self.assert_warnings(
            {'id': ('testcases_regex', 'string', 'profile_filenames'),
             'message': 'Reference to critical user profile data',
             'signing_severity': 'low'})

    def test_categories(self):
        """Tests that dangerous category names are flagged in JS strings."""

        warning = {'id': ('testcases_chromemanifest', 'test_resourcemodules',
                          'resource_modules'),
                   'message': 'Potentially dangerous category entry',
                   'signing_severity': 'medium',
                   'editors_only': True}

        self.run_script("'JavaScript-global-property'")
        self.assert_failed(with_warnings=[warning])

    def test_proxy_filter(self):
        """Tests that registering a proxy filter generates a warning."""

        warning = {'id': ('jstypes', 'hook_on_call',
                          'nsIProtocolProxyService.registerFilter'),
                   'signing_severity': 'low'}

        self.run_script("""
            Cc[""].getService(Ci.nsIProtocolProxyService)
                 .registerFilter(foo, 0);
        """)
        self.assert_failed(with_warnings=[warning])

    @parametrize('method', ('getInstallForFile', 'getInstallForURL'))
    def test_addon_install(self, method):
        """Tests attempts to install an add-on are flagged."""

        self.run_script("""
            AddonManager.{method}(loc, callback, plus, some, other, stuff);
        """.format(method=method))

        self.assert_warnings({'id': ('jstypes', 'hook_on_call',
                                     'AddonManager.%s' % method),
                              'editors_only': True,
                              'signing_severity': 'high'})

    @parametrize('prop', (u'autoUpdateDefault',
                          u'checkUpdateSecurity',
                          u'checkUpdateSecurityDefault',
                          u'updateEnabled'))
    def test_addon_settings(self, prop):
        """Tests that attempts to change add-on settings via the
        AddonManager API are flagged."""

        warning = {
            'description':
                'Changing this preference may have severe security '
                'implications, and is forbidden under most circumstances.',
            'editors_only': True,
            'signing_severity': 'high'}

        self.run_script('AddonManager.{prop} = false;'.format(prop=prop))
        self.assert_warnings(warning)

    @parametrize('script', (
        "ctypes.open('libc.so.6');",
        "Cu.import('resource://gre/modules/ctypes.jsm?foo');",
        "Components.utils.import('resource:///modules/ctypes.jsm');",
    ))
    def test_ctypes(self, script):
        """Tests that usage of `ctypes` generates warnings."""

        self.run_script(script)
        self.assert_failed(with_warnings=[
            {'id': ('testcases_javascript', 'security', 'ctypes'),
             'editors_only': True,
             'signing_severity': 'high'}])

    def test_nsIProcess(self):
        """Tests that usage of `nsIProcess` generates warnings."""

        self.run_script("""
            Cc[""].createInstance(Ci.nsIProcess);
        """)
        self.assert_failed(with_warnings=[
            {'id': ('jstypes', 'hook_on_get', 'nsIProcess'),
             'editors_only': True,
             'signing_severity': 'high'}])

    @parametrize('func', ('eval',
                          'Function',
                          'setTimeout',
                          'setInterval'))
    def test_eval(self, func):
        """Tests that usage of eval-related functions generates warnings."""

        warning = {'id': ('javascript', 'dangerous_global', 'eval'),
                   'signing_severity': 'high'}

        self.run_script('{func}("doEvilStuff()")'.format(func=func))
        self.assert_warnings(warning)

    CERT_WARNING = {'id': ('javascript', 'predefinedentities', 'cert_db'),
                    'editors_only': True,
                    'signing_severity': 'high'}

    @parametrize('contract', ('@mozilla.org/security/x509certdb;1',
                              '@mozilla.org/security/x509certlist;1',
                              '@mozilla.org/security/certoverride;1'))
    def test_cert_service_contract(self, contract):
        """Tests that changes to certificate trust leads to warnings."""

        self.run_script('Cc["{contract}"].getService()'
                        .format(contract=contract))

        self.assert_warnings(self.CERT_WARNING)

    @parametrize('interface', ('nsIX509CertDB',
                               'nsIX509CertDB2',
                               'nsIX509CertList',
                               'nsICertOverrideService'))
    def test_cert_service_interface(self, interface):
        """Tests that changes to certificate trust leads to warnings."""

        self.run_script('Cc[""].getService(Ci.{interface})'
                        .format(interface=interface))

        self.assert_warnings(self.CERT_WARNING)

    @parametrize('script', (
        "if (foo == 'about:newtab') doStuff();",
        'if (bar === "about:blank") doStuff();',
        "if (baz==='about:newtab') doStuff();",
        "if ('about:newtab' == thing) doStuff();",
        '/^about:newtab$/.test(thing)',
        '/about:newtab/.test(thing)',
        "'@mozilla.org/network/protocol/about;1?what=newtab'",
    ))
    def test_new_tab_page(self, script):
        """Tests that attempts to replace about:newtab are flagged."""

        self.run_js_regex(script)
        self.assert_warnings({'signing_severity': 'low'})

    def test_script_creation(self):
        """Tests that creation of script tags generates warnings."""

        warning = {'id': ('testcases_javascript_instanceactions',
                          '_call_expression', 'called_createelement'),
                   'signing_severity': 'medium'}

        self.run_script("""
            doc.createElement("script");
        """)
        self.assert_failed(with_warnings=[warning])

    def test_event_attributes(self):
        """Tests that creation of event handler attributes is flagged."""

        warning = {'id': ('testcases_javascript_instanceactions',
                          'setAttribute', 'setting_on*'),
                   'signing_severity': 'medium'}

        self.run_script("""
            elem.setAttribute("onhover", "doStuff();" + with_stuff);
        """)
        self.assert_failed(with_warnings=[warning])

    def test_event_attributes_innerhtml(self):
        """Tests that creation of event handler attributes via innerHTML
        assignment is flagged."""

        warning = {'id': ('testcases_javascript_instancetypes',
                          'set_innerHTML', 'event_assignment'),
                   'signing_severity': 'medium'}

        self.run_script("""
            elem.innerHTML = '<a onhover="doEvilStuff()"></a>';
        """)
        self.assert_failed(with_warnings=[warning])

    def test_contentScript_dynamic_values(self):
        """Tests that dynamic values passed as contentScript properties
        trigger signing warnings."""

        warning = {'id': ('testcases_javascript_instanceproperties',
                          'contentScript', 'set_non_literal'),
                   'signing_severity': 'high'}

        self.run_script("""
            tab.attach({ contentScript: evil })
        """)
        self.assert_failed(with_warnings=[warning])

    def test_contentScript_static_values(self):
        """Tests that static, verifiable values passed as contentScripts
        trigger no warnings, but unsafe static values do."""

        # Test safe value.
        self.run_script("""
            tab.attach({ contentScript: "everythingIsCool()" })
        """)
        self.assert_silent()

        # Test unsafe value.

        self.setup_err()
        self.run_script("""
            tab.attach({ contentScript: 'doc.createElement("script")' });
        """)
        self.assert_warnings({
            'id': ('testcases_javascript_instanceactions',
                   '_call_expression', 'called_createelement'),
            'signing_severity': 'medium',
        })
