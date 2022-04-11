import time
import cv2
import reip


class Video(reip.Block):
    cap = None
    def __init__(self, index=None, file=None, fps=30, size=None, **kw):
        self.index = index
        self.size = size
        self.fps = fps
        super().__init__(n_inputs=None, **kw)

    def init(self):
        self.cap = cv2.VideoCapture(self.index)
        msg = ''
        if self.size:
            h, w = self.size
            wset = self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(w))
            hset = self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(h))
            msg = f'  (desired window size: {h}x{w})'
        h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.log.debug(f'window size: {w}x{h}' + msg)

    def process(self, x=None, meta=None):
        if not self.cap.isOpened():
            print('closing', self.cap.isOpened())
            return reip.CLOSE
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError(f'Video frame grab failed for {self}')
        return [frame[:, ::-1]], {
            'time': time.time(),
            'dim': frame.shape,
            'fps': self.fps
        }

    def finish(self):
        self.cap.release()


class _VideoWriter(reip.util.CycledWriter):
    # CODECS: XVID, MJPG, MPEG, MP4V
    def __init__(self, filename, duration=600,
                 codec='X264', **kw):
        self.duration = duration
        self.codec = codec
        super().__init__(filename)

    def _new_writer(self, fname, meta):
        if self.duration:
            self.file_length = int(meta['fps'] * self.duration)
        print(meta['dim'])
        return cv2.VideoWriter(
            fname, cv2.VideoWriter_fourcc(*self.codec),
            meta['fps'], meta['dim'][:2][::-1])

    def _close_writer(self):
        if self._writer is not None:
            self._writer.release()


class VideoWriter(reip.Block):
    def __init__(self, filename, **kw):
        self.filename = filename
        super().__init__(extra_kw=True, **kw)

    def init(self):
        self.writer = _VideoWriter(self.filename, **self.extra_kw)

    def process(self, X, meta):
        writer = self.writer.get(meta)
        writer.write(X)
        self.writer.increment()
        return self.writer.output_closed_file()

    def finish(self):
        self.writer.close()


# class VideoShow(reip.Block):
#     '''XXX: Doesn't work in multithreaded environments. use stream_imshow'''
#     def __init__(self, window_name=None, quit_key='q', **kw):
#         super().__init__(n_outputs=0, **kw)
#         self.window_name = window_name or self.name
#         self.quit_keys = {ord(k) for k in quit_key}
#
#     def process(self, X, meta):
#         cv2.imshow(self.window_name, X)
#         if cv2.waitKey(25) & 0xFF in self.quit_keys:
#             return reip.CLOSE
#         return [], {}
#
#     def finish(self):
#         cv2.destroyWindow(self.window_name)


def stream_imshow(stream, *names):
    try:
        for name in names:
            cv2.namedWindow(name)
        with stream:
            for xs, meta in stream:
                for name, x in zip(names, xs):
                    if x is not None:
                        cv2.imshow(name, x)
                if cv2.waitKey(25) & 0xFF == ord('q'):
                    return
                yield
    finally:
        for name in names:
            cv2.destroyWindow(name)
