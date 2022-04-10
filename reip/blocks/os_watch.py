'''File System Events

Watchdog API Reference: https://pythonhosted.org/watchdog/api.html

.. note::

    from experience, I've found file watchers can be a bit unreliable - (potentially
    due to my own misuse !).

    Additionally, many times (for example file upload) watching file 
    events may not actually be what you want, and you may be better off
    polling file lists using glob as that will reduce the number of missed files
    and is resilient to reboots.

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

    def on_any_event(self, event):
        try:
            if not self.event_types or event.event_type in self.event_types:
                self.q.put(event)
        except Exception as e:
            self.q.put(e)

class Watch(reip.Block):
    '''A Generic File Watcher'''
    _q = _event_handler = _watch = None
    event_types = None
    def __init__(self, *patterns, path='./', event_types=None, recursive=False, **kw):
        self.patterns = list(patterns or ('*',))
        self.path = path
        self.event_types = event_types or self.event_types
        self.recursive = recursive
        super().__init__(n_inputs=0, **kw)

    _Handler = _WatchBlockHandler

    # define a global observer - is this right?

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
        # a queue is used to gather all events emitted
        self._q = queue.Queue()
        # create watchdog stuff
        self._event_handler = self._Handler(
            self._q, self.event_types, patterns=self.patterns)
        self._watch = self.observer.schedule(
            self._event_handler, self.path, recursive=self.recursive)

    def process(self, meta):
        if not self._q.empty():
            e = self._q.get()
            if isinstance(e, Exception):
                raise e
            return self._output_event(e, meta)

    def _output_event(self, event, meta):
        return [event.src_path], {'event_type': event.event_type}

    def finish(self):
        # remove handler
        self.observer.remove_handler_for_watch(self._event_handler, self._watch)
        if self.observer.is_alive() and not any(self.observer._handlers.values()):
            # if there are no more handlers, shutdown the observer
            self.observer.unschedule_all()
            self.observer.stop()
            self.observer.join()
            self.observer = None


class Created(Watch):
    '''Outputs any created files.'''
    event_types = ('created',)

class Modified(Watch):
    '''Outputs any modified files.'''
    event_types = ('modified',)

class Deleted(Watch):
    '''Outputs any deleted files.'''
    event_types = ('deleted',)

class Moved(Watch):
    '''Outputs any moved files.'''
    event_types = ('moved',)
    def _output_event(self, event, meta):
        return [event.src_path, event.dest_path], {'event_type': event.event_type}


# Watch.Created = Created
# Watch.Modified = Modified
# Watch.Deleted = Deleted
# Watch.Moved = Moved
