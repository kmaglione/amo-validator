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


def addEventListener(args, traverser, node, wrapper):
    """
    Handle calls to addEventListener and make sure that the fourth argument is
    falsey.
    """

    if not args or len(args) < 4:
        return

    fourth_arg = traverser._traverse_node(args[3])
    if fourth_arg.get_literal_value():
        traverser.err.notice(
            err_id=('js', 'instanceactions', 'addEventListener_fourth'),
            notice='`addEventListener` called with truthy fourth argument.',
            description='When called with a truthy forth argument, listeners '
                        'can be triggered potentially unsafely by untrusted '
                        'code. This requires careful review.',
            filename=traverser.filename,
            line=traverser.line,
            column=traverser.position,
            context=traverser.context)


def createElement(args, traverser, node, wrapper):
    """Handles createElement calls"""

    if not args:
        return

    args = map(traverser._traverse_node, args)

    name = args[0]
    if name.as_str().lower() == u'script':
        _create_script_tag(traverser)
    elif not name.is_clean_literal():
        _create_variable_element(traverser)


def createElementNS(args, traverser, node, wrapper):
    """Handles createElementNS calls"""

    if not args or len(args) < 2:
        return

    args = map(traverser._traverse_node, args)

    name = args[1]
    if 'script' in name.as_str().lower():
        _create_script_tag(traverser)
    elif not name.is_clean_literal():
        _create_variable_element(traverser)


def QueryInterface(args, traverser, node, wrapper):
    """Handles QueryInterface calls"""

    if not args:
        return

    from call_definitions import xpcom_constructor
    return xpcom_constructor('QueryInterface', True, True)(
        wrapper=node,
        arguments=args,
        traverser=traverser)


def getInterface(args, traverser, node, wrapper):
    """Handles getInterface calls"""

    # This really only needs to be handled for nsIInterfaceRequestor
    # intarfaces, but as it's fair for code to assume that that
    # interface has already been queried and methods with this name
    # are unlikely to behave differently, we just process it for all
    # objects.

    if not args:
        return

    from call_definitions import xpcom_constructor
    return xpcom_constructor('getInterface')(
        wrapper=node,
        arguments=args,
        traverser=traverser)


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


def setAttribute(args, traverser, node, wrapper):
    """This ensures that setAttribute calls don't set on* attributes"""

    if not args:
        return

    args = map(traverser._traverse_node, args)

    name = args[0]
    if name.as_str().lower().startswith('on'):
        traverser.warning(
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


def launch(args, traverser, node, wrapper):
    traverser.warning(
        err_id=('testcases_javascript_instanceactions', 'launch'),
        warning='Potentially dangerous use of `launch()`',
        description='Use of the `nsIFile.launch()` method can be dangerous, '
                    'and requires careful review.',
        editors_only=True)


def openDialog(args, traverser, node, wrapper):
    """Raise an error if the first argument is a remote URL."""
    if not args:
        return
    uri = traverser._traverse_node(args[0])
    from call_definitions import open_in_chrome_context
    open_in_chrome_context(uri, 'openDialog', traverser)


def bind(args, traverser, node, wrapper):
    if 'callee' not in node and 'object' not in node['callee']:
        return
    obj = traverser._traverse_node(node['callee']['object'])
    if obj.callable:
        return obj


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
