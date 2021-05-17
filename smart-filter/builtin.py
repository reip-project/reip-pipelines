import reip
import time
import cv2
import numpy as np
import jetson.utils
from bundles import BundleCam

class BuiltinCamOpenCV(BundleCam):
    global_time = None  # Global timestamp
    pixel_format = "RGB"  # Supported pixel formats: RGB
    res = (1944, 2592)  # Supported resolutions: (1944, 2592), (1458, 2592), (720, 1280)
    fps = 30  # Supported max fps: 30, 30, 120
    cam = None  # Actual camera handle

    gst_str = str("nvarguscamerasrc ! video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, format=(string)NV12, framerate=(fraction)%d/1 ! " +
            "nvvidconv ! video/x-raw, format=(string)BGRx ! " +
			"videoconvert ! video/x-raw, format=(string)BGR ! " +
			"appsink")

    def init(self):
        assert(self.pixel_format in ["RGB"])

        self.gst_str = self.gst_str % (self.res[1], self.res[0], self.fps)

        if self.debug:
            print("\ngst_str:\n", self.gst_str, "\n")

        self.cam = cv2.VideoCapture(self.gst_str, cv2.CAP_GSTREAMER)

        super().init()

    # Implements BundleCam.get_buffer()
    def get_buffer(self):
        ret_val, img = self.cam.read()
        t = time.time()
        img = img[:, :, ::-1]

        if not self.bundle:  # copy required by pyarrow because negative strides are not supported
            img = img.copy() # bundles make a copy by default

        if ret_val:
            return img, {"python_timestamp" : t,
                         "resolution": self.res,
                         "fps": self.fps,
                         "pixel_format" : self.pixel_format}
        else:
            return None, {}

    # Provided by BundleCam
    # def process(self, *xs, meta=None):
    #     ...

    def finish(self):
        if self.cam:
            self.cam.release()

        super().finish()


class BuiltinCamJetson(BundleCam):
    device = 0  # CSI camera device ID
    pixel_format = "NV12"  # Supported pixel formats: NV12, RGB8
    cuda_out = False  # Output cuda image if True (see jetson-utils)
    res = (1944, 2592)  # Supported resolutions: (1944, 2592), (1458, 2592), (720, 1280)
    fps = 30  # Supported max fps: 30, 30, 120
    cam = None  # Actual camera handle

    def init(self):
        assert(self.pixel_format in ["NV12", "RGB8"])
        assert(not (self.cuda_out and self.bundle))  # bundles are CPU-only

        self.cam_args = ["--input-width=%d" % self.res[1],
                         "--input-height=%d" % self.res[0],
                         "--input-rate=%d" % self.fps,
                         "--num-buffers=4",
                         "--flip-method=rotate-180"]

        self.cam = jetson.utils.videoSource("csi://%d" % self.device, argv=self.cam_args)

        super().init()

    # Implements BundleCam.get_buffer()
    def get_buffer(self):
        image = self.cam.Capture(format=self.pixel_format.lower())
        t = time.time()
        gt = self.global_time.value if self.global_time is not None else None

        if self.cuda_out:
            if self.zero_copy:
                img = image
            else:
                cuda_img = jetson.utils.cudaAllocMapped(width=image.width,
                                                        height=image.height,
                                                        format=image.format)
                img = jetson.utils.cudaToNumpy(cuda_img)
        else:
            img = jetson.utils.cudaToNumpy(image)
            if not self.bundle and not self.zero_copy:
                img = img.copy()

        return img, {"python_timestamp" : t,
                     "global_timestamp" : gt,
                     "gstreamer_timestamp" : image.timestamp / 1.e+9,
                     "resolution": self.res,
                     "fps": self.fps,
                     "pixel_format" : self.pixel_format}

    # Provided by BundleCam
    # def process(self, *xs, meta=None): 
    #     ...

    # def finish(self):
    #     super().finish()


if __name__ == '__main__':
    from dummies import BlackHole

    # c = BuiltinCamOpenCV(name="BuiltinCam", bundle=None, zero_copy=True, debug=True, verbose=True)
    # c.to(BlackHole(name="Black_Hole", debug=False))

    # reip.default_graph().run(duration=5)

    c = BuiltinCamJetson(name="BuiltinCam", cuda_out=False, bundle=None, zero_copy=True, debug=True, verbose=False)
    c.to(BlackHole(name="Black_Hole", debug=True))

    reip.default_graph().run(duration=3)
