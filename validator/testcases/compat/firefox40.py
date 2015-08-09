from validator.constants import BUGZILLA_BUG, MDN_DOC
from validator.testcases.regex.compat import COMPAT_REGEXPS
from validator.testcases.javascript.predefinedentities import GLOBAL_ENTITIES

from . import build_definition


FX40_DEFINITION = build_definition(40, firefox=True)

COMPAT_REGEXPS.append(
    (FX40_DEFINITION, (
        (r'\b([gs]etKeywordForBookmark|getURIForKeyword)\b',
         {'warning': 'The old keywords API is deprecated.',
          'description': (
            'The old keywords API is deprecated. You should use '
            'PlacesUtils.keywords instead. See %s for more information.'
            % MDN_DOC % 'Mozilla/Tech/Places/Using_the_Places_keywords_API'),
          'compatibility_type': 'warning'}),

        (r'\b(fuelIApplication|extIApplication)\b',
         {'warning': 'The FUEL library is now deprecated.',
          'description': (
            'The FUEL library is now deprecated. You should use the add-ons '
            'SDK or Services.jsm. See %s for more information.'
            % MDN_DOC % 'Mozilla/Tech/Toolkit_API/FUEL'),
          'compatibility_type': 'warning'}),

        (r'\bresource://gre/modules/Dict.jsm\b',
         {'warning': 'The Dict.jsm module has been removed.',
          'description': (
            'The Dict.jsm module has been removed. You can use the native Map '
            'object instead. See %s for more information.'
            % MDN_DOC % 'Web/JavaScript/Reference/Global_Objects/Map'),
          'compatibility_type': 'error'}),

        (r'\bsessionstore-state-write\b',
         {'warning': "The \"sessionstore-state-write\" notification has been "
                     'removed.',
          'description': (
            "The \"sessionstore-state-write\" notification has been removed. "
            'See %s for more information.' % BUGZILLA_BUG % 1157235),
          'compatibility_type': 'error'}),

        (r'\bnsISSLErrorListener\b',
         {'warning': 'The nsISSLErrorListener interface has been removed.',
          'description': (
            'The nsISSLErrorListener interface has been removed. See %s for '
            'more information.' % BUGZILLA_BUG % 844351),
          'compatibility_type': 'error'}),

        (r"""require\(['"]sdk/widget['"]\)""",
         {'warning': 'The widget module has been removed.',
          'description': (
            'The widget module has been removed. You can use ActionButton or '
            'ToggleButton instead. See %s for more information.'
            % 'https://developer.mozilla.org/en-US/Add-ons/SDK/'
              'High-Level_APIs/widget'),
          'compatibility_type': 'error'}),
    )),
)


def fuel_error(traverse_node, err):
    traverse_node.im_self.warning(
        err_id=('js', 'traverser', 'dangerous_global'),
        warning='The FUEL library is now deprecated.',
        description='The FUEL library is now deprecated. You should use the '
                    'add-ons SDK or Services.jsm. See %s for more information.'
                    % MDN_DOC % 'Mozilla/Tech/Toolkit_API/FUEL',
        for_appversions=FX40_DEFINITION,
        tier=5,
        compatibility_type='warning')

GLOBAL_ENTITIES[u'Application'] = {'dangerous_on_read': fuel_error}
