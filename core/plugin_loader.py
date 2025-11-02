"""Plugin discovery utilities for ACMS runtime integrations."""
from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from importlib import metadata
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence

__all__ = ["PluginLoader"]


class PluginLoader:
    """Load plugins from dotted paths, directories or entry points."""

    def __init__(
        self,
        search_paths: Optional[Iterable[str | Path]] = None,
        entry_point_groups: Optional[Sequence[str]] = None,
    ) -> None:
        self._search_paths = [Path(path) for path in search_paths or []]
        self._entry_point_groups = list(entry_point_groups or [])

    # ------------------------------------------------------------------
    # Discovery helpers
    def load(self, target: str) -> Any:
        """Load a plugin referenced via ``module:attribute`` or ``module`` path."""

        module_path, attribute = self._split_target(target)
        module = import_module(module_path)
        return getattr(module, attribute) if attribute else module

    def load_all(self, targets: Iterable[str]) -> List[Any]:
        """Load all plugins referenced by ``targets`` returning the resolved objects."""

        loaded: List[Any] = []
        for target in targets:
            try:
                loaded.append(self.load(target))
            except Exception as exc:  # pragma: no cover - defensive
                loaded.append(exc)
        return loaded

    def iter_entry_points(self) -> List[Any]:
        """Return entry points exposed under the configured namespaces."""

        groups = self._entry_point_groups or []
        discovered: List[Any] = []
        if not groups:
            return discovered

        eps = metadata.entry_points()
        for group in groups:
            candidates = eps.get(group) if isinstance(eps, Mapping) else eps.select(group=group)
            for entry_point in candidates:  # type: ignore[union-attr]
                try:
                    discovered.append(entry_point.load())
                except Exception as exc:  # pragma: no cover - defensive
                    discovered.append(exc)
        return discovered

    def walk_directory(self) -> List[ModuleType]:
        """Load python modules located within the configured search paths."""

        modules: List[ModuleType] = []
        for base_path in self._search_paths:
            if not base_path.exists():
                continue

            with _temporary_sys_path(base_path):
                for path in base_path.rglob("*.py"):
                    relative = path.relative_to(base_path).with_suffix("")
                    dotted = ".".join(relative.parts)
                    try:
                        modules.append(self.load(dotted))
                    except Exception:  # pragma: no cover - directory scanning is best-effort
                        continue
        return modules

    # ------------------------------------------------------------------
    @staticmethod
    def _split_target(target: str) -> tuple[str, str]:
        module, _, attribute = target.partition(":")
        return module, attribute


@contextmanager
def _temporary_sys_path(path: Path) -> Iterator[None]:
    path_str = str(path)
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(path_str)
            except ValueError:  # pragma: no cover - defensive cleanup
                pass
