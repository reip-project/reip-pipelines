# REIP - data processing pipelines



## Install

```bash
# while we're still private:
git clone https://github.com/reip-project/reip-pipelines.git
pip install -e ./reip-pipelines

# eventually:
pip install reip
```

## Usage






### Possible YAML Solution

This is very much still up in the air. In fact, if we choose an existing visual editor (e.g. nodered) this will most likely all change.

```yaml
vars:

components:
  compute:
    block: ...

pipelines:
  main:
    block: interval
    seconds: 3
    then:
      block: compute
      then:
        block: echo


```

```python
import reip

pipelines = reip.pipeline('config.yaml')

if __name__ == '__main__':
  pipelines.cli()
```

## Examples

 - [SONYC (yaml)](configs/sonyc.yaml)
 - [SONYC (python)](examples/sonyc.py)



## API

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

**NOTE:** I am open to looking into eager execution definitions as well (which is the current trend with things like tensorflow), but I know that tensorflow had to do some hacky things for eager execution to work properly so doing something like that will probably increase the complexity a fair amount. For the time being, anything people want to use eager execution for, they can just use the function block (`B.f(lambda: ...)`).




### Block Design



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

```

#### Block Concepts

Many pipeline implementations have concepts around block classes like:
 - Source: something that produces data (the start of a pipeline)
 - Processor: something that transforms data (the body of the pipeline)
 - Sink: something that consumes data (the end of a pipeline)

But personally, I don't think there is a meaningful distinction between a processor and a sink. Take for example, writing out data to a csv file. That would commonly be thought of as a sink, but that block doesn't have a null output. It should output a file which can then be fed into another block (convert to `.tar.gz`, upload, etc.).

So that leaves us with sources and processors. For the most part they are considered one in the same, however:
 - a processor takes in input and passes on outputs - just think of it as a function that is triggered when new input is passed.
 - a source isn't called in the same way because it doesn't have inputs - it is called once and it controls how often data is sent down the pipeline.


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
 - ~~some task~~ means completed
