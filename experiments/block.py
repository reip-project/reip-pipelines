from interface import Sink, Source
from ring_buffer import RingBuffer
from buffer_store import BufferStore
from stopwatch import StopWatch
from base import Worker
import multiprocessing as mp
import threading
import traceback
import queue
import time

RED_ = '\033[91m'
_END = '\033[0m'


class Block(Worker, threading.Thread):
    def __init__(self, name, manager=None, num_sinks=0, num_sources=0, max_rate=None,
                 sink_size=100, debug=True, verbose=False):
        threading.Thread.__init__(self, target=self._run, name=name)
        Worker.__init__(self, name, manager=manager)
        self.max_rate = max_rate
        self.debug = debug
        self.verbose = verbose
        self.processed = 0
        self.sinks = [None] * num_sinks
        self.sources = [None] * num_sources
        self._sink_size = sink_size
        self._sw = StopWatch(name)
        self._select = 0
        self._t0 = 0
        self._process_delay = 1e-5
        self._terminate_delay = 1e-4

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
        if not isinstance(new_sink, (Sink, queue.Queue, mp.queues.Queue)):
            raise ValueError("Not a sink")
        self.sinks[self._select] = new_sink

    @source.setter
    def source(self, new_source):
        if not isinstance(new_source, (Source, queue.Queue, mp.queues.Queue)):
            raise ValueError("Not a source")
        self.sources[self._select] = new_source

    def to(self, other, **kw):
        if not isinstance(other, Block):
            raise ValueError("Not a block")
        if len(self.sinks) == 0:
            raise ValueError("Block %s doesn't have any sinks" % self.name)
        if len(other.sources) == 0:
            raise ValueError("Block %s doesn't have any sources" % other.name)

        if self.sink is None:
            if self._manager != other._manager:
                self.sink = BufferStore(self._sink_size)
                print("Store")
            else:
                self.sink = RingBuffer(self._sink_size)
                print("Ring")

        other.source = self.sink.gen_source(**kw)
        return other

    # Operation

    def init(self):
        pass

    def process(self, buffers):
        return buffers

    def finish(self):
        # raise Exception("Test")
        pass

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    # Resolved by order of inheritance (Worker before threading.Thread)
    # # Resolve ambiguity of start() method between Thread and Worker
    # def start(self):
    #     return Worker.start(self)

    def spawn(self, wait_ready=True):
        for i, source in enumerate(self.sources):
            if source is None:
                raise RuntimeError("Source %d in block %s not connected" % (i, self.name))
        for i, sink in enumerate(self.sinks):
            if sink is None:
                raise RuntimeError("Sink %d in block %s not connected" % (i, self.name))

        self._ready.value, self._done.value = False, False
        self._running.value, self._terminate.value = False, False
        self._error.value, self._exception = False, None

        if self.verbose:
            print("Spawning block %s.." % self.name)

        threading.Thread.start(self)

        if wait_ready:
            while not self.ready:
                time.sleep(1e-5)

    def run(self):
        if self.verbose:
            print("Spawned block", self.name)

        try:
            threading.Thread.run(self)
        except Exception as e:
            self._error.value, self._done.value = True, True
            self._exception = e
            print(RED_ + traceback.format_exc() + _END)
            # raise e  # You can still raise this exception if you need to

        if self.verbose:
            print("Exiting block %s.." % self.name)

    def _run(self):
        self._sw.tick()

        with self._sw("init"):
            self.init()

        if self.debug:
            print("Block %s Initialized in %.4f sec" % (self.name, self._sw["init"]))

        self._ready.value = True
        # self.start()

        while not self._terminate.value:
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
                    if self.max_rate is not None and self._t0 is not None:
                        with self._sw("limit"):
                            while time.time() + 0.5 * self._process_delay < self._t0 + (1. / self.max_rate):
                                time.sleep(self._process_delay)

                    with self._sw("process"):  # recurrent stopwatch overhead (~10 us)
                        self._t0 = time.time()
                        buffers_out = self.process(buffers_in)
                    # check_types(buffers_out)
                    self.processed += 1

                    for source in self.sources:
                        source.next()

                    if len(self.sinks) > 0:
                        for i, buf in enumerate(buffers_out):
                            self.sinks[i].put(buf, block=False)

            with self._sw("wait"):  # recurrent stopwatch overhead (~10 us)
                time.sleep(self._process_delay)

        with self._sw("finish"):
            self.finish()

        if self.debug:
            print("Block %s Finished in %.4f sec" % (self.name, self._sw["finish"]))

        if self._terminate_delay is not None:
            time.sleep(self._terminate_delay)

        self._sw.tock()
        self._done.value = True

        if self.debug:
            print("Block %s Done after %.4f sec" % (self.name, self._sw[""]))

    def join(self, auto_terminate=True):
        if auto_terminate:
            self._terminate.value = True

        threading.Thread.join(self, timeout=(0.1 + self._terminate_delay))

        if self.verbose:
            print("Joined block", self.name)

    def print_stats(self):
        dropped = [sink.dropped for sink in self.sinks if not isinstance(sink, (queue.Queue, mp.queues.Queue))]
        print("Block %s processed %d buffers (Dropped:" % (self.name, self.processed), dropped, ")")
        print(self._sw)


if __name__ == '__main__':
    b = Block("Test", verbose=True, max_rate=None)

    b.spawn()

    with b:
        time.sleep(0.1)

    b.join()

    if b.error:
        raise Exception("Block failed") from b.exception

    b.print_stats()
