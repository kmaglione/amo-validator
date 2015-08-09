"""
Loads all modules which register testcases, in an order which prevents import
loops.
"""
# flake8: noqa

from .testcases import (chromemanifest, content, installrdf, jetpack,
                        l10ncompleteness, langpack, packagelayout,
                        targetapplication, themes)
from .testcases.javascript import (bootstrapped, customization, obsolete,
                                   performance, preferences, security,
                                   security_xss)
from .testcases.compat import (firefox38, firefox39, firefox40,
                               thunderbird29, thunderbird30, thunderbird31)
from . import decorator


decorator.do_post_init()
