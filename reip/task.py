import time
import remoteobj
import multiprocessing as mp
import reip
from reip.util import iters, text

#import logging
#mplog = mp.log_to_stderr()
#mplog.setLevel(logging.DEBUG)
#mplog.setLevel(mp.SUBDEBUG)


class Task(reip.Graph):
    _process = None
    _delay = 1e-4
    _startup_delay = 0.1

    def __init__(self, *blocks, graph=None, **kw):
        super().__init__(*blocks, graph=graph, **kw)
        self.remote = remoteobj.Proxy(self, fulfill_final=True)
        self._except = remoteobj.Except()

    def __repr__(self):
        return self.remote.super.attrs_('__repr__')(_default=self.__local_repr)

    def __local_repr(self):
        self._pull_process_result()
        return super().__repr__()

    # main run loop

    def _run(self, duration=None, _controlling=False, _spawn_flag=None, _ready_flag=None):
        if _spawn_flag is not None:
            _spawn_flag.wait()
        try:
            time.sleep(self._startup_delay)
            with self._except(raises=False), self.remote.listen_(bg=False):
                try:
                    # initialize
                    super().spawn(wait=False, _controlling=_controlling, _ready_flag=_ready_flag)
                    self.log.debug(text.green('Children Spawned!'))
                    while True:
                        if super().error or super().done:
                            return
                        if super().ready:
                            self.log.debug(text.green('Ready'))
                            break
                        self.remote.process_requests()
                        time.sleep(self._delay)

                    # main loop
                    for _ in iters.timed(iters.sleep_loop(self._delay), duration):
                        if super().done or super().error:
                            break
                        self.remote.process_requests()
                except Exception as e:
                    self.log.exception(e)
                except KeyboardInterrupt as e:
                    self.log.info(text.yellow('Interrupting'))
                finally:
                    super().join(raise_exc=False)
        finally:
            self._except.set_result(super().__export_state__())
            #return _



    # process management
    def spawn(self, wait=True, _controlling=True, _ready_flag=None, _spawn_flag=None):
        if self._process is not None:  # only start once
            return
        self.controlling = _controlling

        self._reset_state()
        self._started_process = False
        self.log.debug('Spawning process')
        self._process = mp.Process(target=self._run, kwargs=dict(_spawn_flag=_spawn_flag), daemon=True) #, kwargs=dict(_ready_flag=_ready_flag, _controlling=_controlling)
        self._process.start()
        self._started_process = True

        if wait:
            self.wait_until_ready()
        if self.controlling:
            self.raise_exception()

    def join(self, *a, timeout=10, raise_exc=True, **kw):
        if self._process is None:
            return

        self.log.debug(text.yellow('Joining'))
        self.remote.super.join(*a, raise_exc=False, _default=None, **kw)  # join children
        self._process.join(timeout=timeout)
        self.__import_state__(self._except.get_result()) #self._process.result)
        self._started_process = False

        self._process = None
        if raise_exc:
            self.raise_exception()
        self.log.debug(text.green('Done'))

    def _pull_process_result(self):
        # NOTE: this is to update the state when the remote process has finished
        r = self._except.get_result()
        if r is not None:
            self.__import_state__(r)
            #self.log.info('result: {}'.format(r))

    def _pull_then_get(self, name):
        self._pull_process_result()
        return getattr(super(), name)

    def _pull_then_call(self, name, *a, **kw):
        return self._pull_then_get(name)(*a, **kw)

    def __export_state__(self):
        return self.remote.super.attrs_('__export_state__')(_default=None)

    def _unexpected_exit(self):
        exited = self._started_process and self._process is not None and not self._process.is_alive()
        if exited:
            self.remote._fulfill_final, _ff = False, self.remote._fulfill_final
            self.remote.listening_ = False
            self.remote._fulfill_final = _ff
            self.join()
        return exited

    # children state

    @property
    def ready(self):
        return not self._unexpected_exit() or remoteobj.get(self.remote.super.ready, default=False)

    @property
    def running(self):
        return not self._unexpected_exit() or remoteobj.get(self.remote.super.running, default=False)

    @property
    def terminated(self):
        return self._unexpected_exit() or remoteobj.get(self.remote.super.terminated, default=lambda: self._pull_then_get('terminated'))

    @property
    def done(self):
        return self._unexpected_exit() or remoteobj.get(self.remote.super.done, default=lambda: self._pull_then_get('done'))

    @property
    def error(self):
        return self._unexpected_exit() or remoteobj.get(self.remote.super.error, default=lambda: self._pull_then_get('error'))

    # block control

    def pause(self):
        return self.remote.super.pause()

    def resume(self):
        return self.remote.super.resume()

    def close(self):
        return self.remote.super.close(_default=None)

    def terminate(self):
        return self.remote.super.terminate(_default=None)

    # debug

    def stats(self):
        return self.remote.super.stats(_default=lambda: self._pull_then_call('stats'))

    def summary(self):
        return self.remote.super.summary(_default=lambda: self._pull_then_call('summary'))

    def status(self):
        return self.remote.super.status(_default=lambda: self._pull_then_call('status'))

    def stats_summary(self):
        return self.remote.super.stats_summary(_default=lambda: self._pull_then_call('stats_summary'))
