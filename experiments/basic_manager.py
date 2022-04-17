'''Task and inter-process block calls all managed using multiprocessing Manager Proxies

Main difference between this and original REIP is that 
the manager forks as soon as it's created. I tried to 
change this and start it when the graph was run, but 
I don't think it's possible without rewriting a lot.


The primary modifications are as follows:
 
 - BaseProxy
    - the main modification here is how we:
        - generate the Proxy class from the original class (AutoProxy)
        - how we cache the classes (GetProxyType)
        - supporting proxy property access (_create_exposed_methods)
 - TaskManager
    - taking control of proxy registration / creation
    - optionally supporting dynamically created classes - not sure about this - depends on if they're pickleable
 - TaskManager._Server
    - overridding object creation in the remote process
        - support both public_method detection and custom method lists together
 - Proxyable - reip.Worker base class
    - automatically creates and registers a new proxy class on reip.Block subclass


A sketch of how the block proxying works:

.. code-block:: python

    # block class definition
    Block.__init_subclass__
        # create the ProxyType object - users can extend it before forking if they want to do something special
        Block.ProxyType
        # register it now so we have it in case we fork
        Block.register_proxytype()
            -- 
                TaskManager.register(tid, cls, cls.ProxyType)
                    _registry[tid] = _registration()

    # if the user changes it outside the block, they need to register it over
    class ProxyType(Block.ProxyType): pass
    Block.register_proxytype(ProxyType)


    # spawn task process
    Task()
        TaskManager.__init__
            TaskManager.start()
                [[ ManagerProcess ]]:
                    _Server.serve_forever()

        [[[[[  FORK  ]]]]]

        # spawn task graph
        TaskProxy.__init__
            [[ ManagerProcess ]]:
                Graph.__init__

    # spawn block
    Block.__init__
        # # make sure the block is registered
        # if tid not in manager._registry:
        #     manager.dynamic_register(tid, cls)
        # create the block proxy
        Block.ProxyType.__init__
            [[ ManagerProcess ]]:
                # create the remote block
                TaskManager._Server.create
                    # add proxy attribute getter/setters
                    Block:
                        _proxy__getattr_, _proxy__setattr_
                    # create proxied object
                    Block.__init__
            # get the block's exposed methods
            exposed = TaskManager._Server.get_methods
                [[ ManagerProcess ]]:
                    return public_methods(Block) + Block._proxy__exposed_
            # make sure that the methods are exposed here
            Block.ProxyType._register_exposed_methods(
                exposed, Block._proxy__exposed_props_)

parent | child >
          main    proc A    proc B
main       s       sp         sp
proc A     x       ps         pp
proc B     x       pp         ps

s - Graph.append(Worker)
 - Worker.__init__
sp - Graph.append(WorkerProxy)
 - WorkerProxy.__init__ - append
 - Worker.__init__ - skip
ps - WorkerProxy - Graph.append(Worker)
 - WorkerProxy.__init__ - skip
 - Worker.__init__ - append
pp - GraphProxy.append(WorkerProxy)
 - WorkerProxy.__init__ - append
 - pickle.loads(WorkerProxy.__init__)
 - Worker.__init__ - skip
 - 

'''
import sys
import time
import functools
import threading
from contextlib import contextmanager
import multiprocessing as mp
try:  # they all work as long as we don't use local refs e.g. Block BreaksForSpawn at the bottom == bad
    mp.set_start_method('fork')
    # mp.set_start_method('spawn')
    # mp.set_start_method('forkserver')
except RuntimeError:
    pass
from multiprocessing.managers import SyncManager, public_methods, dispatch



