import reip
from reip.models import posenet


class Posenet(reip.Block):
    def init(self):
        self.model = posenet.Posenet()

    def process(self, frame, meta):
        kps = self.model.predict(frame)
        return [self.model.draw(frame, kps), kps], {}
