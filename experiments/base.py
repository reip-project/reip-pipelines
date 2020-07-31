import multiprocessing as mp
from ctypes import c_bool
import time

RED = '\033[91m'
END = '\033[0m'


class Worker:
    def __init__(self, name, graph=None, debug=False):
        self.name = name
        self._debug = debug
        self._graph_name = None
        (graph or Graph.default).add(self)
        self._ready = mp.Value(c_bool, False, lock=False)
        self._running = mp.Value(c_bool, False, lock=False)
        self._terminate = mp.Value(c_bool, False, lock=False)
        self._error = mp.Value(c_bool, False, lock=False)
        self._done = mp.Value(c_bool, False, lock=False)
        self._exception = None

    @property
    def ready(self):
        return self._ready.value

    @property
    def running(self):
        return self._running.value

    @property
    def error(self):
        return self._error.value

    @property
    def done(self):
        return self._done.value

    @property
    def exception(self):
        return self._exception

    def remote(self, func, *args, **kwargs):
        return getattr(self, func.__name__)(*args, **kwargs)

    def __enter__(self):
        if self._debug:
            print("Worker %s in" % self.name)
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._debug:
            print("Worker %s out" % self.name)
        self.stop()

    def reset(self):
        self._ready.value, self._done.value = False, False
        self._running.value, self._terminate.value = False, False
        self._error.value, self._exception = False, None

    def spawn(self, wait_ready=True):
        raise NotImplementedError

    def wait_ready(self):
        while not self.ready and not self.error:
            time.sleep(1e-5)

    def start(self):
        if not self.ready:
            raise RuntimeError("Worker %s not ready to start" % self.name)
        else:
            self._running.value = True

    def run(self, duration=None):
        self.spawn()

        if self.error:
            self.join()
            raise RuntimeError("Worker %s failed to spawn" % self.name) from self.exception[0]

        with self:
            try:
                t = time.time()
                while (duration is None or time.time() - t < duration) and not self.error:
                    time.sleep(1e-3)
                    # do something else
            except KeyboardInterrupt:
                pass
        self.join()

        if self.error:
            raise RuntimeError("Worker %s failed" % self.name) from self.exception[0]
        else:
            print(self)

    def stop(self):
        if not self.running:
            raise RuntimeError("Worker %s not running" % self.name)
        else:
            self._running.value = False

    def terminate(self, wait_done=True):
        self._terminate.value = True
        if wait_done:
            self.wait_done()

    def wait_done(self):
        while not self.done and not self.error:
            time.sleep(1e-5)

    def join(self, auto_terminate=True):
        raise NotImplementedError

    def stats(self):
        return None

    def __str__(self):
        return ""


class Graph:
    default = None  # the default Graph instance
    _previous = None  # the previous default Graph instance

    def __init__(self, name, debug=False):
        self._name = name
        self._debug = debug
        self._workers = []

    # Global instance management

    @classmethod
    def get_default(cls):
        return cls.default

    def __enter__(self):
        if self._debug:
            print("Graph %s in" % self._name)
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._debug:
            print("Graph %s out" % self._name)
        self.restore_previous()

    def as_default(self):
        self._previous, Graph.default = Graph.default, self
        return self

    def restore_previous(self):
        if self._previous is not None:
            Graph.default, self._previous = self._previous, None
        return self

    # Workers management

    def add(self, worker):
        if isinstance(worker, Worker):
            if worker.name in [w.name for w in self._workers]:
                raise RuntimeError("Worker %s already exists in graph %s" % (worker.name, self._name))
            self._workers.append(worker)
            worker._graph_name = self._name
            setattr(self, worker.name, worker)

    def __getitem__(self, key):
        return getattr(self, key)

    def spawn_all(self, wait_ready=True):
        for worker in self._workers:
            worker.spawn(wait_ready=False)
        if wait_ready:
            self.wait_all_ready()

    def wait_all_ready(self):
        for worker in self._workers:
            worker.wait_ready()

    def start_all(self):
        for worker in self._workers:
            worker.start()

    def check_errors(self, silent=False):
        for worker in self._workers:
            if worker.error:
                if silent:
                    if self._debug:
                        print("Error in worker %s:" % worker.name, worker.exception)
                    return True
                else:
                    self.join_all()
                    print(RED + worker.exception[1] + END)
                    raise Exception("Worker %s failed" % worker.name) from worker.exception[0]
        return False

    def run(self, duration=None):
        self.spawn_all()
        self.check_errors()

        self.start_all()
        try:
            t = time.time()
            while (duration is None or time.time() - t < duration) and not self.check_errors(silent=True):
                time.sleep(1e-3)
                # do something else
        except KeyboardInterrupt:
            pass
        self.stop_all()

        self.terminate_all()
        self.check_errors()

        print(self)
        self.join_all()

    def stop_all(self):
        for worker in self._workers:
            worker.stop()

    def terminate_all(self, wait_done=True):
        for worker in self._workers:
            worker.terminate(wait_done=False)
        if wait_done:
            self.wait_all_done()

    def wait_all_done(self):
        for worker in self._workers:
            worker.wait_done()

    def join_all(self, auto_terminate=True):
        if auto_terminate:
            self.terminate_all()
        for worker in self._workers:
            worker.join(auto_terminate=auto_terminate)

    def stats(self):
        return [worker.remote(worker.stats) for worker in self._workers]

    def __str__(self):
        return "\n".join([worker.remote(worker.__str__) for worker in self._workers])


# Create an initial default Graph
Graph.default = Graph("Default")
