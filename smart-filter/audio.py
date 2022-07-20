import time
import pyaudio
import alsaaudio
import traceback
import numpy as np

import reip
from dummies import BlackHole


class MicArray(reip.Block):
    channels = 16  # LR
    rate = 48000  # Hz
    chunk = 2000  # Use bigger buffer to prevent overrun errors (2048 max)
    dev = 11  # Input device (11 == 'MCHStreamer PDM16: USB Audio (hw:2,0)' on Happy Sensor)
    hw = 2 # Input device (11 == 'MCHStreamer PDM16: USB Audio (hw:2,0)' on Happy Sensor)
    interval = 1  # sec
    use_pyaudio = True
    debug = False
    verbose = False
    audio = None
    stream = None
    pcm = None
    buf = None
    tot_overflows = 0

    def __init__(self, **kw):
        super().__init__(n_inputs=0, **kw)

    def init(self):
        if self.use_pyaudio:
            self.audio = pyaudio.PyAudio()

            if self.debug:
                print("\nMicArray: Available devices")
                for i in range(self.audio.get_device_count()):
                    dev = self.audio.get_device_info_by_index(i)
                    print("\t", (i, dev['name'], dev['maxInputChannels']))

            self.stream = self.audio.open(channels=self.channels, rate=self.rate, format=pyaudio.paInt32,
                                          input=True, input_device_index=self.dev, frames_per_buffer=self.chunk)
        else:
            self.pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL,
                                     channels=self.channels, rate=self.rate, format=alsaaudio.PCM_FORMAT_S32_LE,
                                     device=("hw:%d,0" % self.hw), periodsize=self.chunk)
        self.new_buf()

    def new_buf(self):
        self.n_frames = int(self.interval * self.rate)
        self.n_chunks = self.n_frames // self.chunk
        assert self.n_frames % self.chunk == 0, "MicArray: Interval must be a multiple of chunk size"
        self.buf = np.zeros((self.n_frames, self.channels), dtype=np.int32)
        self.i_chunk, self.overflows = 0, 0

    def process(self, *xs, meta=None):
        if self.buf is None:
            self.new_buf()

        if self.use_pyaudio:
            try:
                # exception_on_overflow=True would cause stream to be closed automatically after the first overrun error
                raw_data = self.stream.read(self.chunk, exception_on_overflow=False)
                data = np.frombuffer(raw_data, dtype=np.int32).reshape((self.chunk, self.channels))
            except Exception as e:
                if self.debug:
                    if self.verbose:
                        print(traceback.format_exc())
                    print("MicArray: Overflow")
                self.tot_overflows += 1
                self.overflows += 1
                data = np.zeros((self.chunk, self.channels), dtype=np.int32)
        else:
            while True:  # keep trying until get valid data
                l, raw_data = self.pcm.read()
                if l < 0:
                    if self.debug:
                        if self.verbose:
                            print(l, len(raw_data), raw_data)
                        print("MicArray: Overflow")
                    self.tot_overflows += 1
                    self.overflows += 1
                elif l == self.chunk:
                    data = np.frombuffer(raw_data, dtype=np.int32).reshape((self.chunk, self.channels))
                    break
                else:
                    # raise ValueError("MicArray: Invalid data length")
                    if self.debug:
                        print("MicArray: Invalid data length", l)

        pos = self.i_chunk * self.chunk
        if self.debug and self.verbose:
            print(pos, self.chunk, data.shape, data.dtype, data[0, :])

        self.buf[pos:(pos+self.chunk), :] = data
        self.i_chunk = (self.i_chunk + 1) % self.n_chunks

        if self.i_chunk == 0:
            ret, self.buf = self.buf, None
            return [ret], {"time": time.time(),
                         "data_type": "audio_raw",
                         "channels": self.channels,
                         "sr": self.rate,
                         "interval": self.interval,
                         "n_frames": self.n_frames,
                         "overflows": self.overflows,
                         "tot_overflows": self.tot_overflows,
                         "device": self.dev,
                         "hw": self.hw,
                         "format": "S32_LE"}

    def finish(self):
        if self.debug and self.tot_overflows:
            print("\nMicArray: %d tot_overflows" % self.tot_overflows)

        if self.use_pyaudio and not self.tot_overflows:
            if self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()

            if self.audio is not None:
                self.audio.terminate()


if __name__ == '__main__':
    # mic = MicArray(name="Mic", max_rate=None, use_pyaudio=True, debug=True, verbose=False)
    mic = MicArray(name="Mic", max_rate=23, use_pyaudio=True, debug=True, verbose=False)
    # mic.interval = 1.7
    mic.to(BlackHole(name="BH"))

    reip.default_graph().run(duration=5.1, stats_interval=1)
