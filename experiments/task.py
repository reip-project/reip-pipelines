from stopwatch import StopWatch
from base import *
import traceback


class Task(Graph, Worker):
    def __init__(self, name, graph=None, debug=True, verbose=False):
        Worker.__init__(self, name, graph=graph, debug=verbose)
        Graph.__init__(self, name, debug=verbose)  # overrides Worker.__enter__() and Worker.__exit__()
        self._manager_conn, self._worker_conn = mp.Pipe()
        self.debug = debug
        self.verbose = verbose
        self._process = None
        self._sw = StopWatch(name)
        self._was_running = False
        self._quit = mp.Value(c_bool, False, lock=False)

    @property
    def exception(self):
        if self._manager_conn.poll():
            self._exception = self._manager_conn.recv()
        return self._exception

    def remote(self, func, *args, **kwargs):
        self._manager_conn.send((func.__name__, args, kwargs))
        ret = self._manager_conn.recv()
        if self.error:
            self._exception = ret
            self.join()
            raise Exception("Remote exception in task %s" % self.name) from ret[0]
        return ret

    def _poll(self):
        if self._worker_conn.poll():
            func, args, kwargs = self._worker_conn.recv()
            ret = getattr(self, func)(*args, **kwargs)
            self._worker_conn.send(ret)

    # Worker implementation

    def reset(self):
        Worker.reset(self)
        self._sw.reset()
        self._was_running = False
        self._quit.value = False

    def spawn(self, wait_ready=True):
        if self.verbose:
            print("Spawning task %s.." % self.name)

        self.reset()
        self._process = mp.Process(target=self._target, name=self.name, daemon=True)
        self._process.start()

        if wait_ready:
            self.wait_ready()

    def _target(self):
        if self.verbose:
            print("Spawned task", self.name)

        try:
            self._quit.value = False
            self._run()
            if self.error:
                self._worker_conn.send(self._exception)

            while not self._quit.value:  # to preserve stats between terminate() and join()
                self._poll()
        except Exception as e:
            tb = traceback.format_exc()
            self._exception = (e, tb)
            self._error.value = True
            self._done.value = True
            print(RED + tb + END)
            try:
                self.join_all()
            except Exception as e2:
                print(RED + "Task %s failed to join blocks after previous exception:\n" % self.name, e2, END)
                # raise e2  # You can still rise this exception if need to
            self._worker_conn.send(self._exception)

        if self.verbose:
            print("Exiting task %s.." % self.name)

    def _run(self):
        self._sw.tick()

        with self._sw("spawn"):
            self.spawn_all()
        self.check_errors()

        if self.debug:
            print("Task %s spawned blocks in %.4f sec" % (self.name, self._sw["spawn"]))

        self._ready.value = True
        # self.start()  # auto_start?

        try:
            while not self._terminate.value:
                if self.running:
                    if not self._was_running:
                        self.start_all()
                        self._was_running = True
                    with self._sw("running"):
                        time.sleep(1e-3)
                else:
                    if self._was_running:
                        self.stop_all()
                        self._was_running = False
                    with self._sw("waiting"):
                        time.sleep(1e-3)
                self._poll()
                self.check_errors()
        except KeyboardInterrupt:
            pass

        with self._sw("join"):
            self.join_all()
        self.check_errors()

        if self.debug:
            print("Task %s joined blocks in %.4f sec" % (self.name, self._sw["join"]))

        self._sw.tock()
        self._done.value = True

        if self.debug:
            print("Task %s Done after %.4f sec" % (self.name, self._sw[""]))

    def join(self, auto_terminate=True):
        if auto_terminate:
            self.terminate()

        self._quit.value = True
        self._process.join(timeout=0.1)

        if self.verbose:
            print("Joined task", self.name)

    # Manager implementation

    def stats(self):
        s = Graph.stats(self)
        s.append((self.name, self._sw))
        return s

    def __str__(self):
        return Graph.__str__(self) + "\n" + str(self._sw)


if __name__ == '__main__':
    from block import Block

    # with Graph("Graph", debug=True) as g:
    with Task("Task", verbose=True) as t:
        b = Block("Block", verbose=True, max_rate=None)

    # t.run(duration=0.1)
    # g.run(duration=0.1)
    Graph.default.run(duration=0.1)
