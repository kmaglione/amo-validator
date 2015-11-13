import pytest

from js_helper import _do_test_raw, TestCase


parametrize = pytest.mark.parametrize


def test_xmlhttprequest():
    """Tests that the XPCOM XHR yields the standard XHR."""

    err = _do_test_raw("""
    // Accessing a member on Components.classes is a wildcard
    var class_ = Components.interfaces.nsIXMLHttpRequest;
    var req = Components.classes["foo.bar"]
                        .createInstance(class_);
    """)

    wrapper = err.final_context.get('req')

    assert 'open' in wrapper.value.hooks['properties']


def test_nsiaccessibleretrieval():
    """Flag any uses of nsIAccessibleRetrieval."""

    err = _do_test_raw("""
    var c = Components.classes[""].createInstance(
        Components.interfaces.nsIAccessibleRetrievalWhatever);
    """)
    assert len(err.warnings) == 0

    err = _do_test_raw("""
    var c = Components.classes[""].createInstance(
        Components.interfaces.nsIAccessibleRetrieval);
    """)
    assert len(err.warnings) == 1


def test_evalinsandbox():
    """Tests that Components.utils.evalInSandbox() is treated like eval."""

    err = _do_test_raw("""
    var Cu = Components.utils;
    Cu.foo("bar");
    """)
    assert not err.failed()

    err = _do_test_raw("""
    var Cu = Components.utils;
    Cu.evalInSandbox("foo");
    """)
    assert err.failed()

    err = _do_test_raw("""
    const Cu = Components.utils;
    Cu.evalInSandbox("foo");
    """)
    assert err.failed()


def test_getinterface():
    """Test the functionality of the getInterface method."""

    assert _do_test_raw("""
        obj.getInterface(Components.interfaces.nsIXMLHttpRequest)
           .open("GET", "foo", false);
    """).failed()


def test_queryinterface():
    """Test the functionality of the QueryInterface method."""

    assert _do_test_raw("""
        var obj = {};
        obj.QueryInterface(Components.interfaces.nsIXMLHttpRequest);
        obj.open("GET", "foo", false);
    """).failed()

    assert _do_test_raw("""
        var obj = {};
        obj.QueryInterface(Components.interfaces.nsIXMLHttpRequest);
        obj.QueryInterface(Components.interfaces.nsISupports);
        obj.open("GET", "foo", false);
    """).failed()

    assert _do_test_raw("""
        var obj = {};
        obj.QueryInterface(Components.interfaces.nsISupports);
        obj.QueryInterface(Components.interfaces.nsIXMLHttpRequest);
        obj.open("GET", "foo", false);
    """).failed()

    assert _do_test_raw("""
        {}.QueryInterface(Components.interfaces.nsIXMLHttpRequest)
          .open("GET", "foo", false);
    """).failed()

    assert _do_test_raw("""
        {}.QueryInterface(Components.interfaces.nsIXMLHttpRequest)
          .QueryInterface(Components.interfaces.nsISupports)
          .open("GET", "foo", false);
    """).failed()

    assert _do_test_raw("""
        {}.QueryInterface(Components.interfaces.nsISupports)
          .QueryInterface(Components.interfaces.nsIXMLHttpRequest)
          .open("GET", "foo", false);
    """).failed()

    # TODO:
    if False:
        assert _do_test_raw("""
            var obj = {};
            obj.QueryInterface(Components.interfaces.nsIXMLHttpRequest);
            obj.open("GET", "foo", false);
        """).failed()

        assert _do_test_raw("""
            var obj = { foo: {} };
            obj.foo.QueryInterface(Components.interfaces.nsIXMLHttpRequest);
            obj.foo.open("GET", "foo", false);
        """).failed()


def test_overwritability():
    """Test that XPCOM globals can be overwritten."""

    assert not _do_test_raw("""
    xhr = Components.classes[""].createInstance(
        Components.interfaces.nsIXMLHttpRequest);
    xhr = "foo";
    """).failed(fail_on_warnings=False)


def _test_when_bootstrapped(code, fail_bootstrapped=True, fail=False):
    """Tests a chunk of code when the add-on is bootstrapped."""

    assert _do_test_raw(code, bootstrap=True).failed() == fail_bootstrapped
    assert _do_test_raw(code, bootstrap=False).failed() == fail


def test_xpcom_shortcut_cu():
    """Test the Components.utils shortcut."""

    assert not _do_test_raw("""
    Cu.foo();
    """).failed()

    assert _do_test_raw("""
    Cu.evalInSandbox("foo");
    """).failed()


def test_xpcom_shortcut_ci():
    """Test the Components.interfaces shortcut."""

    err = _do_test_raw("""
    var item = Components.classes["@mozilla.org/windowmediator;1"]
                         .getService(Ci.nsIWindowMediator);
    item.registerNotification();
    """, bootstrap=True)
    assert len(err.warnings) == 1

    err = _do_test_raw("""
    var item = Components.classes["@mozilla.org/windowmediator;1"]
                         .getService(Ci.nsIWindowMediator);
    item.registerNotification();
    """, bootstrap=False)
    assert len(err.warnings) == 0


