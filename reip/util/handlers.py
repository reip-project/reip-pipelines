'''
Manage a list of functions/context managers as if they are one.
'''
import contextlib


@contextlib.contextmanager
def lineprofile():
    import pyinstrument
    prof = pyinstrument.Profiler()
    prof.start()
    yield
    prof.stop()
    print(prof.output_text(unicode=True, color=True))


@contextlib.contextmanager
def suppress(*excs):
    try:
        yield
    except excs or (Exception,):
        pass

@contextlib.contextmanager
def heartrate():
    import heartrate
    heartrate.trace(browser=True)
    yield
