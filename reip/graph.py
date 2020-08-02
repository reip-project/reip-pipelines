'''

'''

import time

import reip
from reip.util.iters import timed, loop
from reip.util import text


class BaseContext:
    default = None  # the default instance
    _previous = None  # the previous default instance

    def __init__(self, *blocks, name=None, graph=None):
        self.name = name or f'{self.__class__.__name__}_{id(self)}'
        self.blocks = list(blocks)
        self._delay = 1e-6
        self.context_id = Graph.add_if_available(graph, self)

    def __repr__(self):
        return '[~{} ({} children) {}~]'.format(
            self.__class__.__name__, len(self.blocks),
            ''.join('\n' + text.indent(b) for b in self.blocks))

    def add(self, block):
        '''Add block to graph.'''
        self.blocks.append(block)

    # global instance management

    @classmethod
    def get(cls, instance=None):
        return cls.default if instance is None else instance

    @classmethod
    def add_if_available(cls, instance=None, member=None):
        if instance is False:  # disable graph
            return None
        instance = cls.get(instance)  # get default if None
        if instance is None or instance is member:
            return None
        instance.add(member)
        return instance.name

    @classmethod
    def get_default(cls):
        return cls.default

    def __enter__(self):
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_previous()

    def as_default(self):
        self._previous, self.__class__.default = self.__class__.default, self
        return self

    def restore_previous(self):
        if self._previous is not None:
            self.__class__.default, self._previous = self._previous, None
        return self


class Graph(BaseContext):
    _delay = 0.2

    # run graph

    def run(self, duration=None):
        print(text.b_(text.green('Starting'), self), flush=True)
        try:
            self.spawn(wait=False)
            print(text.b_(text.green('Ready'), self), flush=True)
            for _ in timed(loop(), duration):
                if self.terminated or self.error:
                    break
                time.sleep(self._delay)
        except KeyboardInterrupt:
            print(text.b_(text.yellow('Interrupting'), self, '--'))
        finally:
            self.join()
            # if self.context_id is None:
            self.print_stats()

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
        while not self.ready and not self.error and not self.terminated:
            time.sleep(self._delay)

    def join(self, terminate=True, **kw):
        if terminate:
            self.terminate()
        for block in self.blocks:
            block.join(terminate=False, **kw)

    def pause(self):
        for block in self.blocks:
            block.pause()

    def resume(self):
        for block in self.blocks:
            block.resume()

    def terminate(self):
        for block in self.blocks:
            block.terminate()

    def summary(self):
        return '\n'.join(s for s in (b.summary() for b in self.blocks) if s)

    def print_stats(self):
        for block in self.blocks:
            block.print_stats()


# create an initial default graph
Graph.top = Graph.default = Graph()
