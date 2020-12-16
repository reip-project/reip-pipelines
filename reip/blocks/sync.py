import reip
import numpy as np


# class BeatTracker(reip.util.statistics.OnlineStats):
#     last_time = None
#     def append(self, t):
#         self.last_time, last = t, self.last_time
#         if last is not None:
#             return super().append(t - last)


class Synchronize(reip.Block):
    def __init__(self, tol=1e-1, key='time', **kw):
        '''Synchronize two Block outputs'''
        self.key = key
        self.tol = tol
        super().__init__(n_inputs=None, n_outputs=None, **kw)

    # XXX: so that the number of sinks always equals the number of sources
    def set_block_source_count(self, n):
        super().set_block_source_count(n)
        self.set_block_sink_count(n)

    def process(self, *xs, meta):
        # if any queue slot is empty, retry
        is_none = [x is None for x in xs]
        if any(is_none):
            return reip.RETRY

        # check the time differences between samples
        # if any are too far back in the past, then skip them (???)
        # FIXME: is this right??
        times = np.array([m[self.key] for m in meta.sources])
        i_lead = np.argmax(times)
        isbehind = (times[i_lead] - times) > self.tol
        if np.any(isbehind):
            return [reip.NEXT if b else reip.RETRY for b in isbehind], meta
        return xs, meta
