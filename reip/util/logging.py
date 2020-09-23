import sys
import logging
import colorlog



def getLogger(block):
    log = logging.getLogger(block.name)
    log.setLevel(logging.DEBUG)

    # https://stackoverflow.com/questions/16061641/python-logging-split-between-stdout-and-stderr
    log.addFilter(InjectData(dict(naem=block.name, block=block)))
    # '(%(name)s:%(levelname)s) %(asctime)s: %(message)s | %(block)s'
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s[%(levelname)s]%(reset)s %(thin)s%(asctime)s%(reset)s: '
        '%(log_color)s%(message)s%(reset)s\n'
        '%(log_color)s %(block)s%(reset)s\n'
    )

    h_stdout = logging.StreamHandler(sys.stdout)
    h_stdout.setLevel(logging.DEBUG)
    h_stdout.setFormatter(formatter)
    h_stderr = logging.StreamHandler(sys.stderr)
    h_stderr.setLevel(logging.WARNING)
    h_stderr.setFormatter(formatter)
    log.addHandler(h_stdout)
    log.addHandler(h_stderr)
    return log


class InjectData(logging.Filter):
    def __init__(self, fields, *a, **kw):
        self._fields = fields
        super().__init__(*a, **kw)
    def filter(self, record):
        for k, v in self._fields.items():
            setattr(record, k, v)
        return True
