"""
Git Worktree Manager
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


class WorktreeManagerError(RuntimeError):
    """Raised when git worktree operations fail or are misused."""


@dataclass(frozen=True)
class WorktreeInfo:
    """Metadata describing a configured git worktree."""

    path: Path
    branch: Optional[str]
    revision: str

    def is_detached(self) -> bool:
        """Return ``True`` when the worktree is attached to a detached HEAD."""

        return self.branch is None


class WorktreeManager:
    """High-level helper for deterministic git worktree management.

    The manager wraps ``git worktree`` commands to provide predictable,
    testable behaviour that aligns with ACMS isolation requirements.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self._validate_repository()

    def _validate_repository(self) -> None:
        git_dir = self.repo_root / ".git"
        if not git_dir.exists():
            raise WorktreeManagerError(
                f"{self.repo_root} is not a git repository (missing .git directory)"
            )

    def _run_git(
        self,
        *args: str,
        cwd: Optional[Path] = None,
        capture_output: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        command = ["git", "-C", str(cwd or self.repo_root), *args]
        try:
            return subprocess.run(  # noqa: PLW1510 (stdout/err intentionally configurable)
                command,
                check=check,
                capture_output=capture_output,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise WorktreeManagerError(
                f"git command failed: {' '.join(command)}\n{exc.stdout or ''}{exc.stderr or ''}"
            ) from exc

    def list_worktrees(self) -> List[WorktreeInfo]:
        """Return every configured worktree parsed from porcelain output."""

        result = self._run_git(
            "worktree", "list", "--porcelain", capture_output=True
        )
        entries: List[WorktreeInfo] = []
        current: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                if current:
                    entries.append(self._build_info(current))
                    current = {}
                continue
            key, _, value = line.partition(" ")
            current[key] = value.strip()
        if current:
            entries.append(self._build_info(current))
        return entries

    def _build_info(self, payload: dict[str, str]) -> WorktreeInfo:
        path = Path(payload["worktree"]).resolve()
        branch = self._normalize_branch(payload.get("branch"))
        revision = payload.get("HEAD", "")
        return WorktreeInfo(path=path, branch=branch, revision=revision)

    @staticmethod
    def _normalize_branch(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        if raw.startswith("refs/heads/"):
            return raw.split("/", maxsplit=2)[-1]
        if raw == "(detached)":
            return None
        return raw or None

    def worktree_exists(self, worktree_path: Path) -> bool:
        worktree_path = Path(worktree_path).resolve()
        return any(info.path == worktree_path for info in self.list_worktrees())

    def add_worktree(
        self,
        worktree_path: Path,
        branch: str,
        base: Optional[str] = None,
        force: bool = False,
    ) -> Path:
        """Create a worktree at ``worktree_path``.

        When ``base`` is provided a new branch is created from the specified
        reference using ``-b``. Otherwise the worktree is attached to the
        existing ``branch``.
        """

        worktree_path = Path(worktree_path).resolve()
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        args: list[str] = ["worktree", "add"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))
        if base and base != branch:
            args.extend(["-b", branch, base])
        else:
            args.append(branch)
        self._run_git(*args)
        return worktree_path

    def remove_worktree(self, worktree_path: Path, force: bool = False) -> None:
        """Remove the worktree located at ``worktree_path``."""

        worktree_path = Path(worktree_path).resolve()
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))
        self._run_git(*args)

    def prune(self) -> None:
        """Prune stale worktree references."""

        self._run_git("worktree", "prune")

    def ensure_clean_worktree(self, worktree_path: Path) -> None:
        """Raise :class:`WorktreeManagerError` when the worktree is dirty."""

        worktree_path = Path(worktree_path).resolve()
        result = self._run_git(
            "status", "--porcelain", cwd=worktree_path, capture_output=True
        )
        if result.stdout.strip():
            raise WorktreeManagerError(
                f"Worktree {worktree_path} has uncommitted changes"
            )

    def iter_branch_worktrees(self, branch: str) -> Iterable[WorktreeInfo]:
        """Yield worktrees attached to ``branch``."""

        for info in self.list_worktrees():
            if info.branch == branch:
                yield info
