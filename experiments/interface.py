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


class Sink:
    def __init__(self):
        self.dropped = 0

    def full(self):
        raise NotImplementedError

    def _put(self, buffer):
        raise NotImplementedError

    def put(self, buffer, **kw):
        if self.full():
            self.dropped += 1
        else:
            self._put(buffer)

    def gen_source(self, **kw):
        raise NotImplementedError


class Source:
    All = 0
    Latest = 1
    Skip = 2

    def __init__(self, strategy=0, skip=0):
        self.strategy = strategy
        self.skip = skip
        self._skip_id = 0
        self.skipped = 0

    def empty(self):
        raise NotImplementedError

    def last(self):
        raise NotImplementedError

    def next(self):
        raise NotImplementedError

    def _get(self):
        raise NotImplementedError

    def get(self, **kw):
        if self.empty():
            return None

        buffer = None

        if self.strategy == Source.Skip:
            while not self.empty() and self._skip_id < self.skip:
                # self._get()
                self.next()  # discard the buffer
                self._skip_id += 1
                self.skipped += 1

            if self._skip_id == self.skip:
                if not self.empty():
                    buffer = self._get()
                    self._skip_id = 0  # might not process this buffer in multi_source block

        elif self.strategy == Source.Latest:
            while not self.last():
                # self._get()
                self.next()  # discard the buffer
                self.skipped += 1

            buffer = self._get()

        elif self.strategy == Source.All:
            if not self.empty():
                buffer = self._get()
        else:
            raise ValueError("Unknown strategy")

        return buffer
