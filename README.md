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

 - [SONYC](configs/sonyc.yaml)


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
