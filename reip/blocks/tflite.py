'''Machine Learning blocks.



'''

from lazyimport import librosa
import numpy as np
from .block import Block
from ..utils.ml import (
    load_tflite_model_function, padframe, npgenarray, load_resample)


class tflite(Block):
    '''Run a tflite model on the data input.'''
    def __init__(self, *a, filename, **kw):
        super().__init__(*a, **kw)
        self.model = load_tflite_model_function(filename)

    def transform(self, X, meta):
        return self.model(self.get_input_features(X, meta))

    def get_input_features(self, data, meta):
        return data


class stft(tflite):
    '''Run a tflite model on the audio input.'''
    def __init__(self, *a, sr=None, duration=1, hop_size=0.1, n_fft=1024,
                 n_mels=64, mel_hop_len=160, fmax=None, **kw):
        super().__init__(*a, **kw)
        self.sr = sr
        self.duration = duration
        self.hop_size = hop_size
        self.n_fft = n_fft
        self.n_mels = n_mels
        self.mel_hop_len = mel_hop_len
        self.fmax = fmax

    def get_input_features(self, data, meta):
        # load audio
        file, y = (data, None) if isinstance(data, str) else (None, data)
        y, sr = load_resample(file, y, meta.get('sr'), self.sr)
        # frame and extract stft
        frames = padframe(
            y, int(sr * self.duration), int(sr * self.hop_size)).T
        return npgenarray(
            (self.melstft(frame, sr) for frame in frames),
            len(frames))

    def melstft(self, X, sr):
        # magnitude spectrum
        S = np.abs(librosa.core.stft(
            X, n_fft=self.n_fft, hop_length=self.mel_hop_len,
            window='hann', center=True, pad_mode='constant'))

        # log mel spectrogram
        return librosa.power_to_db(
            librosa.feature.melspectrogram(
                S=S, sr=sr, n_mels=self.n_mels, fmax=self.fmax, htk=True),
            amin=1e-10)

tflite.stft = stft
