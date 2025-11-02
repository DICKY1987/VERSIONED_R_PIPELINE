"""
Linting Integration
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
Black/Ruff/mypy/pylint orchestration utilities for the ACMS validation layer.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, List, Mapping, MutableMapping, Optional, Sequence

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LintCommand:
    """Describe a lint command that should be executed as part of the lint suite."""

    name: str
    argv: Sequence[str]
    env: Optional[Mapping[str, str]] = None


@dataclass
class LintResult:
    """Container describing the outcome of executing a lint command."""

    command: LintCommand
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the lint command completed successfully."""

        return self.returncode == 0


Runner = Callable[[Sequence[str], MutableMapping[str, str] | None], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str], env: MutableMapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Execute a lint command using :func:`subprocess.run`.

    Commands are invoked with ``check=False`` so that failures are reported via
    ``returncode`` instead of raising ``CalledProcessError``. ``text=True`` is used to
    ensure output is decoded to ``str`` consistently across platforms.
    """

    LOGGER.debug("Executing lint command", extra={"argv": list(argv)})
    return subprocess.run(  # noqa: PLW1510 - deliberate delegation to subprocess
        argv,
        env=dict(env) if env else None,
        check=False,
        capture_output=True,
        text=True,
    )


class LintSuite:
    """Aggregate a collection of :class:`LintCommand` objects and execute them sequentially."""

    def __init__(
        self,
        commands: Iterable[LintCommand],
        *,
        runner: Runner | None = None,
    ) -> None:
        self._commands = list(commands)
        if not self._commands:
            raise ValueError("LintSuite requires at least one command")
        self._runner: Runner = runner or _default_runner

    @property
    def commands(self) -> List[LintCommand]:
        """Return an immutable snapshot of the configured lint commands."""

        return list(self._commands)

    def run(self) -> List[LintResult]:
        """Execute all configured lint commands, returning their results in order."""

        results: List[LintResult] = []
        for command in self._commands:
            LOGGER.info("Running linter", extra={"linter": command.name})
            completed = self._runner(command.argv, command.env and dict(command.env))
            result = LintResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            if result.succeeded:
                LOGGER.debug(
                    "Linter succeeded",
                    extra={"linter": command.name, "stdout": result.stdout.strip()},
                )
            else:
                LOGGER.warning(
                    "Linter failed",
                    extra={
                        "linter": command.name,
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                    },
                )
            results.append(result)
        return results


__all__ = ["LintCommand", "LintResult", "LintSuite"]
