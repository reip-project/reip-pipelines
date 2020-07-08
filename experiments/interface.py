from abc import ABC, abstractmethod
from collections import Mapping


class ImmutableDict(Mapping):

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)


class Sink(ABC):
    def __init__(self):
        self._dropped = 0

    @abstractmethod
    def full(self):
        raise NotImplementedError

    @abstractmethod
    def _put(self, buffer):
        raise NotImplementedError

    def put(self, buffer, **kw):
        if self.full():
            self._dropped += 1
        else:
            self._put(buffer)

    @abstractmethod
    def gen_source(self, **kw):
        raise NotImplementedError


class Source(ABC):
    All = 0
    Latest = 1
    Skip = 2

    def __init__(self, strategy=0, skip=0):
        self.strategy = strategy
        self.skip = skip
        self._skipped = 0
        self._skipped_total = 0

    @abstractmethod
    def empty(self):
        raise NotImplementedError

    @abstractmethod
    def last(self):
        raise NotImplementedError

    @abstractmethod
    def _next(self):
        raise NotImplementedError

    @abstractmethod
    def _get(self):
        raise NotImplementedError

    def get(self, **kw):
        if self.empty():
            return None

        buffer = None

        if self.strategy == Source.Skip:
            while not self.empty() and self._skipped < self.skip:
                self._get()
                self._next()  # discard the buffer
                self._skipped += 1
                self._skipped_total += 1

            if self._skipped == self.skip:
                if not self.empty():
                    buffer = self._get()
                    self._skipped = 0

        elif self.strategy == Source.Latest:
            while not self.last():
                self._get()
                self._next()  # discard the buffer
                self._skipped_total += 1

            buffer = self._get()

        elif self.strategy == Source.All:
            if not self.empty():
                buffer = self._get()
        else:
            raise ValueError("Unknown strategy")

        return buffer

    def done(self):
        self._next()
