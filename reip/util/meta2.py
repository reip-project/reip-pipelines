import collections

class Meta(collections.abc.MutableMapping):
    '''A traceable history of metadata.
     - should have its own single top-level dict
     - should have a list of metadata that were given as inputs.
     - Should be traceable back to the first input in the chain
    
    I thought about making the input layers immutable, but I haven't thought of 
    a good enough reason to enforce it.
    inputs: []
    mine: {'a': 5, 'time': 112341.232342}
    '''
    def __init__(self, data=None, inputs=None):
        # the current layer of data - a dict
        self.data = data if data is not None else {}
        # this meta object inputs - a list of meta objects
        self.inputs = (
            (list(inputs) if isinstance(inputs, tuple) else inputs) 
            if inputs is not None else [])
        for i, meta in enumerate(self.inputs):  # coerce to meta class
            if not isinstance(meta, Meta):
                self.inputs[i] = Meta(meta)
        # we don't want to actually delete keys from 
        self.deleted_keys = set()

    def __repr__(self):
        return 'Meta({}, [{} inputs])'.format(repr(self.data), len(self.inputs))

    def __len__(self):
        return len(set(self.keys()))

    def __bool__(self):
        return bool(self.data) or any(bool(m) for m in self.inputs)

    # general dict operators

    def __contains__(self, key):
        return key in self.data or any(key in m for m in nearfirst(*self.inputs))

    def __getitem__(self, key):
        # for int keys, get the n-th input meta data
        # meta[2] - get the third input meta
        if isinstance(key, (int, slice)):
            return self.inputs[key]

        # allow basic numpy-style multi-axis keys
        # meta[0, 1, 'time'] - get the first input of the zero-th input - then get the time key from it
        if isinstance(key, tuple):
            meta = self
            for k in key:
                meta = meta[k]
            return meta

        # meta['time'] - find the first value
        if key in self.data:
            return self.data[key]
        # check earlier layers
        if key not in self.deleted_keys:
            for meta in nearfirst(*self.inputs):
                if key in meta:
                    return meta[key]
        return self.__missing__(key)

    def __setitem__(self, key, value):
        # all modifications happen on the top layer
        self.data[key] = value
        self.deleted_keys.discard(key)  # if it was, key isn't deleted anymore

    def __delitem__(self, key):
        try:  # all modifications happen on the top layer
            del self.data[key]
        except KeyError:  # mark key as deleted so we don't go checking previous layers
            pass
        finally:
            self.deleted_keys.add(key)

    def __iter__(self):
        yield from (k for k, v in _metaitems(self))

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __missing__(self, key):
        raise KeyError(key)

    # expanding the meta object

    def update(self, *a, **kw):
        self.data.update(*a, **kw)
        # this isn't totally needed (we check self.data before checking this)
        # but it's just good record keeping
        self.deleted_keys.difference_update(self.data)
        return self

    def append(self, meta):
        '''Add an input meta.'''
        self.inputs.append(meta if isinstance(meta, Meta) else Meta(meta))

    def extend(self, metas):
        '''Add multiple input metas.'''
        self.inputs.extend((m if isinstance(m, Meta) else Meta(m) for m in metas))


    # meta navigation helpers

    def depths(self):
        '''Iterate over each layer.'''
        return depths(self)

    def nearfirst(self):
        return nearfirst(self)

    def deepfirst(self):
        '''Iterate over the meta history left to right (going up the chain of inputs). 
        Basically, prioritizing the "first" input of each block.'''
        return deepfirst(self)

    def find_key(self, key):
        '''Find the first map that contains that key.'''
        for meta in nearfirst(self):
            if key in meta:
                return meta

    def scrub_key(self, key):
        '''Delete a key from all metas in the meta history.'''
        for meta in nearfirst(self):
            if key in meta:
                del meta[key]
        return self

    # general dict methods

    def keys(self):
        return _MetaKeysView(self)
    
    def values(self):
        return _MetaValuesView(self)

    def items(self):
        return _MetaItemsView(self)


class _MetaItemsView(collections.abc.ItemsView):
    def __iter__(self):
        yield from _metaitems(self._mapping)

class _MetaKeysView(collections.abc.KeysView):
    def __iter__(self):
        yield from (k for k, v in _metaitems(self._mapping))

class _MetaValuesView(collections.abc.ValuesView):
    def __iter__(self):
        yield from (v for k, v in _metaitems(self._mapping))


def _metaitems(meta):
    seen = set(meta.deleted_keys)  # so we don't return those
    for meta in nearfirst(meta):
        for k, v in meta.items():
            if k not in seen:
                seen.add(k)
                yield k, v



def depths(*metas):
    '''Iterate over each depth in our metadata tree (layer first, not recursive).
    
    An example (audio -> {spl,classifications,embeddings} -> csv):
    yields each layer
     - [csv(1)] (1)
     - [spl(2), embeddings(3), classifications(4)] (2)
     - [audio(5)] (3)
    '''
    seen = set()
    while metas:
        yield [m.data for m in metas]
        metas = list(_prune_dups((mi for m in metas for mi in m.inputs), seen))


def nearfirst(*metas):
    '''Iterate over each depth in order in our metadata tree. Iterate over my inputs, then all of theirs, and so on.'''
    seen = set()
    while metas:
        yield from (m.data for m in metas)
        metas = list(_prune_dups((mi for m in metas for mi in m.inputs), seen))


def deepfirst(*metas, seen=None):
    '''Iterate through metadata by prioritizing metadata in the first index of each set of inputs.
    It will start at the most recent meta and move back in time and move along the input 
    branches. 
    An example (audio -> {spl,classifications,embeddings} -> csv):
    yields a flat iterable
     - [csv(1)]
     - [spl(2), embeddings(4), classifications(5)]
     - [audio(3)]
    '''
    seen = set() if seen is None else seen
    for meta in metas:
        k = id(meta)
        if k not in seen:
            seen.add(k)
            yield meta.data
            yield from deepfirst(*meta.inputs, seen=seen)


def _prune_dups(items, seen=None):
    '''Remove duplicates from a list based on identity.'''
    seen = set() if seen is None else seen
    for d in items:
        k = id(d)
        if k not in seen:
            seen.add(k)
            yield d
