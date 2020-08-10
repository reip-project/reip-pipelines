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
    _stream = None
    _delay = 1e-6

    def __init__(self, queue=100, n_source=1, n_sink=1, name=None,
                 blocking=False, graph=None, max_rate=None, **kw):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.sources = [None for _ in range(n_source)]
        self.sinks = [Producer(queue) for _ in range(n_sink)]
        self.context_id = reip.Task.add_if_available(graph, self)
        self.max_rate = max_rate
        self._put_blocking = blocking
        # signals
        self._reset_state()
        # block timer
        self._sw = reip.util.Stopwatch(str(self))
        self.extra_kw = kw

    def _reset_state(self):
        # state
        self.ready = False
        self.error = False
        self._exception = None
        self.done = False
        # stats
        self.processed = 0
        # self._sw.reset()

    def __repr__(self):
        return '[Block({}): ({} in, {} out)]'.format(
            self.name, len(self.sources), len(self.sinks))

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

    def synchronize(self, *buffers):
        return None

    def process(self, *xs, meta=None):
        '''Process data.'''
        return xs, meta

    def finish(self):
        '''Cleanup.'''

    # main process loop

    def _main(self, *a, **kw):
        try:
            # profiler = pyinstrument.Profiler()
            # profiler.start()
            print(text.l_(text.green('Starting'), self))
            time.sleep(self._delay)
            with self._sw():
                self._run(**kw)

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
            self.print_stats()

            # profiler.stop()
            # print(profiler.output_text(unicode=True, color=True))

    def _run(self, *a, **kw):
        try:
            # initialize the block
            stream = self._do_init(*a, **kw)
            # iterate over the input data gathered from the sources
            for buffers, meta in stream:
                # process each input batch
                outputs = self._do_process(*buffers, meta=meta)
                # send each output batch to the sinks
                self._do_sinks(outputs, meta)
        finally:
            # finish up and shut down block
            self._do_finish()

    def _do_init(self, *a, **kw):
        '''Initialize the block. Handles block timing and any logging.'''
        # create a new streamer that reads data from sources
        stream = self._init_stream(*a, **kw)
        with self._sw('init'):
            self.init()
        self.ready = True
        print(text.b_(text.green('Ready'), self), flush=True)
        return stream

    def _init_stream(self, duration=None):
        '''Initialize the source stream.

        NOTE: this should set self._stream to be the reip.Stream object so that
        we can call Stream methods to pause, terminate, etc.
        It can return a wrapped iterable which will be used to iterate inside
        the run function, e.g. wrap it with a timer, or additional formatting.
        '''
        # create a stream from sources with a custom control loop
        self._stream = reip.Stream(
            self.sources,
            throttled(
                timed(loop(), duration),
                self.max_rate, self._delay))
        # wrap stream in a timer
        return self._sw.iter(self._stream, 'source')

    def _do_process(self, *buffers, meta=None):
        '''Process buffers. Handles block timing and any logging.'''
        with self._sw('process'):
            outputs = self.process(*buffers, meta=meta)
        # print(text.green(f"{self} processing took {self._sw.last('process'):.2f}s"))
        return outputs

    def _do_finish(self):
        '''Cleanup block. Handles block timing and any logging.'''
        self._stream.close()  # may be redundant
        with self._sw('finish'):
            self.finish()
        self.done = True

    def _do_sinks(self, outputs, meta_in=None):
        '''Send the outputs to the sink.'''
        with self._sw('sink'):
            # retry all sources
            if outputs is reip.RETRY:
                pass
            # increment sources but don't have any outputs to send
            elif outputs is None:
                for s in self.sources:
                    s.next()
            # increment sources and send outputs
            else:
                # convert outputs to a consistent format
                outs, meta = prepare_output(outputs, input_meta=meta_in)
                # increment sources
                for s, out in zip(self.sources, outs):
                    if out is not reip.RETRY:
                        s.next()

                # pass to sinks
                self.processed += 1
                for sink, out in zip(self.sinks, outs):
                    if sink is not None:
                        sink.put((out, meta), self._put_blocking)

    # Thread management

    def spawn(self, wait=True):
        print(text.l_(text.blue('Spawning'), self, '...'))
        print(self.summary())

        for i, s in enumerate(self.sources):
            if s is None:
                raise RuntimeError(f"Source {i} in {self} not connected")
        self._reset_state()
        self.resume()
        self._thread = threading.Thread(target=self._main)
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
        if self._stream is not None:
            self._stream.pause()

    def resume(self):
        if self._stream is not None:
            self._stream.resume()

    def terminate(self):
        if self._stream is not None:
            self._stream.close()

    # XXX: this is temporary. idk how to elegantly handle this
    @property
    def running(self):
        return self._stream.running if self._stream is not None else False

    @property
    def terminated(self):
        return self._stream.closed if self._stream is not None else False

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
