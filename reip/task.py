import time
import functools
from contextlib import contextmanager
import multiprocessing as mp
from ctypes import c_bool
import remoteobj

import reip
from reip.util import iters, text


# def _remote_prop()

def _remote_property(name):
    def inner(self):
        return self.remote.attrs_(name).get_(_default=lambda: getattr(self, name))
    inner.__name__ = name
    return property(inner)

def _remote_func(name):
    def inner(self, *a, **kw):
        return self.remote.attrs_(name)(*a, **kw, _default=getattr(self, name))
    inner.__name__ = name
    return inner


class Task(reip.Graph):
    all_exceptions = ()
    _exception = None
    _process = None
    _delay = 1e-4

    def __init__(self, *blocks, graph=None, **kw):
        super().__init__(*blocks, graph=graph, **kw)
        self.remote = remoteobj.Proxy(self, fulfill_final=True)
        self._except = remoteobj.Except()

    def __repr__(self):
        return self.remote.super.attrs_('__repr__')(_default=None) or super().__repr__()

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

    def _run(self, duration=None, _ready_flag=None):
        self.log.debug(text.blue('Starting'))
        try:
            with self.remote.listen_():
                try:
                    # initialize
                    super().spawn(wait=False, _ready_flag=_ready_flag)
                    while not super().error and not super().done:
                        if super().ready:
                            self.log.info(text.green('Ready'))
                            break
                        self.remote.process_requests()
                        time.sleep(self._delay)

                    # main loop
                    for _ in iters.timed(iters.sleep_loop(self._delay), duration):
                        if super().done or super().error:
                            break
                        self.remote.process_requests()

                except KeyboardInterrupt as e:
                    self.log.info(text.yellow('Interrupting'))
                finally:
                    self.log.info(text.yellow('Joining'))
                    super().join(raise_exc=False)
                    self.log.info(text.green('Done'))

                    # transfer exceptions
                    for b in self.blocks:
                        for exc in b.all_exceptions:
                            self._except.set(exc, b.name)

                    if _ready_flag is None:
                        print(self.stats_summary())
        # except BaseException as e:
        #     self.log.exception(e)
        finally:
            _ = super().__export_state__()
            # self._except.set_result('asdf')
            # self.log.info('state remote {}'.format(_))
            return _



    # process management
    _delay = 1
    def spawn(self, wait=True, _ready_flag=None):
        self.log.debug(text.blue('Spawning'))
        if self._process is not None:  # only start once
            return

        self._reset_state()
        # self._except = remoteobj.Except()
        # self._process = mp.Process(target=self._run, kwargs=dict(_ready_flag=_ready_flag), daemon=True)
        self._process = remoteobj.util.process(self._run, _ready_flag=_ready_flag)
        self._except = self._process.exc
        self._process.start()

        if wait:
            self.wait_until_ready()
        self.raise_exception()

    def join(self, *a, timeout=10, raise_exc=True, **kw):
        if self._process is None:
            return

        def sett(*a, **kw):
            print('set', a, kw)
            return oldset(*a, **kw)
        oldset, self._except.set = self._except.set, sett

        self.remote.super.join(*a, raise_exc=False, _default=None, **kw)  # join children
        # self._process.join(timeout=timeout)  # join process
        self._process.join(timeout=timeout, raises=False)
        # self.log.info('process q len: {} {}'.format(self._process.exc._local.poll(), self._process.exc._remote.poll()))
        # self.log.info('process result: {}'.format(self._process.result))
        self.__import_state__(self._process.result)
        self._process = None
        self.all_exceptions = self._except.all()
        if raise_exc:
            self.raise_exception()

    def _reset_state(self):
        self._except.clear()

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    @property
    def _exception(self):
        return self._except.get()

    def raise_exception(self):
        self._except.raise_any()

    def __export_state__(self):
        return self.remote.super.attrs_('__export_state__')(_default=super().__export_state__)

    # children state

    @property
    def ready(self):
        return self.remote.super.ready.get_(default=False)

    @property
    def running(self):
        return self.remote.super.running.get_(default=False)

    @property
    def terminated(self):
        sup = super()
        return self.remote.super.terminated.get_(default=lambda: sup.terminated)

    @property
    def done(self):
        sup = super()
        return self.remote.super.done.get_(default=lambda: sup.done)

    @property
    def error(self):
        sup = super()
        return self.remote.super.error.get_(default=lambda: sup.error or bool(self._except.all()))

    # block control

    def pause(self):
        return self.remote.super.pause()

    def resume(self):
        return self.remote.super.resume()

    def terminate(self):
        return self.remote.super.terminate(_default=None)

    # debug

    def stats(self):
        return self.remote.super.stats(_default=super().stats)

    def summary(self):
        return self.remote.super.summary(_default=super().stats)

    def status(self):
        return self.remote.super.status(_default=super().stats)

    def stats_summary(self):
        return self.remote.super.stats_summary(_default=super().stats_summary)
