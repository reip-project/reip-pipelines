import soundfile as sf
from ..block import Block


class AudioWriter(Block):
    '''Writes audio data to file.'''
    output_key = 'file'
    def __init__(self, filename, **kw):
        self.filename = filename
        super().__init__(**kw)

    def transform(self, data, sr, **kw):
        filename = self.filename
        sf.write(filename, data, sr)
        return filename
