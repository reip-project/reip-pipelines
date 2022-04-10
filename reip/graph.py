'''




'''
import time
from contextlib import contextmanager
import weakref
import multiprocessing as mp
import remoteobj

import reip
from reip.util import text, iters


def default_graph():
    return _ContextScope.default

def get_graph(graph=None):
    return _ContextScope.default if graph is None else graph

def top_graph():
    return _ContextScope.top


class _ContextScope:
    top = None
    default = None
    all_instances = {}



class BaseContext:  # (metaclass=_MetaContext)
    _delay = 1e-3
    _previous = False  # the previous default instance
    parent_id, task_id = None, None

    def __init__(self, *blocks, name=None, graph=None):
        if blocks and not name and isinstance(blocks[0], str):
            name, blocks = blocks[0], blocks[1:]
        self.blocks = list(blocks)
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = BaseContext.register_instance(self, graph)

        for b in self.blocks:
            self.register_instance(b, self)

    # global instance management

    @classmethod
    def _initialize_default_graph(cls):
        _ContextScope.default = _ContextScope.top = Graph(name='_default_')

    @classmethod
    def get(cls, instance=None):
        '''If `instance` is `None`, the default instance will be returned.
        Otherwise `instance` is returned.'''
        return _ContextScope.default if instance is None else instance

    def add(self, block):
        '''Add block to graph.'''
        self.blocks.append(block)

    def remove(self, block):
        self.blocks.remove(block)

    def clear(self):
        self.blocks.clear()

    @classmethod
    def register_instance(cls, child=None, parent=None):
        '''Add a member (Block, Task) to the graph in instance.

        This is used inside of

        Arguments:
            child (reip.Graph, reip.Block): A graph, task, or block to add to
                instance.
                If `member is instance`, nothing will be added. In other words,
                A graph cannot be added to itself.
            parent (reip.Graph): A graph or task to be added to.
                If instance is None, the default graph/task will be used.
                If instance is False, nothing will be added.

        Returns:
            parent_id (str): the name of the child's parent block.
                Can be a Graph or Task.
            task_id (str or None): the name of the task that a child is attached to.
                If the parent graph is not inside a task or is not a task itself,
                it will return None.

            NOTE: Returning string ids prevents Blocks from having a circular reference
            to the entire graph.

        Basically this should handle:
         - adding a graph to a graph
            - parent.name, parent.task_id
         - adding a task to a graph
            - raise if parent is task
            - raise if graph.task_id is not None
            - if `flatten_tasks`, then iterate through graph parents until you
              find one on the main task
            - parent.name, child.name
         - adding a graph to a task
            - parent.name, parent.task_id
         - adding a block to a graph
            - parent.name, parent.task_id
         - adding a block to a task
            - parent.name, parent.task_id
         - do nothing if parent is False / None+unset default.
        '''
        _ContextScope.all_instances[child.name] = weakref.ref(child)
        task_id = child.name if isinstance(child, reip.Task) else None

        # user explicitly disabled graph for this child
        if parent is False:
            return None, task_id
        parent = get_graph(parent)  # get default if None
        # there is no graph specified and no default graph
        if parent is None:
            return None, task_id

        # trying to add to self
        if parent is child:
            return parent.parent_id, task_id or parent.task_id

        if task_id:  # disallow nested tasks
            # parent_contexts = [parent] + parent.parent_contexts if flatten_tasks else [parent]
            if isinstance(parent, reip.Task):
                raise RuntimeError(
                    'Cannot add a task ({}) to another task ({}).'.format(
                        child.name, parent.name))
            if parent.task_id:
                raise RuntimeError(
                    'Cannot add a task ({}) to a graph ({}) in a different task ({}).'.format(
                        child.name, parent.name, parent.task_id))

        # everything checks out.
        parent.add(child)
        return parent.name, task_id or parent.task_id

    @classmethod
    def get_object(cls, id, require=True):
        '''Get an instance using its name. If the instance '''
        obj = _ContextScope.all_instances.get(id) if id is not None else None
        obj = obj() if obj is not None else None
        if obj is None and require:
            raise ValueError(f'Object {id} does not exist.')
        return obj

    @property
    def parents(self):
        obj = self
        stack = []
        while obj.parent_id:
            obj = BaseContext.get_object(obj.parent_id)
            if obj is None:
                break
            stack.append(obj)
        return stack

    def __enter__(self):
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_previous()

    def as_default(self):
        '''Set this graph as the default graph and track the previous default.'''
        self._previous, _ContextScope.default = _ContextScope.default, self
        return self

    def restore_previous(self):
        '''Restore the previously set graph.'''
        if self._previous is not False:
            _ContextScope.default, self._previous = self._previous, None
        self._previous = False
        return self

    # def rename_child(self, old_name, new_name):
    #     pass


