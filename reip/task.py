import time
import traceback
import multiprocessing as mp
import remoteobj
import reip
from reip.util import iters, text


class Task(reip.Graph):
    _agent = None
    _delay = 1e-3

    def __init__(self, *blocks, graph=None, log_level='debug', **kw):
        super().__init__(*blocks, graph=graph, log_level=log_level, **kw)
        self.remote = remoteobj.Proxy(self, fulfill_final=True)
        # self._except = reip.exceptions.ExceptionTracker()#remoteobj.Except()
        self._should_exit = mp.Event()
        self._exited = mp.Event()

    def __repr__(self):
        if self._in_spawned_agent:
            return self.__repr()
        return self.remote.super.attrs_('__repr__')(_default=self.__local_repr)

    def __local_repr(self):
        self._pull_process_result()
        return self.__repr()

    def __repr(self):
        return '[{}({}) [{}], {} children]'.format(
            self.__class__.__name__, self.name, 
            f'agent: {"alive" if self._agent.is_alive() else "off"}' if self._agent is not None else 'none',
            len(self.children))

    def __str__(self):
        if self._in_spawned_agent:
            return self.__str()
        return self.remote.super.attrs_('__repr__')(_default=self.__local_str)

    def __local_str(self):
        self._pull_process_result()
        return self.__str()

    def __str(self):
        return '{}({}) [{}], {} children:{}\n'.format(
            self.__class__.__name__, self.name, 
            f'agent: {"alive" if self._agent.is_alive() else "off"}' if self._agent is not None else 'none',
            len(self.children),
            ''.join('\n' + text.indent(b) for b in self.children))

    # main run loop

    _in_spawned_agent = False
    def _run(self, duration=None, _controlling=True, _ready_flag=None, _spawn_flag=None):
        self._in_spawned_agent = True
        if _spawn_flag is not None:
            _spawn_flag.wait()  # don't print before this !!!!
        self.log.debug(text.blue('Started agent'))
        try:
            with self.remote.listen_(bg=False):  # self._except(raises=False), 
                try:
                    # initialize
                    try:
                        self.spawn(wait=False, _controlling=_controlling, _ready_flag=_ready_flag)
                    except BaseException:
                        self.terminate()
                        raise
                    while True:
                        if self.error or self.done or self._should_exit.is_set():
                            return
                        if self.ready:
                            self.log.info(text.green('Ready'))
                            break
                        self.remote.process_requests()
                        time.sleep(self._delay)

                    # main loop
                    for _ in iters.timed(iters.sleep_loop(self._delay), duration):
                        if self.done or self.error or self._should_exit.is_set():
                            break
                        self.remote.process_requests()

                except KeyboardInterrupt as e:
                    self.log.warning(text.yellow('Interrupting'))
                finally:
                    self.join(raise_exc=False)
        except KeyboardInterrupt as e:
            self.log.warning(text.yellow('Interrupting'))
        except Exception as e:
            self._exception = e #reip.exceptions.safe_exception(e)
            traceback.print_exc()
        finally:
            self.log.warning(text.yellow('Exiting'))
            self.remote.process_requests()
            self.remote.cancel_requests()
            _ = self.__export_state__()
            # self.log.info(str(_))
            return _
    
    def _reset_state(self):
        super()._reset_state()
        if not self._in_spawned_agent:
            self._should_exit.clear()
            self._exited.clear()


    # process management
    def spawn(self, wait=True, _controlling=True, _ready_flag=None, _spawn_flag=None):
        if self._in_spawned_agent:
            return super().spawn(wait=wait, _controlling=_controlling, _ready_flag=_ready_flag, _spawn_flag=_spawn_flag)

        if self._agent is not None:  # only start once
            return
        self._controlling = _controlling

        self.log.info(text.blue('Spawning'))
        self._reset_state()
        self._agent = reip.util.agent.Process(PickleMethod(self, '_run'), daemon=True)(
            _ready_flag=_ready_flag, _spawn_flag=_spawn_flag, _controlling=_controlling)
        self._agent.start()

        if wait:
            self.wait_until_ready()
        if self._controlling:
            self.raise_exception()

    def join(self, *a, timeout=10, close=True, raise_exc=True, **kw):
        if close:
            self.close()
        if self._in_spawned_agent:
            # self.log.info('joining children!')
            return super().join(*a, raise_exc=False, **kw)
        if self._agent is None:
            return

        # excs = self._except.all()
        # for e in excs:
        #     self.log.error(reip.util.excline(e))

        self.log.info(text.yellow('Joining'))
        self._should_exit.set()
        if self._agent.is_alive():
            self.remote.join(*a, raise_exc=False, _default=None, **kw)  # join children
            self._agent.join(timeout=timeout, raises=False)
        self.__import_state__(self._agent.result)
        self._agent = None

        if raise_exc:
            self.raise_exception()
        self.log.debug(text.green('Done'))

    def _pull_process_result(self):
        # NOTE: this is to update the state when the remote process has finished
        # self.log.info('checking process result')
        if self._agent is not None:
            if self._agent.finished.is_set():
                r = self._agent.result
                self._agent._result = None
                if r is not None:
                    self.__import_state__(r)
                # self.log.info('import state: {}'.format(r))

    def __export_state__(self):
        if self._in_spawned_agent:
            return super().__export_state__()
        return self.remote.super.attrs_('__export_state__')(_default=None)

    # children state

    @property
    def ready(self):
        if self._in_spawned_agent:
            return super().ready
        return remoteobj.get(self.remote.ready, default=False)

    @property
    def running(self):
        if self._in_spawned_agent:
            return super().running
        return remoteobj.get(self.remote.running, default=False)

    @property
    def terminated(self):
        if self._in_spawned_agent:
            return super().terminated
        return remoteobj.get(self.remote.terminated, default=self.__local_terminated)

    @property
    def done(self):
        if self._in_spawned_agent:
            return super().done
        return remoteobj.get(self.remote.done, default=self.__local_done)

    @property
    def error(self):
        if self._in_spawned_agent:
            return super().error
        return remoteobj.get(self.remote.error, default=self.__local_error)

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
        if self._in_spawned_agent:
            return super().pause()
        return self.remote.pause()

    def resume(self):
        if self._in_spawned_agent:
            return super().resume()
        return self.remote.resume()

    def close(self):
        if self._in_spawned_agent:
            return super().close()
        self._should_exit.set()
        return self.remote.close(_default=super().close)

    def terminate(self):
        if self._in_spawned_agent:
            return super().terminate()
        return self.remote.terminate(_default=super().terminate)

    # debug

    def stats(self):
        if self._in_spawned_agent:
            return super().stats()
        return self.remote.stats(_default=super().stats)

    def summary(self):
        if self._in_spawned_agent:
            return super().summary()
        return self.remote.summary(_default=super().summary)

    def status(self):
        if self._in_spawned_agent:
            return super().status()
        return self.remote.super.status(_default=super().status)

    def stats_summary(self):
        if self._in_spawned_agent:
            return super().stats_summary()
        return self.remote.stats_summary(_default=super().stats_summary)


class PickleMethod:
    def __init__(self, obj, attr):
        self.obj = obj
        self.__name__ = attr

    def __call__(self, *a, **kw):
        return getattr(self.obj, self.__name__)(*a, **kw)