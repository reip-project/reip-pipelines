import time
import reip
from reip.util import text, iters

class Stream:
    '''A stream wraps a list of sources so that they can operate as a single
    generator.

    Basically I figured we could use this to add synchronization mechanics
    without over complicating the block code.

    def run(self):
        try:
            self.init()
            for data, meta in stream:
                self.process(*data, meta=meta)
        except Exception:
            pass
        finally:
            self.finish()

    '''
    _delay = 1e-6
    closed = False
    running = True
    terminated = False
    signal = None
    def __init__(self, sources, loop=None, auto_next=True, name=''):
        self.name = name or ''
        self.sources = sources
        self.loop = reip.util.iters.loop() if loop is None else loop
        self.auto_next = auto_next

    def __str__(self):
        state = (
            ' '.join(('closed' * self.closed, 'terminated' * self.terminated))
            or 'running' if self.running else 'paused')

        srcs = ''.join(f'\n{s}' for s in self.sources)
        return f'<{self.__class__.__name__}({self.name}) {state} {text.indent(srcs)}>'

    def reset(self):
        self.signal = None
        self.resume()

    def __iter__(self):
        self.reset()
        for _ in self.loop:
            # if the stream is terminated, exit immediately
            if self.terminated:
                return
            # if the stream doesn't have any sources, then we can close
            if not self.sources and self.closed:
                return
            # otherwise if we're not paused and we have data ready, return it
            if self.running and self.check_ready():
                inputs = [s.get_nowait() for s in self.sources]

                if inputs and all(x == reip.CLOSE for x, meta in inputs):
                    self.signal = reip.CLOSE  # block will send to sinks
                    self.close()
                    self.next()
                    continue

                if inputs and any(x == reip.TERMINATE for x, meta in inputs):
                    self.signal = reip.TERMINATE  # block will send to sinks
                    self.terminate()
                    self.next()
                    continue

                yield prepare_input(inputs)
                if self.auto_next:
                    self.next()

            # if we are out of data and the stream is closed, stop iterating.
            elif self.closed:
                return

            time.sleep(self._delay)
        # the only time this runs is when loop stops iterating.
        # notice that close and terminate all return, they don't break
        # so basically, if we set a run duration and we exceed that duration,
        # close block and send CLOSE signal downstream.
        self.signal = reip.CLOSE

    def next(self):
        for s in self.sources:
            s.next()

    def open(self):
        self.closed = False
        self.terminated = False

    def close(self):
        self.closed = True

    def pause(self):
        self.running = False

    def resume(self):
        self.running = True

    def terminate(self):
        self.terminated = True

    # pre-input

    def check_ready(self):
        '''Check if we're ready to send the inputs to the block.'''
        return all(not s.empty() for s in self.sources)

    #

    def get(self, check=True):
        return (
            prepare_input([s.get_nowait() for s in self.sources])
            if check and self.check_ready() else None)

    @classmethod
    def from_block_sources(cls, block, duration=None, max_rate=None, auto_next=False, **kw):
        '''Generate a stream using a block's sources.

        NOTE: this is unsafe as a public interface, because if you're using
        the same source instances in multiple places, the calls to `.next()` will
        interfere and you'll end up skipping items. That is why `auto_next` is set
        to `False`. For now, this is just used internally when creating a block.
        '''
        loop = iters.throttled(
            iters.timed(iters.loop(), duration),
            max_rate or block.max_rate, block._delay)
        return cls(block.sources, loop=loop, auto_next=auto_next, **kw)

    @classmethod
    def from_block(cls, block, duration=None, max_rate=None, **kw):
        '''Generate a stream using sources generated from a block's sinks.'''
        sources = [sink.gen_source() for sink in block.sinks]
        loop = iters.throttled(
            iters.timed(iters.loop(), duration),
            max_rate or block.max_rate, block._delay)
        return cls(sources, loop=loop, **kw)



def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [b for bs in bufs for b in reip.util.as_list(bs) if b is not ...],
        reip.util.Meta({}, *meta))
