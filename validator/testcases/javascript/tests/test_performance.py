from __future__ import absolute_import, print_function, unicode_literals

import pytest

from tests.helper import Contains, Matches
from tests.js_helper import TestCase


class TestSQL(TestCase):
    @pytest.mark.parametrize('script', ('foo.createAsyncStatement({code})',
                                        'foo.executeSimpleSQL({code})',
                                        'foo.createStatement({code})'))
    def test_dynamic_sql(self, script):
        """Test that the execution of SQL statements using dynamic values
        raises a warning."""

        warning = {'id': Contains('executeSimpleSQL_dynamic'),
                   'description': Matches('dynamic parameter binding')}

        # Unknown value.
        self.run_script(script.format(code='"" + foo'))
        self.assert_warnings(warning)

        # Static string.
        self.setup_err()
        self.run_script(script.format(code='"SELECT ?"'))
        self.assert_no_warnings(warning)

    @pytest.mark.parametrize('code', (
        'foo.executeSimpleSQL("sql")',
        'foo.createStatement().execute()',
        'foo.createStatement().executeStep()',
        'foo.QueryInterface(Ci.mozIStorageBaseStatement).execute()',
        'foo.QueryInterface(Ci.mozIStorageBaseStatement).executeStep()',
    ))
    def test_synchronous_sql(self, code):
        """Test that the use of synchronous Storage APIs is raised as a
        performance issue."""

        self.run_script(code)
        self.assert_warnings({
            'description': Matches(r'Sqlite\.jsm.*`executeAsync`')
        })


class TestXMLHttpRequest(TestCase):
    @pytest.fixture(autouse=True, params=(
        'XMLHttpRequest()',
        'new XMLHttpRequest()',
        'new XMLHttpRequest',
        'Cc[""].createInstance(Ci.nsIXMLHttpRequest)',
    ))
    def get_xhr(self, request):
        return request.param

    @pytest.mark.parametrize('arg', ('false', '""', '0'))
    def test_open_sync(self, get_xhr, arg):
        """Test that the `open` method is flagged when called with a falsy
        third argument."""

        self.run_script('let xhr = {get_xhr};'
                        'xhr.open(method, url, {arg});'
                        .format(arg=arg, get_xhr=get_xhr))

        self.assert_warnings({
            'id': Contains('nsIXMLHttpRequest.open'),
            'description': Matches('Synchronous.*serious UI performance '
                                   'problems'),
        })

    @pytest.mark.parametrize('arg', ('', ', true', ', "0"', ', {}', ', []'))
    def test_open_async(self, get_xhr, arg):
        """Test that the `open` method is not flagged when called with a truthy
        third argument."""

        self.run_script('let xhr = {get_xhr};'
                        'xhr.open(method, url{arg});'
                        .format(arg=arg, get_xhr=get_xhr))

        self.assert_silent()


class TestPrototype(TestCase):
    MESSAGE = {
        'id': ('testcases_javascript', 'performance', 'prototype_mutation'),
        'message': Contains('deprecated'),
        'description': Matches(r'`Object\.create`'),
    }

    def test_set__proto__(self):
        """Test changes to the __proto__ property are flagged."""

        self.run_script('obj.__proto__ = foo;')
        self.assert_warnings(self.MESSAGE)

    def test_create_with__proto__(self):
        """Test that creating a object literals with `__proto__` properties
        is not flagged."""

        self.run_script('var obj = {__proto__: foo};')
        self.run_script('var obj = {"__proto__": foo};')
        self.assert_silent()

    def test_setPrototypeOf(self):
        """Test that changes to object prototypes via `Object.setPrototypeOf`
        are flagged."""

        self.run_script('Object.setPrototypeOf(obj, foo)')
        self.assert_warnings(self.MESSAGE)


class TestOther(TestCase):
    def test_nsIAccessibleRetrieval(self):
        """Test that the entire `nsIAccessibleRetrieval` interface is
        flagged."""

        self.run_script('foo.QueryInterface(Ci.nsIAccessibleRetrieval)')

        self.assert_warnings({
            'id': Contains('nsIAccessibleRetrieval'),
            'description': Matches('performance degradation'),
        })

    def test_nsIDNSService_resolve(self):
        """Test that `nsIDNSService.resolve` is flagged for performance
        issues."""

        self.run_script('Cc[""].getService(Ci.nsIDNSService).resolve(foo)')

        self.assert_warnings({
            'id': Contains('nsIDNSService.resolve'),
            'description': Matches('synchronous.*freeze.*asyncResolve'),
        })

    def test_nsISound_play(self):
        """Test that `nsISound.play` is flagged for performance issues."""

        self.run_script('Cc[""].getService(Ci.nsISound).play(foo)')

        self.assert_warnings({
            'id': Contains('nsISound.play'),
            'description': Matches('synchronous.*freezes.*HTML5 audio'),
        })

    def test_processNextEvent(self):
        """Test that calls to `processNextEvent` are flagged as
        performance/stability issues."""

        self.run_script('foo.processNextEvent()')
        self.assert_warnings({
            'id': Contains('**.processNextEvent'),
            'description': Matches('Spinning the event loop.*'
                                   'deadlocks.*re-?entrancy.*async'),
        })
