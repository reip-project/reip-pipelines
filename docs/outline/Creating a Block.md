# Creating a Block


```python
import reip

class Multiplier(reip.Block):
    '''Multiply the input by some constant.'''
    def __init__(self, multiplier=1, **kw):
        self.multiplier = multiplier
        super().__init__(**kw)

    def init(self):
        '''Any (optional) runtime initialization.'''

    def process(self, X, meta):
        return [X * self.multiplier], meta

    def finish(self, exc=None):
        '''Any (optional) runtime cleanup.'''
```

## Basic Rules
 - a block must return in one of the 3 formats:
    - `[out1, out2], meta` where the number of outputs corresponds to the number of sinks.
    - A sentinel value
        - `reip.RETRY`: try running the block again without incrementing the sources
        - `None`: increment the sources, nothing gets sent to the sinks
        - `reip.CLOSE`: the block is finished, close the block and notify downstream blocks.
        - `reip.TERMINATE`: something abrupt happened, shutdown blocks immediately.
    - A list of sentinel values corresponding to each source respectively (e.g. `return [None, reip.RETRY]` - retry the second source)

## Varying numbers of sources and sinks

```python
import reip

class MyBlock(reip.Block):
    '''A block with no sources and two sinks.'''
    def __init__(self, **kw):
        super().__init__(n_source=0, n_sink=2, **kw)

    def process(self, meta):
        t = time.time()
        return [t, t + 5], meta
```
