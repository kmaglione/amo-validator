from .helper import chrome_manifest

import validator.testcases.chromemanifest as tc_chromemanifest
from validator.errorbundler import ErrorBundle


def test_pass():
    """Test that standard category subjects pass."""

    c = chrome_manifest('category foo bar')
    err = ErrorBundle()
    err.save_resource('chrome.manifest', c)

    tc_chromemanifest.test_categories(err)
    assert not err.failed()


def test_no_chromemanifest():
    """
    Chrome manifest tests should not be run if there is no chrome manifest.
    """
    err = ErrorBundle()
    assert tc_chromemanifest.test_categories(err) is None
    assert not err.failed()

    err = ErrorBundle()
    assert tc_chromemanifest.test_resourcemodules(err) is None
    assert not err.failed()


def test_js_categories_gecko2():
    """Test that JS categories raise problems for hyphenated values."""
    c = chrome_manifest('category JavaScript-DOM-class foo bar')
    err = ErrorBundle()
    err.save_resource('chrome.manifest', c)

    tc_chromemanifest.test_categories(err)
    assert err.failed()

    warning = {'id': ('testcases_chromemanifest', 'test_resourcemodules',
                      'resource_modules'),
               'message': 'Potentially dangerous category entry',
               'signing_severity': 'medium',
               'editors_only': True}
    msg = err.warnings[0]
    for key, value in warning.iteritems():
        assert msg[key] == value


def test_fail_resourcemodules():
    """'resource modules' should fail validation."""
    c = chrome_manifest('resource modules foo')
    err = ErrorBundle()
    err.save_resource('chrome.manifest', c)

    tc_chromemanifest.test_resourcemodules(err)
    assert err.failed()

    # Fail even if it's just a prefix.
    c = chrome_manifest('resource modulesfoo')
    err = ErrorBundle()
    err.save_resource('chrome.manifest', c)

    tc_chromemanifest.test_resourcemodules(err)
    assert err.failed()


def test_content_instructions():
    """Test that banned content namespaces are banned."""

    err = ErrorBundle()
    c = chrome_manifest('content foo bar')
    err.save_resource('chrome.manifest', c)
    tc_chromemanifest.test_content_instructions(err)
    assert not err.failed()

    c = chrome_manifest('content godlikea bar')
    err.save_resource('chrome.manifest', c)
    tc_chromemanifest.test_content_instructions(err)
    assert err.failed()


def test_content_missing_information():
    """Test that incomplete information in a content instruction fails."""

    err = ErrorBundle()
    c = chrome_manifest('content foo')
    err.save_resource('chrome.manifest', c)
    tc_chromemanifest.test_content_instructions(err)
    assert err.failed()


def test_content_instructions_trailing_slash():
    """Test that trailing slashes are necessary for content instructions."""

    err = ErrorBundle()
    c = chrome_manifest('content namespace /uri/goes/here')
    err.save_resource('chrome.manifest', c)
    tc_chromemanifest.test_content_instructions(err)
    assert not err.failed()
    assert err.notices

    err = ErrorBundle()
    c = chrome_manifest('content namespace /uri/goes/here/ flag=true')
    err.save_resource('chrome.manifest', c)
    tc_chromemanifest.test_content_instructions(err)
    assert not err.failed()
    assert not err.notices
