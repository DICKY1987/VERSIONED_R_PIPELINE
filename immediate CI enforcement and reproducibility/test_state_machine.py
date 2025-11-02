# tests/test_state_machine.py
import random
import pytest
from core.state_machine import ExecutionStateMachine, IllegalTransition

STATES = {
    "PENDING":  {"description":"", "allowed_transitions":["RUNNING","SKIPPED","CANCELLED"]},
    "RUNNING":  {"description":"", "allowed_transitions":["COMPLETED","FAILED","CANCELLED"]},
    "COMPLETED":{"description":"", "allowed_transitions":[]},
    "FAILED":   {"description":"", "allowed_transitions":["PENDING"]},
    "SKIPPED":  {"description":"", "allowed_transitions":[]},
    "CANCELLED":{"description":"", "allowed_transitions":[]},
}

def test_basic_allowed_transitions():
    sm = ExecutionStateMachine(STATES, "PENDING")
    sm.transition("RUNNING")
    sm.transition("COMPLETED")

def test_illegal_transition_raises():
    sm = ExecutionStateMachine(STATES, "PENDING")
    with pytest.raises(IllegalTransition):
        sm.transition("COMPLETED")  # PENDING -> COMPLETED is not allowed

def test_retry_flow():
    sm = ExecutionStateMachine(STATES, "PENDING")
    sm.transition("RUNNING")
    sm.transition("FAILED")
    sm.transition("PENDING")  # retry allowed

def test_random_walk_respects_rules(seed=42):
    random.seed(seed)
    sm = ExecutionStateMachine(STATES, "PENDING")
    for _ in range(200):
        allowed = STATES[sm.state]["allowed_transitions"]
        # 70% choose allowed; 30% try something illegal and assert it raises
        if allowed and random.random() < 0.7:
            nxt = random.choice(allowed)
            sm.transition(nxt)
        else:
            # pick a different state that isn't allowed (if possible)
            candidates = [s for s in STATES.keys() if s not in allowed and s != sm.state]
            if candidates:
                illegal = random.choice(candidates)
                with pytest.raises(IllegalTransition):
                    sm.transition(illegal)
            else:
                # nothing to test here
                pass
