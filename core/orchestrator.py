"""Workflow orchestrator for ACMS pipeline executions."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence

from .observability.ledger import Ledger
from .observability.ulid_generator import new_ulid
from .state_machine import ExecutionState, IllegalTransition, TaskExecution, TaskStateMachine
from .task_scheduler import TaskScheduler

__all__ = ["Orchestrator"]


def _resolve_ledger(
    ledger: Optional[Any], ledger_writer: Optional[Any], audit_ledger: Optional[Any]
) -> Optional[Any]:
    for candidate in (ledger, ledger_writer, audit_ledger):
        if candidate is not None:
            return candidate
    return None


def _normalise_plugins(plugins: Optional[Iterable[Any]]) -> List[Any]:
    if not plugins:
        return []
    return [plugin for plugin in plugins]


@dataclass
class Orchestrator:
    """Coordinates task scheduling, execution state transitions and observability."""

    task_scheduler: Optional[Any] = None
    scheduler: Optional[Any] = None
    state_machine: Optional[Any] = None
    state_machine_factory: Optional[Callable[[], Any]] = None
    ledger: Optional[Any] = None
    ledger_writer: Optional[Any] = None
    audit_ledger: Optional[Any] = None
    tracer: Optional[Any] = None
    trace: Optional[Any] = None
    plugins: Optional[Iterable[Any]] = None
    plugin_registry: Optional[Iterable[Any]] = None
    plugin_loader: Optional[Any] = None
    plugin_specs: Optional[Sequence[str]] = None
    _loaded_plugins: List[Any] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._scheduler = self.scheduler or self.task_scheduler
        if self._scheduler is None:
            self._scheduler = TaskScheduler({"tasks": []})

        if self.state_machine_factory is None:
            if self.state_machine is not None:
                self._state_machine_factory = lambda: self.state_machine
            else:
                self._state_machine_factory = TaskStateMachine
        else:
            self._state_machine_factory = self.state_machine_factory

        self._ledger = _resolve_ledger(self.ledger, self.ledger_writer, self.audit_ledger)
        self._tracer = self.trace or self.tracer

        plugin_candidates: List[Any] = []
        for collection in (self.plugins, self.plugin_registry):
            plugin_candidates.extend(_normalise_plugins(collection))

        if self.plugin_loader and self.plugin_specs:
            for spec in self.plugin_specs:
                try:
                    plugin_candidates.append(self.plugin_loader.load(spec))
                except Exception as exc:  # pragma: no cover - defensive
                    plugin_candidates.append(exc)

        self._loaded_plugins = plugin_candidates

    # ------------------------------------------------------------------
    # Public API
    def run_workflow(
        self,
        task_graph: Optional[Mapping[str, Any]] = None,
        execution_plan: Optional[Any] = None,
        plan: Optional[Any] = None,
        request: Optional[Mapping[str, Any]] = None,
        workflow_request: Optional[Mapping[str, Any]] = None,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Execute a workflow and emit trace metadata to the ledger."""

        request_payload = workflow_request or request or {}
        trace_id = trace_id or request_payload.get("trace_id") or new_ulid()
        task_graph = task_graph or request_payload.get("task_graph") or {}

        execution_plan = (
            execution_plan
            or plan
            or request_payload.get("execution_plan")
            or kwargs.get("execution_plan")
        )

        if not execution_plan and task_graph:
            execution_plan = self._build_plan(task_graph)
        elif not execution_plan:
            raise ValueError("An execution plan or task graph must be supplied")

        waves = self._coerce_plan(execution_plan)

        results: List[Mapping[str, Any]] = []
        tracer = self._tracer or nullcontext()
        span_cm = tracer.start_as_current_span("acms.orchestrator.run") if hasattr(tracer, "start_as_current_span") else nullcontext()

        with span_cm:
            for plugin in self._loaded_plugins:
                hook = getattr(plugin, "before_workflow", None)
                if callable(hook):
                    hook(task_graph=task_graph, trace_id=trace_id)

            for wave_index, wave in enumerate(waves):
                for entry in wave:
                    task_payload = self._coerce_task(entry)
                    execution = self._initialise_execution(task_payload, trace_id)
                    machine = self._state_machine_factory()

                    self._advance_state(machine, execution, ExecutionState.RUNNING)
                    self._advance_state(machine, execution, ExecutionState.COMPLETED)

                    record = {
                        "trace_id": trace_id,
                        "task_id": task_payload["id"],
                        "wave": wave_index,
                        "state": execution.state.value,
                    }
                    self._write_ledger(record)
                    results.append(record)

                    for plugin in self._loaded_plugins:
                        hook = getattr(plugin, "after_task", None)
                        if callable(hook):
                            hook(task=task_payload, execution=record)

            for plugin in self._loaded_plugins:
                hook = getattr(plugin, "after_workflow", None)
                if callable(hook):
                    hook(results=results, trace_id=trace_id)

        return {
            "trace_id": trace_id,
            "waves": [[task["id"] for task in wave] for wave in waves],
            "ledger": results,
        }

    def run(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        """Alias for :meth:`run_workflow` to support varied call sites."""

        return self.run_workflow(*args, **kwargs)

    def execute(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        """Alias for :meth:`run_workflow` to match alternate naming schemes."""

        return self.run_workflow(*args, **kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    def _advance_state(
        self, machine: Any, execution: TaskExecution, target: ExecutionState
    ) -> None:
        """Attempt to drive ``machine`` to ``target`` while updating ``execution``."""

        try:
            if hasattr(machine, "transition"):
                machine.transition(target)
            execution.transition_to(target)
        except IllegalTransition:
            # If the custom machine rejects the transition we still record the attempt
            pass

    def _build_plan(self, task_graph: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a plan using the configured scheduler."""

        scheduler = self._scheduler
        if isinstance(scheduler, TaskScheduler):
            return TaskScheduler(task_graph).get_execution_plan()
        if hasattr(scheduler, "get_execution_plan"):
            return scheduler.get_execution_plan()
        if hasattr(scheduler, "topological_sort"):
            waves = scheduler.topological_sort()
            return {"waves": waves}

        derived = TaskScheduler(task_graph)
        return derived.get_execution_plan()

    def _coerce_plan(self, plan: Any) -> List[List[Mapping[str, Any]]]:
        """Normalise the plan into a list of execution waves."""

        if plan is None:
            return []

        if isinstance(plan, Mapping):
            if "waves" in plan:
                waves = plan["waves"]
            elif "tasks" in plan:
                waves = [[task] for task in plan["tasks"]]
            else:
                waves = [plan]
        elif isinstance(plan, Sequence) and not isinstance(plan, (str, bytes)):
            waves = plan
        else:
            waves = [[plan]]

        normalised: List[List[Mapping[str, Any]]] = []
        for wave in waves:
            if isinstance(wave, Mapping):
                normalised.append([self._coerce_task(wave)])
                continue

            if not isinstance(wave, Iterable) or isinstance(wave, (str, bytes)):
                normalised.append([self._coerce_task(wave)])
                continue

            normalised.append([self._coerce_task(task) for task in wave])
        return normalised

    def _coerce_task(self, task: Any) -> Mapping[str, Any]:
        if isinstance(task, Mapping):
            if "id" not in task:
                raise KeyError("Task entries must include an 'id'")
            return dict(task)
        return {"id": str(task)}

    def _initialise_execution(self, task: Mapping[str, Any], trace_id: str) -> TaskExecution:
        dependencies = task.get("dependencies")
        if dependencies is None:
            deps_list: List[str] = []
        elif isinstance(dependencies, Iterable) and not isinstance(dependencies, (str, bytes)):
            deps_list = [str(dep) for dep in dependencies]
        else:
            deps_list = [str(dependencies)]

        execution = TaskExecution(
            task_id=str(task["id"]),
            dependencies=deps_list,
            trace_id=trace_id,
        )
        return execution

    def _write_ledger(self, entry: Mapping[str, Any]) -> None:
        if self._ledger is None:
            return

        if isinstance(self._ledger, Ledger):
            self._ledger.log("task.completed", entry, correlation_id=entry.get("trace_id"))
            return

        writer = getattr(self._ledger, "append", None) or getattr(self._ledger, "write", None)
        if callable(writer):
            writer(entry)
