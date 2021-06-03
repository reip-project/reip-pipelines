import os
import json
import time
import datetime
import numpy as np
#import matplotlib.pyplot as plt

import reip
import reip.blocks as B
import reip.blocks.audio
import traceback
import sys
sys.path.append(os.path.abspath('..'))
os.environ["PYTHONPATH"] = os.path.abspath('..') + ":" + os.environ.get("PYTHONPATH", "")  # for workers

from numpy_io import NumpyWriter
# from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from dummies import Generator, BlackHole
# from cv_utils import ImageConvert, ImageDisplay
# from controls import BulkUSB, Follower, Controller, ConsoleInput
# from benchmark import DummyContext
from cv_utils import ImageWriter
from motion import MotionDetector

import base_app

DATA_DIR = '/mnt/ssd/test_data/'
#DATA_DIR = './data'
MODEL_DIR = '../models'
datafile = lambda *f: os.path.join(DATA_DIR, *f)


reip.Graph._delay = 1e-1
reip.Task._delay = 2e-1
#reip.Block._delay = 1e-1
reip.Block.USE_META_CLASS = True
reip.Block.KW_TO_ATTRS = True
reip.Block.run_profiler = False
reip.Task.run_profiler = False

OUT_DIR = './results'
DURATION = 60

MIC_DEVICE = "hw:2,0" #'Mic' #
MIC_CHANNELS = 1 #None #


def get_blocks(*blocks):
    try:
        import ray_app
        B_ray = ray_app.Block.wrap_blocks(*blocks)
    except ImportError:
        traceback.print_exc()
        B_ray = None
    try:
        import reip_app
        B_reip = reip_app.Block.wrap_blocks(*blocks)
    except ImportError:
        traceback.print_exc()
        B_reip = None
    try:
        import waggle_app
        B_waggle = waggle_app.Block.wrap_blocks(*blocks)
    except ImportError:
        traceback.print_exc()
        B_waggle = None
    try:
        import base_app
        B_base = base_app.Block.wrap_blocks(*blocks)
    except ImportError:
        traceback.print_exc()
        B_base = None
    return B_ray, B_reip, B_waggle, B_base



def define_graph_alt(
        B, size=(1280, 1280), rate=60, ncams=1, 
        throughput='large', use_tasks=True, 
        save_raw=False, meta_only=False, do_hist=True,
        motion=True, include_audio=False, 
        gen_debug=None, bundle_debug=False, bundle_log=True, io_debug=None, bh_debug=None, log_level='info'):

    Graph = B.Task if use_tasks else B.Graph

    cams = []
    for i in range(ncams):
        with Graph(f"cam{i}-task"):
            #rate = 120
            cam = B.Generator(name=f"cam{i}", size=size, inc=True, dtype=np.uint8, max_rate=rate, queue=rate*2, meta={'pixel_format': None}, log_level=log_level)
            cams.append(cam)

    if motion:
        with Graph(f"motion-task"):
            mv = B.MotionDetector(len(cams), name="motion", do_hist=do_hist, log_level=log_level)
            mv.to(B.ImageWriter(name="motion-write", path=DATA_DIR + "/motion/", make_bgr=False, save_raw=save_raw, meta_only=meta_only), throughput=throughput)
        mv(*cams, throughput=throughput, strategy="latest")

    if include_audio:
        define_graph_alt2(B, throughput=throughput, use_tasks=use_tasks)


def define_graph_alt2(B, audio_length=10, rate=4, data_dir='./data', use_tasks=True, throughput='large'):
    timestamp = time.time()

    os.makedirs(data_dir, exist_ok=True)
    cam_fname = os.path.join(data_dir, "video/%d_{}.avi".format(timestamp))
    det_fname = os.path.join(data_dir, "det/{}_%d".format(timestamp))
    spl_fname = os.path.join(data_dir, 'spl/{time}.csv')
    aud_fname = os.path.join(data_dir, 'audio/{time}.wav')

    _kw = dict(log_level='debug')
    Graph = B.Task if use_tasks else B.Graph
    with Graph('mic-task'):
        audio1s = B.Mic(
            name="mic", block_duration=1, channels=MIC_CHANNELS,
            device=MIC_DEVICE, dtype=np.int32)#.to(B.Debug('1s', _kw=_kw))
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length))

    with Graph("audio-write-task"):
        (audio_ns
            .to(B.AudioFile(aud_fname), throughput=throughput)#.to(B.Debug('audfile', _kw=_kw))
            .to(B.BlackHole(name="audio-bh")))

    with Graph("spl-task"):
        weights = 'ZAC'
        spl = audio1s.to(B.SPL(name="spl", calibration=72.54, weighting=weights), throughput=throughput)#.to(B.Debug('spl', _kw=_kw))
        (spl.to(B.Csv(spl_fname, headers=[f'l{w}eq' for w in weights.lower()], max_rows=10))
            .to(B.BlackHole(name="spl-bh")))
