import reip
import numpy as np


class Tflite(reip.Block):
    '''Run a tflite model on the data input.'''
    def __init__(self, filename, labels=None, input_features=None, **kw):
        super().__init__(**kw)
        self.model = load_tflite_model_function(filename)
        self.labels = labels
        self._get_input_features = (
            self.input_features if input_features is None
            else input_features)

    def input_features(self, data, meta):
        return data

    def process(self, X, meta):
        return (
            [self.model(self._get_input_features(X, meta))],
            {'labels': self.labels}
        )


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
