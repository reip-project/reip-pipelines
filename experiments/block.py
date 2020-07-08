from abc import ABC, abstractmethod
import threading
import traceback
import queue
import time
import ctypes

libc = ctypes.CDLL('libc.so.6')

# To find block instance by name?
BlockFactory = {}


class Block(ABC):
    SOURCE = 1
    SINK = 2
    # MULTI_SOURCE = 4
    # MULTI_SINK = 8

    def __init__(self, block_name, block_type, sink=None, source=None):
        self.name = block_name
        if self.name in BlockFactory.keys():
            raise ValueError("Block %s already exists" % block_name)
        else:
            BlockFactory[self.name] = self

        self.has_source = block_type & Block.SOURCE
        self.has_sink = block_type & Block.SINK
        if self.has_source:
            self.source = source
        if self.has_sink:
            self.sink = sink

        self.ready = False
        self.running = False
        self.terminate = False
        self.done = False

        self._thread = None
        self._debug = True
        self._verbose = True
        self._processed = 0
        self._t0 = 0
        self._init_time = 0
        self._process_time = 0
        self._wait_time = 0
        self._finish_time = 0
        self._total_time = 0

        self._process_delay = 1e-6
        self._terminate_delay = 1e-6

    @abstractmethod
    def initialize(self):
        raise NotImplementedError

    # @abstractmethod
    def start(self):
        if not self.ready:
            raise RuntimeError("Block %s not ready to start" % self.name)
        else:
            self.running = True

    @abstractmethod
    def process(self, data, meta):
        raise NotImplementedError

    # @abstractmethod
    def stop(self):
        if not self.running:
            raise RuntimeError("Block %s not running" % self.name)
        else:
            self.running = False

    @abstractmethod
    def finish(self):
        raise NotImplementedError

    def _run(self):
        try:
            if self._debug:
                print("Started thread", self.name)
            self._t0 = time.time()
            self.initialize()
            self._init_time = time.time() - self._t0
            if self._verbose:
                print("Block %s Initialized in %.3f sec" % (self.name, self._init_time))
            self.ready = True
            # self.start()

            while not self.terminate:
                if self.running:
                    if self.has_source:
                        buffer_in = self.source.get(block=False)
                        if buffer_in is not None:
                            p0 = time.time()
                            buffer_out = self.process(*buffer_in)
                            self.source.done()
                            self._process_time += time.time() - p0
                            self._processed += 1
                            if self.has_sink and buffer_out is not None:
                                self.sink.put(buffer_out, block=False)
                    else:
                        p0 = time.time()
                        buffer_out = self.process(None, None)
                        self._process_time += time.time() - p0
                        self._processed += 1
                        if self.has_sink and buffer_out is not None:
                            self.sink.put(buffer_out, block=False)

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
            traceback.print_exc()

    def print_stats(self):
        dropped = 0 if not self.has_sink else (self.sink._dropped if not isinstance(self.sink, queue.Queue) else 0)
        print("Block %s processed %d buffers (dropped %d)" % (self.name, self._processed, dropped))
        service_time = self._total_time - (self._init_time + self._process_time + self._finish_time + self._wait_time)
        print("Total time %.3f sec:\n\t%.3f - Initialization\n\t%.3f - Processing\n\t%.3f - Finishing up\n\t%.3f - Waiting\n\t%.3f - Service time" %
              (self._total_time, self._init_time, self._process_time, self._finish_time, self._wait_time, service_time))

    def spawn(self, wait=True):
        self._thread = threading.Thread(target=self._run, name=self.name)
        self._thread.daemon = True
        if self._verbose:
            print("Starting block %s..." % self.name)
        self.ready = False
        self.done = False
        self._thread.start()

        if wait:
            while not self.ready:
                time.sleep(1e-4)

    def join(self, auto_terminate=True):
        if self._thread is None:
            return

        if auto_terminate:
            self.terminate = True

        self._thread.join()
        if self._debug:
            print("Joined thread", self.name)

    def child(self, other, **kw):
        if other is None:
            raise ValueError
        if not self.has_sink:
            raise ValueError
        if not other.has_source:
            raise ValueError
        other.source = self.sink.gen_source(**kw)

    def parent(self, other, **kw):
        if other is None:
            raise ValueError
        if not self.has_source:
            raise ValueError
        if not other.has_sink:
            raise ValueError
        self.source = other.sink.gen_source(**kw)
