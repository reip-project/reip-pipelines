import time
from abc import ABC, abstractmethod
from collections import Mapping
import numpy as np


def asimmutable(buffer):
    data, meta = buffer
    if isinstance(data, np.ndarray):
        data.flags.writeable = False
    return data, ImmutableDict(meta)


class ImmutableDict(Mapping):

    def __init__(self, data):
        self._data = data

    def __repr__(self):
        return repr(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)



def skip_strategy(source):
    while not source.empty() and source._skip_id < source.skip:
        source._get()
        source.next()  # discard the buffer
        source._skip_id += 1
        source.skipped += 1

    if source._skip_id == source.skip and not source.empty():
        buffer = source._get()
        source._skip_id = 0  # might not process this buffer in multi_source block
        return buffer

def latest_strategy(source):
    while not source.last():
        source._get()
        source.next()  # discard the buffer
        source.skipped += 1
    return source._get()

def all_strategy(source):
    if not source.empty():
        return source._get()



class Sink(ABC):
    def __init__(self):
        self.dropped = 0
        self._full_delay = 1e-6

    @abstractmethod
    def full(self):
        raise NotImplementedError

    @abstractmethod
    def _put(self, buffer):
        raise NotImplementedError

    def wait(self, timeout=None):
        t0 = time.time()
        while self.full():
            time.sleep(self._full_delay)
            if timeout and time.time() - t0 > timeout:
                return None  # QUESTION: TimeoutError instead?

    def put(self, buffer, **kw):
        if self.full():
            self.dropped += 1
        else:
            self._put(buffer)

    @abstractmethod
    def gen_source(self, **kw):
        raise NotImplementedError


class Source(ABC):
    All = 0
    Latest = 1
    Skip = 2

    strategies = {
        All: all_strategy,
        Latest: latest_strategy,
        Skip: skip_strategy,
    }

    def __init__(self, strategy=All, skip=0):
        self.strategy = strategy
        self.skip = skip
        self._skip_id = 0
        self.skipped = 0
        self._empty_delay = 1e-6

    @property
    def strategy(self):
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        if strategy not in self.strategies:
            raise ValueError("Unknown strategy '{}'".format(strategy))

        self._strategy = strategy
        self._strategy_get = self.strategies[strategy].__get__(self)

    @abstractmethod
    def empty(self):
        raise NotImplementedError

    @abstractmethod
    def last(self):
        raise NotImplementedError

    @abstractmethod
    def next(self):
        raise NotImplementedError

    @abstractmethod
    def _get(self):
        raise NotImplementedError

    def wait(self, timeout=None):
        t0 = time.time()
        while self.empty():
            time.sleep(self._empty_delay)
            if timeout and time.time() - t0 > timeout:
                return None  # QUESTION: TimeoutError instead?

    def get(self, block=True, timeout=None, **kw):
        if block:
            self.wait(timeout)
        elif self.empty():
            return None
        return self._strategy_get()
