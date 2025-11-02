"""
Worktree Management Tests
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.worktree.manager import WorktreeManager, WorktreeManagerError
from core.worktree import sync


def _run_git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)


@pytest.fixture()
def git_repository(tmp_path: Path) -> tuple[Path, Path]:
    remote_path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True, capture_output=True)

    repo_path = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
    _run_git(repo_path, "config", "user.email", "acms@example.com")
    _run_git(repo_path, "config", "user.name", "ACMS Bot")

    (repo_path / "README.md").write_text("seed\n")
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "initial commit")
    _run_git(repo_path, "branch", "-M", "main")
    _run_git(repo_path, "remote", "add", "origin", str(remote_path))
    _run_git(repo_path, "push", "-u", "origin", "main")

    return repo_path, remote_path


def test_worktree_lifecycle(tmp_path: Path, git_repository: tuple[Path, Path]) -> None:
    repo_path, _ = git_repository
    manager = WorktreeManager(repo_path)

    worktree_path = tmp_path / "worktrees" / "feature"
    manager.add_worktree(worktree_path, branch="feature/one", base="main")

    infos = manager.list_worktrees()
    feature_branches = {info.branch for info in infos}
    assert "feature/one" in feature_branches

    manager.ensure_clean_worktree(worktree_path)
    (worktree_path / "untracked.txt").write_text("dirty\n")
    with pytest.raises(WorktreeManagerError):
        manager.ensure_clean_worktree(worktree_path)
    (worktree_path / "untracked.txt").unlink()

    manager.remove_worktree(worktree_path)
    assert not worktree_path.exists()


def test_synchronize_worktree_rebases_on_remote(tmp_path: Path, git_repository: tuple[Path, Path]) -> None:
    repo_path, _ = git_repository
    manager = WorktreeManager(repo_path)

    worktree_path = tmp_path / "worktrees" / "feature-sync"
    manager.add_worktree(worktree_path, branch="feature/sync", base="main")

    feature_file = worktree_path / "feature.txt"
    feature_file.write_text("feature change\n")
    _run_git(worktree_path, "add", "feature.txt")
    _run_git(worktree_path, "commit", "-m", "feature work")

    base_file = repo_path / "base.txt"
    base_file.write_text("base change\n")
    _run_git(repo_path, "add", "base.txt")
    _run_git(repo_path, "commit", "-m", "main update")
    _run_git(repo_path, "push")

    sync.synchronize_worktree(repo_path, worktree_path)

    merge_base = _run_git(worktree_path, "merge-base", "HEAD", "origin/main").stdout.strip()
    upstream = _run_git(repo_path, "rev-parse", "origin/main").stdout.strip()
    assert merge_base == upstream


def test_synchronize_requires_existing_remote_branch(tmp_path: Path, git_repository: tuple[Path, Path]) -> None:
    repo_path, _ = git_repository
    manager = WorktreeManager(repo_path)
    worktree_path = tmp_path / "worktrees" / "feature-missing"
    manager.add_worktree(worktree_path, branch="feature/missing", base="main")

    with pytest.raises(sync.WorktreeSyncError):
        sync.synchronize_worktree(repo_root=repo_path, worktree_path=worktree_path, upstream_branch="non-existent")
