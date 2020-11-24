import reip
import numpy as np
import librosa


class SPL(reip.Block):
    weightings = None
    hop_duration = None
    n_fft = None
    def __init__(self, duration=1, weighting='zac',
                 calibration=0, **kw):
        super().__init__(extra_kw=True, **kw)
        self.duration = duration
        self.calibration = calibration
        self._weighting = weighting
        # stft args
        self.extra_kw.setdefault('center', False)
        # blank initial values - see _init()
        self.weight_names = []

    def _init(self, meta):
        # calculate the fft size using the sample rate and window duration
        self.n_fft = self.duration * meta['sr']
        self.n_fft = int(2 ** np.floor(np.log2(self.n_fft)))
        self.extra_kw.setdefault('hop_length', self.n_fft)
        self.hop_duration = self.extra_kw['hop_length'] / meta['sr']
        # get the frequency weights for each weighting function
        freqs = librosa.fft_frequencies(sr=meta['sr'], n_fft=self.n_fft)
        self.weight_names = [w.upper() for w in list(self._weighting or 'Z')]
        self.weightings = librosa.db_to_power(
            librosa.multi_frequency_weighting(freqs, self._weighting or 'Z'))

    def process(self, data, meta):
        if self.weightings is None:  # initialize using sr from metadata
            self._init(meta)
        # select single channel (48000, 1) => (48000,)
        data = np.atleast_2d(data.T)[0]
        # get spectrogram (frequency, time) - (1025, 94)
        S = librosa.core.stft(data, n_fft=self.n_fft, **self.extra_kw)
        # get weighted leq (3, 1025) x (1025, 94) => (94, 3)
        leq = self.calibration + librosa.power_to_db((
            self.weightings[..., None] * (S ** 2)).mean(-2)).T
        return [leq], {
            'spl_weightings': self.weight_names,
            'hop_duration': self.hop_duration,
        }


class Stft(reip.Block):
    def process(self, y, meta):
        S = librosa.amplitude_to_db(np.abs(librosa.stft(
            y[:, 0] if y.ndim > 1 else y,
            **self.extra_kw)))
        return [S], meta
