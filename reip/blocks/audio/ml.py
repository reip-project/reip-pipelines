import numpy as np
import librosa
import reip.blocks as B
from reip.util.iters import npgenarray


class TfliteStft(B.Tflite):
    '''Run a tflite model on the audio input.'''
    def __init__(self, filename, sr=8000, duration=1, hop_size=0.1, n_fft=1024,
                 n_mels=64, mel_hop_len=160, **kw):
        super().__init__(filename, **kw)
        self.sr = sr
        self.duration = duration
        self.hop_size = hop_size
        self.n_fft = n_fft
        self.n_mels = n_mels
        self.mel_hop_len = mel_hop_len

    def get_input_features(self, data, meta):
        # load audio
        file, y = (data, None) if isinstance(data, str) else (None, data)
        y, sr = load_resample(file, y, meta.get('sr'), self.sr)
        # frame and extract stft
        frames = padframe(
            y, int(sr * self.duration), int(sr * self.hop_size)).T

        X = npgenarray(
            (self.melstft(frame, sr) for frame in frames),
            len(frames))[..., None]
        return X

    def melstft(self, X, sr):
        # magnitude spectrum
        S = np.abs(librosa.core.stft(
            X, n_fft=self.n_fft, hop_length=self.mel_hop_len,
            window='hann', center=True, pad_mode='constant'))

        # log mel spectrogram
        return librosa.power_to_db(
            librosa.feature.melspectrogram(
                S=S, sr=sr, n_mels=self.n_mels, htk=True),
            amin=1e-10)


'''

Utils

'''

def load_resample(fname=None, y=None, sr=None, target_sr=None):
    '''Get the audio data at a specified target sample rate.'''
    if y is None:
        y, sr = librosa.load(fname, sr=target_sr)
    else:
        y = y.reshape(-1, y.shape[1])[:,0]
        if sr and target_sr and sr != target_sr:
            y, sr = librosa.resample(y, sr, target_sr), target_sr
    return y, sr


def framepadlen(xlen, flen, hlen):
    '''Calculate the padding for a specific frame and hop size.'''
    return int(np.ceil(1. * (xlen - flen) / hlen) * hlen + flen)


def padframe(y, framelen, hoplen):
    '''Get framed array with zero padding to fill the first/last frames.'''
    y = librosa.util.pad_center(y, framepadlen(len(y), framelen, hoplen))
    return librosa.util.frame(y, framelen, hoplen)
