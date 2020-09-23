import time
import os
import cv2
import reip
import tflit
import numpy as np

def _model_file(name):
    return os.path.join(os.path.dirname(reip.__file__), 'models', name)

class StyleTransfer(reip.Block):
    '''
    https://www.tensorflow.org/lite/models/style_transfer/overview#style_prediction
    '''
    MODEL_FILE = "magenta_arbitrary-image-stylization-v1-256_int8_transfer_1.tflite"
    STYLE_MODEL_FILE = "magenta_arbitrary-image-stylization-v1-256_int8_prediction_1.tflite"
    MODEL_IMAGE_DIM = 384
    STYLE_IMAGE_DIM = 256

    def __init__(self, style, **kw):
        super().__init__(**kw)
        self._init_style = style

    def init(self):
        self.model = tflit.Model(_model_file(self.MODEL_FILE))
        self.style_model = tflit.Model(_model_file(self.STYLE_MODEL_FILE))
        self.size = self.model.input_shape[1:-1]
        self.set_style(self._init_style)

    def process(self, frame, meta):
        X = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        X = preprocess_image(X, self.MODEL_IMAGE_DIM)

        styled = self.model.predict([X[None, ...], self._style_emb])[0]
        # undo
        # styled = cv2.resize(styled, frame.shape[:2][::-1])
        styled = np.uint8(styled * 127.5 + 127.5)
        styled = cv2.cvtColor(styled, cv2.COLOR_RGB2BGR)
        return [restore_aspect(styled, frame)], {}


    def set_style(self, img, img2=None, blend=0.5):
        self._style_emb = (
            self.blend_style(img, img2, blend)[0]
            if img2 is not None else
            self.generate_style(img)[0])
        return self._style_emb

    def blend_style(self, imgA, imgB, blend=0.5):
        styleA, imgA = self.generate_style(imgA)
        styleB, imgB = self.generate_style(imgB)
        return (blend * styleA + (1 - blend) * styleB), imgA, imgB

    def generate_style(self, img):
        if isinstance(img, str):
            img = cv2.imread(img, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        X = preprocess_image(img, self.STYLE_IMAGE_DIM)

        style_emb = self.style_model.predict(X[None, ...])
        return style_emb, img


def preprocess_image(img, target_dim=256):
    # Resize the image so that the shorter dimension becomes 256px.
    shape = img.shape[:2]
    shape = (np.asarray(shape) * target_dim / min(shape)).astype(int)
    img = cv2.resize(img, tuple(shape))

    # Central crop the image.
    img = resize_with_crop_or_pad(img, target_dim, target_dim, 3)
    img = (np.float32(img) - 127.5) / 127.5
    return img

def resize_with_crop_or_pad(arr, *size):
    out = np.zeros(size)
    diffs = [(s1 - s2) / 2 for s1, s2 in zip(arr.shape, size)]
    oslc = tuple(
        slice(int(max(0, -d)), int(min(s, s + d)))
        for d, s in zip(diffs, size))
    aslc = tuple(
        slice(int(max(0, d)), int(min(s, s - d)))
        for d, s in zip(diffs, arr.shape))
    out[oslc] = arr[aslc]
    return out

def restore_aspect(modified, original, stretch=False):
    mh, mw = modified.shape[:2]
    oh, ow = original.shape[:2]
    sh = mw * oh / ow
    sw = mh * ow / oh
    return cv2.resize(modified, (
        sh if (sh > mh) == bool(stretch) else mh,
        sw if (sw > mw) == bool(stretch) else mw,
    ))
