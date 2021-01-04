import time
from contextlib import contextmanager
import reip
from reip.util import text
import remoteobj


class BaseAgent:
    _delay = 1e-6
    ready = done = terminated = False
    _EXCEPT_CLASS = remoteobj.LocalExcept

    def __init__(self, name=None, graph=None):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = reip.Graph.register_instance(self, graph)
        self.log = reip.util.logging.getLogger(self)
        self._except = self._EXCEPT_CLASS()

    def _reset_state(self):
        self._except.clear()




    def run(self, duration=None, **kw):
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, wait=True, raise_exc=True):
        try:
            with self._except('spawn', raises=False, log=self.log):
                self.spawn(wait=wait)
            yield self
        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            self.terminate()
        finally:
            self.join(raise_exc=raise_exc)

    def wait(self, duration=None):
        for _ in reip.util.iters.timed(reip.util.iters.sleep_loop(self._delay), duration):
            if self.done or self.error:
                return True

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)



    def spawn(self, wait=True):
        self.ready = True

    def join(self, raise_exc=True):
        self.done = True

    def terminate(self):
        self.terminated = True



    @property
    def _exception(self):
        return self._except.last

    @property
    def error(self):
        return self._exception is not None

    def raise_exception(self):
        self._except.raise_any()

    def log_exception(self):
        for e in self._except.all():
            self.log.exception(e)




    def __export_state__(self):
        return self.__dict__

    def __import_state__(self, state):
        self.__dict__.update(state)
