


class ParameterError(TypeError):
    pass


class RunExit(BaseException):
    pass


class ReipControl(BaseException):
    pass

class WorkerExit(ReipControl):
    pass







class ExceptionTracker:
    def __init__(self):
        self.caught = []
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
        return self().__exit__(*a)

    def raise_any(self):
        for e in self.caught:
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

# # https://github.com/python/cpython/blob/5acc1b5f0b62eef3258e4bc31eba3b9c659108c9/Lib/concurrent/futures/process.py#L127
# class _RemoteTraceback(Exception):
#     def __init__(self, tb):
#         self.tb = tb
#     def __str__(self):
#         return self.tb

# class RemoteException:
#     '''A wrapper for exceptions that will preserve their tracebacks
#     when pickling. Once unpickled, you will have the original exception
#     with __cause__ set to the formatted traceback.'''
#     def __init__(self, exc):
#         self.exc = exc
#         self.tb = '\n"""\n{}"""'.format(''.join(
#             traceback.format_exception(type(exc), exc, exc.__traceback__)
#         ))
#     def __reduce__(self):
#         return _rebuild_exc, (self.exc, self.tb)

# def _rebuild_exc(exc, tb):
#     exc.__cause__ = _RemoteTraceback(tb)
#     return exc
