import glob
import queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import reip

class _WatchBlockHandler(FileSystemEventHandler):
    def __init__(self, q, event_types, *a, **kw):
        self.q = q
        self.event_types = event_types
        super().__init__(*a, **kw)



class Watch(reip.Block):
    _q = _observer = _event_handler = None
    event_types = None
    def __init__(self, path, event_types=None, **kw):
        self.paths = glob.glob(path)
        assert self.paths, f"{path!r} didn't match any files."
        self.event_types = event_types or self.event_types
        super().__init__(n_source=0, **kw)

    class _Handler(_WatchBlockHandler):
        def on_any_event(self, event):
            if not self.event_types or event.event_type in self.event_types:
                self.q.put(event)

    def init(self):
        self._q = queue.Queue()
        self._event_handler = self._Handler(self._q, self.event_types)
        self._observer = Observer()
        for path in self.paths:
            self._observer.schedule(self._event_handler, path, recursive=True)
        self._observer.start()
        print('Watching:', self.paths)

    def process(self, meta):
        if not self._q.empty():
            event = self._q.get()
            return [event.src_path], {'event_type': event.event_type}

    def finish(self):
        self._observer.stop()
        self._observer.join()


class Created(Watch):
    event_types = ('created',)

class Modified(Watch):
    event_types = ('modified',)

class Deleted(Watch):
    event_types = ('deleted',)

class Moved(Watch):
    event_types = ('moved',)


# Watch.Created = Created
# Watch.Modified = Modified
# Watch.Deleted = Deleted
# Watch.Moved = Moved
