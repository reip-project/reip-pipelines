# import gc
import time
import reip
import numpy as np


class Bundle(reip.Block):
    def __init__(self, size=2, debug=False, verbose=False, **kw):
        self.size = size
        self.debug = debug
        self.verbose = verbose
        self.buffer_id, self.bundle_id = 0, -1
        self.shape, self.dtype = None, None
        self.meta_only = None
        self.bundle = None
        self.metas = None

        super().__init__(**kw)

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        # once detected meta_only, cannot go back
        if self.meta_only is None:
            self.meta_only = xs[0] is None

            if self.debug and self.meta_only:
                    print("Bundle inferred:", "meta_only")

        if self.meta_only:
            if self.debug and self.verbose:
                print("Bundle meta_only:", meta)
        else:
            assert isinstance(xs[0], np.ndarray), 'expected numpy array. Got type {} value={}'.format(type(xs[0]), xs[0])
            #assert(type(xs[0]) == np.ndarray)

            if self.debug and self.verbose:
                print("Bundle buffer:", xs[0].shape, xs[0].dtype, meta)

            if self.shape is None or self.dtype is None:
                self.shape = (self.size, *xs[0].shape)
                self.dtype = np.dtype(xs[0].dtype)

                if self.debug:
                    print("Bundle inferred:", self.shape, self.dtype)

        if self.metas is None or self.buffer_id == 0:
            self.metas = [None] * self.size
            self.bundle_id += 1

            if not self.meta_only:
                self.bundle = np.zeros(self.shape, self.dtype)

            if self.debug:
                print("Bundle new_id = %d:" % self.bundle_id, self.shape, self.dtype, self.meta_only)
        
        self.metas[self.buffer_id] = dict(meta)

        if not self.meta_only:
            self.bundle[self.buffer_id, ...] = xs[0]

        self.buffer_id = (self.buffer_id + 1) % self.size

        if self.buffer_id == 0:
            new_meta = {"buffer_" + str(i): m for i, m in enumerate(self.metas)}
            new_meta["bundle_id"] = self.bundle_id

            if self.debug:
                print("Bundle returning:", new_meta)

            return [None if self.meta_only else self.bundle], new_meta
        else:
            return None
            # return [reip.NEXT], None

    def finish(self):
        self.bundle = None


class BundleCam(reip.Block):
    debug = False  # Print debug info if True
    verbose = False  # Print extra debug info if True
    bundle = None  # Don't bundle frames if None
    zero_copy = False  # Reuse the same frames buffer if True (bundle mode only)

    def __init__(self, **kw):
        super().__init__(n_inputs=0, **kw)

    def init(self):
        self.bundle_reset()

        if self.debug and self.verbose:
            print("BundleCam: Inited")

    def bundle_reset(self):
        self.frame_id, self.bundle_id = 0, -1
        self.frames, self.metas = None, None

    def new_bundle(self, shape):
        if self.frames is None:
            self.frames = np.zeros(shape, np.uint8)
        self.metas = [None] * self.bundle
        self.bundle_id += 1

        if self.debug:
            print("New bundle %d:" % self.bundle_id, self.frames.shape)

    def get_buffer(self):
        raise NotImplementedError("BundleCam: Implement get_buffer() and return (buffer, meta)")

    def process(self, *xs, meta=None):
        buffer, meta = self.get_buffer()

        if buffer is not None:
            if self.bundle:
                ret, idx  = None, self.frame_id % self.bundle

                if self.metas is None:
                    self.new_bundle((self.bundle, *buffer.shape))

                # with self._sw("copy"):
                # t = time.time()
                self.frames[idx, ...] = buffer
                # print("copy time:", time.time() - t)
                meta["frame_id"] = self.frame_id
                # meta["bundle_id"] = self.bundle_id
                self.metas[idx] = meta
                self.frame_id += 1

                if idx == self.bundle-1:
                    ret = ([self.frames],
                           {"buffer_" + str(i): m for i, m in enumerate(self.metas)})

                    ret[1]["bundle_id"] = self.bundle_id
                    ret[1]["n_buffers"] = self.bundle

                    if self.debug and self.verbose:
                        print("Outputting bundle:\n" + "\n".join([str(m) for m in self.metas]))

                    self.metas = None
                    if not self.zero_copy:
                        self.frames = None

                return ret
            else:
                meta["frame_id"] = self.frame_id
                self.frame_id += 1

                if self.debug and self.verbose:
                    print("Outputting single:", meta)

                return [buffer], meta
        else:
            if self.debug: # and self.verbose:
                print("BundleCam: Got empty buffer!")

            return None

    def finish(self):
        self.bundle_reset()

        if self.debug and self.verbose:
            print("BundleCam: Finished")


def test_memory_speed():
    # sz, n = 1024**2, 1000
    sz, n = 8 * 1024 * 1280, 1000

    a = np.zeros((10, 1024, 1280), dtype=np.uint8)
    b = np.ones((1024, 1280), dtype=np.uint8)
    # a = np.zeros(10 * sz, dtype=np.uint8)
    # b = np.ones(sz, dtype=np.uint8)
    print(b.dtype)

    ma = memoryview(a)
    mb = memoryview(b)

    t = time.time()

    for i in range(n):
        # a[i % 10, ...] = b
        # off = sz * (i % 10)
        # a[off:off+sz] = b
        # ma[off:off+sz] = mb
        b = np.zeros((8, 1024, 1280), dtype=np.uint8)

    print((time.time() - t) / n, "sec per", sz / 1024**2, "MB")
    print(sz * n / (time.time() - t) / 1024**2, "MB/s")
    exit()


if __name__ == '__main__':
    # test_memory_speed()

    g = Bundle(size=2, debug=True, verbose=True)

    for i in range(4):
        print(g.process(np.zeros((1000)), meta={"test_input": i+1}))
        # print(g.process(None, meta={"test_input": i+1}))
