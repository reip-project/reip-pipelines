import cv2
import time
import reip
import numpy as np
print("cv2.version =", cv2.__version__)

from numpy_io import *


class ImageSource(reip.Block):
    dev = 0  # Device ID
    make_rgb = True  # Convert BGR to RGB if True
    res = (720, 1280)  # Resolution

    def __init__(self, **kw):
        super().__init__(n_inputs=None, **kw)

    def init(self):
        self.cap = cv2.VideoCapture(self.dev)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.res[1])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.res[0])

    def process(self, meta=None):
        ret, frame = self.cap.read()

        if ret:
            return [frame[:, :, ::-1] if self.make_rgb else frame], {'time': time.time(), 'dim': frame.shape, 'res': self.res}
        else:
            raise RuntimeError("Capture Failed")

    def finish(self):
        self.cap.release()


class ImageConvert(reip.Block):
    fmt = cv2.COLOR_BGR2RGB

    def process(self, img, meta=None):
        assert(type(img) == np.ndarray)
        
        return [cv2.cvtColor(img, self.fmt)], meta


class ImageDisplay(reip.Block):
    title = None  # Window title (block name by default)
    gui_delay = 100  # Process gui event for gui_delay ms before next frame
    make_bgr = True  # Converts rgb to bgr automatically if True
    pass_through = False  # Passes the image through to the next block if True

    def init(self):
        self.title = self.title or self.name

    def process(self, img, meta=None):
        assert(type(img) == np.ndarray)

        cv2.imshow(self.title, img[:, :, ::-1] if self.make_bgr else img)

        for i in range(self.gui_delay // 2):
            cv2.waitKey(1)
            time.sleep(0.001)

        if self.pass_through:
            return [img], dict(meta)
        else:
            return None

    def finish(self):
        cv2.destroyWindow(self.title)


class ImageWriter(reip.Block):
    path = "/mnt/ssd/"  # Data output path
    template = "image_%d"  # Filename template
    file_id = 0  # Initial file_id
    ext = ".bmp"  # Extention
    make_bgr = True  # Converts rgb to bgr automatically if True
    save_meta = True  # Save meta in additional json file if True
    meta_only = False  # Only save meta
    save_raw = False  # Save raw numpy array instead of bmp image
    return_filename = False  # Return written filename if True

    def init(self):
        reip.util.ensure_dir(self.path)

    def process(self, img, meta=None):
        assert(type(img) == np.ndarray)

        filename = self.path + (self.template % self.file_id)

        if meta is not None:
            meta["file_template"] = self.template
            meta["file_id"] = self.file_id
            meta["file_ext"] = self.ext
            meta["filename"] = filename + self.ext

            if self.save_meta:
                with open(filename + ".json", "w") as f:
                    json.dump(dict(meta), f, indent=4, cls=NumpyEncoder)

        if not self.meta_only:
            if self.save_raw:
                np.save(filename + self.ext, img[:, :, ::-1] if self.make_bgr else img)
            else:
                cv2.imwrite(filename + self.ext, img[:, :, ::-1] if self.make_bgr else img)

        self.file_id += 1

        if self.return_filename:
            return [filename], dict(meta)
        else:
            return None


if __name__ == '__main__':
    from dummies import BlackHole

    cam = ImageSource(name="Camera", res=(1944, 2592), dev=0, make_rgb=False)
    bh = BlackHole(name="Black_Hole", debug=False)

    # cam.to(bh)
    # cam.to(ImageDisplay(name="Display", make_bgr=False)).to(bh)
    cam.to(ImageWriter(name="Writer", make_bgr=False)).to(bh)

    reip.default_graph().run(duration=15)