class BaseProxy(mp.managers.BaseProxy):
    # NOTE: This is a list of method names to explore
    _exposed_ = None  # this needs to have some value
    _exposed_props_ = None
    __dont_expose = ['__builtins__']  # XXX: where is this from

    def __init__(self, *a, isauto=False, **kw):
        # NOTE: we have to set this in __init__ otherwise pickling breaks
        self._isauto = isauto
        super().__init__(*a, **kw)

    # NOTE: this needed to be overridden to change the AutoProxy it was using to this one
    def __reduce__(self):
        kwds = {}
        if mp.managers.get_spawning_popen() is not None:
            kwds['authkey'] = self._authkey

        if getattr(self, '_isauto', False):
            kwds['exposed'] = self._exposed_
            kwds['exposed_props'] = self._exposed_props_
            proxytype = self._AutoProxy
        else:
            proxytype = type(self)
        return (mp.managers.RebuildProxy, (proxytype, self._token, self._serializer, kwds))

    # NOTE: This is a tweak of mp.managers.AutoProxy
    @classmethod
    def _AutoProxy(cls, token, serializer, manager=None, authkey=None,
                   exposed=None, exposed_props=None, incref=True, manager_owned=False):
        '''A utility to automatically create a Proxy with certain exposed methods.'''
        if exposed is None:
            exposed = _call_server_method(
                token, serializer, 'get_methods', token,
                authkey=authkey, manager_owned=manager_owned)
        if exposed_props is None:
            exposed_props = _call_server_method(
                token, serializer, 'get_exposed_props', token,
                authkey=authkey, manager_owned=manager_owned)

        if authkey is None and manager is not None:
            authkey = manager._authkey
        if authkey is None:
            authkey = mp.current_process().authkey

        proxytype = cls._GetProxyType(token.typeid)
        proxytype._create_exposed_methods(exposed, exposed_props)

        return proxytype(
            token, serializer, manager=manager, authkey=authkey,
            incref=incref, isauto=True, manager_owned=manager_owned)

    # NOTE: This is a simplification of mp.managers.MakeProxyType
    _cache = {}
    @classmethod
    def _GetProxyType(cls, name, proxytype=None) -> 'BaseProxy':
        '''Get a Proxy class by name, and create it if it does not exist.'''
        if proxytype:
            cls._cache[name] = proxytype
            return proxytype
        try:
            return cls._cache[name]
        except KeyError:
            cls._cache[name] = c = type(name, (cls,), {})
            return c


    # NOTE: This adds proxy methods and properties
    @classmethod
    def _create_exposed_methods(cls, exposed=None, props=None):
        '''Expose certain methods and properties on this Proxy. Will not 
        overwrite if the class already defines it.
        '''
        cdic = cls.__dict__  # XXX: using __dict__ because otherwise we lose things like __str__
        dic = {}
        # define exposed methods
        for meth in exposed or ():
            if meth not in cdic and meth not in cls.__dont_expose:
                exec('''
def %s(self, /, *args, **kwds):
    return self._callmethod(%r, args, kwds)
                ''' % (meth, meth), dic)

        # define exposed properties
        pdic = {}
        for prop in props or ():
            if prop not in cdic and prop not in cls.__dont_expose:
                exec('''
@property
def %s(self):
    return self._callmethod('_proxy__getattr_', (%r,))

@%s.setter
def %s(self, value):
    return self._callmethod('_proxy__setattr_', (%r, value))
            ''' % (prop,prop,prop,prop,prop,), pdic)

        # NOTE: need this to prevent a pickling error
        if cls._exposed_ is None:
            cls._exposed_ = []
        if cls._exposed_props_ is None:
            cls._exposed_props_ = []
        for k in exposed or ():
            if k in dic:
                setattr(cls, k, dic[k])
                cls._exposed_.append(k)
        for k in props or ():
            if k in pdic:
                setattr(cls, k, pdic[k])
                cls._exposed_props_.append(k)
        
    # NOTE: This creates a registry entry for proxies in managers
    @classmethod
    def _registration(cls, callable, proxytype=None, exposed=None, method_to_typeid=None):
        '''Register a typeid with the manager type'''
        proxytype = cls._AutoProxy
        method_to_typeid = method_to_typeid or getattr(proxytype, '_method_to_typeid_', None)
        if method_to_typeid:
            for key, value in method_to_typeid.items():
                assert isinstance(key, str), '%r is not a string' % key
                assert isinstance(value, str), '%r is not a string' % value
        return callable, exposed, method_to_typeid, proxytype




