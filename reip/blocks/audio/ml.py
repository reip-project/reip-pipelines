import os
import numpy as np
import librosa
import reip
import reip.blocks as B
import reip.blocks.ml



as_model_file = lambda f: os.path.join(os.path.dirname(reip.__file__), 'models', f)

class EdgeL3(B.ml.Tflite):
    model_path = as_model_file('edgel3_embedding.tflite')
    model_params = dict(
        target_sr=8000, 
        duration=1, 
        hop_size=0.1, 
        n_fft=1024,
        hop_length=160,
        n_mels=64, 
    )

    def __init__(self, model_path=None, **kw):
        super().__init__(model_path or self.model_path, **kw)

    def process(self, data, meta):
        if isinstance(data, str):
            y, sr = librosa.load(data, sr=None)
        else:
            y, sr = data, meta.get('sr')
        S = preprocess_audio(y, sr, **dict(self.model_params, **self.extra_kw))
        z = self.model(S)
        return [z], meta


class EdgeL3Embedding2Class(B.ml.Tflite):
    classes = [
        'engine',
        'machinery_impact',
        'non_machinery_impact',
        'powered_saw',
        'alert_signal',
        'music',
        'human_voice',
        'dog',
    ]
    model_path = as_model_file('edgel3_mlp_classification.tflite')
    def __init__(self, model_path=None, **kw):
        super().__init__(model_path or self.model_path, **kw)






def preprocess_audio(y, sr, duration, hop_size, target_sr=None, **kw):
    '''Get the audio data at a specified target sample rate.'''
    if y.ndim == 2:
        y = y[:,0]
    # proper sr
    y = librosa.resample(y, orig_sr=sr, target_sr=target_sr or sr)
    sr = target_sr or sr
    # frame
    framelen = int(sr * duration)
    hoplen = int(sr * hop_size)
    y = librosa.util.pad_center(y, size=framepadlen(len(y), framelen, hoplen))
    frames = librosa.util.frame(y, frame_length=framelen, hop_length=hoplen)
    # build mel spec
    S = np.array([
        melstft(frame, sr, **kw)
        for frame in frames.T
    ])[...,None]
    return S


def framepadlen(xlen, flen, hlen):
    '''Calculate the padding for a specific frame and hop size.'''
    return int(np.ceil(1. * (xlen - flen) / hlen) * hlen + flen)


def melstft(X, sr, n_fft=2048, hop_length=512, n_mels=64):
    # magnitude spectrum
    S = np.abs(librosa.core.stft(
        X, n_fft=n_fft, hop_length=hop_length,
        window='hann', center=True, pad_mode='constant'))

    # log mel spectrogram
    return librosa.power_to_db(
        librosa.feature.melspectrogram(
            S=S, sr=sr, n_mels=n_mels, htk=True),
        amin=1e-10)



# def ml_stft_inputs(data, meta, hop_size=0.1, duration=1, sr=8000, **kw):
#     # load audio
#     file, y = (data, None) if isinstance(data, str) else (None, data)
#     y, sr = load_resample(file, y, meta.get('sr'), sr)
#     # frame and extract stft
#     frames = padframe(y, int(sr * duration), int(sr * hop_size)).T
#     X = npgenarray(
#         (melstft(frame, sr, **kw) for frame in frames),
#         len(frames))[..., None]
#     return X

# def melstft(X, sr, n_fft=2048, hop_length=512, n_mels=64):
#     # magnitude spectrum
#     S = np.abs(librosa.core.stft(
#         X, n_fft=n_fft, hop_length=hop_length,
#         window='hann', center=True, pad_mode='constant'))

#     # log mel spectrogram
#     return librosa.power_to_db(
#         librosa.feature.melspectrogram(
#             S=S, sr=sr, n_mels=n_mels, htk=True),
#         amin=1e-10)




# '''

# Utils

# '''

# def load_resample(fname=None, y=None, sr=None, target_sr=None):
#     '''Get the audio data at a specified target sample rate.'''
#     if y is None:
#         y, target_sr = librosa.load(fname, mono=False, sr=target_sr)
#     else:
#         y = y.T
#         y = np.atleast_2d(y)[0, :]
#         if len(y) == 1:
#             y = y[0]
#         if sr and target_sr and sr != target_sr:
#             y = librosa.resample(y, sr, target_sr)
#     return y, target_sr or sr


# def framepadlen(xlen, flen, hlen):
#     '''Calculate the padding for a specific frame and hop size.'''
#     return int(np.ceil(1. * (xlen - flen) / hlen) * hlen + flen)


# def padframe(y, framelen, hoplen):
#     '''Get framed array with zero padding to fill the first/last frames.'''
#     y = librosa.util.pad_center(y, framepadlen(len(y), framelen, hoplen))
#     return librosa.util.frame(y, framelen, hoplen)
