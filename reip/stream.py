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
    def __init__(self, sources, loop=None):
        self.sources = sources
        self.loop = reip.util.iters.loop() if loop is None else loop

    def __str__(self):
        srcs = ''.join(f'\n{s}' for s in self.sources)
        return f'<{self.__class__.__name__} {text.indent(srcs)}>'

    def __iter__(self):
        self.resume()
        for _ in self.loop:
            # if the stream is terminated, exit immediately
            if self.terminated:
                return
            # if the stream doesn't have any sources, then we can close
            if not self.sources and self.closed:
                return
            # otherwise if we're not paused and we have data ready, return it
            if self.running and self.check_ready():
                yield self.get()
            else:
                # if we are out of data and the stream is closed, stop iterating.
                if self.closed:
                    return

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

    def get(self):
        return prepare_input([s.get_nowait() for s in self.sources])



def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [b for bs in bufs for b in reip.util.as_list(bs) if b is not ...],
        reip.util.Meta({}, *meta))
