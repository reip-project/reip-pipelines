'''

Install:

Conda:
$ conda install pygobject gtk3 gst-plugins-base


'''
import time
import reip
from reip.util import gstream

class GStreamer(reip.Block):
    _sample_timeout = 1e+6
    def __init__(self, stream, *outputs):
        self._gs = stream
        self._outputs = outputs
        super().__init__(n_source=0, n_sink=len(outputs))

    def __getattr__(self, key):
        if key not in self._elements:
            raise AttributeError(key)
        return self._elements[key]

    def init(self):
        self._gs.start()
        while not self._gs.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def process(self):
        self._gs.check_messages()
        if self._gs.done:
            return reip.CLOSE
        if self._outputs:
            samples = [
                self._gs[o].try_pull_sample(self._sample_timeout)
                for o in self._outputs]
            if all(samples):
                imgs, tss = zip(*(gstream.unpack_sample(s) for s in samples))
                return imgs, {'timestamps': tss}

    def finish(self):
        self._gs.end()

    @property
    def running(self):
        return self._gs.running

    def pause(self):
        self._gs.pause()
        super().pause()

    def resume(self):
        self._gs.resume()
        super().resume()
