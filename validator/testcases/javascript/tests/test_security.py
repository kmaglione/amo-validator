from __future__ import absolute_import, print_function, unicode_literals

import pytest

from tests.helper import Contains, Matches
from tests.js_helper import TestCase


parametrize = pytest.mark.parametrize


class TestGeneric(TestCase):

    @parametrize('script', ('Ci.nsIProcess',
                            'Components.interfaces.nsIProcess',
                            'Cc[contract].createInstance(Ci.nsIProcess)'))
    def test_nsIProcess(self, script):
        """Test that uses of nsIProcess are flagged."""

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
            'id': Contains('nsIProtocolProxyService.registerFilter'),
            'description': Matches('direct arbitrary network traffic'),
            'signing_help': Matches('must undergo manual code review'),
            'signing_severity': 'low'})


class TestCertificates(TestCase):

    BASE_MESSAGE = {
        'id': ('javascript', 'predefinedentities', 'cert_db'),
        'description': Matches('Access to the X509 certificate '
                               'database'),
        'signing_help': Matches('avoid interacting with the '
                                'certificate and trust databases'),
        'signing_severity': 'high'}

    @parametrize('interface', ('nsIX509CertDB', 'nsIX509CertDB2',
                               'nsIX509CertList', 'nsICertOverrideService'))
    def test_cert_db_interfaces(self, interface):
        """Test that use of the certificate DB interfaces raises a signing
        warning."""

        self.run_script('Cc[""].getService(Ci.{0});'.format(interface))
        self.assert_warnings(self.BASE_MESSAGE)

    @parametrize('contract', ('@mozilla.org/security/x509certdb;1',
                              '@mozilla.org/security/x509certlist;1',
                              '@mozilla.org/security/certoverride;1'))
    def test_cert_db_contracts(self, contract):
        """Test that access to the certificate DB contract IDs raises a signing
        warning."""

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

    @parametrize('script', (
        'Cu.import("resource://gre/modules/ctypes.jsm?foo");',
        'Components.utils.import("resource:///modules/ctypes.jsm");',
    ))
    def test_ctypes_module(self, script):
        """Test that references to ctypes.jsm trigger a signing warning."""

        self.run_script(script)
        self.assert_warnings(self.BASE_MESSAGE)


class TestPreferences(TestCase):
    """Tests that security-related preferences are flagged correctly."""

    @parametrize('branch', ('app.update.',
                            'browser.addon-watch.',
                            'datareporting.',
                            'extensions.blocklist.',
                            'extensions.getAddons.',
                            'extensions.update.',
                            'security.'))
    def test_security_prefs(self, branch):
        """Test that preference branches flagged as security issues."""

        # Check that instances not at the start of the string aren't
        # flagged.
        self.run_script('foo("thing, stuff, bleh.{0}")'.format(branch))
        self.assert_silent()

        self.run_script('foo("{0}thing")'.format(branch))
        self.assert_warnings({
            'description': Matches('severe security implications'),
            'signing_help': Matches('by exception only'),
            'signing_severity': 'high'})

    @parametrize('branch', ('capability.policy.',
                            'extensions.checkCompatibility'))
    def test_other_prefs(self, branch):
        """Test that less security-sensitive preferences are flagged."""

        self.run_script('foo("{0}bar")'.format(branch))
        self.assert_warnings({
            'message': Matches('unsafe preference branch')})
