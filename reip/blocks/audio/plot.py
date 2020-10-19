import os
import reip
import matplotlib
matplotlib.use('agg')
import librosa.display
import matplotlib.pyplot as plt


class Specshow(reip.Block):
    def __init__(self, filename='{time}.png', figsize=(12, 6), cmap='magma', **kw):
        self.filename = filename
        self.figsize = figsize
        self.cmap = cmap
        self.kw = kw
        super().__init__()

    def process(self, X, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # plot
        plt.figure(figsize=self.figsize)
        librosa.display.specshow(X, cmap=self.cmap, **self.kw)
        plt.savefig(fname)
        return [fname], meta
