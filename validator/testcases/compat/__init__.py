from ..javascript.jstypes import Global, Interfaces
from validator.decorator import version_range
from validator.constants import (ANDROID_GUID, BUGZILLA_BUG, FENNEC_GUID,
                                 FIREFOX_GUID, THUNDERBIRD_GUID)


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
        definition[THUNDERBIRD_GUID] = app_version_range('thunderbird')
    if android:
        definition[ANDROID_GUID] = app_version_range('android')

    return definition


def register_entity(name):
    """Allow an entity's modifier to be registered for use."""
    def wrap(func):
        if name.startswith('nsI'):
            Interfaces.hook(name.split('.'), on_call=func)
        else:
            Global.hook(name.split('.'), on_call=func)
        return func
    return wrap


def deprecated_entity(name, version, message, bug, status='deprecated',
                      compat_type='error'):
    def wrap(this, value, name=None):
        this.traverser.warning(
            err_id=('js', 'entities', name),
            warning='`%s` has been %s.' % (name, status),
            description=(message,
                         'See %s for more information.' % BUGZILLA_BUG % bug),
            for_appversions=version,
            compatibility_type=compat_type,
            tier=5)

    if name.startswith('nsI'):
        Interfaces.hook(name.split('.'), on_get=wrap)
    else:
        Global.hook(name.split('.'), on_get=wrap)


def register_changed_entities(version_definition, entities, version_string):
    for entity in entities:
        deprecated_entity(
            name=entity['name'],
            version=version_definition,
            message='The method or property `%s` has been `%s` in `%s`.'
                    % (entity['name'], entity['status'], version_string),
            bug=entity['bug'],
            compat_type=entity['compat_type'])
