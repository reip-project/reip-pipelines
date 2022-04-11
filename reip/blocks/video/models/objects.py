import os
import cv2
import reip
import tflit
import numpy as np

def _model_file(name):
    return os.path.join(os.path.dirname(reip.__file__), 'models', name)

class COCOMobileNet(reip.Block):
    '''
    Object detection model from tensorflow. 80 classes.

    https://github.com/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi/blob/master/TFLite_detection_webcam.py

    Outputs:
      - boxes - Bounding box coordinates of detected objects
      - classes - Class index of detected objects
      - scores - Confidence of detected objects
      - num - Total number of detected objects (inaccurate and not needed)

    '''
    MODEL_FILE = "coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.tflite"
    LABEL_FILE = "coco_ssd_mobilenet_v1_1.0_quant_2018_06_29_labelmap.txt"

    def __init__(self, threshold=0.5, draw=None, **kw):
        self._should_draw = draw
        self.threshold = threshold
        super().__init__(n_outputs=2, **kw)

    def init(self):
        self.model = tflit.Model(reip.package_file('models', self.MODEL_FILE))
        # print(self.model.input_shape, self.model.output_shape, self.model.dtype)
        self.size = self.model.input_shape[1:-1]

        with open(reip.package_file('models', self.LABEL_FILE), 'r') as f:
            self.labels = [line.strip() for line in f.readlines()]
        if self.labels[0] == '???':
            del self.labels[0]

        self.should_draw = bool(self.sinks[1].readers) if self._should_draw is None else self._should_draw
        self.log.debug(f'will draw: {self.should_draw}')

    def process(self, frame, meta):
        X = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        X = cv2.resize(X, self.size)
        X = (np.float32(X) - 127.5) / 127.5
        boxes, classes, scores, _ = self.model.predict(X[None, ...])
        return [
            [boxes, classes, scores],
            draw_boxes(frame.copy(), boxes[0], classes[0], scores[0], self.labels, self.threshold)
            if self.should_draw else None
        ], meta


def draw_boxes(img, boxes, classes, scores, labels, threshold=0.5):
    imH, imW = img.shape[:2]
    for i in range(len(scores)):
        if threshold < scores[i] <= 1.0:
            # Get bounding box coordinates and draw box
            # Interpreter can return coordinates that are outside of image dimensions,
            # need to force them to be within image using max() and min()
            ymin = int(max(1, (boxes[i][0] * imH)))
            xmin = int(max(1, (boxes[i][1] * imW)))
            ymax = int(min(imH, (boxes[i][2] * imH)))
            xmax = int(min(imW, (boxes[i][3] * imW)))
            cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (10, 255, 0), 2)

            # Draw label
            label = '{}: {:.2%}'.format(labels[int(classes[i])], scores[i])
            labelSize, baseLine = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
            # Make sure not to draw label too close to top of window
            label_ymin = max(ymin, labelSize[1] + 10)
            cv2.rectangle(
                img, (xmin, label_ymin-labelSize[1]-10),
                (xmin+labelSize[0], label_ymin+baseLine-10),
                (10, 255, 0), cv2.FILLED) # Draw white box to put label text in
            cv2.putText(
                img, label, (xmin, label_ymin-7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2) # Draw label text

    # # Draw framerate in corner of frame
    # cv2.putText(img, 'FPS: {0:.2f}'.format(frame_rate_calc), (30,50),
    #             cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
    return img


Objects = COCOMobileNet