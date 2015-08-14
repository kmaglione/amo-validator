"""Tests which relate specifically to bootstrapped add-ons, primarily use
of APIs which require explicit cleanup."""

from .predefinedentities import INTERFACES, hook_global, hook_interface


def if_bootstrapped(msg):
    def dangerous(this, args, callee):
        if this.traverser.err.get_resource('em:bootstrap'):
            return msg
    return dangerous


def if_jetpack(msg):
    def dangerous(this, args, callee):
        if this.traverser.err.metadata.get('is_jetpack'):
            return msg
    return dangerous


hook_interface(('nsIComponentRegistrar', 'autoRegister'),
               dangerous=if_bootstrapped(
                   'Bootstrapped add-ons may not register chrome '
                   'manifest files.'))

hook_interface(('nsIComponentRegistrar', 'registerFactory'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care to '
                   'clean up any component registrations at shutdown.'))

hook_interface(('nsIObserverService',),
               dangerous=if_jetpack(
                   'The observer service should not be used directly in '
                   "SDK add-ons. Please use the 'sdk/system/events' "
                   'module instead.'))

hook_interface(('nsIObserverService', 'addObserver'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care '
                   'to remove any added observers '
                   'at shutdown.'))


def setSubstitution(this, args, callee):
    if this.traverser.err.get_resource('em:bootstrap'):
        if len(args) > 1 and args[1].as_bool():
            return ('Authors of bootstrapped add-ons must take care '
                    'to clean up any added resource substitutions '
                    'at shutdown.')

hook_interface(('nsIResProtocolHandler', 'setSubstitution'),
               dangerous=setSubstitution)

hook_interface(('nsIStringBundleService', 'createStringBundle'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care '
                   'to flush the string bundle cache at shutdown.'))

hook_interface(('nsIStringBundleService', 'createExtensibleBundle'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care '
                   'to flush the string bundle cache at shutdown.'))

hook_interface(('nsIStyleSheetService', 'loadAndRegisterSheet'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care to '
                   'unregister registered stylesheets at shutdown.'))

hook_interface(('nsIWindowMediator', 'registerNotification'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care '
                   'to remove any added observers at shutdown.'))

hook_interface(('nsIWindowWatcher', 'addListener'),
               dangerous=if_bootstrapped(
                   'Authors of bootstrapped add-ons must take care '
                   'to remove any added observers at shutdown.'))


def addCategoryEntry(this, args, callee):
    if this.traverser.err.get_resource('em:bootstrap'):
        if len(args) > 3 and args[3].as_bool():
            return ('Bootstrapped add-ons may not create persistent category '
                    'entries.')
        else:
            return ('Authors of bootstrapped add-ons must take care to clean '
                    'up any added category entries at shutdown.')

hook_interface(('nsICategoryManager', 'addCategoryEntry'),
               dangerous=addCategoryEntry)

hook_global(('XPCOMUtils', 'categoryManager'),
            value=lambda traverser: INTERFACES['nsICategoryManager'])