#define_graph_alt = define_graph_alt2

def build_full_benchmark(B, stereo=False, max_fps=15, save_raw=False, meta_only=False,
                    motion=True, do_hist=True, objects=False, thr=0.5, display=False,
                    threads_only=False, all_processes=False, throughput='large',
                    debug=False, verbose=False, config_id=-1):

    assert not (threads_only and all_processes), "Choose either threads_only or all_processes"

    n_cams = 2 if stereo else 1
    cams = [None] * n_cams

    Group = B.Graph if threads_only else B.Task
    Group2 = B.Task if all_processes else B.Graph

    for i in range(n_cams):
        with Group("Camera_%d_Task" % i):
            cams[i] = B.UsbCamGStreamer(name="Camera_%d" % i, filename=DATA_DIR + "/video/%d_{time}.avi",
                                      dev=i, bundle=None, rate=max_fps, debug=debug, verbose=verbose)

    if motion:
        with Group("Motion_Task"):
            mv = B.MotionDetector(name="Motion_Detector", do_hist=do_hist, debug=debug, verbose=verbose, log_level='debug')

        with Group2("Motion_Writer_Task"):
            mv.to(B.ImageWriter(name="Motion_Writer", path=DATA_DIR + "/motion/", make_bgr=False,
                                save_raw=save_raw, meta_only=meta_only), throughput=throughput)
        if display:
            with Group2("Motion_Display_Task"):
                mv.to(B.ImageDisplay(name="Motion_Display", make_bgr=False), throughput=throughput, strategy="latest")

        for i, cam in enumerate(cams):
            cam.to(mv, throughput=throughput, strategy="latest")#, index=i)

    if objects:
        with Group("Objects_Task"):
            obj = B.ObjectDetector(name="Objects_Detector", model="ssd-mobilenet-v2", thr=thr, labels_dir=MODEL_DIR,
                                 draw=True, cuda_out=False, zero_copy=False, debug=debug, verbose=verbose, log_level='debug')

        with Group2("Objects_Writer_Task"):
            obj.to(B.ImageWriter(name="Objects_Writer", path=DATA_DIR + "/objects/", make_bgr=True,
                                save_raw=save_raw, meta_only=meta_only), throughput=throughput)
        if display:
            with Group2("Objects_Display_Task"):
                obj.to(B.ImageDisplay(name="Objects_Display", make_bgr=True), throughput=throughput, strategy="latest")

        for i, cam in enumerate(cams):
            cam.to(obj, throughput=throughput, strategy="latest")#, index=i)


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

def define_graph(B, audio_length=10, rate=4, data_dir='./data', cam_2nd=True, use_tasks=True, throughput='large'):
    timestamp = time.time()

    os.makedirs(data_dir, exist_ok=True)
    cam_fname = os.path.join(data_dir, "video/%d_{}.avi".format(timestamp))
    det_fname = os.path.join(data_dir, "det/{}_%d".format(timestamp))
    spl_fname = os.path.join(data_dir, 'spl/{time}.csv')
    aud_fname = os.path.join(data_dir, 'audio/{time}.wav')

    Graph = B.Task if use_tasks else B.Graph
    with Graph("cam0-task"):
        cam_0 = B.UsbCamGStreamer(
            name="cam0", filename=cam_fname, dev=0,
            bundle=None, rate=rate, debug=False, verbose=False)

    if cam_2nd:
        with Graph("cam1-task"):
            cam_1 = B.UsbCamGStreamer(
                name="cam1", filename=cam_fname, dev=1,
                bundle=None, rate=rate, debug=False, verbose=False)

    with Graph('detect-task'):
        det = B.ObjectDetector(
            name='detect', n_inputs=1, labels_dir=MODEL_DIR, max_rate=None, thr=0.1,
            draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
        det.model = "ssd-mobilenet-v2"

        cam_0.to(det, throughput=throughput, strategy="latest", index=0)
        if cam_2nd:
            cam_1.to(det, throughput=throughput, strategy="latest", index=1)

        (det.to(B.Bundle(name='det-bundle', size=10, meta_only=True))
            .to(B.NumpyWriter(name='det-write', filename_template=det_fname))
            .to(B.BlackHole(name='det-bh')))

    with Graph('mic-task'):
        audio1s = B.Mic(
            name="mic", block_duration=1, channels=16, 
            device="hw:2,0", dtype=np.int32)
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length)).to(B.Debug('audio 10s'))

    with Graph("audio-write-task"):
        (audio_ns
            .to(B.AudioFile(aud_fname), throughput=throughput)
            .to(B.BlackHole(name="audio-bh")))

    with Graph("spl-task"):
        weights = 'ZAC'
        spl = audio1s.to(B.SPL(name="spl", calibration=72.54, weighting=weights), throughput=throughput)
        (spl.to(B.Csv(spl_fname, headers=[f'l{w}eq' for w in weights.lower()], max_rows=10))
            .to(B.BlackHole(name="spl-bh")))
   



