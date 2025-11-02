"""State Machine Unit Tests
Version: 1.0.0
Date: 2025-11-02
Coverage Target: 80%+
"""

import pytest

from core.state_machine import ExecutionState, TaskExecution, TaskStateMachine


def test_state_transition_validation():
    task = TaskExecution.create(task_id="test")
    assert task.can_transition_to(ExecutionState.RUNNING) is True
    assert task.can_transition_to(ExecutionState.COMPLETED) is False

    task.transition_to(ExecutionState.RUNNING)
    assert task.can_transition_to(ExecutionState.COMPLETED) is True


def test_invalid_transition_raises():
    task = TaskExecution.create(task_id="test")
    with pytest.raises(ValueError):
        task.transition_to(ExecutionState.COMPLETED)


def test_dependency_enforcement():
    task = TaskExecution.create(task_id="child", dependencies=["parent"])
    machine = TaskStateMachine(task)

    with pytest.raises(RuntimeError):
        machine.ensure_dependencies_satisfied([])

    machine.ensure_dependencies_satisfied(["parent"])


def test_task_state_machine_snapshot():
    task = TaskExecution.create(task_id="snapshot")
    machine = TaskStateMachine(task)
    snapshot = machine.to_dict()

    assert snapshot["task_id"] == "snapshot"
    assert snapshot["state"] == ExecutionState.PENDING.name
    assert len(snapshot["trace_id"]) == 26


def test_task_retry_cycle():
    task = TaskExecution.create(task_id="retry", max_attempts=2)
    machine = TaskStateMachine(task)

    machine.start()
    machine.fail()
    assert task.state is ExecutionState.FAILED
    machine.reset()
    assert task.state is ExecutionState.PENDING

    machine.start()
    machine.complete()
    assert task.state is ExecutionState.COMPLETED
