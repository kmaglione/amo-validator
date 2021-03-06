from defusedxml.common import DefusedXmlException
from mock import patch
from nose.tools import raises

import validator.testcases.installrdf as installrdf
from validator.constants import PACKAGE_THEME
from validator.errorbundler import ErrorBundle
from validator.rdf import RDFParser


def _test_value(key, value, failure=True):
    'Tests a value against a test.'

    err = ErrorBundle()

    test = installrdf.PREDICATE_TESTS[key]
    test(err, value, source='install.rdf')

    if hasattr(test, 'func'):
        func = test.func
    else:
        func = test

    if failure:
        assert err.failed(), '{value} did not fail {func}'.format(
            value=value, func=func.__name__)
    else:
        assert not err.failed(), '{value} did not pass {func}'.format(
            value=value, func=func.__name__)


def test_pass_id():
    'Tests that valid IDs will be accepted.'

    _test_value('id', '{12345678-1234-1234-1234-123456789012}', False)
    _test_value('id', 'abc@foo.bar', False)
    _test_value('id', 'a+bc@foo.bar', False)


def test_fail_id():
    'Tests that invalid IDs will not be accepted.'

    _test_value('id', '{1234567-1234-1234-1234-123456789012}')
    _test_value('id', '!@foo.bar')


def test_pass_version():
    'Tests that valid versions will be accepted.'

    _test_value('version', '1.2.3.4', False)
    _test_value('version', '1a.2.3b+*.-_', False)
    _test_value('version', 'twenty', False)


def test_fail_version():
    'Tests that invalid versions will not be accepted.'

    _test_value('version', '2.0 alpha')
    _test_value('version', '123456789012345678901234567890123')
    _test_value('version', '1.2.3%')


def test_pass_name():
    'Tests that valid names will be accepted.'

    _test_value('name', "Joe Schmoe's Feed Aggregator", False)
    _test_value('name', 'Ozilla of the M', False)


def test_fail_name():
    'Tests that invalid names will not be accepted.'

    _test_value('name', 'Love of the Firefox')
    _test_value('name', 'Mozilla Feed Aggregator')


def _run_test(filename, failure=True, detected_type=0, listed=True,
              overrides=None, compat=False):
    'Runs a test on an install.rdf file'

    return _run_test_raw(open(filename).read(), failure, detected_type,
                         listed, overrides, compat)


def _run_test_raw(data, failure=True, detected_type=0, listed=True,
                  overrides=None, compat=False):
    'Runs a test on an install.rdf snippet'

    data = data.strip()

    err = ErrorBundle()
    err.detected_type = detected_type
    err.save_resource('listed', listed)
    err.overrides = overrides

    if compat:
        err.save_resource('is_compat_test', True)

    err.save_resource('has_install_rdf', True)
    err.save_resource('install_rdf', RDFParser(err, data))
    installrdf.test_install_rdf_params(err)

    print err.print_summary(verbose=True)

    if failure:  # pragma: no cover
        assert err.failed() or err.notices
    else:
        assert not err.failed() and not err.notices

    return err


@patch('validator.testcases.installrdf._test_rdf')
def test_has_rdf(install_rdf):
    "Tests that tests won't be run if there's no install.rdf"

    err = ErrorBundle()

    assert installrdf.test_install_rdf_params(err, None) is None

    err.detected_type = 0
    err.save_resource('install_rdf', RDFParser(err, '<rdf></rdf>'))
    err.save_resource('has_install_rdf', True)

    installrdf.test_install_rdf_params(err, None)
    assert install_rdf.called


def test_passing():
    'Tests a passing install.rdf package.'

    err = _run_test('tests/resources/installrdf/pass.rdf', False)
    assert not err.get_resource('unpack')


def test_unpack():
    err = _run_test('tests/resources/installrdf/unpack.rdf', False)
    assert err.get_resource('em:unpack') == 'true'


def test_compat_flag():
    'Tests that elements that must exist once only exist once.'

    _run_test('tests/resources/installrdf/must_exist_once_missing.rdf',
              compat=True, failure=False)


def test_must_exist_once():
    'Tests that elements that must exist once only exist once.'

    _run_test('tests/resources/installrdf/must_exist_once_missing.rdf')
    _run_test('tests/resources/installrdf/must_exist_once_extra.rdf')


def test_may_exist_once():
    'Tests that elements that may exist once only exist up to once.'

    _run_test('tests/resources/installrdf/may_exist_once_missing.rdf',
              False)
    _run_test('tests/resources/installrdf/may_exist_once_extra.rdf')


def test_may_exist_once_theme():
    'Tests that elements that may exist once in themes.'

    _run_test('tests/resources/installrdf/may_exist_once_theme.rdf',
              False,
              PACKAGE_THEME)
    _run_test('tests/resources/installrdf/may_exist_once_theme_fail.rdf',
              True,
              PACKAGE_THEME)
    _run_test('tests/resources/installrdf/may_exist_once_extra.rdf',
              True,
              PACKAGE_THEME)


