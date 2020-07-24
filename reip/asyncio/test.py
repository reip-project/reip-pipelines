import os
import time

import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt

import reip.asyncio.core as reip

reip.init()


######################
# Custom Blocks
######################


class Interval(reip.Block):
    '''Call this function every X seconds'''
    def __init__(self, seconds=2, **kw):
        self.seconds = seconds
        super().__init__(n_source=0, **kw)

    def process(self, meta=None):
        time.sleep(self.seconds)
        meta['time'] = time.time()
        print(meta['time'])
        return (), {'time': time.time()}


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


class Sleep(reip.Block):
    def __init__(self, sleep=2, **kw):
        self.sleep = sleep
        super().__init__(**kw)

    def process(self, *ys, meta):
        time.sleep(self.sleep)
        return ys, meta


class Stft(reip.Block):
    def __init__(self, **kw):
        self.kw = kw
        super().__init__()

    def process(self, y, meta):
        S = librosa.amplitude_to_db(np.abs(librosa.stft(y, **self.kw)))
        return [S], meta


class Debug(reip.Block):
    def __init__(self, message='Debug', **kw):
        self.message = message
        super().__init__(**kw)

    def process(self, *xs, meta=None):
        print('*', '-'*12)
        print('*', self.message)
        print('*', 'buffers:')
        for i, x in enumerate(xs):
            print('*', '\t', i, x.shape, x.dtype)
        print('*', 'meta:', meta)
        print('*', '-'*12)
        return xs, meta


class Specshow(reip.Block):
    def __init__(self, filename='{time}.png', figsize=(12, 6), **kw):
        self.filename = filename
        self.figsize = figsize
        self.kw = kw
        super().__init__()

    def process(self, X, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # plot
        plt.figure(figsize=self.figsize)
        librosa.display.specshow(X, **self.kw)
        plt.savefig(fname)
        return fname, meta




######################
# Scratch
######################

def simple():
    interval = Interval()
    audio = ExampleAudio()
    transform = Stft()
    sleep = Sleep()
    debug = Debug()
    saveimage = Specshow('plots/{offset:.1f}s+{window:.1f}s-{time}.png')

    interval.to(audio).to(transform).to(sleep).to(debug).to(saveimage)
    reip.run(interval, audio, transform, sleep, debug, saveimage)


# def keras_like_interface():  # XXX: this is hypothetical
#     line = Pipeline()
#     inp = x = Interval()(line)
#     x = ExampleAudio()(x)
#     x = Stft()(x)
#     x = Sleep()(x)
#     x = Debug()(x)
#     line.run()


if __name__ == '__main__':
    import fire
    fire.Fire({
        'simple': simple,
    })
