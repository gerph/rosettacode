"""
Functions for manipulating JSON.

json_iterable + json_encode allow the serialisation of objects which contain the
`__jsonencode__` method. If called, this should return a serialisable object (simple
python objects).

write_json will use those functions to write out a JSON file.
"""

import json


def json_encode(obj):
    """
    Encoding function to use for objects which are not known to the standard JSON encoder.

    If the object contains a property '__jsonencode__', it is called to obtain the representation
    of the object.
    """

    def jsonspecial_datetime(obj):  # pylint: disable=unused-variable
        return obj.isoformat()

    if hasattr(obj, '__jsonencode__'):
        return obj.__jsonencode__()

    special_name = 'jsonspecial_%s' % (obj.__class__.__name__,)
    special_func = locals().get(special_name, None)
    if special_func:
        return special_func(obj)

    raise TypeError("Cannot serialise a '%s' object: %r" % (obj.__class__.__name__, obj))


def json_iterable(obj, pretty=False):
    if pretty:
        return json.JSONEncoder(default=json_encode,
                                sort_keys=True,
                                indent=2,
                                separators=(',', ': ')).iterencode(obj)
    else:
        return json.JSONEncoder(default=json_encode).iterencode(obj)


def write_json(filename, obj, pretty=False):
    with open(filename, 'w') as fh:
        for chunk in json_iterable(obj, pretty=pretty):
            fh.write(chunk)


