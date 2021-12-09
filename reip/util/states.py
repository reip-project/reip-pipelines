'''

Basic State Mechanics:

I wanted states to feel as organic as possible while not adding too much weight to enabling/disabling/checking them.

.. code-block:: python

    # creating a state machine
    states = reip.util.States({'mode1', 'mode2'})

    # turning on a state
    states.mode1()
    states.mode1 = True
    states['mode1'] = True

    # checking if a state is active
    assert states.mode1
    assert not states.mode2

    if states.mode1:
        ...
    else states.mode2:
        ...
    else:
        ...

    # turning off a state
    states.mode1(False)
    states.mode1 = False
    states['mode1'] = False

    # checking if a state is inactive
    assert not states.mode1
    assert not states.mode2

    # turning on/off within a context manager
    with states.mode1:
        assert states.mode1
    assert not states.mode1

Requesting a state configuration (i.e. from another thread):

(simple example):

.. code-block:: python

    # hierarchical state model: while running you can be in mode1 or mode2 (or neither)
    states = reip.util.States({
        'running': {'mode1', 'mode2'},
    })

    with states.running:        # activate running inside this context
        while states.running:   # run while states.running wants to be active
            if should_exit():
                break

            # here we have two possible states that we can alternate between

            if states.mode1:             # check if mode1 wants to be active
                with states.mode1:       # activate mode1 inside this context
                    while states.mode1:  # run while mode1 wants to be active
                        if should_switch_modes():
                            states.mode2.request()  # set the potential of mode1 to -1 and mode2 to 1
                        ...

            elif states.mode2:           # check if mode2 wants to be active
                with states.mode2:       # activate mode2 inside this context
                    while states.mode2:  # run while mode2 wants to be active
                        if should_switch_modes():
                            states.mode1.request()  # set the potential of mode2 to -1 and mode1 to 1
                        ...

            else:  # if for some reason no modes are active, just default to mode1
                states.mode1.request()  # set the potential of mode1 to 1

    # you're also free to assign a state to a variable (for performance reasons perhaps) and it will still work the same way
    mode1 = states.mode1
    if mode1:             # check if mode1 wants to be active
        with mode1:       # activate mode1 inside this context
            while mode1:  # run while mode1 wants to be active
                ...
    # this won't have to lookup the attribute everytime.

States are made up of two internal states ``value`` and ``potential``. ``value`` is the actual value of the state 
and is handled by the controlling code. This is what is changed when you do ``state.enabled(False)``.

But we also want a way for someone outside the controlling thread to say: "You should make your way into the 'off' state." 
This is done using ``state.enabled.request(False)``.

To this end, the boolean-ness of a state is actually a combination of their actual state and their potential. If a state is
off, but it has potential=1, ``if state.enabled`` will evaluate to True, because we want it to be active (and 
vice-versa for a potential of -1). If the potential is 0, then it will just be equal to the state.
If you want the actual current value, just use ``state.enabled.value``.

.. code-block:: python

    def running_in_a_thread():
        with states.enabled:  # make sure it's enabled to start with
            while states.enabled:
                do_something()
                time.sleep(1)

    # ... start thread
    states.enabled.request(False)  # makes `while states.enabled:` return False
    # ... join thread


Traffic Light Example:
.. code-block:: python

    # creating states for a traffic light
    states = reip.util.States({
        'on': {'red', 'yellow', 'green'},
    })

    # add a callback function that gets called whenever a state changes
    @states.add_callback
    def change_color_on_change(state, value):
        if state in states.on:  # checking if its a child state of "on"
            set_color(state.name)  # set color as red, yellow, green

    # add a callback for just the red state
    @states.red.add_callback
    def debug_red_state(state, value):
        print('State', state, 'set to be', value)

    def set_color(color): ...

    def run(control_queue, yellow_delay=2):
        with states.red:  # initial state: red
            while states.on:
                can_go = control_queue.get(block=True)
                if can_go:
                    states.green()
                else:
                    if states.red:
                        continue

                    # switch to yellow for a little bit
                    with states.yellow:
                        time.sleep(yellow_delay)
                    # switch to red
                    states.red()

    # run this is a background thread
    th = threading.Thread(target=run, ...)
    th.start()

    # lets change the light back and forth 
    time.sleep(3)
    for _ in range(6):
        # go green for 4 seconds
        control_queue.put(True)
        time.sleep(4)
        # go red for 4 seconds (+yellow for 2 seconds)
        control_queue.put(False)
        time.sleep(6)

    states.on.request(False)  # ask the state to turn off
    th.join()

'''
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
        # return bool(self.potential > 0 or (self.value and self.potential == 0))
        return self.value + self.potential > 0  # 0+0(False), 0+1(True), 1+0(True), 1-1(False)

    def __eq__(self, other):
        '''Comparisons are done based on value, unless you're comparing with a string (which compares with the name).'''
        me = self.name if isinstance(other, str) else self.value
        other = other.value if isinstance(other, State) else other
        return me == other

    def __contains__(self, child):
        return child in self._children

    def __call__(self, value=True, notify=None, **kw):
        '''Set the state value.'''
        changed = self.value != value

        if notify is None:  # by default, only do callback if the value changed.
            notify = changed
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
        '''Request a state change. This does not change the value of a state,
        only the potential of this state and all states in between this state 
        and the current state.'''
        changed = self.value != value
        self.potential = 0 if not changed else 1 if value else -1
 
        if notify is None:
            notify = changed
        if notify:  # trigger callbacks for request
            for callback_request in self._callbacks['request']:
                callback_request(self, value, **kw)
        return self

    def cancel_request(self):
        self.potential = 0
        return self


    # alternative interfaces

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


    # callbacks

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


