"""
Security Scanning
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
bandit + gitleaks enforcement utilities for the ACMS validation layer.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Mapping, MutableMapping, Optional, Sequence

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecurityCommand:
    """Representation of a security scanning command invocation."""

    name: str
    argv: Sequence[str]
    env: Optional[Mapping[str, str]] = None
    expects_report: bool = False
    report_path: Optional[Path] = None


@dataclass
class SecurityResult:
    """Outcome from running a security scanning command."""

    command: SecurityCommand
    returncode: int
    stdout: str
    stderr: str
    findings: Optional[List[dict]] = None

    @property
    def succeeded(self) -> bool:
        """Return ``True`` if the command exit status indicates success."""

        return self.returncode == 0 and not self.findings


Runner = Callable[[Sequence[str], MutableMapping[str, str] | None], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str], env: MutableMapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Execute a security command via :func:`subprocess.run` with safe defaults."""

    LOGGER.debug("Executing security command", extra={"argv": list(argv)})
    return subprocess.run(  # noqa: PLW1510 - deliberate delegation to subprocess
        argv,
        env=dict(env) if env else None,
        check=False,
        capture_output=True,
        text=True,
    )


def _load_report(command: SecurityCommand) -> Optional[List[dict]]:
    """Load structured findings from a report file when requested."""

    if not command.expects_report or not command.report_path:
        return None
    try:
        report_data = command.report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        LOGGER.warning(
            "Expected security report missing",
            extra={"command": command.name, "path": str(command.report_path)},
        )
        return None
    try:
        payload = json.loads(report_data) if report_data.strip() else []
        if isinstance(payload, list):
            return payload
        LOGGER.error(
            "Unexpected report payload type",
            extra={"command": command.name, "type": type(payload).__name__},
        )
    except json.JSONDecodeError as exc:
        LOGGER.error(
            "Failed to decode security report",
            extra={"command": command.name, "error": str(exc)},
        )
    return None


class SecuritySuite:
    """Aggregate security scanning commands and execute them sequentially."""

    def __init__(
        self,
        commands: Iterable[SecurityCommand],
        *,
        runner: Runner | None = None,
    ) -> None:
        self._commands = list(commands)
        if not self._commands:
            raise ValueError("SecuritySuite requires at least one command")
        self._runner: Runner = runner or _default_runner

    @property
    def commands(self) -> List[SecurityCommand]:
        """Return a copy of the configured security commands."""

        return list(self._commands)

    def run(self) -> List[SecurityResult]:
        """Execute all configured security commands and return their results."""

        results: List[SecurityResult] = []
        for command in self._commands:
            LOGGER.info("Running security scan", extra={"scanner": command.name})
            completed = self._runner(command.argv, command.env and dict(command.env))
            findings = _load_report(command)
            result = SecurityResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                findings=findings,
            )
            if result.succeeded:
                LOGGER.debug(
                    "Security scan passed",
                    extra={"scanner": command.name, "stdout": result.stdout.strip()},
                )
            else:
                LOGGER.warning(
                    "Security scan failed",
                    extra={
                        "scanner": command.name,
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                        "findings": findings or [],
                    },
                )
            results.append(result)
        return results


__all__ = ["SecurityCommand", "SecurityResult", "SecuritySuite"]
