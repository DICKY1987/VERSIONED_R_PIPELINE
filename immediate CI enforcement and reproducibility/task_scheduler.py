# core/task_scheduler.py
from __future__ import annotations
from typing import Dict, List, Set, Tuple

class CycleError(Exception):
    pass

def topo_sort(tasks: List[dict]) -> List[dict]:
    """
    Kahn-style topological sort with deterministic tie-breaking.
    Input items must have: id: str, dependencies: List[str], optional priority: int
    Tie-breaker: higher priority first, then id ascending.
    """
    # Build graph
    by_id: Dict[str, dict] = {t["id"]: t for t in tasks}
    indeg: Dict[str, int] = {t["id"]: 0 for t in tasks}
    adj: Dict[str, List[str]] = {t["id"]: [] for t in tasks}

    for t in tasks:
        for dep in t.get("dependencies", []):
            if dep not in by_id:
                raise KeyError(f"Unknown dependency: {dep}")
            indeg[t["id"]] += 1
            adj[dep].append(t["id"])

    # Start with nodes of indegree 0
    def sort_key(tid: str):
        prio = by_id[tid].get("priority", 0)
        return (-prio, tid)  # higher prio first, then id asc

    zero = sorted([tid for tid, d in indeg.items() if d == 0], key=sort_key)
    out: List[dict] = []

    while zero:
        tid = zero.pop(0)  # pop smallest (most preferred by sort_key)
        out.append(by_id[tid])
        for nxt in adj[tid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                # insert and resort to keep deterministic ordering
                zero.append(nxt)
                zero.sort(key=sort_key)

    if len(out) != len(tasks):
        raise CycleError("Graph has at least one cycle")
    return out
