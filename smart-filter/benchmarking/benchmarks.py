import os
import time
import numpy as np
import matplotlib.pyplot as plt

import reip
import reip.blocks as B
import reip.blocks.audio
import traceback
import sys
sys.path.append('..')
from numpy_io import NumpyWriter
# from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from dummies import Generator, BlackHole
# from cv_utils import ImageConvert, ImageDisplay
# from controls import BulkUSB, Follower, Controller, ConsoleInput

import base_app

DATA_DIR = '/mnt/ssd/test_data/'
datafile = lambda *f: os.path.join(DATA_DIR, *f)


reip.Graph._delay = 1e-1
reip.Task._delay = 2e-1
#reip.Block._delay = 1e-1
reip.Block.USE_META_CLASS = True
reip.Block.KW_TO_ATTRS = True
reip.Block.run_profiler = True
reip.Task.run_profiler = True


def get_blocks(*blocks):
    try:
        import ray_app
        print(ray_app.Block)
        B_ray = ray_app.Block.wrap_blocks(*blocks)
    except ImportError:
        traceback.print_exc()
        B_ray = None
    try:
        import reip_app
        print(reip_app.Block)
        B_reip = reip_app.Block.wrap_blocks(*blocks)
        print(B_reip)
        print(B_reip.Generator.__mro__)
    except ImportError:
        traceback.print_exc()
        B_reip = None
    try:
        import waggle_app
        print(waggle_app.Block)
        B_waggle = waggle_app.Block.wrap_blocks(*blocks)
        print(B_waggle)
    except ImportError:
        traceback.print_exc()
        B_waggle = None
    try:
        import base_app
        B_base = base_app.Block.wrap_blocks(*blocks)
        print('basic:', B_base)
    except ImportError:
        traceback.print_exc()
        B_base = None
    return B_ray, B_reip, B_waggle, B_base



def define_graph_alt(
        B, sizeA=(720, 1280), sizeB=(2000, 2500),
        rate_divider=1, throughput='large', use_tasks=True,
        gen_debug=None, bundle_debug=False, bundle_log=True,
        io_debug=None, bh_debug=None, include_audio=True):

    Graph = B.Task if use_tasks else B.Graph
    with Graph("Basler"):
        basler = (
            B.Generator(name="Basler_Cam", size=sizeA, dtype=np.uint8, max_rate=120 // rate_divider, debug=gen_debug, queue=120*2)
                .to(B.Bundle(name="Basler_Bundle", size=12, queue=10*2, debug=bundle_debug)))#, log_level=bundle_log

    with Graph("Builtin"):
        builtin = (
            B.Generator(name="Builtin_Cam", size=sizeB, dtype=np.uint8, max_rate=30 // rate_divider, debug=gen_debug, queue=30*2)
                .to(B.Bundle(name="Builtin_Bundle", size=3, queue=10*2, debug=bundle_debug)))#, strategy="skip", skip=3)#, log_level=bundle_log

    (basler
        .to(B.Bundle(name="Basler_Write_Bundle", size=5, queue=5, debug=bundle_debug, log_level=bundle_log), throughput=throughput)
        .to(B.NumpyWriter(name="Basler_Writer", filename_template=datafile("basler_%d"), debug=io_debug))
        .to(B.BlackHole(name="Basler_Black_Hole", debug=bh_debug)))

    (builtin
        .to(B.Bundle(name="Builtin_Write_Bundle", size=5, queue=5, debug=bundle_debug, log_level=bundle_log), throughput=throughput)
        .to(B.NumpyWriter(name="Builtin_Writer", filename_template=datafile("builtin_%d"), debug=io_debug))
        .to(B.BlackHole(name="Builtin_Black_Hole", debug=bh_debug)))

    if include_audio:
        define_graph_alt2(B, throughput=throughput)


def define_graph_alt2(B, audio_length=10, rate=4, data_dir='./data', cam_2nd=True, throughput='large'):
    timestamp = time.time()

    os.makedirs(data_dir, exist_ok=True)
    cam_fname = os.path.join(data_dir, "video/%d_{}.avi".format(timestamp))
    det_fname = os.path.join(data_dir, "det/{}_%d".format(timestamp))
    spl_fname = os.path.join(data_dir, 'spl/{time}.csv')
    aud_fname = os.path.join(data_dir, 'audio/{time}.wav')

    _kw = dict(log_level='debug')
    with B.Task('mic-task'):
        audio1s = B.Mic(
            name="mic", block_duration=1, channels=16,
            device="hw:2,0", dtype=np.int32)#.to(B.Debug('1s', _kw=_kw))
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length))

    with B.Task("audio-write-task"):
        (audio_ns
            .to(B.AudioFile(aud_fname), throughput=throughput)#.to(B.Debug('audfile', _kw=_kw))
            .to(B.BlackHole(name="audio-bh")))

    with B.Task("spl-task"):
        weights = 'ZAC'
        spl = audio1s.to(B.SPL(name="spl", calibration=72.54, weighting=weights), throughput=throughput)#.to(B.Debug('spl', _kw=_kw))
        (spl.to(B.Csv(spl_fname, headers=[f'l{w}eq' for w in weights.lower()], max_rows=10))
            .to(B.BlackHole(name="spl-bh")))
