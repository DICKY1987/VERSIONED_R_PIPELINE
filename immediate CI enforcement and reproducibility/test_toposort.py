# tests/test_toposort.py
import random
import pytest
from core.task_scheduler import topo_sort, CycleError

def test_simple_order():
    tasks = [
        {"id":"A","dependencies":[],"priority":1},
        {"id":"B","dependencies":["A"],"priority":5},
        {"id":"C","dependencies":["A"],"priority":2},
        {"id":"D","dependencies":["B","C"],"priority":1},
    ]
    order = [t["id"] for t in topo_sort(tasks)]
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")
    # B has higher priority than C, so B should come before C
    assert order.index("B") < order.index("C")

def test_cycle_detection():
    tasks = [
        {"id":"A","dependencies":["C"]},
        {"id":"B","dependencies":["A"]},
        {"id":"C","dependencies":["B"]},
    ]
    with pytest.raises(CycleError):
        topo_sort(tasks)

def test_random_dag_is_valid(seed=7):
    random.seed(seed)
    # generate a random DAG with N nodes by only allowing edges from lower idx to higher idx
    N = 25
    tasks = [{"id":f"T{i:02d}","dependencies":[], "priority": random.randint(0,10)} for i in range(N)]
    for j in range(1, N):
        # each node j depends on a random subset of [0..j-1]
        preds = [f"T{i:02d}" for i in range(j) if random.random() < 0.2]
        tasks[j]["dependencies"] = preds

    order = [t["id"] for t in topo_sort(tasks)]
    pos = {tid:i for i,tid in enumerate(order)}
    # All edges respected
    for t in tasks:
        for d in t["dependencies"]:
            assert pos[d] < pos[t["id"]]
