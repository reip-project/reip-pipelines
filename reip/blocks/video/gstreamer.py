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
    def __init__(self, stream, *outputs, lazy_sources=True):
        self._gs = stream
        self._outputs = outputs
        self._lazy_sources = lazy_sources
        super().__init__(n_inputs=0, n_outputs=len(outputs))

    def init(self):
        self._gs.start()
        while not self._gs.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def process(self, meta):
        self._gs.check_messages()
        if self._gs.done:
            return reip.CLOSE
        if self._outputs:
            # will only pull samples if the sink has readers
            samples = [
                self._gs[o].try_pull_sample(self._sample_timeout)
                if not self._lazy_sources or self.sinks[i].readers else None
                for i, o in enumerate(self._outputs)]
            if all(samples):
                imgs, tss = zip(*(
                    gstream.unpack_sample(s)
                    if s is not None else (None, None)
                    for s in samples))
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
