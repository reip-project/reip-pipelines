'''




'''
import time
from contextlib import contextmanager
import multiprocessing as mp
from . import base
from .base import Context
from . import exceptions
import reip
from reip.util import text, iters


# import blessed


def default_graph():
    return Graph._context_scope.default

# def get_graph(graph=None):
#     return Graph._context_scope.get(graph)

def top_graph():
    return Graph._context_scope.top


class Graph(Context):
    _delay = 1e-3
    _main_delay = 1e-3#0.1
    _controlling = None
    task_id = None
    _exception = None

    def __init__(self, *children, graph=None, parent=None, log_level='info', **kw):
        super().__init__(*children, parent=graph if parent is None else parent, **kw)
        self.log = reip.util.logging.getLogger(self, level=log_level)
        # self._except = exceptions.ExceptionTracker()

    def __repr__(self):
        return '[{}({}), {} children]'.format(self.__class__.__name__, self.name, len(self.children))

    def __str__(self):
        return '{}({}), {} children:{}\n'.format(
            self.__class__.__name__, self.name, len(self.children),
            ''.join('\n' + text.indent(b).rstrip() for b in self.children))

    


    # @property  # XXX: phase out this attr
    # def blocks(self): return self.children
    # @blocks.setter
    # def blocks(self, children): self.children = children

    # context management

    @classmethod
    def register_instance(cls, child, parent=None):
        parent = cls._context_scope.get(parent)
        task_id = child.name if isinstance(child, reip.Task) else None
        parent_task_id = parent.task_id if parent else None
        if task_id and parent_task_id:  # disallow nested tasks
            raise RuntimeError(
                'Cannot nest a task ({}) inside another task ({}).'.format(
                    child.name, parent.name))
        super().register_instance(child=child, parent=parent)
        child.task_id = task_id or parent_task_id


    # block accessors

    def get_block(self, name, require=True, match_graphs=False):
        found = next((
            b for b in self.iter_blocks(include_graphs=match_graphs)
            if b.name == name), None)
        if require and found is None:
            raise KeyError(name)
        return found

    def all_blocks(self, *a, **kw):
        return list(self.iter_blocks(*a, **kw))

    def iter_blocks(self, include_graphs=False):
        return self.nested(include_contexts=include_graphs)

    # run graph

    def run(self, duration=None, stats_interval=None, print_graph=True, **kw):
        if print_graph:
            self.log.info(f"Starting \n{self}\n")
        with self.run_scope(**kw):
            self.wait(duration, stats_interval=stats_interval)

    @contextmanager
    def run_scope(self, wait=True, timeout=None, terminate=False, raise_exc=True):
        self.log.debug(text.green('Starting'))
        try:
            try:
                self.spawn(wait=wait)
                # controlling = self._controlling
                self.log.debug(text.green('Ready'))
            except Exception as e:
                self.log.error(text.red('Spawn Error:\n{}'.format(reip.util.excline(e))))
                self.log.warning(self)
                self.terminate()
                raise
            finally:
                yield self
        except exceptions.WorkerExit:  # A worker saying we should exit
            pass
        except Exception as e:
            self._exception = e #exceptions.safe_exception(e)
        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            self.terminate()
        finally:
            try:
                self.join(raise_exc=raise_exc, terminate=terminate, timeout=timeout)
            finally:
                self.log.debug(text.green('Done'))

    # _delay = 1
    def wait(self, duration=None, stats_interval=None):
        t, t0 = time.time(), time.time()
        for _ in iters.timed(iters.sleep_loop(self._delay), duration):
            if self.done or self.terminated:
                return True

            if stats_interval and time.time() - t > stats_interval:
                t = time.time()
                status = self.status()
                print("Status after %.3f sec:\n%s" % (time.time() - t0, status[status.find("\n")+1:]))

    def _reset_state(self):
        self._controlling = False
        self._ready_flag = None
        self._spawn_flag = None
        self._exception = None

    # state

    @property
    def ready(self):
        return all(b.ready for b in self.children)

    @property
    def running(self):
        return any(b.running for b in self.children)

    @property
    def terminated(self):
        return any(b.terminated for b in self.children)

    @property
    def done(self):
        return all(b.done for b in self.children)

    @property
    def error(self):
        # return bool(self._except.caught) or any(b.error for b in self.children)
        return bool(self._exception) or any(b.error for b in self.children)

    # Block control
    _spawn_flag = _ready_flag = None
    def spawn(self, wait=True, _controlling=True, _ready_flag=None, _spawn_flag=None, **kw):
        self._controlling = _controlling
        if self._controlling:
            #self._ready_flag = _ready_flag = mp.Event()
            if _spawn_flag is None:
                self._spawn_flag = _spawn_flag = mp.Event()

        for block in self.children:
            block.spawn(wait=False, _controlling=False, _ready_flag=_ready_flag, _spawn_flag=_spawn_flag, **kw)

        # this makes all blocks wait to begin threads/processes together
        if self._controlling:
            workers = self._gather_workers()
            while not all(w.is_alive() for w in workers) and not self.done and not self.error:
                time.sleep(self._delay)
            if _spawn_flag is not None:
                _spawn_flag.set()

        if wait:
            self.wait_until_ready()
        if self._controlling:
            self.raise_exception()
            if self._ready_flag is not None:
                _ready_flag.set()

    def _gather_workers(self):
        workers = []
        for block in self.children:
            if isinstance(block, (reip.Task, reip.Block)):
                workers.append(block._agent)
            else:
                gather = getattr(block, '_gather_workers', None)
                if gather:
                    workers.extend(gather())
        return workers

    def wait_until_ready(self, stats_interval=4):
        print_th = reip.util.iters.HitThrottle(stats_interval) if stats_interval else False
        while not self.ready and not self.done:
            if print_th:
                self.log.info('[ready={}, done={}] waiting on {}'.format(self.ready, self.done, reip.util.text.b_(*(str(b).rstrip() for b in self.children if not b.ready))))
            time.sleep(self._delay)

    def join(self, close=True, terminate=False, raise_exc=None, **kw):
        # just in case there's a weird timing thing
        if self._spawn_flag is not None and not self._spawn_flag.is_set():
            self._spawn_flag.set()
        if self._ready_flag is not None and not self._ready_flag.is_set():
            self._ready_flag.set()
        if close:
            self.close()
        if terminate:
            self.terminate()
        for block in self.children:
            block.join(terminate=False, raise_exc=False, **kw)
        if raise_exc is None and self._controlling:
            raise_exc = True
        if raise_exc:
            self.raise_exception()
        self._controlling = self._ready_flag = self._spawn_flag = None

    def pause(self):
        for block in self.children:
            block.pause()

    def resume(self):
        for block in self.children:
            block.resume()

    def close(self):
        for block in self.children:
            block.close()

    def terminate(self):
        for block in self.children:
            self.log.warning(f'terminating {block}')
            block.terminate()

    def raise_exception(self):
        e = exceptions.get_exception(self)
        if e is not None:
            raise e

    def __export_state__(self):
        return {
            'children': [b.__export_state__() for b in self.children],
            '_exception': self._exception
        }

    def __import_state__(self, state):
        # self.log.debug('import state: {}'.format(state))
        if state:
            for b, update in zip(self.children, state.pop('children', ())):
                b.__import_state__(update)
            self.__dict__.update(state)

    def short_str(self):
        return '[{}({})[{} children, {} up]]'.format(
            self.__class__.__name__[0],
            self.name, len(self.children), sum(b.ready for b in self.children))

    def stats(self):
        return {
            'name': self.name,
            'children': {b.name: b.stats() for b in self.children}
        }

    def summary(self):
        return '\n'.join(s for s in (b.summary() for b in self.children) if s)

    def status(self):
        return text.b_(
            f'[{self.name}]',
            text.indent('\n'.join(
                s for s in (b.status() for b in self.children) if s)), ""
        )

    def stats_summary(self):
        return text.block_text(
            f'[{self.name}]',
            *(s for s in (b.stats_summary() for b in self.children) if s)
        )


# create an initial default graph
# Graph.top = Graph.default = Graph()
