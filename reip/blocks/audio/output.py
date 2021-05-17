import os
import soundfile
import reip
# import time


class AudioFile(reip.Block):
    def __init__(self, filename='{time}.wav'):
        self.filename = filename
        super().__init__()

    def process(self, X, meta):
        # meta["time"] = time.time()
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        soundfile.write(fname, X, meta['sr'])
        return [fname], meta
