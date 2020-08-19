import time
from .constants import *
from . import util

from .interface import *
from . import stores
from .stores import Producer
from .stream import *
from .block import *
from .graph import *
from .task import *
from .blocks import *


def run(*a, **kw):
    Graph.default.run(*a, **kw)

def moment(delay=1e-6):
    '''Sleep for the minimum amount of time.'''
    time.sleep(delay)
