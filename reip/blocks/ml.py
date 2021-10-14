import reip
import numpy as np
import tflit
# import reip_gui.builder as rgui


class Tflite(reip.Block):
    model = None
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
        return self.model.predict(self._get_input_features(X, meta)), {'labels': self.labels}

    def finish(self):
        self.model = None