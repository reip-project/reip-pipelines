'''

What these tests should guarantee:
 - that graph/task contexts work correctly

'''
from contextlib import contextmanager
import reip
import pytest


class Indexes:  # help visualize graph inheritance depth
    i = -1
    idxs = {}
    def get(self, key):
        self.i += 1
        ikey = (key, self.i)
        self.idxs[ikey] = self.idxs.get(ikey, -1) + 1
        return '{}_{}.{}'.format(key or 'idx', self.i, self.idxs[ikey])
    def dec(self):
        self.i -= 1
idxs = Indexes()

@contextmanager
def checked_graph_instance(cls, parent, **kw):
    print(11111, parent.name)
    print(22222, [b.name for b in parent.blocks], parent.name)
    with cls(name=idxs.get(cls.__name__)) as g1:
        assert isinstance(g1, cls)
        assert reip.default_graph() is g1
        assert g1 is not reip.top_graph()
        print(33333, [b.name for b in parent.blocks])
        print(44444, parent.parent_id, parent.task_id, g1.parent_id, g1.task_id)
        print()
        assert sum(g1 is b for b in parent.blocks) == 1

        assert g1.parent_id is parent.name
        yield g1
    assert reip.default_graph() is parent
    idxs.dec()

def test_graph_inheritance():
    # test that graphs can be activated as the default
    # test that blocks/tasks are correctly added to the correct task
    top = reip.default_graph()
    assert isinstance(top, reip.Graph)
    assert top.parent_id is None
    assert top.task_id is None

    with checked_graph_instance(reip.Graph, top) as g1:
        assert g1.task_id is None
        with checked_graph_instance(reip.Graph, g1) as g2:
            assert g1.task_id is None
            with checked_graph_instance(reip.Graph, g2) as g3:
                assert g1.task_id is None
                with checked_graph_instance(reip.Graph, g3) as g4:
                    assert g1.task_id is None
                assert reip.default_graph() is g3
                with checked_graph_instance(reip.Graph, g3) as g5:
                    assert g1.task_id is None

    top.clear()


def test_task_inheritance():
    # test that a task cannot exist as a child of another task.
    with checked_graph_instance(reip.Graph, reip.top_graph()) as g1:
        assert g1.task_id is None
        with checked_graph_instance(reip.Task, g1) as g2:
            assert g2.task_id is g2.name
            with pytest.raises(RuntimeError):
                with checked_graph_instance(reip.Task, g2):
                    pass

            with checked_graph_instance(reip.Graph, g2) as g3:
                assert g3.task_id is g2.name

                with checked_graph_instance(reip.Graph, g3) as g4:
                    assert g4.task_id is g2.name
                    with checked_graph_instance(reip.Graph, g4) as g5:
                        assert g5.task_id is g2.name
                assert reip.default_graph() is g3

                with pytest.raises(RuntimeError):
                    with checked_graph_instance(reip.Task, g3):
                        pass
                assert reip.default_graph() is g3
                with checked_graph_instance(reip.Graph, g3) as g4:
                    assert g4.task_id is g2.name
                    with checked_graph_instance(reip.Graph, g4) as g5:
                        assert g5.task_id is g2.name

    reip.top_graph().clear()


def test_graph_run():
    # test graph run.
    # test properties:
    #   ready, running, terminated, done, error
    # test methods:
    #   pause, resume
    pass


def test_task_run():
    # test task run.
    # test properties:
    #   ready, running, terminated, done, error
    # test methods:
    #   pause, resume
    pass
