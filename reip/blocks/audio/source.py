import time
import queue
import pyaudio
import numpy as np

import reip

PA2NP = {
    pyaudio.paInt8: 'int8',
    pyaudio.paInt16: 'int16',
    pyaudio.paInt32: 'int32',
    pyaudio.paFloat32: 'float32',
    pyaudio.paUInt8: 'uint8',
}
PA2NP = {k: np.dtype(v) for k, v in PA2NP.items()}
NP2PA = {v: k for k, v in PA2NP.items()}

def pa2npfmt(fmt):
    return np.dtype(fmt if fmt in NP2PA else PA2NP[fmt])

def np2pafmt(fmt):
    return fmt if fmt in PA2NP else NP2PA[np.dtype(fmt)]


class Mic(reip.Block):
    def __init__(self, device=None, sr=None, block_duration=1, channels=None, mono=False, fmt='int16', **kw):
        self.device = device
        self.sr = sr
        self.block_duration = block_duration
        self.channels = channels
        self.mono = (0 if mono is True else mono if mono is not False else None)
        self.fmt = np.dtype(fmt)
        self._is_float = self.fmt == np.float32
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
            if d['maxInputChannels'] >= min_input
            and d['maxOutputChannels'] >= min_output
            and (query is None or query in d['name'])
        ), None)

    def init(self):
        '''Start pyaudio and start recording'''
        # initialize pyaudio
        self._pa = pyaudio.PyAudio()
        device = self.search_devices(self.device)
        self.log.info('Using audio device: {} - {}'.format(device['name'], device))

        # get parameters from device
        self.device = device
        self.sr = int(self.sr or device['defaultSampleRate'])
        self.channels = self.channels or device['maxInputChannels']
        self.blocksize = int(self.block_duration * self.sr)
        self.log.debug('sr: {} channels: {}  block size: {}'.format(
            self.sr, self.channels, self.blocksize))

        # start audio streamer
        self._q = queue.Queue()
        self._pastream = self._pa.open(
            input_device_index=device['index'],
            frames_per_buffer=self.blocksize,
            format=np2pafmt(self.fmt),
            channels=self.channels,
            rate=self.sr,
            input=True, output=False,
            stream_callback=self._stream_callback)

    def _stream_callback(self, buf, frame_count, time_info, status_flags):
        '''Append frames to the queue - blocking API is suuuuuper slow.'''
        if status_flags:
            self.log.error('Input overflow status: {}'.format(status_flags))
        t0 = time.time()  # time_info['input_buffer_adc_time'] or 
        self._q.put((buf, t0))
        return None, pyaudio.paContinue

    def process(self, meta=None):
        # buff = self._pastream.read(self.blocksize, exception_on_overflow=False)
        pcm, t0 = self._q.get()
        pcm = np.frombuffer(pcm, dtype=self.fmt)

        if not self._is_float:
            pcm = pcm / float(np.iinfo(pcm.dtype).max)
        pcm = pcm.reshape(-1, self.channels or 1)
        if self.mono is not None:
            pcm = pcm[:,self.mono]
        return [pcm], {
            'input_latency': self._pastream.get_input_latency(),
            'output_latency': self._pastream.get_output_latency(),
            'time': t0,
            'sr': self.sr,
        }

    def finish(self):
        '''Stop pyaudio'''
        self._pastream.stop_stream()
        self._pastream.close()
        self._pa.terminate()
