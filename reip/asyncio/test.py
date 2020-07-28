'''

Blocks:
 - microphone source
 - SPL -> CSV -> tar.gz
 - audio -> wav

TODO:
 - audio temporal sampler
 - ML -> CSV -> tar.gz
 - status messages
 - -> status

'''
import os
import time
import queue
import csv
import tarfile

import soundfile
# import sounddevice
import pyaudio
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

#
# class Mic(reip.Block):
#     def __init__(self, device=None, sr=22050, block_duration=0.1, **kw):
#         self.device = device
#         self.sr = sr
#         self.block_duration = block_duration
#         self.kw = kw
#         super().__init__(n_source=0)
#
#     def init(self):
#         self._stream = sounddevice.Stream(
#             device=self.device, samplerate=self.sr,
#             blocksize=int(self.block_duration * self.sr),
#             **self.kw)
#         self._stream.start()
#
#     def process(self, meta):
#         data, overflowed = self._stream.read(self._stream.blocksize)
#         return [data], {
#             'overflowed': overflowed,
#             'latency': self._stream.latency,
#             'time': self._stream.time,
#             'sr': self.sr,
#         }
#
#     def finish(self):
#         self._stream.close()
#

class Mic(reip.Block):
    def __init__(self, device=None, sr=None, block_duration=1, channels=None, **kw):
        self.device = device
        self.sr = sr
        self.block_duration = block_duration
        self.channels = channels
        self.kw = kw
        super().__init__(n_source=0)

    def search_devices(self, query, min_input=1, min_output=0):
        '''Search for an audio device by name.'''
        if query is None:
            return self._pa.get_device_info_by_index(0)
        devices = (
            dict(self._pa.get_device_info_by_index(i), index=i)
            for i in range(self._pa.get_device_count()))
        return next((
            d for d in devices
            if query in d['name']
            and d['maxInputChannels'] >= min_input
            and d['maxOutputChannels'] >= min_output
        ), None)

    def init(self):
        '''Start pyaudio and start recording'''
        # initialize pyaudio
        self._pa = pyaudio.PyAudio()
        device = self.search_devices(self.device)
        print('Using audio device:', device['name'], device)

        # get parameters from device
        self.device = device
        self.sr = int(self.sr or device['defaultSampleRate'])
        self.channels = self.channels or device['maxInputChannels']
        self.blocksize = int(self.block_duration * self.sr)

        # start audio streamer
        self._q = queue.Queue()
        self._stream = self._pa.open(
            input_device_index=device['index'],
            frames_per_buffer=self.blocksize,
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sr,
            input=True, output=False,
            stream_callback=self._stream_callback)

    def _stream_callback(self, buf, frame_count, time_info, status_flags):
        '''Append frames to the queue - blocking API is suuuuuper slow.'''
        if status_flags:
            print('Input overflow status:', status_flags)
        t0 = time_info['input_buffer_adc_time'] or time.time()
        self._q.put((buf, t0))
        return None, pyaudio.paContinue

    def process(self, meta=None):
        # buff = self._stream.read(self.blocksize, exception_on_overflow=False)
        pcm, t0 = self._q.get()
        pcm = np.frombuffer(pcm, dtype=np.int16)
        pcm = pcm / float(np.iinfo(pcm.dtype).max)
        pcm = pcm.reshape(-1, self.channels or 1)
        return [pcm], {
            'input_latency': self._stream.get_input_latency(),
            'output_latency': self._stream.get_output_latency(),
            'time': t0,
            'sr': self.sr,
        }

    def finish(self):
        '''Stop pyaudio'''
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()


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
        if y.ndim > 1:
            y = y[:, 0]
        S = librosa.amplitude_to_db(np.abs(librosa.stft(y, **self.kw)))
        return [S], meta


class SPL(reip.Block):
    def __init__(self, duration=1, weighting='zac',
                 calibration=0, **kw):
        super().__init__()
        self.duration = duration
        self.calibration = calibration
        self._weighting = weighting
        # stft args
        self.kw = kw
        self.kw.setdefault('center', False)
        # blank initial values - see _init()
        self.weight_names = []
        self.weightings = None
        self.n_fft = None

    def _init(self, data, meta):
        # calculate the fft size using the sample rate and window duration
        self.n_fft = self.duration * meta['sr']
        self.n_fft = int(2 ** np.floor(np.log2(self.n_fft)))
        self.kw.setdefault('hop_length', self.n_fft)
        assert len(data) >= self.n_fft
        # get the frequency weights for each weighting function
        freqs = librosa.fft_frequencies(sr=meta['sr'], n_fft=self.n_fft)
        self.weight_names = [w.upper() for w in list(self._weighting or 'Z')]
        self.weightings = librosa.db_to_power(
            librosa.multi_frequency_weighting(freqs, self._weighting))

    def process(self, data, meta):
        if self.weightings is None:  # initialize using sr from metadata
            self._init(data, meta)
        # select single channel (48000, 1) => (48000,)
        data = data.reshape(len(data), -1)[:, 0]
        # get spectrogram (frequency, time) - (1025, 94)
        S = librosa.core.stft(data, n_fft=self.n_fft, **self.kw)
        # get weighted leq (3, 1025) x (1025, 94) => (1, 3)
        leq = self.calibration + librosa.power_to_db((
            self.weightings[..., None] * (S ** 2)).mean(-2)).T
        return [leq], {}


