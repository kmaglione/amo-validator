from __future__ import absolute_import, print_function, unicode_literals

import re

from validator.errorbundler import maybe_tuple, merge_description
from validator.decorator import define_post_init
from validator.testcases.regex import javascript as regex_javascript
from validator.testcases.regex.javascript import JSRegexTest, STRING_REGEXPS
from .jstypes import Global, Interfaces


PREFERENCE_ERROR_ID = 'testcases_regex', 'string', 'preference'

NETWORK_PREF_MESSAGE = {
    'description':
        'Changing network preferences may be dangerous, and often leads to '
        'performance costs.',
    'signing_help':
        'Changes to these preferences are strongly discouraged. If at all '
        'possible, you should remove any reference to them from '
        'your extension. Extensions which do modify these preferences '
        'must undergo light manual code review for at least one submission.',
    'signing_severity': 'low',
}

BANNED_PREF_BRANCHES = [
    # Network
    ('network.proxy.autoconfig_url', {
        'description':
            'As many add-ons have reason to change the proxy autoconfig URL, '
            'and only one at a time may do so without conflict, extensions '
            'must make proxy changes using other mechanisms. Installing a '
            'proxy filter is the recommended alternative: '
            'https://developer.mozilla.org/en-US/docs/Mozilla/Tech/XPCOM/'
            'Reference/Interface/nsIProtocolProxyService#registerFilter()',
        'signing_help':
            'Dynamic proxy configuration should be implemented via proxy '
            'filters, as described above. This preference should not be '
            'set, except directly by end users.',
        'signing_severity': 'low'}),
    ('network.proxy.', NETWORK_PREF_MESSAGE),
    ('network.http.', NETWORK_PREF_MESSAGE),
    ('network.websocket.', NETWORK_PREF_MESSAGE),

    # Other
    ('browser.preferences.instantApply', None),

    ('extensions.alwaysUnpack', None),
    ('extensions.bootstrappedAddons', None),
    ('extensions.dss.', None),
    ('extensions.installCache', None),
    ('extensions.lastAppVersion', None),
    ('extensions.pendingOperations', None),

    ('general.useragent.', None),

    ('nglayout.debug.disable_xul_cache', None),
]

BANNED_PREF_REGEXPS = []

PREF_REGEXPS = []


def add_pref_help(desc):
    """Add help text to an error description suggesting passing the preference
    directly to preference getter functions.

    This is used to add additional help text to warnings about bare preference
    string literals which would not apply if said literal is being passed
    directly to a known preference API method."""

    desc = desc.copy()
    for key in 'description', 'signing_help':
        if key in desc:
            desc[key] = maybe_tuple(desc[key]) + maybe_tuple(PREF_STRING_HELP)

    return desc

PREF_STRING_HELP = (
    'If you are reading, but not writing, this preference, please consider '
    'passing a string literal directly to `Preferences.get()` or '
    '`nsIPrefBranch.get*Pref`.')


@define_post_init
def pref_tester():
    """Create a JSRegexTest instance based on the final values in the
    PREF_REGEXPS, BANNED_PREF_REGEXPS, and BANNED_PREF_BRANCHES definitions,
    and add most of the resulting expressions to the bare JS string
    tester as well."""

    # Match exact preference names from BANNED_PREF_REGEXPS.
    PREF_REGEXPS.extend(
        (pattern,
         {'err_id': PREFERENCE_ERROR_ID,
          'warning': 'Potentially unsafe preference branch referenced',
          'description': 'Extensions should not alter preferences '
                         'matching /%s/.' % pattern})
        for pattern in BANNED_PREF_REGEXPS)

    # Match any preference under each branch in BANNED_PREF_BRANCHES.
    PREF_REGEXPS.extend(
        ('^%s' % re.escape(branch),
         merge_description(
             {'err_id': PREFERENCE_ERROR_ID,
              'warning': 'Potentially unsafe preference branch referenced'},
             reason or ('Extensions should not alter preferences in '
                        'the `%s` preference branch' % branch)))
        for branch, reason in BANNED_PREF_BRANCHES)

    # Make sure our string tester has not yet been finalized.
    assert regex_javascript.string_tester is None
    STRING_REGEXPS.extend((pattern, add_pref_help(desc))
                          for pattern, desc in PREF_REGEXPS)

    # The following patterns should only be flagged in strings we're certain
    # are being passed to preference setter functions, so add them after
    # appending the others to the literal string tests.
    PREF_REGEXPS.append(
        (r'.*password.*',
         {'err_id': PREFERENCE_ERROR_ID,
          'warning': 'Passwords should not be stored in preferences',
          'description': 'Storing passwords in preferences is insecure. '
                         'The Login Manager should be used instead.'}),
    )

    return JSRegexTest(PREF_REGEXPS)


