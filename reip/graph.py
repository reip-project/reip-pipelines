'''




'''

import time
from contextlib import contextmanager
import weakref

import reip
from reip.util.iters import timed, loop
from reip.util import text


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
    _delay = 1e-6
    _previous = False  # the previous default instance
    parent_id, task_id = None, None

    def __init__(self, *blocks, name=None, graph=None):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.parent_id, self.task_id = BaseContext.register_instance(self, graph)

    # global instance management

    @classmethod
    def _initialize_default_graph(cls):
        _ContextScope.default = _ContextScope.top = Graph()

    @classmethod
    def get(cls, instance=None):
        '''If `instance` is `None`, the default instance will be returned.
        Otherwise `instance` is returned.'''
        return _ContextScope.default if instance is None else instance

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
    _delay = 1e-6
    _main_delay = 0.1

    def __init__(self, *blocks, **kw):
        super().__init__(**kw)
        self.blocks = list(blocks)
        self.log = reip.util.logging.getLogger(self)

    def __repr__(self):
        return '[~{}({}) ({} children) {}~]'.format(
            self.__class__.__name__, self.name, len(self.blocks),
            ''.join('\n' + text.indent(b) for b in self.blocks))

    def add(self, block):
        '''Add block to graph.'''
        self.blocks.append(block)

    def remove(self, block):
        self.blocks.remove(block)

    def clear(self):
        self.blocks.clear()

    # run graph

    def run(self, duration=None, **kw):
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, raise_exc=False):
        self.log.info(text.green('Starting'))
        try:
            self.spawn()
            self.log.info(text.green('Ready'))
            yield self
        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            self.terminate()
        finally:
            self.join(raise_exc=raise_exc)
            self.log.info(text.green('Done'))

    def wait(self, duration=None):
        for _ in timed(loop(), duration):
            if self.done or self.error:
                return True
            time.sleep(self._main_delay)

    # state

    @property
    def ready(self):
        return all(b.ready for b in self.blocks)

    @property
    def running(self):
        return any(b.running for b in self.blocks)

    @property
    def terminated(self):
        return all(b.terminated for b in self.blocks)

    @property
    def done(self):
        return all(b.done for b in self.blocks)

    @property
    def error(self):
        return any(b.error for b in self.blocks)

    # Block control

    # def _reset_state(self):
    #     for block in self.blocks:
    #         block._reset_state()

    def spawn(self, wait=True):
        for block in self.blocks:
            block.spawn(wait=False)
        if wait:
            self.wait_until_ready()

    def wait_until_ready(self):
        while not self.ready and not self.error and not self.done:
            time.sleep(self._delay)

    def join(self, close=True, terminate=False, raise_exc=False, **kw):
        if close:
            self.close()
        if terminate:
            self.terminate()
        for block in self.blocks:
            block.join(terminate=False, **kw)
        if raise_exc:
            self.raise_exception()

    def pause(self):
        for block in self.blocks:
            block.pause()

    def resume(self):
        for block in self.blocks:
            block.resume()

    def close(self):
        for block in self.blocks:
            block.close()

    def terminate(self):
        for block in self.blocks:
            block.terminate()

    def raise_exception(self):
        for block in self.blocks:
            block.raise_exception()

    def summary(self):
        return '\n'.join(s for s in (b.summary() for b in self.blocks) if s)

    def status(self):
        return text.b_(
            f'[{self.name}]',
            text.indent('\n'.join(
                s for s in (b.status() for b in self.blocks) if s))
        )

    def print_stats(self):
        for block in self.blocks:
            block.print_stats()


# create an initial default graph
# Graph.top = Graph.default = Graph()
