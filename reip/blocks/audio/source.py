import time
import queue
import pyaudio
import numpy as np

import reip


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
