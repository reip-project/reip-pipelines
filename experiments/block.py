from interface import Sink, Source
from ring_buffer import RingBuffer
from buffer_store import BufferStore
from stopwatch import StopWatch
import multiprocessing as mp
import threading
import traceback
import queue
import time
# import ctypes
#
# libc = ctypes.CDLL('libc.so.6')


class Block:
    def __init__(self, name, max_rate=None, num_sinks=0, num_sources=0, sink_size=100):
        self.name = name
        self.max_rate = max_rate
        self.sink_size = sink_size
        self.sinks = [None] * num_sinks
        self.sources = [None] * num_sources
        self.task = None
        self._sw = StopWatch(name)

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
        self._p0 = None

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

    def process(self, buffers):
        return buffers

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
            self._sw.tick()

            if self._debug:
                print("Started thread", self.name)

            with self._sw("init"):
                self.init()

            if self._verbose:
                print("Block %s Initialized in %.4f sec" % (self.name, self._sw["init"]))

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
                            with self._sw("limit"):
                                while time.time() + 0.25 * self._dt < self._p0 + (1. / self.max_rate):
                                    time.sleep(self._process_delay)

                        with self._sw("process"):
                            buffers_out = self.process(buffers_in)
                        # check_types(buffers_out)
                        self.processed += 1
                        for source in self.sources:
                            source.next()
                        if len(self.sinks) > 0:
                            for i, buf in enumerate(buffers_out):
                                self.sinks[i].put(buf, block=False)

                with self._sw("wait"):
                    # libc.usleep(1)
                    # libc.nanosleep(1)
                    time.sleep(self._process_delay)

            with self._sw("finish"):
                self.finish()

            self._sw.tock()

            if self._verbose:
                print("Block %s Finished after %.4f sec" % (self.name, self._sw[""]))

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
        dropped = [sink.dropped for sink in self.sinks if not isinstance(sink, (queue.Queue, mp.queues.Queue))]
        print("Block %s processed %d buffers (Dropped:" % (self.name, self.processed), dropped, ")")
        print(self._sw)
