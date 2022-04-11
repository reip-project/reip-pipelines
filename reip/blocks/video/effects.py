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
                 poly_n=5, poly_sigma=1.2, flags=0, resize=(256, 256), draw_mag_scale=10, draw=None, **kw):
        self.pyr_scale = pyr_scale
        self.levels = levels
        self.winsize = winsize
        self.iterations = iterations
        self.poly_n = poly_n
        self.poly_sigma = poly_sigma
        self.flags = flags
        self.resize = resize
        self._should_draw = draw
        self.draw_mag_scale = draw_mag_scale
        super().__init__(n_outputs=2, **kw)

    def init(self):
        self.should_draw = bool(self.sinks[1].readers) if self._should_draw is None else self._should_draw
        self.log.debug(f'will draw: {self.should_draw}')

    def process(self, frame, meta):
        original = frame
        if self.resize:
            frame = cv2.resize(frame, self.resize)
        current = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype('uint8')
        if self.hsv is None:
            self.hsv = np.zeros_like(frame)
            self.hsv[..., 1] = 255
            self._prev = current
            return

        flow = cv2.calcOpticalFlowFarneback(
            self._prev, current, None, self.pyr_scale, self.levels, self.winsize,
            self.iterations, self.poly_n, self.poly_sigma, self.flags)
        self._prev = current

        flow = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return [flow, self.draw(original, flow) if self.should_draw else None], {}

    def draw(self, im, flow, mix=0.5):
        mag, ang = flow
        self.hsv[..., 0] = ang * 180 / np.pi / 2
        # self.hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        self.hsv[..., 2] = np.clip(mag*self.draw_mag_scale, 0, 255)
        flow = cv2.cvtColor(self.hsv, cv2.COLOR_HSV2BGR)

        if im.shape != flow.shape:
            flow = cv2.resize(flow, im.shape[:2][::-1])
        im = im * (1-mix) + flow * mix
        return (im/255).astype('float32')