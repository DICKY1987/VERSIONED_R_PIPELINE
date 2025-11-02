# core/state_machine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

class IllegalTransition(Exception):
    pass

@dataclass
class StateDef:
    description: str
    allowed_transitions: List[str]
    entry_actions: Optional[List[str]] = None
    exit_actions: Optional[List[str]] = None

class ExecutionStateMachine:
    """
    Generic state machine that enforces allowed transitions.
    Instantiate with a dict mapping state name -> StateDef-like dict.
    """
    def __init__(self, states: Dict[str, dict], initial_state: str):
        if initial_state not in states:
            raise ValueError(f"Initial state {initial_state} not in states")
        self.states = states
        self.state = initial_state

    def can_transition(self, new_state: str) -> bool:
        allowed = self.states[self.state].get("allowed_transitions", [])
        return new_state in allowed

    def transition(self, new_state: str) -> None:
        if not self.can_transition(new_state):
            raise IllegalTransition(f"{self.state} -> {new_state} not allowed")
        self.state = new_state
