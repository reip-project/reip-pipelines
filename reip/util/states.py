#%%
import functools


class State:
    '''A single state that can be used as a boolean and context manager.'''
    def __init__(self, name, default=False):
        self._callbacks = {'before': [], 'after': [], 'request': []}
        self.name = name
        self.default = default
        self.value = default
        self.potential = 0

    def __repr__(self):
        return '<State {}>'.format(self)

    def __str__(self):
        return '({}{}{})'.format(
            '✔' if self.value else '✘', self.name, 
            '+' if self.potential > 0 else '-' if self.potential < 0 else '') # '↑' if self.potential > 0 else '↓' if self.potential < 0 else ''

    def __hash__(self):
        '''Can be used in place of a name for dict lookups.'''
        return hash(self.name)

    def __bool__(self):
        '''Are we and should we be in a positive state? If false, either we're not in the state or we're trying to exit the state.'''
        return bool(self.potential > 0 or (self.value and self.potential == 0))

    @property
    def current(self):
        '''The current value of the state.'''
        return bool(self.value)

    def __eq__(self, other):
        '''Comparisons are done based on value, unless you're comparing with a string (which compares with the name).'''
        me = self.name if isinstance(other, str) else self.value
        other = other.value if isinstance(other, State) else other
        return me == other

    def __call__(self, value=True, notify=None):
        '''Set the state value.'''
        changed = self.value != value
        notify = changed if notify is None else notify  # by default, only do callback if the value changed.
        if notify:  # trigger callbacks for before change
            for func in self._callbacks['before']:
                func(self, value)

        if changed:
            if self.potential and bool(value) * 2 - 1 == self.potential:  # check if we met potential
                self.potential = 0
            self.value = value

        if notify:  # trigger callbacks for after change
            for func in self._callbacks['after']:
                func(self, value)
        return self

    def request(self, value=True, notify=None):
        '''Request a state change.'''
        changed = self.value != value
        self.potential = 0 if not changed else 1 if value else -1
        notify = changed if notify is None else notify
        if notify:  # trigger callbacks for request
            for func in self._callbacks['request']:
                func(self, value)
        return self

    def __enter__(self):
        return self(True)

    def __exit__(self, *a):
        self(False)

    def on(self):
        return self(True)

    def off(self):
        return self(False)

    def toggle(self):
        '''Toggle the state.'''
        return self(not self.value)

    def reset(self):
        '''Reset the value to it's default value (provided at instantiation).'''
        return self(self.default)

    def add_callback(self, name=None, func=None):
        '''Add callback functions to be called during the state's lifecycle.'''
        def add_cb(func, name=None):
            self._callbacks[name or 'after'].append(func)
            return func
        return (
            add_cb(func, name) if callable(func) else 
            add_cb(name) if callable(name) else 
            lambda func: add_cb(func, name))

    def wrap(self, func):
        '''Enable a state for the lifetime of a function.'''
        @functools.wraps(func)
        def inner(*a, **kw):
            with self:
                return func(*a, **kw)
        return inner





class States:
    '''A hierarchical state model.'''
    def __init__(self, tree):
        self._states = {}
        self.define(tree)

    def __str__(self):
        return '({})'.format('+'.join(
            str(state) for name, state in self._states.items() if state.current) or '- null -')

    def define(self, tree, *root, tracked=True):
        '''Define states.
        
        Arguments:
            tree (dict): a nested dictionary where the keys represent the state names and the 
                values are dicts containing any child states (if applicable).
            root (*str): the state names of the parent state to the tree.
            tracked (bool): whether we should track state updates for the tree and it's children.
                I added this because I wanted "error" to be able to be its own state. But I'm sure there 
                are other independent states like that.
        '''
        for key, children in tree.items():
            if key is not None and key not in self._states:
                state = self._states[key] = State(key)
                state._parents = root
                state._children = set(children)
                if tracked:
                    state.add_callback('request', self._on_state_update_request)
                    state.add_callback('before', self._on_state_update)
            if children:
                self.define(children, *root, key, tracked=tracked and key is not None)

    def __getitem__(self, key):
        '''Get a state by name.'''
        return self._states[key]

    def __getattr__(self, key):
        '''Get a state by name.'''
        try:
            if not key.startswith('_'):
                return self._states[key]
        except KeyError:
            pass
        raise AttributeError(key)

    def __setattr__(self, key, value):
        '''Set a state value.'''
        if not key.startswith('_') and key in self._states:
            return self._states[key](value)
        super().__setattr__(key, value)

    def __setitem__(self, key, value):
        '''Set a state value.'''
        self._states[key](value)

    def update(self, states):
        '''Update the values of multiple states.'''
        for name, value in state.items():
            self._states[name](value)
        return self

    _desired = None
    _current = None
    _updating = False
    _requesting = False
    def _on_state_update_request(self, state, value):
        '''Track state update requests. Requests updates for all of the other states between the current state and the desired state.'''
        if self._requesting:  # prevent recursion
                return
        try:
            self._requesting = True

            state, remove, add = self._get_transition(self._current, state, value)
            for k in remove:
                self._states[k].request(False)
            for k in add:
                self._states[k].request(True)
            self._desired = state
        finally:
            self._requesting = False

    def _on_state_update(self, state, value):
        '''Track state updates. Updates all of the other states between the current state and the desired state.'''
        if self._updating:  # prevent recursion
            return
        try:
            self._updating = True

            state, remove, add = self._get_transition(self._current, state, value)
            for k in remove:
                self._states[k](False)
            for k in add:
                self._states[k](True)
            self._current = state
            if value and self._desired is not None and state.name == self._desired.name:
                self._desired = None
        finally:
            self._updating = False

    def _get_transition(self, start, state, value):
        '''Get the states to add remove to get from one state to another.'''
        add, remove = (), ()
        stack = start._parents + (start.name,) if start is not None else ()
        parents = state._parents if state is not None else ()
        if value:  # state enabled, disable/enable any states that are not shared between the two
            i = next((i for i, (k1, k2) in enumerate(zip(stack, parents)) if k1 != k2), min(len(stack), len(parents)))
            remove, add = stack[i:][::-1], parents[i:]
        elif start is not None and state is not None and start.name == state.name:
            state = next((s for s in (self._states[k] for k in parents[::-1]) if s), None)
        return state, remove, add

    def add_callback(self, name=None, func=None):
        '''Add a callback to all states. Useful for logging and debugging.'''
        def add_cb(func, name=None):
            for s in self._states.values():
                s.add_callback(name, func)
            return func
        return (
            add_cb(func, name) if callable(func) else 
            add_cb(name) if callable(name) else 
            lambda func: add_cb(func, name))

    def reset(self, **values):
        '''Reset states to their default values.'''
        for state in self._states.values():
            state.reset()



