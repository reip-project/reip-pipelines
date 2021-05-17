import cv2
import time
import reip
import numpy as np
print(cv2.__version__)


class ImageConvert(reip.Block):
    fmt = cv2.COLOR_BGR2RGB

    def process(self, img, meta=None):
        assert(type(img) == np.ndarray)
        
        return [cv2.cvtColor(img, self.fmt)], meta


class ImageDisplay(reip.Block):
    title = "Image"  # Window title
    gui_delay = 100  # Process gui event for gui_delay ms before next frame
    make_bgr = True  # Converts rgb to bgr automatically if True
    pass_through = False  # Passes the image through to the next block if True

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
