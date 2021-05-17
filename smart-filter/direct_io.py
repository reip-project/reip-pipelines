import os
import time
import mmap
import json
import reip
import directio  # comment if not using this method
import numpy as np
from numpy_io import NumpyEncoder


class DirectWriter(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    filename_template = "%d"  # Numbered based on number of input buffers
    bundle = None  # Budle multiple buffers into a single file
    method = "directio"  # Writing method: mmap or directio (faster)

    def init(self):
        assert(self.method in ["mmap", "directio"])

        self.file_id, self.buffer_id = 0, 0
        self.f, self.mm, self.metas = None, None, None

    def create_file(self, buffer_size):
        filename = self.filename_template % self.file_id + ".dio"
        self.f = os.open(filename, os.O_CREAT | os.O_DIRECT | os.O_RDWR)
        sz = buffer_size * (self.bundle or 1)
        os.ftruncate(self.f, sz)
        if self.method == "mmap":
            self.mm = mmap.mmap(self.f, sz, offset=0, access=mmap.ACCESS_WRITE)
        self.metas = [None] * self.bundle if self.bundle else None
        self.buffer_id = 0

        if self.debug:
            print("Direct_Writer created file:", filename)

    def write_buffer(self, buffer, meta):
        assert(self.f is not None)
        assert(isinstance(buffer, np.ndarray))

        t0 = time.time()

        if self.method == "mmap":
            self.mm.write(buffer)
        else:
            directio.write(self.f, buffer)

        dt = time.time() - t0

        if self.debug:
            print("Direct_Writer wrote buffer %d: %d bytes at %f MB/s" %
                    (self.buffer_id, buffer.nbytes, buffer.nbytes / dt / 1024**2))

        full_meta = {"meta": dict(meta),
                    "shape": buffer.shape,
                    "dtype": np.dtype(buffer.dtype).name,
                    "size": buffer.nbytes}

        if self.bundle:
            self.metas[self.buffer_id] = full_meta
        else:
            self.metas = full_meta

        self.buffer_id += 1

    def finish_file(self):
        if self.f:
            os.close(self.f)

            filename = self.filename_template % self.file_id + ".json"
            with open(filename, "w") as f:
                if self.bundle:
                    self.metas = {"buffer_" + str(i): m for i, m in enumerate(self.metas)}

                self.metas["file_id"] = self.file_id
                self.metas["bundle"] = self.bundle
                self.metas["n_buffers"] = self.buffer_id
                json.dump(self.metas, f, indent=4, cls=NumpyEncoder)

            if self.debug:
                print("Direct_Writer finished file:", filename)

        elif self.debug:
            print("Direct_Writer: No file to finish!")

        ret = [self.filename_template % (self.file_id)], self.metas
        self.f, self.mm, self.metas = None, None, None
        self.file_id += 1
        return ret

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        assert(type(xs[0]) == np.ndarray)

        if self.f is None:
            self.create_file(xs[0].nbytes)

        self.write_buffer(xs[0], meta)

        if self.buffer_id == (self.bundle or 1):
            return self.finish_file()
        else:
            return None

    def finish(self):
        if self.f:
            self.finish_file()


class DirectReader(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    filename_template = None  # Numbered sequentially or based on int input if not None
    method = "mmap"  # Writing method: mmap (faster) or directio

    def init(self):
        assert(self.method in ["mmap", "directio"])

    def process(self, *xs, meta=None):
        assert(len(xs) == 1 or self.filename_template)

        if len(xs) == 1:
            if type(xs[0]) == str:
                filename = xs[0]
            elif type(xs[0]) == int and self.filename_template:
                filename = self.filename_template % xs[0]
            else:
                raise RuntimeError("Direct_Reader: Invalid input!")
        elif len(xs) > 1:
            raise RuntimeError("Direct_Reader: To many inputs!")
        else:
            filename = self.filename_template % self.processed

        if self.debug:
            print("Direct_Reader filename:", filename)

        with open(filename + ".json", "r") as f:
            metas = json.load(f)
            bundle, n_buffers = metas["bundle"], metas["n_buffers"]

            shape, dtype, size = [metas["buffer_0"][name] if bundle else metas[name]
                                    for name in ["shape", "dtype", "size"]]
            if bundle:
                meta = [metas["buffer_%d" % i]["meta"] for i in range(n_buffers)]
            else:
                meta = metas["meta"]

            if self.debug and self.verbose:
                print("Direct_Reader " + ("%d/%d bundle:" % (n_buffers, bundle) if bundle \
                        else "single:"), shape, dtype, "(%d bytes)" % size)

        t0 = time.time()
        f = os.open(filename + ".dio", os.O_CREAT | os.O_DIRECT | os.O_RDWR)

        mm = mmap.mmap(f, size * (bundle or 1), offset=0, access=mmap.ACCESS_WRITE) \
                                                            if self.method == "mmap" else None
        def read_buffer():
            return mm.read(size) if self.method == "mmap" else directio.read(f, size)

        if bundle:
            data = [np.frombuffer(read_buffer(), dtype).reshape(shape) for i in range(n_buffers)]
        else:
            data = np.frombuffer(read_buffer(), dtype).reshape(shape)

        os.close(f)        
        dt = time.time() - t0

        if self.debug:
            print("Direct_Reader read: %d buffers at %f MB/s" %
                    (n_buffers, size * n_buffers / dt / 1024**2))

        return [data], meta
    

if __name__ == '__main__':
    from dummies import Generator, BlackHole

    g = Generator(name="Generator", size=(4, 1024, 1280), dtype=np.uint8, inc=False, max_rate=50)
    w = DirectWriter(name="Writer", filename_template="test_data/%d",
                        bundle=30, debug=True, verbose=True)
    g.to(w).to(BlackHole(name="Black_Hole", debug=False))

    reip.default_graph().run(duration=3)

    g.max_rate = 0
    w.bundle = None

    # reip.default_graph().run(duration=1)

    # r = DirectReader(name="reader", filename_template="test_data/%d", debug=True, verbose=True)
    # b = r.process()
    # print(b)
