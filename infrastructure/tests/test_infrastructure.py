"""
Infrastructure Tests (TDI)
Version: 1.0.0
Date: 2025-11-02
Framework: pytest-testinfra
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PULUMI_DIR = PROJECT_ROOT / "infrastructure" / "pulumi"


def test_pulumi_project_declares_expected_name() -> None:
    config_path = PULUMI_DIR / "Pulumi.yaml"
    contents = config_path.read_text(encoding="utf-8")
    assert "name: acms-infrastructure" in contents
    assert "acms-infrastructure:environment" in contents


def test_stack_plan_schema() -> None:
    stack_plan_path = (PULUMI_DIR / ".." / "stack_plan.json").resolve()
    payload = json.loads(stack_plan_path.read_text(encoding="utf-8"))
    assert payload["environment"] in {"dev", "staging", "prod"}
    resources = payload["resources"]
    assert set(resources.keys()) == {"security_group", "instance"}


def test_main_module_requires_environment() -> None:
    module_source = (PULUMI_DIR / "__main__.py").read_text(encoding="utf-8")
    assert "CONFIG.require(\"environment\")" in module_source
    assert "serialize_stack_plan()" in module_source
