from interface import Sink, Source
from abc import ABC, abstractmethod
from ring_buffer import RingBuffer
from buffer_store import BufferStore
import multiprocessing as mp
import threading
import traceback
import queue
import time
# import ctypes
#
# libc = ctypes.CDLL('libc.so.6')


class Block(ABC):
    def __init__(self, name, max_rate=None, num_sinks=0, num_sources=0, sink_size=100):
        self.name = name
        self.max_rate = max_rate
        self.sink_size = sink_size
        self.sinks = [None] * num_sinks
        self.sources = [None] * num_sources
        self.task = None

        self.ready = False
        self.running = False
        self.terminate = False
        self.error = False
        self.done = False
        self.processed = 0

        self._select = 0
        self._thread = None
        self._debug = True
        self._verbose = True
        self._t0 = 0
        self._p0 = None
        self._init_time = 0
        self._process_time = 0
        self._wait_time = 0
        self._rate_time = 0
        self._finish_time = 0
        self._total_time = 0

        t = time.time()
        time.sleep(1e-6)
        self._dt = time.time() - t
        self._process_delay = 1e-6
        self._terminate_delay = 1e-6

    # Construction

    def __getitem__(self, key):
        if type(key) is int:
            if key < 0:
                raise ValueError("Invalid key value")
            else:
                self._select = key
                return self
        else:
            raise TypeError("Invalid key type")

    @property
    def sink(self):
        return self.sinks[self._select]

    @property
    def source(self):
        return self.sources[self._select]

    @sink.setter
    def sink(self, new_sink):
        if not issubclass(type(new_sink), Sink):
            if isinstance(new_sink, queue.Queue) or isinstance(new_sink, mp.queues.Queue):
                self.sinks[self._select] = new_sink
            else:
                raise ValueError("Not a sink")
        else:
            self.sinks[self._select] = new_sink

    @source.setter
    def source(self, new_source):
        if not issubclass(type(new_source), Source):
            if isinstance(new_source, queue.Queue):
                self.sources[self._select] = new_source
            else:
                raise ValueError("Not a source")
        else:
            self.sources[self._select] = new_source

    def child(self, other, **kw):
        if not issubclass(type(other), Block):
            raise ValueError("Not a block")
        if len(self.sinks) == 0:
            raise ValueError("Block %s doesn't have any sinks" % self.name)
        if len(other.sources) == 0:
            raise ValueError("Block %s doesn't have any sources" % other.name)
        else:
            if self.sink is None:
                if self.task != other.task:
                    self.sink = BufferStore(self.sink_size)
                    print("Store")
                else:
                    self.sink = RingBuffer(self.sink_size)
                    print("Ring")
            other.source = self.sink.gen_source(**kw)
            return other

    def parent(self, other, **kw):
        return other.child(self, **kw)

    # Operation

    def init(self):
        pass

    def start(self):
        if not self.ready:
            raise RuntimeError("Block %s not ready to start" % self.name)
        else:
            self.running = True

    def __enter__(self):
        self.start()
        return self

    @abstractmethod
    def process(self, buffers):
        raise NotImplementedError

    def stop(self):
        if not self.running:
            raise RuntimeError("Block %s not running" % self.name)
        else:
            self.running = False

    def __exit__(self, type, value, traceback):
        self.stop()
        return False

    def finish(self):
        pass

    def spawn(self, wait=True):
        for i, source in enumerate(self.sources):
            if source is None:
                raise RuntimeError("Source %d in block %s not connected" % (i, self.name))
        for i, sink in enumerate(self.sinks):
            if sink is None:
                raise RuntimeError("Sink %d in block %s not connected" % (i, self.name))

        self._thread = threading.Thread(target=self._run, name=self.name)
        self._thread.daemon = True
        if self._verbose:
            print("Spawning block %s..." % self.name)
        self.ready = False
        self.done = False
        self._thread.start()

        if wait:
            while not self.ready:
                time.sleep(1e-6)

    def _run(self):
        try:
            if self._debug:
                print("Started thread", self.name)
            self._t0 = time.time()
            self.init()
            self._init_time = time.time() - self._t0
            if self._verbose:
                print("Block %s Initialized in %.3f sec" % (self.name, self._init_time))
            self.ready = True
            # self.start()

            while not self.terminate:
                if self.running:
                    buffers_in = []
                    valid = True

                    for source in self.sources:
                        buf = source.get(block=False)
                        if buf is None:
                            valid = False
                            break
                        else:
                            buffers_in.append(buf)

                    if valid:
                        if self.max_rate is not None and self._p0 is not None:
                            r0 = time.time()
                            while time.time() + 0.25 * self._dt < self._p0 + (1. / self.max_rate):
                                time.sleep(self._process_delay)
                            self._rate_time += time.time() - r0

                        self._p0 = time.time()
                        buffers_out = self.process(buffers_in)
                        # check_types(buffers_out)
                        self._process_time += time.time() - self._p0
                        self.processed += 1
                        for source in self.sources:
                            source.next()
                        if len(self.sinks) > 0:
                            for i, buf in enumerate(buffers_out):
                                self.sinks[i].put(buf, block=False)

                if self._process_delay is not None:
                    w0 = time.time()
                    # libc.usleep(1)
                    # libc.nanosleep(1)
                    time.sleep(self._process_delay)
                    self._wait_time += time.time() - w0

            f0 = time.time()
            self.finish()
            self._finish_time = time.time() - f0
            self._total_time = time.time() - self._t0
            if self._verbose:
                print("Block %s Finished after %.3f sec" % (self.name, self._total_time))
            if self._terminate_delay is not None:
                time.sleep(self._terminate_delay)
            self.done = True
        except:
            self.error = True
            traceback.print_exc()

    def join(self, auto_terminate=True):
        if self._thread is None:
            return

        if auto_terminate:
            self.terminate = True

        print("Joining block %s..." % self.name)
        self._thread.join(timeout=0.5)
        if self._debug:
            print("Joined thread", self.name)

    def print_stats(self):
        print("Block %s processed %d buffers" % (self.name, self.processed))
        print("Dropped:", [sink.dropped for sink in self.sinks if not isinstance(sink, queue.Queue) and not isinstance(sink, mp.queues.Queue)])
        service_time = self._total_time - (self._init_time + self._process_time + self._finish_time + self._wait_time + self._rate_time)
        print("Total time %.3f sec:\n\t%.3f - Initialization\n\t%.3f - Processing\n\t%.3f - Finishing up\n\t%.3f - Waiting\n\t%.3f - Rate limit\n\t%.3f - Service time" %
              (self._total_time, self._init_time, self._process_time, self._finish_time, self._wait_time, self._rate_time, service_time))
