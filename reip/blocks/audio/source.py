import time
import pyaudio
import librosa
import numpy as np

from ..block import Block
from ...utils import audio as audioutils


def buffer2np(channels, fmt=np.int16):
    return lambda x: np.frombuffer(x, fmt).reshape(-1, channels)

def wait_for_device(valid_device):
    return 0, {}


class RecordError(Exception):
    pass



class AudioSource(Block):
    '''Reads audio from an audio input.'''
    callback_update = 0

    pa = pyaudio.PyAudio()

    def __init__(self, *a, valid_device=None, channels=None, sr=44100,
                 frames_per_buffer=None, duration=None, timeout=None, fmt=np.int16, **kw):
        super().__init__(*a, **kw)
        self.index, self.info = wait_for_device(valid_device)
        self.channels = channels or self.info.get('maxInputChannels')
        self.duration = duration
        self.timeout = timeout
        self.to_array = buffer2np(self.channels, audioutils.pa2npfmt(fmt))
        self._stream = self.pa.open(
            start=False, input=True,
            input_device_index=self.index,
            rate=sr, format=audioutils.np2pafmt(fmt),
            channels=self.channels,
            frames_per_buffer=frames_per_buffer or int(sr / 4),
            stream_callback=self.__callback)

    def open(self):
        self._stream.start_stream()
        return self

    def close(self):
        self._stream.stop_stream()
        return self

    def run(self):
        '''Record audio for a certain amount of time - or indefinitely.'''
        with self:
            t0 = time.time()
            timeout, duration = self.timeout, self.duration
            curr_update = last_update = self.callback_update
            while True:
                time.sleep(timeout or duration)
                last_update, curr_update = curr_update, self.callback_update
                if timeout and curr_update - last_update == 0:
                    raise RecordError('No updates in the last {} second(s).'.format(
                        timeout))
                if duration and time.time() - t0 >= duration:
                    return True

    def __callback(self, buf, frame_count, time_info, status_flags):
        '''Callback for async recording using dual buffer.'''
        self.callback_update = (self.callback_update + 1) % 1000
        if status_flags:
            self.log.error('Input overflow status: %s', status_flags)
        self.send_output({
            'data': self.to_array(buf),
            'time': time_info['input_buffer_adc_time'] or time.time()
        })
        return None, pyaudio.paContinue
