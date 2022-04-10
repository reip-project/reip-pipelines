Common Recipes
===================


Call a function every X seconds
------------------------------------


.. code-block:: python 

    class MyData(reip.Block):
        def __init__(self, interval, **kw):
            super().__init__(max_rate=1/interval, **kw)


        def process(self, meta):
            x, y, z = read_some_data()
            return [{'x': x, 'y': y, 'z': z}], {'time': time.time()}

    
    with reip.Graph() as g:
        MyData(5).to(B.Csv('{time}.csv'))
