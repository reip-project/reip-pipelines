# Blocks

## Audio
 - Input
    - Microphone - feeds audio from microphone
    - Audio File
 - Process
    - SPL
        - avg
        - octave band
    - STFT
        - linear
        - mel
 - Output
    - Audio File
    - Spectrogram
    - Speaker

## ML
 - tflite
 - keras

## OS
 - Watch Directory

## General Data Output and Serialization
 - CSV File
 - HDF5
 - Encryption
 - Archives
    - tar/.gz
 - HTTP Uploader
 - TCP? (ugh)

## Communication
 - HTTP Server (e.g. Flask)
    - For inter-node communication, data access api, etc.?

## Common Data Operations / Control Flow
 - Rebuffer - Concatenate and slice along a certain dimension to get a different chunk size. e.g. buffer 1 second audio to be in 10 second chunks.
 - Unravel (for) - Take a list input and send one element at a time
 - Gate (if) - pass to outputs based on some data condition


## General Utilities
 - Interval - Pass outputs at a certain minimum rate (e.g. run every 5 seconds)
 - Lambda - general process functions
    - Problem: you can't pickle actual lambda functions to send to another task... would be restricted to top level functions. Maybe cloudpickle?



## Other Ideas

#### Block Functions
Basic blocks without complicated state can probably be more efficiently written in this form.

The problem is that generators are blocking so if stream runs out of input (if someone doesn't yield inside the loop) then it will hang indefinitely.
That may be fine since it's in its own thread, but we'd need to handle control signals. Perhaps that can happen inside the stream class. Like if it runs some custom exit exception, then their try, finally block will catch it and run the cleanup and then we just catch the exception outside.
```python
import reip
import reip.blocks as B

@B.streamer()
def custom_block(stream, step=2):
    try:
        # basically init() - do some initialization
        start = 10
        # basically process() - do some processing
        for i, ((data,), meta) in enumerate(stream, start):
            yield data * step, {'index': i}
    finally:
        # basically finish() - do some cleanup
        print('all done. just cleaning up.')

(B.Constant(5)
 .to(custom_block(step=4))
 .to(B.Debug('asdf')))

```
