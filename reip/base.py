'''

Worker:
    id

Context:
    id:
    __enter__
    __exit__
    register: NotImplemented

'''
import weakref
from .util import text
import reip


class Worker:
    # parent = None
    parent_id = None
    def __init__(self, name=None, parent=None):
        self.name = Context._context_scope.auto_name(self, name=name)
        reip.Graph.register_instance(self, parent)

    @property
    def id(self): return self.name  # XXX change to __id so it's harder to change?

    # @property
    # def parent_id(self): return self.parent.name

    @property
    def parents(self):
        stack = []
        parent = Context.get_object(self.parent_id, require=False)
        while parent:
            stack.append(parent)
            parent = Context.get_object(parent.parent_id, require=False)
        return stack

    @property
    def full_id(self):
        return '/'.join(n.id for n in self.parents + [self])

    @classmethod
    def detached(cls, *a, **kw):
        return cls(*a, parent=False, **kw)


class _ContextScope:
    top = None
    default = None
    def __init__(self):
        self.refs = {}
        self.ns_index = {}

    def init(self, instance):
        '''Initialize the scope with a default/top instance.'''
        self.top = self.default = instance

    def register(self, instance, weak=True):
        self.refs[instance.name] = weakref.ref(instance) if weak else instance

    def get(self, instance):
        '''Get an instance.'''
        if instance is False:
            return None
        if instance is None:
            return self.default
        if isinstance(instance, str):
            return self.refs[instance]()
        return instance

    _NAMESPACES_IDX = {}
    def auto_name(self, instance, *attrs, name=None, ns=None):
        '''Generate an auto-incrementing name.'''
        # create a name from the block attributes
        name = name or text.pascal2kebab(instance.__class__.__name__)  # MyClass -> my-class
        name = name + ''.join('_'+str(x) for x in attrs)
        name = name.replace('/', '-')
        # get the count, based on some namespace. add count to name if above 1
        if ns not in self.ns_index:
            self.ns_index[ns] = {}
        ns = self.ns_index[ns]
        count = ns[name] = ns.get(name, -1) + 1
        return '{}-{:02.0f}'.format(name, count) if count else name

    def clear_ns_index(self):
        self.ns_index.clear()

    def get_object(self, id, require=True):  # XXX remove
        '''Get an instance using its name. If the instance '''
        obj = self.refs.get(id)
        obj = obj() if obj is not None else None
        if obj is None and require:
            raise ValueError(f'Object {id} does not exist.')
        return obj


def auto_name(block, *attrs, name=None, ns=None):
    '''Generate an auto-incrementing name.'''
    return Context._context_scope.auto_name(block, *attrs, name=name, ns=ns)

def _auto_name_clear():
    Context._context_scope.clear_ns_index()
auto_name.clear = _auto_name_clear




class Context(Worker):
    _previous = False  # the previous default instance
    _context_scope = _ContextScope()

    def __init__(self, *children, name=None, parent=None):
        if children and not name and isinstance(children[0], str):
            name, children = children[0], children[1:]

        super().__init__(name, parent)
        
        self.children = children = list(children)
        for c in children:
            self.register_instance(c, self)

    def __iter__(self):
        yield from self.children

    def nested(self, include_contexts=True):
        for b in self.children:
            if isinstance(b, Context):
                if include_contexts:
                    yield b
                yield from b.nested(include_contexts=include_contexts)
                continue
            yield b

    # context management

    @classmethod
    def get_context(cls, instance=None):  # XXX
        return cls._context_scope.get(instance)

    def __enter__(self):
        return self.as_default()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_previous()

    def as_default(self):
        '''Set this graph as the default graph and track the previous default.'''
        self._previous, self._context_scope.default = self._context_scope.default, self
        return self

    def restore_previous(self):
        '''Restore the previously set graph.'''
        if self._previous is not False:
            self._context_scope.default, self._previous = self._previous, None
        self._previous = False
        return self

    # 

    def add(self, child):
        '''Add block to graph.'''
        self.children.append(child)

    def remove(self, child):
        self.children.remove(child)

    def clear(self):
        self.children.clear()

    @classmethod
    def register_instance(cls, child=None, parent=None):
        '''Add a member (Block, Task) to the graph in instance.

        This is used inside of

        Arguments:
            child (reip.Graph, reip.Block): A graph, task, or block to add to
                instance.
                If `member is instance`, nothing will be added. In other words,
                A graph cannot be added to itself.
            parent (reip.Graph): A graph or task to be added to.
                If instance is None, the default graph/task will be used.
                If instance is False, nothing will be added.

        Returns:
            parent_id (str): the name of the child's parent block.
                Can be a Graph or Task.
            task_id (str or None): the name of the task that a child is attached to.
                If the parent graph is not inside a task or is not a task itself,
                it will return None.

            NOTE: Returning string ids prevents Blocks from having a circular reference
            to the entire graph.

        Basically this should handle:
         - adding a graph to a graph
            - parent.name, parent.task_id
         - adding a task to a graph
            - raise if parent is task
            - raise if graph.task_id is not None
            - if `flatten_tasks`, then iterate through graph parents until you
              find one on the main task
            - parent.name, child.name
         - adding a graph to a task
            - parent.name, parent.task_id
         - adding a block to a graph
            - parent.name, parent.task_id
         - adding a block to a task
            - parent.name, parent.task_id
         - do nothing if parent is False / None+unset default.
        '''
        parent = cls._context_scope.get(parent)
        cls._context_scope.register(child)
        if parent is None:  # no parent
            return
        if parent is child:  # trying to add to self ??
            return

        # everything checks out.
        parent.children.append(child)
        child.parent_id = parent.name
        return True

    @classmethod
    def get_object(cls, id, require=True):
        return cls._context_scope.get_object(id, require)
