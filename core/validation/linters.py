"""Utilities for running lint tools as part of the validation gates."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

__all__ = ["LintResult", "LintRunner"]


@dataclass(frozen=True)
class LintResult:
    """Outcome of executing a single lint tool."""

    tool: str
    command: Sequence[str]
    succeeded: bool
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Return combined stdout/stderr for convenience."""

        return "\n".join(filter(None, (self.stdout.strip(), self.stderr.strip()))).strip()


class LintRunner:
    """Execute linters with a deterministic command mapping."""

    def __init__(
        self,
        tools: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._tools: MutableMapping[str, Sequence[str]] = dict(tools or _DEFAULT_TOOLS)

    def available_tools(self) -> Sequence[str]:
        """Return the configured tool names."""

        return tuple(sorted(self._tools))

    def run(self, tool: str, paths: Iterable[str]) -> LintResult:
        """Execute ``tool`` for the provided ``paths`` returning a :class:`LintResult`."""

        if tool not in self._tools:
            raise KeyError(f"Unknown lint tool: {tool}")

        command = list(self._tools[tool]) + list(paths)
        binary = command[0]
        if shutil.which(binary) is None:
            raise FileNotFoundError(f"Required lint tool '{binary}' not found on PATH")

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        return LintResult(
            tool=tool,
            command=tuple(command),
            succeeded=completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


_DEFAULT_TOOLS: Mapping[str, Sequence[str]] = {
    "black": ("black", "--check"),
    "ruff": ("ruff", "check"),
    "mypy": ("mypy",),
    "pylint": ("pylint",),
}
