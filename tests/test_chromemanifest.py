from .helper import MockXPI, chrome_manifest

from validator.chromemanifest import ChromeManifest
from validator.errorbundler import ErrorBundle


def test_open():
    """Open a chrome file and ensure that data can be pulled from it."""

    xpi = MockXPI({
        'chrome.manifest': 'tests/resources/chromemanifest/chrome.manifest'})

    manifest = ChromeManifest(xpi, 'chrome.manifest')
    assert manifest is not None

    g_obj = list(manifest.get_entries('subject', 'predicate'))

    assert len(g_obj) == 1
    assert g_obj[0]['args'][1] == 'object'

    sub_locale = list(manifest.get_entries('locale'))
    assert len(sub_locale) == 2


def test_lines():
    """Test that the correct line numbers are given in a chrome.manifest."""

    c = chrome_manifest("""
        zero foo bar
        one bar foo
        two abc def
        #comment
        four def abc
    """.strip())

    assert next(c.get_entries('zero'))['line'] == 1
    assert next(c.get_entries('one'))['line'] == 2
    assert next(c.get_entries('two'))['line'] == 3
    assert next(c.get_entries('four'))['line'] == 5


def test_incomplete_triplets():
    """Test that incomplete triplets are ignored."""

    c = chrome_manifest('foo\nbar')
    assert not c.entries


def test_duplicate_subjects():
    """Test that two triplets with the same subject can be retrieved."""

    c = chrome_manifest("""
        foo bar abc
        foo bar def
        foo bam test
        oof rab cba
    """)

    assert len(list(c.get_entries('foo'))) == 3
    assert len(list(c.get_entries('foo', 'bar'))) == 2
    assert len(list(c.get_entries('foo', 'bar', 'abc'))) == 1


def test_applicable_overlays():
    """
    Test that overlays that apply to the current chrome context are returned
    with proper paths.
    """

    c = chrome_manifest("""
        content ns1 jar:foo.jar!/content/junk/
        content ns1 jar:bar.jar!/content/stuff/
        content ns2 jar:zap.jar!/
        content ns3 /baz/

        overlay chrome://foo.xul chrome://ns1/content/junk/o1.xul
        overlay chrome://foo.xul chrome://ns1/content/junk/o2.xul
        overlay chrome://foo.xul chrome://ns1/content/stuff/o3.xul
        overlay chrome://foo.xul chrome://ns2/content/dir/o4.xul
        overlay chrome://foo.xul chrome://ns3/content/root/dir/o5.xul
        overlay chrome://foo.xul chrome://ns1/content/invalid/o6.xul
    """)

    gac = c.get_applicable_overlays

    assert gac(MockPackStack()) == set(['/baz/root/dir/o5.xul'])
    assert gac(MockPackStack(['foo.jar'])) == set(['/o1.xul', '/o2.xul'])
    assert gac(MockPackStack(['bar.jar'])) == set(['/o3.xul'])
    assert gac(MockPackStack(['zap.jar'])) == set(['/content/dir/o4.xul'])


def test_reverse_lookup():
    """Test that the chrome reverse lookup function works properly."""

    c = chrome_manifest("""
        content ns1 /dir1/
        content ns2 /dir2/foo/
        content nsbad1 /dir3
        content ns3 jar:foo.jar!/subdir1/
        content ns3 jar:zap.jar!/altdir1/
        content ns4 jar:bar.jar!/subdir2
    """)

    assert c.reverse_lookup(MockPackStack(), 'random.js') is None
    assert (c.reverse_lookup(MockPackStack(), '/dir1/x.js') ==
            'chrome://ns1/x.js')
    assert c.reverse_lookup(MockPackStack(), '/dir2/x.js') is None
    assert (c.reverse_lookup(MockPackStack(), '/dir2/foo/x.js') ==
            'chrome://ns2/x.js')
    assert (c.reverse_lookup(MockPackStack(), '/dir3/x.js') ==
            'chrome://nsbad1/x.js')
    assert (c.reverse_lookup(MockPackStack(['foo.jar']), '/x.js') ==
            'chrome://ns3/subdir1/x.js')
    assert (c.reverse_lookup(MockPackStack(['foo.jar']), '/zap/x.js') ==
            'chrome://ns3/subdir1/zap/x.js')
    assert (c.reverse_lookup(MockPackStack(['bar.jar']), '/x.js') ==
            'chrome://ns4/subdir2/x.js')
    assert (c.reverse_lookup(MockPackStack(['zap.jar']), '/x.js') ==
            'chrome://ns3/altdir1/x.js')


def test_overlay_object():
    """Test that overlay instructions have all its properties."""

    err = ErrorBundle()

    c = chrome_manifest("""
        content namespace /foo/bar
        overlay namespace /uri/goes/here
    """)

    err.save_resource('chrome.manifest', c)
    c.get_applicable_overlays(err)
    assert not err.failed()
    assert not err.notices

    err = ErrorBundle()

    c = chrome_manifest("""
        content namespace /foo/bar
        overlay /uri/goes/here
    """)
    err.save_resource('chrome.manifest', c)
    c.get_applicable_overlays(err)
    assert err.failed()
    assert not err.notices


class MockPackStack(object):

    def __init__(self, stack=None):
        if stack is None:
            stack = []
        self.package_stack = stack

    @property
    def is_nested_package(self):
        return bool(self.package_stack)
