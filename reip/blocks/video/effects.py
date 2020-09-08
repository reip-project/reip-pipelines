import numpy as np
import cv2
import reip



class OpticalFlow(reip.Block):
    '''
    https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_video/py_lucas_kanade/py_lucas_kanade.html#dense-optical-flow-in-opencv
    '''
    hsv = None
    _prev = None

    # pyr_scale=0.5, levels=3, winsize=15, iterations=3,
    # poly_n=5, poly_sigma=1.2, flags=0
    def __init__(self, pyr_scale=0.5, levels=3, winsize=15, iterations=3,
                 poly_n=5, poly_sigma=1.2, flags=0, **kw):
        self.pyr_scale = pyr_scale
        self.levels = levels
        self.winsize = winsize
        self.iterations = iterations
        self.poly_n = poly_n
        self.poly_sigma = poly_sigma
        self.flags = flags
        super().__init__(**kw)

    def process(self, frame, meta):
        current = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.hsv is None:
            self.hsv = np.zeros_like(frame)
            self.hsv[..., 1] = 255
            self._prev = current
            return

        flow = cv2.calcOpticalFlowFarneback(
            self._prev, current, None, self.pyr_scale, self.levels, self.winsize,
            self.iterations, self.poly_n, self.poly_sigma, self.flags)

        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        self.hsv[..., 0] = ang * 180 / np.pi / 2
        self.hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        out = cv2.cvtColor(self.hsv, cv2.COLOR_HSV2BGR)
        return [out], {}
