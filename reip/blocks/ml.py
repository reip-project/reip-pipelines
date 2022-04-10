import reip
import numpy as np
import tflit
# import reip_gui.builder as rgui


class Tflite(reip.Block):
    '''Run a tflite model.'''
    model = None
    # @rgui.options(rgui.Text(), rgui.MultiLabel(), input_features=rgui.FunctionDef('data', 'meta'))
    # @rgui.options  # infer from docstring
    def __init__(self, filename, labels=None, input_features=None, **kw):
        '''Run a tflite model on the data input.

        Arguments:
            filename (str): the model filename.
            labels (list[str]): the labels corresponding to each model output.
            input_features (callable): prepare the block input so that it is in
                the format needed by the model.
        '''
        super().__init__(**kw)
        self.filename = filename
        self.labels = labels
        self._get_input_features = (
            self.input_features if input_features is None
            else input_features)

    def input_features(self, data, meta):
        return data

    def init(self):
        self.model = tflit.Model(self.filename)

    def process(self, X, meta):
        meta["labels"] = self.labels
        return (
            [self.model.predict(self._get_input_features(X, meta))],
            meta
        )
        # return (
        #     [self.model.predict(self._get_input_features(X, meta))],
        #     {'labels': self.labels}
        # )

    def finish(self):
        self.model = None


# def load_tflite_model_function(model_path):
#     import tflite_runtime.interpreter as tflite
#     compute = prepare_model_function(tflite.Interpreter(model_path))
#     compute.model_path = model_path
#     return compute
#
#
# def prepare_model_function(model, verbose=False):
#     # allocate and get shapes
#     in0_dets = model.get_input_details()[0]
#     out0_dets = model.get_output_details()[0]
#     input_shape, output_shape = in0_dets['shape'][1:], out0_dets['shape'][1:]
#     in_idx, out_idx = in0_dets['index'], out0_dets['index']
#     model.allocate_tensors()
#
#     if verbose:
#         print('-- Input details --')
#         print(in0_dets, '\n')
#         print('-- Output details --')
#         print(out0_dets, '\n')
#
#     # Get the L3 embedding
#     def compute(x):
#         model.set_tensor(in_idx, x.copy().astype(np.float32))
#         model.invoke()
#         return model.get_tensor(out_idx).copy()
#     compute.input_shape = input_shape
#     compute.output_shape = output_shape
#     return compute
