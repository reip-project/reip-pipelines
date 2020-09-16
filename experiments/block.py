from interface import Sink, Source
from ring_buffer import RingBuffer
from buffer_producer import Producer
from buffer_store import BufferStore
from stopwatch import StopWatch
import multiprocessing.queues
from base import *
import threading
import traceback
import queue


class Block(Worker):
    def __init__(self, name, graph=None, num_sinks=0, num_sources=0, max_rate=None,
                 sink_size=100, debug=True, verbose=False):
        Worker.__init__(self, name, graph=graph, debug=verbose)
        self.max_rate = max_rate
        self.debug = debug
        self.verbose = verbose
        self.processed = 0
        self.sinks = [None] * num_sinks
        self.sources = [None] * num_sources
        self._thread = None
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

    def to(self, other, plasma=True, faster_queue=True, **kw):
        if not isinstance(other, Block):
            raise ValueError("Not a block")
        if len(self.sinks) == 0:
            raise ValueError("Block %s doesn't have any sinks" % self.name)
        if len(other.sources) == 0:
            raise ValueError("Block %s doesn't have any sources" % other.name)

        if self.sink is None:
            if self._graph_name != other._graph_name:
                if plasma:
                    self.sink = BufferStore(self._sink_size, name=self.name, debug=self.verbose)
                else:
                    self.sink = Producer(self._sink_size, faster_queue=faster_queue, name=self.name, debug=self.verbose)

                if self.verbose:
                    print("Store" if plasma else "Producer")
            else:
                self.sink = RingBuffer(self._sink_size, name=self.name, debug=self.verbose)
                if self.verbose:
                    print("Ring")

        other.source = self.sink.gen_source(**kw)
        return other

    # Operation

    def init(self):
        # if self.name == "Block1":
        #     raise Exception("Test")
        pass

    def process(self, buffers):
        # if self.name == "Block1":
        #     raise Exception("Test")
        return buffers

    def finish(self):
        # if self.name == "Block1":
        #     raise Exception("Test")
        pass

    def reset(self):
        Worker.reset(self)
        self._sw.reset()
        self.processed = 0

    def spawn(self, wait_ready=True):
        for i, source in enumerate(self.sources):
            if source is None:
                raise RuntimeError("Source %d in block %s not connected" % (i, self.name))
        for i, sink in enumerate(self.sinks):
            if sink is None:
                raise RuntimeError("Sink %d in block %s not connected" % (i, self.name))

        if self.verbose:
            print("Spawning block %s.." % self.name)

        self.reset()
        for sink in self.sinks:
            if not isinstance(sink, (queue.Queue, mp.queues.Queue)):
                sink.spawn()
        self._thread = threading.Thread(target=self._target, name=self.name, daemon=True)
        self._thread.start()

        if wait_ready:
            self.wait_ready()

    def _target(self):
        if self.verbose:
            print("Spawned block", self.name)
        try:
            self._run()
        except Exception as e:
            self._exception = (e, traceback.format_exc())
            self._error.value = True
            self._done.value = True

        if self.verbose:
            print("Exiting block %s.." % self.name)

    def _run(self):
        self._sw.tick()

        with self._sw("init"):
            self.init()

        if self.debug:
            print("Block %s Initialized in %.4f sec" % (self.name, self._sw["init"]))

        self._ready.value = True
        # self.start()  # auto_start?

        while not self._terminate.value:
            if self.running:
                buffers_in = []
                valid = True

                with self._sw("collect"):  # recurrent stopwatch overhead (~20 us on Jetson Nano)
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

                    with self._sw("process"):  # recurrent stopwatch overhead (~20 us on Jetson Nano)
                        self._t0 = time.time()
                        buffers_out = self.process(buffers_in)
                    # check_types(buffers_out)
                    self.processed += 1

                    for source in self.sources:
                        source.next()

                    if len(self.sinks) > 0:
                        with self._sw("write"):  # recurrent stopwatch overhead (~20 us on Jetson Nano)
                            for i, buf in enumerate(buffers_out):
                                self.sinks[i].put(buf, block=False)

            with self._sw("sleep"):  # recurrent stopwatch overhead (~20 us on Jetson Nano)
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
            self.terminate()

        self._thread.join(timeout=0.1)
        for sink in self.sinks:
            if not isinstance(sink, (queue.Queue, mp.queues.Queue)):
                sink.join()

        if self.verbose:
            print("Joined block", self.name)

    def stats(self):
        # if self.name == "Block1":
        #     raise Exception("Test")
        dropped = [sink.dropped for sink in self.sinks if not isinstance(sink, (queue.Queue, mp.queues.Queue))]
        return self.name, self.processed, dropped, self._sw

    def __str__(self):
        s = "Block %s processed %d buffers (Dropped: %s)\n" % (self.name, self.processed, str(self.stats()[2]))
        return s + str(self._sw)


if __name__ == '__main__':
    b = Block("Test", verbose=True, max_rate=None)

    i = 0

    def loop():
        global i
        print(i)
        # if i == 7:
        #     raise Exception("Test")
        i += 1
        time.sleep(1e-2)

    b.run(duration=0.1, loop_func=loop)
