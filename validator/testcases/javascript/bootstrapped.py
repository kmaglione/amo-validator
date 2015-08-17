"""Tests which relate specifically to bootstrapped add-ons, primarily use
of APIs which require explicit cleanup."""

from __future__ import absolute_import, print_function, unicode_literals

from .jstypes import Global, Hook, Interfaces


def if_bootstrapped(traverser):
    return bool(traverser.err.get_resource('em:bootstrap'))


def if_jetpack(traverser):
    return traverser.err.metadata.get('is_jetpack')


@Global.hook('Components', 'on_get')
def get_Components(this, value, name=None):
    if if_jetpack(this.traverser):
        return ('The `Components` global may not be accessed directly from '
                'SDK modules. If you cannot avoid using XPCOM, please do '
                'so via `require("chrome")` instead.')


@Interfaces.extend
class CleanupInterfaces(Hook):

    class nsIComponentRegistrar(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def autoRegister(this, args, callee):
            return ('Bootstrapped add-ons may not register chrome manifest '
                    'files.')

        @Hook.on_call(scope_filter=if_bootstrapped)
        def registerFactory(this, args, callee):
            return ('Authors of bootstrapped add-ons must take care to '
                    'clean up any component registrations at shutdown.')

    class nsIObserverService(Hook):

        @Hook.on_get
        def __self__(this, value, name=None):
            if if_jetpack(this.traverser):
                return ('The observer service should not be used directly in '
                        "SDK add-ons. Please use the 'sdk/system/events' "
                        'module instead.'),

        @Hook.on_call(scope_filter=if_bootstrapped)
        def addObserver(this, args, callee):
            return ('Authors of bootstrapped add-ons must take care to remove '
                    'any added observers at shutdown.')

    class nsIResProtocolHandler(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def setSubstitution(this, args, callee):
            if len(args) > 1 and args[1].as_bool():
                return ('Authors of bootstrapped add-ons must take care '
                        'to clean up any added resource substitutions '
                        'at shutdown.')

    class nsIStringBundleService(Hook):
        createStringBundle = {
            'scope_filter': if_bootstrapped,
            'on_call': ('Authors of bootstrapped add-ons must take care '
                        'to flush the string bundle cache at shutdown.'),
        }

        createExtensibleBundle = createStringBundle

    class nsIStyleSheetService(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def loadAndRegisterSheet(this, args, callee):
            return ('Authors of bootstrapped add-ons must take care to '
                    'unregister registered stylesheets at shutdown.')

    class nsIWindowMediator(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def registerNotification(this, args, callee):
            return ('Authors of bootstrapped add-ons must take care '
                    'to remove any added observers at shutdown.')

    class nsIWindowWatcher(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def addListener(this, args, callee):
            return ('Authors of bootstrapped add-ons must take care '
                    'to remove any added observers at shutdown.')

    class nsICategoryManager(Hook):

        @Hook.on_call(scope_filter=if_bootstrapped)
        def addCategoryEntry(this, args, callee):
            if len(args) > 3 and args[3].as_bool():
                return ('Bootstrapped add-ons may not create persistent '
                        'category entries.')
            else:
                return ('Authors of bootstrapped add-ons must take care to '
                        'clean up any added category entries at shutdown.')


@Global.hook
class XPCOMUtils(Hook):

    @Hook.value
    def categoryManager(traverser):
        return traverser.wrap().query_interface('nsICategoryManager')
