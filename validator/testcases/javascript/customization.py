from ..regex.generic import FILE_REGEXPS, strip_whitespace
from .predefinedentities import INTERFACES
from .preferences import BANNED_PREF_BRANCHES


CUSTOMIZATION_API_HELP = (
    'We are currently working to provide libraries and APIs to allow '
    'extensions to modify these settings in ways that we can guarantee are '
    'in-policy. In the interim, we recommend that you avoid changing these '
    'settings altogether, if at all possible.')

CUSTOMIZATION_PREF_MESSAGE = {
    'description': (
        'Extensions must not alter user preferences such as the current home '
        'page, new tab page, or search engine, without explicit user consent, '
        'in which a user takes a non-default action. Such changes must also '
        'be reverted when the extension is disabled or uninstalled.',
        'In nearly all cases, new values for these preferences should be '
        'set in the default preference branch, rather than the user branch.'),
    'signing_help':
        'Add-ons which directly change these preferences must undergo at '
        'manual code review for at least one submission. ' +
        CUSTOMIZATION_API_HELP,
    'signing_severity': 'high',
}

SEARCH_PREF_MESSAGE = {
    'description':
        'Search engine preferences may not be changed by add-ons directly. '
        'All such changes must be made only via the browser search service, '
        'and only after an explicit opt-in from the user. All such changes '
        'must be reverted when the extension is disabled or uninstalled.',
    'signing_help': (
        'You should remove all references to these preferences from your '
        'code, and interact with search settings only via the '
        '`Services.search` interface. Extensions which interact with these '
        'preferences directly are not acceptable within the Firefox add-on '
        'ecosystem.',
        'Note, however, that extensions which change search settings even via '
        'the search service must undergo manual code review for at least '
        'one submission. ' + CUSTOMIZATION_API_HELP),
    'signing_severity': 'high',
}


BANNED_PREF_BRANCHES.extend([
    # Search, homepage, and customization preferences
    (u'browser.newtab.url', CUSTOMIZATION_PREF_MESSAGE),
    (u'browser.newtabpage.enabled', CUSTOMIZATION_PREF_MESSAGE),
    (u'browser.search.defaultenginename', SEARCH_PREF_MESSAGE),
    (u'browser.search.searchEnginesURL', SEARCH_PREF_MESSAGE),
    (u'browser.startup.homepage', CUSTOMIZATION_PREF_MESSAGE),
    (u'extensions.getMoreThemesURL', None),
    (u'keyword.URL', SEARCH_PREF_MESSAGE),
    (u'keyword.enabled', SEARCH_PREF_MESSAGE),
])

SEARCH_MESSAGE = 'Potentially dangerous use of the search service'
SEARCH_DESCRIPTION = (
    'Changes to the default and currently-selected search engine settings '
    'may only take place after users have explicitly opted-in, by taking '
    'a non-default action. Any such changes must be reverted when the add-on '
    'making them is disabled or uninstalled.')


def search_warning(severity='medium', editors_only=False,
                   message=SEARCH_MESSAGE,
                   description=SEARCH_DESCRIPTION):
    return {'err_id': ('testcases_javascript_actions',
                       'search_service',
                       'changes'),
            'signing_help':
                'Add-ons which directly change search settings must undergo '
                'manual code review for at least one submission. ' +
                CUSTOMIZATION_API_HELP,
            'signing_severity': severity,
            'editors_only': editors_only,
            'warning': message,
            'description': description}

INTERFACES.update({
    u'nsIBrowserSearchService':
        {'value':
            {u'currentEngine':
                {'readonly': search_warning(severity='high')},
             u'defaultEngine':
                {'readonly': search_warning(severity='high')},
             u'addEngine':
                {'dangerous': search_warning()},
             u'addEngineWithDetails':
                {'dangerous': search_warning()},
             u'removeEngine':
                {'dangerous': search_warning()},
             u'moveEngine':
                {'dangerous': search_warning()}}},
})

FILE_REGEXPS.append(
    # Possible attempts to replace the new tab page.
    (strip_whitespace(r"""
        == \s* ["']about:(newtab|blank)["'] |
        ["']about:(newtab|blank)["'] \s* == |
        /\^?about:newtab\$?/ \s* \. test\b |
        \?what=newtab
     """),
     {'err_id': ('testcases_regex', 'file', 'new-tab-page'),
      'warning': 'Possible attempt to override new tab page',

      'description': (
         'The new tab page should be changed only by writing '
         'to the appropriate preference in the default preferences '
         'branch. Such changes may only be made after an explicit '
         'user opt-in, unless the add-on was explicitly and directly '
         'installed by the user, and changing the new tab page is its '
         'primary purpose.',
         'If this code does not change the behavior of the new tab '
         'page, it may be ignored.'),

      'signing_help':
         'Extensions may not programmatically override the new tab '
         'page. If this code has another purpose, we nonetheless '
         'recommend against testing URLs for these values, since '
         'results can be unpredictable, and better options usually '
         'exist. If you cannot avoid making these tests, please leave '
         'this code unchanged, and it will be ignored in future '
         'submissions.',

      'signing_severity': 'low'}),
)
