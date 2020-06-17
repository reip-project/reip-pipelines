'''
String Template Utilities
=========================


'''
import jinja2

env = jinja2.Environment()

class templated:
    '''An object property that evaluates values as jinja strings.

    Example:
        >>> class MyBlock(reip.Block):
        ...     filename = reip.templated('default/path_{{ timestamp }}.txt')
        ...     def __init__(self, filename=None):
        ...         self.filename = filename

        ...     def transform(self, data):
        ...         fname = self.filename # rendered with timestamp
        ...         with open(fname, 'w') as f:
        ...             f.write(data)
        ...         return fname
    '''
    VALUE = None
    def __init__(self, func=None, default=..., set_none=False):
        if not callable(func):
            default, func = func, None
        self.default = (default,) if default != ... else ()
        self.set_none = set_none

        self.func = func or (lambda x: x)
        self.id = id(func)



    def objid(self, obj):
        return '_tpl{}_{}'.format(id(obj), self.id)

    def __get__(self, obj, owner):

        return env.from_string(getattr(obj, self.objid(obj), *self.default)).render()
    def __set__(self, obj, value):
        if self.set_none or value is not None:
            setattr(obj, self.objid(obj), value)