#define_graph_alt = define_graph_alt2


# def define_graph(B, use_tasks=True, throughput='large'):
#     Task = B.Task if use_tasks else B.Graph
#     with Task("USB"):
#         bulk_usb = B.BulkUSB(name="Bulk_USB", debug=True, verbose=False)

#     with Task("Basler_Camera"):
#         basler_cam = B.BaslerCam(name="Basler_Camera", fps=120, exp=0, bundle=8, global_time=bulk_usb.timestamp, queue=15)

#     with Task("Builtin_Camera"):
#         builtin_cam = B.BuiltinCamJetson(
#             name="Builtin_Camera", fps=15, bundle=None, zero_copy=True, global_time=bulk_usb.timestamp,
#             queue=15, debug=False, verbose=False, max_rate=None)

#     with Task("Basler_Writer"):
#         (basler_cam
#             .to(B.DirectWriter(name="Basler_Writer", filename_template=DATA_DIR + "basler_%d", bundle=16), throughput=throughput)
#             .to(B.BlackHole(name="Black_Hole_Basler")))

#     with Task("Builtin_Writer"):
#         (builtin_cam
#             .to(B.Bundle(name="Builtin_Write_Bundle", size=4, queue=3), throughput=throughput)
#             .to(B.DirectWriter(name="Builtin_Writer", filename_template=DATA_DIR + "builtin_%d", bundle=4))
#             .to(B.BlackHole(name="Black_Hole_Builtin")))

#     det = B.ObjectDetector(name="Object_Detector", max_rate=10, thr=0.8, draw=False, cuda_out=False, zero_copy=True, debug=True, verbose=False)
#     det.model = "ssd-mobilenet-v2"
#     # det.switch_interval = 10

#     basler_cam.to(det, throughput=throughput, strategy="latest")
#     builtin_cam.to(det, throughput=throughput, strategy="latest")

#     bh = B.BlackHole(name="Black_Hole_Detector")
#     (det.to(B.Bundle(name="Detection_Bundle", size=10))
#         .to(B.NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "detection_%d"))
#         .to(bh))

#     fol = B.Follower(name="Automatic_Follower", usb_device=bulk_usb, override=True, detector=det, debug=True, verbose=False)
#     fol.zoom_cam, fol.wide_cam = 0, 1
#     det.to(fol)

#     cin = B.ConsoleInput(name="Console_Input", debug=True)
#     ctl = B.Controller(name="Manual_Controller", usb_device=bulk_usb, debug=True)
#     ctl.selector = det.target_sel
#     cin.to(ctl)

#     # reip.default_graph().run(duration=None, stats_interval=10)