# NOTE: This gets exposed methods from remote instance (taken from mp.managers.AutoProxy)
def _call_server_method(token, serializer, method, *a, authkey=None, manager_owned=None, **kw):
    '''Get a proxy target's exposed methods from the remote server instance.'''
    if manager_owned is None:
        server = getattr(mp.current_process(), '_manager_server', None)
        manager_owned = server and server.address == token.address
    if manager_owned:
        return getattr(server, method)(None, *a, **kw)
    _Client = mp.managers.listener_client[serializer][1]
    conn = _Client(token.address, authkey=authkey)
    try:
        return dispatch(conn, None, method, a, kw)
    finally:
        conn.close()


class TaskManager(SyncManager):

    # NOTE: we override this to customize workings inside process
    class _Server(SyncManager._Server):
        # let us dynamically register classes
        public = SyncManager._Server.public + ['dynamic_register', 'get_exposed_props']

        # _dont_expose = ['__builtins__']

        # NOTE: this lets us register a proxy after forking (if necessary)
        def dynamic_register(self, c, name, callable, *a, base=None, **kw):
            self.registry[name] = (base or BaseProxy)._registration(callable, *a, **kw)

        # NOTE: we customize this so we can modify the object after proxying
        def create(self, c, typeid, /, *args, **kwds):
            '''Create a new shared object and return its id'''
            with self.mutex:
                callable, exposed, method_to_typeid, proxytype = self.registry[typeid]

                if callable is None:
                    if kwds or (len(args) != 1):
                        raise ValueError("Without callable, must have one non-keyword argument")
                    obj = args[0]
                else:
                    obj = callable(*args, **kwds)

                # +++ add proxy attribute get/set methods
                _maybe_set_attr(obj.__class__, '_proxy__getattr_', _proxy__getattr_)
                _maybe_set_attr(obj.__class__, '_proxy__setattr_', _proxy__setattr_)

                only_exposed = set()
                exposed_methods = set(['_proxy__getattr_', '_proxy__setattr_'])
                exposed_props = set()
                if not exposed:
                    # get methods from the private attributes for each class
                    only_exposed.update(getattr(obj, '__override_exposed', None) or ())
                    exposed_methods.update(getattr(obj, '__exposed', None) or ())
                    exposed_props.update(getattr(obj, '__exposed_props', None) or ())
                    for pcls in obj.__class__.mro():
                        only_exposed.update(getattr(obj, f'_{pcls.__name__}__override_exposed', None) or ())
                        exposed_methods.update(getattr(obj, f'_{pcls.__name__}__exposed', None) or ())
                        exposed_props.update(getattr(obj, f'_{pcls.__name__}__exposed_props', None) or ())

                # +++ this attribute can be used to override all exposed methods
                if only_exposed:
                    exposed = only_exposed
                else:
                    if exposed is None:
                        exposed = public_methods(obj)
                    # +++ allow exposing without dropping public_methods result
                    exposed = tuple(exposed) + tuple(exposed_methods)

                if method_to_typeid is not None:
                    if not isinstance(method_to_typeid, dict):
                        raise TypeError(
                            "Method_to_typeid {0!r}: type {1!s}, not dict".format(
                                method_to_typeid, type(method_to_typeid)))
                    exposed = tuple(exposed) + tuple(method_to_typeid)
                
                obj.__proxy_exposed_methods = exposed_methods #tuple(set() - set(self._dont_expose))
                obj.__proxy_exposed_props = exposed_props #tuple(set() - set(self._dont_expose))

                ident = '%x' % id(obj)  # convert to string because xmlrpclib
                                        # only has 32 bit signed integers
                mp.util.debug('%r callable returned object with id %r', typeid, ident)

                self.id_to_obj[ident] = (obj, set(exposed), method_to_typeid)
                if ident not in self.id_to_refcount:
                    self.id_to_refcount[ident] = 0

            self.incref(c, ident)
            return ident, tuple(exposed)

        def get_exposed_props(self, c, token):
            try:
                return self.id_to_obj[token.id][0].__proxy_exposed_props or ()
            except AttributeError:
                return ()

        # Customizing the Manager process:
        # https://github.com/python/cpython/blob/f5542ecf6d340eaaf86f31d90a7a7ff7a99f25a2/Lib/multiprocessing/managers.py#L164

    # NOTE: mp.Manager wrapper function does this for us, so just do this inside init
    def __init__(self, *, start=True, **kw):
        # log('__init__', 'TaskManager')
        if 'ctx' not in kw:
            kw['ctx'] = mp.get_context()
        super().__init__(**kw)
        if start:
            self.start()

    # NOTE: call a method on the server object in the remote process
    def _call_server_method(self, meth, *a, **kw):
        conn = self._Client(self._address, authkey=self._authkey)
        try:
            dispatch(conn, None, meth, a, kw)
        finally:
            conn.close()

    # NOTE: this re-implements register using our overridden code
    @classmethod
    def register(cls, typeid, *a, create_method=True, base=None, **kw):
        if '_registry' not in cls.__dict__:
            cls._registry = cls._registry.copy()
        cls._registry[typeid] = (base or BaseProxy)._registration(*a, **kw)
        if create_method:
            def init(self, *a, **kw):
                return self.create_proxy(typeid, *a, **kw)
            init.__name__ = typeid
            setattr(cls, typeid, init)

    # NOTE: this is for registering after a Server has forked - 
    #       needs to update the remote registry as well
    def dynamic_register(self, typeid, *a, **kw):
        if typeid not in self._registry:
            self.register(typeid, *a, **kw)
            self._call_server_method('dynamic_register', typeid, *a, **kw)
        return functools.partial(self.create_proxy, typeid)

    # NOTE: This is taken from Manager.register inside create_method
    def create_proxy(self, typeid, *a, **kw):
        callable, exposed, method_to_typeid, proxytype = self._registry[typeid]
        token, exp = self._create(typeid, *a, **kw)
        proxy = proxytype(
            token, self._serializer, manager=self,
            authkey=self._authkey, exposed=exp)
        conn = self._Client(token.address, authkey=self._authkey)
        dispatch(conn, None, 'decref', (token.id,))
        return proxy


