'''

Watchdog API Reference: https://pythonhosted.org/watchdog/api.html

'''
import queue
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import reip
from reip.util import text

class _WatchBlockHandler(PatternMatchingEventHandler):
    def __init__(self, q, event_types, *a, **kw):
        self.q = q
        self.event_types = event_types
        super().__init__(*a, **kw)


class Watch(reip.Block):
    _q = _event_handler = _watch = None
    event_types = None
    def __init__(self, *patterns, relative='./', event_types=None, **kw):
        self.patterns = list(patterns or ('*',))
        self.relative = relative
        self.event_types = event_types or self.event_types
        super().__init__(n_source=0, **kw)

    class _Handler(_WatchBlockHandler):
        def on_any_event(self, event):
            try:
                if not self.event_types or event.event_type in self.event_types:
                    self.q.put(event)
            except Exception as e:
                print(text.yellow(text.l_(type(e), e)))

    _observer = None
    @property
    def observer(self):
        if Watch._observer is None:
            Watch._observer = Observer()
            Watch._observer.start()
        return Watch._observer

    @observer.setter
    def observer(self, value):
        Watch._observer = value

    def init(self):
        self._q = queue.Queue()
        self._event_handler = self._Handler(
            self._q, self.event_types, patterns=self.patterns)
        self._watch = self.observer.schedule(
            self._event_handler, self.relative, recursive=True)

    def process(self, meta):
        if not self._q.empty():
            return self._output_event(self._q.get(), meta)

    def _output_event(self, event, meta):
        return [event.src_path], {'event_type': event.event_type}

    def finish(self):
        self.observer.remove_handler_for_watch(self._event_handler, self._watch)
        if self.observer.is_alive() and not any(self.observer._handlers.values()):
            self.observer.unschedule_all()
            self.observer.stop()
            self.observer.join()
            self.observer = None


class Created(Watch):
    event_types = ('created',)

class Modified(Watch):
    event_types = ('modified',)

class Deleted(Watch):
    event_types = ('deleted',)

class Moved(Watch):
    event_types = ('moved',)
    def _output_event(self, event, meta):
        return [event.src_path, event.dest_path], {'event_type': event.event_type}


# Watch.Created = Created
# Watch.Modified = Modified
# Watch.Deleted = Deleted
# Watch.Moved = Moved
