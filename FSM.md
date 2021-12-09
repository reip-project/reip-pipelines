# Proposed State Machine Mechanics in REIP

## At it's core, this is how the (draft) finite state machines work:

(NOTE: this is for illustration purposes and is not 100% complete code)

The individual state (a value ( `bool` ) and a potential ( ∈ `[-1, 0, 1]` - think potential energy of the state value )):

```python

class State:
    value = False
    potential = 0
    def __init__(self, name):
        self.name = name
        self._callbacks = {'before': [], 'after': [], 'request': []}

    def __call__(self, value=True):
        '''Set the state value.'''
        if value == self.value:
            return

        for callback in self._callbacks['before']:
            callback(self, value)

        # change the state
        self.value = value
        # check if the potential has been satisfied
        if self.potential and bool(value) * 2 - 1 == self.potential:
            self.potential = 0

        for callback in self._callbacks['after']:
            callback(self, value)

    def request(self, value):
        '''Request a state value'''
        self.potential = 0 if self.value == value else 1 if value else -1
        for callback in self._callbacks['request']:
            callback(self, value)

    def __bool__(self):
        '''Are we (or should we be) in this state?'''
        return self.value + self.potential > 0  # 0+0(False), 0+1(True), 1+0(True), 1-1(False)

    # context manager
    def __enter__(self): self(True)
    def __exit__(self, *a): self(False)

```

and the state machine (a dictionary of states):

```python

class States:
    def __init__(self, tree):
        self.null = State(None)
        self._current = self.null

        self._states = {}  
        self.define(tree)
        # tree is nested dict of state names and their children
        # _states is flat dict for all states: { name: State(name), ... }

    def __getattr__(self, name):
        '''Get a state by name'''
        return self._states[name]

    def define(self, tree, *parents):
        '''Initialize the state tree.'''
        for name, children in tree.items():
            state = self._states[name] = State(name, parents=parents)
            state.add_callback('before', self._on_state_update)
            state.add_callback('request', self._on_state_update_request)
            # add as child in parent state
            (self._states[parents[-1]] if parents else self.null)._children.add(name)

            if children:
                self.define(children, *(parents + (name,)))

    def _on_state_update(self, state, value):
        '''check that a state transition is valid'''
        self._current = self._check_state_transition(self._current, state, value)

    def _on_state_update_request(self, state, value, transition=True):
        '''tell intermediate states if they should turn on/off'''
        if not transition: 
            return

        remove, add = self._get_transition(self._current, state, value)
        for k in remove:
            self._states[k].request(False, transition=False)
        for k in add:
            self._states[k].request(True, transition=False)

```

## Here's what a block's state definition would look like:

```python

self.state = reip.util.states.States({
    'spawned': {
        'configured': {
            'initializing': {},
            'ready': {
                'waiting': {},
                'processing': {},
                'paused': {},
            },
            'finishing': {},
        },
        'needs_reconfigure': {},
    },
    'done': {}
})

```

## And here's how the block core could look:

```python

class Block:

    def __main(self):
        # the top level loop:
        with self.state.spawned:
            while self.state.spawned:
                if not self.state.configured:
                    self.__reconfigure()
                self.__run_configured()

    def __run_configured(self):
        sw, exc = self._sw, self._except
        try:
            with self.state.initializing, sw('init'), exc('init'):
                self.init()

            ready, processing, paused = (
                self.state.ready, self.state.processing, self.state.paused)
            with ready:
                while ready:
                    time.sleep(self._delay)
                    if paused:
                        continue
                    # do throttling, check time limit, etc...
                    # check if we have data in sources, etc.

                    # were good to go! let's process our next batch
                    with processing:
                        # read
                        with sw('source'):
                            inputs = self.__read_sources()
                            if inputs is None:
                                continue
                            buffers, meta = inputs

                        # process
                        with sw('process'), exc('process'):
                            outputs = self.__process_buffer(buffers, meta)

                        # write
                        with sw('sink'):
                            self.__send_to_sinks(outputs, meta)

        except KeyboardInterrupt:
            self.log.info(text.yellow('Interrupting'))
            self.terminate()
        finally:
            with self.state.finishing, sw('finish'), exc('finish'):
                self.finish()
```

## Performance

Setup:
```python
states = reip.util.States({'on'}, validate=True)
on = states.on

class Baseline:
    on=False
    def setvalue(self, value):
        self.on = value
    def __enter__(self):
        self.on = True
    def __exit__(self, *a):
        self.on = False
baseline = Baseline()
```

Results:
```bash
python experiments/states_speed.py compare
```
```
--------------------
-- Timing (1,000,000x):

baseline.setvalue(True)
bool(baseline.on)
baseline.setvalue(False)
bool(baseline.on)

-- 4.34084e-07s/it. 0.4341s total.

--------------------
-- Timing (1,000,000x):

baseline.on = True
bool(baseline.on)
baseline.on = False
bool(baseline.on)

-- 2.79461e-07s/it. 0.2795s total.
-- 0.643794x slower

--------------------
-- Timing (1,000,000x):

with baseline:
    bool(baseline.on)
bool(baseline.on)

-- 4.74217e-07s/it. 0.4742s total.
-- 1.092454x slower

--------------------
-- Timing (1,000,000x):

states.on()
bool(states.on)
states.on(False)
bool(states.on)

-- 4.18522e-06s/it. 4.1852s total.
-- 9.641506x slower

--------------------
-- Timing (1,000,000x):

with states.on:
    bool(states.on)
bool(states.on)

-- 4.03224e-06s/it. 4.0322s total.
-- 9.289079x slower

--------------------
-- Timing (1,000,000x):

states.on.request()
bool(states.on)
states.on.request(False)
bool(states.on)

-- 3.65265e-06s/it. 3.6526s total.
-- 8.414608x slower

--------------------
-- Timing (1,000,000x):

states.on(notify=False)
bool(states.on)
states.on(False, notify=False)
bool(states.on)

-- 2.76043e-06s/it. 2.7604s total.
-- 6.359211x slower

--------------------
-- Timing (1,000,000x):

on()
bool(on)
on(False)
bool(on)

-- 2.35671e-06s/it. 2.3567s total.
-- 5.429166x slower

```