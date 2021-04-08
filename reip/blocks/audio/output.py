import os
import soundfile
import reip


class AudioFile(reip.Block):
    def __init__(self, filename='{time}.wav', **kw):
        self.filename = filename
        super().__init__(extra_kw=True, **kw) #extra_kw=True,

    def process(self, X, meta):
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname) or '.', exist_ok=True)
        soundfile.write(fname, X, meta['sr'], **self.extra_kw)
        return [fname], meta
