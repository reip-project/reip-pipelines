from collections import ChainMap


class Meta(ChainMap):
    '''Merged metadata dict stacks into one. Removes duplicates and empty maps.
    The original input maps can be accessed using `[d for d in stack.sources]`
    '''
    def __init__(self, *maps, filter=False):
        super().__init__(*ordered_unique(flatten_maps(*maps, filter=filter)))
        self.sources = maps

    def update(self, *a, **kw):
        super().update(*a, **kw)
        return self


def flatten_maps(*metas, filter=False):
    '''Flatten nested chain maps.'''
    for m in metas:
        if isinstance(m, ChainMap):
            yield from flatten_maps(*m.maps, filter=filter)
        elif not filter or m:
            yield m


def ordered_unique(maps):
    '''Remove duplicate maps (may happen due to branching+merging).'''
    ids = set()
    for m in maps:
        i = repr(m)
        if i not in ids:
            ids.add(i)
            yield m
