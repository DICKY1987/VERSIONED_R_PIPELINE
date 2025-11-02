"""Plugin package exposing shared helper utilities for ACMS extensions."""
from __future__ import annotations

from importlib import resources as _resources
from pathlib import Path
from typing import Iterable

__all__ = ["discover_specs"]


def discover_specs(root: str | Path | None = None) -> Iterable[Path]:
    """Yield plugin specification files beneath ``root``.

    When ``root`` is omitted the plugins package directory is used. Only
    ``plugin.spec.json`` files located directly within plugin folders are
    returned, keeping discovery deterministic for validation scripts.
    """

    if root is None:
        with _resources.as_file(_resources.files(__name__)) as package_dir:
            root_path = package_dir
    else:
        root_path = Path(root)

    if not root_path.exists():
        return []

    specs: list[Path] = []
    for entry in root_path.iterdir():
        if entry.is_dir():
            candidate = entry / "plugin.spec.json"
            if candidate.exists():
                specs.append(candidate)
    return tuple(sorted(specs))
