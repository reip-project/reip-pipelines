import time
import traceback
import multiprocessing as mp
from ctypes import c_bool

import reip
from reip.util.iters import timed, loop
from reip.util.remote import RemoteProxy
from reip.util import text


class Task(reip.Graph):
    _exception = None
    _process = None
    _delay = 1#e-5

    def __init__(self, *blocks, graph=None):
        super().__init__(*blocks, graph=graph)
        self.remote = RemoteProxy(self)
        self._terminated = mp.Value(c_bool, False)
        self._error = mp.Value(c_bool, False)

    # main run loop

    def _run(self, duration=None):
        print(text.b_(text.green('Starting'), self), flush=True)
        with self.remote.listen():  # I tried to have this done automatically thru hooks, but.. not working.
            try:
                # main loop
                super().spawn(wait=False)
                super().wait_until_ready()
                print(text.b_(text.green('Ready'), self), flush=True)
                for _ in timed(loop(), duration):
                    if super().terminated or super().error:
                        break

                    # if self.restart_failed_blocks():  # return true if a block is failed?
                    #     break
                    time.sleep(self._delay)

                # for b in self.blocks:
                #     if b.error:
                #         raise b._exception

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
                # if self.context_id is None:
                super().print_stats()

    def restart_failed_blocks(self):
        return self.remote.super.restart_failed_blocks()._

    # process management

    def spawn(self, wait=True):
        if self._process is not None:  # only start once
            return

        print(text.b_(text.blue('Spawning'), self))
        self._process = mp.Process(target=self._run, daemon=True)
        self._process.start()
        self._check_errors()

    def join(self, terminate=True, timeout=0.5):
        if self._process is None:
            return

        print(text.b_(text.blue('Joining'), self))
        self.remote.super.join(terminate=terminate)._  # join children
        self._process.join(timeout=timeout)  # join process
        self._process = None
        self._check_errors()

    def _check_errors(self):
        # raise any exceptions
        result = self.remote.get_result(None, wait=False)
        if result is not None:  # returns None if already closed.
            x, exc = result
            if self._exception is not None:
                print(387234787342, self._exception, type(self._exception))
                raise Exception(f'Exception in {self}') from self._exception

    def wait_until_ready(self):
        while not self.ready:
            time.sleep(self._delay)

    # children state

    @property
    def ready(self):
        return self.remote.super.ready._

    @property
    def running(self):
        return self.remote.super.running._

    @property
    def terminated(self):
        return self._terminated.value or self.remote.super.terminated._

    @property
    def done(self):
        return self.remote.super.done._

    @property
    def error(self):
        return self._error.value or self.remote.super.error._

    @terminated.setter
    def terminated(self, value):
        self._terminated.value = value

    @error.setter
    def error(self, value):
        self._error.value = value

    # block control

    def pause(self):
        return self.remote.super.pause()._

    def resume(self):
        return self.remote.super.resume()._

    def terminate(self):
        self.terminated = True
        return self.remote.super.terminate()._

    # def _reset_state(self):
    #     return self.remote.super._reset_state()._

    # debug

    def summary(self):
        return self.remote.super.summary()._

    def print_stats(self):
        return self.remote.super.print_stats()._
