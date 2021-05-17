import cv2
import time
import numpy as np
import matplotlib.pyplot as plt

import reip
import reip.blocks as B
from numpy_io import NumpyWriter
from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from basler import BaslerCam
from builtin import BuiltinCamOpenCV, BuiltinCamJetson
from dummies import Generator, BlackHole
from cv_utils import ImageConvert, ImageDisplay
from ai import ObjectDetector, PoseDetector
from controls import BulkUSB, Follower, Controller, ConsoleInput

DATA_DIR = '/mnt/ssd/test_data/'


def lego():
    gen_debug, bundle_debug, io_debug, bh_debug = False, False, False, False
    rate_divider, throughput = 1, 'large'
    Generator.debug = gen_debug

    with reip.Task("Basler"):
        basler = Generator(name="Basler_Cam", size=(720, 1280), dtype=np.uint8, max_rate=120 // rate_divider, queue=120*2)
        basler_bundle = Bundle(name="Basler_Bundle", size=12, queue=10*2, debug=bundle_debug)
        basler.to(basler_bundle)

    with reip.Task("Builtin"):
        builtin = Generator(name="Builtin_Cam", size=(2000, 2500), dtype=np.uint8, max_rate=30 // rate_divider, queue=30*2)
        builtin_bundle = Bundle(name="Builtin_Bundle", size=3, queue=10*2, debug=bundle_debug)
        builtin.to(builtin_bundle)#, strategy="skip", skip=3)

    basler_writer = NumpyWriter(name="Basler_Writer", filename_template=DATA_DIR + "basler_%d", debug=io_debug)
    builtin_writer = NumpyWriter(name="Builtin_Writer", filename_template=DATA_DIR + "builtin_%d", debug=io_debug)

    basler_bundle.to(Bundle(name="Basler_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput) \
                .to(basler_writer).to(BlackHole(name="Basler_Black_Hole", debug=bh_debug))

    builtin_bundle.to(Bundle(name="Builtin_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput) \
                 .to(builtin_writer).to(BlackHole(name="Builtin_Black_Hole", debug=bh_debug))

    reip.default_graph().run(duration=5)


def test():
    rate = 240
    gen = Generator(name="Generator", size=(720, 1280), dtype=np.uint8, max_rate=rate, queue=rate*2, debug=False)
    bundle = Bundle(name="Bundle", size=rate//5, debug=False, queue=200)
    gen.to(bundle).to(BlackHole(name="Black_Hole", debug=False))
    # gen.to(BlackHole(name="Black_Hole", debug=False))

    reip.default_graph().run(duration=5)


def basler_test_0():
    with reip.Task("Basler"):
        cam = BaslerCam(name="Camera", fps=200, exp=0, bundle=8)

    bh = BlackHole(name="Black_Hole")
    cam.to(bh, throughput='large')

    reip.default_graph().run(duration=6)


def basler_test_1():
    with reip.Task("Basler"):
        cam = BaslerCam(name="Camera", fps=200, exp=0, bundle=8)

    writer = NumpyWriter(name="Writer", filename_template=DATA_DIR + "basler_%d")
    bh = BlackHole(name="Black_Hole")

    cam.to(Bundle(name="Write_Bundle", size=25, queue=3), throughput='large').to(writer).to(bh)

    reip.default_graph().run(duration=6)

    img = np.load(open(DATA_DIR + "basler_0.npy", "rb"))

    img = img[-1, -1, ...]
    img = cv2.cvtColor(img, cv2.COLOR_BayerGB2BGR)

    plt.imshow(2 * img / np.max(img))
    plt.colorbar()
    plt.show()


def basler_test_2():
    with reip.Task("Basler"):
        cam = BaslerCam(name="Camera", fps=200, exp=0, bundle=8)

    writer = DirectWriter(name="Writer", filename_template=DATA_DIR + "basler_%d", bundle=25)
    bh = BlackHole(name="Black_Hole")

    cam.to(writer, throughput='large').to(bh)

    reip.default_graph().run(duration=6)

    r = DirectReader(name="reader", debug=True, verbose=True)
    b = r.process(DATA_DIR + "basler_0")[0][0]

    img = b[0][-1, ...]
    img = cv2.cvtColor(img, cv2.COLOR_BayerGB2BGR)

    plt.imshow(2 * img / np.max(img))
    plt.colorbar()
    plt.show()

##########################################################################

def builtin_test_0():
    with reip.Task("Builtin"):
        cam = BuiltinCamOpenCV(name="Camera", bundle=2, debug=True, verbose=True)

    bh = BlackHole(name="Black_Hole")
    cam.to(bh, throughput='large')

    reip.default_graph().run(duration=6)


def builtin_test_1():
    with reip.Task("Builtin"):
        cam = BuiltinCamOpenCV(name="Camera", bundle=None, debug=True, verbose=True)

    cvt = ImageConvert(name="Image_Convert")
    disp = ImageDisplay(name="Image_Display", title="builtin", pass_through=True)
    bh = BlackHole(name="Black_Hole")

    cam.to(cvt, throughput='large', strategy="latest").to(disp, strategy="latest").to(bh)

    reip.default_graph().run(duration=10)


def builtin_test_2():
    with reip.Task("Builtin"):
        cam = BuiltinCamOpenCV(name="Camera", bundle=None, debug=True, verbose=True)

    writer = DirectWriter(name="Writer", filename_template=DATA_DIR + "builtin_%d", bundle=10)
    bh = BlackHole(name="Black_Hole")

    cam.to(writer, throughput='large').to(bh)

    reip.default_graph().run(duration=10)

    r = DirectReader(name="reader", debug=True, verbose=True)
    b = r.process(DATA_DIR + "builtin_0")[0][0]

    img = b[0][-1, ...]

    plt.imshow(img / np.max(img))
    plt.colorbar()
    plt.show()


def builtin_test_3():
    with reip.Task("Builtin"):
        cam = BuiltinCamOpenCV(name="Camera", bundle=None, debug=False, verbose=False, max_rate=None)

    # with reip.Task("Detector"):
    det = ObjectDetector(name="Object_Detector", draw=False, debug=True, verbose=True)

    # cvt = ImageConvert(name="Image_Convert")
    # disp = ImageDisplay(name="Image_Display", title="builtin", pass_through=True)
    # gr = Bundle(name="Write_Bundle", size=2, queue=3)
    # writer = DirectWriter(name="Writer", filename_template=DATA_DIR + "builtin_%d", bundle=2)
    # bh = BlackHole(name="Black_Hole")

    cam.to(det, throughput='large', strategy="latest") \
        # .to(cvt, throughput='large').to(disp, strategy="latest").to(gr).to(writer).to(bh)

    reip.default_graph().run(duration=30)

    # r = DirectReader(name="reader", debug=True, verbose=True)
    # b = r.process(DATA_DIR + "builtin_0")[0][0]

    # img = b[1][-1, ...]

    # plt.imshow(img[:, :, ::-1] / np.max(img))
    # plt.colorbar()
    # plt.show()


def ai_test_1():
    with reip.Task("Builtin"):
        cam = BuiltinCamJetson(name="Camera", bundle=None, zero_copy=True, debug=False, verbose=False, max_rate=None)

    bh = BlackHole(name="Black_Hole")
    det = ObjectDetector(name="Object_Detector", draw=False, cuda_out=False, zero_copy=True, debug=False, verbose=False)
    det.model = "ssd-mobilenet-v2"

    cam.to(det, throughput='large', strategy="latest").to(bh)

    reip.default_graph().run(duration=30)


def ai_test_2():
    with reip.Task("Builtin"):
        cam = BuiltinCamJetson(name="Camera", bundle=None, zero_copy=True, debug=False, verbose=False, max_rate=None)

    with reip.Task("Writer"):
        bh_w = BlackHole(name="Black_Hole_W")
        gr = Bundle(name="Write_Bundle", size=4, queue=3)
        wr = DirectWriter(name="Writer", filename_template=DATA_DIR + "builtin_%d", bundle=8)

        cam.to(gr, throughput='large').to(wr).to(bh_w)

    bh_d = BlackHole(name="Black_Hole_D")
    det = ObjectDetector(name="Object_Detector", draw=True, cuda_out=False, zero_copy=False, debug=False, verbose=False)
    det.model = "ssd-mobilenet-v2"

    disp = ImageDisplay(name="Image_Display", title="basler", pass_through=True)

    cam.to(det, throughput='large', strategy="latest").to(disp, strategy="latest").to(bh_d)
    # cam.to(det, throughput='large', strategy="latest").to(bh_d)

    reip.default_graph().run(duration=None)


def ai_test_3():
    with reip.Task("Basler"):
        cam = BaslerCam(name="Basler", fps=4, exp=0, bundle=2)

    with reip.Task("Writer"):
        bh_w = BlackHole(name="Black_Hole_W")
        wr = DirectWriter(name="Writer", filename_template=DATA_DIR + "basler_%d", bundle=25)

        cam.to(wr, throughput='large').to(bh_w)

    bh_d = BlackHole(name="Black_Hole_D")
    det = ObjectDetector(name="Object_Detector", draw=True, cuda_out=False, zero_copy=False, debug=False, verbose=False)
    det.model = "ssd-mobilenet-v2"

    disp = ImageDisplay(name="Image_Display", title="basler", pass_through=True)

    cam.to(det, throughput='large', strategy="latest").to(disp, strategy="latest").to(bh_d)

    reip.default_graph().run(duration=None)


def test_both_1():
    with reip.Task("USB"):
        bulk_usb = BulkUSB(name="Bulk_USB", debug=True, verbose=False)

    with reip.Task("Basler_Camera"):
        basler_cam = BaslerCam(name="Basler_Camera", fps=120, exp=0, bundle=8, global_time=bulk_usb.timestamp, queue=15)

    with reip.Task("Builtin_Camera"):
        builtin_cam = BuiltinCamJetson(name="Builtin_Camera", fps=15, bundle=None, zero_copy=True, global_time=bulk_usb.timestamp,
                                                            queue=15, debug=False, verbose=False, max_rate=None)

    with reip.Task("Basler_Writer"):
        basler_bh_w = BlackHole(name="Black_Hole_Basler")
        basler_wr = DirectWriter(name="Basler_Writer", filename_template=DATA_DIR + "basler_%d", bundle=16)

        basler_cam.to(basler_wr, throughput='large').to(basler_bh_w)

    with reip.Task("Builtin_Writer"):
        builtin_bh_w = BlackHole(name="Black_Hole_Builtin")
        builtin_gr = Bundle(name="Builtin_Write_Bundle", size=4, queue=3)
        builtin_wr = DirectWriter(name="Builtin_Writer", filename_template=DATA_DIR + "builtin_%d", bundle=4)

        builtin_cam.to(builtin_gr, throughput='large').to(builtin_wr).to(builtin_bh_w)

    bh_d = BlackHole(name="Black_Hole_Detector")
    det = ObjectDetector(name="Object_Detector", max_rate=10, thr=0.8, draw=False, cuda_out=False, zero_copy=True, debug=True, verbose=False)
    det.model = "ssd-mobilenet-v2"
    # det.switch_interval = 10

    basler_cam.to(det, throughput='large', strategy="latest")
    builtin_cam.to(det, throughput='large', strategy="latest")

    # disp = ImageDisplay(name="Image_Display", title="basler", pass_through=True)
    # det.to(disp, strategy="latest").to(bh_d)
    # det.to(bh_d)

    det_gr = Bundle(name="Detection_Bundle", size=10)
    det_wr = NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "detection_%d")
    det.to(det_gr).to(det_wr).to(bh_d)

    fol = Follower(name="Automatic_Follower", usb_device=bulk_usb, override=True, detector=det, debug=True, verbose=False)
    fol.zoom_cam, fol.wide_cam = 0, 1
    det.to(fol)

    cin = ConsoleInput(name="Console_Input", debug=True)
    ctl = Controller(name="Manual_Controller", usb_device=bulk_usb, debug=True)
    ctl.selector = det.target_sel
    cin.to(ctl)

    reip.default_graph().run(duration=None, stats_interval=10)


if __name__ == '__main__':
    # If camera got stcuk and does not open, run:
    # sudo service nvargus-daemon restart

    # lego()
    # test()

    # basler_test_2()
    # builtin_test_3()
    # ai_test_2()

    test_both_1()

