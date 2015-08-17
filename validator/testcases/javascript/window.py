"""Contains definitions which pertain to DOM window scopes, including XUL
browser windows."""
from __future__ import absolute_import, print_function, unicode_literals

from .jstypes import Global, Hook


@Global.hook
class document(Hook):
    title = {'overwritable': True}

    defaultView = {'value': lambda traverser: traverser.global_}


@Global.extend
class window(Hook):
    window = {'value': lambda traverser: traverser.global_}

    top = window

    opener = {'value': lambda traverser: traverser.wrap(hooks=Global)}

    width = {'overwritable': True}
    height = {'overwritable': True}

    innerWidth = {'overwritable': True}
    innerHeight = {'overwritable': True}


@Global.hook
class navigator(Hook):
    geolocation = {'on_get': True}
    wifi = {'on_get': True}


@Global.extend
class BrowserWindow(Hook):
    class gBrowser(Hook):
        contentDocument = {'value': lambda traverser: (
            traverser.global_['content']['document'])}

        contentWindow = {'value': lambda traverser: (
            traverser.global_['content'])}

        selectedTab = {'overwritable': True}

    class content(Hook):
        class Meta:
            scope = 'content'
            inherit = {'scope'}

        document = Global['properties']['document']

    _content = {'value': lambda traverser: traverser.global_['content'],
                'on_get': ('The `content_` global is deprecated, and should '
                           'not be accessed. Please use `content` instead.')}
