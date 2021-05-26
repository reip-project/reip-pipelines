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


B_ray, B_reip, B_waggle = get_blocks(Generator, Bundle, NumpyWriter, BlackHole)


def define_graph(
        B, sizeA=(720, 1280), sizeB=(2000, 2500),
        rate_divider=1, throughput='large', use_tasks=True,
        gen_debug=None, bundle_debug=None, 
        io_debug=None, bh_debug=None):

    Graph = B.Task if use_tasks else B.Graph
    with Graph("Basler"):
        basler = (
            B.Generator(name="Basler_Cam", size=sizeA, dtype=np.uint8, max_rate=120 // rate_divider, debug=gen_debug, queue=120*2)
                .to(B.Bundle(name="Basler_Bundle", size=12, queue=10*2, debug=bundle_debug)))

    with Graph("Builtin"):
        builtin = (
            B.Generator(name="Builtin_Cam", size=sizeB, dtype=np.uint8, max_rate=30 // rate_divider, debug=gen_debug, queue=30*2)
                .to(B.Bundle(name="Builtin_Bundle", size=3, queue=10*2, debug=bundle_debug)))#, strategy="skip", skip=3)

    (basler
        .to(B.Bundle(name="Basler_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
        .to(B.NumpyWriter(name="Basler_Writer", filename_template=datafile("basler_%d"), debug=io_debug))
        .to(B.BlackHole(name="Basler_Black_Hole", debug=bh_debug)))

    (builtin
        .to(B.Bundle(name="Builtin_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
        .to(B.NumpyWriter(name="Builtin_Writer", filename_template=datafile("builtin_%d"), debug=io_debug))
        .to(B.BlackHole(name="Builtin_Black_Hole", debug=bh_debug)))


def adapted_graph(Graph, Block):
    B=Block
    with Graph("Basler"):
        basler = (
            Generator(name="Basler_Cam", size=sizeA, dtype=np.uint8, max_rate=120 // rate_divider, debug=gen_debug, queue=120*2)
                .to(Bundle(name="Basler_Bundle", size=12, queue=10*2, debug=bundle_debug)))

    with Graph("Builtin"):
        builtin = (
            Generator(name="Builtin_Cam", size=sizeB, dtype=np.uint8, max_rate=30 // rate_divider, debug=gen_debug, queue=30*2)
                .to(Bundle(name="Builtin_Bundle", size=3, queue=10*2, debug=bundle_debug)))#, strategy="skip", skip=3)

    (basler
        .to(Bundle(name="Basler_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
        .to(NumpyWriter(name="Basler_Writer", filename_template=datafile("basler_%d"), debug=io_debug))
        .to(BlackHole(name="Basler_Black_Hole", debug=bh_debug)))

    (builtin
        .to(Bundle(name="Builtin_Write_Bundle", size=5, queue=5, debug=bundle_debug), throughput=throughput)
        .to(NumpyWriter(name="Builtin_Writer", filename_template=datafile("builtin_%d"), debug=io_debug))
        .to(BlackHole(name="Builtin_Black_Hole", debug=bh_debug)))




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
    with reip.Graph() as g:
        define_graph(*a, use_tasks=False, **kw)
    g.run(duration=duration)

    # a) multi process - pickle
    with reip.Graph() as g:
        define_graph(*a, throughput='medium', **kw)
    g.run(duration=duration)

    # a) multi process - plasma
    with reip.Graph() as g:
        define_graph(*a, throughput='large', **kw)
    g.run(duration=duration)


def compare_2(*a, duration=30, **kw):
    '''2) Overhead: Comparison inside of REIP - prove that we don’t add much overhead over the actual tasks that we want to perform.'''
    with reip.Graph() as g:
        define_graph(*a, **kw)
    g.run(duration=duration)




def compare_3():
    '''3) Hardware platform: REIP’s software blocks are Linux-platform  agnostic  so  they  can  be  executed  on  a  large  variety of 
    single  board  computers  (SBC)  at  various  price  and  powerpoints.  This  flexibility  allows  the  software  to  be  matched 
    to suitable hardware based on the computational demands of theblocks and the project budget. In this use case, real-time, high-resolution 
    audio  processing  is  part  of  the  requirements  so  a minimum of a multi-core CPU SBC with at least 512 MB of RAM is required.
    '''
    with reip.Graph() as g:
        define_graph(*a, **kw)
    g.run(duration=duration)


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