try:
    # raise ImportError()

    from cv_utils import ImageDisplay
    from usb_cam import UsbCamGStreamer
    from ai import ObjectDetector

    B_ray, B_reip, B_waggle, B_base = get_blocks(
        UsbCamGStreamer, ObjectDetector, MotionDetector, ImageWriter, ImageDisplay, Bundle, NumpyWriter, BlackHole,
        B.audio.Mic, B.FastRebuffer, B.audio.AudioFile, B.audio.SPL, B.Csv)

    define_graph = build_full_benchmark

    # from ai import ObjectDetector
    # from usb_cam import UsbCamGStreamer
    # B_ray, B_reip, B_waggle, B_base = get_blocks(
    #     UsbCamGStreamer, ObjectDetector, Bundle, NumpyWriter, BlackHole,
    #     B.audio.Mic, B.FastRebuffer, B.audio.AudioFile, B.audio.SPL, B.Csv)
    # BLOCKS = ['cam0', 'cam1', 'detect']
except ImportError:
    import traceback
    traceback.print_exc()
    print('Continuing on with dummy graph...')

    B_ray, B_reip, B_waggle, B_base = get_blocks(
            Generator, Bundle, NumpyWriter, BlackHole, MotionDetector, ImageWriter,
            B.audio.Mic, B.FastRebuffer, B.audio.AudioFile, B.audio.SPL, B.Csv, B.Debug)
    # define_graph = define_graph_alt2
    define_graph = define_graph_alt
    BLOCKS = ['Basler_Cam', 'Builtin_Cam', 'Basler_Write_Bundle', 'Builtin_Write_Bundle', 'mic', 'spl-task']

Bs = {'ray': B_ray, 'reip': B_reip, 'waggle': B_waggle, 'base': B_base}


def run_graph(B, *a, duration=15, stats_interval=5, **kw):
    # clear names
    base_app.auto_name.clear()
    # define graph
    with B.Graph() as g:
        print(g.__class__.__module__)
        define_graph(B, *a, **kw)
        #B.Monitor(g)
    # run graph
    try:
        g.run(duration=duration, stats_interval=stats_interval)
    except KeyboardInterrupt as e:
        print('interrupted.')
        g.log.exception(e)  # show where it was interrupted
    except Exception as e:
        g.log.exception(e)  # always return g
    finally:
        print(g.status())
    return g



def test(module='reip', *a, duration=22, **kw):
    if module == "ray":
        import ray
        ray.init()

    g = run_graph(Bs[module], *a, duration=duration, **kw)


SIZES = [
    (2, 2),
    (60, 60),
    (120, 120),
    #(180, 180),
    (240, 240),
    (480, 480),
    (960, 960),
    (1080, 1080),
    #(1200, 1200),
    #(1800, 1800),
    #(2400, 2400),
    #(3600, 3600),
]


def get_block_stats(b, size=None, data_size=None, **kw):
    try:
        duration = b.duration
    except AttributeError:
        duration = b._sw.total()
    processed = b.processed
    buf_per_sec = 1. * processed / duration if duration else 0
    d = dict(
        block=b.name, size=size, data_size=data_size,
        buffers_per_sec=buf_per_sec,
        pixels_per_sec=data_size*buf_per_sec if data_size else None,
        processed=processed, 
        duration=duration,
        block_status=b.status(), 
        **kw)
    return d


