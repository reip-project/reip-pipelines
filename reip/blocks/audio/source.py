import time
import queue
import sounddevice as sd
import numpy as np
import reip


class Mic(reip.Block):
    _audio_stream = device = blocksize = None
    def __init__(self, device=None, sr=None, block_duration=1, channels=None,
                 mono=False, search_interval=10, dtype=np.int16, **kw):
        self.device_name = device
        self.sr = sr
        self.channels = channels
        self.mono = (0 if mono is True else mono if mono is not False else None)
        self.dtype = np.dtype(dtype)
        self._is_float = self.dtype == np.float32
        self.block_duration = block_duration
        self.search_interval = search_interval
        super().__init__(**kw)

        self._q = reip.stores.Producer()
        self.sources[0] = self._q.gen_source()

    # def init(self):
    #     '''Start pyaudio and start recording'''
    #     for i in reip.util.iters.run_loop(interval=self.search_interval):
    #         try:
    #             self._init()
    #             break
    #         except Exception as e:
    #             self.log.error('Microphone Init: ({}) {}'.format(e.__class__.__name__, e))
    #             if i == 0:
    #                 self.log.exception(e)

    def init(self):
        # initialize pyaudio
        device = find_device(self.device_name)
        self.log.info('Using audio device: {} - {}'.format(device['name'], device))

        # get parameters from device
        self.device = device
        self.sr = int(self.sr or device['default_samplerate'])
        self.channels = self.channels or device['max_input_channels']
        self.blocksize = int(self.block_duration * self.sr)

        # start audio streamer
        self._audio_stream = sd.InputStream(
            device=self.device['index'], blocksize=self.blocksize,
            samplerate=self.sr, channels=self.channels, dtype=self.dtype,
            callback=self._stream_callback)
        self._audio_stream.start()

    def _stream_callback(self, buf, frames, time_info, status):
        '''Append frames to the queue - blocking API is suuuuuper slow.'''
        if status:
            self.log.error('Input overflow status: {}'.format(status))
        self._q.put((buf, {'time': time.time()}))

    def process(self, pcm, meta):
        if not self._is_float:
            pcm = pcm / float(np.iinfo(pcm.dtype).max)
        if self.mono is not None:
            pcm = pcm[:,self.mono]
        return [pcm], {'sr': self.sr}

    def finish(self):
        '''Stop pyaudio'''
        if self._audio_stream is not None:
            self._audio_stream.close()
            self._audio_stream.stop()
        self._audio_stream = None


def find_device(query, min_input=1, min_output=0, log=None):
    '''Search for an audio device by name.'''
    devices = [dict(d, index=i) for i, d in enumerate(sd.query_devices())]
    if log is not None:
        log.debug('Available Audio Devices: {}'.format(devices))
    try:
        return next((
            d for d in devices
            if d['max_input_channels'] >= min_input
            and d['max_output_channels'] >= min_output
            and (query is None or query in d['name'])
        ))
    except StopIteration:
        raise OSError('No device found matching "{}" in {}.'.format(
            query, [d['name'] for d in devices]))
