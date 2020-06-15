import librosa
import numpy as np
from ..block import Block

class SPL(Block):
    def __init__(self, sr=22050, n_fft=2048, hop_length=512, weighting='z', calibration=0, **kw):
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.calibration = calibration

        self.freqs = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        self.weight_names, self.weightings = get_weighting_power(
            self.freqs, weighting)

        super().__init__(**kw)

    def output_names(self):
        return {'data': self.weight_names}

    def transform(self, data, **kw):
        # select single channel
        data = data.reshape(len(data), -1)[:, 0]
        # get [frequency, time]
        S = librosa.core.stft(
            data,
            n_fft=self.n_fft,
            hop_length=self.hop_length)
        # get weighted leq
        return self.calibration + librosa.power_to_db((
            self.weightings[:,None] * S[None] ** 2).mean(-2))


class SPLOctaves(Block):
    def __init__(self, n_bands=1, sr=22050, hop_length=512, weighting=None,
                 fmin=20, fmax=20000, calibration=0, **kw):
        self.sr = sr
        self.fmin = fmin
        self.n_bands = n_bands
        self.hop_length = hop_length
        self.calibration = calibration

        self.n_bins = np.ceil(
            librosa.hz_to_octs(fmax)
            - librosa.hz_to_octs(fmin)) * self.n_bands

        self.freqs = librosa.core.cqt_frequencies(
            self.n_bins, self.fmin, self.n_bands)
        self.weight_names, self.weightings = get_weighting_power(
            self.freqs, weighting)

        super().__init__(**kw)

    def output_names(self):
        return {'data': (self.weight_names, self.freqs)}

    def transform(self, data, **kw):
        # select single channel
        data = data.reshape(len(data), -1)[:, 0]
        # get [frequency, time]
        S = librosa.core.pseudo_cqt(
            data,
            sr=self.sr,
            fmin=self.fmin,
            n_bins=self.n_bins,
            hop_length=self.hop_length,
            bins_per_octave=self.n_bands)
        # get weighted leq
        return self.calibration + librosa.power_to_db((
            self.weightings * S[None] ** 2).mean(-1))



def get_weighting_power(freqs, weighting):
    weighting = [w.upper() for w in list(weighting or 'Z')]
    return weighting, np.stack([
        librosa.db_to_power(librosa.frequency_weighting(freqs, w))
        for w in weighting
    ], axis=0)

#
# def get_f_center(bands=1, n=None, center=1000):
#     '''Get an array of 1/n octave band center frequencies.'''
#     n = n or bands * 10
#     return center / (2 ** ((n // 2 - np.arange(n)) / bands))
#
#
# def octave_setup(freq, f_center, b):
#     '''Create octave band slices'''
#     # create slice indices for bands
#     f_b = 2.0 ** (1.0 / 2.0 * b)
#     idx1 = np.abs(freq[None] - (f_center / f_b)[:,None]).argmin(1)
#     idx2 = np.abs(freq[None] - (f_center * f_b)[:,None]).argmin(1)
#     idx = [slice(i1, i2) for i1, i2 in zip(idx1, idx2)]
#
#     # Preallocate octave amplitude array
#     f_fcs = freq.copy()
#     for fc, ix in zip(f_center, idx):
#         f_fcs[ix] = freq[ix] / fc
#
#     dfq = freq[1] - freq[0]
#     amp = 2 * dfq / (1. + (1.507 * b * (f_fcs - 1. / f_fcs)) ** 6.)
#     return amp, idx
#
#
# def make_octaves(n_bands, freq):
#     # get frequency bands
#     f_center = get_f_center(n_bands)
#     amp, idx = octave_setup(freq, f_center, b=n_bands)
#
#     def compute(X):
#         return 10 * np.log10(np.stack([
#             np.mean(X[...,i] * amp[...,i], -1) for i in idx], -1))
#     compute.n_bands = n_bands
#     compute.f_center = f_center
#     compute.idx = idx
#     return compute
