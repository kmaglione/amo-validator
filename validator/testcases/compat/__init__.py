from validator.decorator import version_range
from validator.constants import (FIREFOX_GUID, FENNEC_GUID,
                                 THUNDERBIRD_GUID as TB_GUID, ANDROID_GUID)


# Compatibility app/version ranges:

def build_definition(maj_version_num, firefox=False, fennec=False,
                     thunderbird=False, android=False):
    definition = {}
    app_version_range = (
        lambda app: version_range(app, '%d.0a1' % maj_version_num,
                                       '%d.0a1' % (maj_version_num + 1)))
    if firefox:
        definition[FIREFOX_GUID] = app_version_range('firefox')
    if fennec:
        definition[FENNEC_GUID] = app_version_range('fennec')
    if thunderbird:
        definition[TB_GUID] = app_version_range('thunderbird')
    if android:
        definition[ANDROID_GUID] = app_version_range('android')

    return definition
