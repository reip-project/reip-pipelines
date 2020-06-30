'''Data Filtering Blocks




'''

from fnmatch import fnmatch as fnm_
import numpy as np
from .block import Block




class filter(Block):
    def __init__(self, x, **kw):
        super().__init__(**kw)
        self.x_pattern = x

    def match(self, x, pattern):
        return pattern(x) if callable(pattern) else x == pattern

    def transform(self, X, meta):
        if self.x_pattern:
            X = [x for x in X if self.match(x, self.x_pattern)]
        if not all(self.match(meta[k], v) for k, v in self.kw.items()):
            return None
        return X, meta


class fnmatch(Block):
    def __init__(self, x, **kw):
        super().__init__(**kw)
        self.x_pattern = x

    def match(self, x, pattern):
        return fnm_(x, pattern)
