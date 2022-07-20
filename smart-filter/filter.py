import os
import cv2
import time
import functools
import numpy as np
# import matplotlib.pyplot as plt

import reip
import reip.blocks as B
import reip.blocks.ml
import reip.blocks.audio
# import reip.blocks.encrypt
import reip.blocks.os_watch
import reip.blocks.upload

from numpy_io import NumpyWriter
from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from usb_cam import UsbCamGStreamer
from dummies import Generator, BlackHole
from cv_utils import ImageConvert, ImageDisplay, ImageWriter
from ai import ObjectDetector
from motion import MotionDetector
from controls import BulkUSB, Follower, Controller, ConsoleInput
from audio import MicArray

# DATA_DIR = './data'
DATA_DIR = '/home/reip/data'
MODEL_DIR = './models'


def mono_object():
    with reip.Task("Cam"):
        cam = UsbCamGStreamer(name="Cam", filename=DATA_DIR + "/video/%d_{time}.avi", dev=0,
                              bundle=None, rate=15, debug=False, verbose=False)

    with reip.Task("Det"):
        det = ObjectDetector(name="Detector", labels_dir=MODEL_DIR, max_rate=None, thr=0.1, model = "ssd-mobilenet-v2",
                            draw=True, cuda_out=False, zero_copy=False, debug=True, verbose=False)

    cam.to(det, throughput='large', strategy="latest")

    det.to(ImageWriter(name="Writer", path=DATA_DIR + "/objects/"), throughput='large').to(BlackHole(name="Writer_BH"))

    # det.to(ImageDisplay(name="Display"), throughput='large', strategy="latest").to(BlackHole(name="Display_BH"))


def mono_motion():
    with reip.Task("Cam"):
        cam = UsbCamGStreamer(name="Cam", filename=DATA_DIR + "/video/%d_{time}.avi", dev=1,
                              bundle=None, rate=15, debug=False, verbose=False)

    with reip.Task("Det"):
        det = MotionDetector(name="Detector", do_hist=True, debug=True, verbose=False)

    cam.to(det, throughput='large', strategy="latest")

    det.to(ImageWriter(name="Writer", path=DATA_DIR + "/motion/", make_bgr=False), throughput='large').to(BlackHole(name="Writer_BH"))

    # det.to(ImageDisplay(name="Display", make_bgr=False), throughput='large', strategy="latest").to(BlackHole(name="Display_BH"))


def mono_both():
    # with reip.Task("Cam"):
    cam = UsbCamGStreamer(name="Cam", filename=DATA_DIR + "/video/%d_{time}.avi", dev=0,
                            bundle=None, rate=15, debug=False, verbose=False)

    # with reip.Task("Det_Objects"):
    det = ObjectDetector(name="Objects_Detector", labels_dir=MODEL_DIR, max_rate=None, thr=0.1, model = "ssd-mobilenet-v2",
                        draw=True, cuda_out=False, zero_copy=False, debug=True, verbose=False)

    cam.to(det, throughput='large', strategy="latest")

    det.to(ImageWriter(name="Objects_Writer", path=DATA_DIR + "/objects/"), throughput='large').to(BlackHole(name="Objects_Writer_BH"))

    # det.to(ImageDisplay(name="Objects_Display"), throughput='large', strategy="latest").to(BlackHole(name="Objects_Display_BH"))

    # with reip.Task("Det_Motion"):
    det = MotionDetector(name="Motion_Detector", do_hist=True, debug=True, verbose=False)

    cam.to(det, throughput='large', strategy="latest")

    det.to(ImageWriter(name="Motion_Writer", path=DATA_DIR + "/motion/", make_bgr=False), throughput='large').to(BlackHole(name="Motion_Writer_BH"))

    # det.to(ImageDisplay(name="Motion_Display", make_bgr=False), throughput='large', strategy="latest").to(BlackHole(name="Motion_Display_BH"))


