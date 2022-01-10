import traceback
import reip
from reip.util import text


class ParameterError(TypeError):
    pass


class RunExit(BaseException):
    pass


class ReipControl(BaseException):
    pass

class WorkerExit(ReipControl):
    pass






def get_exception(g):
    e = g._exception
    if isinstance(g, reip.Graph):
        excs = [e for e in (get_exception(b) for b in g.children) if e is not None]
        if e is None and not excs:
            return
        return GraphException(e, excs, name=g.name, type_name=type(g).__name__)
    if e is None:
        return
    if isinstance(e, GraphException):
        return e
    return GraphException(e, name=g.name, type_name=type(g).__name__)

class GraphException(Exception):
    # NOTE: Custom formatting for graph exception
    def __init__(self, exc=None, child_excs=(), name=None, type_name='Graph'):
        self.exc = exc
        self.child_excs = child_excs or ()
        self.excs = d = {}
        if exc is not None:
            d[name] = self
        for e in child_excs:
            d.update(e.excs)
        exc2 = getattr(exc, 'exc', None) or exc
        super().__init__(f'{type_name} [{name}] : ' + (f'{type(exc2).__name__}' if exc2 else ''))

    def __iter__(self):
        for e in self.excs.values():
            yield e.exc

    def __getitem__(self, key):
        return self.excs[key]

    def get(self, key):
        return self.excs.get(key)

    def __str__(self):
        return text.block_text(super().__str__(), format_exc(self.exc), *[str(e) for e in self.child_excs])


def format_exc(e):
    try:
        return (''.join(getattr(e, 'tb', None) or traceback.format_exception(type(e), e, e.__traceback__)) if e else None)
    except Exception as ee:
        return f"__str__ Exception in ({type(e).__name__} {e}) : ({type(ee).__name__}) {ee}"


class ExceptionAnnotate:
    '''I'm trying out a new exception interface
    where we just add an attribute to the exception 
    instead of '''
    def __init__(self):
        self._cache = {}

    def __call__(self, name=None, system=False):
        try:  # only created once
            return self._cache[name]
        except KeyError:  
            self._cache[name] = a = _Annotator(name, system=system)
            return a

    def __enter__(self):
        return self().__enter__()

class _Annotator:
    def __init__(self, name=None, system=False):
        self.name = name
        self.system = system  # TODO

    def __enter__(self):
        pass

    def __exit__(self, t, e, tb):
        if e is not None:
            e.__annotation__ = self.name
            e.__is_system_exception__ = self.system

annotate = ExceptionAnnotate()


class ExceptionTracker:
    def __init__(self, caught=None):
        self.caught = caught or []
        self.types = {}

    @property
    def exception(self):
        return self.caught[-1] if self.caught else None

    def __str__(self):
        return '<ExceptCatch groups={} n={} types={}>'.format(
            set(self.types), len(self.caught), {type(e).__name__ for e in self.caught})

    def __call__(self, name=None):
        try:  # only created once
            return self.types[name]
        except KeyError:  
            # only catch exceptions once they reach the top
            track = self.caught if name is None else False
            catcher = self.types[name] = _ExceptCatch(name, track)
            return catcher

    def __enter__(self):
        return self().__enter__()

    def __exit__(self, *a):
        # traceback.print_exc()
        return self().__exit__(*a)

    def raise_any(self):
        for e in self.caught[::-1]:
            raise e

class _ExceptCatch:
    def __init__(self, name, track=False):
        self.name = name
        self.track = [] if track is True else track

    def __str__(self):
        return '<ExceptCatch[{}]>'.format(self.name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_value and isinstance(exc_value, Exception):
            exc_value._exception_tracking_name_ = self.name
            if self.track is not False:
                self.track.append(exc_value)




def safe_exception(e):
    '''Make an exception with traceback that can survive pickling.'''
    if e is None:
        return
    if isinstance(e, (SafeException, GraphException)):
        return e
    e = SafeException(e)
    return e


# https://github.com/python/cpython/blob/5acc1b5f0b62eef3258e4bc31eba3b9c659108c9/Lib/concurrent/futures/process.py#L127
class _RemoteTraceback(Exception):
    def __init__(self, tb):
        self.tb = tb
    def __str__(self):
        return f'\n"""\n{"".join(self.tb)}"""'

class SafeException:
    '''A wrapper for exceptions that will preserve their tracebacks
    when pickling. Once unpickled, you will have the original exception
    with __cause__ set to the formatted traceback.'''
    def __init__(self, exc):
        self.exc = exc
        self.tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # self.tb = f'\n"""\n{"".join(self.tb)}"""'
    def __reduce__(self):
        return _rebuild_exc, (self.exc, self.tb)

def _rebuild_exc(exc, tb):
    exc.tb = tb
    exc.__cause__ = _RemoteTraceback(tb)
    return exc

RemoteException = SafeException