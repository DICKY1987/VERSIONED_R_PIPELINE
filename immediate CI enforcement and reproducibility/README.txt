# Reference Artifacts (Schemas, Tests, Context Broker)

## Contents
- `schemas/execution_state_machine.schema.json` — JSON Schema for the Execution State Machine & Task DAG contract.
- `schemas/context_broker.schema.json` — JSON Schema for the Context Broker contract.
- `schemas/*.example.json` — Minimal examples that validate against the schemas.
- `core/state_machine.py` — Lightweight state machine used by tests.
- `core/task_scheduler.py` — Deterministic DAG topological sort with priority and id tie-breakers.
- `tests/test_state_machine.py` — Tiny test suite for legal/illegal transitions and retry flow.
- `tests/test_toposort.py` — Tests for valid topological ordering and cycle detection.
- `tools/context_broker.py` — Reference context broker that emits a stable `context_manifest.json`.

## Run tests
```bash
pip install pytest
pytest -q
```

## Generate a context manifest
```bash
python tools/context_broker.py --root . --out context_manifest.json --keywords orchestrator state --task-type edit
```
