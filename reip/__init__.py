import time
from .constants import *
from . import exceptions
from . import util
from .util import status

from .interface import *
from . import stores
from .stores import Producer
from .stream import *
from .block import *
from .graph import *
from .task import *
Graph._initialize_default_graph()
from .blocks import *

def run(*a, **kw):
    default_graph().run(*a, **kw)

def moment(delay=1e-6):
    '''Sleep for the minimum amount of time.'''
    time.sleep(delay)
