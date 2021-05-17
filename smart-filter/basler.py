import reip
import time
import numpy as np
from pypylon import pylon
from bundles import BundleCam


class BaslerCam(BundleCam):
    global_time = None  # Global timestamp
    ext_trigger = False  # Use external trigger if True
    pixel_format = "BayerGB8"  # Supported pixel formats: BayerGB8, Mono8
    roi = None  # Full frame if None
    fps = None  # Max fps if None
    exp = None  # Auto if None, 0.99e+6/fps if 0, or us otherwise
    cam = None  # Actual camera handle
    wb = None  # Auto (on start) if None, defaut (5000 K) if "default", or 3-tuple otherwise

    def init(self):
        assert(self.pixel_format in ["BayerGB8", "Mono8"])

        self.cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.cam.Open()

        self.model_name = self.cam.GetDeviceInfo().GetModelName()
        self.cam.UserSetSelector = "Default"
        self.cam.UserSetLoad.Execute()

        self.cam.ReverseX = True
        self.cam.PixelFormat = "BayerGB8"
        self.cam.SensorReadoutMode = 'Fast'
        self.cam.DeviceLinkThroughputLimitMode = "Off"

        self.cam.LineSelector = "Line3"
        self.cam.LineMode = "Input"
        self.cam.LineSelector = "Line4"
        self.cam.LineMode = "Output"
        self.cam.LineSource = "ExposureActive"
        self.cam.TriggerSource = "Line3"
        self.cam.TriggerActivation = "FallingEdge"

        if self.debug:
            print(self.name, "inited (%s)" % self.model_name)
        
        self.start()
    
    def start(self):
        if self.roi is None:
            roi = (0, 0, self.cam.WidthMax.Value, self.cam.HeightMax.Value)
        self.optimal_exp = None
        
        self.cam.OffsetX, self.cam.OffsetY, self.cam.Width, self.cam.Height = roi

        if self.wb is None:
            self.cam.TriggerMode = "Off"
            self.cam.AcquisitionFrameRateEnable = True
            self.cam.AcquisitionFrameRate = 200
            self.cam.ExposureAuto = "Continuous"
            self.cam.BalanceWhiteAuto = "Continuous"

            print("Estimating white balance for %s..." % self.model_name)
            self.cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            time.sleep(1)
            self.cam.StopGrabbing()

            self.cam.BalanceWhiteAuto = "Off"
            self.optimal_exp = self.cam.ExposureTime.Value
            self.wb = [None] * 3

        elif self.wb == "default":
            self.wb = [None] * 3

        elif type(self.wb) in [list, tuple]:
            assert(len(self.wb) == 3)

            self.cam.BalanceWhiteAuto = "Off"

            for i, ch in enumerate(["Red", "Green", "Blue"]):
                self.cam.BalanceRatioSelector = ch
                self.cam.BalanceRatio = self.wb[i]
        else:
            print("Invalid white balance:", self.wb)
            self.wb = [None] * 3

        if self.ext_trigger:
            self.cam.AcquisitionFrameRateEnable = False
            self.cam.TriggerMode = "On"
        else:
            self.cam.TriggerMode = "Off"
            self.cam.AcquisitionFrameRateEnable = True
            self.cam.AcquisitionFrameRate = self.fps or 1.e+6 / self.cam.SensorReadoutTime.Value

        if self.exp is None:
            self.cam.ExposureAuto = "Continuous"
            self.exposure = "Auto"
        else:
            self.cam.ExposureAuto = "Off"
            self.cam.ExposureTime = self.exp or 0.99e+6 / self.cam.AcquisitionFrameRate.Value
            self.exposure = str(self.cam.ExposureTime.Value) + " us"

        for i, ch in enumerate(["Red", "Green", "Blue"]):
            self.cam.BalanceRatioSelector = ch
            self.wb[i] = self.cam.BalanceRatio.Value

        print("\nROI:", roi)
        print("White Balance:", self.wb)
        print("Resulting FPS:", self.cam.ResultingFrameRate.Value)
        print("Exposure:", self.exposure, "\n")

        self.bundle_reset()
        self.cam.OutputQueueSize = 100
        self.cam.StopGrabbing()  # clears the queue
        self.cam.StartGrabbing(pylon.GrabStrategy_OneByOne)
        # self.cam.StartGrabbing(pylon.GrabStrategy_LatestImages)
        # self.cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        if self.debug:
            print(self.name, "started")

    # Implements BundleCam.get_buffer()
    def get_buffer(self):
        buffer, meta = None, {}

        if self.cam.IsGrabbing():
            grabResult = self.cam.RetrieveResult(1000, pylon.TimeoutHandling_Return)
            t = time.time()
            gt = self.global_time.value if self.global_time is not None else None

            if grabResult.IsValid():
                if grabResult.GrabSucceeded():
                    buffer = grabResult.Array
                    meta = { "python_timestamp" : t,
                                "global_timestamp" : gt,
                                "basler_timestamp" : grabResult.TimeStamp / 1.e+9,
                                "skipped_images" : grabResult.NumberOfSkippedImages,
                                "image_number" : grabResult.ImageNumber,
                                "external_trigger" : self.ext_trigger,
                                "pixel_format" : self.pixel_format,
                                "white_balance" : self.wb,
                                "optimal_exposure" : self.optimal_exp,
                                "exposure" : self.exposure,
                                "roi" : self.roi,
                                "resolution" : buffer.shape[:2],
                                "grab_id" : grabResult.ID }

                    if self.debug and self.verbose:
                        print("New buffer:", meta)
                else:
                    if self.debug:
                        print("Grab failed!")
                        
                grabResult.Release()
            else:
                if self.debug:
                    print("Invalid grab result!")
        else:
            raise RuntimeError("Basler camera not grabbing!")

        return buffer, meta

    # Provided by BundleCam
    # def process(self, *xs, meta=None): 
    #     ...

    def stop(self):
        if self.cam:
            self.cam.StopGrabbing()

        self.bundle_reset()

        if self.debug:
            print(self.name, "stopped")

    def finish(self):
        self.stop()

        if self.cam:
            if self.cam.IsOpen():
                self.cam.Close()

        if self.debug:
            print(self.name, "finished")


if __name__ == '__main__':
    from dummies import BlackHole

    with reip.Task("Camera"):
        c = BaslerCam(name="DefaultCam", debug=True, verbose=True, zero_copy=True)

    bh = BlackHole(name="Black_Hole", debug=False)
    bh._delay = 1e-3

    c.to(bh, throughput="large")

    # reip.default_graph().run(duration=5)

    c.name = "ConfiguredCam"
    c.fps = 120
    c.exp = 0
    c.bundle = 12
    c.verbose = False
    c.debug = False
    c.wb = "default"
    c._delay = 1e-3

    frames = np.zeros((8, 1024, 1280), dtype=np.uint8)

    # c.init()
    # for i in range(1000):
    #     with c._sw("process"):
    #         c.process()
    #     # with c._sw("get_buffer"):
    #     #     b = c.get_buffer()
    #     # with c._sw("copy"):
    #     #     # t = time.time()
    #     #     frames[i % 8, ...] = b[0]
    #     #     # print("copy time:", time.time() - t)

    # print(c._sw)

    reip.default_graph().run(duration=10)
