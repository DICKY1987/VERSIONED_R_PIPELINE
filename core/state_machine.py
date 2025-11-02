"""ACMS Execution State Machine
Version: 1.0.0
Date: 2025-11-02
Implements: EXECUTION_STATE_MACHINE_CONTRACT.yaml
Owner: Platform.Engineering
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Iterable, List, Optional
from datetime import UTC, datetime
import secrets

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, length: int) -> str:
    """Encode an integer into Crockford's Base32 with fixed length."""
    chars: List[str] = []
    for _ in range(length):
        chars.append(CROCKFORD_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def generate_ulid() -> str:
    """Generate a ULID string without third-party dependencies."""
    timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
    randomness = int.from_bytes(secrets.token_bytes(10), "big")
    return _encode_base32(timestamp_ms, 10) + _encode_base32(randomness, 16)


class ExecutionState(Enum):
    """Enumeration of valid execution states."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()
    CANCELLED = auto()


_ALLOWED_TRANSITIONS: Dict[ExecutionState, List[ExecutionState]] = {
    ExecutionState.PENDING: [ExecutionState.RUNNING, ExecutionState.SKIPPED, ExecutionState.CANCELLED],
    ExecutionState.RUNNING: [ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED],
    ExecutionState.COMPLETED: [],
    ExecutionState.FAILED: [ExecutionState.PENDING, ExecutionState.CANCELLED],
    ExecutionState.SKIPPED: [],
    ExecutionState.CANCELLED: [],
}


@dataclass(slots=True)
class TaskExecution:
    """Mutable state for a task as it moves through the execution lifecycle."""

    task_id: str
    state: ExecutionState
    trace_id: str
    attempt: int = 0
    max_attempts: int = 3
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task_id: str,
        *,
        initial_state: ExecutionState = ExecutionState.PENDING,
        dependencies: Optional[Iterable[str]] = None,
        max_attempts: int = 3,
        metadata: Optional[Dict[str, str]] = None,
    ) -> "TaskExecution":
        """Factory helper that generates a trace identifier automatically."""

        return cls(
            task_id=task_id,
            state=initial_state,
            trace_id=generate_ulid(),
            attempt=0,
            max_attempts=max_attempts,
            dependencies=list(dependencies or []),
            metadata=dict(metadata or {}),
        )

    def can_transition_to(self, new_state: ExecutionState) -> bool:
        """Return ``True`` when ``new_state`` is a valid transition."""

        return new_state in _ALLOWED_TRANSITIONS.get(self.state, [])

    def transition_to(self, new_state: ExecutionState) -> None:
        """Transition to ``new_state`` enforcing contract rules."""

        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid transition from {self.state.name} to {new_state.name} for task {self.task_id}."
            )
        self.state = new_state

    def mark_failed(self) -> None:
        """Mark the task as failed and increment the attempt counter."""

        self.transition_to(ExecutionState.FAILED)
        self.attempt += 1

    def mark_completed(self) -> None:
        """Mark the task as completed."""

        self.transition_to(ExecutionState.COMPLETED)

    def reset_for_retry(self) -> None:
        """Reset a failed task back to pending for another attempt."""

        if self.state != ExecutionState.FAILED:
            raise ValueError("Only failed tasks can be reset for retry.")
        self.transition_to(ExecutionState.PENDING)


class TaskStateMachine:
    """State machine helper that manages transitions and validation."""

    def __init__(self, task: TaskExecution):
        self._task = task

    @property
    def task(self) -> TaskExecution:
        return self._task

    def ensure_dependencies_satisfied(self, completed_tasks: Iterable[str]) -> None:
        """Validate that task dependencies are satisfied before execution."""

        unmet = sorted(set(self._task.dependencies) - set(completed_tasks))
        if unmet:
            raise RuntimeError(
                f"Task {self._task.task_id} cannot run; unmet dependencies: {', '.join(unmet)}"
            )

    def start(self) -> None:
        """Move task into the RUNNING state."""

        self._task.transition_to(ExecutionState.RUNNING)

    def complete(self) -> None:
        """Mark the task as completed."""

        self._task.mark_completed()

    def fail(self) -> None:
        """Record a failure and increment the attempt counter."""

        self._task.mark_failed()

    def reset(self) -> None:
        """Reset task back to pending to allow retry."""

        self._task.reset_for_retry()

    def to_dict(self) -> Dict[str, object]:
        """Return a serialisable snapshot of the task state."""

        return {
            "task_id": self._task.task_id,
            "state": self._task.state.name,
            "trace_id": self._task.trace_id,
            "attempt": self._task.attempt,
            "max_attempts": self._task.max_attempts,
            "dependencies": list(self._task.dependencies),
            "metadata": dict(self._task.metadata),
        }


class IllegalTransition(Exception):
    """Raised when an invalid state transition is attempted."""


class ExecutionStateMachine:
    """Generic state machine enforcing allowed transitions."""

    def __init__(self, states: Dict[str, dict], initial_state: str):
        if initial_state not in states:
            raise ValueError(f"Initial state {initial_state} not in states")
        self._states = states
        self._state = initial_state

    @property
    def state(self) -> str:
        return self._state

    def can_transition(self, new_state: str) -> bool:
        allowed = self._states[self._state].get("allowed_transitions", [])
        return new_state in allowed

    def transition(self, new_state: str) -> None:
        if not self.can_transition(new_state):
            raise IllegalTransition(f"{self._state} -> {new_state} not allowed")
        self._state = new_state

