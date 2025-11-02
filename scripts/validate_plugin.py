"""Validate ACMS plugin scaffolds to enforce contract compliance."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REQUIRED_ARTIFACTS = {
    "plugin.spec.json",
    "manifest.json",
    "policy_snapshot.json",
    "ledger_contract.json",
    "README_PLUGIN.md",
    "healthcheck.md",
}

REQUIRED_SPEC_FIELDS = {
    "name",
    "version",
    "lifecycle_event",
    "entry_point",
    "timeout_seconds",
    "dependencies",
    "input_schema",
    "output_schema",
}


@dataclass(frozen=True)
class ValidationIssue:
    """Represents a validation failure."""

    path: Path
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Collection of validation issues."""

    issues: Sequence[ValidationIssue]

    @property
    def passed(self) -> bool:
        return not self.issues

    def raise_on_failure(self) -> None:
        if not self.passed:
            lines = [f"- {issue.path}: {issue.message}" for issue in self.issues]
            raise SystemExit("Plugin validation failed:\n" + "\n".join(lines))


def load_json(path: Path) -> Mapping[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_spec(path: Path) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    data = load_json(path)
    missing = REQUIRED_SPEC_FIELDS - data.keys()
    if missing:
        issues.append(
            ValidationIssue(path, f"Missing required spec fields: {sorted(missing)}")
        )
    return issues


def validate_manifest(manifest_path: Path, spec: Mapping[str, object]) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    manifest = load_json(manifest_path)
    expected = {
        "name": spec.get("name"),
        "version": spec.get("version"),
        "entry_point": spec.get("entry_point"),
        "lifecycle_event": spec.get("lifecycle_event"),
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            issues.append(
                ValidationIssue(
                    manifest_path,
                    f"Manifest field '{key}' expected {value!r} but found {manifest.get(key)!r}",
                )
            )
    return issues


def validate_policy_snapshot(path: Path, spec: Mapping[str, object]) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    snapshot = load_json(path)
    if snapshot.get("plugin") != spec.get("name"):
        issues.append(ValidationIssue(path, "Policy snapshot plugin name mismatch"))
    if snapshot.get("version") != spec.get("version"):
        issues.append(ValidationIssue(path, "Policy snapshot version mismatch"))
    return issues


def validate_ledger_contract(path: Path, spec: Mapping[str, object]) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ledger = load_json(path)
    required_fields = {"timestamp", "ulid", "status", "summary"}
    ledger_fields = set(ledger.get("fields", []))
    missing_fields = required_fields - ledger_fields
    if missing_fields:
        issues.append(
            ValidationIssue(path, f"Ledger contract missing fields: {sorted(missing_fields)}")
        )
    if ledger.get("plugin") != spec.get("name"):
        issues.append(ValidationIssue(path, "Ledger contract plugin mismatch"))
    return issues


def validate_tests_directory(root: Path) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    tests_dir = root / "tests"
    if not tests_dir.exists():
        issues.append(ValidationIssue(tests_dir, "tests/ directory missing"))
        return issues
    if not any(tests_dir.glob("test_*.py")):
        issues.append(ValidationIssue(tests_dir, "No test_*.py files present"))
    return issues


def validate_entry_point(root: Path, spec: Mapping[str, object]) -> Sequence[ValidationIssue]:
    issues: list[ValidationIssue] = []
    entry_point = str(spec.get("entry_point", ""))
    module, _, attribute = entry_point.partition(":")
    if not module:
        issues.append(ValidationIssue(root, "Spec entry_point is empty"))
        return issues

    module_path = root / Path(*module.split(".")).with_suffix(".py")
    if not module_path.exists():
        issues.append(ValidationIssue(module_path, "Entry point module missing"))
    else:
        source = module_path.read_text(encoding="utf-8")
        if attribute and attribute not in source:
            issues.append(
                ValidationIssue(
                    module_path,
                    f"Entry point attribute '{attribute}' not defined in module",
                )
            )
    return issues


def validate_plugin(path: Path) -> ValidationReport:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {path}")

    issues: list[ValidationIssue] = []
    for artifact in sorted(REQUIRED_ARTIFACTS):
        artifact_path = path / artifact
        if not artifact_path.exists():
            issues.append(ValidationIssue(artifact_path, "Required artifact missing"))

    spec_path = path / "plugin.spec.json"
    if spec_path.exists():
        issues.extend(validate_spec(spec_path))
        spec = load_json(spec_path)
        issues.extend(validate_manifest(path / "manifest.json", spec))
        issues.extend(validate_policy_snapshot(path / "policy_snapshot.json", spec))
        issues.extend(validate_ledger_contract(path / "ledger_contract.json", spec))
        issues.extend(validate_tests_directory(path))
        issues.extend(validate_entry_point(path, spec))
    else:
        issues.append(ValidationIssue(spec_path, "Specification file missing"))

    return ValidationReport(tuple(issues))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, help="Path to plugin directory")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    plugin_path = Path(args.path).expanduser().resolve()
    report = validate_plugin(plugin_path)
    report.raise_on_failure()
    print(f"Validation passed for plugin at {plugin_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
