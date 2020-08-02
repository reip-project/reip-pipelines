import numpy as np
import librosa
import reip


class ExampleAudio(reip.Block):
    y = sr = None
    def __init__(self, window=3, **kw):
        self.window = window
        super().__init__(**kw)

    def init(self):
        self.y, self.sr = librosa.load(librosa.util.example_audio_file())

    def process(self, meta=None):
        i = np.random.randint(len(self.y) - self.window * self.sr)
        y = self.y[i:i + self.window * self.sr]
        return [y], {
            'sr': self.sr,
            'offset': i / self.sr,
            'window': self.window
        }

    def finish(self):
        self.y = self.sr = None
