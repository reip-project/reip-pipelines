import os
import sys
import time
import logging
import colorlog

MULTILINE_FORMAT = (
    '%(log_color)s[%(levelname)s]%(reset)s %(thin)s%(asctime)s%(reset)s: '
    '%(log_color)s%(message)s%(reset)s\n'
    '%(log_color)s %(block)s%(reset)s\n'
)
# [DEBUG] 2020-11-23 19:54:28,836: Starting...
#  [Block(Csv_3979680560): (1/1 in, 1 out; 0 processed) - --]

COMPACT_FORMAT = (
    '%(log_color)s[%(levelname)s]%(reset)s%(thin)s%(asctime)s%(reset)s '
    '%(log_color)s %(block)s%(reset)s: %(log_color)s%(message)s%(reset)s'
)
# [DEBUG]2020-11-23 19:54:28,836 [B(Csv_3979680560[1|1])--]: Starting...

DATE_FORMAT = "%m/%d/%y %H:%M:%S"

DEFAULT_LEVEL = os.getenv('REIP_LOG_LEVEL') or 'info'

import collections
class _FileWrapper:
    '''This is so we can flip a switch and start queue-ing up messages.'''
    diverting = False
    def __init__(self, file):
        self.file = file
        self.q = collections.deque()

    def __getstate__(self):
        return dict(self.__dict__, q=collections.deque(), diverting=False)

    def __getattr__(self, key):
        return getattr(self.file, key)

    def write(self, x):
        if self.diverting:
            self.q.append(x)
        else:
            while self.diverting:
                self.file.write(self.diverting.popleft())
            self.file.write(x)



def getLogger(block, level=DEFAULT_LEVEL, strrep=None, compact=True, propagate=False):
    is_block = block is not None and not isinstance(block, str)
    log = logging.getLogger(os.path.join(__name__.split('.')[0], 'block' if is_block else '', block.name if is_block else block or ''))

    if getattr(log, '_is_configured_by_reip_', False):
        return log
    log._is_configured_by_reip_ = True

    if is_block:
        log.addFilter(InjectData(dict(
            block=StrRep(block, __str__=strrep if strrep else 'short_str' if compact else None)
        )))
    log.propagate = propagate
    log.setLevel(aslevel(DEFAULT_LEVEL if level is None else level))
    formatter = colorlog.ColoredFormatter(COMPACT_FORMAT if compact else MULTILINE_FORMAT)
    formatter.converter = time.localtime
    return add_stdouterr(log, formatter=formatter, level=level)


def add_stdouterr(log, formatter=None, level='info', errlevel=logging.WARNING):
    # https://stackoverflow.com/questions/16061641/python-logging-split-between-stdout-and-stderr
    add_filehandle(log, sys.stdout, level, errlevel, formatter=formatter)
    add_filehandle(log, sys.stderr, errlevel, formatter=formatter)
    return log


def add_filehandle(log, file, minlevel=None, maxlevel=None, formatter=None):
    hand = levelrange(logging.StreamHandler(file), aslevel(minlevel), aslevel(maxlevel))
    if formatter is not None:
        hand.setFormatter(formatter)
    log.addHandler(hand)
    return log


def levelrange(log, minlevel=logging.DEBUG, maxlevel=None):
    if minlevel is not None:
        log.setLevel(aslevel(minlevel))
    if maxlevel is not None:
        log.addFilter(MaxLevel(aslevel(maxlevel)))
    return log

def aslevel(level):
    if str(level) == level:
        levelkey = level.upper() if level not in logging._nameToLevel else level
        return logging._nameToLevel.get(levelkey, level)
    return level

def minlevel(debug=False):
    return logging.DEBUG if debug else logging.INFO


class StrRep:
    '''Wrapping an object to provide an alternative string representation.'''
    def __init__(self, obj, *a, __str__=None, **kw):
        self._str = __str__ if callable(__str__) else getattr(obj, __str__ or '__str__')
        self.a, self.kw = a, kw

    def __str__(self):
        return self._str(*self.a, **self.kw)


class MaxLevel(logging.Filter):
    '''Filters (lets through) all messages with level < LEVEL'''
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


class InjectData(logging.Filter):
    def __init__(self, fields, *a, **kw):
        self._fields = fields
        super().__init__(*a, **kw)

    def filter(self, record):
        for k, v in self._fields.items():
            setattr(record, k, v)
        return True
