import logging
log = logging.getLogger(__name__)
# log.propagate = True
log.setLevel(logging.INFO)

import time
from .constants import *
from . import exceptions
from . import util
from .util import status, Meta

from .interface import *
from . import stores
from .stores import Producer
from .stream import *
from .block import *
from .graph import *
from .task import *
Graph._initialize_default_graph()
from .helpers import *
from . import blocks

def yurii_mode():
    '''Any configurations that can be made to put things the way Yurii likes them.'''
    reip.Block.USE_META_CLASS = False  # NOTE: not well tested yet
    reip.Block.KW_TO_ATTRS = True  # extra keywords get set as attributes
    # reip.Block.EXTRA_KW = True

def run(*a, **kw):
    default_graph().run(*a, **kw)

def graph_function(func):
    def inner(*a, **kw):
        with reip.Graph() as g:
            func(*a, **kw)
        g.run()
        return g
    return inner


def moment(delay=1e-6):
    '''Sleep for the minimum amount of time.'''
    time.sleep(delay)
