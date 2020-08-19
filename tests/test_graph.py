'''

What these tests should guarantee:
 - that graph/task contexts work correctly

'''
import reip


def test_graph_default():
    # test that graphs can be activated as the default
    # test that blocks/tasks are correctly added to the correct task
    top = reip.Graph.default
    assert isinstance(top, reip.Graph)

    with reip.Graph() as g:
        assert reip.Graph.default is g
        assert g is not top

    assert reip.Graph.default is top


def test_graph_inheritance():
    # test that a task cannot exist as a child of another task.
    pass


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
