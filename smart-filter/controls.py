import json
import time
import reip
import usb.core
import usb.util
import threading
import queue
import numpy as np
from dummies import BlackHole
import multiprocessing as mp
import multiprocessing.queues
from ctypes import *
import re


class ConsoleInput(reip.Block):
    debug = False  # Debug output

    def __init__(self, **kw):
        super().__init__(n_inputs=0, **kw)

    def init(self):
        self.last_input = None
        if self.debug:
            print('Enter Commands:')

    def process(self, *xs, meta=None):
        assert(len(xs) == 0)

        new_input = input()

        if new_input == "" and self.last_input is not None:
            new_input = self.last_input
        else:
            self.last_input = new_input

        return [new_input], {"input": new_input, "timestamp": time.time()}


class BulkUSB(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    usb_dev = None  # USB Bulk Device Class handle
    max_usb_stats = 60000  # Max number of usb stats to accumulate before printing (about a minute)
    idVendor = 0x1cbe
    idProduct = 0x0003

    flags = mp.Value(c_uint, 0, lock=False)
    timestamp = mp.Value(c_uint, 0, lock=False)
    values = {}  # To be replaced by shared dict upon init

    def __init__(self, **kw):
        self.manager = mp.Manager()
        self.values = self.manager.dict()
        self.write_queue = mp.SimpleQueue()

        super().__init__(n_inputs=0, **kw)

    def init(self):
        self.usb_dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        assert(self.usb_dev is not None)
        self._delay = 1e-5

        self.usb_dev.reset()
        self.usb_dev.set_configuration(1)
        usb.util.claim_interface(self.usb_dev, 0)

        # 7-bit and 8-bit C1 ANSI sequences
        self.ansi_escape_8bit = re.compile(br'''
            (?: # either 7-bit C1, two bytes, ESC Fe (omitting CSI)
                \x1B
                [@-Z\\-_]
            |   # or a single 8-bit byte Fe (omitting CSI)
                [\x80-\x9A\x9C-\x9F]
            |   # or CSI + control codes
                (?: # 7-bit CSI, ESC [ 
                    \x1B\[
                |   # 8-bit CSI, 9B
                    \x9B
                )
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
        # result = ansi_escape_8bit.sub(b'', somebytesvalue)

        self.reset_usb_stats()

    def send(self, cmd):
        self.write_queue.put(cmd)
        if len(cmd) > 0 and cmd[0] == "!":
            cmd = cmd[1:]
        self.values[cmd] = None

    def receive(self, cmd, wait=False, timeout=0.1):
        t = time.time()
        while wait:
            if self.values[cmd] is not None:
                break
            if time.time() - t > timeout:
                break
            time.sleep(1e-4)

        return self.values[cmd]

    def process(self, *xs, meta=None):
        self.loop()
        return None

    # def finish(self):
    #     pass

    def reset_usb_stats(self):
        self.write_times, self.read_times = [], []
        self.write_errors, self.read_errors = 0, 0
        self.loops, self.tl = 0, time.time()

    def print_usb_stats(self):
        print("Avg Write: %.3f ms. Avg Read: %.3f ms. %d loops in %.3f sec. Write/Read Errors: %d/%d" %
                    (1000 * np.average(self.write_times), 1000 * np.average(self.read_times),
                    self.loops, time.time() - self.tl, self.write_errors, self.read_errors))

    def loop(self):
        # Write
        try:
            if not self.write_queue.empty():
                data = bytes(self.write_queue.get()[:32].encode("ascii"))
                if data.decode("ascii") == "usb_stats":
                    self.print_usb_stats()
                    data = bytes([0])
                elif self.debug and self.verbose:
                    print("Sending:", data.decode("ascii"))
            else:
                data = bytes([0])
            tw = time.time()
            wrote = self.usb_dev.write(0x01, data, 1)
            self.write_times.append(time.time() - tw)
            if wrote != len(data):
                print("USB: Wrote %d out of %d" % (wrote, len(data)))
        except usb.core.USBError as e:
            self.write_errors += 1
            if e.errno != 110:  # timeout
                raise e
        # Read
        try:
            tr = time.time()
            data = self.usb_dev.read(0x81, 64, 1)
            self.read_times.append(time.time() - tr)
            read = len(data)
        except usb.core.USBError as e:
            self.read_errors += 1
            data = None
            if e.errno != 110:  # timeout
                raise e
        self.loops += 1

        self.parse(data, read)

        if self.loops == self.max_usb_stats:
            if self.debug:
                self.print_usb_stats()
            self.reset_usb_stats()

    def parse(self, data, read):
        if data is not None and read > 0:
            data = bytes(data)
            if data[0] == 0 and read == 9:
                # Default packet contains current flags and timestamp
                new_flags = int.from_bytes(data[1:5], byteorder='little', signed=False)
                new_timestamp = int.from_bytes(data[5:9], byteorder='little', signed=False)

                if new_flags != self.flags.value and self.debug and self.verbose:
                    print("USB Flags: 0x%x, Timestamp: %d" % (new_flags, new_timestamp))

                self.flags.value, self.timestamp.value = new_flags, new_timestamp
            else:
                # Map value reads to self.values dict or print otherwise
                res = data.decode("ascii")
                res = res[:-1] if res[len(res)-1] == "\n" else res

                printed = False
                if self.debug and self.verbose:
                    print("Received:", res)
                    printed = True

                if ":" in res:
                    res_e = self.ansi_escape_8bit.sub(b'', data).decode("ascii").strip()
                    # print(res_e)

                    p = res_e.find(":")
                    cmd, value = res_e[:p], res_e[p+1:].strip()
                    self.values[cmd] = value

                elif not printed and self.debug:
                    print(res)

        elif self.debug and self.verbose:
            print("USB: Empty read")


class Controller(reip.Block):
    debug = False  # Debug output
    usb_device = None  # Device to command
    selector = None  # Remote selector to control
    t0 = time.time()

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        assert(type(xs[0]) is str)
        cmd = xs[0].strip()

        args = cmd.split()
        if len(args) > 1 and args[0] == "select" and self.selector is not None:
            self.selector.value = int(args[1])
            return None

        if self.usb_device is not None:
            t0 = time.time()
            self.usb_device.send(cmd)
            if self.debug:
                print("Commanded: %s at %f.3 sec (%d)" %(cmd, time.time() - self.t0, self.usb_device.timestamp.value))
            if len(cmd) > 0 and cmd[0] == "!":
                cmd = cmd[1:]
                cmd = cmd.split()
                if len(cmd) > 0:
                    cmd = cmd[0]
                if self.debug:
                    print("Awaiting %s..." % cmd)
                ret = self.usb_device.receive(cmd, wait=True)
                print("Returned:", ret, "after", time.time()-t0, "sec")

        return None


class Follower(reip.Block):
    debug = False  # Debug output
    verbose = False  # Detailed debug output
    usb_device = None  # USD device to send commands to
    override = False  # Override master radio flags if True
    detector = None  # Remote object detector to control
    center_x = None  # Current average position of detected people
    zoom_cam = 0  # Index of zoomed camera
    wide_cam = 0  # Index of wide-angle camera
    hist_len = 3  # Detection hisoty length

    def init(self):
        assert(self.usb_device is not None)
        assert(self.detector is not None)

        self.usb_device.send("m.ena.set")
        self.usb_device.send("m.target 2")
        self.usb_device.send("m.home")
        self.usb_device.send("override %d" % (1 if self.override else 0))
        self.usb_device.send("m.follow 1")

        self.prev_det = {self.zoom_cam: [None] * self.hist_len, self.wide_cam: [None] * self.hist_len}

    def process_detections(self, meta):
        detections = meta["objects"]
        self.center_x = None

        if len(detections) > 0:
            people = []
            if self.debug and self.verbose:
                print("Detections:")

            for det in detections:
                label = meta["class_labels"][det["ClassID"]]

                if self.debug and self.verbose:
                    print("\t", label, det)

                if label == "person":
                    people.append((det["Center"], det["Confidence"]))

            if len(people) > 0:
                self.center_x = int(np.mean([p[0][0] * p[1] for p in people]))

                if self.debug:
                    print("Detected people (center_x = %d):" % self.center_x, people)

    def process(self, *xs, meta=None):
        assert(len(xs) == 1)
        assert(xs[0] is None)

        # if self.usb_device is None or self.detector is None:
        #     if self.debug:
        #         print("Follower: usb_device and/or detector object(s) not specified")
        #     return None

        self.process_detections(meta)
        # cur_sel = self.detector.current_sel.value
        cur_sel = meta["source_sel"]
        width = meta["source_meta"]["resolution"][1]

        # Rolling history to combat outliers / missing detections
        self.prev_det[cur_sel].append(self.center_x)
        self.prev_det[cur_sel] = self.prev_det[cur_sel][1:]

        self.usb_device.send("!m.pos")
        cur_pos = self.usb_device.receive("m.pos", wait=True)

        if cur_pos is None:  # timeout
            if self.debug and self.verbose:
                print("Current pos:", None)
            return None

        cur_pos = int(cur_pos)
        if self.debug and self.verbose:
            print("Current pos:", cur_pos)

        if cur_sel == self.zoom_cam:
            if not any(self.prev_det[cur_sel]):
                self.detector.target_sel.value = self.wide_cam
                self.prev_det[self.wide_cam] = [None] * self.hist_len
            else:
                mean_x = np.mean([det for det in self.prev_det[cur_sel] if det is not None])

                if mean_x < width / 3:
                    self.usb_device.send("m.target %d" % (max(0, cur_pos + 1)))
                elif mean_x > width * 2/3:
                    self.usb_device.send("m.target %d" % (max(0, cur_pos - 1)))

        elif any(self.prev_det[cur_sel]):
            mean_x = np.mean([det for det in self.prev_det[cur_sel] if det is not None])
            new_pos = int(110 * mean_x/width)

            if abs(new_pos - cur_pos) > 2:
                self.usb_device.send("m.target %d" % new_pos)
                if self.debug:
                    print("New target:", new_pos)

            self.prev_det[self.zoom_cam] = [None] * self.hist_len
            self.detector.target_sel.value = self.zoom_cam
 
        return None


def test_example():
    cin = ConsoleInput(name="Console_Input", debug=True)

    with reip.Task("USB"):
        bulk_usb = BulkUSB(name="Bulk_USB", debug=True, verbose=True)

    ctl = Controller(name="Manual_Controller", usb_device=bulk_usb, debug=True)
    cin.to(ctl)

    reip.default_graph().run(duration=None, stats_interval=None)


if __name__ == '__main__':
    test_example()
