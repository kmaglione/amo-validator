from validator.testcases.regex.compat import (COMPAT_REGEXPS,
                                              CheapCompatBugPatternTests)

from . import build_definition, register_changed_entities


TB29_DEFINITION = build_definition(29, thunderbird=True)

COMPAT_REGEXPS.extend([
    (TB29_DEFINITION, CheapCompatBugPatternTests('Thunderbird 29', {
        r'update\.checkingAddonCompat': 707489,
        r'columnChooser\.tooltip': 881073,
        r'threadColumn\.tooltip': 881073,
        r'fromColumn\.tooltip': 881073,
        r'recipientColumn\.tooltip': 881073,
        r'attachmentColumn\.tooltip': 881073,
        r'subjectColumn\.tooltip': 881073,
        r'dateColumn\.tooltip': 881073,
        r'priorityColumn\.tooltip': 881073,
        r'tagsColumn\.tooltip': 881073,
        r'accountColumn\.tooltip': 881073,
        r'statusColumn\.tooltip': 881073,
        r'sizeColumn\.tooltip': 881073,
        r'junkStatusColumn\.tooltip': 881073,
        r'unreadColumn\.tooltip': 881073,
        r'totalColumn\.tooltip': 881073,
        r'readColumn\.tooltip': 881073,
        r'receivedColumn\.tooltip': 881073,
        r'flagColumn\.tooltip': 881073,
        r'starredColumn\.tooltip': 881073,
        r'locationColumn\.tooltip': 881073,
        r'idColumn\.tooltip': 881073,
        r'phishingOptionDisableDetection\.label': 926473,
        r'phishingOptionDisableDetection\.accesskey': 926473,
        r'contextEditAsNew\.label': 956481,
        r'contextEditAsNew\.accesskey': 956481,
        r'EditContact\.label': 956481,
        r'EditContact\.accesskey': 956481,
        r'choosethisnewsserver\.label': 878805,
        r'moveHereMenu\.label': 878805,
        r'moveHereMenu\.accesskey': 878805,
        r'newfolderchoosethis\.label': 878805,
        r'thisFolder\.label': 878805,
        r'thisFolder\.accesskey': 878805,
        r'fileHereMenu\.label': 878805,
        r'fileHereMenu\.accesskey': 878805,
        r'copyHereMenu\.label': 878805,
        r'copyHereMenu\.accesskey': 878805,
        r'autoCheck\.label': 958850,
        r'enableAppUpdate\.label': 958850,
        r'enableAppUpdate\.accesskey': 958850,
        r'enableAddonsUpdate\.label': 958850,
        r'enableAddonsUpdate\.accesskey': 958850,
        r'whenUpdatesFound\.label': 958850,
        r'modeAskMe\.label': 958850,
        r'modeAskMe\.accesskey': 958850,
        r'modeAutomatic\.label': 958850,
        r'modeAutomatic\.accesskey': 958850,
        r'modeAutoAddonWarn\.label': 958850,
        r'modeAutoAddonWarn\.accesskey': 958850,
        r'showUpdates\.label': 958850,
        r'showUpdates\.accesskey': 958850,
        r'update\.checkInsideButton\.label': 707489,
        r'update\.checkInsideButton\.accesskey': 707489,
        r'update\.resumeButton\.label': 707489,
        r'update\.resumeButton\.accesskey': 707489,
        r'update\.openUpdateUI\.applyButton\.label': 707489,
        r'update\.openUpdateUI\.applyButton\.accesskey': 707489,
        r'update\.restart\.updateButton\.label': 707489,
        r'update\.restart\.updateButton\.accesskey': 707489,
        r'update\.restart\.restartButton\.label': 707489,
        r'update\.restart\.restartButton\.accesskey': 707489,
        r'update\.openUpdateUI\.upgradeButton\.label': 707489,
        r'update\.openUpdateUI\.upgradeButton\.accesskey': 707489,
        r'update\.restart\.upgradeButton\.label': 707489,
        r'update\.restart\.upgradeButton\.accesskey': 707489,
        r'command\.invite': 920801,
        r'ctcp\.ping': 957918,
        r'vkontakte\.usernameHint': 957918,
        r'dateformat': 544315})),
])

TB29_JS_ENTITIES = [
    {'name': 'DisablePhishingWarning',
     'status': '', 'bug': 926473, 'compat_type': 'error'},
    {'name': 'RoomInfo',
     'status': '', 'bug': 920801, 'compat_type': 'error'},
    {'name': 'FillInHTMLTooltip',
     'status': '', 'bug': 956586, 'compat_type': 'error'},
    {'name': 'escapeXMLchars',
     'status': '', 'bug': 942638, 'compat_type': 'error'},
    {'name': 'gPluginHandler.isTooSmall',
     'status': 'removed', 'bug': 951800, 'compat_type': 'error'},
    {'name': 'XMPPSession.authDialog',
     'status': 'removed', 'bug': 920801, 'compat_type': 'error'},
    {'name': 'XMPPMUCConversation.supportChatStateNotifications',
     'status': 'removed', 'bug': 920801, 'compat_type': 'error'},
    {'name': 'Socket.inputSegmentSize',
     'status': 'removed', 'bug': 920801, 'compat_type': 'error'},
    {'name': 'XMPPMUCConversationPrototype.normalizedName',
     'status': 'removed', 'bug': 957918, 'compat_type': 'error'},
    {'name': 'XMPPAccountBuddyPrototype.normalizedName',
     'status': 'removed', 'bug': 957918, 'compat_type': 'error'},
    {'name': 'XMPPAccountPrototype.normalizedName',
     'status': 'removed', 'bug': 957918, 'compat_type': 'error'},
    {'name': 'GenericAccountPrototype.maxMessageLength',
     'status': 'removed', 'bug': 954484, 'compat_type': 'error'},
    {'name': 'mailTabType.desiredColumnStates',
     'status': 'removed', 'bug': 528044, 'compat_type': 'error'},
]
register_changed_entities(version_definition=TB29_DEFINITION,
                          entities=TB29_JS_ENTITIES,
                          version_string='Thunderbird 29')
