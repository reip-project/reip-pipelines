
class _Manager:
    '''This manages a global manager object, and any namespaces from that manager.'''
    def __init__(self):
        self._manager = None
        self.ns = {}

    @property
    def manager(self):
        if self._manager is None:
            import multiprocessing as mp
            self._manager = mp.Manager()
        return self._manager

    def get(self, name):
        if name is None:
            return self.manager
        try:
            return self.ns[name]
        except KeyError:
            ns = self.ns[name] = self.manager
            return ns

_manager = _Manager()   
get_manager = _manager.get

from .interface import *
from .core import *
from .queue import *
try:
    import pyarrow
except ImportError:
    PlasmaStore = ArrowQueue = None
    HAS_PYARROW = False
else:
    from .plasma import *
    HAS_PYARROW = True
from .queue_store import *
from .producer import *
