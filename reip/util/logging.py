import sys
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

class StrRep:
    '''Wrapping an object to provide an alternative string representation.'''
    def __init__(self, obj, method=None, *a, **kw):
        self._str = getattr(obj, method or '__str__')
        self.a, self.kw = a, kw

    def __str__(self):
        return self._str(*self.a, **self.kw)

# def str_rep(obj, method=None, *a, **kw):
#     func = getattr(obj, method or '__str__')
#     return type('StrRep', (), {'__str__': lambda self: func(*a, **kw)})

def getLogger(block, debug=True, compact=True):
    log = logging.getLogger(block.name)
    log.setLevel(logging.DEBUG if debug else logging.INFO)

    # https://stackoverflow.com/questions/16061641/python-logging-split-between-stdout-and-stderr
    log.addFilter(InjectData(dict(
        name=block.name,
        block=StrRep(block, 'short_str' if compact else None)
    )))
    # '(%(name)s:%(levelname)s) %(asctime)s: %(message)s | %(block)s'
    formatter = colorlog.ColoredFormatter(
        COMPACT_FORMAT if compact else MULTILINE_FORMAT)

    h_stdout = logging.StreamHandler(sys.stdout)
    h_stdout.setLevel(logging.DEBUG if debug else logging.INFO)
    h_stdout.addFilter(MaxLevel(logging.INFO))
    h_stdout.setFormatter(formatter)
    h_stderr = logging.StreamHandler(sys.stderr)
    h_stderr.setLevel(logging.WARNING)
    h_stderr.setFormatter(formatter)
    log.addHandler(h_stdout)
    log.addHandler(h_stderr)
    return log


class MaxLevel(logging.Filter):
    '''Filters (lets through) all messages with level < LEVEL'''
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno <= self.level


class InjectData(logging.Filter):
    def __init__(self, fields, *a, **kw):
        self._fields = fields
        super().__init__(*a, **kw)
    def filter(self, record):
        for k, v in self._fields.items():
            setattr(record, k, v)
        return True
