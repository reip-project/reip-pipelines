import timeit
import reip

states = reip.util.States({'on'}, validate=True)

class Baseline:
    on=False
    def setvalue(self, value):
        self.on = value
    def __enter__(self):
        self.on = True
    def __exit__(self, *a):
        self.on = False
baseline = Baseline()


BASELINE_METHOD = '''
baseline.setvalue(True)
bool(baseline.on)
baseline.setvalue(False)
bool(baseline.on)
'''

BASELINE_ATTRS = '''
baseline.on = True
bool(baseline.on)
baseline.on = False
bool(baseline.on)
'''

BASELINE_CONTEXT = '''
with baseline:
    bool(baseline.on)
bool(baseline.on)
'''

ENABLE_DISABLE = '''
states.on()
bool(states.on)
states.on(False)
bool(states.on)
'''

on = states.on
ENABLE_DISABLE_NO_ATTR = '''
on()
bool(on)
on(False)
bool(on)
'''

ENABLE_DISABLE_WITH_NO_ATTR = '''
with on:
    bool(on)
bool(on)
'''

ENABLE_DISABLE_NO_NOTIFY = '''
states.on(notify=False)
bool(states.on)
states.on(False, notify=False)
bool(states.on)
'''

ENABLE_DISABLE_WITH = '''
with states.on:
    bool(states.on)
bool(states.on)
'''

ENABLE_DISABLE_REQUEST = '''
states.on.request()
bool(states.on)
states.on.request(False)
bool(states.on)
'''


def compare(**kw):
    base = timt(BASELINE_METHOD, **kw)
    timt(BASELINE_ATTRS, compare=base, **kw)
    timt(BASELINE_CONTEXT, compare=base, **kw)
    
    timt(ENABLE_DISABLE, compare=base, **kw)
    timt(ENABLE_DISABLE_WITH, compare=base, **kw)
    timt(ENABLE_DISABLE_REQUEST, compare=base, **kw)
    timt(ENABLE_DISABLE_NO_NOTIFY, compare=base, **kw)
    timt(ENABLE_DISABLE_NO_ATTR, compare=base, **kw)
    timt(ENABLE_DISABLE_WITH_NO_ATTR, compare=base, **kw)



def maybe_profile(func):
    def wrap(*a, profile=False, interval=0.01, **kw):
        if profile:
            import pyinstrument
            p = pyinstrument.Profiler(interval=interval)
            try:
                with p:
                    return func(*a, **kw)
            finally:
                print(p.output_text())
        return func(*a, **kw)
    return wrap

@maybe_profile
def timt(code, number=1000000, compare=None):
    print('-'*20)
    print(f'-- Timing ({number:,}x):')
    print(code)
    t = timeit.timeit(code, globals=globals(), number=number)
    dt = t/number
    print(f'-- {dt:.6g}s/it. {t:.4f}s total.')
    if compare is not None:
        print(f'-- {dt / compare:.6f}x slower')
    print('')
    return dt

def timts(*codes, **kw):
    compare = None
    for code in codes:
        dt = timt(code, compare=compare, **kw)
        compare = compare or dt




if __name__ == '__main__':
    import fire
    fire.Fire()
