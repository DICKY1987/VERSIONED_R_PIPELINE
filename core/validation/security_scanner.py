"""Security scanning helpers for validation workflows."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

__all__ = ["SecurityResult", "SecurityScanner"]


@dataclass(frozen=True)
class SecurityResult:
    """Result of running an individual security scanner."""

    tool: str
    command: Sequence[str]
    succeeded: bool
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        """Return combined stdout and stderr output."""

        return "\n".join(filter(None, (self.stdout.strip(), self.stderr.strip()))).strip()


class SecurityScanner:
    """Execute security scanners defined by the operating contract."""

    def __init__(
        self,
        tools: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._tools: MutableMapping[str, Sequence[str]] = dict(tools or _DEFAULT_TOOLS)

    def available_tools(self) -> Sequence[str]:
        """Return the configured tool names."""

        return tuple(sorted(self._tools))

    def run(self, tool: str, paths: Iterable[str]) -> SecurityResult:
        """Execute ``tool`` with ``paths`` returning a :class:`SecurityResult`."""

        if tool not in self._tools:
            raise KeyError(f"Unknown security tool: {tool}")

        command = list(self._tools[tool]) + list(paths)
        binary = command[0]
        if shutil.which(binary) is None:
            raise FileNotFoundError(f"Required security tool '{binary}' not found on PATH")

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        return SecurityResult(
            tool=tool,
            command=tuple(command),
            succeeded=completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


_DEFAULT_TOOLS: Mapping[str, Sequence[str]] = {
    "bandit": ("bandit", "-q", "-r"),
    "gitleaks": ("gitleaks", "detect", "--no-banner"),
}
