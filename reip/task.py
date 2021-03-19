import time
import remoteobj
import reip
from reip.util import iters, text


class Task(reip.Graph):
    _process = None
    _delay = 1e-3

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

    def _run(self, duration=None, _controlling=True, _ready_flag=None):
        self.log.debug(text.blue('Starting'))
        try:
            with self._except(raises=False), self.remote.listen_(bg=False):
                try:
                    # initialize
                    super().spawn(wait=False, _controlling=_controlling, _ready_flag=_ready_flag)
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

                except KeyboardInterrupt as e:
                    self.log.info(text.yellow('Interrupting'))
                finally:
                    super().join(raise_exc=False)
        finally:
            _ = super().__export_state__()
            return _



    # process management
    def spawn(self, wait=True, _controlling=True, _ready_flag=None):
        if self._process is not None:  # only start once
            return
        self.controlling = _controlling

        self._reset_state()
        self._process = remoteobj.util.process(self._run, _ready_flag=_ready_flag, _controlling=_controlling)
        self._except = self._process.exc
        self._process.start()

        if wait:
            self.wait_until_ready()
        if self.controlling:
            self.raise_exception()

    def join(self, *a, timeout=10, raise_exc=True, **kw):
        if self._process is None:
            return

        self.log.debug(text.yellow('Joining'))
        self.remote.super.join(*a, raise_exc=False, _default=None, **kw)  # join children
        self._process.join(timeout=timeout, raises=False)
        self.__import_state__(self._process.result)

        self._process = None
        if raise_exc:
            self.raise_exception()
        self.log.debug(text.green('Done'))

    def _pull_process_result(self):
        # NOTE: this is to update the state when the remote process has finished
        if self._process is not None:
            r = self._process.result
            self.__import_state__(r)
            #self.log.info('result: {}'.format(r))

    def __export_state__(self):
        return self.remote.super.attrs_('__export_state__')(_default=None)

    # children state

    @property
    def ready(self):
        return remoteobj.get(self.remote.super.ready, default=False)

    @property
    def running(self):
        return remoteobj.get(self.remote.super.running, default=False)

    @property
    def terminated(self):
        return remoteobj.get(self.remote.super.terminated, default=self.__local_terminated)

    @property
    def done(self):
        return remoteobj.get(self.remote.super.done, default=self.__local_done)

    @property
    def error(self):
        return remoteobj.get(self.remote.super.error, default=self.__local_error)

    def __local_terminated(self):  # for when the remote process is not running
        self._pull_process_result()
        return super().terminated

    def __local_done(self):  # for when the remote process is not running
        self._pull_process_result()
        return super().done

    def __local_error(self):  # for when the remote process is not running
        self._pull_process_result()
        #self.log.debug('local error {} {}'.format(super().error, self))
        return super().error

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
        return self.remote.super.stats(_default=super().stats)

    def summary(self):
        return self.remote.super.summary(_default=super().summary)

    def status(self):
        return self.remote.super.status(_default=super().status)

    def stats_summary(self):
        return self.remote.super.stats_summary(_default=super().stats_summary)
