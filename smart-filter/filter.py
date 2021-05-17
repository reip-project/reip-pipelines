import cv2
import time
import numpy as np
# import matplotlib.pyplot as plt

import reip
import reip.blocks as B
from numpy_io import NumpyWriter
from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from usb_cam import UsbCamGStreamer
from dummies import Generator, BlackHole
from cv_utils import ImageConvert, ImageDisplay
from ai import ObjectDetector
from controls import BulkUSB, Follower, Controller, ConsoleInput

DATA_DIR = './test_data/'

def mono():
    with reip.Task("Cam"):
        cam = UsbCamGStreamer(name="Cam", dev=1, bundle=None, rate=10, debug=True, verbose=False)

    # with reip.Task("Det"):
    det = ObjectDetector(name="Detector", max_rate=None, thr=0.5, draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
    det.model = "ssd-mobilenet-v2"

    bh_det = BlackHole(name="Black_Hole_Detector")
    det_gr = Bundle(name="Detection_Bundle", size=10, meta_only=True)
    det_wr = NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "detection_%d")

    cam.to(det, throughput='large', strategy="latest")
    det.to(det_gr).to(det_wr).to(bh_det)

    # bh_disp = BlackHole(name="Black_Hole_Display")
    # disp = ImageDisplay(name="Display", make_bgr=True)
    # det.to(disp, throughput='large', strategy="latest").to(bh_disp)

    reip.default_graph().run(duration=45, stats_interval=2)


if __name__ == '__main__':
    # If camera got stcuk and does not open, run:
    # sudo service nvargus-daemon restart

    mono()
    # stereo()

