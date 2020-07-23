import time
from collections import OrderedDict
from contextlib import contextmanager
# import wrappingpaper as wp


class _TimerDict(OrderedDict):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.descriptions = {}

# class Timer(wp.propobject):
#     '''
#
#
#     '''
#     __name__ = None
#     __output__ = None
#     _timer_history = ()
#
#     def __init_instance__(self):
#         '''This is run the first time the attribute is referenced on each instance.'''
#         self._timer_history = []
#         self.reset()
#
#     def reset(self):
#         '''Clear the timer set'''
#         if self._times or not self._timer_history: # append only if the last element isn't empty
#             self._timer_history.append(_TimerDict())
#
#     @property
#     def _times(self):
#         return self._timer_history[-1] if self._timer_history else _TimerDict()
#
#     def __str__(self):
#         times = self._times
#         if times:
#             time_items = [(k, v) for k, v in times.items() if k is not None]
#             subtotal = sum(t for k, t in time_items)
#             if None in times: # if we have a total time recorded, calc the service time.
#                 total_time = times[None]
#                 time_items.append(('Service time', total_time - subtotal))
#             else: # otherwise just use the subtotal
#                 total_time = subtotal
#
#             x = 'Total time: {:.3f} secs.{}\n'.format(
#                 total_time, ''.join(
#                     '\n\t{:.3f} - {}'.format(t, times.descriptions.get(k, k))
#                     for k, t in time_items))
#         else:
#             x = 'empty.'
#         return '<Timers: {}>'.format(x)
#
#
#     def __call__(self, name=None, description=None, output=False):
#         '''Assign a name to the '''
#         if description:
#             self._times.descriptions[name] = description
#         return self._new(__name__=name, __desc__=description, __output__=output)
#
#     def __enter__(self):
#         if self.__name__ is None:
#             self.reset()
#         self.t0 = time.time()
#
#     def __exit__(self, *a, **kw):
#         t = time.time() - self.t0
#         if self.__output__:
#             print("{} {} {} in {:.3f} sec".format(
#                 self.__target__.__type_name__,
#                 getattr(self.__target__, 'name', ''),
#                 self.__desc__ or self.__name__,
#                 t))
#
#         ts = self._times
#         ts[self.__name__] = ts.get(self.__name__, 0) + t
#
#     def __getattr__(self, name):
#         '''Get timer value by name.'''
#         times = self._times
#         return times[name] if name in times else super().__getattr__(name)
#
#     def summary(self):
#         print(str(self))



class Timer:
    _times = None
    def __init__(self, name=''):
        self._timer_history = []
        self.reset()
        self.name = name

    def reset(self):
        '''Clear the timer set'''
        if self._times:
            self._timer_history.append(self._times)
        self._times = _TimerDict()

    def __call__(self, name=None, description=None, output=False):
        '''Assign a name to the '''
        return self._context(name, description, output)

    @contextmanager
    def _context(self, name=None, description=None, output=False):
        if name is None:
            self.reset()
        t0 = time.time()
        yield
        self.lap(t0, name, description, output)


    def lap(self, t0, name, description=None, output=False):
        t = time.time() - t0
        self._times.descriptions[name] = description
        self._times[name] = self._times.get(name, 0) + t

        if output:
            print("{} {} in {:.3f} sec".format(
                self.name, description or name or 'ran', t))

    def __getitem__(self, key):
        return self._times[key]

    def __setitem__(self, key, value):
        self._times[key] = value


    ##################
    # Value Access
    ##################

    def __getattr__(self, name):
        '''Get timer value by name.'''
        try:
            return self._times[name]
        except KeyError:
            raise AttributeError(name)

    def get(self, *include, exclude=()):
        '''Get multiple timer values.'''
        return {
            k: t for k, t in self._times.items()
            if (not include or k in include) and (not exclude or k not in exclude)
        }


    ##################
    # Display
    ##################

    def __str__(self):
        times = self._times
        if times:
            time_items = [(k, v) for k, v in times.items() if k is not None]
            subtotal = sum(t for k, t in time_items)
            if None in times: # if we have a total time recorded, calc the service time.
                total_time = times[None]
                time_items.append(('Service time', total_time - subtotal))
            else: # otherwise just use the subtotal
                total_time = subtotal

            x = 'Total time: {:.3f} secs.{}\n'.format(
                total_time, ''.join(
                    '\n\t{:.3f} - {}'.format(t, times.descriptions.get(k, k))
                    for k, t in time_items))
        else:
            x = 'empty.'
        return '<Timers: {}>'.format(x)


# class patchprop:
#     '''
#     class A:
#         sources = patchprop()
#
#
#     '''
#     def __init__(self):
#         self.__key__ = '_prop{}'.format(id(self))
#
#     def __get__(self, instance, owner=None):
#         return getattr(instance, self.__key__)
#
#     def __set__(self, instance, value):
#         c = value.__class__
#         newc = type(c.__name__, (c,), dict(self.__class__.__dict__))
#         new = newc.__new__(newc)
#         try:
#             new.__dict__.update(value.__dict__)
#         except AttributeError:
#             pass
#         new.__dict__.update(self.__dict__)
#         setattr(instance, self.__key__, value)


if __name__ == '__main__':
    class A:
        timer = Timer()
        def task(self):
            with self.timer:
                with self.timer('first', 'First'):
                    time.sleep(0.5)

                with self.timer('second', 'Second'):
                    time.sleep(0.5)
                self.timer.summary()
            return self


    print(A().task().timer)
    print(A().timer)
