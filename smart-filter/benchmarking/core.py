# import cv2
import time
import random

class Base:
    def __init__(self, *a, **kw):
        self.a = a
        self.kw = kw

    def init(self):
        pass

    def process(self, *xs):
        pass

    def finish(self):
        pass

class Camera(Base):
    pass
    # def init(self):
    #     pass

    # def process(self):
    #     pass

    # def finish(self):
    #     pass


class Stitch(Base):
    pass

class ML(Base):
    pass


class Motion(Base):
    pass

class Write(Base):
    pass