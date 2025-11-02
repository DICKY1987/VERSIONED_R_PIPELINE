"""Unit tests for the dependency-aware task scheduler."""
from __future__ import annotations

import random

import pytest

from core.task_scheduler import CycleError, topo_sort


def test_simple_dependency_ordering() -> None:
    """Dependent tasks must execute after their prerequisites."""

    tasks = [
        {"id": "A", "dependencies": [], "priority": 1},
        {"id": "B", "dependencies": ["A"], "priority": 5},
        {"id": "C", "dependencies": ["A"], "priority": 2},
        {"id": "D", "dependencies": ["B", "C"], "priority": 1},
    ]

    order = [task["id"] for task in topo_sort(tasks)]

    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")
    assert order.index("B") < order.index("C"), "Higher priority task should execute first"


def test_cycle_detection() -> None:
    """A cycle in the graph should raise :class:`CycleError`."""

    tasks = [
        {"id": "A", "dependencies": ["C"]},
        {"id": "B", "dependencies": ["A"]},
        {"id": "C", "dependencies": ["B"]},
    ]

    with pytest.raises(CycleError):
        topo_sort(tasks)


def test_random_dag_respects_dependencies(seed: int = 7) -> None:
    """Randomly generated DAGs should maintain topological order."""

    random.seed(seed)

    task_count = 25
    tasks = [
        {"id": f"T{i:02d}", "dependencies": [], "priority": random.randint(0, 10)}
        for i in range(task_count)
    ]

    for index in range(1, task_count):
        predecessors = [
            f"T{candidate:02d}"
            for candidate in range(index)
            if random.random() < 0.2
        ]
        tasks[index]["dependencies"] = predecessors

    order = [task["id"] for task in topo_sort(tasks)]
    positions = {task_id: idx for idx, task_id in enumerate(order)}

    for task in tasks:
        for dependency in task["dependencies"]:
            assert positions[dependency] < positions[task["id"]]
