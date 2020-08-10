from .constants import *
from . import util

from .stream import *
from .block import *
from .graph import *
from .task import *
from .blocks import *


def run(*a, **kw):
    Graph.default.run(*a, **kw)
