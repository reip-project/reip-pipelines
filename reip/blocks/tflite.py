import librosa
import numpy as np
from .block import Block
from ..utils.ml import *


class Tflite(Block):
    '''Run a tflite model on the data input.'''
    def __init__(self, *a, filename, **kw):
        super().__init__(*a, **kw)
        self.model = load_tflite_model_function(filename)

    def transform(self, **kw):
        return self.model(self.get_input_features(**kw))

    def get_input_features(self, x):
        return x



class AudioTflite(Tflite):
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

    def get_input_features(self, file=None, data=None, sr=None):
        if data is None:
            data, sr = librosa.load(file, sr=self.sr)
        elif sr and self.sr and sr != self.sr:
            data, sr = librosa.resample(data, sr, self.sr), self.sr

        frames = padframe(
            data, int(sr * self.duration), int(sr * self.hop_size)).T
        return npgenarray((
            self.melstft(frame, sr)
            for frame in frames),
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
