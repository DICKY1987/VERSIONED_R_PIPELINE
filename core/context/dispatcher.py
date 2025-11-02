"""LLM tool dispatcher integrating the ACMS context broker.

Phase 4 of the ACMS execution plan introduces deterministic context
filtering for downstream LLM tooling. This module provides a thin
abstraction that:

1. Generates context manifests by invoking ``tools/context_broker.py``.
2. Dispatches tasks to Aider or Claude Code using the curated context.
3. Offers a dry-run mode for tests and validation pipelines.

The implementation is intentionally lightweight so it can operate inside
non-interactive automation environments.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

LOGGER = logging.getLogger("acms.llm_dispatcher")


@dataclass(frozen=True)
class DispatchResult:
    """Outcome of a dispatch request."""

    command: List[str]
    manifest_path: Path
    manifest: Dict[str, object]
    process: Optional[subprocess.CompletedProcess]


class ManifestGenerationError(RuntimeError):
    """Raised when the context broker manifest cannot be produced."""


class LLMToolDispatcher:
    """Dispatch tasks to LLM tooling with deterministic context."""

    def __init__(
        self,
        repo_root: Optional[Path | str] = None,
        broker_script: Optional[Path | str] = None,
        manifest_dir: Optional[Path | str] = None,
        run: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    ) -> None:
        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        default_broker = self.repo_root / "tools" / "context_broker.py"
        self.broker_script = Path(broker_script).resolve() if broker_script else default_broker
        self.manifest_dir = Path(manifest_dir or (self.repo_root / ".runs" / "manifests")).resolve()
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self._run = run or subprocess.run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def dispatch_to_aider(
        self,
        task_description: str,
        target_files: Sequence[str],
        keywords: Optional[Sequence[str]] = None,
        *,
        max_tokens: Optional[int] = None,
        include_tests: Optional[bool] = None,
        model: str = "deepseek-coder",
        extra_flags: Optional[Iterable[str]] = None,
        dry_run: bool = False,
    ) -> DispatchResult:
        """Invoke Aider with filtered context."""

        manifest, manifest_path = self._generate_manifest(
            task_type="edit",
            target_files=target_files,
            keywords=list(keywords or []),
            max_tokens=max_tokens,
            include_tests=include_tests,
        )

        cmd: List[str] = [
            "aider",
            "--model",
            model,
            "--message",
            task_description,
        ]

        for file_info in manifest.get("files", []):
            cmd.extend(["--read", self._normalise_path(file_info.get("path", ""))])

        if extra_flags:
            cmd.extend(list(extra_flags))

        process = None
        if not dry_run:
            LOGGER.info("Executing Aider with %d files", len(manifest.get("files", [])))
            process = self._run(cmd, capture_output=True, text=True, check=False)
        else:
            LOGGER.info("Aider dry-run: %s", " ".join(cmd))

        return DispatchResult(command=cmd, manifest_path=manifest_path, manifest=manifest, process=process)

    def dispatch_to_claude_code(
        self,
        task_description: str,
        target_files: Sequence[str],
        keywords: Optional[Sequence[str]] = None,
        *,
        max_tokens: Optional[int] = None,
        include_tests: Optional[bool] = None,
        extra_flags: Optional[Iterable[str]] = None,
        dry_run: bool = False,
    ) -> DispatchResult:
        """Invoke Claude Code CLI with filtered context."""

        manifest, manifest_path = self._generate_manifest(
            task_type="plan",
            target_files=target_files,
            keywords=list(keywords or []),
            max_tokens=max_tokens,
            include_tests=include_tests,
        )

        cmd: List[str] = [sys.executable or "python", "-m", "claude_code", "plan", "--no-tui"]
        for file_info in manifest.get("files", []):
            cmd.extend(["--file", self._normalise_path(file_info.get("path", ""))])

        if extra_flags:
            cmd.extend(list(extra_flags))

        cmd.append(task_description)

        process = None
        if not dry_run:
            LOGGER.info("Executing Claude Code with %d files", len(manifest.get("files", [])))
            process = self._run(cmd, capture_output=True, text=True, check=False)
        else:
            LOGGER.info("Claude Code dry-run: %s", " ".join(cmd))

        return DispatchResult(command=cmd, manifest_path=manifest_path, manifest=manifest, process=process)

    # ------------------------------------------------------------------
    # Manifest generation
    # ------------------------------------------------------------------
    def _generate_manifest(
        self,
        *,
        task_type: str,
        target_files: Sequence[str],
        keywords: Sequence[str],
        max_tokens: Optional[int],
        include_tests: Optional[bool],
    ) -> tuple[Dict[str, object], Path]:
        manifest_path = self._build_manifest_path(task_type)
        cmd: List[str] = [
            sys.executable or "python",
            str(self.broker_script),
            "--root",
            str(self.repo_root),
            "--out",
            str(manifest_path),
            "--task-type",
            task_type,
        ]

        for keyword in keywords:
            cmd.extend(["--keywords", keyword])

        for path in target_files:
            cmd.extend(["--target", str(path)])

        if max_tokens is not None:
            cmd.extend(["--max-tokens", str(max_tokens)])
        if include_tests is True:
            cmd.append("--include-tests")
        elif include_tests is False:
            cmd.append("--no-tests")

        LOGGER.debug("Generating context manifest via: %s", " ".join(cmd))
        result = self._run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ManifestGenerationError(result.stderr or result.stdout)

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ManifestGenerationError(f"Failed to read manifest {manifest_path}: {exc}") from exc

        return manifest, manifest_path

    def _build_manifest_path(self, task_type: str) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        safe_task = task_type.replace("/", "-")
        return self.manifest_dir / f"context_{safe_task}_{timestamp}.json"

    @staticmethod
    def _normalise_path(path: str) -> str:
        return Path(path).as_posix()


__all__ = [
    "DispatchResult",
    "ManifestGenerationError",
    "LLMToolDispatcher",
]