class ReadOnlyState(State):
    '''This provides a wrapper around a State object 
    that is read only, meaning that the wrapper prevents 
    modifying the state through it's interface. The 
    underlying state is still allowed to change.

    XXX: UNFINISHED and UNTESTED !!
    '''
    def __init__(self, state):
        self.state = state

    # prevent changing state

    def __call__(self, *a, **kw):  # TODO callbacks
        return self

    def request(self, *a, **kw):
        return self

    # prevent writing attributes

    @property
    def value(self):
        return self.state.value

    @value.setter
    def value(self, value):
        pass

    @property
    def potential(self):
        return self.state.potential

    @potential.setter
    def potential(self, potential):
        pass



class ProcessSafeState(State):
    def __init__(self, *a, **kw):
        import multiprocessing as mp
        self._value = mp.Value('i', 0)
        self._potential = mp.Value('i', 0)
        super().__init__()

    @property
    def value(self):
        return self._value.value

    @value.setter
    def value(self, value):
        self._value.value = value

    @property
    def potential(self):
        return self._potential.value

    @potential.setter
    def potential(self, value):
        self._potential.value = value


def sync_states(source, *states):  # lol thought it'd be more complicated
    for state in states:
        source.add_callback(state)
    # TODO: support bidirectional syncing without blowing up?

def sync_states_bidirectional(stateA, stateB):
    def sync(a, b):
        def _sync(value, sync_response=False):
            if sync_response:
                return
            b(value, sync_response=True)
        a.add_callback(_sync)
    sync(stateA, stateB)
    sync(stateB, stateA)
    # TODO: support multiple chained states (a->b, b->c)


def sync_states_bidirectional_chained(stateA, stateB):  # idk I'm sure this will break in some ways
    def sync(a, b):
        def _sync(value, sync_response=False):
            b_id = id(b)
            if sync_response == b_id:
                return
            b(value, sync_response=b_id)
        a.add_callback(_sync)
    sync(stateA, stateB)
    sync(stateB, stateA)
    # TODO: support multiple chained states (a->b, b->c)


