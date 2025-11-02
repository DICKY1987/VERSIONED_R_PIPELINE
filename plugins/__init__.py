"""ACMS Plugins Module
Version: 1.0.0
Date: 2025-11-02
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

__all__ = ["discover_plugin_packages"]


def discover_plugin_packages(root: Path | None = None) -> Iterable[Path]:
    """Yield plugin package directories located below ``root``.

    Parameters
    ----------
    root:
        Optional root directory that contains plugin packages.  When omitted,
        the function assumes the ``plugins`` directory that sits next to the
        current module.
    """

    search_root = Path(root) if root is not None else Path(__file__).resolve().parent
    if not search_root.exists():
        return []
    return sorted(p for p in search_root.iterdir() if p.is_dir())
