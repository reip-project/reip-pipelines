import functools
import reip

def synchronized(key='time', tol=0):
    def outer(func):
        @functools.wraps(func)
        def inner(self, *xs, meta):
            ts = [m[key] for m in meta.inputs]
            dts = [t - ts[0] for t in ts]
            if any(abs(t) > tol for t in dts):
                return reip.RETRY
            return func(self, *xs, meta=meta)
        return inner
    return outer