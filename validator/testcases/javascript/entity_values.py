from validator.constants import BUGZILLA_BUG
from .predefinedentities import hook_global, hook_interface


def register_entity(name):
    """Allow an entity's modifier to be registered for use."""
    def wrap(func):
        def return_wrap(t):
            output = func(traverser=t)

            if output is not None:
                return output
            else:
                return {'value': {}}

        if name.startswith('nsI'):
            hook_interface(name.split('.'), value=return_wrap)
        else:
            hook_global(name.split('.'), value=return_wrap)
        return func
    return wrap


def deprecated_entity(name, version, message, bug, status='deprecated',
                      compat_type='error'):
    def wrap(traverser):
        traverser.warning(
            err_id=('js', 'entities', name),
            warning='`%s` has been %s.' % (name, status),
            description=(message,
                         'See %s for more information.' % BUGZILLA_BUG % bug),
            for_appversions=version,
            compatibility_type=compat_type,
            tier=5)
    register_entity(name)(wrap)


def register_changed_entities(version_definition, entities, version_string):
    for entity in entities:
        deprecated_entity(
            name=entity['name'],
            version=version_definition,
            message='The method or property `%s` has been `%s` in `%s`.'
                    % (entity['name'], entity['status'], version_string),
            bug=entity['bug'],
            compat_type=entity['compat_type'])


@register_entity('nsIWindowWatcher.openWindow')
def nsIWindowWatcher_openWindow(traverser):
    def on_open(wrapper, arguments, traverser):
        if not arguments:
            return
        uri = traverser._traverse_node(arguments[0])

        from call_definitions import open_in_chrome_context
        open_in_chrome_context(uri, 'nsIWindowWatcher.openWindow', traverser)

    return {'return': on_open}


@register_entity('nsITransferable.init')
def nsITransferable_init(traverser):
    def on_init(wrapper, arguments, traverser):
        if not arguments:
            return
        first_arg = traverser._traverse_node(arguments[0])
        if first_arg.get_literal_value():
            return
        traverser.warning(
            err_id=('js_entity_values', 'nsITransferable', 'init'),
            warning='`init` should not be called with a null first argument',
            description='Calling `nsITransferable.init()` with a null first '
                        'argument has the potential to leak data across '
                        'private browsing mode sessions. `null` is  '
                        'appropriate only when reading data or writing data '
                        'which is not associated with a particular window.')

    return {'return': on_init}
