import time
import threading
import traceback

import reip
from reip.stores import Producer
from reip.util.iters import throttled, timed, loop
from reip.util import text, check_block

__all__ = ['Block']


class Block:
    '''This is the base instance of a block.'''
    _thread = None
    _delay = 1e-6

    def __init__(self, queue=100, n_source=1, n_sink=1, name=None,
                 blocking=False, graph=None, max_rate=None,
                 wait_all_sources=True):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.sources = [None for _ in range(n_source)]
        self.sinks = [Producer(queue) for _ in range(n_sink)]
        self.context_id = reip.Task.add_if_available(graph, self)
        self.max_rate = max_rate
        self.__put_blocking = blocking
        self.__wait_all_sources = wait_all_sources
        # signals
        self._reset_state()
        # block timer
        self._sw = reip.util.Stopwatch(str(self))

    def _reset_state(self):
        # state
        self.ready = False
        self.running = False
        self.terminated = False
        self.error = False
        self._exception = None
        self.done = False
        # stats
        self.processed = 0
        # self._sw.reset()

    # _error = False
    # @property
    # def error(self):
    #     return self._error
    #
    # @error.setter
    # def error(self, value):
    #     reip.util.print_stack(f'setting value for {self}.error to {value}')
    #     self._error = value

    def __repr__(self):
        return '[Block({}): {} ({} in, {} out)]'.format(
            id(self), self.__class__.__name__,
            len(self.sources), len(self.sinks))

    # Graph definition

    def __call__(self, *others, **kw):
        for i, other in enumerate(others):
            # TODO: how to allow for sinks with empty buffers (but not empty meta)?
            self.sources[i] = other.sinks[0].gen_source(
                self.context_id == other.context_id, **kw)
        return self

    def to(self, *others, squeeze=True, **kw):
        outs = [other(self, **kw) for other in others]
        return outs[0] if squeeze and len(outs) == 1 else outs

    # User Interface

    def init(self):
        '''Initialize the block.'''

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # main process loop

    def __run(self, duration=None):
        print(text.l_(text.green('Starting'), self))
        time.sleep(self._delay)
        try:
            # profiler = pyinstrument.Profiler()
            # profiler.start()

            # initialize blocks
            self._sw.tick()

            with self._sw('init'):
                self.init()
            self.ready = True
            print(text.b_(text.green('Ready'), self), flush=True)

            for _ in throttled(timed(loop(), duration), self.max_rate, self._delay):
                if self.terminated:
                    break

                if self.running and (
                        not self.__wait_all_sources or
                        all(not s.empty() for s in self.sources)):
                    self.__run_step()

                # sleep to allow other threads to run
                self._sw.sleep(self._delay)  # adds timer

        except Exception as e:
            self._exception = e
            self.error = True
            print(text.red(text.b_(
                f'Exception occurred in {self}: ({type(e).__name__}) {e}',
                traceback.format_exc(),
            )))
        except KeyboardInterrupt:
            print(text.b_(text.yellow('\nInterrupting'), self))
        finally:
            # finish up and shut down block
            with self._sw('finish'):
                self.finish()
            self.done = True
            self._sw.tock()
            # if self.context_id is None:
            self.print_stats()

            # profiler.stop()
            # print(profiler.output_text(unicode=True, color=True))

    def __run_step(self):
        # get items from queue
        with self._sw('source'):
            inputs = [s.get_nowait() for s in self.sources]

        # transform input to output
        with self._sw('process'):
            bufs, meta_in = prepare_input(inputs)
            outputs = self.process(*bufs, meta=meta_in)
        # print(text.green(f"{self} processing took {self._sw.last('process'):.2f}s"))

        # feed output to sink, skip if None
        with self._sw('sink'):
            if outputs is reip.RETRY:
                pass
            elif outputs is None:
                for s in self.sources:
                    s.next()
            else:
                outs, meta = prepare_output(outputs, input_meta=meta_in)
                for s, out in zip(self.sources, outs):
                    if out is not reip.RETRY:
                        s.next()

                self.processed += 1
                for sink, out in zip(self.sinks, outs):
                    if sink is not None:
                        sink.put((out, meta), self.__put_blocking)

    # Thread management

    def spawn(self, wait=True):
        print(text.l_(text.blue('Spawning'), self, '...'))
        print(self.summary())

        for i, s in enumerate(self.sources):
            if s is None:
                raise RuntimeError(f"Source {i} in {self} not connected")
        self._reset_state()
        self.resume()
        self._thread = threading.Thread(target=self.__run)
        self._thread.daemon = True
        self._thread.start()

        if wait:
            self.wait_until_ready()

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def join(self, terminate=True, timeout=0.5):
        if terminate:
            self.terminate()
        if self._thread is None:
            return

        print(text.l_(text.blue('Joining'), self, '...'))
        self._thread.join(timeout=timeout)
        # raise any exception
        # if self._exception is not None:
        #     raise Exception(f'Exception in {self}') from self._exception

    # State management

    def pause(self):
        self.running = False

    def resume(self):
        self.running = True

    def terminate(self):
        self.terminated = True

    # debug

    def stats(self):
        return {
            'name': self.name,
            'processed': self.processed,
            'dropped': [getattr(sink, "dropped", None) for sink in self.sinks],
            'sw': self._sw,
        }

    def summary(self):
        return text.block_text(
            text.green(str(self)),
            'Sources:',
            text.indent(text.b_(*(f'- {s}' for s in self.sources))),
            '',
            'Sinks:',
            text.indent(text.b_(*(f'- {s}' for s in self.sinks)), 2),
            ch=text.blue('*'), n=40,
        )

    def status(self):
        '''
        e.g. `[Block_123412341 24,580 buffers, 1,230 x/s]`
        '''
        n = self.processed
        total_time = self._sw.elapsed()
        return f'[{self.name} {n:,} buffers, {n / total_time:,.2f} x/s]'

    def print_stats(self):
        total_time = self._sw.stats()[0] if '' in self._sw._samples else 0
        print(text.block_text(
            # block title
            f'Stats for {text.red(self) if self.error else text.green(self)}',
            # any exception, if one was raised.
            text.red(f'({type(self._exception).__name__}) {self._exception}')
            if self._exception else None,
            # basic stats
            f'Processed {self.processed} buffers in {total_time:.2f} sec. '
            f'({self.processed / total_time if total_time else 0:.2f} x/s)',
            f'Dropped: {[getattr(sink, "dropped", None) for sink in self.sinks]}',
            # timing info
            self._sw, ch=text.blue('*')))


def prepare_input(inputs):
    '''Take the inputs from multiple sources and prepare to be passed to block.process.'''
    bufs, meta = zip(*inputs) if inputs else ((), ())
    return (
        # XXX: ... is a sentinel for empty outputs - how should we handle them here??
        #      if there's a blank in the middle
        [] if all(b is ... for b in bufs) else bufs,
        reip.util.Stack({}, *meta))


def prepare_output(outputs, input_meta=None, expected_length=None):
    '''Take the inputs from block.process and prepare to be passed to block.sinks.'''

    bufs, meta = None, None
    if isinstance(outputs, tuple):
        if len(outputs) == 2:
            bufs, meta = outputs

    if expected_length is not None and len(outputs) != expected_length:
        raise ValueError(
            'Expected outputs to have length '
            f'{expected_length} but got {len(outputs)}')
    if input_meta:
        meta = reip.util.Meta(meta, input_meta)
    return bufs or (...,), meta or reip.util.Meta()
