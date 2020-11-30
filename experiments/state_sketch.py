from state import *
import remoteobj
# import reip


class BlockDataModel:
    def get(self):
        return [], {}

    def put(self, output):
        pass

    def _reconfigure(self, update):
        pass


class BlockState(BlockDataModel, StateModel):
    def __init__(self):
        self._except = remoteobj.LocalExcept()

    _thread = None
    @State
    def spawned(self):
        if self._thread is not None:
            pass
        self._thread = remoteobj.util.thread(self.lifecycle)

    @State
    def running(self):
        while self.running:
            data, meta = self.get()
            output = self.on_buffer(*data, meta=meta)
            self.put(output)

    @State
    def paused(self):
        while self.paused:
            self.on_idle()

    def lifecycle(self):
        try:
            self.on_spawn()
            while True:
                self.state()
        finally:
            self.on_join()

    @State
    def updating(self, update):
        state = self.state
        self.idle.set()
        self._reconfigure(update)
        state.set()

    spawn = State.null.to(spawned)
    resume = State.any(running, paused).to(running)
    pause = running.to(paused)
    # update = reip.state.any.to(paused)
    join = reip.state.any.to(State.null)

    def on_spawn(self):
        pass

    def on_running(self):
        pass

    def on_update(self, old, new):
        pass

    def on_buffer(self, *xs, meta):
        return [], {}

    def on_idle(self):
        pass

    def on_join(self):
        pass
