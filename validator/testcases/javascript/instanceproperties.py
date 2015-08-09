import types

import jstypes


def set_on_event(new_value, traverser):
    """Ensure that on* properties are not assigned string values."""

    is_literal = new_value.is_literal()

    if (is_literal and
            isinstance(new_value.get_literal_value(), types.StringTypes)):
        traverser.warning(
            err_id=('testcases_javascript_instancetypes', 'set_on_event',
                    'on*_str_assignment'),
            warning='on* property being assigned string',
            description='Event handlers in JavaScript should not be '
                        'assigned by setting an on* property to a '
                        'string of JS code. Rather, consider using '
                        'addEventListener.',
            signing_help='Please add event listeners using the '
                         '`addEventListener` API. If the property you are '
                         'assigning to is not an event listener, please '
                         'consider renaming it, if at all possible.',
            signing_severity='medium')
    elif (not is_literal and isinstance(new_value.value, jstypes.JSObject) and
          'handleEvent' in new_value.value.data):
        traverser.warning(
            err_id=('js', 'on*', 'handleEvent'),
            warning='`handleEvent` no longer implemented in Gecko 18.',
            description='As of Gecko 18, objects with `handleEvent` methods '
                        'may no longer be assigned to `on*` properties. Doing '
                        'so will be equivalent to assigning `null` to the '
                        'property.')


OBJECT_DEFINITIONS = {}


def get_operation(mode, prop):
    """
    This returns the object definition function for a particular property
    or mode. mode should either be 'set' or 'get'.
    """

    if prop in OBJECT_DEFINITIONS and mode in OBJECT_DEFINITIONS[prop]:
        return OBJECT_DEFINITIONS[prop][mode]

    elif mode == 'set' and unicode(prop).startswith('on'):
        # We can't match all of them manually, so grab all the "on*" properties
        # and funnel them through the set_on_event function.

        return set_on_event
