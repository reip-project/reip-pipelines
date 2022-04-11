
import os
import cv2
import reip
import tflit
import numpy as np

import reip


class Posenet(reip.Block):
    '''Pose Keypoint Detection.
    
    Outputs:
        keypoints (np.ndarray[n, (x, y, z)]): coordinates of the keypoints and flags for
            those that have low probability.
        drawn_image (np.ndarray[h, w, c]): The input image with keypoints drawn on.
    '''
    def __init__(self, draw=None, **kw):
        self._should_draw = draw
        super().__init__(n_outputs=2, **kw)

    def init(self):
        self.model = PosenetModel()
        self.should_draw = bool(self.sinks[1].readers) if self._should_draw is None else self._should_draw
        self.log.debug(f'will draw: {self.should_draw}')


    def process(self, frame, meta):
        frame = np.array(frame)
        kps = self.model.predict_batch(frame[None])
        return [kps, self.model.draw(frame, kps) if self.should_draw else None], meta


class PosenetModel(tflit.Model):
    '''Posenet - pose estimation
    
    Source: https://www.tensorflow.org/lite/examples/pose_estimation/overview
    '''
    MODEL_FILE = "posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite"
    multi_input = False
    def __init__(self, threshold=0.3):
        super().__init__(reip.package_file('models', self.MODEL_FILE))
        self.summary()
        self.size = self.input_shape[1:-1]
        self.threshold = threshold

    def predict_batch(self, image, *a, **kw):
        small = cv2.resize(image[0], self.size)
        x = (np.float32(small) - 127.5) / 127.5
        heat, offset = super().predict_batch(x[None], *a, **kw)[:2]
        kps = parse_output(heat[0], offset[0], self.threshold)
        return kps

    def draw(self, X, kps, **kw):
        return draw_kps(X, kps, size=self.size)



def parse_output(heatmap, offset, threshold=0.3):
    '''Parse Posenet outputs.

    Args:
        heatmap (np.array[d=3]): heatmaps for an image. First output of model.
        offset (np.array[d=3]): offset vectors for an image. Second output of model.
        threshold (float): probability threshold for the keypoints.

    Returns:
        kps (np.array[n x (x,y,z)]): coordinates of the keypoints and flags for
            those that have low probability.
    '''

    joint_num = heatmap.shape[-1]
    pose_kps = np.zeros((joint_num, 3), np.uint32)

    for i in range(joint_num):
        joint_heatmap = heatmap[...,i]
        max_prob = np.max(joint_heatmap)
        i_max = np.squeeze(np.argwhere(joint_heatmap == max_prob))
        remap_pos = np.array(i_max/8*257, dtype=np.int32)
        pose_kps[i, 0] = int(remap_pos[0] + offset[i_max[0], i_max[1], i])
        pose_kps[i, 1] = int(remap_pos[1] + offset[i_max[0], i_max[1], i+joint_num])
        if max_prob > threshold and pose_kps[i, 0] < 257 and pose_kps[i, 1] < 257:
            pose_kps[i, 2] = 1
    return pose_kps

def draw_kps(img, kps, limbs=True, face=True, size=None, thickness=3):
    if size:
        ratio = np.array(tuple(x/y for x, y in zip(img.shape, size)) + (1,))
        kps = (kps * ratio).astype(kps.dtype)
    for i in range(0 if face else 5, len(kps)):
        if kps[i, 2]:
            cv2.circle(img, (kps[i, 1], kps[i, 0]), 2, color=(255, 0, 255), thickness=thickness)

    if limbs:
        for part in body_parts:
            kp1, kp2 = kps[part[0]], kps[part[1]]
            if kp1[2] and kp2[2]:
                cv2.line(
                    img, (kp1[1], kp1[0]), (kp2[1], kp2[0]),
                    color=(255, 255, 255), lineType=cv2.LINE_AA,
                    thickness=thickness)
    return img


body_parts = [(5,6),(5,7),(6,8),(7,9),(8,10),(11,12),(5,11),(6,12),(11,13),(12,14),(13,15),(14,16)]


Pose = Posenet