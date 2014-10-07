from helper import CompatTestCase
from validator.compat import FX33_DEFINITION


class TestFX33Compat(CompatTestCase):
    """Test that compatibility tests for Gecko 33 are properly executed."""

    VERSION = FX33_DEFINITION

    def test_setTabValue_string(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var currentTab = gBrowser.selectedTab;
            var dataToAttach = "I want to attach this";
            ss.setTabValue(currentTab, "key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_silent()

    def test_setWindowValue_string(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var currentTab = gBrowser.selectedTab;
            var dataToAttach = "I want to attach this";
            ss.setWindowValue(currentTab, "key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_silent()

    def test_setGlobalValue_string(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var dataToAttach = "I want to attach this";
            ss.setGlobalValue("key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_silent()

    def test_setTabValue_int(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var currentTab = gBrowser.selectedTab;
            var dataToAttach = 750;
            ss.setTabValue(currentTab, "key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_error()

    def test_setWindowValue_int(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var currentTab = gBrowser.selectedTab;
            var dataToAttach = 750;
            ss.setWindowValue(currentTab, "key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_error()

    def test_setGlobalValue_int(self):
        self.run_script_for_compat("""
            var ss = Components.classes["@mozilla.org/browser/sessionstore;1"]
                               .getService(Components.interfaces.nsISessionStore);
            var dataToAttach = 750;
            ss.setGlobalValue("key-name-here", dataToAttach);
        """)
        self.assert_silent()
        self.assert_compat_error()