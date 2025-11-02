"""
Plugin Integration Tests
Version: 1.0.0
Date: 2025-11-02
Tests: Plugin execution in pipeline
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

import pytest


REQUIRED_PLUGIN_FILES = {
    "plugin.spec.json",
    "manifest.json",
    "policy_snapshot.json",
    "ledger_contract.json",
    "README_PLUGIN.md",
    "healthcheck.md",
}


@pytest.fixture(scope="session")
def plugin_directories(project_root: Path) -> Iterable[Path]:
    """Yield plugin directories present in the repository."""
    plugins_root = project_root / "plugins"
    if not plugins_root.exists():
        pytest.skip("No plugins directory present; scaffold plugins before running integration tests.")
    directories = [item for item in plugins_root.iterdir() if item.is_dir()]
    if not directories:
        pytest.skip("No plugin scaffolds detected in plugins/.")
    return directories


@pytest.mark.integration
@pytest.mark.parametrize("required_file", sorted(REQUIRED_PLUGIN_FILES))
def test_plugin_scaffold_contains_required_files(plugin_directories, required_file):
    """Ensure each plugin scaffold includes all governance-mandated artifacts."""
    for directory in plugin_directories:
        path = directory / required_file
        assert path.exists(), f"Missing {required_file} in {directory.name}"


@pytest.mark.integration
def test_plugin_spec_declares_required_fields(plugin_directories):
    """Validate plugin.spec.json files align with the contract structure."""
    required_fields = {
        "name",
        "version",
        "lifecycle_event",
        "entry_point",
        "timeout_seconds",
        "dependencies",
        "input_schema",
        "output_schema",
    }

    for directory in plugin_directories:
        spec_path = directory / "plugin.spec.json"
        with spec_path.open("r", encoding="utf-8") as handle:
            data: Dict[str, object] = json.load(handle)
        missing = required_fields - data.keys()
        assert not missing, f"{spec_path} missing required fields: {sorted(missing)}"
        assert data.get("timeout_seconds") <= 120, "Timeout should enforce deterministic execution"


@pytest.mark.integration
def test_plugin_has_corresponding_unit_tests(plugin_directories):
    """Confirm plugin unit tests exist for coverage tracking and regression safety."""
    for directory in plugin_directories:
        tests_dir = directory / "tests"
        assert tests_dir.exists(), f"{directory.name} missing tests/ directory"
        unit_tests = list(tests_dir.glob("test_*.py"))
        assert unit_tests, f"{directory.name} lacks test_*.py suite"
