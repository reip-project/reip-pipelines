import numpy as np
from collections import deque


class Queue(deque):
    def __init__(self, callback, size=1):
        self.callback = callback
        self.emit_size = size

    @property
    def size(self):
        return len(self)

    def append(self, item):
        super().append(item)
        if self.size > self.emit_size:
            self.emit()

    def emit(self):
        self.callback(list(self))


class ChainQueue(Queue):
    def __init__(self, callback, size=1, item_dims=2):
        self.sizes = {}
        self.q_size = size
        self.item_dims = item_dims
        super().__init__(callback, size)

    @property
    def size(self):
        return

    def append(self, item):
        sizes = {
            k: len(v) if isinstance(v, np.ndarray) and len(v.shape) > 1 else 1
            for k, v in item.items()
        }

        for k in item:
            self.sizes[k] = self.sizes.get(k, 0) + len(item[k])
        super().append(item)

    def emit(self):
        self.callback(list(self))

    def clear(self):
        super().clear()
        self.sizes = {k: 0 for k in self.sizes}
