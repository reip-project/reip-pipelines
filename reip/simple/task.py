import time
import queue
import traceback
import multiprocessing
from abc import ABC, abstractmethod

from .interface import *
from .block import *


class Task(Block):
    __type_name__ = 'Task'
    _initialized = False

    def __init__(self, *a, **kw):
        self._block_factory = {}
        super().__init__(*a, **kw)
        self._initialized = True


    # Construction

    def add(self, block, name=None):
        block.name = name or block.name # XXX:

        if block.name in self._block_factory.keys():
            raise ValueError("Block %s already exists in task %s" % (block.name, self.name))
        self._block_factory[block.name] = block
        return block

    def __setattr__(self, name, value):
        if self._initialized and isinstance(value, Block):
            self.add(value, name)
        super().__setattr__(name, value)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._block_factory[key]
        return super().__getitem__(key)

    # Operation

    def start(self):
        super().start()
        for block in self._block_factory.values():
            block.start()

    def stop(self):
        super().stop()
        for block in self._block_factory.values():
            block.stop()

    def _spawn_children(self, wait=False):
        for block in self._block_factory.values():
            block.spawn(wait=False)

        if wait:
            for block in self._block_factory.values():
                while not block.ready:
                    time.sleep(self._process_delay)

    def _run(self):
        try:
            with self.timer(output=self._verbose):
                with self.timer('init', 'Initialized', self._verbose):
                    self.init()

                with self.timer('spawn', 'Spawned', self._verbose):
                    self._spawn_children()
                self.ready = True

                with self.timer('running', 'Running'):
                    while not self.terminate:
                        self._run_step()

                with self.timer('finish', 'Finishing'):
                    self.finish()

                with self.timer('join', 'Joining'):
                    self._join_children()
            self.done = True
        except:
            self.error = True
            # traceback.print_exc()
            raise

    def _run_step(self):
        time.sleep(self._process_delay)

    def _join_children(self, auto_terminate=True):
        if auto_terminate:
            for block in self._block_factory.values():
                block.terminate = True
        for block in self._block_factory.values():
            block.join()

    def print_stats(self):
        for name, block in self._block_factory.items():
            block.print_stats()
        print(self.timer)