class BasicStates:
    '''A basic state model. All states are independently controlled.'''
    STATES = []
    def __init__(self, *names):
        self._states = {}
        self.define(*(self.STATES or ()), *names)
    
    def __str__(self):
        return '[{}]'.format('+'.join(
            name for name, state in self._states.items() if state) or '- null -')

    def define(self, *names):
        '''Add new states.'''
        for name in names:
            if name not in self._states:
                self._states[name] = State(name)

    def __getitem__(self, key):
        '''Get the state object by name.'''
        return self._states[key]

    def __getattr__(self, key):
        '''Get the state object by name.'''
        try:
            if not key.startswith('_'):
                return self._states[key]
        except KeyError:
            pass
        raise AttributeError(key)

    def __setattr__(self, key, value):
        '''Set a state value.'''
        if not key.startswith('_') and key in self._states:
            return self._states[key](value)
        super().__setattr__(key, value)

    def __setitem__(self, key, value):
        '''Set a state value.'''
        self._states[key](value)

    def reset(self):
        '''Reset states to their default values.'''
        for state in self._states.values():
            state.reset()



if __name__ == '__main__':

    class BlockStates(BasicStates):
        STATES = 'started', 'ready', 'running', 'closed', 'done', 'terminated'

    state = BlockStates()

    print(state)
    print(state._states)
    state.started()
    print(state)
    with state.ready:
        print(state)
        with state.running:
            print(state)
        print(state)
    state.done = True
    print(state)
    state.started = False
    print(state)


    state = States({
        'spawned': {
            'initializing': {},
            'ready': {
                'waiting': {},
                'processing': {},
                'idle': {}
            },
            'closing': {},
        },
        'done': {
            'error': {},
            'terminated': {},
        },
    })
    

    @state.add_callback('after')
    def log_changes(state, value):
        # if not block.state.ready:
        print('\tchg: {} - changed to {}'.format(state, value))

    @state.add_callback('request')
    def log_changes(state, value):
        # if not block.state.ready:
        print('\treq: {} - requested changed to {}'.format(state, value))

    # import time

    print('-'*20)
    print(state)
    with state.spawned:
        print(state)
        with state.initializing:
            print('initializing...', state)
        try:
            assert not state.ready
            with state.ready:
                for i in range(15):
                    if not state.ready:
                        print('breaking!!')
                        break
                    print(i)
                    if i == 6:
                        state.idle()
                    if i == 8:
                        state.idle.off()
                    
                    assert state.ready
                    assert not state.waiting
                    if state.idle:
                        continue

                    with state.waiting:
                        assert state.ready
                        assert state.waiting
                        print('waiting...', state)
                        # time.sleep(0.5)
                    assert not state.waiting

                    with state.processing:
                        assert state.processing
                        print('processing...', state)
                        # time.sleep(0.2)
                    assert not state.processing
                    if i == 10:
                        state.done.request()
            assert not state.ready
        except Exception as e:
            print('caught:', type(e).__name__, e)
        finally:
            assert not state.ready
            with state.closing:
                assert state.closing
                print('closing...', state)
            assert not state.closing
    state.done()
    print(state)

# %%
