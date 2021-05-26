import time
import random
import numpy as np


class Base:  # test class
    init_time, init_std = 0.1, 0.05
    process_time, process_std = 0.2, 0.1
    finish_time, finish_std = 0.1, 0.05
    output_shape = None
    verbose = False

    def pretend(self, name, amt_time, time_std, *extra):
        # print(self.__class__.__name__, ':', name, *extra)
        dt = max(0, random.gauss(amt_time, time_std))
        time.sleep(dt)
        if self.verbose:
            print(self.__class__.__name__, ':', name, '(took {:.3f}s)'.format(dt), extra)

    def init(self):
        self.pretend('init', self.init_time, self.init_std)

    def process(self, *xs):
        self.pretend('process', self.process_time, self.process_std, *(getattr(x, 'shape', x) for x in xs))
        if self.output_shape is not None:
            return np.ones(self.output_shape)
        return '{}({})'.format(self.__class__.__name__, ', '.join(map(str, xs)))

    def finish(self):
        self.pretend('finish', self.finish_time, self.finish_std)


class Camera(Base):
    output_shape = (1000, 1000)

class Stitch(Base):
    output_shape = (1000, 1800)

class ML(Base):
    output_shape = (10,)

class MotionFilter(Base):
    output_shape = (1,)

class Write(Base):
    output_shape = ()