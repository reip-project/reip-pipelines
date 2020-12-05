''''''
import copy
import time
# import reip


def copymod(obj, __no_new_attrs=False, **kw):
    '''copy an object and overwrite attributes.'''
    if __no_new_attrs:  # only allow overwriting attributes that already exist
        unknown_kw = set(kw) - set(obj.__dict__)
        if unknown_kw:
            raise TypeError('Unknown kwargs: {}'.format(unknown_kw))

    obj = copy.copy(obj)
    obj.__dict__.update(kw)
    return obj

def maybe_call(__obj, __name, *a, **kw):
    '''call a method if the object has it as an attribute.
    e.g. maybe_call(state, 'on_spawn', 1, 2, somearg=3)
    '''
    func = getattr(__obj, __name, None)
    if func is not None:
        return func(*a, **kw)


class BaseState:
    name = None
    instance = None

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, str(self))

    _map_name = None
    def __get__(self, instance, owner=None):
        '''Called when a state is accessed from a class. Gives the state access
        to the instance.'''
        if instance is None:  # called when gotten from a class, not instance. ignore.
            return self
        if isinstance(instance, BaseState):  # handle weird cases like state in state
            instance = instance.instance
            if instance is None:
                return self
        map_ = getattr(instance, self._map_name, None)
        if map_ is None:  # in case a state is added to some non-statemodel instance
            return self
        x = map_[self.name]
        if x.instance is None:  # bind instance - should only happen once per instance per state
            x = map_[self.name] = self._with_instance(instance)
        return x

    def _with_name(self, name):
        '''Add a name to the state.'''
        self.name = self.name or name
        return self

    def _with_instance(self, instance):
        '''Add an instance to the state.'''
        return copymod(self, instance=instance)

    def _require_instance(self):
        if self.instance is None:
            raise ValueError('{} has no bound instance.'.format(self))
        return self.instance


class State(BaseState):
    '''Represents a state that a model can be in.'''
    _map_name = '_states_map'
    def __init__(self, action=None, name=None, initial=False, final=False):
        if isinstance(action, str):
            action, name = None, action
        self.action = action
        self.name = name or getattr(action, '__name__', None)
        self.initial = initial
        self.final = final

    def __str__(self):
        return '{}{}'.format(
            self.name, '[{}]'.format('*' if self else '') if self.instance is not None else '')

    def __bool__(self):
        '''Test that a state is active.'''
        return self._require_instance().state.name == self.name

    def __call__(self, *a, force=False, **kw):
        '''Run the state action code.'''
        maybe_call(self.instance, 'before_{}'.format(self.name), *a, **kw)
        if self.set() or force:
            maybe_call(self.instance, 'on_{}'.format(self.name), *a, **kw)
            if self.action is not None:
                self.action(self.instance, *a, **kw)
            maybe_call(self.instance, 'after_{}'.format(self.name), *a, **kw)

    def __enter__(self):
        self.set()
        return self

    def __exit__(self, *x):
        self.unset()

    _previous_state = None
    def set(self):
        '''Activate the state, if not already active. Returns True if there was
        a state change.'''
        if self:
            print('.. already set', self)
            return False
        self.instance.state, self._previous_state = self, self.instance.state
        print('!! setting', self)
        return True

    def unset(self):  # XXX: idk may remove this.
        '''Revert to the previous state - (undo set().)'''
        if self and self._previous_state is not None:
            self.instance.state = self._previous_state

    def to(self, *states, **kw):
        '''Connect this state to another state to form a transition.'''
        return Transition(self, *states, **kw)


class Transition(BaseState):
    '''Represents the transition between a sequence of states.'''
    _map_name = '_trans_map'
    def __init__(self, *states, name=None, force=False):
        self.states = states
        self.name = name
        # will force going to first state instead of throwing an error
        self.force = force

    def __str__(self):
        return '({}:{})'.format(self.name, ('->'.join(str(s) for s in self.states)))

    def __bool__(self):
        '''Test that the final state in the transition is active.'''
        return bool(self.states[-1])

    def _with_instance(self, instance):
        '''Add an instance to the transition.'''
        return copymod(
            self, instance=instance,
            states=[s.__get__(instance) for s in self.states])

    def __call__(self, *a, **kw):
        '''Call the transition sequence.'''
        maybe_call(self.instance, 'before_{}'.format(self.name), *a, **kw)
        if self.force:
            self.states[0](*a, **kw)
        elif self.states[-1]:
            print('.. already in end state', self.states[-1], self)
            return
        assert self.states[0]
        maybe_call(self.instance, 'on_{}'.format(self.name), *a, **kw)
        for state in self.states[1:]:
            state(*a, **kw)
        maybe_call(self.instance, 'after_{}'.format(self.name), *a, **kw)

    def to(self, *states, name=None, **kw):
        '''Connect the transition sequence to more states.'''
        return copymod(self, states=self.states + states, name=name, **kw)


