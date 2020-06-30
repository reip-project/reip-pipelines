



def expects(*types):
    def outer(func):
        def inner(X, meta, **kw):
            return func(X, meta, **kw)
        return inner
    return outer

def as_type(x, *types):
    for t in types:
        if t is list:
            return as_list(x)



def as_list(x):
    return (
        x if isinstance(x, list) else
        list(x) if isinstance(x, tuple) else [x])

def as_array(x):
    return np.asarray(x)
