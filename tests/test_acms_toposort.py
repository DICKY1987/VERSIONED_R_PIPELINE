"""Topological Sort Tests
Version: 1.0.0
Date: 2025-11-02
Tests: DAG ordering and cycle detection
"""

import pytest

from core.task_scheduler import TaskScheduler, CycleError
from core.orchestrator import Orchestrator
from core.state_machine import ExecutionState, TaskExecution


def test_dag_topological_sort():
    graph = {
        "tasks": [
            {"id": "A", "dependencies": []},
            {"id": "B", "dependencies": ["A"]},
            {"id": "C", "dependencies": ["A"]},
            {"id": "D", "dependencies": ["B", "C"]},
        ]
    }
    scheduler = TaskScheduler(graph)
    waves = scheduler.topological_sort()

    assert waves[0] == ["A"]
    assert set(waves[1]) == {"B", "C"}
    assert waves[2] == ["D"]

    plan = scheduler.get_execution_plan()
    assert plan["total_tasks"] == 4
    assert plan["total_waves"] == 3
    assert plan["max_parallelism"] == 2


def test_cycle_detection():
    graph = {
        "tasks": [
            {"id": "A", "dependencies": ["B"]},
            {"id": "B", "dependencies": ["A"]},
        ]
    }
    scheduler = TaskScheduler(graph)
    with pytest.raises(CycleError):
        scheduler.topological_sort()


def test_orchestrator_executes_in_dependency_order():
    executed = []

    def executor(task_id: str, task: TaskExecution):
        executed.append(task_id)
        return f"done-{task_id}"

    graph = {
        "tasks": [
            {"id": "setup", "dependencies": []},
            {"id": "plan", "dependencies": ["setup"]},
            {"id": "execute", "dependencies": ["plan"]},
        ]
    }

    orchestrator = Orchestrator(graph, executor)
    results = orchestrator.run()

    assert executed == ["setup", "plan", "execute"]
    assert set(results.keys()) == {"setup", "plan", "execute"}
    assert all(result.state is ExecutionState.COMPLETED for result in results.values())
