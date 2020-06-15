import numpy as np

def get_np_pa_conversion():
    import pyaudio
    pa2np = {
        pyaudio.paInt8: 'int8',
        pyaudio.paInt16: 'int16',
        pyaudio.paInt32: 'int32',
        pyaudio.paFloat32: 'float32',
        pyaudio.paUInt8: 'uint8',
    }
    pa2np.update({k: np.dtype(v) for k, v in pa2np.items()})
    np2pa = {v: k for k, v in pa2np.items()}
    return pa2np, np2pa

def pa2npfmt(fmt):
    np2pa, pa2np = get_np_pa_conversion()
    return np.dtype(fmt if fmt in np2pa else pa2np[fmt])

def np2pafmt(fmt):
    np2pa, pa2np = get_np_pa_conversion()
    return fmt if fmt in pa2np else np2pa[np.dtype(fmt)]
