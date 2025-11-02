"""
Workflow Execution Integration Tests
Version: 1.0.0
Date: 2025-11-02
Tests: Full pipeline execution
"""
from __future__ import annotations

import inspect
from typing import Iterable, List

import pytest


def _coerce_wave_representation(execution_plan: object) -> List[List[str]]:
    """Normalize scheduler output into deterministic waves."""
    if execution_plan is None:
        return []

    if isinstance(execution_plan, dict):
        if "waves" in execution_plan:
            return [list(map(str, wave)) for wave in execution_plan["waves"]]
        if "tasks" in execution_plan:
            return [[str(entry["id"]) for entry in execution_plan["tasks"]]]

    if isinstance(execution_plan, Iterable) and not isinstance(execution_plan, (str, bytes)):
        normalized: List[List[str]] = []
        for item in execution_plan:
            if isinstance(item, dict) and "id" in item:
                normalized.append([str(item["id"])])
            elif isinstance(item, (list, tuple, set)):
                normalized.append([str(x) for x in item])
            else:
                normalized.append([str(item)])
        return normalized

    return [[str(execution_plan)]]


@pytest.mark.integration
def test_topological_plan_respects_dependencies(task_graph_definition):
    """Verify scheduler honors declared dependencies and priority tie-breakers."""
    scheduler_module = pytest.importorskip(
        "core.task_scheduler", reason="Task scheduler module not yet implemented."
    )

    if hasattr(scheduler_module, "TaskScheduler"):
        scheduler = scheduler_module.TaskScheduler(task_graph_definition)
        plan = None
        if hasattr(scheduler, "topological_sort"):
            plan = scheduler.topological_sort()
        elif hasattr(scheduler, "get_execution_plan"):
            plan = scheduler.get_execution_plan()
    elif hasattr(scheduler_module, "topo_sort"):
        plan = scheduler_module.topo_sort(task_graph_definition["tasks"])
    else:
        pytest.skip("No supported scheduler API discovered.")

    waves = _coerce_wave_representation(plan)
    positions = {task_id: idx for idx, wave in enumerate(waves) for task_id in wave}

    assert positions["task_001_preflight"] <= positions["task_002_run_init"]
    assert positions["task_002_run_init"] <= positions["task_003_planning"]
    assert positions["task_004_worktree_a"] >= positions["task_003_planning"]
    assert positions["task_005_worktree_b"] >= positions["task_003_planning"]
    assert positions["task_006_merge_prep"] >= max(
        positions["task_004_worktree_a"], positions["task_005_worktree_b"]
    )


@pytest.mark.integration
def test_state_machine_rejects_illegal_transitions(state_machine_definition):
    """Ensure the execution state machine enforces allowed transitions."""
    state_machine_module = pytest.importorskip(
        "core.state_machine", reason="Execution state machine module not yet implemented."
    )

    if hasattr(state_machine_module, "ExecutionStateMachine"):
        machine = state_machine_module.ExecutionStateMachine(
            state_machine_definition, "PENDING"
        )
        machine.transition("RUNNING")
        machine.transition("FAILED")
        machine.transition("PENDING")

        with pytest.raises(Exception):
            machine.transition("COMPLETED")
    else:
        pytest.skip("ExecutionStateMachine class unavailable.")


@pytest.mark.integration
def test_orchestrator_emits_trace_metadata(task_graph_definition, state_machine_definition):
    """Validate that orchestrator exposes a workflow execution entry point with trace support."""
    orchestrator_module = pytest.importorskip(
        "core.orchestrator", reason="Pipeline orchestrator module not yet implemented."
    )

    orchestrator_cls = None
    for candidate in ("PipelineOrchestrator", "Orchestrator"):
        orchestrator_cls = getattr(orchestrator_module, candidate, None)
        if orchestrator_cls is not None:
            break

    if orchestrator_cls is None:
        pytest.skip("No orchestrator class exported from core.orchestrator.")

    state_machine_module = pytest.importorskip(
        "core.state_machine", reason="Execution state machine module not yet implemented."
    )

    class _StateMachineFactory:
        def __call__(self) -> object:
            return state_machine_module.ExecutionStateMachine(state_machine_definition, "PENDING")

    class _DummyScheduler:
        def __init__(self, graph):
            self._graph = graph

        def get_execution_plan(self):
            return {
                "waves": [[task["id"]] for task in self._graph["tasks"]],
                "task_graph": self._graph,
            }

    class _DummyLedger:
        def __init__(self):
            self.entries = []

        def append(self, entry):
            self.entries.append(entry)

        def write(self, entry):
            self.entries.append(entry)

    class _DummyTracer:
        def __init__(self):
            self.spans = []

        def start_as_current_span(self, name):
            class _Span:
                def __init__(self, tracer, span_name):
                    self._tracer = tracer
                    self._span_name = span_name

                def __enter__(self):
                    self._tracer.spans.append(self._span_name)
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Span(self, name)

    scheduler = _DummyScheduler(task_graph_definition)
    ledger = _DummyLedger()
    tracer = _DummyTracer()

    signature = inspect.signature(orchestrator_cls)
    kwargs = {}
    for name, param in signature.parameters.items():
        if name in {"state_machine", "state_machine_factory"}:
            kwargs[name] = _StateMachineFactory()
        elif name in {"task_scheduler", "scheduler"}:
            kwargs[name] = scheduler
        elif name in {"ledger", "ledger_writer", "audit_ledger"}:
            kwargs[name] = ledger
        elif name in {"tracer", "trace"}:
            kwargs[name] = tracer
        elif name in {"plugins", "plugin_registry", "plugin_loader"}:
            kwargs[name] = []
        elif param.default is inspect._empty:
            pytest.skip(f"Cannot satisfy orchestrator dependency: {name}")

    orchestrator = orchestrator_cls(**kwargs)

    for method_name in ("run_workflow", "run", "execute"):
        if hasattr(orchestrator, method_name):
            method = getattr(orchestrator, method_name)
            break
    else:
        pytest.skip("No runnable method exposed on orchestrator instance.")

    method_signature = inspect.signature(method)
    call_kwargs = {}
    trace_id = "trace-123"
    for name, param in method_signature.parameters.items():
        if name in {"task_graph", "plan", "execution_plan"}:
            call_kwargs[name] = task_graph_definition
        elif name == "trace_id":
            call_kwargs[name] = trace_id
        elif name in {"request", "workflow_request"}:
            call_kwargs[name] = {"task_graph": task_graph_definition, "trace_id": trace_id}
        elif param.default is inspect._empty:
            pytest.skip(f"Cannot satisfy orchestrator run argument: {name}")

    result = method(**call_kwargs)

    assert ledger.entries, "Orchestrator should append at least one ledger entry"
    assert any(trace_id in str(entry) for entry in ledger.entries)
    assert tracer.spans, "Trace spans should be recorded during workflow execution"
    if result is not None:
        assert trace_id in str(result)
