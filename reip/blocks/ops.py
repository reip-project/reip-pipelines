'''Basic data manipulation - used to format/slice data in the middle of a pipeline.


Example:
>>> pipe = reip.audio.source() | reip.audio.spl() | (
...     reip.X[-1] | status.add(),
...     reip.csv()
... )

'''

from .block import Block
import opop

# Disable any piping operators
opop.Node.__or__ = lambda self, x: NotImplementedError
opop.Node.__ror__ = lambda self, x: NotImplementedError
