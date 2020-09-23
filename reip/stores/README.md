# Stores

This contains implementations of the Source/Sink concepts.

We have:
 - Producer: A sink that data gets sent to
 - Customer: A source that reads from a Producer's queue.

Producers and Customers have a one-to-many relationship. Several customers can read from a single Producer and each have their own cursors which define their position in the data queue. Once all Customers have move past a data item, it is subject to deletion from the data store.

Inside each Producer, we have what we call Data Stores. They represent different ways of serializing, storing, and transmitting data between blocks and processes.

For Stores we have:
 - Store: a standard store that keeps items in a list. This is ideal for inter-thread communication because it doesn't have any serialization overhead.
 - PlasmaStore: uses a Plasma Object Store which was written by Apache for distributed Machine Learning applications. It is ideal for serializing and passing large numpy arrays between processes. It has a small/moderate overhead for serialization, but has fast deserialization because it can read the arrays directly from the memory store. (not sure if I explained this right.)
 - ClientStore: ...
    - pyarrow: for medium-size buffers
    - pickle: for small buffers




## Object Relationships
```
             Producer -> [Store1 Store2]
Customer1 -> Producer -> [Pointer1, ________, ________], [Store1, ______]
Customer2 -> Producer -> [________, Pointer2, ________], [Store1, ______]
Customer3 -> Producer -> [________, ________, Pointer3], [______, Store2]

get:
    Customer -> Pointer1 -> Store
put:
    Producer -> Store
```
