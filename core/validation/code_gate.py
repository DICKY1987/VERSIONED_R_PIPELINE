"""Quality gate orchestration for ACMS validation workflows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

from .linters import LintRunner
from .security_scanner import SecurityScanner

__all__ = [
    "GateStatus",
    "GateReport",
    "GateSuiteReport",
    "run_quality_gates",
]


class GateStatus(str, Enum):
    """Enumerates the possible outcomes of a validation gate."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class GateReport:
    """Individual gate execution report."""

    name: str
    status: GateStatus
    details: str = ""

    def is_successful(self) -> bool:
        """Return ``True`` when the gate passed or was explicitly skipped."""

        return self.status in {GateStatus.PASSED, GateStatus.SKIPPED}


@dataclass(frozen=True)
class GateSuiteReport:
    """Aggregate report produced by :func:`run_quality_gates`."""

    reports: Sequence[GateReport]
    passed: bool
    record_path: Path


def run_quality_gates(
    paths: Iterable[str],
    coverage_percent: float,
    *,
    coverage_threshold: float = 80.0,
    lint_tools: Sequence[str] = ("black", "ruff", "mypy", "pylint"),
    security_tools: Sequence[str] = ("bandit", "gitleaks"),
    runs_root: str | Path = ".runs",
) -> GateSuiteReport:
    """Execute lint, security and coverage gates for ``paths``.

    The function runs the configured tool suites and writes a timestamped
    summary file beneath ``runs_root`` capturing the overall outcome. Missing
    tools do not cause failure but are reported as skipped gates so the output
    remains actionable in constrained CI environments.
    """

    lint_runner = LintRunner()
    security_runner = SecurityScanner()
    reports: list[GateReport] = []

    for tool in lint_tools:
        try:
            result = lint_runner.run(tool, paths)
            status = GateStatus.PASSED if result.succeeded else GateStatus.FAILED
            details = result.output
        except FileNotFoundError as exc:
            status = GateStatus.SKIPPED
            details = str(exc)
        reports.append(GateReport(name=f"lint:{tool}", status=status, details=details))

    for tool in security_tools:
        try:
            result = security_runner.run(tool, paths)
            status = GateStatus.PASSED if result.succeeded else GateStatus.FAILED
            details = result.output
        except FileNotFoundError as exc:
            status = GateStatus.SKIPPED
            details = str(exc)
        reports.append(GateReport(name=f"security:{tool}", status=status, details=details))

    coverage_status = (
        GateStatus.PASSED if coverage_percent >= coverage_threshold else GateStatus.FAILED
    )
    reports.append(
        GateReport(
            name="coverage",
            status=coverage_status,
            details=(
                f"coverage={coverage_percent:.2f}% threshold={coverage_threshold:.2f}%"
            ),
        )
    )

    overall_passed = all(report.is_successful() for report in reports)
    record_path = _record_gate_results(reports, overall_passed, Path(runs_root))
    return GateSuiteReport(reports=tuple(reports), passed=overall_passed, record_path=record_path)


def _record_gate_results(
    reports: Sequence[GateReport], passed: bool, runs_root: Path
) -> Path:
    runs_root.mkdir(parents=True, exist_ok=True)
    target_dir = runs_root / ("approved" if passed else "rejected")
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_path = target_dir / f"quality_gates_{timestamp}.log"
    lines = [
        f"overall={GateStatus.PASSED.value if passed else GateStatus.FAILED.value}",
    ]
    for report in reports:
        lines.append(f"{report.name}:{report.status.value}:{report.details}")
    record_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return record_path
