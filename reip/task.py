import time
from contextlib import contextmanager
import multiprocessing as mp
from ctypes import c_bool
import remoteobj

import reip
from reip.util import iters, text


class Task(reip.Graph):
    _exception = None
    _process = None
    _delay = 1e-5

    def __init__(self, *blocks, graph=None, **kw):
        super().__init__(*blocks, graph=graph, **kw)
        self.remote = remoteobj.Proxy(self)
        self._catch = remoteobj.Except()
        self._terminated = mp.Value(c_bool, False)
        self._error = mp.Value(c_bool, False)
        self._done = mp.Value(c_bool, False)

    # main run loop

    def run(self, duration=None, **kw):
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, raise_exc=True):
        try:
            self.spawn()
            yield self
        except KeyboardInterrupt:
            self.terminate()
        finally:
            self.join(raise_exc=raise_exc)

    def wait(self, duration=None):
        for _ in reip.util.iters.timed(reip.util.iters.sleep_loop(self._delay), duration):
            if self.done or self.error:
                return True

    def _run(self, duration=None):
        self.log.info(text.green('Starting'))
        with self._catch(raises=False):
            with self.remote.listen_():
                try:
                    # initialize
                    super().spawn()
                    self.log.info(text.green('Ready'))

                    # main loop
                    for _ in iters.timed(iters.sleep_loop(self._delay), duration):
                        if super().done or super().error:
                            break

                        self.remote.process_requests()
                    self.error = super().error
                except Exception:
                    self.error = True
                    raise
                except KeyboardInterrupt as e:
                    self.log.info(text.yellow('Interrupting'))
                finally:
                    super().join(raise_exc=False)
                    self.remote.process_requests()
                    for b in self.blocks:
                        for exc in b.all_exceptions:
                            self._catch.set(exc, b.name)
                    self.log.info(text.green('Done'))


    # process management

    def spawn(self, wait=True):
        if self._process is not None:  # only start once
            return
        self.done = False
        self._catch.clear()
        self._process = mp.Process(target=self._run, daemon=True)
        self._process.start()
        if wait:
            self.wait_until_ready()
        self.raise_exception()

    def join(self, *a, timeout=0.5, raise_exc=True, **kw):
        if self._process is None:
            return
        self.remote.super.join(*a, raise_exc=False, default=None, **kw)  # join children
        self._process.join(timeout=timeout)  # join process
        self.done = True
        self._process = None
        self.all_exceptions = self._catch.all()
        if raise_exc:
            self.raise_exception()

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    @property
    def _exception(self):
        return self._catch.get()

    def raise_exception(self):
        self._catch.raise_any()

    # children state

    @property
    def ready(self):
        return self.remote.super.ready.get_(default=False)

    @property
    def running(self):
        return self.remote.super.running.get_(default=False)

    @property
    def terminated(self):
        return (
            self._terminated.value or
            self.remote.super.terminated.get_(default=True)) # default ???

    @property
    def done(self):
        return self._done.value or self.remote.super.done.get_(default=False) # default ???

    @property
    def error(self):
        return self._error.value or self.remote.super.error.get_(default=False)

    @done.setter
    def done(self, value):
        self._done.value = value

    @terminated.setter
    def terminated(self, value):
        self._terminated.value = value

    @error.setter
    def error(self, value):
        self._error.value = value

    # block control

    def pause(self):
        return self.remote.super.pause()

    def resume(self):
        return self.remote.super.resume()

    def terminate(self):
        self.terminated = True
        return self.remote.super.terminate(default=None)

    # def _reset_state(self):
    #     return self.remote.super._reset_state()

    # debug

    def summary(self):
        return self.remote.super.summary()

    def status(self):
        return self.remote.super.status()

    def print_stats(self):
        return self.remote.super.print_stats()