def test_xpcom_shortcut_cc():
    """Test the Components.classes shortcut."""

    err = _do_test_raw("""
    var item = Components.classes["@mozilla.org/windowmediator;1"]
                   .getService(Components.interfaces.nsIWindowMediator);
    item.registerNotification();
    """, bootstrap=True)
    assert len(err.warnings) == 1

    err = _do_test_raw("""
    var item = Cc["@mozilla.org/windowmediator;1"]
                   .getService(Components.interfaces.nsIWindowMediator);
    item.registerNotification();
    """, bootstrap=True)
    assert len(err.warnings) == 1

    err = _do_test_raw("""
    var item = Cc["@mozilla.org/windowmediator;1"]
                   .getService(Components.interfaces.nsIWindowMediator);
    item.registerNotification();
    """, bootstrap=False)
    assert len(err.warnings) == 0


def test_xpcom_shortcut_services_wm():
    """Test that Services.wm throws a warning when bootstrapped."""

    _test_when_bootstrapped("""
    Services.wm.registerNotification();
    """)


def test_xpcom_shortcut_services_ww():
    """Test that Services.ww throws a warning when bootstrapped."""

    _test_when_bootstrapped("""
    Services.ww.addListener();
    """)


def test_synchronous_sql():
    """Test that uses of synchronous SQL are flagged."""

    assert _do_test_raw("database.executeSimpleSQL('foo');").failed()

    assert not _do_test_raw('database.createStatement();').failed()

    for meth in 'execute', 'executeStep':
        assert _do_test_raw('database.createStatement().%s();' % meth).failed()

    assert not _do_test_raw("""
        database.createStatement().executeAsync()
    """).failed()


def test_nsisound_play():
    """Test that nsISound.play is flagged."""

    assert not _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsISound);
    foo.bar("asdf");
    """).failed()

    assert _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsISound);
    foo.play("asdf");
    """).failed()


def test_nsidnsservice_resolve():
    """Test that nsIDNSService.resolve is flagged."""

    assert not _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsIDNSService);
    foo.asyncResolve("asdf");
    """).failed()

    assert _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsIDNSService);
    foo.resolve("asdf");
    """).failed()


def test_xpcom_nsiwebbrowserpersist():
    """
    Test that nsIWebBrowserPersist.saveURI is flagged when called
    with a null load context.
    """

    def test(js, want_pass):
        err = _do_test_raw(js)
        if err.warnings:
            result = err.warnings[0]['id'][-1] != 'webbrowserpersist_saveuri'
            assert result == want_pass
        else:
            assert want_pass

    test("""
    var foo = Cc["foo"].getService(Components.interfaces.nsIWebBrowserPersist);
    foo.saveURI(null, null, null, null, null, null, null);
    """, False)

    test("""
    var foo = Cc["foo"].getService(Components.interfaces.nsIWebBrowserPersist);
    var thing = null;
    foo.saveURI(null, null, null, null, null, null, thing);
    """, False)

    test("""
    var foo = Cc["foo"].getService(Components.interfaces.nsIWebBrowserPersist);
    foo.saveURI(null, null, null, null, null, null, thing);
    """, True)


def test_xpcom_nsiwebbrowserpersist_deprecation():
    """Tests that nsIWebBrowserPersist emits deprecation warnings."""

    assert _do_test_raw("""
    thing.QueryInterface(Components.interfaces.nsIWebBrowserPersist).saveChannel()
    """).failed()

    assert _do_test_raw("""
    thing.QueryInterface(Ci.nsIWebBrowserPersist).saveURI(1, 2, 3, 4, 5, 6, 7);
    """).failed()

    assert _do_test_raw("""
    thing.QueryInterface(Ci.nsIWebBrowserPersist).savePrivacyAwareURI()
    """).failed()


class TestnsIWindowWatcher(TestCase):

    def _run_against_foo(self, script):
        self.run_script("""
        var foo = Cc["foo"].getService(Components.interfaces.nsIWindowWatcher);
        %s
        """ % script)

    def test_openWindow_pass(self):
        """
        Test that `foo.openWindow("<remote url>")` throws doesn't throw an error
        for chrome/local URIs.
        """
        self._run_against_foo("""
        foo.openWindow("foo")
        foo.openWindow("chrome://foo/bar")
        """)
        self.assert_silent()

    def test_openWindow_flag_var(self):
        """
        Test that `foo.openWindow(bar)` throws doesn't throw an error where `bar`
        is a dirty object.
        """
        self._run_against_foo("""
        foo.openWindow(bar)
        """)
        self.assert_notices()

    @parametrize('uri', ('http://foo/bar/',
                         'https://foo/bar/',
                         'ftp://foo/bar/',
                         'data:asdf'))
    def test_openWindow(self, uri):
        """
        Test that `foo.openWindow("<remote url>")` throws an error where
        <remote url> is a non-chrome, non-relative URL.
        """

        self._run_against_foo('foo.openWindow("%s")' % uri)
        self.assert_failed(with_warnings=True)


def test_nsITransferable_init():
    """
    Tests that nsITransferable.init() is not called with a null first arg.
    """

    err = _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsITransferable);
    foo.init("hello");
    """)
    assert not err.failed()

    err = _do_test_raw("""
    var foo = Cc["foo"].getService(Components.interfaces.nsITransferable);
    foo.init(null);
    """)
    assert err.failed()
