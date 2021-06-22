import json
import reip
import numpy as np


class NumpyWriter(reip.Block):
    def __init__(self, filename_template="%d", verbose=False, **kw):
        self.filename_template = filename_template
        self.verbose = verbose
        self.id = 0

        super().__init__(**kw)

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        assert(type(xs[0]) == np.ndarray)

        filename, self.id = self.filename_template % self.id, self.id + 1
        if self.verbose:
            print(xs[0].shape, filename)

        with open(filename + ".npy", "wb") as f:
            np.save(f, xs[0])
        
        if meta is not None:
            meta["id"] = self.id - 1
            if self.verbose:
                print(meta)

            with open(filename + ".json", "w") as f:
                json.dump(dict(meta), f, indent=4)

        return [filename], meta


class NumpyReader(reip.Block):
    def __init__(self, filename_template="%d", verbose=False, **kw):
        self.filename_template = filename_template
        self.verbose = verbose
        self.id = 0

        super().__init__(**kw)

    def process(self, *xs, meta=None):
        filename, self.id = self.filename_template % self.id, self.id + 1
        if self.verbose:
            print(filename)

        with open(filename + ".npy", "rb") as f:
            data = np.load(f)

        with open(filename + ".json", "r") as f:
            meta = json.load(f)
            meta["id"] = self.id - 1

        return [data], meta


if __name__ == '__main__':
    w = NumpyWriter(filename_template="test/%d", verbose=True)

    ret = w.process(np.zeros((1000, 1000)), meta={"meta": "test"})

    print(ret)

    r = NumpyReader(filename_template="test/%d", verbose=True)

    print(r.process([]))