def define_graph(audio_length=10, rate=4, data_dir='./data', cam_2nd=True, throughput='large'):
    rate, timestamp = 4, str(time.time())

    os.makedirs(data_dir, exist_ok=True)
    cam_fname = os.path.join(data_dir, "video/%d_{}.avi".format(timestamp))
    det_fname = os.path.join(data_dir, "det/{}_%d".format(timestamp))
    spl_fname = os.path.join(data_dir, 'spl/{time}.csv')
    aud_fname = os.path.join(data_dir, 'audio/{time}.wav')

    with reip.Task("cam0-task"):
        cam_0 = UsbCamGStreamer(
            name="cam0", filename=cam_fname, dev=0,
            bundle=None, rate=rate, debug=False, verbose=False)

    if cam_2nd:
        with reip.Task("cam1-task"):
            cam_1 = UsbCamGStreamer(
                name="cam1", filename=cam_fname, dev=1,
                bundle=None, rate=rate, debug=False, verbose=False)

    with reip.Task('detect-task'):
        det = ObjectDetector(name='detect', n_inputs=1, labels_dir=MODEL_DIR, max_rate=None, thr=0.1,
                            draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
        det.model = "ssd-mobilenet-v2"

        cam_0.to(det, throughput=throughput, strategy="latest", index=0)
        if cam_2nd:
            cam_1.to(det, throughput=throughput, strategy="latest", index=1)

        (det.to(Bundle(name='det-bundle', size=10, meta_only=True))
            .to(NumpyWriter(name='det-write', filename_template=det_fname))
            .to(BlackHole(name='det-bh')))

    with reip.Task('mic-task'):
        audio1s = B.audio.Mic(
            name="mic", block_duration=1, channels=16, 
            device="hw:2,0", dtype=np.int32)
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length)).to(B.Debug('audio 10s'))

    with reip.Task("audio-write-task"):
        (audio_ns
            .to(B.audio.AudioFile(aud_fname), throughput=throughput)
            .to(BlackHole(name="audio-bh")))

    with reip.Task("spl-task"):
        spl = audio1s.to(B.audio.SPL(name="spl", calibration=72.54, weighting='ZAC'), throughput=throughput)
        (spl.to(B.Csv(spl_fname, headers=[f'l{w}eq' for w in spl.weight_names.lower()], max_rows=10))
            .to(BlackHole(name="spl-bh")))
   



try:
    from ai import ObjectDetector
    from usb_cam import UsbCamGStreamer
    B_ray, B_reip, B_waggle, B_base = get_blocks(
        UsbCamGStreamer, ObjectDetector, Bundle, NumpyWriter, BlackHole, 
        B.audio.Mic, B.FastRebuffer, B.audio.AudioFile, B.audio.SPL, B.Csv)
except ImportError:
    import traceback
    traceback.print_exc()
    print('Continuing on with dummy graph...')

    B_ray, B_reip, B_waggle, B_base = get_blocks(
            Generator, Bundle, NumpyWriter, BlackHole,
            B.audio.Mic, B.FastRebuffer, B.audio.AudioFile, B.audio.SPL, B.Csv, B.Debug)
    define_graph = define_graph_alt

Bs = {'ray': B_ray, 'reip': B_reip, 'waggle': B_waggle, 'base': B_base}


def run_graph(B, *a, duration=15, stats_interval=5, **kw):
    # a) single process
    with B.Graph() as g:
        print(g.__class__.__module__)
        define_graph(B, *a, **kw)
        #B.Monitor(g)
    try:
        g.run(duration=duration, stats_interval=stats_interval)
    except KeyboardInterrupt:
        print('interrupted.')
        raise
    finally:
        print(g.status())
    return g



def test(module='reip', *a, duration=10, **kw):
    g = run_graph(Bs[module], *a, duration=duration, **kw)


SIZES = [
    (2, 2),
    (60, 60),
    (120, 120),
    (180, 180),
    (240, 240),
    (480, 480),
    (960, 960),
    (1080, 1080),
    (1200, 1200),
    (1800, 1800),
    (2400, 2400),
    (3600, 3600),
]

def get_block_stats(b, data_size=None, **kw):
    n_proc, duration = b.processed, b.duration
    buf_per_sec = 1.*b.processed/b.duration
    d = dict(
        block=b.name, size=size, 
        buf_per_sec=buf_per_sec,
        data_per_sec=data_size*buf_per_sec if data_size else None,
        processed=n_proc, duration=duration, **kw)
    return d


def dump_results(results, i):
    with open('compare-{}-results-{}.json'.format(i, datetime.datetime.now().strftime('%c')), 'w') as f:
        json.dump(results, f)
    return results


def header(*txt, ch='*', s=2):
    txt = [str(' '.join(t) if isinstance(t, (list, tuple)) else t or '') for t in txt]
    n = max((len(t) for t in txt), default=0)
    n = max(n+1, 10)
    print('\n' + (ch*n) + '\n'*(max(0, i)) + '\n'.join(txt) + '\n' + (ch*n) + '\n')


