'''
Machine Learning Utilities
==========================


'''

import itertools
import numpy as np
import librosa



framepadlen = lambda xlen, flen, hlen: int(
    np.ceil(1. * (xlen - flen) / hlen) * hlen + flen)

def padframe(y, framelen, hoplen):
    return librosa.util.frame(
        librosa.util.pad_center(y, framepadlen(y.size, framelen, hoplen)),
        framelen, hoplen)



def load_tflite_model_function(model_path):
    import tflite_runtime.interpreter as tflite
    compute = prepare_model_function(tflite.Interpreter(model_path))
    compute.model_path = model_path
    return compute


def prepare_model_function(model, verbose=False):
    # allocate and get shapes
    in0_dets = model.get_input_details()[0]
    out0_dets = model.get_output_details()[0]
    input_shape, output_shape = in0_dets['shape'][1:], out0_dets['shape'][1:]
    in_idx, out_idx = in0_dets['index'], out0_dets['index']
    model.allocate_tensors()

    if verbose:
        print('-- Input details --')
        print(in0_dets, '\n')
        print('-- Output details --')
        print(out0_dets, '\n')

    # Get the L3 embedding
    def compute(x):
        model.set_tensor(in_idx, x.copy().astype(np.float32))
        model.invoke()
        return model.get_tensor(out_idx).copy()
    compute.input_shape = input_shape
    compute.output_shape = output_shape
    return compute


'''

Utils

'''

def peakiter(it, n=1):
    '''Check the value first n items of an iterator without unloading them from
    the iterator queue.'''
    it = iter(it)
    items = [_ for _, i in zip(it, range(n))]
    return items, itertools.chain(items, it)

def npgenarray(it, shape, **kw):
    '''Create a np.ndarray from a generator. Must specify at least the length
    of the generator or the entire shape of the final array.'''
    if isinstance(shape, int):
        (x0,), it = peakiter(it)
        shape = (shape,) + x0.shape
    X = np.zeros(shape, **kw)
    for i, x in enumerate(it):
        X[i] = x
    return X

def npmaparray(func, X):
    return npgenarray((func(x) for x in X), len(X))