def test_may_exist():
    'Tests that elements that may exist once only exist up to once.'

    _run_test('tests/resources/installrdf/may_exist_missing.rdf',
              False)
    _run_test('tests/resources/installrdf/may_exist_extra.rdf', False)


def test_mustmay_exist():
    'Tests that elements that may exist once only exist up to once.'

    # The first part of this is proven by test_must_exist_once

    _run_test('tests/resources/installrdf/mustmay_exist_extra.rdf',
              False)


def test_shouldnt_exist():
    "Tests that elements that shouldn't exist aren't there."

    _run_test('tests/resources/installrdf/shouldnt_exist.rdf')
    _run_test('tests/resources/installrdf/shouldnt_exist.rdf',
              listed=False,
              failure=False)


def test_obsolete():
    'Tests that obsolete elements are reported.'

    err = _run_test('tests/resources/installrdf/obsolete.rdf')
    assert err.notices and not err.failed()


def test_invalid_id():
    """Test that invalid ids get a nice error message."""

    err = _run_test_raw(data="""
<?xml version="1.0"?>

<RDF xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:em="http://www.mozilla.org/2004/em-rdf#">
    <Description about="urn:mozilla:install-manifest">
        <em:id>invalid</em:id>
    </Description>
</RDF>
""")
    assert err.failed()
    assert any('<em:id> is invalid' in msg['message']
               for msg in err.errors)

def test_overrides():
    """Test that overrides will work on the install.rdf file."""

    assert _run_test_raw(data="""
<?xml version="1.0"?>

<RDF xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:em="http://www.mozilla.org/2004/em-rdf#">
    <Description about="urn:mozilla:install-manifest">
        <em:id>bastatestapp1@basta.mozilla.com</em:id>
        <em:version>1.2.3.4</em:version>
        <!-- NOTE THAT NAME IS MISSING -->
        <em:targetApplication>
            <Description>
                <em:id>{ec8030f7-c20a-464f-9b0e-13a3a9e97384}</em:id>
                <em:minVersion>3.7a5pre</em:minVersion>
                <em:maxVersion>0.3</em:maxVersion>
            </Description>
        </em:targetApplication>
    </Description>
</RDF>
    """, failure=False, overrides={'ignore_empty_name': True})


def test_optionsType():
    """Test that the optionsType element works."""

    assert _run_test_raw(data="""
<?xml version="1.0"?>
<RDF xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:em="http://www.mozilla.org/2004/em-rdf#">
    <Description about="urn:mozilla:install-manifest">
        <em:id>bastatestapp1@basta.mozilla.com</em:id>
        <em:version>1.2.3.4</em:version>
        <em:name>foo bar</em:name>
        <em:targetApplication>
            <Description>
                <em:id>{ec8030f7-c20a-464f-9b0e-13a3a9e97384}</em:id>
                <em:minVersion>3.7a5pre</em:minVersion>
                <em:maxVersion>0.3</em:maxVersion>
            </Description>
        </em:targetApplication>
        <em:optionsType>2</em:optionsType>
    </Description>
</RDF>
    """, failure=False)


def test_optionsType_fail():
    """Test that the optionsType element fails with an invalid value."""

    assert _run_test_raw(data="""
<?xml version="1.0"?>
<RDF xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:em="http://www.mozilla.org/2004/em-rdf#">
    <Description about="urn:mozilla:install-manifest">
        <em:id>bastatestapp1@basta.mozilla.com</em:id>
        <em:version>1.2.3.4</em:version>
        <em:name>foo bar</em:name>
        <em:targetApplication>
            <Description>
                <em:id>{ec8030f7-c20a-464f-9b0e-13a3a9e97384}</em:id>
                <em:minVersion>3.7a5pre</em:minVersion>
                <em:maxVersion>0.3</em:maxVersion>
            </Description>
        </em:targetApplication>
        <em:optionsType>5</em:optionsType>
    </Description>
</RDF>
    """, failure=True)


@raises(DefusedXmlException)
def test_billion_laughs_fail():
    """Test that the parsing fails for XML will a billion laughs attack."""
    xml = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT Description (#PCDATA)>
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
 <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
 <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
 <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
 <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
 <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<RDF xmlns="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:em="http://www.mozilla.org/2004/em-rdf#">
    <Description about="urn:mozilla:install-manifest">
        <em:id>&lol9;@basta.mozilla.com</em:id>
        <em:version>1.2.3.4</em:version>
        <em:name>foo bar</em:name>
        <em:targetApplication>
            <Description>
                <em:id>{ec8030f7-c20a-464f-9b0e-13a3a9e97384}</em:id>
                <em:minVersion>3.7a5pre</em:minVersion>
                <em:maxVersion>0.3</em:maxVersion>
            </Description>
        </em:targetApplication>
        <em:optionsType>2</em:optionsType>
    </Description>
</RDF>
"""
    RDFParser(ErrorBundle(), xml)
