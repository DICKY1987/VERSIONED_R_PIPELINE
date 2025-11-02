"""
Worktree Synchronization
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class WorktreeSyncError(RuntimeError):
    """Raised when worktree synchronisation fails."""


def _run_git(
    location: Path,
    *args: str,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(Path(location).resolve()), *args]
    try:
        return subprocess.run(  # noqa: PLW1510 - managed capturing
            command,
            check=check,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise WorktreeSyncError(
            f"git command failed: {' '.join(command)}\n{exc.stdout or ''}{exc.stderr or ''}"
        ) from exc


def fetch_remote(repo_root: Path, remote: str = "origin") -> None:
    """Fetch updates from ``remote`` for the repository at ``repo_root``."""

    _run_git(repo_root, "fetch", remote)


def ensure_remote_branch(repo_root: Path, remote: str, branch: str) -> None:
    """Validate that ``remote/branch`` exists before attempting a rebase."""

    result = _run_git(
        repo_root,
        "ls-remote",
        "--heads",
        remote,
        branch,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise WorktreeSyncError(
            f"Remote branch {remote}/{branch} does not exist or is unreachable"
        )


def ensure_clean(path: Path) -> None:
    """Ensure the worktree at ``path`` has no staged or unstaged changes."""

    result = _run_git(path, "status", "--porcelain", capture_output=True)
    if result.stdout.strip():
        raise WorktreeSyncError(f"Worktree {path} has uncommitted changes")


def rebase_onto(worktree_path: Path, upstream_ref: str) -> None:
    """Rebase the branch checked out in ``worktree_path`` onto ``upstream_ref``."""

    _run_git(worktree_path, "rebase", upstream_ref)


def hard_reset(worktree_path: Path, ref: str) -> None:
    """Forcefully reset the worktree to ``ref``."""

    _run_git(worktree_path, "reset", "--hard", ref)


def synchronize_worktree(
    repo_root: Path,
    worktree_path: Path,
    remote: str = "origin",
    upstream_branch: str = "main",
    fetch: bool = True,
    clean_check: bool = True,
    allow_reset: bool = False,
) -> None:
    """Synchronise ``worktree_path`` with ``remote/upstream_branch``.

    The function optionally fetches updates, verifies that the remote branch
    exists, enforces cleanliness, and rebases the worktree. When
    ``allow_reset`` is ``True`` the function will perform a hard reset instead
    of a rebase when the latter fails (useful for short-lived throwaway
    worktrees).
    """

    repo_root = Path(repo_root).resolve()
    worktree_path = Path(worktree_path).resolve()

    if fetch:
        fetch_remote(repo_root, remote)

    ensure_remote_branch(repo_root, remote, upstream_branch)

    upstream_ref = f"{remote}/{upstream_branch}"

    if clean_check:
        ensure_clean(worktree_path)

    try:
        rebase_onto(worktree_path, upstream_ref)
    except WorktreeSyncError:
        if not allow_reset:
            raise
        hard_reset(worktree_path, upstream_ref)


def current_revision(path: Path) -> str:
    """Return the ``HEAD`` revision of the worktree at ``path``."""

    result = _run_git(path, "rev-parse", "HEAD", capture_output=True)
    return result.stdout.strip()


def remote_revision(repo_root: Path, remote: str, branch: str) -> Optional[str]:
    """Return the commit hash for ``remote/branch`` if it exists."""

    result = _run_git(
        repo_root,
        "rev-parse",
        "--verify",
        f"{remote}/{branch}",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()
