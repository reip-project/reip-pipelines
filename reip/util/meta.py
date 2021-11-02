import copy

class Meta(dict):
    '''A metadata object. It combines a dictionary with metadata from earlier inputs.

    This has two attributes 
        - meta.data: a dictionary containing the values for this layer
        - meta.inputs: a list of meta/dicts that represents the metadata 
            from previous blocks
    
    The Meta object itself subclasses a dictionary which contains a flatten version
    of meta.data and meta.inputs. Modifications to the meta object are applied to both
    the flattened version and the data object. 

    Arguments:
        data (dict, None): The current data dictionary.
        *inputs (dict): The input dictionaries to inherit.
        deep_access (bool): Should the meta object access values from the input dictionaries?
        masked_keys (set): Any keys to ignore from the input dictionaries. Unused currently,
            but might be necessary to track deleted keys and pass them to 
    '''
    def __init__(self, data=None, *inputs, deep_access=True, masked_keys=None):
        # the current layer of data - a dict
        self.data = data = data if data is not None else {}
        # this meta object inputs - a list of meta objects
        self.inputs = list(inputs)
        self._deep_access = deep_access
        self._masked_keys = set(masked_keys or ())
        super().__init__(self._compile_dict())

    def _compile_dict(self):
        merged = {}
        if self._deep_access:
            for d in self.inputs[::-1]:
                merged.update(d)
            for k in self._masked_keys:
                merged.pop(k, None)
        merged.update(self.data)
        return merged

    def _compile(self):
        return self.clear().update(self._compile_dict())

    def __str__(self):
        return 'Meta({}, [{}])'.format(self.data, ', '.join(map(str, self.inputs)))

    def __getitem__(self, k):
        if isinstance(k, (int, slice)):
            return self.inputs[k]
        return super().__getitem__(k)

    def __setitem__(self, k, v):
        if isinstance(k, (int, slice)):
            self.inputs[k] = v
            return
        self.data[k] = v
        return super().__setitem__(k, v)

    def __delitem__(self, k):
        if isinstance(k, (int, slice)):
            del self.inputs[k]
        if k in self.data:
            del self.data[k]
        return super().__delitem__(k)

    def __or__(self, other):
        return self.copy().update(other)

    def __ior__(self, other):
        return self.update(other)

    def clear(self):
        self.data.clear()
        super().clear()
        return self

    def update(self, *a, **kw):
        if a and not hasattr(a[0], '__len__'): # handle generators
            a = (dict(a[0]),)
        self.data.update(*a, **kw)
        super().update(*a, **kw)
        return self

    def setdefault(self, k, v=None):
        if k not in self:
            self[k] = v
        return self[k]

    def pop(self, k, *default):
        self.data.pop(k, None)
        return super().pop(k, *default)

    def copy(self):
        m = copy.copy(self)
        m.data = m.data.copy()
        return m

    @classmethod
    def as_meta(cls, d):
        if not isinstance(d, cls):
            if isinstance(d, Meta):
                return cls(d, *d.inputs)
            return cls(d)
        return d

    def append(self, *inputs):
        self.inputs.extend(inputs)
        self._compile()
        return self

    def extend(self, inputs):
        self.inputs.extend(inputs)
        self._compile()
        return self


class ImmutableMeta(Meta):
    def __setitem__(self, k, v):
        raise TypeError
    def __delitem__(self, k):
        raise TypeError
    def update(self, *a, **kw):
        raise TypeError
    def setdefault(self, k, v=None):
        raise TypeError
    def append(self, *inputs):
        raise TypeError
    def extend(self, inputs):
        raise TypeError