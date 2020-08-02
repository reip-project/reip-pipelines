import reip
import numpy as np
import librosa


class SPL(reip.Block):
    def __init__(self, duration=1, weighting='zac',
                 calibration=0, **kw):
        super().__init__()
        self.duration = duration
        self.calibration = calibration
        self._weighting = weighting
        # stft args
        self.kw = kw
        self.kw.setdefault('center', False)
        # blank initial values - see _init()
        self.weight_names = []
        self.weightings = None
        self.n_fft = None

    def _init(self, data, meta):
        # calculate the fft size using the sample rate and window duration
        self.n_fft = self.duration * meta['sr']
        self.n_fft = int(2 ** np.floor(np.log2(self.n_fft)))
        self.kw.setdefault('hop_length', self.n_fft)
        assert len(data) >= self.n_fft
        # get the frequency weights for each weighting function
        freqs = librosa.fft_frequencies(sr=meta['sr'], n_fft=self.n_fft)
        self.weight_names = [w.upper() for w in list(self._weighting or 'Z')]
        self.weightings = librosa.db_to_power(
            librosa.multi_frequency_weighting(freqs, self._weighting))

    def process(self, data, meta):
        if self.weightings is None:  # initialize using sr from metadata
            self._init(data, meta)
        # select single channel (48000, 1) => (48000,)
        data = data.reshape(len(data), -1)[:, 0]
        # get spectrogram (frequency, time) - (1025, 94)
        S = librosa.core.stft(data, n_fft=self.n_fft, **self.kw)
        # get weighted leq (3, 1025) x (1025, 94) => (1, 3)
        leq = self.calibration + librosa.power_to_db((
            self.weightings[..., None] * (S ** 2)).mean(-2)).T
        return [leq], {}


class Stft(reip.Block):
    def __init__(self, **kw):
        self.kw = kw
        super().__init__()

    def process(self, y, meta):
        if y.ndim > 1:
            y = y[:, 0]
        S = librosa.amplitude_to_db(np.abs(librosa.stft(y, **self.kw)))
        return [S], meta
