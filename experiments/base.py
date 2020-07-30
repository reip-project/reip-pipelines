import multiprocessing as mp
from ctypes import c_bool
import time

RED = '\033[91m'
END = '\033[0m'


class Worker:
    def __init__(self, name, manager=None):
        self.name = name
        self._manager = manager or Manager.default  # Too much to pickle (contains all workers)
        self._manager.add(self)
        # (manager or Manager.default).add(self)
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

    def __enter__(self):
        print("Worker in")
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Worker out")
        self.stop()

    def spawn(self, wait_ready=True):
        raise NotImplementedError

    def start(self):
        if not self.ready:
            raise RuntimeError("Worker %s not ready to start" % self.name)
        else:
            self._running.value = True

    def remote(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def run(self):
        raise NotImplementedError

    def stop(self):
        if not self.running:
            raise RuntimeError("Worker %s not running" % self.name)
        else:
            self._running.value = False

    def terminate(self, wait_done=True):
        self._terminate.value = True
        if wait_done:
            while not self.done:
                time.sleep(1e-5)

    def join(self, auto_terminate=True):
        raise NotImplementedError

    def get_stats(self):
        return None

    def print_stats(self):
        pass


class Manager:
    default = None  # the default Manager instance
    _previous = None  # the previous default Manager instance

    def __init__(self):
        self.workers = []

    # Global instance management

    @classmethod
    def get_default(cls):
        return cls.default

    def __enter__(self):
        print("Manager in")
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Manager out")
        self.restore_previous()

    def as_default(self):
        self._previous, Manager.default = Manager.default, self
        return self

    def restore_previous(self):
        if self._previous is not None:
            Manager.default, self._previous = self._previous, None
        return self

    # Worker management

    def add(self, worker):
        if isinstance(worker, Worker):
            self.workers.append(worker)
            setattr(self, worker.name, worker)

    def __getitem__(self, key):
        return getattr(self, key)

    def spawn_all(self, wait_ready=True):
        for worker in self.workers:
            worker.spawn(wait_ready=False)
        if wait_ready:
            self.wait_all_ready()

    def wait_all_ready(self):
        for worker in self.workers:
            while not worker.ready:
                time.sleep(1e-5)

    def start_all(self):
        for worker in self.workers:
            worker.start()

    def check_errors(self):
        for worker in self.workers:
            if worker.error:
                raise Exception("Worker failed") from worker.exception

    def stop_all(self):
        for worker in self.workers:
            worker.stop()

    def terminate_all(self, wait_done=True):
        for worker in self.workers:
            worker.terminate(wait_done=False)
        if wait_done:
            self.wait_all_done()

    def wait_all_done(self):
        for worker in self.workers:
            while not worker.done:
                time.sleep(1e-5)

    def join_all(self, auto_terminate=True):
        if auto_terminate:
            self.terminate_all()
        for worker in self.workers:
            worker.join(auto_terminate=False)

    def get_stats(self):
        return [worker.remote(worker.get_stats) for worker in self.workers]

    def print_stats(self):
        for worker in self.workers:
            worker.remote(worker.print_stats)


# Create an initial default Manager
Manager.default = Manager()


if __name__ == '__main__':
    pass
