# reip - Reconfigurable Environmental IoT Platform (??)

`reip` is a framework for defining graphs of data operations that handles the dirty details of passing data between each of those operations so that you don't have to.

## Motivation

Designing code for IoT data collection can be quite daunting, especially when starting from scratch because in addition to defining all of the code needed to read from your sensors, you also need to be worried about how best to structure your code base, how to deal with inter-process communication, changing constraints about how your data is passed around, etc.

Often it can lead to tangled webs and frustrating nights of refactoring (speaking from experience).

What `reip` tries to do is remove the need for worrying about how to get data from point A to point B so you can focus on reading and processing your data and pointing it where you want to go.

## How it works

`reip` is similar to `tensorflow` in that
 - there is a *graph definition stage* where you define the pieces of computation and the parameters that you want to perform,
 - and there is a *graph execution stage* where the graph that you run takes all of the blocks that are assigned to that graph and starts them up in their own threads.

`reip` provides 3 core concepts:
 - `reip.Block`: A modular piece of computation with initialization, processing, and cleanup. (e.g. block1: reading audio from a microphone, block2: calculating audio SPL, etc.)
 - `reip.Graph`: a collection of blocks that run together
 - `reip.Task`: a `Graph` that executes all of its blocks together in a separate process.

Graphs can be nested inside of both Graphs and Tasks, but Tasks can only be nested inside of Graphs - you can't nest a Task inside another Task.

### Blocks

Blocks are each run in their own thread and have a certain number of sources and sinks. A sink is essentially a queue that holds data for connected blocks to read, and a sink is a cursor that can read from another block's sink.

```python
# chaining
B.Block().to(B.Block()).to(B.Block()).to(...)

# keras-like
input = B.Block()
x = B.Block()(input)
y = B.Block()(x)
z = B.Block(n_source=2)(x, y)
```

### Graphs

Graphs work as context managers that alter the global default graph so that blocks defined inside the context manager are added to that graph.

```python
with reip.Graph() as g:
    assert g is reip.default_graph()

    # define some blocks under g
    b1 = B.Block()
    b2 = B.Block()

    # add a nested graph
    with reip.Graph() as g2:
        b3 = B.Block()

    # see what's inside each graph
    assert g.blocks == [b1, b2, g2]
    assert g2.blocks == [b3]

# now the top default graph should be restored
assert reip.top_graph() is reip.default_graph()
# and Graph g should be a child of the top graph
assert reip.top_graph().blocks == [g]
```
