import multiprocessing as mp


class Counter:
    def __init__(self, initial=0):
        self.value = initial

    def as_basic(self):
        return Counter(self.value)

    def as_shared(self):
        return SharedCounter(self.value)

class SharedCounter:
    def __init__(self, initial=0):
        self._value = mp.Value('i', initial, lock=False)
        super().__init__(initial)

    @property
    def value(self):
        return self._value.value

    @value.setter
    def value(self, new_value):
        self._value.value = new_value


class Pointer:
    def __init__(self, size, counter=0):
        self.counter = counter
        self.size = size

    def __str__(self):
        return (
            f'<{self.__class__.__name__} i={self.counter} '
            f'pos={self.pos}/{self.size - 1} loop={self.loop}>')

    @property
    def pos(self):
        return self.counter % self.size

    @property
    def loop(self):
        return self.counter // self.size

    def as_basic(self):
        return Pointer(self.size, self.counter)

    def as_shared(self):
        return SharedPointer(self.size, self.counter)


class SharedPointer(Pointer):
    def __init__(self, size, counter=0):
        self._counter = mp.Value('i', counter, lock=False)
        super().__init__(size, counter)

    @property
    def counter(self):
        return self._counter.value

    @counter.setter
    def counter(self, new_value):
        self._counter.value = new_value
