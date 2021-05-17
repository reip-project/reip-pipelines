import os
import sys
import time
import json
import reip
import numpy as np
from ctypes import *
from numpy_io import NumpyEncoder
import multiprocessing as mp
import jetson.inference
import jetson.utils
import cv2
# import torch
# import torchvision
# import trt_pose.coco
# import trt_pose.models
# import torch2trt
# from torch2trt import TRTModule
# import torchvision.transforms as transforms
# import PIL.Image

# from trt_pose.draw_objects import DrawObjects
# from trt_pose.parse_objects import ParseObjects

print(cv2.__version__)


class ObjectDetector(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    draw = False  # Output drawn image if True
    cuda_out = False  # Output cuda image if True
    zero_copy = False  # Output a copy if False
    model = "ssd-inception-v2"  # Detection model: ssd-mobilenet-v1, ssd-mobilenet-v2 or ssd-inception-v2
    labels_dir = "./"  # Directory with ssd_coco_labels.txt
    # labels_dir = "/mnt/ssd/legotracker/vscode_workspace/models/"  # Directory with ssd_coco_labels.txt
    thr = 0.5  # Confidence threshold
    target_sel = mp.Value(c_uint, 0, lock=False)  # Desired (external) input source selection
    current_sel = mp.Value(c_uint, 0, lock=False)  # Current input source selection
    switch_interval = None  # Switch input with fixed interval if not None (overrides target_sel)
    inner_sw = None

    def __init__(self, **kw):
        # enable variable number of sources
        super().__init__(n_inputs=None, source_strategy=all, **kw)

    def init(self):
        assert(self.model in ["ssd-mobilenet-v1", "ssd-mobilenet-v2", "ssd-inception-v2"])
        self.n_in = len(self.sources) or 1
        if self.debug:
            print("ObjectDetector: %d inputs avaiable" % self.n_in)

        with open(self.labels_dir + "ssd_coco_labels.txt", "r") as f:
            self.labels = [line.strip() for line in f.readlines()]
            if self.debug or True:
                print("ObjectDetector Labels:", self.labels)

        self.net = jetson.inference.detectNet(self.model, threshold=self.thr)
        self.inner_sw = reip.util.Stopwatch("inner")
        self.cuda_in, self.np_in = [None] * self.n_in, [None] * self.n_in
        self.cuda_det, self.np_det = [None] * self.n_in, [None] * self.n_in

    def parse_detection(self, detection):
        fields = ["ClassID", "Confidence", "Left", "Top", "Right", "Bottom", "Width", "Height", "Area", "Center"]
        # return {field.lower(): getattr(detection, field) for field in fields}
        return {field: getattr(detection, field) for field in fields}

    def process(self, *xs, meta=None):
        assert(len(xs) == self.n_in)
        # print(xs, type(meta), meta)
        if self.n_in == 1:
            meta = [dict(meta)]

        if self.switch_interval is not None:
            if self.processed % self.switch_interval == 0:
                self.current_sel.value = (self.current_sel.value + 1) % self.n_in
                if self.debug:
                    print("\nObjectDetector: Select input %d\n" % self.current_sel.value)
        else:
            if self.current_sel.value != self.target_sel.value and (self.debug or True):
                print("\nObjectDetector: New input %d\n" % self.target_sel.value)
            self.current_sel.value = self.target_sel.value

        sel = self.current_sel.value

        if type(xs[sel]) != np.ndarray:
            if self.debug:
                print("ObjectDetector: No data on desired input (%d)" % sel)
            return None

        # assert(type(xs[sel]) == np.ndarray)  # TODO: Accept cuda images as input
        # assert(len(xs[sel].shape) in [3, 4])

        # detect bundle input
        bundle = (len(xs[sel].shape) == 4) or ("buffer_0" in dict(meta[sel]).keys())
        # take the last image if bundle input
        img_in = xs[sel][-1, ...] if bundle else xs[sel]
        sel_meta = meta[sel]["buffer_%d" % (xs[sel].shape[0] - 1)] if bundle else meta[sel]
        sel_meta = dict(sel_meta)
        # parse metadata
        h, w = sel_meta["resolution"]
        pixel_format = sel_meta["pixel_format"].lower()

        # adapt basler camera formatting
        if pixel_format == "bayergb8":
            pixel_format = "bayer-gbrg"
        if pixel_format == "mono8":
            pixel_format = "gray8"
        # if pixel_format == "i420":
        #     pixel_format = "nv12"
        if len(img_in.shape) == 2:
            img_in = img_in[:, :, None]

        if self.debug and self.verbose:
            print("\nObjectDetector: Received", (h, w), pixel_format)

        if self.cuda_in[sel] is not None:
            if w != self.cuda_in[sel].width or h != self.cuda_in[sel].height or pixel_format != self.cuda_in[sel].format:
                self.cuda_in[sel] = None

        if self.cuda_in[sel] is None:
            if self.debug:
                print("ObjectDetector: Allocating buffers")

            with self.inner_sw("allocate"):
                print(w, h, pixel_format)
                self.cuda_in[sel] = jetson.utils.cudaAllocMapped(width=w, height=h, format=pixel_format)
                self.np_in[sel] = jetson.utils.cudaToNumpy(self.cuda_in[sel])
                print(self.cuda_in[sel], self.np_in[sel])

                self.cuda_det[sel] = jetson.utils.cudaAllocMapped(width=w, height=h, format="rgb8")
                self.np_det[sel] = jetson.utils.cudaToNumpy(self.cuda_det[sel])

        with self.inner_sw("cvt_in"):
            t0 = time.time()

            if pixel_format == "rgb8":
                self.np_det[sel][...] = img_in
            else:
                self.np_in[sel][...] = img_in
                jetson.utils.cudaConvertColor(self.cuda_in[sel], self.cuda_det[sel])
                jetson.utils.cudaDeviceSynchronize()

            if self.debug and self.verbose:
                print("cvt_in time:", time.time() - t0)

        with self.inner_sw("detect"):
            detections = self.net.Detect(self.cuda_det[sel], overlay=("box,label,conf" if self.draw else ""))

            if self.debug and self.verbose and len(detections) > 0:
                print("ObjectDetector: Detected", len(detections), "objects:")

                if self.verbose:
                    # for detection in detections:
                    #     print(detection)
                    self.net.PrintProfilerTimes()

        with self.inner_sw("cvt_out"):
            t0 = time.time()
            if self.draw:
                if self.cuda_out:
                    if self.zero_copy:
                        img_out = self.cuda_det[sel]
                    else:
                        cuda_tmp = jetson.utils.cudaAllocMapped(width=w, height=h, format="rgb8")
                        img_out = jetson.utils.cudaToNumpy(cuda_tmp)
                        img_out[...] = self.np_det[sel]
                else:
                    img_out = self.np_det[sel] if self.zero_copy else self.np_det[sel].copy()
            else:
                img_out = None

            if self.debug and self.verbose:
                print("cvt_out time:", time.time() - t0)

        return [img_out], {"model": self.model,
                            "thr": self.thr,
                            "draw": self.draw,
                            "pixel_format": "rgb8" if self.draw else None,
                            "objects": [self.parse_detection(det) for det in detections if det.Confidence >= self.thr],
                            "class_labels": self.labels,
                            "detections_id": self.processed,
                            "source_sel": sel,
                            "source_meta": sel_meta}

    def finish(self):
        if self.debug or True:
            print("\nObjectDetector inner stats:\n" + str(self.inner_sw), "\n")


# class PoseDetector(reip.Block):
#     debug = False  # Debug output
#     verbose = False  # Detailed debug output
#     weights_dir = "/mnt/ssd/legotracker/vscode_workspace/models/"  # Directory with weights
#     model = "densenet121"  # Detection model: resnet18 or densenet121
#     draw = False  # Output drawn image if True

#     weights_filename = {"resnet18": 'resnet18_baseline_att_224x224_A_epoch_249.pth',
#                         "densenet121": 'densenet121_baseline_att_256x256_B_epoch_160.pth'}
#     model_size = {"resnet18": 224, "densenet121": 256}

#     def init(self):
#         assert(self.model in ["resnet18", "densenet121"])

#         self.model_weights = self.weights_dir + self.weights_filename[self.model]
#         self.optimized_model = self.model_weights[:-4] + "_trt.pth"
#         self.size = self.model_size[self.model]

#         with open(self.weights_dir + 'human_pose.json', 'r') as f:
#             self.human_pose = json.load(f)

#         self.topology = trt_pose.coco.coco_category_to_topology(self.human_pose)
#         self.parse_objects = ParseObjects(self.topology)
#         self.draw_objects = DrawObjects(self.topology)

#         if self.debug:
#             print("Human pose:", self.human_pose)
#             # print("Topology:", self.topology)

#         if not os.path.isfile(self.optimized_model):
#             self.optimize_weights()

#         self.model_trt = TRTModule()
#         self.model_trt.load_state_dict(torch.load(self.optimized_model))
#         self.device = torch.device('cuda')
#         self.mean = torch.Tensor([0.485, 0.456, 0.406]).cuda()
#         self.std = torch.Tensor([0.229, 0.224, 0.225]).cuda()

#         if self.debug:
#             print("Loaded model_trt:", self.optimized_model)

#     def optimize_weights(self):
#         num_parts = len(self.human_pose['keypoints'])
#         num_links = len(self.human_pose['skeleton'])

#         if self.model == "resnet18":
#             model = trt_pose.models.resnet18_baseline_att(num_parts, 2 * num_links).cuda().eval()
#         else:
#             model = trt_pose.models.densenet121_baseline_att(num_parts, 2 * num_links).cuda().eval()

#         model.load_state_dict(torch.load(self.model_weights))
#         if self.debug:
#             print("Loaded weights:", self.model_weights)

#         dummy_data = torch.zeros((1, 3, self.size, self.size)).cuda()
#         model_trt = torch2trt.torch2trt(model, [dummy_data], fp16_mode=True, max_workspace_size=1<<25)
#         if self.debug and self.verbose:
#             print("model_trt:", model_trt)    

#         torch.save(model_trt.state_dict(), self.optimized_model)
#         if self.debug:
#             print("Saved model_trt:", self.optimized_model)

#     def preprocess(self, img):
#         img = PIL.Image.fromarray(img)  # expects RGB
#         img = img.resize((self.size, self.size), resample=PIL.Image.BILINEAR)
#         img = transforms.functional.to_tensor(img).to(self.device)
#         img.sub_(self.mean[:, None, None]).div_(self.std[:, None, None])

#         return img[None, ...]

#     def process(self, *xs, meta=None):
#         assert(len(xs) == 1)
#         assert(type(xs[0]) == np.ndarray)
#         assert(len(xs[0].shape) == 3)

#         img = self.preprocess(xs[0])

#         if self.debug and self.verbose:
#             print("Preprocessed img:", img.shape, img.dtype)
#             print("Original:", xs[0].shape, xs[0].dtype)

#         cmap, paf = self.model_trt(img)
#         cmap, paf = cmap.detach().cpu(), paf.detach().cpu()
#         counts, objects, peaks = self.parse_objects(cmap, paf)#, cmap_threshold=0.15, link_threshold=0.15)

#         if self.debug:
#             print("Pose detection %d:" % self.processed, int(counts), "poses")

#         if self.draw:
#             out_img = xs[0].copy()
#             self.draw_objects(out_img, counts, objects, peaks)
#             # out_img = out_img[:, ::-1, :]  # flip horizontally for mirror effect
#         else:
#             out_img = None

#         counts, objects, peaks = int(counts.numpy()), objects.numpy(), peaks.numpy()

#         return [out_img], {"model": self.model,
#                             "size": self.size,
#                             "counts": counts,
#                             "objects": objects,
#                             "peaks": peaks,
#                             "detections_id": self.processed}


if __name__ == '__main__':
    # test_img = cv2.imread(PoseDetector.weights_dir + "test_image.png")[:, :, ::-1]  # BGR to RGB
    test_img = cv2.imread("test_image.png")[:, :, ::-1]  # BGR to RGB
    test_meta = {"resolution": test_img.shape[:2], "pixel_format": "rgb8"}

    od = ObjectDetector(name="Objects_Detector", draw=True, cuda_out=False, zero_copy=True, debug=True, verbose=True)
    od.init()

    obj = od.process(test_img, meta=test_meta)
    print("\nResults:\n", obj)

    od.finish()

    # pd = PoseDetector(name="Pose_Detector", draw=True, debug=True, verbose=True)
    # pd.init()

    # pose = pd.process(test_img)
    # print("\npose:\n", pose)

    cv2.imshow('Detected Objects', obj[0][0][:, :, ::-1])  # RGB to BGR
    # cv2.imshow('Detected Poses', pose[0][0][:, :, ::-1])  # RGB to BGR

    while True:
        if cv2.waitKey(1) == 27:
            break  # esc to quit
        time.sleep(0.001)
    cv2.destroyAllWindows()
