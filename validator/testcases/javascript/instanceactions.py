"""
Prototype
---------

args
    the raw list of arguments
traverser
    the traverser
node
    the current node being evaluated
"""


def addEventListener(this, args, callee):
    """
    Handle calls to addEventListener and make sure that the fourth argument is
    falsey.
    """

    if len(args) > 3 and args[3].as_bool():
        this.traverser.notice(
            err_id=('js', 'instanceactions', 'addEventListener_fourth'),
            notice='`addEventListener` called with truthy fourth argument.',
            description='When called with a truthy forth argument, listeners '
                        'can be triggered potentially unsafely by untrusted '
                        'code. This requires careful review.')


def createElement(this, args, callee):
    """Handles createElement calls"""

    if not args:
        return

    name = args[0]
    if name.as_str().lower() == u'script':
        _create_script_tag(this.traverser)
    elif not name.is_clean_literal():
        _create_variable_element(this.traverser)


def createElementNS(this, args, callee):
    """Handles createElementNS calls"""

    if len(args) < 2:
        return

    name = args[1]
    if 'script' in name.as_str().lower():
        _create_script_tag(this.traverser)
    elif not name.is_clean_literal():
        _create_variable_element(this.traverser)


def QueryInterface(this, args, callee):
    """Handles QueryInterface calls"""

    if args:
        from call_definitions import xpcom_constructor
        return xpcom_constructor('QueryInterface', True, True)(
            this, args, callee)


def getInterface(this, args, callee):
    """Handles getInterface calls"""

    # This really only needs to be handled for nsIInterfaceRequestor
    # intarfaces, but as it's fair for code to assume that that
    # interface has already been queried and methods with this name
    # are unlikely to behave differently, we just process it for all
    # objects.

    if args:
        from call_definitions import xpcom_constructor
        return xpcom_constructor('getInterface')(
            this, args, callee)


def _create_script_tag(traverser):
    """Raises a warning that the dev is creating a script tag"""
    traverser.warning(
        err_id=('testcases_javascript_instanceactions', '_call_expression',
                'called_createelement'),
        warning='createElement() used to create script tag',
        description='Dynamic creation of script nodes can be unsafe if '
                    'contents are not static or are otherwise unsafe, '
                    'or if `src` is remote.',
        signing_help='Please avoid using <script> tags to load scripts. '
                     'For potential alternatives, please see '
                     'https://developer.mozilla.org/en-US/Add-ons/'
                     'Overlay_Extensions/XUL_School/'
                     'Appendix_D:_Loading_Scripts',
        signing_severity='medium')


def _create_variable_element(traverser):
    """Raises a warning that the dev is creating an arbitrary element"""
    traverser.warning(
        err_id=('testcases_javascript_instanceactions', '_call_expression',
                'createelement_variable'),
        warning='Variable element type being created',
        description=('createElement or createElementNS were used with a '
                     'variable rather than a raw string. Literal values '
                     'should be used when taking advantage of the element '
                     'creation functions.',
                     "E.g.: createElement('foo') rather than "
                     'createElement(el_type)'))


def setAttribute(this, args, callee):
    """This ensures that setAttribute calls don't set on* attributes"""

    if not args:
        return

    name = args[0]
    if name.as_str().lower().startswith('on'):
        this.traverser.warning(
            err_id=('testcases_javascript_instanceactions', 'setAttribute',
                    'setting_on*'),
            warning='on* attribute being set using setAttribute',
            description='To prevent vulnerabilities, event handlers (like '
                        "'onclick' and 'onhover') should always be defined "
                        'using addEventListener.',
            signing_help='Please use `addEventListener` any place you might '
                         'otherwise create event listener attributes. Event '
                         'listener attributes will not be accepted in add-ons '
                         'submitted for automated signing in any instance '
                         'where they may be reasonably avoided.',
            signing_severity='medium')


def launch(this, args, callee):
    this.traverser.warning(
        err_id=('testcases_javascript_instanceactions', 'launch'),
        warning='Potentially dangerous use of `launch()`',
        description='Use of the `nsIFile.launch()` method can be dangerous, '
                    'and requires careful review.',
        editors_only=True)


def openDialog(this, args, callee):
    """Raise an error if the first argument is a remote URL."""
    if args:
        from call_definitions import open_in_chrome_context
        open_in_chrome_context(args[0], 'openDialog', this.traverser)


def bind(this, args, callee):
    if this.callable:
        return this


INSTANCE_DEFINITIONS = {
    'addEventListener': addEventListener,
    'bind': bind,
    'createElement': createElement,
    'createElementNS': createElementNS,
    'getInterface': getInterface,
    'launch': launch,
    'openDialog': openDialog,
    'QueryInterface': QueryInterface,
    'setAttribute': setAttribute,
}
