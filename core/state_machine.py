"""Execution state machine primitives for the ACMS orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Tuple

from .observability.ulid_generator import new_ulid

__all__ = [
    "ExecutionState",
    "IllegalTransition",
    "TaskExecution",
    "ExecutionStateMachine",
    "TaskStateMachine",
]


class IllegalTransition(RuntimeError):
    """Raised when an invalid state transition is requested."""


class ExecutionState(str, Enum):
    """Enumeration of the supported execution states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


_TASK_STATE_DEFINITION: Mapping[str, Dict[str, Iterable[str]]] = {
    ExecutionState.PENDING.value: {
        "allowed_transitions": (
            ExecutionState.RUNNING.value,
            ExecutionState.SKIPPED.value,
            ExecutionState.CANCELLED.value,
        ),
        "entry_actions": ("log_start_event",),
        "exit_actions": (),
    },
    ExecutionState.RUNNING.value: {
        "allowed_transitions": (
            ExecutionState.COMPLETED.value,
            ExecutionState.FAILED.value,
            ExecutionState.CANCELLED.value,
        ),
        "entry_actions": (
            "generate_trace_id",
            "log_start_event",
            "acquire_resources",
        ),
        "exit_actions": ("log_completion_event",),
    },
    ExecutionState.COMPLETED.value: {
        "allowed_transitions": (),
        "entry_actions": (
            "log_completion_event",
            "release_resources",
            "trigger_dependent_tasks",
        ),
        "exit_actions": (),
    },
    ExecutionState.FAILED.value: {
        "allowed_transitions": (
            ExecutionState.PENDING.value,
            ExecutionState.CANCELLED.value,
        ),
        "entry_actions": (
            "log_failure_event",
            "release_resources",
            "checkpoint_rollback",
            "evaluate_retry_policy",
        ),
        "exit_actions": (),
    },
    ExecutionState.SKIPPED.value: {
        "allowed_transitions": (),
        "entry_actions": (),
        "exit_actions": (),
    },
    ExecutionState.CANCELLED.value: {
        "allowed_transitions": (),
        "entry_actions": (),
        "exit_actions": (),
    },
}


def _coerce_state_name(state: str | ExecutionState) -> str:
    if isinstance(state, ExecutionState):
        return state.value
    return str(state)


@dataclass
class TaskExecution:
    """Mutable execution record for a single task instance."""

    task_id: str
    state: ExecutionState = ExecutionState.PENDING
    trace_id: str = field(default_factory=new_ulid)
    attempt: int = 0
    max_attempts: int = 3
    dependencies: List[str] = field(default_factory=list)

    def can_transition_to(self, new_state: ExecutionState | str) -> bool:
        """Return ``True`` when the task may transition to ``new_state``."""

        candidate = _coerce_state_name(new_state)
        allowed = _TASK_STATE_DEFINITION[self.state.value]["allowed_transitions"]
        return candidate in allowed

    def transition_to(self, new_state: ExecutionState | str) -> ExecutionState:
        """Transition the task to ``new_state`` and return the resolved state."""

        candidate = ExecutionState(_coerce_state_name(new_state))
        if not self.can_transition_to(candidate):
            raise IllegalTransition(
                f"Task {self.task_id} cannot transition from {self.state.value} to {candidate.value}"
            )

        if self.state is ExecutionState.FAILED and candidate is ExecutionState.PENDING:
            if self.attempt >= self.max_attempts:
                raise IllegalTransition(
                    f"Task {self.task_id} exceeded retry budget ({self.max_attempts})"
                )
        elif candidate is ExecutionState.RUNNING:
            if self.attempt >= self.max_attempts:
                raise IllegalTransition(
                    f"Task {self.task_id} exceeded retry budget ({self.max_attempts})"
                )
            self.attempt += 1

        self.state = candidate
        if self.trace_id is None:
            self.trace_id = new_ulid()
        return self.state


class ExecutionStateMachine:
    """Generic state machine that validates transitions against a definition."""

    def __init__(self, states: Mapping[str, Mapping[str, Iterable[str]]], initial_state: str):
        if initial_state not in states:
            raise KeyError(f"Initial state {initial_state!r} not present in state definition")
        self._states: Dict[str, MutableMapping[str, Iterable[str]]] = {
            name: {
                "allowed_transitions": tuple(defn.get("allowed_transitions", ())),
                "entry_actions": tuple(defn.get("entry_actions", ())),
                "exit_actions": tuple(defn.get("exit_actions", ())),
            }
            for name, defn in states.items()
        }
        self._state = initial_state

    @property
    def state(self) -> str:
        """Return the current state name."""

        return self._state

    def allowed_transitions(self) -> Tuple[str, ...]:
        """Return the allowed transitions from the current state."""

        return tuple(self._states[self._state]["allowed_transitions"])

    def can_transition(self, candidate: str | ExecutionState) -> bool:
        """Return ``True`` if the state machine may transition to ``candidate``."""

        target = _coerce_state_name(candidate)
        return target in self.allowed_transitions()

    def transition(self, candidate: str | ExecutionState) -> str:
        """Transition to ``candidate`` or raise :class:`IllegalTransition`."""

        target = _coerce_state_name(candidate)
        if not self.can_transition(target):
            raise IllegalTransition(f"Transition from {self._state} to {target} is not permitted")
        self._state = target
        return self._state

    def reset(self, state: str | ExecutionState) -> None:
        """Reset the state machine to ``state`` without validation."""

        target = _coerce_state_name(state)
        if target not in self._states:
            raise KeyError(f"Unknown state {target!r}")
        self._state = target

    def iter_states(self) -> Iterator[str]:
        """Yield the known state names in insertion order."""

        return iter(self._states.keys())


class TaskStateMachine(ExecutionStateMachine):
    """Specialised execution state machine using :class:`ExecutionState`."""

    def __init__(self, initial_state: ExecutionState | str = ExecutionState.PENDING):
        super().__init__(_TASK_STATE_DEFINITION, _coerce_state_name(initial_state))

    @property
    def state(self) -> ExecutionState:  # type: ignore[override]
        return ExecutionState(super().state)

    def transition(self, candidate: ExecutionState | str) -> ExecutionState:  # type: ignore[override]
        state = super().transition(candidate)
        return ExecutionState(state)

    def allowed_transitions(self) -> Tuple[ExecutionState, ...]:  # type: ignore[override]
        return tuple(ExecutionState(item) for item in super().allowed_transitions())