def stereo():
    # with reip.Task("Cam_Task_0"):
    cam_0 = UsbCamGStreamer(name="Cam_0", filename=DATA_DIR + "/video/%d_{time}.avi", dev=0,
                              bundle=None, rate=6, debug=True, verbose=False)

    # with reip.Task("Cam_Task_1"):
    cam_1 = UsbCamGStreamer(name="Cam_1", filename=DATA_DIR + "/video/%d_{time}.avi", dev=1,
                              bundle=None, rate=6, debug=True, verbose=False)

    # with reip.Task("Detector_Task"):
    det = ObjectDetector(name="Detector", n_inputs=2, labels_dir=MODEL_DIR, max_rate=None, thr=0.1,
                        draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
    det.model = "ssd-mobilenet-v2"

    cam_0.to(det, throughput='large', strategy="latest", index=0)
    cam_1.to(det, throughput='large', strategy="latest", index=1)

    det_gr = Bundle(name="Detection_Bundle", size=10, meta_only=True)
    det_wr = NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "/det/detections_%d")
    det.to(det_gr).to(det_wr).to(BlackHole(name="Black_Hole_Detector"))

    # bh_disp = BlackHole(name="Black_Hole_Display")
    # disp = ImageDisplay(name="Display", make_bgr=True)
    # det.to(disp, throughput='large', strategy="latest").to(bh_disp)


def audio():
    audio1s = B.audio.Mic(block_duration=1, channels=16, device="hw:2,0", dtype=np.int32)#.to(B.Debug('audio pcm'))
    audio10s = audio1s.to(B.FastRebuffer(size=10))
    
    audio10s.to(B.audio.AudioFile(os.path.join(DATA_DIR, 'audio/{time}.wav')))

    weightings = 'ZAC'
    spl = audio1s.to(B.audio.SPL(calibration=72.54, weighting=weightings))
    # write to file
    spl_headers = [f'l{w}eq' for w in weightings.lower()]
    spl.to(B.Csv(os.path.join(DATA_DIR, 'spl/{time}.csv'), headers=spl_headers, max_rows=10))

    with reip.Task("Embeddings_Task"):
        emb = audio1s.to(B.ml.Tflite(os.path.join(MODEL_DIR, 'quantized_default_int8.tflite'),
                input_features=functools.partial(B.audio.ml_stft_inputs, sr=8000, duration=1, hop_size=0.1, n_fft=1024, n_mels=64, hop_length=160),
                name='embedding-model'))

        emb.to(B.Csv(os.path.join(DATA_DIR, 'emb/{time}.csv'), max_rows=10))

        clsf_path = os.path.join(MODEL_DIR, 'mlp_ust.tflite')
        class_names = ['engine', 'machinery_impact', 'non_machinery_impact', 'powered_saw', 'alert_signal', 'music', 'human_voice', 'dog']

        clsf = emb.to(B.ml.Tflite(clsf_path, name='classification-model'))
        clsf.to(B.Csv(os.path.join(DATA_DIR, 'clsf/{time}.csv'), headers=class_names, max_rows=10))


