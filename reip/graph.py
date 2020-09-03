'''

'''

import time
from contextlib import contextmanager
import weakref

import reip
from reip.util.iters import timed, loop
from reip.util import text


class BaseContext:
    default = None  # the default instance
    _previous = False  # the previous default instance

    _all_instances = {}

    def __init__(self, *blocks, name=None, graph=None):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.blocks = list(blocks)
        self._delay = 1e-6
        self.context_id = Graph.register_instance(self, graph)


    def __repr__(self):
        return '[~{} ({} children) {}~]'.format(
            self.__class__.__name__, len(self.blocks),
            ''.join('\n' + text.indent(b) for b in self.blocks))

    def add(self, block):
        '''Add block to graph.'''
        self.blocks.append(block)

    def remove(self, block):
        self.blocks.remove(block)

    def clear(self):
        self.blocks.clear()

    # global instance management

    @classmethod
    def get(cls, instance=None):
        '''If `instance` is `None`, the default instance will be returned.
        Otherwise `instance` is returned.'''
        return cls.default if instance is None else instance

    @classmethod
    def register_instance(cls, member=None, instance=None):
        '''Add a member (Block, Task) to the graph in instance.

        This is used inside of

        Arguments:
            instance (reip.Graph): A graph or task to be added to.
                If instance is None, the default graph/task will be used.
                If instance is False, nothing will be added.
            member (reip.Graph, reip.Block): A graph, task, or block to add to
                instance.
                If `member is instance`, nothing will be added. In other words,
                A graph cannot be added to itself.

        Returns:
            The name of `instance`. This prevents Blocks from having a reference
            to the entire graph.
        '''
        BaseContext._all_instances[member.name] = weakref.ref(member)
        if instance is False:  # disable graph
            return None
        instance = cls.get(instance)  # get default if None
        if instance is None or instance is member:
            return None
        instance.add(member)
        return instance.name

    @classmethod
    def get_object(self, id):
        obj = self._all_instances.get(id)
        if obj is None:
            raise ValueError(f'Object {id} does not exist.')
        obj = obj()  # call weakref to get actual ref
        if obj is None:
            raise ValueError(f'Object {id} no longer exists.')
        return obj

    def __enter__(self):
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_previous()

    def as_default(self):
        '''Set this graph as the default graph and track the previous default.'''
        self._previous, self.__class__.default = self.__class__.default, self
        return self

    def restore_previous(self):
        '''Restore the previously set graph.'''
        if self._previous is not False:
            self.__class__.default, self._previous = self._previous, None
        self._previous = False
        return self

    # def rename_child(self, old_name, new_name):
    #     pass


# import blessed

class Graph(BaseContext):
    _delay = 1e-6
    _main_delay = 0.1

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.log = reip.util.logging.getLogger(self)

    # run graph

    def run(self, duration=None, **kw):
        with self.run_scope(**kw):
            self.wait(duration)

    @contextmanager
    def run_scope(self, raise_exc=False):
        self.log.info(text.green('Starting'))
        # print(text.b_(text.green('Starting'), self), flush=True)
        try:
            self.spawn()
            self.log.info(text.green('Ready'))
            # print(text.b_(text.green('Ready'), self), flush=True)
            yield self
        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            # print(text.b_(text.yellow('Interrupting'), self, '--'))
        finally:
            self.join(raise_exc=raise_exc)
            # print(text.b_(text.green('Done'), self), flush=True)
            self.log.info(text.green('Done'))

    def wait(self, duration=None):
        for _ in timed(loop(), duration):
            if self.done or self.error:
                break
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
Graph.top = Graph.default = Graph()
