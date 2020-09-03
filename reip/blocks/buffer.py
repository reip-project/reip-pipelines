import time
import queue
import warnings
import numpy as np
import reip


class Rebuffer(reip.Block):
    def __init__(self, size=None, duration=None, sr_key='sr', **kw):
        assert size or duration, 'You must specify a size or duration.'
        self.size = size
        self.duration = duration
        self.sr_key = sr_key
        super().__init__(**kw)

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



class GatedRebuffer(Rebuffer):
    TIME_KEY = 'time'
    def __init__(self, sampler, n_pass=1, **kw):
        self.sampler = (
            sampler if callable(sampler) else
            (lambda: sampler) if sampler else None)
        self.n_pass = n_pass
        self.pause_until = None
        self.allow_index = None
        super().__init__(**kw)

    def check_input_skip(self, meta):
        if not self.sampler:
            return

        t0 = meta.get(self.TIME_KEY) or time.time()

        # check if we are currently allowing buffers
        if self.allow_index is not None:
            if self.processed - self.allow_index >= self.n_pass:  # we've exceeded
                self.allow_index = None
                self.pause_until = t0 + self.sampler()
            else:
                return

        # check if we should be pausing
        if t0 < self.pause_until:
            return True

        # if not, record the processed count
        self.allow_index = self.processed


    def process(self, x, meta):
        if self.check_input_skip(meta):
            return
        return super().process(x, meta)




def temporal_coverage(clip_duration, coverage=0.5, min_silence=5.0, sampling='normal'):
    '''Given a clip_duration and desired coverage fraction, compute
    how long the silence between clips needs to be to satisfy the desired
    coverage and add some random variance to the silence based so that it
    gives values sampled from the distribution specified by sampling.

    Parameters
    ----------
    clip_duration : float
        Duration of non-silent clip in seconds
    coverage : float
        Fraction of time to be recorded (non-silence), must be in range
        (0,1]
    min_silence : float
        Minimum silence allowed between clips, in seconds
    sampling : str
        The distribution from which silence durations will be sampled, must
        be 'uniform' or 'normal'.

    Returns
    -------
    silence : float
        The amount of silence to insert between the current and next clip,
        in seconds.

    '''
    # checks and warnings
    if clip_duration <= 0:
        raise ValueError('Clip duration must be positive.')
    if not (0 < coverage <= 1):
        raise ValueError('Coverage outside the allowed range of (0,1].')
    if sampling not in ['normal', 'uniform']:
        raise ValueError('Unknown sampling method.')

    # Compute exact silence duration
    silence = (1 - coverage) / float(coverage) * clip_duration

    # If the silence required to obtain the specified coverage is shorter
    # than min_silence we default back to min_silence and report the
    # estimated coverage
    if silence < min_silence:
        warnings.warn(
            "Coverage too high to meet min_silence of {:.2f} seconds, "
            "returning {:.2f}. Estimated coverage is {:.2%}".format(
                min_silence, min_silence,
                clip_duration / float(clip_duration + min_silence)))
        return min_silence

    # Add some variance
    sigma = np.abs(silence - min_silence)
    max_silence = silence + sigma

    if sampling == 'uniform':
        silence += sigma * (np.random.random_sample() * 2 - 1) # +[-sig, +sig]
    elif sampling == 'normal':
        silence += sigma / 3. * np.random.randn() # +N(0, sig/3)

    # Make sure silence is within limits
    silence = min(max(silence, min_silence), max_silence)
    return silence
