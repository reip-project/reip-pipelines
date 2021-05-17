import sys
import cv2
import time
from gstreamer import *

device = 0
width, height, fps = 2592, 1944, 15
# width, height, fps = 1920, 1080, 30
tot_samples, tot_overrun, t0 = 0, 0, time.time()

def new_sample(sink, data):
    global tot_samples, t0
    # sink.emit("try-pull-sample", 1e+6)
    tot_samples += 1
    print("Samples_0:", tot_samples, time.time() - t0)
    return Gst.FlowReturn.OK

def overrun(queue, data):
    global tot_overrun, t0
    tot_overrun += 1
    print("\nOverrun_0:", tot_overrun, time.time() - t0)
    return Gst.FlowReturn.OK

if __name__ == "__main__":
    if len(sys.argv) > 1:
        device = int(sys.argv[1])
    GStreamer.init()

    g = GStreamer()

    g.add("v4l2src", "src").set_property("device", "/dev/video%d" % device)
    g.add("capsfilter", "caps").set_property("caps", g.from_string("image/jpeg,width=%d,height=%d,framerate=%d/1" % (width, height, fps)))
    q = g.add("queue", "q")
    g.add("jpegdec", "decode")
    s = g.add("appsink", "sink")

    # g.src.set_property("num-buffers", 150)
    # print("\n\tname", g.src.get_property("device-name"))

    q.set_property("max-size-buffers", 5)
    q.set_property("leaky", "no")
    q.connect("overrun", overrun, q)

    s.set_property("emit-signals", True)  # eos is not processed otherwise
    s.set_property("max-buffers", 10)  # protection from memory overflow
    s.set_property("drop", True)  # if python is too slow with pulling the samples
    s.connect("new-sample", new_sample, s)

    g.link()

    g.start()

    count, title = 0, "img%d" % device
    cv2.namedWindow(title)

    sl = 0.001
    while True:
        try:
            sample = g.sink.try_pull_sample(1e+6)

            if sample:
                count += 1
                img, ts, fmt = GStreamer.unpack_sample(sample, debug=True)
                print("Pulled_0:", count, ts / 1.e+9, "at", time.time() - t0)

                if count % 3 == 0 and True:
                    w, h, ch, fmt = fmt
                    assert(fmt == "I420")
                    cv2.imshow(title, img[: img.shape[0] * 2 // 3].reshape((h, w)))

                if cv2.waitKey(1) == 27:
                    g.eos()  # esc to quit
                    sl = 0
            time.sleep(sl)
        except KeyboardInterrupt:
            print("KeyboardInterrupt - breaking the loop")
            g.eos()
            sl = 0
        if g._done:
            break

    if g._error:
        raise RuntimeError("Bus thread failed") from g._exception

    g.stop(timeout=1)

    print("tot_samples", tot_samples, "tot_overrun", tot_overrun)
    cv2.destroyAllWindows()