def dump_results(results, name, out_dir='.'):
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, '{}-results-{}.json'.format(name, datetime.datetime.now().strftime('%Y_%m_%d-%H_%M_%S')))
    with open(fname, 'w') as f:
        json.dump(results, f)
    print('Wrote {} results to {}.'.format(len(results), fname))
    return results


#def header(*txt, ch='*', s=2):
    #txt = [str(' '.join(t) if isinstance(t, (list, tuple)) else t or '') for t in txt]
    #n = max((len(t) for t in txt), default=0)
    #n = max(n+1, 10)
    #print('\n' + (ch*n) + '\n'*(max(0, i)) + '\n'.join(txt) + '\n' + (ch*n) + '\n')
def header(*txt, **kw):
    print(reip.util.text.block_text(*txt, **kw))




def run(kind, *a, size=(480,480), name=None, blocks=None, out_dir=OUT_DIR, **kw):
    header(kind, ('size', size), ('args', str(a), str(kw)))
    g = run_graph(Bs[kind], *a, size=size, **kw)
    blocks = [g.get_block(k) for k in blocks] if blocks else g.iter_blocks()
    results = {
        b.name: get_block_stats(b, size=size, data_size=size[0]*size[1], status=g.status())
        for b in blocks
    }
    dump_results(results, name, out_dir=out_dir)
    print({k: {ki: d[ki] for ki in ('size', 'pixels_per_sec', 'processed', 'buffers_per_sec')} for k, d in results.items()})



def compare_1(*a, duration=DURATION, out_dir=OUT_DIR, **kw):
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
        g = run_graph(B_reip, *a, use_tasks=False, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(g.get_block(name), group='single', size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    for size in SIZES:
        # a) multi process - pickle
        header('pickle', ('size:', size))
        g = run_graph(B_reip, *a, throughput='medium', size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(g.get_block(name), group='pickle', size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    for size in SIZES:
        # a) multi process - plasma
        header('plasma', ('size:', size))
        g = run_graph(B_reip, *a, throughput='large', size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group='plasma', size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    return dump_results(results, 1, out_dir=out_dir)


def compare_2(*a, duration=DURATION, out_dir=OUT_DIR, **kw):
    '''2) Overhead: Comparison inside of REIP - prove that we don’t add much overhead over the actual tasks that we want to perform.'''
    results = []
    for size in SIZES:
        header(('size:', size))
        g = run_graph(B_reip, *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group='plasma', size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})
    return dump_results(results, 2, out_dir=out_dir)


def compare_3(*a, duration=DURATION, out_dir=OUT_DIR, **kw):
    '''3) Hardware platform: REIP’s software blocks are Linux-platform  agnostic  so  they  can  be  executed  on  a  large  variety of 
    single  board  computers  (SBC)  at  various  price  and  powerpoints.  This  flexibility  allows  the  software  to  be  matched 
    to suitable hardware based on the computational demands of theblocks and the project budget. In this use case, real-time, high-resolution 
    audio  processing  is  part  of  the  requirements  so  a minimum of a multi-core CPU SBC with at least 512 MB of RAM is required.
    '''
    results = []
    for size in SIZES:
        header(('size:', size))
        g = run_graph(B_reip, *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})
    return dump_results(results, 3, out_dir=out_dir)


def compare_4(*a, duration=DURATION, out_dir=OUT_DIR, **kw):
    '''4) Comparing to other systems:'''
    results = []
    for size in SIZES:
        kind = 'reip'
        header(kind, ('size:', size))
        g = run_graph(Bs[kind], *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group=kind, size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    for size in SIZES:
        kind = 'ray'
        header(kind, ('size:', size))
        g = run_graph(Bs[kind], *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group=kind, size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    for size in SIZES:
        kind = 'waggle'
        header(kind, ('size:', size))
        g = run_graph(Bs[kind], *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group=kind, size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})

    return dump_results(results, 4, out_dir=out_dir)


def compare_4_sep(kind, *a, duration=DURATION, out_dir=OUT_DIR, **kw):
    '''4) Comparing to other systems:'''
    results = []
    for size in SIZES:
        header(kind, ('size:', size))
        g = run_graph(Bs[kind], *a, size=size, duration=duration, **kw)
        results.extend({
            b.name: get_block_stats(b, group=kind, size=size, data_size=size[0]*size[1], status=g.status())
            for b in g.iter_blocks()})
    return dump_results(results, f'4_{kind}', out_dir=out_dir)


if __name__ == '__main__':
    import fire
    fire.Fire()
