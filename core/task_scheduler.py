"""Dependency-aware task scheduler for ACMS workflows."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, Iterator, List, Mapping, Sequence

__all__ = ["CycleError", "TaskScheduler", "topo_sort"]


class CycleError(RuntimeError):
    """Raised when the task graph contains a cycle."""


@dataclass(frozen=True)
class _Task:
    """Internal representation of a task with deterministic ordering helpers."""

    id: str
    payload: Mapping[str, object]

    @property
    def priority(self) -> int:
        value = self.payload.get("priority", 0)
        try:
            return int(value)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - defensive
            return 0

    def sort_key(self) -> tuple[int, str]:
        return (-self.priority, self.id)


class TaskScheduler:
    """Topologically sort ACMS task graphs while preserving stability."""

    def __init__(self, task_graph: Mapping[str, Sequence[Mapping[str, object]]]):
        if "tasks" not in task_graph:
            raise KeyError("Task graph must include a 'tasks' collection")

        tasks = []
        for task in task_graph["tasks"]:
            if "id" not in task:
                raise KeyError("Each task requires an 'id' field")
            tasks.append(_Task(str(task["id"]), dict(task)))

        self._task_index: Dict[str, _Task] = {task.id: task for task in tasks}
        self._graph: Dict[str, List[str]] = defaultdict(list)
        self._indegrees: Dict[str, int] = defaultdict(int)

        for task in tasks:
            dependencies = task.payload.get("dependencies", [])
            if not isinstance(dependencies, Iterable):
                raise TypeError(f"Dependencies for task {task.id!r} must be iterable")
            for dependency in dependencies:
                dep_name = str(dependency)
                if dep_name not in self._task_index:
                    raise KeyError(f"Unknown dependency {dep_name!r} referenced by {task.id!r}")
                self._graph[dep_name].append(task.id)
                self._indegrees[task.id] += 1

        for task in tasks:
            self._indegrees.setdefault(task.id, 0)
            self._graph.setdefault(task.id, [])

    @property
    def tasks(self) -> Mapping[str, Mapping[str, object]]:
        """Return a mapping of task id to task payload."""

        return {task_id: dict(task.payload) for task_id, task in self._task_index.items()}

    def topological_sort(self) -> List[List[str]]:
        """Return execution waves honouring dependency constraints."""

        indegrees = dict(self._indegrees)
        ready = [
            self._task_index[task_id]
            for task_id, degree in indegrees.items()
            if degree == 0
        ]
        ready.sort(key=_Task.sort_key)
        queue: Deque[_Task] = deque(ready)
        waves: List[List[str]] = []
        visited = 0

        while queue:
            wave: List[_Task] = []
            wave_size = len(queue)
            for _ in range(wave_size):
                current = queue.popleft()
                wave.append(current)
                for successor in self._graph[current.id]:
                    indegrees[successor] -= 1
                    if indegrees[successor] == 0:
                        queue.append(self._task_index[successor])
                queue = deque(sorted(queue, key=_Task.sort_key))

            visited += len(wave)
            waves.append([task.id for task in wave])

        if visited != len(self._task_index):
            raise CycleError("Graph has at least one cycle")

        return waves

    def iter_execution_order(self) -> Iterator[Mapping[str, object]]:
        """Yield tasks in dependency order as a flat sequence."""

        for wave in self.topological_sort():
            for task_id in wave:
                yield dict(self._task_index[task_id].payload)

    def get_execution_plan(self) -> Mapping[str, object]:
        """Return a serialisable execution plan structure."""

        waves = self.topological_sort()
        return {
            "waves": waves,
            "tasks": [dict(self._task_index[task_id].payload) for wave in waves for task_id in wave],
        }


def topo_sort(tasks: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
    """Convenience wrapper returning a flat topological order for ``tasks``."""

    scheduler = TaskScheduler({"tasks": list(tasks)})
    return list(scheduler.iter_execution_order())
