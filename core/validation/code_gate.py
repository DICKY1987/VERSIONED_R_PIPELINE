"""
Code Gate — Validation Router
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
Routes approved/rejected by gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .linters import LintResult
from .security_scanner import SecurityResult


class GateStatus(str, Enum):
    """Enumeration describing the overall status produced by the validation gate."""

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class GateReport:
    """Aggregate report returned by the :class:`CodeGate`."""

    status: GateStatus
    lint_results: Sequence[LintResult]
    security_results: Sequence[SecurityResult]

    @property
    def approved(self) -> bool:
        """Convenience flag mirroring whether the gate approved the change."""

        return self.status is GateStatus.APPROVED


class CodeGate:
    """Coordinate linting and security validation for the ACMS pipeline."""

    def __init__(
        self,
        lint_runner,
        security_runner,
    ) -> None:
        self._lint_runner = lint_runner
        self._security_runner = security_runner

    def evaluate(self) -> GateReport:
        """Run all validation gates and produce a consolidated report."""

        lint_results = list(self._run_linters())
        security_results = list(self._run_security_scans())
        status = GateStatus.APPROVED
        if any(not result.succeeded for result in lint_results + security_results):
            status = GateStatus.REJECTED
        return GateReport(status=status, lint_results=lint_results, security_results=security_results)

    def _run_linters(self) -> Iterable[LintResult]:
        """Execute the configured lint runner and yield its results."""

        results = self._lint_runner.run()
        _validate_result_collection(results, "lint")
        return results

    def _run_security_scans(self) -> Iterable[SecurityResult]:
        """Execute the configured security runner and yield its results."""

        results = self._security_runner.run()
        _validate_result_collection(results, "security")
        return results


def _validate_result_collection(results: Sequence, label: str) -> None:
    """Guard against runners returning unsupported result types."""

    if not isinstance(results, Sequence):
        raise TypeError(f"Expected {label} runner to return a sequence, got {type(results).__name__}")


__all__ = ["CodeGate", "GateReport", "GateStatus"]
