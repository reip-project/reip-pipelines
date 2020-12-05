import sys
import time
import logging
import colorlog
logging.Formatter.converter = time.localtime

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


def getLogger(block, debug=True, compact=True):
    if isinstance(block, str):
        log = logging.getLogger(block)
    else:
        log = logging.getLogger(block.name)
        log.addFilter(InjectData(dict(
            block=StrRep(block, 'short_str' if compact else None)
        )))
    log.setLevel(minlevel(debug))
    formatter = colorlog.ColoredFormatter(COMPACT_FORMAT if compact else MULTILINE_FORMAT)
    return add_stdouterr(log, formatter=formatter, debug=debug)


def add_stdouterr(log, formatter=None, debug=False, errlevel=logging.WARNING):
    # https://stackoverflow.com/questions/16061641/python-logging-split-between-stdout-and-stderr
    h_out = levelrange(logging.StreamHandler(sys.stdout), minlevel(debug), errlevel)
    h_err = levelrange(logging.StreamHandler(sys.stderr), errlevel)
    if formatter is not None:
        h_out.setFormatter(formatter)
        h_err.setFormatter(formatter)
    log.addHandler(h_out)
    log.addHandler(h_err)
    return log


def levelrange(log, minlevel=logging.DEBUG, maxlevel=None):
    if minlevel is not None:
        log.setLevel(minlevel)
    if maxlevel is not None:
        log.addFilter(MaxLevel(maxlevel))
    return log


def minlevel(debug=False):
    return logging.DEBUG if debug else logging.INFO


class StrRep:
    '''Wrapping an object to provide an alternative string representation.'''
    def __init__(self, obj, method=None, *a, **kw):
        self._str = getattr(obj, method or '__str__')
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
