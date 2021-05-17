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
import reip.blocks.encrypt
import reip.blocks.os_watch
import reip.blocks.upload

from numpy_io import NumpyWriter
from direct_io import DirectWriter, DirectReader
from bundles import Bundle
from usb_cam import UsbCamGStreamer
from dummies import Generator, BlackHole
from cv_utils import ImageConvert, ImageDisplay
from ai import ObjectDetector
from controls import BulkUSB, Follower, Controller, ConsoleInput

DATA_DIR = './data'
MODEL_DIR = './models'


def mono():
    with reip.Task("Cam"):
        cam = UsbCamGStreamer(name="Cam", filename=DATA_DIR + "/video/%d_{time}.avi", dev=1,
                              bundle=None, rate=5, debug=True, verbose=False)
        cam.to(BlackHole(name="Black_Hole_Cam"))

    # with reip.Task("Det"):
    #     det = ObjectDetector(name="Detector", labels_dir=MODEL_DIR, max_rate=None, thr=0.1,
    #                         draw=False, cuda_out=False, zero_copy=False, debug=True, verbose=False)
    #     det.model = "ssd-mobilenet-v2"

    # bh_det = BlackHole(name="Black_Hole_Detector")
    # det_gr = Bundle(name="Detection_Bundle", size=10, meta_only=True)
    # det_wr = NumpyWriter(name="Detection_Writer", filename_template=DATA_DIR + "/det/detections_%d")

    # cam.to(det, throughput='large', strategy="latest")
    # det.to(det_gr).to(det_wr).to(bh_det)

    # bh_disp = BlackHole(name="Black_Hole_Display")
    # disp = ImageDisplay(name="Display", make_bgr=True)
    # det.to(disp, throughput='large', strategy="latest").to(bh_disp)


def stereo():
    with reip.Task("Cam_Task_0"):
        cam_0 = UsbCamGStreamer(name="Cam_0", filename=DATA_DIR + "/video/%d_{time}.avi", dev=0,
                              bundle=None, rate=6, debug=True, verbose=False)

    with reip.Task("Cam_Task_1"):
        cam_1 = UsbCamGStreamer(name="Cam_1", filename=DATA_DIR + "/video/%d_{time}.avi", dev=1,
                              bundle=None, rate=6, debug=True, verbose=False)

    with reip.Task("Detector_Task"):
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
    rate, timestamp = 4, str(time.time())

    with reip.Task("Cam_Task_0"):
        cam_0 = UsbCamGStreamer(name="Cam_0", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=0,
                              bundle=None, rate=rate, debug=False, verbose=False)

    # with reip.Task("Cam_Task_1"):
    #     cam_1 = UsbCamGStreamer(name="Cam_1", filename=DATA_DIR + "/video/%d_"+timestamp+".avi", dev=1,
    #                           bundle=None, rate=rate, debug=False, verbose=False)

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
        
    # with reip.Task("Audio_AI_Task"):
    #     emb = audio1s.to(B.ml.Tflite(os.path.join(MODEL_DIR, 'quantized_default_int8.tflite'),
    #             input_features=functools.partial(B.audio.ml_stft_inputs, sr=8000, duration=1, hop_size=0.1, n_fft=1024, n_mels=64, hop_length=160),
    #             name='embedding-model'), throughput='large')

    #     emb.to(B.Csv(os.path.join(DATA_DIR, 'emb/{time}.csv'), max_rows=10))

    #     clsf_path = os.path.join(MODEL_DIR, 'mlp_ust.tflite')
    #     class_names = ['engine', 'machinery_impact', 'non_machinery_impact', 'powered_saw', 'alert_signal', 'music', 'human_voice', 'dog']

    #     clsf = emb.to(B.ml.Tflite(clsf_path, name='classification-model'))
    #     clsf.to(B.Csv(os.path.join(DATA_DIR, 'clsf/{time}.csv'), headers=class_names, max_rows=10))


if __name__ == '__main__':
    # If camera got stcuk and does not open, run:
    # sudo service nvargus-daemon restart

    # mono()
    # stereo()
    # audio()
    all()

    reip.default_graph().run(duration=None, stats_interval=2)

