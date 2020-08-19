import time
import traceback
import multiprocessing as mp
from ctypes import c_bool

import reip
from reip.util.iters import timed, loop
from reip.util import remote, text


class Task(reip.Graph):
    _exception = None
    _process = None
    _delay = 1#e-5

    def __init__(self, *blocks, graph=None):
        super().__init__(*blocks, graph=graph)
        self.remote = remote.RemoteProxy(self)
        self._terminated = mp.Value(c_bool, False)
        self._error = mp.Value(c_bool, False)

    # main run loop

    def _run(self, duration=None):
        print(text.b_(text.green('Starting'), self), flush=True)
        self.remote.listening = True  # XXX: let the main process know that it's listening
        try:
            # initialize
            super().spawn()
            print(text.b_(text.green('Ready'), self), flush=True)

            # main loop
            for _ in timed(loop(), duration):
                if super().terminated or super().error:
                    break

                self.remote.poll_until_clear()
                time.sleep(self._delay)

            # send empty (successful) result
            self.remote._local.put((None, None, None))

        except Exception as e:
            # any exception, print tb
            print(text.b_(
                text.red(f'Exception occurred in {self}'),
                text.red(traceback.format_exc()),
            ), flush=True)
            self.error = True

            # send exception
            self.remote._local.put((None, None, e))
        except KeyboardInterrupt as e:
            print(text.b_(
                text.yellow('Interrupting'), self, text.yellow('--')))
        finally:
            super().terminate()
            super().join(terminate=False)
            self.error = super().error  # get child errors before closing, just in case
            self.remote.poll_until_clear()
            self.remote.listening = False

    # process management

    def spawn(self, wait=True):
        if self._process is not None:  # only start once
            return

        print(text.b_(text.blue('Spawning'), self))
        self._process = mp.Process(target=self._run, daemon=True)
        self._process.start()
        if wait:
            self.wait_until_ready()
        self._check_errors()

    def join(self, timeout=0.5):
        if self._process is None:
            return

        print(text.b_(text.blue('Joining'), self))
        self.remote.super.join(default=None)  # join children
        self._process.join(timeout=timeout)  # join process
        self._process = None
        self._check_errors()

    def _check_errors(self):
        # raise any exceptions
        result = self.remote.get_result(None, wait=False)
        if result is not None:  # returns None if already closed.
            x, exc = result
            if self._exception is not None:
                raise Exception(f'Exception in {self}') from self._exception

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            self.remote.poll_until_clear()
            time.sleep(self._delay)

    # children state

    @property
    def ready(self):
        return remote.retrieve(self.remote.super.ready, default=False)

    @property
    def running(self):
        return remote.retrieve(self.remote.super.running, default=False)

    @property
    def terminated(self):
        return (
            self._terminated.value or
            remote.retrieve(self.remote.super.terminated, default=True)) # default ???

    @property
    def done(self):
        return remote.retrieve(self.remote.super.done, default=True) # default ???

    @property
    def error(self):
        return (
            self._error.value or
            remote.retrieve(self.remote.super.error, default=False))

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
