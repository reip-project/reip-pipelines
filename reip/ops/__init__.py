import functools
import wrappingpaper as wp
from contextlib import contextmanager
from .ops import Ops




def applyops(op, value):
    with op.scope(value):
        for o in op._ops:
            value = o.apply(value)
    return value


# class testobj:
#     def hi(self, a, b):
#         return [a, b]
#
#
# def test(op, x=None):
#     print(op)
#     print(applyops(op, testobj() if x is None else x))
#     return op
#
#
# X = Ops()
# a = test(-X.hi(a=5, b=10)[-1] < 0)
# test(a.ops[:-1])
#
# test(X.hi(a=5, b=10)[0] == 10)
#
# test(X.hi(a=5, b=10)[:1] == [5])
#
# test(X.hi(a=5, b=10)[::-1] == [10, 5])
#
# # test(X.hi(a=5, b=10)[::-1] == [10, 5])
#
#
# # %%
# import numpy as np
#
# test(X[X > 6], np.arange(10))
