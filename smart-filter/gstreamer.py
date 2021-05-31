import time
import numpy
import threading
import gi
gi.require_version('Gst', '1.0')
gi.require_version("GstApp", "1.0")
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstApp, GLib, GObject, GstVideo

class GStreamer:
    _inited = False
    # _main_loop = None
    # _main_thread = None

    @classmethod
    def init(cls):
        GObject.threads_init()
        Gst.init(None)
        # cls._main_loop = GLib.MainLoop.new(None, False)
        cls._inited = True

    @classmethod
    def unpack_sample(cls, sample, debug=False):
        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        sz, w, h, ch, fmt = buf.get_size(), caps.get_value('width'), caps.get_value('height'), caps.get_value('channel'), caps.get_value('format')
        if debug:
            print("\tSize:", sz, (w, h, ch, fmt), "Timestamp:", buf.pts / 1e+9)

        return numpy.ndarray((sz), buffer=buf.extract_dup(0, sz), dtype=numpy.uint8), buf.pts, (w, h, ch, fmt)

    def __init__(self, debug=True):
        if not self._inited:
            raise RuntimeError("Run global init GStreamer.init() first!")

        self._pipeline = Gst.Pipeline()
        self._elements = {}
        self._creation_order = []
        self._included = []
        self._debug = debug
        self._bus = None
        self._bus_thread = None
        self._terminate = False
        self._exception = None
        self._done = False
        self.multifilesink_index = 0

    def add(self, name, title = None):
        title = title or name
        if title in self._creation_order:
            raise ValueError("Element already exists:" + title)

        new_element = Gst.ElementFactory.make(name)
        if not new_element:
            raise RuntimeError("Could not create element: " + name)

        self._elements[title] = new_element
        self.__dict__[title] = new_element
        self._creation_order.append(title)

        return new_element

    def __getitem__(self, e):
        return self._elements[e]

    def from_string(self, s):
        return Gst.caps_from_string(s)

    def link(self, elements=None):
        elements = elements or self._creation_order
        if len(elements) == 0:
            raise ValueError("Nothing to link")

        for e in elements:
            if e not in self._included:
                self._pipeline.add(self._elements[e])
                self._included.append(e)
            else:
                if self._debug:
                    print("Element was already included:", e)

        for i in range(len(elements)-1):
            if not self._elements[elements[i]].link(self._elements[elements[i+1]]):
                raise RuntimeError("Could not link element: " + elements[i])

        return self

    def check_ready(self, required=False):
        state = self._pipeline.get_state(1e+5).state
        # Gst.State.READY is little different from Gst.State.NULL, so
        # we judge whether pipeline is ready by Gst.State.PAUSED or Gst.State.PAYLING
        if state == Gst.State.PLAYING or state == Gst.State.PAUSED:
            return True
        if required:
            raise RuntimeError("Pipeline not ready")
        return False

    def check_running(self, required=False):
        if self._pipeline.get_state(1e+5).state == Gst.State.PLAYING:
            return True
        if required:
            raise RuntimeError("Pipeline not running")
        return False

    def start(self, auto_play=True):
        if self.check_ready() is True:
            print("\tPipeline was ready")
            return 

        self._done = False
        self._error = False
        self._exception = None
        self._terminate = False

        if self._pipeline.set_state(Gst.State.PLAYING if auto_play else Gst.State.PAUSED) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Could not start pipeline")

        self._bus = self._pipeline.get_bus()
        self._bus_thread = threading.Thread(target=self._bus_loop, daemon=True)
        self._bus_thread.start()

        if self._debug:
            print("\n\tStarted pipeline")

    def pause(self):
        self.check_ready(required=True)

        if self.check_running() is False:
            print("\tPipeline was paused")
            return 

        if self._pipeline.set_state(Gst.State.PAUSED) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Could not pause pipeline")

    def resume(self):
        self.check_ready(required=True)

        if self.check_running() is True:
            print("\tPipeline was running")
            return 

        if self._pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Could not resume pipeline")

    def eos(self):
        self._pipeline.send_event(Gst.Event.new_eos())
        if self._debug:
            print("\n\tInserted EOS")

    # timeout = -1 - no timeout
    def stop(self, wait=True, timeout=0.1):
        self.check_ready(required = not self._done)

        if not self._done:
            self.eos()

        if wait:
            t0 = time.time()
            while not self._done:
                if time.time() - t0 > timeout and timeout >= 0:
                    print("\n\tWait timeout")
                    break
                time.sleep(1e-3)

        self._terminate = True
        self._bus_thread.join()
        self._bus_thread = None
        self._bus = None

    def _bus_loop(self):
        if self._debug:
            print("\n\tEnter bus loop")

        while not self._terminate:
            try:
                self.process_messages()
                time.sleep(1e-3)
            except KeyboardInterrupt:
                if self._debug:
                    print("\tKeyboardInterrupt in bus loop - sending eos")
                self.eos()
            except Exception as e:
                self._exception = e
                self._error = True
                self._done = True
                break

        if self._debug:
            print("\n\tExit bus loop")

    def process_messages(self, all=True):
        if self._bus:
            while self._bus.have_pending():
                message = self._bus.pop()
                if message:
                    t = message.type
                    if t == Gst.MessageType.ERROR:
                        err, debug = message.parse_error()
                        raise RuntimeError("Error received from element %s: %s\nDebugging information:%s" % (message.src.get_name(), err, debug))
                    elif t == Gst.MessageType.EOS:
                        if self._debug:
                            print("\n\tEnd-Of-Stream reached")
                        self._pipeline.set_state(Gst.State.NULL)
                        time.sleep(1e-3)  # Bus stops receiving messages after EOS for some reason
                        self._done = True
                    elif t == Gst.MessageType.STATE_CHANGED:
                        if isinstance(message.src, Gst.Pipeline):
                            old_state, new_state, pending_state = message.parse_state_changed()
                            if self._debug:
                                print("\tPipeline state changed from %s to %s" % (old_state.value_nick, new_state.value_nick))
                            # Bus stops receiving messages after EOS
                            # if new_state == Gst.State.NULL:
                            #     print("\tDone")
                            #     self._done = True
                    elif t == Gst.MessageType.ELEMENT:
                        el_name = message.src.get_name()
                        # if self._debug:
                        #     print("\tMessage from %s:" % el_name, message)
                        if el_name == "multifilesink0":
                            self.multifilesink_index = message.src.get_property("index")
                            if self._debug:
                                print("\n\tNew file index:", self.multifilesink_index)
                            # print("\t", message.src.get_property("next-file"),
                            #     message.src.get_property("max-file-size"), message.src.get_property("max-file-duration"))
                    else:
                        print("\tUnknown message:", message.type, message.src.get_name())
                else:
                    raise ValueError("Empty message")
                if not all:
                    break
        else:
            ValueError("Invalid bus")

    def run(self, in_thread=False):
        self.start()

        while True:
            try:
                time.sleep(0.001)
            except KeyboardInterrupt:
                if self._debug:
                    print("\tKeyboardInterrupt in run loop - breaking the loop")
                break
            if self._done:
                break

        if self._error:
            raise RuntimeError("Bus thread failed") from self._exception

        self.stop()

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


if __name__ == "__main__":
    GStreamer.init()

    g = GStreamer()

    g.add("videotestsrc", "src")
    g.add("xvimagesink", "sink")

    g.link()

    with g:
        time.sleep(0.75)
        g.pause()
        time.sleep(0.5)
        g.resume()
        time.sleep(0.75)

    time.sleep(0.5)
    g.run()