class AnyState(State):
    '''(Unfinished) Asserts that the current state is in one of the given states.'''
    def __init__(self, *states):
        self.states = states
        # setting name this way could have a problem when a state infers its name
        # from the class attribute it is assigned to.
        super().__init__(name='any:{}'.format('|'.join(str(s) for s in states)))

    def __bool__(self):
        return any(s for s in self.states)

    def _with_name(self, name):  # XXX: how to handle this ????
        # how do we dynamically pull their names when we may not even have the
        # names yet ???
        return super()._with_name(name)

    def _with_instance(self, instance):
        return copymod(
            self, instance=instance,
            states=[s.__get__(instance) for s in self.states])

    def set(self):
        assert self

# defaults
State.any = AnyState
State.null = NullState = State('null')

# # monkeypatching for now
# reip.state = State


class StateMachineMetaclass(type):
    '''Metaclass to track any state instances added to the class.'''
    __reserved_state_keys = ['state', '_initial_state', '_end_state']
    def __new__(cls, name, bases, attrs):
        # use the attribute name as a state name
        # XXX: caveat - this is run after the class definition body is run
        for k, v in list(attrs.items()):
            if k not in cls.__reserved_state_keys and isinstance(v, (State, Transition)):
                attrs[k] = v._with_name(k)
        return super().__new__(cls, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        cls._states_map = {}
        cls._trans_map = {}
        for base in bases:  # gather states/transitions from base classes
            cls._states_map.update(base._states_map)
            cls._trans_map.update(base._trans_map)
        # gather states/transitions from attributes
        cls._states_map.update({k: v for k, v in attrs.items() if isinstance(v, State)})
        cls._trans_map.update({k: v for k, v in attrs.items() if isinstance(v, Transition)})


class StateModel(metaclass=StateMachineMetaclass):
    _initial_state = _end_state = None
    def __init__(self):
        # copy maps and initialize states with instance
        self._states_map = dict(self.__class__._states_map)
        self._trans_map = dict(self.__class__._trans_map)
        for s in self._states_map.values():
            s.__get__(self)
        for s in self._trans_map.values():
            s.__get__(self)
        # get first, last, current states
        self._initial_state = self._initial_state or next(
            (v for v in self._states_map.values() if v.initial), NullState)
        self._end_state = self._end_state or next(
            (v for v in self._states_map.values() if v.final), NullState)
        self.state = self._initial_state

    def __repr__(self):  # pretty print the state model
        return (
            '<{} initial={} final={} current={} {}{}>'.format(
                self.__class__.__name__,
                self._initial_state, self._end_state, self.state,
                ('\n  states:\n' if self._states_map else '') +
                '\n'.join('    {}: {}'.format(k, state)
                        for k, state in self._states_map.items()),
                ('\n  transitions:\n' if self._states_map else '') +
                '\n'.join('    {}: {}'.format(k, trans)
                        for k, trans in self._trans_map.items()),
            )
        )

    # XXX: not sure if these are necessary

    def __state_idle__(self, delay=1e-4):
        '''Wait until the state changes.'''
        initial_state = self.state
        while self.state == initial_state:
            time.sleep(delay)

    def __idle_lifecycle__(self):
        '''Run until the state reaches the end state.'''
        self.__state_idle__()  # run once in case the initial state is the same as the end one
        while self.state != self._end_state:
            self.__state_idle__()


# Example

class TrafficLight(StateModel):
    green = State()

    @State
    def yellow(self):
        print('slow dowwwwwwn')
        time.sleep(1)
        print('ok too late dont go now')
        time.sleep(0.4)

    red = State('red')
    off = State('off', initial=True, final=True)

    go = red.to(green)
    stop = green.to(yellow).to(red)
    on = off.to(green)

    # __hierarchy__ = {
    #     off: None,
    #     on: [go, yellow, red],
    # }

    # def on_green(self):
    #     print('on_green')
    # def before_green(self):
    #     print('before_green')
    # def after_green(self):
    #     print('after_green')
    # def on_yellow(self):
    #     print('on_yellow')
    # ...
    # def after_stop(self):
    #     print('after_stop')


# create events for all states / transitions for debugging
import functools
for s in (set(TrafficLight._states_map) | set(TrafficLight._trans_map)):
    for e in ['on', 'before', 'after']:
        setattr(TrafficLight, '{}_{}'.format(e, s), functools.partial(
            print, '-- event:', '{}_{}'.format(e, s)))

def test():
    tl = TrafficLight()
    print(tl)
    print()

    print('turning on')
    tl.on()
    print()

    print('gooo')
    tl.go()
    time.sleep(3)
    print()

    print('stoooop')
    tl.stop()
    time.sleep(1)
    print()

    print('goo')
    tl.go()
    time.sleep(1)
    print()

    print('goo')
    tl.go()
    time.sleep(1)
    print()

    print('off. bye!')
    tl.off()
    print()

    print(tl)


if __name__ == '__main__':
    import fire
    fire.Fire(test)
