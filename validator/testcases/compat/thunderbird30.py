from validator.testcases.regex.compat import (COMPAT_REGEXPS,
                                              CheapCompatBugPatternTests)

from . import build_definition, register_changed_entities


TB30_DEFINITION = build_definition(30, thunderbird=True)

COMPAT_REGEXPS.extend([
    (TB30_DEFINITION, CheapCompatBugPatternTests('Thunderbird 30', {
        r'log\.lastWeek': 863226,
        r'log\.twoWeeksAgo': 863226,
        r'filemessageschoosethis\.label': 964425,
        r'recentfolders\.label': 964425,
        r'protocolNotFound\.title': 973368,
        r'protocolNotFound\.longDesc': 973368,
        r'quickFilterBar\.barLabel\.label': 592248,
        r'updateOthers\.label': 978563,
        r'enableAddonsUpdate3\.label': 978563,
        r'enableAddonsUpdate3\.accesskey': 978563,
        r'bounceSystemDockIcon\.label': 601263,
        r'bounceSystemDockIcon\.accesskey': 601263})),
])

# Thunderbird 30 IDL changes
TB30_ENTITIES = [
    {'name': 'nsIMsgDatabase.forceFolderDBClosed',
     'status': 'moved to nsIMsgDBService',
     'bug': 876548,
     'compat_type': 'error'},
    {'name': 'nsIMsgCompose.checkAndPopulateRecipients',
     'status': 'removed',
     'bug': 970118,
     'compat_type': 'error'},
]
register_changed_entities(version_definition=TB30_DEFINITION,
                          entities=TB30_ENTITIES,
                          version_string='Thunderbird 30')

# Thunderbird 30 JS changes
TB30_JS_ENTITIES = [
    {'name': 'GlodaMsgSearcher.retrievalLimit',
     'status': 'removed', 'bug': 742236, 'compat_type': 'error'},
    {'name': 'GlodaIMSearcher.retrievalLimit',
     'status': 'removed', 'bug': 742236, 'compat_type': 'error'},
    {'name': 'getNonHtmlRecipients',
     'status': 'removed', 'bug': 970118, 'compat_type': 'error'},
]
register_changed_entities(version_definition=TB30_DEFINITION,
                          entities=TB30_JS_ENTITIES,
                          version_string='Thunderbird 30')
