import reip
import numpy as np

class MotionDetector(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    do_hist = True # Compute histogram of differences if True
    sel = 0  # Input selection
    inner_sw = None

    def __init__(self, n_inputs=None, **kw):
        # enable variable number of sources
        super().__init__(n_inputs=n_inputs, source_strategy=all, **kw)

    def init(self):
        self.n_in = len(self.sources) or 1
        self.inner_sw = reip.util.Stopwatch("inner")

        self.refs, self.metas = [None] * self.n_in, [None] * self.n_in

    def process(self, *xs, meta=None):
        assert(len(xs) == self.n_in)
        # print(xs, type(meta), meta)
        if self.n_in == 1:
            meta = [dict(meta)]
        
        self.sel = (self.sel + 1) % self.n_in
        sel = self.sel
        x, meta = xs[sel], dict(meta[sel])
        pixel_format = meta["pixel_format"].lower()

        if type(x) != np.ndarray:
            if self.debug:
                print("MotionDetector: No data on desired input (%d)" % self.sel)
            return None

        if pixel_format == "i420":
            x = x[:x.shape[0] * 2 // 3]
            x = x.reshape(meta["resolution"])
        
        if self.refs[sel] is None:
            # self.refs[sel] = x.astype(np.int)
            self.refs[sel] = np.right_shift(x, 1) + 128
            self.metas[sel] = meta
            return None
        else:
            diff = self.refs[sel] - np.right_shift(x, 1)#.astype(np.uint8)
            # diff = np.abs(x//2 + 128 - self.refs[sel]//2)#.astype(np.uint8)
            # print(diff.dtype)
            self.refs[sel] = None

            if self.do_hist:
                hist = np.bincount(diff.ravel())
                # hist = np.histogram(diff.ravel(), bins=256, range=(-0.5,255.5))
            else:
                hist = None

            return [diff], {"hist": hist, "sel": sel, "source_meta_before": self.metas[sel], "source_meta_after": meta}
    