#################################################
#
# Base Class for Proxyable Class Inheritance
# will automatically manage Proxies for base classes.
#
#################################################

class Proxyable:
    '''A class that will automatically create and register a proxy class when you subclass it.'''
    _ProxyType = BaseProxy
    def __init_subclass__(cls, *a, **kw):
        # create a name that we can use to refer to this block/graph
        # NOTE: be wary of name collisions - how do we want to handle this ?? 
        cls._proxy_registration_name = f'ProxyType_{cls.__qualname__.replace(".", "_")}'
        # register the initial proxytype instance - can be overridden later
        cls.register_proxytype()

    def __new__(cls, *a, manager=None, **kw):
        # create a proxy if a manager was provided, otherwise create a normal instance
        x = cls._create_proxy(manager, *a, **kw) if manager else super().__new__(cls)
        # XXX: do we need to do this? if we don't store this here we can get duplicate blocks
        x._process_name = mp.current_process().name
        return x

    @classmethod
    def register_proxytype(cls, ProxyType=None):
        '''Register a ProxyType for this class.
        
        .. code-block:: python

            # as a decorator
            @MyClass.register_proxytype
            class SomeNewProxy(MyClass._ProxyType):
                def hi(self): ...

            # or forego the decorator and do it after
            MyClass.register_proxytype(SomeNewProxy)

            # or if the instance changes, update the current proxy
            MyClass._ProxyType = SomeNewProxy
            MyClass.register_proxytype()
        '''
        # get the proxy type - optionally, create one if one does not already exist.
        if ProxyType:
            cls._ProxyType = ProxyType
        # create a proxy if this class doesn't have one personally
        if '_ProxyType' not in cls.__dict__:
            cls._ProxyType = Proxy = type(f'ProxyType_{cls.__name__}', (cls._ProxyType,), {})
            Proxy.__qualname__ = f'{cls.__qualname__}._ProxyType'

        # XXX: is this redundant?
        # This just makes sure the class is in BaseProxy._cache
        cls._ProxyType = Proxy = cls._ProxyType._GetProxyType(cls._proxy_registration_name, cls._ProxyType)
        # register this class under a supposedly unique ID with the proxy class
        TaskManager.register(cls._proxy_registration_name, cls, Proxy, base=cls._ProxyType, create_method=False)
        return Proxy

    @classmethod
    def _create_proxy(cls, manager, *a, **kw):
        # dynamic register just to be safe? maybe catch an edge case idk
        manager.dynamic_register(cls._proxy_registration_name, cls, cls._ProxyType)
        # actually create the proxy instance
        return manager.create_proxy(cls._proxy_registration_name, *a, **kw)



