from abc import ABC, abstractmethod
import threading
import multiprocessing as mp
import traceback
import queue
import time
from . import util
from .ring_buffer import RingBuffer
from .interface import Sink, Source


WORKER_CLASSES = {'thread': threading.Thread, 'process': mp.Process}


class Block(ABC):
    _worker = None
    __type_name__ = 'Block'  # for log messages

    def __init__(self, max_rate=None, num_sinks=0, num_sources=0, verbose=1,
                 name=None, delay=1e-6, run_mode='thread'):
        ''''''
        self.name = name or self.__class__.__name__
        self.timer = util.Timer('{} {}'.format(self.__type_name__, self.name))

        if run_mode not in WORKER_CLASSES:
            raise ValueError('Invalid run_mode {}. Must be one of {}'.format(
                run_mode, set(WORKER_CLASSES)))
        self._worker_cls = WORKER_CLASSES[run_mode]

        self.max_rate = max_rate
        self.sinks = [None] * num_sinks
        self.sources = [None] * num_sources
        self._select = 0

        self.ready = False
        self.running = False
        self.done = False
        self.error = False
        self.exception = None
        self.terminate = False

        self.processed = 0
        self._verbose = verbose
        self._p0 = None

        t = time.time()
        time.sleep(delay)
        self._dt = time.time() - t
        self._spawn_delay = delay
        self._process_delay = delay
        self._terminate_delay = delay

    # Construction

    # # these props allow you to override certain methods of the attributes
    # # value
    # sources = _LinksProp((Source, queue.Queue), name='source')
    # sinks = _LinksProp((Sink, queue.Queue), name='sink')

    def __getitem__(self, key):
        if isinstance(key, int):
            if key < 0:
                raise ValueError("Invalid key value")
            self._select = key
            return self
        raise TypeError("Invalid key type")

    @property
    def sink(self):
        return self.sinks[self._select] # XXX: how should we do this ?

    @property
    def source(self):
        return self.sinks[self._select] # XXX: how should we do this ?

    @sink.setter
    def sink(self, new_sink):
        if not isinstance(new_sink, (Sink, queue.Queue)):
            raise ValueError("Not a sink")
        self.sinks[self._select] = new_sink

    @source.setter
    def source(self, new_source):
        if not isinstance(new_source, (Source, queue.Queue)):
            raise ValueError("Not a source")
        self.sources[self._select] = new_source


    def child(self, other, **kw):
        if not isinstance(other, Block):
            raise ValueError("Not a {}".format(self.__type_name__))
        other.source = self.sink.gen_source(**kw) # XXX
        return other

    def parent(self, other, **kw):
        return other.child(self, **kw)

    def queue(self, length=None):
        '''Set the queue size.'''
        self.sink = RingBuffer(length) if length else queue.Queue()
        return self

    # Operation

    def init(self):
        '''Any start up tasks on the worker.'''
        pass

    def process(self, buffers):
        return buffers

    def finish(self):
        '''Any cleanup to do.'''
        pass

    # Context Managing

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if exc_type:
            self.join(auto_terminate=True)

    def spawn(self, wait=True):
        # check sources
        for i, source in enumerate(self.sources):
            if source is None:
                raise RuntimeError("Source %d in block %s not connected" % (i, self.name))
        # check sinks
        for i, sink in enumerate(self.sinks):
            if sink is None:
                raise RuntimeError("Sink %d in block %s not connected" % (i, self.name))

        # start worker
        if self._verbose:
            print("Spawning {} {}...".format(self.__type_name__, self.name))
        self.ready = self.done = False
        self._worker = self._worker_cls(target=self._run, name=self.name)
        self._worker.daemon = True
        self._worker.start()

        if wait: # wait for worker to initialize
            while not self.ready:
                time.sleep(self._spawn_delay)

    # @profile
    def _run(self):
        try:
            if self._verbose:
                print("Started", self._worker_cls.__name__, self.name)

            with self.timer(output=self._verbose):
                # initialized
                with self.timer('init', 'Initialized', self._verbose):
                    self.init()
                self.ready = True

                while not self.terminate:
                    # run the actual block processing code
                    if self.running:
                        self._run_step()

                    # pause to allow other workers to work
                    if self._process_delay:
                        t_ = time.time()
                        time.sleep(self._process_delay)
                        self.timer.lap(t_, 'wait', 'Waiting')  # less overhead

                # close
                with self.timer('finish', 'Finishing', self._verbose):
                    self.finish()

            # sleep at close
            if self._terminate_delay is not None:
                time.sleep(self._terminate_delay)

            self.done = True
        except Exception as e:
            self.error = True
            self.exception = e
            print('Exception in', self.name, '({}) {}'.format(type(e), str(e)))
            # traceback.print_exc()
            raise

    def _run_step(self):
        buffers_in = self._gather_sources()
        if buffers_in is None:
            return

        # throttle
        with self.timer('rate', 'Rate limit'):
            self._throttle()

        # run block code
        self._p0 = time.time()  # for throttling
        with self.timer('process', 'Processing'):
            buffers_out = self.process(buffers_in)
        self.processed += 1

        # notify and increment the source
        for source in self.sources:
            source.next()

        # send buffers to sinks
        for sink, buf in zip(self.sinks, buffers_out):
            sink.put(buf, block=False)

    def _gather_sources(self):
        # wait for all buffers to be ready
        buffers_in = []
        for source in self.sources:
            buf = source.get(block=False)
            if buf is None:
                return
            buffers_in.append(buf)
        return buffers_in

    def _throttle(self):
        if self.max_rate and self._p0:
            secs = 1. / self.max_rate - ((time.time() - self._p0) + 0.25 * self._dt)
            if secs > 0:
                time.sleep(secs)

    def join(self, auto_terminate=True):
        if self._worker is None:
            return

        if auto_terminate:
            self.terminate = True

        if self._verbose:
            print("Joining {} {}...".format(self.__type_name__, self.name))
        self._worker.join()
        if self._verbose:
            print("Joined", self._worker_cls.__name__, self.name)

    def print_stats(self):
        print("Block {} processed {} buffers".format(self.name, self.processed))
        print("Dropped:", [sink.dropped for sink in self.sinks if isinstance(sink, Sink)])
        print(self.timer)

    def run(self, block=True, duration=None, delay=0.1):
        self.spawn()
        self.start()
        if block:
            try:
                if duration:
                    time.sleep(duration)
                else:
                    while True:
                        time.sleep(delay)
            finally:
                self.stop()
                self.join()
        return self