def compare_1(*a, duration=30, **kw):
    '''1) Concurrency: Comparison  inside  of  REIP  -  prove that sometimes you need threading vs. multiprocessing 

    Comparing performance within  REIP - data rates/throughput for single process, multi process, and multi-process w/ shared memory
        (a) Single process: All blocks running on same process
        (b) MultiProcess: Same block setup, multiprocess
        (c) MultiProcess with shared memory: Same block setupwith Plasmastore

    IDEA: difficult scenarios have different requirements of data streams,  processing  times,  computational  cost, 
    this subsection should show that REIP can scale to multiple of those scenarios efficiently.
    '''
    results = []
    for size in SIZES:
        header(('size:', size))
        # a) single process
        header('single process', ('size:', size), s=1)
        g1 = run_graph(B_reip, *a, use_tasks=False, duration=duration, **kw)
        writer = g1.get_block('Builtin_Write_Bundle')
        det = g1.get_block('Object_Detector')
        results.extend(
            get_block_stats(b, group='single', size=size, data_size=size[0]*size[1])
            for b in [writer, det])

        # a) multi process - pickle
        header('single process', ('size:', size))
        g2 = run_graph(B_reip, *a, throughput='medium', duration=duration, **kw)
        writer = g2.get_block('Builtin_Write_Bundle')
        det = g2.get_block('Object_Detector')
        results.extend(
            get_block_stats(b, group='pickle', size=size, data_size=size[0]*size[1])
            for b in [writer, det])

        # a) multi process - plasma
        header('single process', ('size:', size))
        g3 = run_graph(B_reip, *a, throughput='large', duration=duration, **kw)
        writer = g3.get_block('Builtin_Write_Bundle')
        det = g3.get_block('Object_Detector')
        results.extend(
            get_block_stats(b, group='plasma', size=size, data_size=size[0]*size[1])
            for b in [writer, det])

    return dump_results(results, 1)


def compare_2(*a, duration=30, **kw):
    '''2) Overhead: Comparison inside of REIP - prove that we don’t add much overhead over the actual tasks that we want to perform.'''
    results = []
    for size in SIZES:
        g = run_graph(B_reip, *a, duration=duration, **kw)
        results.extend(
            get_block_stats(b, group='plasma', size=size, data_size=size[0]*size[1])
            for b in g.iter_blocks())
    return dump_results(results, 2)


def compare_3():
    '''3) Hardware platform: REIP’s software blocks are Linux-platform  agnostic  so  they  can  be  executed  on  a  large  variety of 
    single  board  computers  (SBC)  at  various  price  and  powerpoints.  This  flexibility  allows  the  software  to  be  matched 
    to suitable hardware based on the computational demands of theblocks and the project budget. In this use case, real-time, high-resolution 
    audio  processing  is  part  of  the  requirements  so  a minimum of a multi-core CPU SBC with at least 512 MB of RAM is required.
    '''
    results = []
    for size in SIZES:
        g = run_graph(B_reip, *a, duration=duration, **kw)
        results.extend(
            get_block_stats(b, size=size, data_size=size[0]*size[1])
            for b in g.iter_blocks())
    return dump_results(results, 3)


def compare_4():
    '''4) Comparing to other systems:'''
    results = []
    for size in SIZES:
        # REIP
        with B_reip.Graph() as g:
            define_graph(B_reip, *a, **kw)
        g.run(duration=duration)
        results.extend(
            get_block_stats(g2.get_block(name), group='reip', size=size, data_size=size[0]*size[1])
            for name in ['Builtin_Write_Bundle', 'Object_Detector'])

        # Ray
        with B_ray.Graph() as g:
            define_graph(B_ray, *a, **kw)
        g.run(duration=duration)
        results.extend(
            get_block_stats(g2.get_block(name), group='ray', size=size, data_size=size[0]*size[1])
            for name in ['Builtin_Write_Bundle', 'Object_Detector'])

        # Waggle
        with B_waggle.Graph() as g:
            define_graph(B_waggle, *a, **kw)
        g.run(duration=duration)
        results.extend(
            get_block_stats(g2.get_block(name), group='waggle', size=size, data_size=size[0]*size[1])
            for name in ['Builtin_Write_Bundle', 'Object_Detector'])

        # # Deepstream
        # with reip.Graph() as g:
        #     define_graph(*a, **kw)
        # g.run(duration=duration)
    return dump_results(results, 4)


if __name__ == '__main__':
    import fire
    fire.Fire()
