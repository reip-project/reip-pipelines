import os
import cv2
import reip
import tflit
import numpy as np


class Posenet(tflit.Model):
    MODEL_FILE = "models/posenet_mobilenet_v1_100_257x257_multi_kpt_stripped.tflite"
    def __init__(self):
        super().__init__(os.path.join(os.path.dirname(reip.__file__), self.MODEL_FILE))
        self.size = self.input_shape[1:-1]

    def predict_batch(self, X, *a, **kw):
        small = cv2.resize(X, self.size)
        X = (np.float32(small) - 127.5) / 127.5
        heat, offset = super().predict_batch([X], *a, **kw)[:2]
        kps = parse_output(heat[0], offset[0])
        return kps

    def draw(self, X, kps, **kw):
        return draw_kps(X, kps, size=self.size)



def parse_output(heatmap, offset, threshold=0.3):

    '''
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

def draw_kps(img, kps, limbs=True, face=True, size=None, thickness=1):
    if size:
        ratio = np.array(tuple(x/y for x, y in zip(img.shape, size)) + (1,))
        kps = (kps * ratio).astype(kps.dtype)
    for i in range(0 if face else 5, len(kps)):
        if kps[i, 2]:
            cv2.circle(img, (kps[i, 1], kps[i, 0]), 2, color=(0, 255, 255), thickness=thickness)

    if limbs:
        for part in body_parts:
            kp1, kp2 = kps[part[0]], kps[part[1]]
            if kps[i, 2]:
                cv2.line(
                    img, (kp1[1], kp1[0]), (kp2[1], kp2[0]),
                    color=(255, 255, 255), lineType=cv2.LINE_AA,
                    thickness=thickness)
    return img


body_parts = [(5,6),(5,7),(6,8),(7,9),(8,10),(11,12),(5,11),(6,12),(11,13),(12,14),(13,15),(14,16)]
