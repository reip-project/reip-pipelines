#%%
import functools
import reip

class InvalidTransition(RuntimeError):
    pass

class State:
    '''A single state that can be used as a boolean and context manager.
    
    You can request a state which will set the "potential" of the current state 
    (representing whether a state wants to be on or off)
    and all other states between the two state to either low or high depending 
    on what is needed to get to the requested state.
    TODO: should update potential as we are moving towards the requested state
          because sometimes we will move away from the requested state 
          (e.g. states.done.request(), then we do with states.closing)
    >>> states.running.request()  # request on (can pass True)
    >>> states.running.request(False)  # request off

    What using potential lets us do:
    >>> with states.configured:
    ...     while states.configured:
    ...         ...
    This will run the while loop until we have exited or want to exit the "configured" state.
    But the actual state changes are still handled by the context manager (seen by doing `states.running.value`).
    This lets you distinguish between "is the state actually finished?" or "is it still finishing? why does it say it is done, but it's hanging??"
    '''
    def __init__(self, name, default=False, parents=None, children=None):
        self._callbacks = {'before': [], 'after': [], 'request': []}
        self.name = name
        self.default = default
        self.value = default
        self.potential = 0
        # used in states model object - given default values for convenience/robustness
        self._parents = () if parents is None else parents
        self._children = set() if children is None else children
        self._tracked = False

    def __repr__(self):
        return '<State {}>'.format(self)

    def __str__(self):
        return '({}{}{})'.format(
            '✔' if self.value else '✘',
            '+' if self.potential > 0 else '-' if self.potential < 0 else '',
            self.name)

    def __hash__(self):
        '''Can be used in place of a name for dict lookups.'''
        return hash(self.name)

    def __bool__(self):
        '''Are we and should we be in a positive state? If false, either we're not in the state or we're trying to exit the state.'''
        return bool(self.potential > 0 or (self.value and self.potential == 0))

    def __eq__(self, other):
        '''Comparisons are done based on value, unless you're comparing with a string (which compares with the name).'''
        me = self.name if isinstance(other, str) else self.value
        other = other.value if isinstance(other, State) else other
        return me == other

    def __call__(self, value=True, notify=None, **kw):
        '''Set the state value.'''
        changed = self.value != value

        notify = changed if notify is None else notify  # by default, only do callback if the value changed.
        if notify:  # trigger callbacks for before change
            for callback_before in self._callbacks['before']:
                callback_before(self, value, **kw)

        if changed:
            if self.potential and bool(value) * 2 - 1 == self.potential:  # check if we met potential
                self.potential = 0
            self.value = value

        if notify:  # trigger callbacks for after change
            for callback_after in self._callbacks['after']:
                callback_after(self, value, **kw)
        return self

    def request(self, value=True, notify=None, **kw):
        '''Request a state change.'''
        changed = self.value != value
        self.potential = 0 if not changed else 1 if value else -1
 
        notify = changed if notify is None else notify
        if notify:  # trigger callbacks for request
            for callback_request in self._callbacks['request']:
                callback_request(self, value, **kw)
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
        '''Add callback functions to be called during the state's lifecycle.
        
        Examples:
        >>> @state.add_callback
        >>> def log(state, value): 
        ...     print(state, value)
        >>> state.add_callback('before', lambda state, value: print(state, value))
        >>> state.add_callback('request', print)
        >>> state.add_callback(print)  # defaults to 'after'
        '''
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
        # having a root null state simplifies things
        self.null = State(None)
        self.define(tree)
        # self._exit_stack = []
        # self._enter_stack = []

    def __str__(self):
        return '[{}]'.format('|'.join(
            str(state) for name, state in self._states.items() if state.value) or 'null')

    def treeview(self):
        '''Dumps a nested yaml-like view of the state tree.'''
        return _treeview_yml(self._states, self.null._children)

    def define(self, tree, *root, tracked=True):
        '''Define nested states.
        
        Arguments:
            tree (dict): a nested dictionary where the keys represent the state names and the 
                values are dicts containing any child states (if applicable).
            root (*str): the state names of the parent state to the tree.
            tracked (bool): whether we should track state updates for the tree and it's children.
                I added this because I wanted "error" to be able to be its own state. But I'm sure there 
                are other independent states like that.
        '''
        for key, children in tree.items():
            if key is not None:
                if key not in self._states:
                    state = self._states[key] = State(key, parents=root)
                    if tracked:
                        state.add_callback('request', self._on_state_update_request)
                        state.add_callback('before', self._on_state_update)
                        state._tracked = True
                # add as child in parent state
                child_set = (self._states[root[-1]] if root else self.null)._children
                child_set.add(key)

            if children:
                root_k = root + (key,) if key is not None else root
                self.define(children, *root_k, tracked=tracked and key is not None)

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

    def update_nested(self, value, *names):
        '''Recursively update all child states - can be used to turn off all child states.'''
        for name in names:
            state = self._states[name]
            state(value)
            self.update_nested(value, *state._children)

    def transition(self, state):
        '''Transition from the current state to a target state.'''
        if state is None:
            state = self.null
        if not isinstance(state, State):
            state = self._states[state]

        state, remove, add = self._get_transition(self._current, state, value, **kw)
        for k in remove:
            self._states[k](False, tracked=False)
        for k in add:
            self._states[k](True, tracked=False)

    # def to_desired(self):
    #     '''Transition to the desired state called by state.request().'''
    #     if self._desired is not None:
    #         self.transition(self._desired)

    _desired = None
    _current = None
    _updating = False
    _requesting = False
    def _on_state_update_request(self, state, value, tracked=True, **kw):
        '''Track state update requests. Requests updates for all of the other states between the current state and the desired state.'''
        if self._requesting or not tracked:  # prevent recursion
            return
        try:
            self._requesting = True

            state, remove, add = self._get_transition(self._current, state, value, **kw)
            for k in remove:
                self._states[k].request(False)
            for k in add:
                self._states[k].request(True)
            self._desired = state
        finally:
            self._requesting = False

    def _on_state_update(self, state, value, tracked=True, auto_transition=False, **kw):
        '''Track state updates. This makes sure that a state transition is valid.'''
        if self._updating or not tracked:  # prevent recursion
            return
        try:
            self._updating = True
            current = self._current
            if current is None:
                current = self.null

            state = self._check_state_transition(current, state, value, **kw)
            self._current = state if state is not self.null else None

            if value and self._desired is not None and state.name == self._desired.name:
                self._desired = None
        finally:
            self._updating = False

    def _check_state_transition(self, start, state, value, **kw):
        '''Check that a transition between two states is valid.'''
        if not value:
            assert start.name == state.name
            state = self._states[state._parents[-1]] if state._parents else self.null

        if state.name not in start._children and start.name not in state._children:
            raise InvalidTransition('state {} not in current state children {} and current state {} not in state children {}'.format(
                state, start._children, start, state._children))
        return state

    def _get_transition(self, start, state, value, auto_transition=True, **__):
        '''Get the states to remove+add to get from one state to another.'''
        start = self.null if start is None else start
        state = self.null if state is None else state
        # noop - no change of state needed
        if value and start.name == state.name:
            return state, (), ()
        # get the state parents
        current, target = start._parents, state._parents
        current_ = current + (start.name,) if start.name is not None else current
        target_ = target + (state.name,) if state.name is not None else target

        # turn off state
        if not value:
            # we're turning off this state, find the next highest state that is turned on.
            state = (
                next((s for s in (self._states[k] for k in target[::-1]) if s.value), None) 
                if auto_transition else self._states[target[-1]] if target else self.null)
            if state is None:  # go to null state
                return None, current_[::-1], ()
            target = state._parents

        if not auto_transition:  # check that we're going to an adjacent state.
            if state not in start._children and start not in state._children:
                raise InvalidTransition(
                    'Could not transition directly from {} to {}. '
                    'Please activate the intermediate states first.'.format(start, state))

        # find minimum path between current and target states
        i = next((
            i for i, (k1, k2) in enumerate(zip(current_, target_)) if k1 != k2), 
            min(len(current_), len(target_))) if current and target else 0
        remove, add = current[i:][::-1], target[i:]
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

    def reset(self, non_current=False):
        '''Reset states to their default values.'''
        if non_current:
            current = self._current
            stack = current._parents + (current.name,) if current is not None else ()
        for state in self._states.values():
            if not non_current or state.name not in stack:
                state.reset()


def _treeview_yml(states, keys, indent=0):
    tree = {str(states[k]): _treeview_yml(states, states[k]._children, indent=indent+1) for k in keys}
    return '\n'.join(' '*2*indent + k + ('\n' + v if v else '') for k, v in tree.items())


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