def validate_pref(*args, **kw):
    return pref_tester.test(*args, **kw)


# Preference APIs.

@Global.hook(('**', 'getBranch'), 'return')
@Global.hook(('**', 'getDefaultBranch'), 'return')
def create_preference_branch(this, args, callee):
    """Creates a preference branch, which can be used for testing composed
    preference names."""

    if args:
        if args[0].is_literal:
            res = this.traverser.wrap().query_interface('nsIPrefBranch')
            res.hooks['preference_branch'] = args[0].as_str()
            return res


def drop_pref_messages(wrapper):
    """Drop any preference-related messages for the given wrapper, if that
    wrapper is an immediate literal that was passed as an argument, and the
    messages are on the same line as the traverser.

    Used to ignore preference warnings when the strings are provably being
    read rather than written, or when they're provably being written and
    have a more useful, redundant warning already.
    """

    traverser = wrapper.traverser

    if wrapper.parse_node['type'] == 'Literal':
        for msg in wrapper.value.messages:
            if (msg['id'] == PREFERENCE_ERROR_ID and
                    (msg['file'], msg['line']) == (
                        traverser.filename, traverser.line)):
                traverser.err.drop_message(msg)


nsIPrefBranch = Interfaces.hook('nsIPrefBranch')


@nsIPrefBranch.hook('getBoolPref', 'on_call')
@nsIPrefBranch.hook('getCharPref', 'on_call')
@nsIPrefBranch.hook('getChildList', 'on_call')
@nsIPrefBranch.hook('getComplexValue', 'on_call')
@nsIPrefBranch.hook('getFloatPref', 'on_call')
@nsIPrefBranch.hook('getIntPref', 'on_call')
@nsIPrefBranch.hook('getPrefType', 'on_call')
@nsIPrefBranch.hook('prefHasUserValue', 'on_call')
def get_preference(this, args, callee):
    """Test get preference calls, and remove preference write warnings
    when they are not necessary."""

    if args and args[0].is_clean_literal:
        drop_pref_messages(args[0])


@nsIPrefBranch.hook('setBoolPref', 'on_call')
@nsIPrefBranch.hook('setCharPref', 'on_call')
@nsIPrefBranch.hook('setComplexValue', 'on_call')
@nsIPrefBranch.hook('setIntPref', 'on_call')
@nsIPrefBranch.hook('clearUserPref', 'on_call')
@nsIPrefBranch.hook('deleteBranch', 'on_call')
@nsIPrefBranch.hook('resetBranch', 'on_call')
def set_preference(this, args, callee):
    """Test set preference calls against dangerous values."""

    if len(args) < 1:
        return

    arg = args[0]
    if arg.is_literal:
        parent = getattr(callee, 'parent', this)
        pref = arg.as_str()

        # If we're being called on a preference branch other than the root,
        # prepend its branch name to the passed preference name.
        branch = parent.hooks.get('preference_branch')
        if branch:
            pref = branch + pref
        elif arg.is_clean_literal:
            drop_pref_messages(arg)

        kw = {'err_id': ('testcases_javascript_actions',
                         '_call_expression', 'called_set_preference'),
              'warning': 'Attempt to set a dangerous preference'}

        validate_pref(pref, traverser=this.traverser, extra=kw, wrapper=arg)


def default_prefs_file(traverser):
    return traverser.filename.startswith('defaults/preferences/')


@Global.hook('pref', 'on_call', scope_filter=default_prefs_file)
@Global.hook('user_pref', 'on_call', scope_filter=default_prefs_file)
def call_pref(this, args, callee):
    """
    Handler for pref() and user_pref() calls in defaults/preferences/*.js files
    to ensure that they don't touch preferences outside of the "extensions."
    branch.
    """
    if args:
        set_preference(this, args, callee)
        return test_preference(args[0].as_str())


def test_preference(value):
    for branch in 'extensions.', 'services.sync.prefs.sync.extensions.':
        if value.startswith(branch) and value.rindex('.') > len(branch):
            return

    return ('Extensions should not alter preferences outside of the '
            "'extensions.' preference branch. Please make sure that "
            "all of your extension's preferences are prefixed with "
            "'extensions.add-on-name.', where 'add-on-name' is a "
            'distinct string unique to and indicative of your add-on.')


Global.hook('Preferences', {
    # From Preferences.jsm.
    # TODO: Support calls that return instances of this object which
    # operate on non-root branches.
    'get': {'on_call': get_preference},
    'reset': {'on_call': set_preference},
    'resetBranch': {'on_call': set_preference},
    'set': {'on_call': set_preference},
})