def _check_matching_process(a, b):
    return _get_proxyable_process_name(a) == _get_proxyable_process_name(b)

def _get_proxyable_process_name(a):
    try:
        return a._manager._process.name
    except AttributeError:
        try:
            return a._process_name  # XXX: we need Proxyable._process_name for this
        except AttributeError:
            return mp.current_process().name

def is_main_process(name=None):
    return (name or mp.current_process().name) == 'MainProcess'
def is_main_thread(name=None):
    return (name or threading.current_thread().name) == 'MainThread'


############################
#
# General Utilities
#
############################

def _indent(x, n=2):
    '''Indent each line in text'''
    return ''.join(' '*n + x for x in str(x).splitlines(keepends=True))

def _iframes():
    '''iterate over stack frames (used for getting current line number, function name, etc.)'''
    f = sys._getframe().f_back
    while f:
        yield f
        f = f.f_back

def iframes(up=0):
    '''Iterate over stack frames (supports skipping lowest ones)'''
    return (f for i, f in enumerate(_iframes()) if i > up)

def getframe(up=0):
    return next(f for i, f in enumerate(iframes(up)) if i >= up)

def stack_desc(up=0, limit=None):
    return f'{C.BLACK} < {C.END}'.join(f'{C.CYAN}{f.f_code.co_name}{C.BLACK}:{f.f_lineno}{C.END}' for f in list(iframes(up+1))[:limit])

def whereami():
    '''Get the current process+thread names'''
    return mp.current_process().name, threading.current_thread().name

def log(*x, up=0, **kw):
    '''Quick logging with code location'''
    pn, tn = whereami()
    print(
        f'{C.YELLOW if is_main_process(pn) else C.GREEN}{pn}::{C.YELLOW if is_main_thread(tn) else C.PURPLE}{tn}{C.END}  '
        f'{stack_desc(up+1)}{C.END} \n'
        f'{_indent(" ".join(map(str, x)), 2)}\n', end='', **kw)

class C:
    LIGHT_GREY = '\033[97m'
    CYAN = '\033[96m'
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLACK = '\033[90m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# NOTE: These are attribute getters for objects behind a proxy
def _proxy__getattr_(self, name): return getattr(self, name)
def _proxy__setattr_(self, name, value): setattr(self, name, value)


# NOTE: this is used to set _proxy__getattr_
def _maybe_set_attr(self, name, value):
    '''Try setting an attribute if it's not already set - if it is, 
    or if you can't set an attribute, keep going.'''
    try:
        try:
            getattr(self, name)
        except AttributeError:
            setattr(self, name, value)
    except AttributeError:
        pass


##########################
#
# REIP's Implementation
#
##########################




class AgentExit(BaseException):
    pass

class Worker(Proxyable):
    _delay = 0.1
    __exposed = ['__str__']
    __exposed_props = ['name', 'running']

    class _ProxyType(Proxyable._ProxyType):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            parent = Graph._default
            if parent and is_main_process() and not _check_matching_process(parent, self):
                parent.__append__(self)

    def __new__(cls, *a, **kw):
        # get the parent graph, and if it has a manager
        # pass that to the worker
        manager = getattr(Graph._default, '_manager', None)
        if manager:
            kw.setdefault('manager', manager)
        # this will either return a Worker or a Proxy to a remote worker, depending
        # on the value of manager
        return super().__new__(cls, *a, **kw)

    def __init__(self):
        super().__init__()
        # add the worker to the current graph
        parent = Graph._default
        if parent and _check_matching_process(parent, self):
            parent.__append__(self)

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
            log('closing', self)
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

    def sayhi(self):
        log('hi from', self)