class Rebuffer(reip.Block):
    def __init__(self, size=None, duration=None, sr_key='sr'):
        assert size or duration, 'You must specify a size or duration.'
        self.size = size
        self.duration = duration
        self.sr_key = sr_key
        super().__init__()

    def init(self):
        self._q = queue.Queue()
        self.sr = None
        self.current_size = 0

    def process(self, x, meta):
        # calculate the size the first time using the sr in metadata
        if not self.size:
            self.sr = self.sr or meta[self.sr_key]
            self.size = self.duration * self.sr

        # place buffer into queue. If buffer is full, gather buffers and emit.
        if self._place_buffer(x, meta):
            return self._gather_buffers()

    def _place_buffer(self, x, meta):
        '''put items on the queue and return if the buffer is full.'''
        xsize = self._get_size(x)
        self.current_size += xsize
        self._q.put((x, meta, xsize))
        return self.current_size >= self.size

    def _gather_buffers(self):
        '''Read items from the queue and emit once it's reached full size.'''
        size = 0
        xs, metas = [], []
        while size < self.size:
            x, meta, xsize = self._q.get()
            xs.append(x)
            metas.append(meta)
            size += xsize
            self.current_size -= xsize
        return [self._merge_buffers(xs)], self._merge_meta(metas)

    def _get_size(self, buf):
        '''Return the size of a buffer, based on it's type.'''
        return len(buf)

    def _merge_buffers(self, bufs):
        return np.concatenate(bufs)

    def _merge_meta(self, metas):
        return metas[0]


# class TemporalSampler(reip.Block):
#     def __init__(self, func=None):
#         self.sampler = func or self.sampler or (lambda meta: True)
#         super().__init__()
#
#     def process(self, *xs, meta=None):
#         if self.sampler(meta):
#             return xs, meta


class Debug(reip.Block):
    def __init__(self, message='Debug', value=False, **kw):
        self.message = message
        self.value = value
        super().__init__(**kw)

    def process(self, *xs, meta=None):
        print('*', '-'*12)
        print('*', self.message)
        print('*', 'buffers:')
        for i, x in enumerate(xs):
            if isinstance(x, np.ndarray):
                print('*', '\t', i, x.shape, x.dtype, x if self.value else '')
            else:
                print('*', '\t', i, type(x), x if self.value else '')
        print('*', 'meta:', meta)
        print('*', '-'*12)
        return xs, meta


class Csv(reip.Block):
    _fname = _file = _writer = None
    def __init__(self, filename='{time}.csv', max_rows=1000, **kw):
        self.filename = filename
        self.max_rows = max_rows
        self.n_rows = 0
        self.kw = kw
        super().__init__()

    def should_get_new_writer(self, meta):
        return self.max_rows and self.n_rows > self.max_rows

    def get_writer(self, meta):
        closed_file = None
        if self._writer is None or self.should_get_new_writer(meta):
            closed_file = self.close_writer()
            # get filename
            fname = self.filename.format(**meta)
            os.makedirs(os.path.dirname(fname), exist_ok=True)
            print('opening new csv writer:', fname)
            # make writer
            self._fname = fname
            self._file = open(fname, 'w', newline='')
            self._writer = csv.writer(self._file, **self.kw)
            self.n_rows = 0
        return self._writer, closed_file

    def close_writer(self):
        if self._file is not None:
            self._file.close()
        return self._fname

    def process(self, X, meta):
        writer, closed_file = self.get_writer(meta)
        for x in X:
            writer.writerow(list(x))
            self.n_rows += 1
        if closed_file:
            return [closed_file], {}

    def finish(self):
        self.close_writer()


