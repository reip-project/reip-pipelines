import pytest
import reip



def test_meta():
    meta_a1 = reip.Meta({'i': 1, 'a': 1})
    meta_a2 = reip.Meta({'i': 2, 'b': 2}, meta_a1)
    meta_a3 = reip.Meta({'i': 3, 'b': 3}, meta_a2)

    meta_b1 = reip.Meta({'i': 1, 'a': 4})
    meta_b2 = reip.Meta({'i': 2, 'c': 6}, meta_b1)

    meta = reip.Meta({'i': 0, 'd': 10}, meta_a3, meta_b2)
    print(dict(meta))

    # flat = {'i': 0, 'd': 10, 'b': 3, 'c': 6, 'a': 4}
    flat = {'i': 0, 'd': 10, 'b': 3, 'c': 6, 'a': 1}

    # check as an iterable
    assert dict(meta) == flat
    assert set(meta) == set(flat)
    assert len(meta) == len(flat)

    # check contains
    assert 'a' in meta
    assert 'z' not in meta

    # check getitem
    assert meta['a'] == 1
    assert meta['b'] == 3
    assert meta['c'] == 6
    assert meta['d'] == 10
    assert meta['i'] == 0
    assert meta.get('a', 99) == 1
    assert meta.get('z', 99) == 99

    # check slicing input list
    assert meta[1] == meta.inputs[1]
    assert meta[1:] == meta.inputs[1:]

    # check dict views
    assert set(meta.keys()) == set(flat.keys())
    assert set(meta.values()) == set(flat.values())
    assert set(meta.items()) == set(flat.items())

    # # check iterators
    # depths = [
    #     [meta.data],
    #     [meta_a3.data, meta_b2.data],
    #     [meta_a2.data, meta_b1.data],
    #     [meta_a1.data],
    # ]

    # assert list(meta.depths()) == depths
    # assert list(meta.nearfirst()) == [d for ds in depths for d in ds]
    # assert list(meta.deepfirst()) == [
    #     meta.data, meta_a3.data, meta_a2.data, meta_a1.data, 
    #     meta_b2.data, meta_b1.data
    # ]

    # check set/del item
    meta['b'] = 5
    assert meta['b'] == 5
    assert meta.data['b'] == 5
    assert 'b' in meta.data
    del meta['b']
    assert 'b' not in meta.data
    assert 'b' not in meta
    # assert 'b' in meta.deleted_keys
    meta['b'] = 6
    assert 'b' in meta
    assert 'b' in meta.data
    # assert 'b' not in meta.deleted_keys
    assert meta['b'] == 6

    # check append, extend, update
    assert len(meta.inputs) == 2
    meta.append({'e': 10})
    meta.extend([{'f': 11, 'g': 12}, {'g': 10}])
    meta.update(h=13)

    assert len(meta.inputs) == 5
    assert 'h' in meta.data
    assert meta['e'] == 10
    assert meta['f'] == 11
    assert meta['g'] == 12
    assert meta['h'] == 13

    # assert meta.find_key('a') is meta_b1.data
    # meta.scrub_key('b')
    # for m in meta.nearfirst():
    #     assert 'b' not in m