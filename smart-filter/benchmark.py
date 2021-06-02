import reip

from cv_utils import ImageWriter, ImageDisplay
from usb_cam import UsbCamGStreamer
from motion import MotionDetector
from ai import ObjectDetector

DATA_DIR = '/mnt/ssd/data'
MODEL_DIR = './models'


class DummyContext:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def build_benchmark(stereo=False, max_fps=15, save_raw=False, meta_only=False,
                    motion=True, do_hist=True, objects=True, thr=0.5, display=False,
                    threads_only=False, all_processes=False, throughput='large',
                    debug=False, verbose=False, config_id=-1):

    assert not (threads_only and all_processes), "Choose either threads_only or all_processes"

    n_cams = 2 if stereo else 1
    cams = [None] * n_cams

    for i in range(n_cams):
        with DummyContext() if threads_only else reip.Task("Camera_%d_Task" % i):
            cams[i] = UsbCamGStreamer(name="Camera_%d" % i, filename=DATA_DIR + "/video/%d_{time}.avi",
                                      dev=i, bundle=None, rate=max_fps, debug=debug, verbose=verbose)

    if motion:
        with DummyContext() if threads_only else reip.Task("Motion_Task"):
            mv = MotionDetector(name="Motion_Detector", do_hist=do_hist, debug=debug, verbose=verbose)

            if not all_processes and not threads_only:
                mv.to(ImageWriter(name="Motion_Writer", path=DATA_DIR + "/motion/",
                                  make_bgr=False, save_raw=save_raw, meta_only=meta_only))
                if display:
                    mv.to(ImageDisplay(name="Motion_Display", make_bgr=False), strategy="latest")

        if all_processes or threads_only:
            with DummyContext() if threads_only else reip.Task("Motion_Writer_Task"):
                mv.to(ImageWriter(name="Motion_Writer", path=DATA_DIR + "/motion/", make_bgr=False,
                                  save_raw=save_raw, meta_only=meta_only), throughput=throughput)
            if display:
                with DummyContext() if threads_only else reip.Task("Motion_Display_Task"):
                    mv.to(ImageDisplay(name="Motion_Display", make_bgr=False), throughput=throughput, strategy="latest")

        for i, cam in enumerate(cams):
            cam.to(mv, index=i, throughput=throughput, strategy="latest")

    if objects:
        with DummyContext() if threads_only else reip.Task("Objects_Task"):
            obj = ObjectDetector(name="Objects_Detector", model="ssd-mobilenet-v2", thr=thr, labels_dir=MODEL_DIR,
                                 draw=True, cuda_out=False, zero_copy=False, debug=debug, verbose=verbose)

            if not all_processes and not threads_only:
                obj.to(ImageWriter(name="Objects_Writer", path=DATA_DIR + "/objects/",
                                   make_bgr=True, save_raw=save_raw, meta_only=meta_only))
                if display:
                    obj.to(ImageDisplay(name="Objects_Display", make_bgr=True), strategy="latest")

        if all_processes or threads_only:
            with DummyContext() if threads_only else reip.Task("Objects_Writer_Task"):
                obj.to(ImageWriter(name="Objects_Writer", path=DATA_DIR + "/objects/", make_bgr=True,
                                   save_raw=save_raw, meta_only=meta_only), throughput=throughput)
            if display:
                with DummyContext() if threads_only else reip.Task("Objects_Display_Task"):
                    obj.to(ImageDisplay(name="Objects_Display", make_bgr=True), throughput=throughput, strategy="latest")

        for i, cam in enumerate(cams):
            cam.to(obj, index=i, throughput=throughput, strategy="latest")


def run_benchmark(duration=42, stats_interval=10, **kw):
    print("\nRunning for %d seconds:\n" % duration, kw, "\n")

    build_benchmark(**kw)
    reip.default_graph().run(duration=duration, stats_interval=stats_interval)

    exit(0)


def gen_script():
    with open("benchmark.sh", "w") as f:
        f.write("#!/bin/bash\n\n")

        f.write("rm -fr logs\n")
        f.write("mkdir logs\n\n")

        template = "python3 benchmark.py --stereo=%s --threads_only=%s --all_processes=%s --throughput=%s --config_id=%d"

        config = 0
        for stereo in [True, False]:
            for threads_only, all_processes in [(False, False), (True, False), (False, True)]:
                for throughput in ["small", "medium", "large"]:
                    cmd = template % (str(stereo), str(threads_only), str(all_processes), throughput, config)
                    cmd += " | tee \'logs/config_%d.log\'\n\n" % config
                    config += 1

                    f.write(cmd)

    exit(0)


if __name__ == '__main__':
    # run_benchmark(stereo=True, motion=True, objects=True, display=False, threads_only=False, all_processes=False, debug=True)

    # gen_script()

    import fire
    fire.Fire(run_benchmark)
