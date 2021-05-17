import json
import os.path
import reip
import time
import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class NumpyWriter(reip.Block):
    debug = False  # Print debug if True
    filename_template="%d"  # Filename template with integer %d strting at 0 by default
    file_id = 0  # Starting & current file ID

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        if xs[0] is not None:
            assert(type(xs[0]) == np.ndarray)

        if xs[0] is None and meta is None:
            return None

        filename = self.filename_template % self.file_id
        reip.util.ensure_dir(filename)

        if self.debug:
            print("Numpy_Writer filename:", filename, xs[0].shape if xs[0] is not None else None, meta)

        if xs[0] is not None:
            with open(filename + ".npy", "wb") as f:
                np.save(f, xs[0])
        
        if meta is not None:
            meta["file_id"] = self.file_id

            with open(filename + ".json", "w") as f:
                json.dump(dict(meta), f, indent=4, cls=NumpyEncoder)

        self.file_id += 1
        return [filename], meta


class NumpyReader(reip.Block):
    debug = False  # Print debug if True
    verbose = False  # Print verbose debug if True
    mmap = False  # TODO: mmap if True instead or reading and making a copy
    filename_template="%d"  # Filename template with integer %d strting at 0 by default
    file_id = 0  # Starting & current file ID

    def process(self, *xs, meta=None):
        filename = self.filename_template % self.file_id

        if os.path.exists(filename + ".npy"):
            with open(filename + ".npy", "rb") as f:
                # data = np.load(f, mmap=self.mmap)  # Not supported
                data = np.load(f)
        else:
            data = None

        if os.path.exists(filename + ".json"):
            with open(filename + ".json", "r") as f:
                meta = json.load(f)
                meta["file_id"] = self.file_id
        else:
            meta = {}

        self.file_id += 1

        if data is None and meta is None:
            if self.debug and self.verbose:
                print("Numpy_Reader missing:", filename)
            return None
        else:
            if self.debug:
                print("Numpy_Reader filename:", filename)
            return [data], meta


if __name__ == '__main__':
    w = NumpyWriter(filename_template="test_data/%d", debug=True, verbose=True)

    d = np.zeros((10, 1000, 1000), dtype=np.uint8)
    t0 = time.time()
    for i in range(10):
        print(w.process(d, meta={"meta": "test"}))
    print(time.time() - t0)
    print(w.process(None, meta={"meta": "test"}))

    r = NumpyReader(filename_template="test_data/%d", debug=True, verbose=True)

    for i in range(3):
        print(r.process([]))
