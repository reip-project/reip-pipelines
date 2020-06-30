'''OS Monitoring triggers


'''

import time
from lazyimport import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .block import Block



class watch(Block):
    def __init__(self, path, **kw):
        self.path = path
        super().__init__(**kw)

    def transform(self, X, meta):
        event_handler = FileSystemEventHandler()
        observer = Observer()
        observer.schedule(event_handler, self.path, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


class create(watch):
    pass


class modify(watch):
    pass


class delete(watch):
    pass


watch.create = create
watch.modify = modify
watch.delete = delete