class Graph(Worker):
    _manager = None
    _default = None
    __exposed = ['__append__', '__enter__', '__exit__', '__as_default__']

    class _ProxyType(Worker._ProxyType):
        # activate context both here and in remote process

        def __enter__(self):
            self._callmethod('__as_default__')
            return Graph.__enter__(self)

        def __exit__(self, *a):
            self._callmethod('__exit__')
            return Graph.__exit__(self, *a)

    # basic

    def __init__(self, name=None):
        self.children = []
        self.name = name
        super().__init__()
        # self.sayhi()

    def __str__(self) -> str:
        ch = ''.join(f'\n{_indent(b).rstrip()}' for b in self.children)
        return f'[{f"{self._process_name}|" if not is_main_process(self._process_name) else ""}{self.__class__.__name__}({self.name or ""}){ch}]'

    # context capturing

    def __enter__(self):
        self.__previous, Graph._default = Graph._default, self
        return self

    def __as_default__(self): 
        '''Call enter, but don't try to return self - for remote proxy'''
        self.__enter__()

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
    def running(self) -> bool:
        return all(b.running for b in self.children)

    @classmethod
    def Task(cls, *a, manager=None, **kw) -> 'Graph._ProxyType':
        return cls(*a, manager=manager or TaskManager(), **kw)

Graph._default = Graph()
Task = Graph.Task



# block

class Block(Worker):
    _agent = _exception = None
    running = terminated = False

    # basic

    def __init__(self, *a, name=None, **kw):
        self.name = name or id(self)
        self.a = a
        self.kw = kw
        super().__init__()

    def __str__(self) -> str:
        symbol = (
            f'{C.RED}!{C.END}' if self._exception else 
            f"{C.GREEN}*{C.END}" if self.is_alive() else 
            f'{C.BLACK}-{C.END}')
        return f'[{symbol}|{self.__class__.__name__}({self.name})]'

    # control

    def spawn(self):
        self.running = True
        self.terminated = False
        if self._agent:
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
        if not self._agent:
            return
        self._agent.join()
        self._agent = None

    def is_alive(self) -> bool:
        agent = self._agent
        return agent is not None and agent.is_alive()

    # core mechanics

    def __run_agent(self):
        try:
            self._safe_(self.run)
        except AgentExit:
            pass

    def _safe_(self, func, *a, **kw):
        try:
            return func(*a, **kw)
        except KeyboardInterrupt:
            log('Interrupted')
            self.terminate()
            raise AgentExit()
        except Exception as e:
            self._exception = e
            import traceback
            log(f'--\nError in {self.name}.{func.__name__}:\n--\n{traceback.format_exc()}', up=1, file=sys.stderr)
            self.terminate()
            raise AgentExit()

    # Implementation specific:
    # Do changes here.

    def run(self):
        self._safe_(self.init, *self.a, **self.kw)
        try:
            while self.running:
                self._safe_(self.process)
        finally:
            self._safe_(self.finish)

    def init(self): pass

    def process(self):
        self.sayhi()
        time.sleep(1)

    def finish(self): pass


class BadApple(Block):
    '''Throw an error after a little bit.'''
    die_after = 2
    def init(self):
        self.t = time.time()
    def process(self):
        if time.time() - self.t > self.die_after:
            raise RuntimeError("boom!")


if __name__ == '__main__':
    def main():
        # normally, this would throw an error because it's a local variable
        # but here we're giving it a publically accessible name
        # only works for forking though !
        class BreaksForSpawn(Block):
            __qualname__ = 'Block.BreaksForSpawn'
        Block.BreaksForSpawn = BreaksForSpawn
        Block.BreaksForSpawn.__qualname__ = 'Block.BreaksForSpawn'

        with Graph('top') as g:
            b = Block(name='asdf')
            with Task('task1') as t:
                bt1 = Block(name='zxcv')
                BadApple(name='boom')
                # BreaksForSpawn(name='hello')

                with Task('task1-1') as t:
                    bt2 = Block(name='zxcvzxcv')
                    # BadApple('boom')
            with Task('task3333'):
                bt2 = Block(name='aaa')
                # BadApple('boom')

            # You can spawn a block with it's own TaskManager
            # Shows how process management is decoupled from 
            # graph/block instances
            manager = TaskManager()
            Block(name='asdfasdf', manager=manager)
            Block(name='asdfasdf2', manager=manager)
            with Graph('task4', manager=manager):
                Block(name='asdfasdf')

        print(g)
        b.sayhi()
        bt1.sayhi()
        bt2.sayhi()

        g.run(duration=5)
        print(g)
    import fire
    fire.Fire(main)