# Features
These are the features that I want to make sure we keep when doing any bigger refactors.

Please add any other features that you find important and want to make sure that we keep.

## Block
### \_\_init\_\_:
```python
# injecting arbitrary metadata
Block(meta={'a': 5})
```
```python
# input handlers that can arbitrarily modify the input
def filter_odd(X, meta):
    if not X % 2:
        return [X], meta

Block(input_handlers=[filter_odd])
```
```python
# output handlers (same idea)
Block(output_handlers=[filter_odd])
```
```python
# run handlers (allows for arbitrary functionality around running the block)
def retry(n_tries):
    def handler(block, run):
        for i in reip.util.loop():
            try:
                return run()  # the full block code
            except Exception as e:
                if n_tries and i >= n_tries-1:
                    raise
                block.log.error(reip.util.excline(e))

Block(handlers=[retry(5)])
```

```python
# arbitrary init keywords
class MyBlock(Block):
    def __init__(self, *a, **kw):
        super().__init__(*a, extra_kw=True, **kw)
    def process(self, X, meta):
        return [func(X, **kw)], meta
Block(a=5, b=6, c=7)
```

```python
# allow yielding from self.process which allows you to fan out data.
class Unravel(Block):
    def process(self, X, meta):
        if isinstance(X, list):
            for x in X:
                yield [x], meta
        yield [X], meta
Block(a=5, b=6, c=7)
```

## .to()
```python
# providing a default value for sources if nothing is present
# this prevents blocks from holding up other blocks if they don't have a value.
Block().to(Block(), default=lambda *xs, meta: ([{'present': 0}], {}))
```

## Helpers
These are helper functions that turn alternative block definitions into a Block class.

I'm totally happy to rename them, but this functionality is really important for making one-liner adhoc blocks.

For example: `block = reip.helpers.asbasic(lambda *xs: np.log(xs) - 1)()`

```python
# basic function helpers (process)

# this is a basic block that is naive of meta data/multiple outputs
@reip.helpers.asbasic  # equiv: reip.helpers.asblock(single_output=True, meta=False)
def Sum(*xs, i=2):
    return sum(xs * i)

# basic block that has multiple outputs, but no meta
@reip.helpers.asmulti  # equiv: reip.helpers.asblock(meta=False)
def MyBlock2(*xs, i=2):
    x = sum(xs)
    return [x * i, x * (i+1)]

# basic block that has a single output, with meta
@reip.helpers.asbasicmeta  # equiv: reip.helpers.asblock(single_output=True)
def MyBlock3(*xs, i=2):
    return sum(xs * i), {'i': i}

# basic block that has multiple outputs, with meta
@reip.helpers.asmultimeta  # equiv: reip.helpers.asblock()
def MyBlock2(*xs):
    x = sum(xs)
    return [x * i, x * (i+1)], {'i': i}
```
```python
# context helpers (init, process, finish)

@reip.helpers.asbasiccontext  # equiv: reip.helpers.asblock(context=True, self=True, single_output=True, meta=False)
def MyBlock5(block, i=2):
    block.history = []
    def process(xs):
        x = sum(xs * i)
        block.history.append(x)
        return x

    try:
        with some_context_manager():
            yield process
    finally:
        block.history.clear()


@reip.helpers.ascontext  # equiv: reip.helpers.asblock(context=True, self=True, single_output=True, meta=False)
def MyBlock5(block, i=2):
    try:
        block.log.info('hi! Im doin some initializing')
        def process(xs):
            x = sum(xs * i)
            return [x, x*2], {'i': i}
        yield process
    finally:
        block.log.info('jus doing some cleanupppp')
```

## Streams
These are really useful for working with streaming data outside of a block context which can be a pain with a bunch of queue-checking boilerplate otherwise.

```python
# iterating over a stream that pulls from all of the outputs of a block
b = Increment(10)

with b.run_scope():
  for (i,), meta in b.stream():  # stream is tied to the state of the block
      print(i, meta)
  print('I exited right away because the block finished.')
```

```python
# allow you to select a subset of the stream (only data, only meta)
b = Increment(10)
with b.run_scope():
    list(b.stream().data)
    list(b.stream().data[0])
    list(b.stream().meta)
```
