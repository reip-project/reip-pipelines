import os
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
datafile = lambda *f: os.path.join(DATA_DIR, *f)


def get_blocks(*blocks):
    import reip_app, ray_app, waggle_app
    B_ray = ray_app.wrap_blocks(*blocks)
    B_reip = reip_app.wrap_blocks(*blocks)
    B_waggle = waggle_app.wrap_blocks(*blocks)
    return B_ray, B_reip, B_waggle

B_ray, B_reip, B_waggle = get_blocks(
    BulkUSB, BaslerCam, BuiltinCamJetson, DirectWriter, Bundle, 
    ObjectDetector, NumpyWriter, Follower, ConsoleInput, Controller, BlackHole)

# def define_graph(
#         B, sizeA=(720, 1280), sizeB=(2000, 2500),
#         rate_divider=1, throughput='large', use_tasks=True,
#         gen_debug=None, bundle_debug=None, 
#         io_debug=None, bh_debug=None):

#     Graph = B.Task if use_tasks else B.Graph
#     with Graph("Basler"):
#         basler = (
#             B.Generator(name="Basler_Cam", size=sizeA, dtype=np.uint8, max_rate=120 // rate_divider, debug=gen_debug, queue=120*2)
#                 .to(B.Bundle(name="Basler_Bundle", size=12, queue=10*2, debug=bundle_debug)))

#     with Graph("Builtin"):
#         builtin = (
#             B.Generator(name="Builtin_Cam", size=sizeB, dtype=np.uint8, max_rate=30 // rate_divider, debug=gen_debug, queue=30*2)
#                 .to(B.Bundle(name="Builtin_Bundle", size=3, queue=10*2, debug=bundle_debug)))#, strategy="skip", skip=3)

#     (basler
#         .to(B.Bundle(name="Basler_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
#         .to(B.NumpyWriter(name="Basler_Writer", filename_template=datafile("basler_%d"), debug=io_debug))
#         .to(B.BlackHole(name="Basler_Black_Hole", debug=bh_debug)))

#     (builtin
#         .to(B.Bundle(name="Builtin_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
#         .to(B.NumpyWriter(name="Builtin_Writer", filename_template=datafile("builtin_%d"), debug=io_debug))
#         .to(B.BlackHole(name="Builtin_Black_Hole", debug=bh_debug)))


def define_graph(B):
    with B.Task("USB"):
        bulk_usb = B.BulkUSB(name="Bulk_USB", debug=True, verbose=False)

    with B.Task("Basler_Camera"):
        basler_cam = B.BaslerCam(name="Basler_Camera", fps=120, exp=0, bundle=8, global_time=bulk_usb.timestamp, queue=15)

    with B.Task("Builtin_Camera"):
        builtin_cam = B.BuiltinCamJetson(
            name="Builtin_Camera", fps=15, bundle=None, zero_copy=True, global_time=bulk_usb.timestamp,
            queue=15, debug=False, verbose=False, max_rate=None)

    with B.Task("Basler_Writer"):
        (basler_cam
            .to(B.DirectWriter(name="Basler_Writer", filename_template=DATA_DIR + "basler_%d", bundle=16), throughput='large')
            .to(B.BlackHole(name="Black_Hole_Basler")))

    with B.Task("Builtin_Writer"):
        (builtin_cam
            .to(B.Bundle(name="Builtin_Write_Bundle", size=4, queue=3), throughput='large')
            .to(B.DirectWriter(name="Builtin_Writer", filename_template=DATA_DIR + "builtin_%d", bundle=4))
            .to(B.BlackHole(name="Black_Hole_Builtin")))

    hole = B.BlackHole(name="Black_Hole_Detector")
    det = B.ObjectDetector(name="Object_Detector", max_rate=10, thr=0.8, draw=False, cuda_out=False, zero_copy=True, debug=True, verbose=False)
    det.model = "ssd-mobilenet-v2"
    # det.switch_interval = 10

    basler_cam.to(det, throughput='large', strategy="latest")
    builtin_cam.to(det, throughput='large', strategy="latest")

    # disp = ImageDisplay(name="Image_Display", title="basler", pass_through=True)
    # det.to(disp, strategy="latest").to(hole)
    # det.to(hole)

    (det.to(B.Bundle(name="Detection_Bundle", size=10))
        .to(B.NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "detection_%d"))
        .to(hole))

    fol = B.Follower(name="Automatic_Follower", usb_device=bulk_usb, override=True, detector=det, debug=True, verbose=False)
    fol.zoom_cam, fol.wide_cam = 0, 1
    det.to(fol)

    cin = B.ConsoleInput(name="Console_Input", debug=True)
    ctl = B.Controller(name="Manual_Controller", usb_device=bulk_usb, debug=True)
    ctl.selector = det.target_sel
    cin.to(ctl)

    # reip.default_graph().run(duration=None, stats_interval=10)


def run_graph(B, *a, duration=15, **kw):
    # a) single process
    with B.Graph() as g:
        define_graph(B, *a, **kw)
    g.run(duration=duration)
    return g



def test(*a, duration=15, **kw):
    run_graph(B_reip, *a, duration=15, **kw)
    return g


def compare_1(*a, duration=30, **kw):
    '''1) Concurrency: Comparison  inside  of  REIP  -  prove that sometimes you need threading vs. multiprocessing 

    Comparing performance within  REIP - data rates/throughput for single process, multi process, and multi-process w/ shared memory
        (a) Single process: All blocks running on same process
        (b) MultiProcess: Same block setup, multiprocess
        (c) MultiProcess with shared memory: Same block setupwith Plasmastore

    IDEA: difficult scenarios have different requirements of data streams,  processing  times,  computational  cost, 
    this subsection should show that REIP can scale to multiple of those scenarios efficiently.
    '''

    # a) single process
    run_graph(B_reip, *a, use_tasks=False, duration=duration, **kw)

    # a) multi process - pickle
    run_graph(B_reip, *a, throughput='medium', duration=duration, **kw)

    # a) multi process - plasma
    run_graph(B_reip, *a, throughput='large', duration=duration, **kw)


def compare_2(*a, duration=30, **kw):
    '''2) Overhead: Comparison inside of REIP - prove that we don’t add much overhead over the actual tasks that we want to perform.'''
    run_graph(B_reip, *a, duration=duration, **kw)



def compare_3():
    '''3) Hardware platform: REIP’s software blocks are Linux-platform  agnostic  so  they  can  be  executed  on  a  large  variety of 
    single  board  computers  (SBC)  at  various  price  and  powerpoints.  This  flexibility  allows  the  software  to  be  matched 
    to suitable hardware based on the computational demands of theblocks and the project budget. In this use case, real-time, high-resolution 
    audio  processing  is  part  of  the  requirements  so  a minimum of a multi-core CPU SBC with at least 512 MB of RAM is required.
    '''
    run_graph(B_reip, *a, duration=duration, **kw)


def compare_4():
    '''4) Comparing to other systems:'''

    # REIP
    with B_reip.Graph() as g:
        define_graph(B_reip, *a, **kw)
    g.run(duration=duration)

    # Ray
    with B_ray.Graph() as g:
        define_graph(B_ray, *a, **kw)
    g.run(duration=duration)

    # Waggle
    with B_waggle.Graph() as g:
        define_graph(B_waggle, *a, **kw)
    g.run(duration=duration)

    # Deepstream
    with reip.Graph() as g:
        define_graph(*a, **kw)
    g.run(duration=duration)


if __name__ == '__main__':
    import fire
    fire.Fire()