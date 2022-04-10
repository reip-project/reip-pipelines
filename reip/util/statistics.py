import collections
import numpy as np


class OnlineStats:
    '''Online statistics - calculate and update mean and variance as new data comes in.'''
    count = mean = _var = 0
    def __init__(self, history=0):
        self.last = 0
        self.samples = collections.deque(maxlen=history) if history else None

    def __getstate__(self):  # don't copy samples when pickling
        return dict(self.__dict__, samples=None)

    def __str__(self):
        return '(total = {total:.4f} avg = {mean:.6f} ± {std:.6f}, n = {count:8,})\n'.format(
            total=self.sum, mean=self.mean, std=self.std, count=self.count)

    def __len__(self):
        return self.count

    def append(self, x):
        '''Append a value to the rolling mean.'''
        # online mean
        # online std deviation
        last_mean, self.mean = self.mean, (self.mean * self.count + x) / (self.count + 1)
        if self.count:
            self._var = self._var + (x - last_mean) * (x - self.mean)

        self.last = x
        self.count += 1
        if self.samples is not None:
            self.samples.append(x)

    def extend(self, xs):
        '''Append multiple values.'''
        for x in xs:
            self.append(x)

    @property
    def sum(self):
        '''Get the rolling sum.'''
        return self.mean * self.count

    @property
    def std(self):
        '''Get the rolling standard deviation.'''
        return np.sqrt(self.var)

    @property
    def var(self):
        '''Get the rolling variance.'''
        return self._var / (self.count - 1) if self.count > 1 else 0
