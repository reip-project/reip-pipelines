import time
from collections import OrderedDict
import warnings
import numpy as np
import gi
gi.require_version('Gst', '1.0')
gi.require_version("GstApp", "1.0")
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstApp, GLib, GObject, GstVideo


class GStream:
    _inited = False

    @classmethod
    def initialize(cls):
        GObject.threads_init()
        Gst.init(None)
        cls._inited = True

    _bus = None
    done = False
    _debug = True
    _state_timeout = 1e+5
    def __init__(self, auto_play=True, pipeline=None):
        if not self._inited:
            warnings.warn('GStreamer is uninitialized. Initializing automatically.')
            self.initialize()

        self._pipeline = pipeline or Gst.Pipeline()
        self._elements = OrderedDict()
        self.auto_play = auto_play

    def __len__(self):
        return len(self._elements)

    def __getattr__(self, key):
        # access elements by attribute
        if key not in self._elements:
            raise AttributeError(key)
        return self._elements[key]

    def __getitem__(self, key):
        return self._elements[key]

    # Graph Definition

    def add(self, name, title=None, **kw):
        '''Add an element.'''
        element = (
            name if isinstance(name, Gst.Element) else
            Gst.ElementFactory.make(name, title))

        if element is None:
            raise RuntimeError("Could not create element: " + name)
        title = title or element.name
        if title in self._elements:
            raise ValueError("Element already exists:" + title)

        self._elements[title or element.name] = element
        for k, v in kw.items():
            element.set_property(k.replace('_', '-'), v)
            # Gst.caps_from_string(v) if isinstance(v, str) else v
        return element

    def link(self, *elements, start=None, end=None):
        '''Connect consecutive elements together.'''
        # select starting element
        if not elements:
            elements = tuple(self._elements)
            elements = elements[
                _get_element_index(elements, start):
                _get_element_index(elements, end)]

        # add elements to gst object
        for e in elements:
            self._pipeline.add(self._elements[e])

        # connect elements together
        for el1, el2 in zip(elements, elements[1:]):
            if not self._elements[el1].link(self._elements[el2]):
                raise RuntimeError("Could not link element: " + el1)
        return self

    # Control Flow

    @property
    def ready(self):
        # Gst.State.READY is little different from Gst.State.NULL, so
        # we judge whether pipeline is ready by Gst.State.PAUSED or Gst.State.PAYLING
        return self._check_state(Gst.State.PLAYING, Gst.State.PAUSED)

    @property
    def running(self):
        return self._check_state(Gst.State.PLAYING)

    def _check_state(self, *states):
        return self._gs.get_state(self._state_timeout).state in states

    def toggle(self, running, msg1='resume', msg2='pause'):
        state, msg = (Gst.State.PLAYING, msg1) if running else (Gst.State.PAUSED, msg2)
        if self.running != running:
            if self._pipeline.set_state(state) == Gst.StateChangeReturn.FAILURE:
                if msg:
                    raise RuntimeError("Could not {} pipeline".format(msg))
        return True

    def start(self, running=True):
        self.done = False
        self._bus = self._pipeline.get_bus()
        self.toggle(running, 'start')

    def pause(self):
        return self.toggle(False)

    def resume(self):
        return self.toggle(True)

    def end(self):
        self._pipeline.send_event(Gst.Event.new_eos())


    def check_messages(self, all_pending=True):
        if not self._bus:
            raise ValueError("Invalid bus")

        while self._bus.have_pending():
            message = self._bus.pop()
            if not message:
                raise ValueError("Empty message")

            t = message.type
            if t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                raise RuntimeError((
                    "Error received from element {}: {}\n"
                    "Debugging information:{}").format(
                        message.src.get_name(), err, debug))

            elif t == Gst.MessageType.EOS:
                if self._debug:
                    print("\n\tEnd-Of-Stream reached\n")
                self._pipeline.set_state(Gst.State.NULL)
                time.sleep(1e-3)  # Bus stops receiving messages after EOS for some reason
                self.done = True

            elif t == Gst.MessageType.STATE_CHANGED:
                if isinstance(message.src, Gst.Pipeline):
                    old, new, pending = message.parse_state_changed()
                    if self._debug:
                        print("\tPipeline state changed from {} to {}".format(
                            old.value_nick, new.value_nick))
            else:
                print("\tUnknown message:", message.type)
            if not all_pending:
                break



def _get_element_index(elements, search):
    if search is None or isinstance(search, int):
        return search
    try:
        return next(
            len(elements) - i
            for i, el in enumerate(tuple(elements)[::-1], 1)
            if el == search or elements[el] is search)
    except StopIteration:
        raise ValueError('No element matching {}'.format(search))


def cap(x):
    return Gst.caps_from_string(x)


def unpack_sample(sample, fmt='I420', debug=False):
    buf = sample.get_buffer()
    caps = sample.get_caps().get_structure(0)
    sz, imfmt = buf.get_size(), caps.get_value('format')
    assert not fmt or imfmt == fmt

    X = np.ndarray(
        sz, buffer=buf.extract_dup(0, sz), dtype=np.uint8).reshape((
            caps.get_value('width'), caps.get_value('height'),
            caps.get_value('channel')))
    ts = buf.pts

    if debug:
        print("\tSize:", sz, X.shape, imfmt, "Timestamp:", buf.pts / 1e+9)
    return X, ts
