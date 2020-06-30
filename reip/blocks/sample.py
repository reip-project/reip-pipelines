'''Sampling data from block input.


'''

import random
from .block import Block


class sample(Block):
    '''Sample files from the '''


class even(Block):
    '''Sample files evenly.'''
    def __init__(self, n=None, start=0, stop=None, step=None, **kw):
        self.start, self.stop, self.step = start, stop, step
        self.n = n
        super().__init__(**kw)

    def transform(self, X, meta):
        step = self.step or (int(len(X) / self.n) if self.n else None)
        return X[
            self.start or None:
            self.stop or None:
            step or None][:self.n or None]


class random(Block):
    '''Sample files randomly.'''
    def __init__(self, n, **kw):
        super().__init__(**kw)
        self.n = n

    def transform(self, X, meta):
        return random.sample(X, self.n)


sample.even = even
sample.random = random
