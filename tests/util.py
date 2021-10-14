import copy
import functools


def method_count(func):
    def inner(self, *a, **kw):
        try:
            count = self.method_counts
        except AttributeError:
            self.method_counts = count = {}
        count[name] = count.get(name, 0) + 1
        if isfunc:
            return func(self, *a, **kw)
    isfunc = callable(func)
    inner.__name__ = name = func.__name__ if isfunc else func
    return inner


# def count_calls(obj=None):
#     cls = obj.__class__
#     obj.method_call_counts = {}
#     obj.__class__ = type(cls.__name__, (_CallCount, cls,), {'__oldcls': cls})
#     return obj
#
# class _CallCount:
#     def revert(self):
#         self.__class__ = self.__oldcls
#
#     def __getattribute__(self, name):
#         if name != 'method_call_counts':
#             self.method_call_counts[name] = self.method_call_counts.get(name, 0) + 1
#         return super().__getattribute__(name)
#
#
# if __name__ == '__main__':
#     class A:
#         def a(self):
#             pass
#
#         def b(self):
#             pass
#
#         def __call__(self):
#             pass
#
#     a = count_calls(A())
#     a.a()
#     a.a()
#     a.b()
#     a()  # call doesn't work because access happens on the class
#
#
#     print(a.method_call_counts)
