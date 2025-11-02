"""Unit tests for the execution state machine primitives."""
from __future__ import annotations

import random

import pytest

from core.state_machine import ExecutionStateMachine, IllegalTransition


_STATES = {
    "PENDING": {
        "description": "Pending execution",
        "allowed_transitions": ["RUNNING", "SKIPPED", "CANCELLED"],
    },
    "RUNNING": {
        "description": "Currently executing",
        "allowed_transitions": ["COMPLETED", "FAILED", "CANCELLED"],
    },
    "COMPLETED": {
        "description": "Finished successfully",
        "allowed_transitions": [],
    },
    "FAILED": {
        "description": "Failed with an error",
        "allowed_transitions": ["PENDING"],
    },
    "SKIPPED": {
        "description": "Skipped by orchestration",
        "allowed_transitions": [],
    },
    "CANCELLED": {
        "description": "Cancelled by operator",
        "allowed_transitions": [],
    },
}


def test_allows_expected_transitions() -> None:
    """Happy-path transitions should succeed without raising exceptions."""

    machine = ExecutionStateMachine(_STATES, "PENDING")

    machine.transition("RUNNING")
    machine.transition("COMPLETED")


def test_rejects_illegal_transitions() -> None:
    """An illegal transition should raise :class:`IllegalTransition`."""

    machine = ExecutionStateMachine(_STATES, "PENDING")

    with pytest.raises(IllegalTransition):
        machine.transition("COMPLETED")


def test_retry_flow_allows_return_to_pending() -> None:
    """FAILED state may transition back to PENDING for retries."""

    machine = ExecutionStateMachine(_STATES, "PENDING")
    machine.transition("RUNNING")
    machine.transition("FAILED")
    machine.transition("PENDING")


def test_random_walk_respects_allowed_transitions(seed: int = 42) -> None:
    """Randomly walk the state machine and ensure rules are respected."""

    random.seed(seed)
    machine = ExecutionStateMachine(_STATES, "PENDING")

    for _ in range(200):
        allowed = _STATES[machine.state]["allowed_transitions"]
        if allowed and random.random() < 0.7:
            candidate = random.choice(allowed)
            machine.transition(candidate)
        else:
            disallowed = [
                state
                for state in _STATES
                if state not in allowed and state != machine.state
            ]
            if not disallowed:
                continue
            illegal = random.choice(disallowed)
            with pytest.raises(IllegalTransition):
                machine.transition(illegal)
