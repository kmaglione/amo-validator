from validator.constants import BUGZILLA_BUG, MDN_DOC
from validator.testcases.regex.compat import COMPAT_REGEXPS

from . import build_definition


FX39_DEFINITION = build_definition(39, firefox=True)

COMPAT_REGEXPS.append(
    (FX39_DEFINITION, (
        (r'\b__noSuchMethod__\b',
         {'warning': 'The __noSuchMethod__ property has been deprecated.',
          'description': (
              'The __noSuchMethod__ property has been deprecated. See %s for '
              'more information.'
              % MDN_DOC % ('Web/JavaScript/Reference/Global_Objects/Object/'
                           'noSuchMethod')),
          'compatibility_type': 'warning'}),

        (r'\bsendAsBinary\b',
         {'warning': 'The function sendAsBinary() in XMLHttpRequest has been '
                     'removed.',
          'description': (
              'The function sendAsBinary() in XMLHttpRequest has been '
              'removed. You can use send() with a Blob instead. '
              'See %s for more information.' % BUGZILLA_BUG % 853162)}),

        (r'\blightweightThemes\.(usedThemes|isThemeSelected)\b',
         {'warning': 'The preferences used to store theme selection have '
                     'changed.',
          'description': 'The preferences used to store theme selection have '
                         'changed. See %s#c39 for more information.'
                         % BUGZILLA_BUG % 1094821}),
    )),
)
