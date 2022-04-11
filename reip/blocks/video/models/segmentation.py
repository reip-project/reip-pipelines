import os
import cv2
import reip
import tflit
import numpy as np


class Deeplabv3(reip.Block):
    '''
    Object detection model from tensorflow. 80 classes.

    https://github.com/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi/blob/master/TFLite_detection_webcam.py

    Outputs:
      - boxes - Bounding box coordinates of detected objects
      - classes - Class index of detected objects
      - scores - Confidence of detected objects
      - num - Total number of detected objects (inaccurate and not needed)

    '''
    MODEL_FILE = "coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.tflite"
    LABEL_FILE = "coco_ssd_mobilenet_v1_1.0_quant_2018_06_29_labelmap.txt"
    def __init__(self, draw=None, **kw):
        self._should_draw = draw
        super().__init__(n_outputs=2, **kw)

    def init(self):
        self.model = Deeplabv3Model()
        self.should_draw = bool(self.sinks[1].readers) if self._should_draw is None else self._should_draw
        self.log.debug(f'will draw: {self.should_draw}')

    def process(self, frame, meta):
        X = self.model.predict(frame[None])
        return [X, self.model.draw(frame, X[0]) if self.should_draw else None], meta


class Deeplabv3Model(tflit.Model):
    input_size = (257, 257)
    MODEL_FILE = "lite-model_deeplabv3_1_metadata_2.tflite"
    def __init__(self) -> None:
        self.size = self.input_shape[1:-1]
        super().__init__(reip.package_file('models', self.MODEL_FILE))

    def predict_batch(self, im, *a, **kw):
        im = cv2.resize(im[0][0], self.input_size)
        im = (im / 255).astype('float32')[None]
        return super().predict_batch([im], *a, **kw)

    def draw(self, im, segment, mix=0.5, xpad=5, rect_size=20, ypad=30, label_spacing=40):
        seg_cls = np.argmax(segment, axis=-1)
        ids, counts = np.unique(seg_cls, return_counts=True)
        seg_im = np.array(colors[seg_cls], dtype='float32')
        total = seg_cls.size

        if im.shape != seg_im.shape:
            seg_im = cv2.resize(seg_im, im.shape[:2][::-1])
        im = im * (1-mix) + seg_im * mix

        for i, (c, k) in enumerate(sorted(zip(counts[ids != 0], ids[ids != 0]), reverse=True)):
            if c > total * 0.01:
                color = tuple(map(int, colors[k]))
                cv2.rectangle(
                    im, 
                    (xpad, ypad + i * label_spacing - rect_size//2),
                    (xpad + rect_size, ypad + i * label_spacing + rect_size//2),
                    color, cv2.FILLED)
                label = f'{classes[k]} ({c / total:.2%})'
                txy = (xpad * 2 + rect_size, ypad + i * label_spacing)
                cv2.putText(im, label, txy, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                cv2.putText(im, label, txy, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
        return im / 255

Segment = Deeplabv3


classes = [
    '__background__', 'aeroplane', 'bicycle', 'bird', 'boat', 'bottle', 'bus',
    'car', 'cat', 'chair', 'cow', 'diningtable', 'dog', 'horse', 'motorbike',
    'person', 'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor']

colors = np.array([
    [0, 0, 0],
    [255,102,51],
    [255,179,153],
    [255,51,255],
    [255,255,153],
    [0,179,230],
    [230,179,51],
    [51,102,230],
    [153,153,102],
    [153,255,153],
    [179,77,77],
    [128,179,0],
    [128,153,0],
    [230,179,179],
    [102,128,179],
    [102,153,26],
    [255,153,230],
    [204,255,26],
    [255,26,102],
    [230,51,26],
    [51,255,204],
    [102,153,77],
    [179,102,204],
    [77,128,0],
    [179,51,0],
    [204,128,204],
    [102,102,77],
    [153,26,255],
    [230,102,255],
    [77,179,255],
    [26,179,153],
    [230,102,179],
    [51,153,26],
    [204,153,153],
    [179,179,26],
    [0,230,128],
    [77,128,102],
    [128,153,128],
    [230,255,128],
    [26,255,51],
    [153,153,51],
    [255,51,128],
    [204,204,0],
    [102,230,77],
    [77,128,204],
    [153,0,179],
    [230,77,102],
    [77,179,128],
    [255,77,77],
    [153,230,230],
    [102,102,255],
], dtype='float32')