class States:
    '''A hierarchical state model.'''
    def __init__(self, tree=None, **kw):
        self._states = {}
        # having a root null state simplifies things
        self.null = State(None)
        self._current = self.null
        self.define(tree or {}, **kw)

    def __str__(self):
        return '[{}]'.format('|'.join(
            str(state) for name, state in self._states.items() 
            if state.value and not state.name.startswith('_')) or 'null')

    def treeview(self):
        '''Dumps a nested yaml-like view of the state tree.'''
        return _treeview_yml(self._states, self.null._children)

    def define(self, tree, *root, validate=True, request_tracing=True):
        '''Define nested states.
        
        Arguments:
            tree (dict): a nested dictionary where the keys represent the state names and the 
                values are dicts containing any child states (if applicable).
            root (*str): the state names of the parent state to the tree.
            tracked (bool): whether we should track state updates for the tree and it's children.
                I added this because I wanted "error" to be able to be its own state. But I'm sure there 
                are other independent states like that.
        '''
        if isinstance(tree, (set, list, tuple)):
            tree = {k: {} for k in tree}
        for key, children in tree.items():
            if key is not None:
                if key not in self._states:
                    state = self._states[key] = State(key, parents=root)
                    if validate:
                        state.add_callback('before', self._on_state_update)
                    if request_tracing:
                        state.add_callback('request', self._on_state_update_request)
                # add as child in parent state
                child_set = (self._states[root[-1]] if root else self.null)._children
                child_set.add(key)

            if children:
                disconnected = key is None
                self.define(
                    children, *(root + (key,) if key is not None else root),
                    validate=validate and not disconnected,
                    request_tracing=request_tracing and not disconnected)

    def __getitem__(self, key):
        '''Get a state by name.'''
        return self._states[key]

    def __getattr__(self, key):
        '''Get a state by name.'''
        if key[0] != '_':
            try:
                return self._states[key]
            except KeyError:
                pass
        raise AttributeError(key)

    def __setattr__(self, key, value):
        '''Set a state value.'''
        if key[0] != '_':
            states = self._states
            if key in states:
                return states[key](value)
        self.__dict__[key] = value

    def __setitem__(self, key, value):
        '''Set a state value.'''
        self._states[key](value)

    def __contains__(self, state):
        return state in self._states

    def update(self, states):
        '''Update the values of multiple states.'''
        for name, value in states.items():
            self._states[name](value)
        return self

    def update_nested(self, value, *names):
        '''Recursively update all child states - can be used to turn off all child states.'''
        for name in names:
            state = self._states[name]
            state(value)
            self.update_nested(value, *state._children)

    def transition(self, state, value=True, **kw):
        '''Transition from the current state to a target state.'''
        state = self._states[state] if state is not None else self.null
        state, remove, add = self._get_transition(self._current, state, value, **kw)
        for k in remove:
            self._states[k](False, validate=False)
        for k in add:
            self._states[k](True, validate=False)

    def _on_state_update(self, state, value, validate=True, **kw):
        '''Track state updates. This makes sure that a state transition is valid.'''
        if not validate:
            return
        self._current = self._check_state_transition(self._current, state, value, **kw)

    def _on_state_update_request(self, state, value, transition=True, **kw):
        '''Track state update requests. Requests updates for all of the other states between the current state and the desired state.'''
        if not transition:  # prevent recursion
            return
        state, remove, add = self._get_transition(self._current, state, value, **kw)
        for k in remove:
            self._states[k].request(False, transition=False)
        for k in add:
            self._states[k].request(True, transition=False)

    def _check_state_transition(self, start, state, value, **kw):
        '''Check that a transition between two states is valid.'''
        if not value:
            assert start.name == state.name
            return self._states[state._parents[-1]] if state._parents else self.null

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
            stack = current._parents + (current.name,) if current is not self.null else ()
        for state in self._states.values():
            if not non_current or state.name not in stack:
                state.reset()


def _treeview_yml(states, keys, indent=0, include_private=False, indent_width=2):
    tree = {
        str(states[k]): _treeview_yml(
            states, states[k]._children, 
            indent=indent+1, include_private=include_private) 
        for k in keys if include_private or not k.startswith('_')
    }
    return '\n'.join(' '*indent_width*indent + k + ('\n' + v if v else '') for k, v in tree.items())


if __name__ == '__main__':

    state = States({'started', 'ready', 'running', 'closed', 'done', 'terminated'})

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
