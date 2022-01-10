import time
import timeit
import reip
import inspect

number = 100000

class ShowSource:
    def __init__(self, file):
        self.file = file
        self.prefix = f'{"="*20} {file} =\n'
        self.suffix = f'{"="*40}\n\n'

    def __enter__(self):
        self.start = inspect.currentframe().f_back.f_lineno

    def __exit__(self, *a):
        end = inspect.currentframe().f_back.f_lineno
        with open(self.file, 'r') as f:
            print(self.prefix + ''.join(f.readlines()[self.start:end]) + self.suffix)


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
def timt(code, number=number, compare=None):
    print('-'*20)
    print(f'-- Timing ({number:,}x):')
    print(code)
    t = timeit.timeit(code, globals=globals(), number=number)
    dt = t/number
    print(f'-- {dt:.6g}s/it. {t:.4f}s total.')
    if compare is not None:
        print(f'-- {dt / compare:.6f}x slower ({dt - compare:+.6g})')
    print('')
    return dt

def itimts(*codes, number=number, **kw):
    compare = None
    for code in codes:
        dt = timt(code, compare=compare, number=number, **kw)
        compare = compare or dt
        yield dt

def timts(*codes, **kw):
    return list(itimts(*codes, **kw))




with ShowSource(__file__):
    states = reip.util.States({'on'})
    on = states.on
    ro_on_ = reip.util.States({'on'}).on
    ro_on = reip.util.states.ReadOnlyState(ro_on_)
    mp_on_ = reip.util.States({'on'}).on
    mp_on = reip.util.states.ProcessSafeState(mp_on_)
    ro_mp_on_ = reip.util.States({'on'}).on
    ro_mp_on = reip.util.states.ReadOnlyProcessSafeState(ro_mp_on_)

    class Baseline:
        on=False
        def setvalue(self, value):
            self.on = value
        def __enter__(self):
            self.setvalue(True)
        def __exit__(self, *a):
            self.setvalue(False)
    baseline = Baseline()




BASELINE_METHOD = '''
# This is a baseline method where we are just changing the value of an attribute on an object
# this is the most basic state change we could do
baseline.setvalue(True)
bool(baseline.on)
baseline.setvalue(False)
bool(baseline.on)
'''

BASELINE_ATTRS = '''
# well, technically this is, but I'm comparing to a function call because we're probably going to
# want to have sooooome level of abstraction i.e. checking state changes, or notifying something else, etc.
baseline.on = True
bool(baseline.on)
baseline.on = False
bool(baseline.on)
'''

BASELINE_CONTEXT = '''
# any speed decrease here is likely because we're wrapping with another function call
with baseline:
    bool(baseline.on)
bool(baseline.on)
'''

ENABLE_DISABLE = '''
# Now we can actually test the state object. This shows end to end with looking up the 
# state from the state machine to calling and changing the state.
states.on()
bool(states.on)
states.on(False)
bool(states.on)
'''

ENABLE_DISABLE_WITH = '''
# This shows the state change with attribute lookup and context switching
with states.on:
    bool(states.on)
bool(states.on)
'''

ENABLE_DISABLE_NO_ATTR = '''
# and this is just the state change. This is arguably the most important because
# for performance critical code, we can do the attribute lookup at the top.
on()
bool(on)
on(False)
bool(on)
'''

ENABLE_DISABLE_WITH_NO_ATTR = '''
# and similarly, this is the speed of the value change via context manager.
with on:
    bool(on)
bool(on)
'''

# ENABLE_DISABLE_NO_NOTIFY = '''
# states.on(notify=False)
# bool(states.on)
# states.on(False, notify=False)
# bool(states.on)
# '''



ENABLE_DISABLE_REQUEST = '''
# This is the speed of requesting a state. This speed shouldn't matter as much because 
# requesting a state is mainly for when you want to close a block which isn't so time sensitive.
states.on.request()
bool(states.on)
states.on.request(False)
bool(states.on)
'''


# 

ENABLE_DISABLE_RO_NO_ATTR = '''
# This is the speed of changing a state and reading its value through a ReadOnlyState which
# serves as a proxy of the original state.
ro_on_()
bool(ro_on)
ro_on_(False)
bool(ro_on)
'''

ENABLE_DISABLE_MP_NO_ATTR = '''
# This is the speed of changing and reading a state that is managed using multiprocessing.Value.
# This does use a lock which is why it's so slow
mp_on()
bool(mp_on)
mp_on(False)
bool(mp_on)
'''

ENABLE_DISABLE_MP_RO_NO_ATTR = '''
# This is a read-only process-safe state proxy that could be used to interoperate with block 
# states between processes / tasks. This is the most important multiprocessing version.
# This does not have a lock, so it is suitable as long as you're not trying to change the 
# state from multiple processes (which you probably shouldn't be)
ro_mp_on_()
bool(ro_mp_on)
ro_mp_on_(False)
bool(ro_mp_on)

# e.g.
# block1 = Block()
# with reip.Task():
#     block2 = MyBlock(other_paused=block1.state.paused.process_safe())
'''


def compare(**kw):
    timts(
        BASELINE_METHOD, BASELINE_ATTRS, BASELINE_CONTEXT, 
        ENABLE_DISABLE, ENABLE_DISABLE_WITH, ENABLE_DISABLE_REQUEST, 
        ENABLE_DISABLE_NO_ATTR, ENABLE_DISABLE_WITH_NO_ATTR, 
        ENABLE_DISABLE_RO_NO_ATTR, ENABLE_DISABLE_MP_NO_ATTR, ENABLE_DISABLE_MP_RO_NO_ATTR, **kw)

    print('\nChecking States:\n')
    timts('baseline.on', 'states.on', 'on', 'ro_on', 'mp_on', 'ro_mp_on')


# def compare(**kw):
#     setval = lambda f, value: f'{f}({value})'
#     toggle = lambda f: f'{f}(True)\n{f}(False)'
#     check = lambda f: f'bool({f})'
#     toggle_check = lambda f, c: f'{f}(True)\n{check(c)}\n{f}(False)\n{check(c)}'
    
#     changes = ['baseline.setvalue', 'states.on', 'on', 'ro_on_', 'mp_on_', 'ro_mp_on_']
#     checks = ['baseline.on', 'states.on', 'on', 'ro_on', 'mp_on', 'ro_mp_on']
#     dt_change = timts(*(toggle(f) for f in changes))
#     dt_check = timts(*(check(f) for f in checks))
#     dt_check = timts(*(toggle_check(f, c) for f, c in zip(changes, checks)))

if __name__ == '__main__':
    import fire
    fire.Fire()
