from validator.constants import BUGZILLA_BUG, MDN_DOC
from validator.testcases.regex.compat import COMPAT_REGEXPS

from . import build_definition


FX38_DEFINITION = build_definition(38, firefox=True)

COMPAT_REGEXPS.append(
    (FX38_DEFINITION, (
        (r'\bmozIndexedDB\b',
         {'warning': 'mozIndexedDB has been removed.',
          'description': 'mozIndexedDB has been removed. You should use '
                         'indexedDB instead. '
                         'See %s for more information.'
                         % BUGZILLA_BUG % 975699}),

        (r'\b(?:nsICompositionStringSynthesizer|sendCompositionEvent|'
         r'createCompositionStringSynthesizer)\b',

         {'warning': 'nsICompositionStringSynthesizer, '
                     'sendCompositionEvent, and '
                     'createCompositionStringSynthesizer were removed.',

          'description': (
              'The nsICompositionStringSynthesizer interface and the '
              'sendCompositionEvent and createCompositionStringSynthesizer '
              'functions have been removed. See %s for more information.'
              % MDN_DOC
              % ('Mozilla/Tech/XPCOM/Reference/Interface/'
                 'nsITextInputProcessor')),
          }),

        (r'\b(?:newChannel2|asyncFetch2)\b',
         {'warning': 'asyncFetch2 and newChannel2 are now deprecated.',
          'description': 'asyncFetch2 and newChannel2 are now deprecated. '
                         'Use asyncFetch or newChannel instead. See %s for '
                         'more information.' % BUGZILLA_BUG % 1125618,
          'compatibility_type': 'warning'}),

        (r'\b(onProxyAvailable|asyncResolve)\b',
         {'warning': 'The onProxyAvailable and asyncResolve functions have '
                     'changed.',
          'description': 'They now take an nsIChannel instead of an nsIURI '
                         'as an argument. '
                         'See %s for more information.'
                         % BUGZILLA_BUG % 436344}),
    )),
)
