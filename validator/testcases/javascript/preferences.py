import re

from validator.errorbundler import maybe_tuple, merge_description
from validator.decorator import define_post_init
from validator.testcases.regex import javascript as regex_javascript
from validator.testcases.regex.javascript import JSRegexTest, STRING_REGEXPS
from .instanceactions import INSTANCE_DEFINITIONS
from .predefinedentities import GLOBAL_ENTITIES, INTERFACES, build_quick_xpcom


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
    (u'network.proxy.autoconfig_url', {
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
    (u'network.proxy.', NETWORK_PREF_MESSAGE),
    (u'network.http.', NETWORK_PREF_MESSAGE),
    (u'network.websocket.', NETWORK_PREF_MESSAGE),

    # Other
    (u'browser.preferences.instantApply', None),

    (u'extensions.alwaysUnpack', None),
    (u'extensions.bootstrappedAddons', None),
    (u'extensions.dss.', None),
    (u'extensions.installCache', None),
    (u'extensions.lastAppVersion', None),
    (u'extensions.pendingOperations', None),

    (u'general.useragent.', None),

    (u'nglayout.debug.disable_xul_cache', None),
]

BANNED_PREF_REGEXPS = []

PREF_REGEXPS = []


# For tests in literal strings, add help text suggesting passing the
# preference directly to preference getter functions.
def add_pref_help(desc):
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

def create_preference_branch(arguments, traverser, node, wrapper):
    """Creates a preference branch, which can be used for testing composed
    preference names."""

    if arguments:
        arg = traverser._traverse_node(arguments[0])
        if arg.is_literal():
            res = build_quick_xpcom('createInstance', 'nsIPrefBranch',
                                    traverser, wrapper=True)
            res.hooks['preference_branch'] = arg.as_str()
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

    if wrapper.value.source == 'arguments':
        for msg in wrapper.value.messages:
            if (msg['id'] == PREFERENCE_ERROR_ID and
                    (msg['file'], msg['line']) == (
                        traverser.filename, traverser.line)):
                traverser.err.drop_message(msg)


def get_preference(wrapper, arguments, traverser):
    """Tests get preference calls, and removes preference write warnings
    when they are not necessary."""

    if len(arguments) >= 1:
        arg = traverser._traverse_node(arguments[0])
        if arg.is_clean_literal():
            drop_pref_messages(arg)


def set_preference(wrapper, arguments, traverser):
    """Tests set preference calls for non-root preferences branches against
    dangerous values."""

    if len(arguments) < 1:
        return

    parent = getattr(wrapper, 'parent', None)
    arg = traverser._traverse_node(arguments[0])
    if arg.is_literal():
        pref = arg.as_str()

        # If we're being called on a preference branch other than the root,
        # prepend its branch name to the passed preference name.
        branch = parent and parent.hooks.get('preference_branch')
        if branch:
            pref = branch + pref
        elif arg.is_clean_literal():
            drop_pref_messages(arg)

        kw = {'err_id': ('testcases_javascript_actions',
                         '_call_expression', 'called_set_preference'),
              'warning': 'Attempt to set a dangerous preference'}

        validate_pref(pref, traverser=traverser, extra=kw, wrapper=arg)


def call_pref(a, t, e):
    """
    Handler for pref() and user_pref() calls in defaults/preferences/*.js files
    to ensure that they don't touch preferences outside of the "extensions."
    branch.
    """

    # We really need to clean up the arguments passed to these functions.
    traverser = t.im_self
    args = a

    if not traverser.filename.startswith('defaults/preferences/') or not args:
        return

    set_preference(traverser.wrap(None), args, traverser)

    value = traverser._traverse_node(args[0]).as_str()
    return test_preference(value)


def test_preference(value):
    for branch in 'extensions.', 'services.sync.prefs.sync.extensions.':
        if value.startswith(branch) and value.rindex('.') > len(branch):
            return

    return ('Extensions should not alter preferences outside of the '
            "'extensions.' preference branch. Please make sure that "
            "all of your extension's preferences are prefixed with "
            "'extensions.add-on-name.', where 'add-on-name' is a "
            'distinct string unique to and indicative of your add-on.')


INSTANCE_DEFINITIONS.update({
    'getBranch': create_preference_branch,
    'getDefaultBranch': create_preference_branch,
})

INTERFACES.update({
    u'nsIPrefBranch': {
        'value': dict(
            tuple((method, {'return': set_preference})
                  for method in (u'setBoolPref',
                                 u'setCharPref',
                                 u'setComplexValue',
                                 u'setIntPref',
                                 u'clearUserPref',
                                 u'deleteBranch',
                                 u'resetBranch')) +
            tuple((method, {'return': get_preference})
                  for method in (u'getBoolPref',
                                 u'getCharPref',
                                 u'getChildList',
                                 u'getComplexValue',
                                 u'getFloatPref',
                                 u'getIntPref',
                                 u'getPrefType',
                                 u'prefHasUserValue')))},
})

GLOBAL_ENTITIES.update({
    # From Preferences.jsm.
    # TODO: Support calls that return instances of this object which
    # operate on non-root branches.
    u'Preferences': {'value': {
        u'get': {'return': get_preference},
        u'reset': {'return': set_preference},
        u'resetBranch': {'return': set_preference},
        u'set': {'return': set_preference}}},

    # Preference creation in pref defaults files.
    u'pref': {'dangerous': call_pref},
    u'user_pref': {'dangerous': call_pref},
})
