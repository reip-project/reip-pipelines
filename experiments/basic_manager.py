'''Task and inter-process block calls all managed using multiprocessing Manager Proxies

Main difference between this and original REIP is that 
the manager forks as soon as it's created. I tried to 
change this and start it when the graph was run, but 
I don't think it's possible without rewriting a lot.

'''
import sys
import time
import threading
from contextlib import contextmanager
import multiprocessing as mp
from multiprocessing.managers import SyncManager, MakeProxyType, public_methods, dispatch

def _indent(x, n=2):
    return ''.join(' '*n + x for x in str(x).splitlines(keepends=True))


class AgentExit(BaseException):
    pass

class Worker:
    _delay = 0.1
    def run(self, duration=None, **kw):
        '''Run a block synchronously.'''
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self):
        '''Run a block while we are inside the context manager.'''
        try:
            self.spawn()
            yield self
        except KeyboardInterrupt:
            print('Interrupted')
            self.terminate()
        finally:
            self.join()

    def wait(self, duration=None):
        '''Wait until the block is done.'''
        t0 = time.time()
        while True:
            if not self.running:
                return True
            if duration and time.time() - t0 > duration:
                break
            time.sleep(self._delay)



class Graph(Worker):
    _manager = None
    _default = None

    # basic

    def __init__(self):
        self.children = []
        if Graph._default: 
            Graph._default.__append__(self)

    def __str__(self) -> str:
        ch = ''.join(f'\n{_indent(b).rstrip()}' for b in self.children)
        return f'[{self.__class__.__name__}{ch} ]'

    # context capturing

    def __enter__(self):
        self.__previous, Graph._default = Graph._default, self
        return self

    def __exit__(self, *e):
        self.__previous, Graph._default = None, self.__previous

    def __append__(self, child):
        self.children.append(child)

    # control

    def spawn(self):
        for b in self.children:
            b.spawn()

    def close(self):
        for b in self.children:
            b.close()

    def terminate(self):
        for b in self.children:
            b.terminate()

    def join(self):
        self.close()
        for b in self.children:
            b.join()

    @property
    def running(self):
        return all(b.running for b in self.children)

Graph._default = Graph()




# Task multiprocessing Manager weirdness

def _proxy__getattr_(self, name): return getattr(self, name)
def _proxy__setattr_(self, name, value): return setattr(self, name, value)

def prop(name, readonly=False):
    return property(
        lambda self: self._callmethod('_proxy__getattr_', (name,)), 
        None if readonly else (lambda self, value: self._callmethod('_proxy__setattr_', (name, value))))

class _GraphCompat(Graph):
    _proxy__getattr_ = _proxy__getattr_
    _proxy__setattr_ = _proxy__setattr_
_GraphCompat.__name__ = 'Task'

# class Task:
#     _REIP__CREATE_TASK_FROM_MANAGER = True
#     def __new__(cls, *a, manager=None, **kw):
#         if cls._REIP__CREATE_TASK_FROM_MANAGER:
#             x = (manager or TaskManager()).Task(*a, **kw)
#             return init_noop(x)
#         return super().__new__(cls)

_Graph_methods = public_methods(_GraphCompat) + ['__str__', '_proxy__getattr_', '_proxy__setattr_', '__append__']
class TaskProxy(MakeProxyType('Task', _Graph_methods)):
    _REIP__CREATE_TASK_FROM_MANAGER = False
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if Graph._default:
            Graph._default.__append__(self)
    __enter__ = Graph.__enter__
    __exit__ = Graph.__exit__
    name = prop('name')
    running = prop('running')




class TaskManager(SyncManager):
    # _Server = MyServer
    class _Server(SyncManager._Server):
        # let us dynamically register classes
        public = SyncManager._Server.public + ['dynamic_register']
        def dynamic_register(self, c, name, x):
            self.registry[name] = x

    def __init__(self, *, start=True, **kw):
        if 'ctx' not in kw:
            kw['ctx'] = mp.get_context()
        super().__init__(**kw)
        if start:
            self.start()

    def dynamic_register(self, name, *a, **kw):
        self.register(name, *a, **kw)
        x = self._registry[name]
        conn = self._Client(self._address, authkey=self._authkey)
        try:
            dispatch(conn, None, 'dynamic_register', [name, x])
        finally:
            conn.close()
        return getattr(self, name)


TaskManager.register('Task', _GraphCompat, TaskProxy)

def Task(*a, manager=None, **kw):
    return (manager or TaskManager()).Task(*a, **kw)