def all(audio_length=10):
    rate, timestamp = 10, str(time.time())

    with reip.Task("Cam_Task_0"):
        cam_0 = UsbCamGStreamer(name="Cam_0", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=0,
                              bundle=None, rate=rate, debug=False, verbose=False)

    with reip.Task("Cam_Task_1"):
        cam_1 = UsbCamGStreamer(name="Cam_1", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=1,
                               bundle=None, rate=rate, debug=False, verbose=False)

    with reip.Task("Detector_Task"):
       det = ObjectDetector(name="Detector", n_inputs=1, labels_dir=MODEL_DIR, max_rate=None, thr=0.1,
                           draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
       det.model = "ssd-mobilenet-v2"

       cam_0.to(det, throughput='large', strategy="latest", index=0)
       # cam_1.to(det, throughput='large', strategy="latest", index=1)

       det_gr = Bundle(name="Detection_Bundle", size=10, meta_only=True)
       det_wr = NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "/det/"+timestamp+"_%d")
       det.to(det_gr).to(det_wr).to(BlackHole(name="Black_Hole_Detector"))

    with reip.Task("Mic_Array_Task"):
        audio1s = B.audio.Mic(name="Mic_rray", block_duration=1, channels=16, device="hw:2,0", dtype=np.int32)#.to(B.Debug('audio pcm'))
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length))

    with reip.Task("Audio_Writer_Task"):
        audio_ns.to(B.audio.AudioFile(os.path.join(DATA_DIR, 'audio/{time}.wav')), throughput='large').to(BlackHole(name="Black_Hole_Audio_Writer"))

    with reip.Task("SPL_Task"):
       weightings = 'ZAC'
       spl = audio1s.to(B.audio.SPL(name="SPL", calibration=72.54, weighting=weightings), throughput='large')
       # write to file
       spl_headers = [f'l{w}eq' for w in weightings.lower()]
       spl.to(B.Csv(os.path.join(DATA_DIR, 'spl/{time}.csv'), headers=spl_headers, max_rows=10)).to(BlackHole(name="Black_Hole_SPL"))
        
    with reip.Task("Audio_AI_Task"):
        emb = audio1s.to(B.ml.Tflite(os.path.join(MODEL_DIR, 'quantized_default_int8.tflite'),
                input_features=functools.partial(B.audio.ml_stft_inputs, sr=8000, duration=1, hop_size=0.1, n_fft=1024, n_mels=64, hop_length=160),
                name='embedding-model'), throughput='large')

        emb.to(B.Csv(os.path.join(DATA_DIR, 'emb/{time}.csv'), max_rows=10))

        clsf_path = os.path.join(MODEL_DIR, 'mlp_ust.tflite')
        class_names = ['engine', 'machinery_impact', 'non_machinery_impact', 'powered_saw', 'alert_signal', 'music', 'human_voice', 'dog']

        clsf = emb.to(B.ml.Tflite(clsf_path, name='classification-model'))
        clsf.to(B.Csv(os.path.join(DATA_DIR, 'clsf/{time}.csv'), headers=class_names, max_rows=10))


def test_audio():
    # audio1s = B.audio.Mic(block_duration=1, channels=16, device="hw:2,0", dtype=np.int32)#.to(B.Debug('audio pcm'))
    audio1s = MicArray(name="MicArray", interval=1, use_pyaudio=False, debug=True, verbose=False)#.to(B.Debug('audio pcm'))
    audio20s = audio1s.to(B.FastRebuffer(size=20))
    audio20s.to(B.audio.AudioFile(os.path.join(DATA_DIR, 'audio/test_{time}.wav')))


def nec(audio_length=60):
    rate, timestamp = 3, str(time.time())

    with reip.Task("USB"):
        bulk_usb = BulkUSB(name="Bulk_USB", debug=True, verbose=True)

    with reip.Task("Cam_Task_0"):
        cam_0 = UsbCamGStreamer(name="Cam_0", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=0, g_time=bulk_usb.timestamp,
                              bundle=None, rate=rate, debug=False, verbose=False)
        cam_0_gr = Bundle(name="Cam_0_Bundle", size=180, meta_only=True)
        cam_0_wr = NumpyWriter(name="Cam_0_Writer", filename_template=DATA_DIR + "/time/0_"+timestamp+"_%d")
        cam_0.to(cam_0_gr).to(cam_0_wr).to(BlackHole(name="Cam_0_BH"))

    with reip.Task("Cam_Task_1"):
        cam_1 = UsbCamGStreamer(name="Cam_1", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=1, g_time=bulk_usb.timestamp,
                               bundle=None, rate=rate, debug=False, verbose=False)
        cam_1_gr = Bundle(name="Cam_1_Bundle", size=180, meta_only=True)
        cam_1_wr = NumpyWriter(name="Cam_1_Writer", filename_template=DATA_DIR + "/time/1_"+timestamp+"_%d")
        cam_1.to(cam_1_gr).to(cam_1_wr).to(BlackHole(name="Cam_1_BH"))

    with reip.Task("Mic_Array_Task"):
        audio1s = MicArray(name="MicArray", interval=1, use_pyaudio=False, debug=True, verbose=False)
        audio_ns = audio1s.to(B.FastRebuffer(size=audio_length))
        audio_ns.to(B.audio.AudioFile(os.path.join(DATA_DIR, 'audio/{time}.wav'))).to(BlackHole(name="Audio_Writer_BH"))


if __name__ == '__main__':
    # If camera got stcuk and does not open, run:
    # sudo service nvargus-daemon restart

    # mono_object()
    # mono_motion()
    #mono_both()

    # test_audio()
    # stereo()
    # audio()
    # all()
    nec()

    reip.default_graph().run(duration=None, stats_interval=3)

