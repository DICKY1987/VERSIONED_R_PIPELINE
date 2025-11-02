"""ACMS Task Scheduler - DAG Implementation
Version: 1.0.0
Date: 2025-11-02
Implements: Topological sort with deterministic ordering
Owner: Platform.Engineering
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, MutableMapping


class CycleError(Exception):
    """Raised when the dependency graph contains a cycle."""


class TaskScheduler:
    """Topological sort + parallel group execution for task DAG."""

    def __init__(self, task_graph: Dict):
        if "tasks" not in task_graph:
            raise ValueError("task_graph must contain a 'tasks' collection")
        self.tasks: Dict[str, Dict] = {t["id"]: dict(t) for t in task_graph["tasks"]}
        self.graph: Dict[str, List[str]] = self._build_adjacency_list()

    def _build_adjacency_list(self) -> Dict[str, List[str]]:
        """Build an adjacency list keyed by dependency identifiers."""

        graph: Dict[str, List[str]] = defaultdict(list)
        for task_id, task in self.tasks.items():
            for dep in task.get("dependencies", []):
                if dep not in self.tasks:
                    raise KeyError(f"Dependency '{dep}' referenced by '{task_id}' is undefined")
                graph[dep].append(task_id)
        return graph

    def _initial_in_degree(self) -> MutableMapping[str, int]:
        """Compute the in-degree for each task."""

        in_degree: MutableMapping[str, int] = defaultdict(int)
        for task_id in self.tasks:
            in_degree.setdefault(task_id, 0)
        for task_id, task in self.tasks.items():
            for dep in task.get("dependencies", []):
                in_degree[task_id] += 1
        return in_degree

    def _sort_key(self, task_id: str):
        task = self.tasks[task_id]
        priority = task.get("priority", 0)
        return (-priority, task_id)

    def topological_sort(self) -> List[List[str]]:
        """Return execution waves that can run in parallel."""

        in_degree = self._initial_in_degree()
        ready = sorted([task_id for task_id, deg in in_degree.items() if deg == 0], key=self._sort_key)
        waves: List[List[str]] = []
        visited = 0

        while ready:
            current_wave = list(ready)
            waves.append(current_wave)
            visited += len(current_wave)

            next_ready: List[str] = []
            for task_id in current_wave:
                for dependent in self.graph.get(task_id, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_ready.append(dependent)

            ready = sorted(next_ready, key=self._sort_key)

        if visited != len(self.tasks):
            raise CycleError("Cycle detected in task graph")

        return waves

    def get_execution_plan(self) -> Dict[str, object]:
        """Generate execution plan metadata for orchestration."""

        waves = self.topological_sort()
        return {
            "total_tasks": len(self.tasks),
            "total_waves": len(waves),
            "max_parallelism": max((len(wave) for wave in waves), default=0),
            "execution_order": [
                {
                    "wave": index,
                    "tasks": wave,
                    "can_parallel": len(wave) > 1,
                }
                for index, wave in enumerate(waves, start=1)
            ],
        }

    def iter_dependencies(self, task_id: str) -> Iterable[str]:
        """Yield the dependencies configured for ``task_id``."""

        try:
            task = self.tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"Unknown task '{task_id}'") from exc
        return tuple(task.get("dependencies", []))


def topo_sort(tasks: List[dict]) -> List[dict]:
    """Compatibility wrapper returning a linearised execution order."""

    scheduler = TaskScheduler({"tasks": tasks})
    ordered_tasks: List[dict] = []
    for wave in scheduler.topological_sort():
        for task_id in wave:
            ordered_tasks.append(scheduler.tasks[task_id])
    return ordered_tasks
