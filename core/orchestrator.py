"""ACMS Main Pipeline Orchestrator
Version: 1.0.0
Date: 2025-11-02
Entry Point: Main execution controller
Owner: Platform.Engineering
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional

from .state_machine import ExecutionState, TaskExecution, TaskStateMachine
from .task_scheduler import TaskScheduler


@dataclass
class TaskResult:
    """Container for task execution metadata."""

    task_id: str
    state: ExecutionState
    attempt: int
    trace_id: str
    output: Optional[object] = None
    error: Optional[BaseException] = None


class Orchestrator:
    """Coordinate execution of tasks defined in a DAG."""

    def __init__(
        self,
        task_graph: Mapping,
        executor: Callable[[str, TaskExecution], object],
    ) -> None:
        self.scheduler = TaskScheduler(task_graph)
        self.executor = executor
        self.state_machines: Dict[str, TaskStateMachine] = {}
        self.results: MutableMapping[str, TaskResult] = {}

        for task_id, task_data in self.scheduler.tasks.items():
            execution = TaskExecution.create(
                task_id,
                dependencies=task_data.get("dependencies", []),
                max_attempts=task_data.get("max_attempts", 3),
                metadata={k: v for k, v in task_data.items() if k not in {"id", "dependencies", "max_attempts"}},
            )
            self.state_machines[task_id] = TaskStateMachine(execution)

    def _completed_tasks(self) -> List[str]:
        return [tid for tid, result in self.results.items() if result.state == ExecutionState.COMPLETED]

    def run(self) -> Dict[str, TaskResult]:
        """Execute the DAG respecting dependencies and retry policy."""

        plan = self.scheduler.get_execution_plan()
        for wave in plan["execution_order"]:
            for task_id in wave["tasks"]:
                machine = self.state_machines[task_id]
                machine.ensure_dependencies_satisfied(self._completed_tasks())
                attempt = 0

                while attempt < machine.task.max_attempts:
                    attempt += 1
                    try:
                        machine.start()
                        output = self.executor(task_id, machine.task)
                        machine.complete()
                        self.results[task_id] = TaskResult(
                            task_id=task_id,
                            state=machine.task.state,
                            attempt=attempt,
                            trace_id=machine.task.trace_id,
                            output=output,
                        )
                        break
                    except Exception as exc:  # pragma: no cover - re-raised condition handled below
                        machine.fail()
                        if attempt >= machine.task.max_attempts:
                            self.results[task_id] = TaskResult(
                                task_id=task_id,
                                state=machine.task.state,
                                attempt=attempt,
                                trace_id=machine.task.trace_id,
                                error=exc,
                            )
                            raise
                        machine.reset()
        return dict(self.results)

    def snapshot(self) -> List[Dict[str, object]]:
        """Return a JSON-serialisable snapshot of orchestration state."""

        return [machine.to_dict() for machine in self.state_machines.values()]

    def completed(self) -> Iterable[str]:
        """Yield identifiers for completed tasks."""

        for task_id, result in self.results.items():
            if result.state == ExecutionState.COMPLETED:
                yield task_id