# import blessed

class Graph(BaseContext):
    '''Represents a collection of Blocks.
    
    
    '''
    _delay = 1e-3
    _main_delay = 1e-2#0.1
    controlling = None

    def __init__(self, *blocks, log_level='info', **kw):
        super().__init__(*blocks, **kw)
        self.log = reip.util.logging.getLogger(self, level=log_level)
        self._except = remoteobj.LocalExcept()

    def __repr__(self):
        return '{}({}), {} children:{}\n'.format(
            self.__class__.__name__, self.name, len(self.blocks),
            ''.join('\n' + text.indent(b) for b in self.blocks))

    def __bool__(self):
        return not (self.done or self.error)

    @classmethod
    def detached(cls, *blocks, **kw):
        return cls(*blocks, graph=None, **kw)

    # run graph

    def run(self, duration=None, stats_interval=1, print_graph=True, **kw):
        '''Run a graph and all of its child blocks.
        
        .. code-block::

            with reip.Graph() as g:
                BlockA().to(BlockB()).to(BlockC())

            g.run(duration=10)
        '''
        if print_graph:
            print("\nStarting:", self, "\n")

        with self.run_scope(**kw):
            self.wait(duration, stats_interval=stats_interval)

    @contextmanager
    def run_scope(self, wait=True, raise_exc=True):
        '''Run a graph and its child blocks while inside the context manager.
        
        .. code-block:: python

            with reip.Graph() as g:
                BlockA().to(BlockB()).to(BlockC())

            with g.run_scope():
                # gives you more flexibility in here
                g.wait(duration=5)
            # equivalent to g.run(duration=5)
        '''
        self.log.debug(text.green('Starting'))
        # controlling = False
        try:
            with self._except('spawn', raises=False):
                try:
                    self.spawn(wait=wait)
                    # controlling = self.controlling
                    self.log.debug(text.green('Ready'))
                except Exception as e:
                    self.log.error(text.red('Spawn Error'))
                    self.log.exception(e)
                    raise
            with self._except(raises=False):
                yield self
        except KeyboardInterrupt as e:
            self.log.warning(text.yellow('Interrupting'))
            # reip.util.print_stack('Interrupted here')
            self.log.exception(e)
            self.terminate()
        finally:
            try:
                self.join(raise_exc=raise_exc)
            finally:
                self.log.debug(text.green('Done'))
                # if controlling:
                #     print(self.stats_summary())

    # _delay = 1
    def wait(self, duration=None, stats_interval=None):
        t, t0 = time.time(), time.time()
        for _ in iters.timed(iters.sleep_loop(self._delay), duration):
            if self.done:
                return True

            if stats_interval and time.time() - t > stats_interval:
                t = time.time()
                status = self.status()
                self.log.info("Status after %.3f sec:\n%s" % (time.time() - t0, status[status.find("\n")+1:]))

    def _reset_state(self):
        self._except.clear()

    # state

    @property
    def ready(self):
        '''True if all child blocks are ready'''
        return all(b.ready for b in self.blocks)

    @property
    def running(self):
        '''True if any child blocks are running'''
        return any(b.running for b in self.blocks)

    @property
    def terminated(self):
        '''True if any child blocks are ready'''
        return all(b.terminated for b in self.blocks)

    @property
    def done(self):
        '''True if any child blocks are done'''
        return any(b.done for b in self.blocks)

    @property
    def error(self):
        '''True if any child blocks threw an error'''
        return bool(self._except.all()) or any(b.error for b in self.blocks)

    # Block control
    _ready_flag = None
    def spawn(self, wait=True, _controlling=True, _ready_flag=None, **kw):
        '''Spawns the graph and its children.'''
        self.controlling = _controlling
        if self.controlling:
            self._ready_flag = _ready_flag = mp.Event()

        self._spawn_tasks_first(_ready_flag=_ready_flag, **kw)
        for block in self.blocks:
            block.spawn(wait=False, _controlling=False, _ready_flag=_ready_flag, **kw)

        if wait:
            self.wait_until_ready()
        if self.controlling:
            self.raise_exception()
            if self._ready_flag is not None:
                _ready_flag.set()

    def _spawn_tasks_first(self, **kw):
        for b in self.blocks:
            if isinstance(b, reip.Task):
                b.spawn(wait=False, _controlling=False, **kw)
            elif isinstance(b, reip.Graph):
                b._spawn_tasks_first(wait=False, _controlling=False, **kw)

    def wait_until_ready(self, stats_interval=5):
        t = time.time()
        while not self.ready and not self.done:
            time.sleep(self._delay)
            
            if stats_interval and time.time() - t > stats_interval:
                t = time.time()
                self.log.info(f'waiting for all blocks to initialize...\n{self}')

    def join(self, close=True, terminate=False, raise_exc=None, **kw):
        '''Joins the graph and its children.'''
        if self._ready_flag is not None and not self._ready_flag.is_set():
            self._ready_flag.set()
        if close:
            self.close()
        if terminate:
            self.terminate()
        for block in self.blocks:
            block.join(terminate=False, raise_exc=False, **kw)
        if raise_exc is None and self.controlling:
            raise_exc = True
        if raise_exc:
            self.raise_exception()
        self.controlling = self._ready_flag = None

    def pause(self):
        '''Pause all blocks.'''
        for block in self.blocks:
            block.pause()

    def resume(self):
        '''Resume all blocks.'''
        for block in self.blocks:
            block.resume()

    def close(self):
        '''Close all blocks.'''
        for block in self.blocks:
            block.close()

    def terminate(self):
        '''Terminate all blocks.'''
        for block in self.blocks:
            block.terminate()

    def raise_exception(self):
        '''Raise any exceptions from blocks.'''
        for block in self.blocks:
            block.raise_exception()
        self._except.raise_any()

    def __export_state__(self):
        return {
            'blocks': [b.__export_state__() for b in self.blocks],
            '_except': self._except,
        }

    def __import_state__(self, state):
        if state:
            for b, update in zip(self.blocks, state.pop('blocks', ())):
                b.__import_state__(update)

    def short_str(self):
        return '[{}({})[{} children]]'.format(
            self.__class__.__name__[0],
            self.name, len(self.blocks))

    def stats(self):
        return {
            'name': self.name,
            'blocks': {b.name: b.stats() for b in self.blocks}
        }

    def summary(self):
        return '\n'.join(s for s in (b.summary() for b in self.blocks) if s)

    def status(self):
        return text.b_(
            f'[{self.name}]',
            text.indent('\n'.join(
                s for s in (b.status() for b in self.blocks) if s)), ""
        )

    def stats_summary(self):
        return text.block_text(
            f'[{self.name}]',
            *(s for s in (b.stats_summary() for b in self.blocks) if s)
        )


# create an initial default graph
# Graph.top = Graph.default = Graph()
