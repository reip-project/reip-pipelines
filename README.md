# REIP - data processing pipelines

[![pypi](https://badge.fury.io/py/reip.svg)](https://pypi.python.org/pypi/reip/)
<!-- ![tests](https://github.com/beasteers/pathtrees/actions/workflows/ci.yaml/badge.svg) -->
[![docs](https://readthedocs.org/projects/reip-pipelines/badge/?version=latest)](http://reip-pipelines.readthedocs.io/?badge=latest)
[![License](https://img.shields.io/pypi/l/reip.svg)](https://github.com/reip-project/reip/blob/master/LICENSE.md)


## Install

```bash
# while we're still private:
git clone https://github.com/reip-project/reip-pipelines.git
pip install -e ./reip-pipelines

# eventually:
pip install reip
```

More detailed installation instruction for NVIDIA Jeton platform can be found [here](Installation.md).

## Usage


#### Chain Interface
Javascript-esque method chaining.
```python
import reip
import reip.blocks as B
import reip.blocks.audio

# record audio and buffer into chunks of 10
audio = B.audio.Mic(block_duration=1)
audio10s = (
    audio.to(B.Debug('Audio'))
    .to(B.Rebuffer(duration=10)))
# plot a spectrogram
spec_img = (
    audio10s.to(B.audio.Stft())
    .to(B.Debug('Spec'))
    .to(B.Specshow('plots/{time}.png')))
# to wavefile
wav = (
    audio10s.to(B.Debug('Audio 222'))
    .to(B.audio.AudioFile('audio/{time}.wav')))

print(reip.default_graph())
reip.run()

```

#### Function Interface
Mimicking a Keras interface.
```python
import reip.blocks as B

# record audio and buffer into chunks of 10
audio = B.audio.Mic(block_duration=1)
audio10s = B.Rebuffer(duration=10)(audio)

# to spectrogram
stft = B.audio.Stft()(audio)
specshow = B.Specshow('plots/{time}.png')(spec)
# to wavefile
wav10s = B.audio.AudioFile('audio/{time}.wav')(audio10s)

print(reip.default_graph())
reip.run()

```

<!-- ## Concepts

### Block
A block is an isolated piece of computation that takes a variable number of inputs and a metadata dictionary (`(*Xs, meta={})`) and returns a variable number of outputs and a metadata dictionary `([X], {})`.

Like Tensorflow, there is a graph definition stage, and a graph execution stage.

All blocks exist as separate threads and pass data in between each other using queues.

These threads can either be run on the current process (the top-level default graph) or on a separate process (a Task).

If they are run in a separate process, the data is serialized using `pyarrow` and is passed to the other process using a Plasma Object Store.

#### Building your own Blocks

```python

class Custom(reip.Block):
    def init(self):
        '''Initialize the block.

        __init__ is called during graph execution.
        This function is for initialization that you
        don't want to have to pickle to send to
        another task.
        '''

    def process(self, *Xs, meta=None):
        '''The main processing code that gets called with
        every input added to the queue.

        For now, it should return a tuple of a list
        (data buffers, e.g. numpy arrays or strings)
        and a dictionary of any metadata you might want
        to pass to the next block.
        '''
        return Xs, meta

    def finish(self):
        '''Any cleanup that you want to do.'''

``` -->


<!-- ### Graph
A collection of blocks that operate together.

Here's how graph contexts work.

```python
import reip

# you always start with a default graph.
top_graph = reip.default_graph()

print(top_graph)
# [~Graph (0 children) ~]

# create some block, it get's automatically
# added to the default graph.
reip.blocks.Debug()

# the block automatically shows up 'o'
print(top_graph)
# [~Graph (1 children)
#     [Block(4363961616): Debug (1 in, 1 out)]~]


# create a nested graph and set as default within
# the context. New blocks will be added  to this
# graph.
with reip.Graph() as g:
    reip.blocks.Csv()
    print(g)
    # [~Graph (1 children)
    #     [Block(5007675152): Csv (1 in, 1 out)]~]

# the graph `g` is added to the top graph. ^-^
print(top_graph)
# [~Graph (2 children)
#     [Block(4363961616): Debug (1 in, 1 out)]
#     [~Graph (1 children)
#         [Block(5007675152): Csv (1 in, 1 out)]~]~]


# create a separate graph (by setting graph=False).
# this will not be added to the top graph.
with reip.Graph(graph=False) as separate_graph:  
    reip.blocks.TarGz()
    print(separate_graph)
    # [~Graph (1 children)
    #     [Block(4687358032): TarGz (1 in, 1 out)]~]

# pass separate_graph into a block.
reip.blocks.Interval(graph=separate_graph)

# it gets added to separate_graph, not the default.
print(separate_graph)
# [~Graph (2 children)
#     [Block(4432609104): TarGz (1 in, 1 out)]
#     [Block(4391746128): Interval (0 in, 1 out)]~]

# separate_graph is not here. x.x
print(top_graph)
# [~Graph (2 children)
#     [Block(4363961616): Debug (1 in, 1 out)]
#     [~Graph (1 children)
#         [Block(5007675152): Csv (1 in, 1 out)]~]~]
```
And you can modify the default without using contexts.
```python
# after exiting the `with` context the previous
# default is set.
assert reip.default_graph() is top_graph

# but you can change the default like this too
separate_graph.as_default()
assert reip.default_graph() is separate_graph

# and reset it back.
separate_graph.restore_previous()
assert reip.default_graph() is top_graph

```

```python


``` -->


<!-- ### Task
A Task is a Graph that executes in a separate process.

All of the same principles of Graphs apply to Tasks. They can be set as the default and blocks will automatically add themselves to it.

```python
import reip

top_graph = reip.default_graph()

with reip.Graph() as g:
    with reip.Task() as t:
        reip.blocks.Csv()
print(top_graph)
# [~Graph (1 children)
#     [~Graph (1 children)
#         [~Task (1 children)
#             [Block(4997015120): Csv (1 in, 1 out)]~]~]~]

```

Currently, Tasks will add to the default graph and not other tasks. This was done because I figured nested processes would get messy, but idk. That may change once we test it. -->


<!-- ## API - out of date, will update

The goal of the API is to provide a simple and easily understandable interface to build out ad-hoc data processing pipelines.

There are two steps to build out a pipeline:
 - graph definition
 - graph execution

```python
import reip
import reip.blocks as B

# graph definition

class C:
    ml_threshold = 0.5
    ml_classes = 'human voice', 'engine', 'dog'


# audio source
audio = B.audio.source(channels=1, sr=48000, chunk=4800)

# audio processors
spl = B.audio.spl(n_fft=8192, duration=1)
ml_emb = B.tflite.stft(filename='/path/to/emb_model.tf')
ml_cls = ml_emb | B.tflite(filename='/path/to/cls_model.tf')

ml_label = ml_cls | B.f(lambda X, meta:
    C.ml_classes[np.argmax(X)]
    if np.any(X > C.ml_threshold)
    else 'unknown')

# graph execution

reip.run(
    # feed audio into each processor and print results
    audio=audio | (
        spl | B.log(),
        ml_emb | B.log(),
        ml_cls | B.log(),
        ml_label | B.log(),
    )
)
```

**NOTE:** I am open to looking into eager execution definitions as well (which is the current trend with things like tensorflow), but I know that tensorflow had to do some hacky things for eager execution to work properly so doing something like that will probably increase the complexity a fair amount. For the time being, anything people want to use eager execution for, they can just use the function block (`B.f(lambda: ...)`). -->




<!-- ### Block Design



Most simply, a block is a class with init code (optional), and a data transformation function.

The transformation function receives:
 - `X` which is the data output of the previous block.
    - type should be a numpy array or an [xarray](http://xarray.pydata.org/en/stable/) - `xarray` is like a numpy array, but you can also encode column information, so you can assign labels to each numpy array column (`laeq`, `lzeq`, etc.) This will make it really easy to write to things like csv.
 - `meta`, which is the accumulated metadata (`dict`) from this run iteration.
    ```python
    {
        'time': time.time(),
        ''
    }
    ```

```python
import json
from reip import Block

class Inspect(Block):
    '''A block that prints out info about the data passed to it.'''
    def __init__(self, message=''):
        self.message = message

    def call(self, X, meta):
        '''Apply some transformation to the data, then return it.

        Arguments:
            X (np.ndarray or xarray.xarray): the data output from
                the previous block.
            meta (dict): the accumulated metadata from this run
                iteration. It should contain keys like:

        Returns:
            X: transformed input data
            meta (dict): the accumulated metadata
        '''
        print(self.message, f'''
        shape: {X.shape},      dtype: {X.dtype}
        mean:  {X.mean():.2f}, std:   {X.std():.2f}
        min:   {X.min():.2f},  max:   {X.max():.2f}
        meta: {json.dumps(meta, indent=2, sort_keys=True)}
        ''')
        return X, meta

``` -->

<!-- #### Block Concepts

Many pipeline implementations have concepts around block classes like:
 - Source: something that produces data (the start of a pipeline)
 - Processor: something that transforms data (the body of the pipeline)
 - Sink: something that consumes data (the end of a pipeline)

But personally, I don't think there is a meaningful distinction between a processor and a sink. Take for example, writing out data to a csv file. That would commonly be thought of as a sink, but that block doesn't have a null output. It should output a file which can then be fed into another block (convert to `.tar.gz`, upload, etc.).

So that leaves us with sources and processors. For the most part they are considered one in the same, however:
 - a processor takes in input and passes on outputs - just think of it as a function that is triggered when new input is passed.
 - a source isn't called in the same way because it doesn't have inputs - it is called once and it controls how often data is sent down the pipeline. -->

<!-- 
## TODO

### Larger Decisions to be Made
 - What do we use for building computational graphs?
    - can we use existing solutions or will they add too much serialization overhead (e.g. nodered is javascript-based and expects JSON serialization which could be unnecessarily slow for numpy arrays)? We could use our own serialization
 - Does that solution manage job queues?
    - Yurii has been talking about using distributed computations? Can we utilize existing cluster management tools to spread the load without adding too much data transmission overhead?

### Block Core
 - ~~ input / output regularization/formatting
 - ~~ chaining
 - ~~ clean subclass override implementation
 - jinja formatting
    - late formatting for values
    - nested variable scopes
    - take unused arguments to use as general variables
 - data buffering/chaining
   - efficient - multiprocessing etc.
 - looping?
 - conditions?

### Audio Blocks
 - ~~ Audio Source
 - ~~ Audio file writer
 - ~~ Audio tflite
 - ~~ SPL
   - ~~ weighting
   - ~~ octave bands
   - what does output look like?

### ML Blocks
 - ~~ Tflite
   - data windowing

### Misc
 - ~~ Interval Source
 - File/glob source
  - one at a time
  - sorting/sampling
 - ~~ Encryption
 - state persistent/tmp
 - CSV
  - how to do column names
 - Tar - or even general compress/dump
 - upload

### Notes
 - `~~` means in progress / partially done?
 - ~~some task~~ means completed -->
