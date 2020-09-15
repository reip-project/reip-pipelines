import sys
import cv2
import time
from gstreamer import *

device = 0
width, height, fps = 2592, 1944, 15
# width, height, fps = 1920, 1080, 30
tot_samples, tot_overrun, t0 = [0, 0], [0, 0], time.time()
tot_pulled = [0, 0]

def new_sample(sink, id):
    global tot_samples, t0
    # sink.emit("try-pull-sample", 1e+6)
    tot_samples[id] += 1
    print("Samples_%d:" % id, tot_samples[id], time.time() - t0)
    return Gst.FlowReturn.OK

def overrun(queue, id):
    global tot_overrun, t0
    tot_overrun[id] += 1
    print("\nOverrun_%d:" % id, tot_overrun[id], time.time() - t0)
    return Gst.FlowReturn.OK

def add_camera(g, id):
    i = str(id)
    l = len(g._creation_order)
    g.add("v4l2src", "src" + i).set_property("device", "/dev/video%d" % id)
    g.add("capsfilter", "caps" + i).set_property("caps", g.from_string("image/jpeg,width=%d,height=%d,framerate=%d/1" % (width, height, fps)))
    q = g.add("queue", "q" + i)
    g.add("jpegdec", "decode" + i)
    s = g.add("appsink", "sink" + i)

    q.set_property("max-size-buffers", fps)  # prevents lost frames at a startup
    q.set_property("leaky", "downstream")
    q.connect("overrun", overrun, id)

    s.set_property("emit-signals", True)  # eos is not processed otherwise
    s.set_property("max-buffers", fps + 5)  # protection from memory overflow
    s.set_property("drop", False)  # if python is too slow with pulling the samples
    s.connect("new-sample", new_sample, id)

    g.link(g._creation_order[l:])


def try_pull_camera(g, id):
    sample = g["sink"+str(id)].try_pull_sample(1e+6)

    if sample:
        tot_pulled[id] += 1
        img, ts, fmt = GStreamer.unpack_sample(sample, debug=False)
        print("Pulled_%d:"%id, tot_pulled[id], ts / 1.e+9, "at", time.time() - t0)

        # if count % 3 == 0 and False:
        #     w, h, ch, fmt = fmt
        #     assert(fmt == "I420")
        #     cv2.imshow(title, img[: img.shape[0] * 2 // 3].reshape((h, w)))

        # if cv2.waitKey(1) == 27:
        #     g.eos()  # esc to quit


if __name__ == "__main__":
    if len(sys.argv) > 1:
        device = int(sys.argv[1])
    GStreamer.init()

    g = GStreamer()

    add_camera(g, 0)
    add_camera(g, 1)

    g.start()

    while True:
        try:
            try_pull_camera(g, 0)
            try_pull_camera(g, 1)
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt - breaking the loop")
            g.eos()
        if g._done:
            break

    if g._error:
        raise RuntimeError("Bus thread failed") from g._exception

    g.stop(timeout=1)

    print("tot_samples", tot_samples, "tot_overrun", tot_overrun, "tot_pulled", tot_pulled)
