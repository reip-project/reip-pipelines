from abc import ABC, abstractmethod
import threading
import traceback
import queue
import time
from . import util
from .ring_buffer import RingBuffer
from .interface import Sink, Source


# class _LinksProp(util.patchprop):
#     '''Make sure that items assigned to this property's keys are of a certain type.'''
#     def __init__(self, bases=(), name='object'):
#         self._bases, self.__name__ = bases, name
#         super().__init__()
#
#     def __setitem__(self, key, value):
#         if not isinstance(value, self._bases):
#             raise ValueError("{} must be one of types: {}".format(
#                 self.__name__, self._bases))
#         return super().__setitem__(key, value)


class Block(ABC):
    _worker = None
    _worker_cls = threading.Thread
    __type_name__ = 'Block'

    def __init__(self, max_rate=None, num_sinks=0, num_sources=0, verbose=1, name=None, delay=1e-6):
        self.name = name or self.__class__.__name__
        self.timer = util.Timer('{} {}'.format(self.__type_name__, self.name))

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
        if len(self.sinks) == 0:
            raise ValueError("{} {} doesn't have any sinks".format(
                self.__type_name__, self.name))
        if len(other.sources) == 0:
            raise ValueError("{} {} doesn't have any sources".format(
                other.__type_name__, other.name))

        other.source = self.sink.gen_source(**kw) # XXX
        return other

    def parent(self, other, **kw):
        return other.child(self, **kw)

    def queue(self, length=None):
        self.sinks[0] = RingBuffer(length) if length else queue.Queue() # XXX.
        return self

    # Operation

    def init(self):
        pass

    def process(self, buffers):
        return buffers

    def finish(self):
        pass

    # Context Managing

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()
        if type:
            self.join(auto_terminate=True)
        return False

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
        self._worker = self._worker_cls(target=self._run, name=self.name)
        self._worker.daemon = True
        if self._verbose:
            print("Spawning {} {}...".format(self.__type_name__, self.name))
        self.ready = False
        self.done = False
        self._worker.start()

        if wait: # wait for worker to initialize
            while not self.ready:
                time.sleep(1e-6)

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
                    # if not multiprocessing.parent_process().is_alive():
                    #     break
                    if self.running:
                        self._run_step()

                    # pause to allow other workers to work
                    if self._process_delay:
                        t_ = time.time()
                        time.sleep(self._process_delay)
                        self.timer.lap(t_, 'wait', 'Waiting')

                # close
                with self.timer('finish', 'Finishing', self._verbose):
                    self.finish()

            if self._terminate_delay is not None:
                time.sleep(self._terminate_delay)

            self.done = True
        except Exception as e:
            self.error = True
            self.exception = e
            # traceback.print_exc()
            raise

    def _run_step(self):
        buffers_in = []
        for source in self.sources:
            buf = source.get(block=False)
            if buf is None:
                return
            buffers_in.append(buf)

        # throttle
        with self.timer('rate', 'Rate limit'):
            while self._throttle():
                time.sleep(self._process_delay)

        # run block code
        self._p0 = time.time()
        with self.timer('process', 'Processing'):
            buffers_out = self.process(buffers_in)
        self.processed += 1

        # notify the source
        for source in self.sources:
            source.next()
        # send buffers to sinks
        for sink, buf in zip(self.sinks, buffers_out):
            sink.put(buf, block=False)

    def _throttle(self):
        return (
            self.max_rate and self._p0 and
            (time.time() + 0.25 * self._dt < self._p0 + (1./self.max_rate)))

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
