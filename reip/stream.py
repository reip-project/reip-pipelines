import time
import reip
from reip.util import text

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
    def __init__(self, sources, loop=None):
        self.sources = sources
        self.loop = reip.util.iters.loop() if loop is None else loop

    def __str__(self):
        srcs = ''.join(f'\n{s}' for s in self.sources)
        return f'<{self.__class__.__name__} {text.indent(srcs)}>'

    def __iter__(self):
        self.resume()
        return self

    def __next__(self):
        for _ in self.loop:
            if self.running and (self.check_closed() or self.check_ready()):
                break
            time.sleep(self._delay)
        return prepare_input(self.get_inputs())

    def close(self):
        self.closed = True

    def pause(self):
        self.running = False

    def resume(self):
        self.running = True

    # pre-input

    def check_ready(self):
        '''Check if we're ready to send the inputs to the block.'''
        return all(not s.empty() for s in self.sources)

    def check_closed(self):
        '''If the stream is closed, exit the iterator.'''
        if self.closed:
            raise StopIteration
        return False

    #

    def get_inputs(self):
        return [s.get_nowait() for s in self.sources]



def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [b for bs in bufs for b in reip.util.as_list(bs) if b is not ...],
        reip.util.Meta({}, *meta))
