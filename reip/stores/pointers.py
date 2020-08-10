import multiprocessing as mp


class Pointer:
    same_context = True
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

    @property
    def store_id(self):
        return self.same_context

    def as_basic(self):
        return Pointer(self.size, self.counter)

    def as_shared(self):
        return SharedPointer(self.size, self.counter)


class SharedPointer(Pointer):
    same_context = False
    def __init__(self, size, counter=0):
        self._counter = mp.Value('i', counter, lock=False)
        super().__init__(size, counter)

    @property
    def counter(self):
        return self._counter.value

    @counter.setter
    def counter(self, new_value):
        self._counter.value = new_value