class TarGz(reip.Block):
    def __init__(self, filename='{time}.tar.gz', **kw):
        self.filename = filename
        self.kw = kw
        super().__init__()

    def process(self, *files, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # write to tar
        with tarfile.open(fname, "w:gz") as tar:
            for f in files:
                tar.add(f, arcname=os.path.basename(f))
        return [fname], {}


class Specshow(reip.Block):
    def __init__(self, filename='{time}.png', figsize=(12, 6), cmap='magma', **kw):
        self.filename = filename
        self.figsize = figsize
        self.cmap = cmap
        self.kw = kw
        super().__init__(exec_mode='process')

    def process(self, X, meta):
        # get filename
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # plot
        plt.figure(figsize=self.figsize)
        librosa.display.specshow(X, cmap=self.cmap, **self.kw)
        plt.savefig(fname)
        return [fname], meta


class AudioFile(reip.Block):
    def __init__(self, filename='{time}.wav'):
        self.filename = filename
        super().__init__()

    def process(self, X, meta):
        fname = self.filename.format(**meta)
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        soundfile.write(fname, X, meta['sr'])
        return fname, meta





# def get_silence_period(clip_duration, coverage, min_silence=5.0, sampling='normal'):
#     '''Given a clip_duration and desired coverage fraction, compute
#     how long the silence between clips needs to be to satisfy the desired
#     coverage and add some random variance to the silence based so that it
#     gives values sampled from the distribution specified by sampling.
#
#     Parameters
#     ----------
#     clip_duration : float
#         Duration of non-silent clip in seconds
#     coverage : float
#         Fraction of time to be recorded (non-silence), must be in range
#         (0,1]
#     min_silence : float
#         Minimum silence allowed between clips, in seconds
#     sampling : str
#         The distribution from which silence durations will be sampled, must
#         be 'uniform' or 'normal'.
#
#     Returns
#     -------
#     silence : float
#         The amount of silence to insert between the current and next clip,
#         in seconds.
#
#     '''
#     # checks and warnings
#     if clip_duration <= 0:
#         logger.warning('Clip duration must be positive, setting to default: 10.0')
#         clip_duration = 10.0
#
#     if coverage <= 0 or coverage > 1:
#         logger.warning('Coverage outside the allowed range of (0.1], setting to default: 0.5')
#         coverage = 0.5
#
#     if min_silence <= 0:
#         logger.warning('min_silence must be positive, setting to default: 5.0')
#         min_silence = 5.0
#
#     if sampling not in ['normal', 'uniform']:
#         logger.warning('Unknown sampling, defaulting to normal.')
#         sampling = 'normal'
#
#     # Compute exact silence duration
#     silence = (1 - coverage) / float(coverage) * clip_duration
#
#     # If the silence required to obtain the specified coverage is shorter
#     # than min_silence we default back to min_silence and report the
#     # estimated coverage
#     if silence < min_silence:
#         est_coverage = (
#             clip_duration / float(clip_duration + min_silence) * 100)
#         logger.warning(
#             "Coverage too high to meet min_silence of {:.2f} seconds, "
#             "returning {:.2f}. Estimated coverage is {:.2f}%".format(
#                 min_silence, min_silence, est_coverage))
#         return min_silence
#
#     # Add some variance
#     sigma = np.abs(silence - min_silence)
#     max_silence = silence + sigma
#
#     if sampling == 'uniform':
#         silence += sigma * (np.random.random_sample() * 2 - 1) # +[-sig, +sig]
#     elif sampling == 'normal':
#         silence += sigma / 3. * np.random.randn() # +N(0, sig/3)
#
#     # Make sure silence is within limits
#     silence = min(max(silence, min_silence), max_silence)
#     return silence




######################
# Scratch
######################

def simple():
    (Interval(seconds=2)
        .to(ExampleAudio())
        .to(Stft())
        .to(Sleep())
        .to(Debug())
        .to(Specshow('plots/{offset:.1f}s+{window:.1f}s-{time}.png')))

    print(reip.Graph.default)
    reip.Graph.default.run()


def record():
    # record audio
    audio = Mic(block_duration=10).to(Debug('Audio'))
    # to spectrogram
    audio.to(Stft()).to(Debug('Spec')).to(Specshow('plots/{time}.png'))
    # to audio file
    audio.to(AudioFile('audio/{time}.wav'))

    print(reip.Graph.default)
    reip.Graph.default.run()

def record10s():
    # record audio and buffer into chunks of 10
    audio = Mic(block_duration=1)
    audio10s = audio.to(Debug('Audio')).to(Rebuffer(duration=10))
    # to spectrogram
    audio10s.to(Stft()).to(Debug('Spec')).to(Specshow('plots/{time}.png'))
    # to wavefile
    audio10s.to(Debug('Audio 222')).to(AudioFile('audio/{time}.wav'))

    print(reip.Graph.default)
    reip.Graph.default.run()


def record_and_spl():
    with reip.Graph() as g:
        # audio source
        audio = Mic(block_duration=1)
        audio10s = audio.to(Debug('Audio')).to(Rebuffer(duration=10))
        # # to spectrogram
        audio10s.to(Stft()).to(Debug('Spec')).to(Specshow('plots/{time}.png'))
        # # to wav file
        audio10s.to(Debug('Audio 222')).to(AudioFile('audio/{time}.wav'))
        # to spl -> csv -> tar.gz
        (audio.to(SPL(calibration=72.54))
         .to(Debug('SPL', value=True))
         .to(Csv('csv/{time}.csv', max_rows=10))
         .to(TarGz('tar/{time}.tar.gz'))
         .to(Debug('SPL Tars', value=True)))
    print(g)
    g.run()


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
    fire.Fire()
