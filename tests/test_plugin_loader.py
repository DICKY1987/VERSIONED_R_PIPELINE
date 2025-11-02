"""Unit tests for the ACMS plugin loader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.plugin_loader import (
    DEFAULT_REQUIRED_FILES,
    PluginImportError,
    PluginLoader,
    PluginValidationError,
)


def write_plugin(tmp_path: Path, name: str = "demo-plugin") -> Path:
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    spec = {
        "name": name,
        "version": "0.1.0",
        "handles_event": "FileDetected",
    }
    manifest = {
        "name": name,
        "version": "0.1.0",
        "handles_event": "FileDetected",
        "generated_at": "2025-11-02T00:00:00Z",
        "contract_version": "1.0.0",
    }
    policy_snapshot = {
        "policy": {},
        "contract_allowed_actions": ["propose_move"],
        "contract_allowed_events": ["FileDetected"],
    }
    ledger_contract = {"required": ["ulid", "ts", "event", "actions", "status"]}
    handler_code = """
from __future__ import annotations
from typing import Any, Dict, List


def handle(event: dict) -> List[Dict[str, Any]]:
    if event.get("name") != "FileDetected":
        return []
    return [
        {
            "action": "propose_move",
            "payload": {"from": event.get("inputs", {}).get("path", ""), "to": "src/README.md"},
        }
    ]
"""
    (plugin_dir / "plugin.spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (plugin_dir / "policy_snapshot.json").write_text(json.dumps(policy_snapshot), encoding="utf-8")
    (plugin_dir / "ledger_contract.json").write_text(json.dumps(ledger_contract), encoding="utf-8")
    (plugin_dir / "handler.py").write_text(handler_code, encoding="utf-8")
    (plugin_dir / "README_PLUGIN.md").write_text("# Demo plugin", encoding="utf-8")
    (plugin_dir / "healthcheck.md").write_text("# Health", encoding="utf-8")
    return plugin_dir


@pytest.mark.parametrize("missing_file", DEFAULT_REQUIRED_FILES)
def test_missing_required_files_raise(tmp_path: Path, missing_file: str) -> None:
    plugin_dir = write_plugin(tmp_path)
    (plugin_dir / missing_file).unlink()

    loader = PluginLoader(plugin_root=tmp_path)
    with pytest.raises(PluginValidationError):
        loader.load_plugin(plugin_dir)


def test_load_and_invoke_plugin(tmp_path: Path) -> None:
    plugin_dir = write_plugin(tmp_path)
    loader = PluginLoader(plugin_root=tmp_path)

    definition = loader.load_plugin(plugin_dir)
    assert definition.name == "demo-plugin"
    assert definition.version == "0.1.0"
    assert definition.handles_event == "FileDetected"

    result = definition.invoke({"name": "FileDetected", "inputs": {"path": "docs/README.md"}})
    assert result == [
        {
            "action": "propose_move",
            "payload": {"from": "docs/README.md", "to": "src/README.md"},
        }
    ]


def test_invoke_rejects_bad_payload(tmp_path: Path) -> None:
    plugin_dir = write_plugin(tmp_path)
    (plugin_dir / "handler.py").write_text(
        """
from __future__ import annotations

def handle(event):
    return ["not-a-dict"]
""",
        encoding="utf-8",
    )

    loader = PluginLoader(plugin_root=tmp_path)
    definition = loader.load_plugin(plugin_dir)
    with pytest.raises(PluginValidationError):
        definition.invoke({"name": "FileDetected"})


def test_missing_handle_raises(tmp_path: Path) -> None:
    plugin_dir = write_plugin(tmp_path)
    (plugin_dir / "handler.py").write_text("def not_handle():\n    return []\n", encoding="utf-8")

    loader = PluginLoader(plugin_root=tmp_path)
    with pytest.raises(PluginImportError):
        loader.load_plugin(plugin_dir)