def join_all(threads, timeout, step=0.1):
    start = cur_time = time.time()

    while cur_time <= (start + timeout) and not all(not t.is_alive() for t in threads):
        first = True
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=step if first else 0)
                first = False
        cur_time = time.time()
    still_running = [t for t in threads if t.is_alive()]
    if still_running:
        raise RuntimeError(
            f'Timeout on {len(still_running)} threads: {[t.name for t in still_running]}')


# block

def init_noop(x):
    c = x.__class__
    def fake_init(self, *a, **kw):
        x.__class__ = c
        print('fake init', x, type(x), x.__class__.mro())
    x.__class__ = type('FixInit', (c,), {'__init__': fake_init})
    return x

class Block(Worker):
    __EXPOSED_PROPS = ['running']  # internal block attributes
    _proxy__getattr_ = _proxy__getattr_
    _proxy__setattr_ = _proxy__setattr_
    _agent = None

    # automatic manager proxy

    def __init_subclass__(cls, *a, **kw):
        # create a proxy class for this Block - this lets you create it from a multiprocessing.Manager
        # need to do it here so that it is pickleable
        cls.__proxy_name = name = f'reip_Block_Proxy__{cls.__qualname__.replace(".", "__")}'
        cls.__proxytype = c = type(name, (MakeProxyType(
            cls.__name__, 
            public_methods(cls) + ['__str__', '_proxy__getattr_', '_proxy__setattr_']),), 
            {m: prop(m) for m in cls.__EXPOSED_PROPS})
        c.__qualname__ = f'{cls.__qualname__}._Block__proxytype'

    def __new__(cls, *a, **kw):
        parent = Graph._default
        manager = parent._manager
        if manager:
            # it belongs to a task - make sure to register the proxy class with the manager
            # TODO: register in __init_subclass__ ?
            pcls = manager.dynamic_register(cls.__proxy_name, cls, cls.__proxytype)
            x = pcls(*a, **kw)
            parent.__append__(x)
            return x

        x = super().__new__(cls)
        parent.__append__(x)
        return x

    # basic

    def __init__(self, *a, name, **kw):
        self.name = name
        self.a = a
        self.kw = kw

    def __str__(self):
        return f'[{self.__class__.__name__}({self.name})]'

    # control

    def spawn(self):
        self.running = True
        self.terminated = False
        if self._agent is not None:
            return
        self._agent = threading.Thread(
            target=self.__run_agent, 
            name=f'Thread:{self.name}', 
            daemon=True)
        self._agent.start()

    def close(self):
        self.running = False

    def terminate(self):
        self.running = False
        self.terminated = True

    def join(self):
        self.close()
        if self._agent is None:
            return
        self._agent.join()
        self._agent = None

    # core mechanics

    def __run_agent(self):
        try:
            self.SAFE__(self.run)
        except AgentExit:
            pass

    def SAFE__(self, func, *a, **kw):
        try:
            return func(*a, **kw)
        except KeyboardInterrupt:
            print('Interrupted')
            self.terminate()
        except Exception as e:
            self.__exception = e
            import traceback
            print(f'--\nError in {self.name}.{func.__name__}:\n--\n{traceback.format_exc()}', file=sys.stderr)
            self.terminate()
            raise AgentExit()

    # Implementation specific:

    def run(self):
        self.SAFE__(self.init, *self.a, **self.kw)
        try:
            while self.running:
                self.SAFE__(self.process)
        finally:
            self.SAFE__(self.finish)

    def init(self): pass

    def process(self):
        self.SAYHI()
        time.sleep(1)

    def finish(self): pass

    def SAYHI(self):
        print('hi from', self.name, mp.current_process().name, threading.current_thread().name)

# initialize a proxy class for block
Block.__init_subclass__(Block)



class BadApple(Block):
    die_after = 2
    def init(self):
        self.t = time.time()
    def process(self):
        if time.time() - self.t > self.die_after:
            raise RuntimeError("boom!")


if __name__ == '__main__':



    def main():
        with Graph() as g:
            b = Block(name='asdf')
            with Task() as t:
                bt1 = Block(name='zxcv')
                BadApple(name='boom')
            with Task() as t:
                bt2 = Block(name='zxcvzxcv')
                # BadApple('boom')

        print(g)
        b.SAYHI()
        bt1.SAYHI()
        bt2.SAYHI()

        g.run(duration=5)
    import fire
    fire.Fire(main)