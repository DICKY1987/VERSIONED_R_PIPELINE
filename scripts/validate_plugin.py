#!/usr/bin/env python3
"""Plugin Validator (Python)
Version: 1.0.0
Date: 2025-11-02
Validates plugin contract compliance
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import util
from pathlib import Path
from typing import Any, Dict, List

import yaml

CONTRACT_DEFAULT = Path("./core/OPERATING_CONTRACT.md")
REQUIRED_FILES = (
    "plugin.spec.json",
    "manifest.json",
    "policy_snapshot.json",
    "ledger_contract.json",
    "handler.py",
    "README_PLUGIN.md",
    "healthcheck.md",
)

YAML_BLOCKS = {
    "events": r"```yaml\s*lifecycle_events:(.*?)```",
    "actions": r"```yaml\s*allowed_actions_contract:(.*?)```",
}

DANGEROUS_PATTERNS = (
    r"^\s*import\s+subprocess",
    r"os\.system\(",
    r"Popen\(",
    r"^\s*import\s+requests",
    r"^\s*import\s+urllib",
    r"^\s*import\s+http\.",
    r"^\s*import\s+socket",
    r"curl\s",
    r"wget\s",
    r"git\s",
)

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_yaml_block(md: str, which: str) -> Dict[str, Any]:
    match = re.search(YAML_BLOCKS[which], md, re.S)
    if not match:
        msg = f"Cannot find YAML block: {which}"
        raise SystemExit(msg)
    key = "lifecycle_events" if which == "events" else "allowed_actions_contract"
    block = match.group(1)
    return yaml.safe_load(f"{key}:{block}")



def kebab_ok(name: str) -> bool:
    return re.fullmatch(r"[a-z0-9-]+", name) is not None


def semver_ok(ver: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None


def static_check_handler(code: str) -> List[str]:
    errors: List[str] = []
    if "BEGIN AUTO SECTION" not in code or "END AUTO SECTION" not in code:
        errors.append("handler.py must contain AUTO region markers")
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.I | re.M):
            errors.append(f"Forbidden pattern found: {pattern}")
    return errors


def import_handler(handler_path: Path, module_name: str):
    spec = util.spec_from_file_location(module_name, handler_path.as_posix())
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_contract(path: Path) -> str:
    if not path.exists():
        msg = f"Contract file not found: {path}"
        raise FileNotFoundError(msg)
    return read_text(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", required=True, help="Path to plugin folder")
    parser.add_argument(
        "-c",
        "--contract",
        default=str(CONTRACT_DEFAULT),
        help="Path to OPERATING_CONTRACT.md",
    )
    args = parser.parse_args()

    root = Path(args.path)
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    if missing:
        parser.error("Missing files: " + ", ".join(missing))

    spec = json.loads(read_text(root / "plugin.spec.json"))
    manifest = json.loads(read_text(root / "manifest.json"))
    for key in ("name", "version", "handles_event"):
        if key not in spec:
            parser.error(f"Spec missing required field: {key}")
        if key not in manifest:
            parser.error(f"Manifest missing required field: {key}")

    if not kebab_ok(spec["name"]):
        parser.error("spec.name must be kebab-case [a-z0-9-]+")
    if not semver_ok(spec["version"]):
        parser.error("spec.version must be SemVer X.Y.Z")

    if spec["name"] != manifest["name"]:
        parser.error(
            f"Spec/manifest name mismatch: {spec['name']!r} != {manifest['name']!r}"
        )
    if spec["version"] != manifest["version"]:
        parser.error(
            f"Spec/manifest version mismatch: {spec['version']!r} != {manifest['version']!r}"
        )
    if spec["handles_event"] != manifest["handles_event"]:
        parser.error(
            "Spec/manifest handles_event mismatch: "
            f"{spec['handles_event']!r} != {manifest['handles_event']!r}"
        )

    contract_md = load_contract(Path(args.contract))
    events = extract_yaml_block(contract_md, "events")["lifecycle_events"]
    allowed_events = [entry["name"] for entry in events]
    if spec["handles_event"] not in allowed_events:
        parser.error(f"handles_event '{spec['handles_event']}' not allowed by contract")

    actions = extract_yaml_block(contract_md, "actions")["allowed_actions_contract"]
    allowed_action_names = list(actions.keys())

    handler_code = read_text(root / "handler.py")
    errors = static_check_handler(handler_code)

    try:
        module = import_handler(root / "handler.py", f"handler_{spec['name']}")
        sample_event = {
            "name": spec["handles_event"],
            "inputs": {
                "path": "__test__",
                "size": 1,
                "sha256": "deadbeef",
                "mime": "text/plain",
            },
        }
        proposals = module.handle(sample_event)
        if proposals is None:
            proposals = []
        if not isinstance(proposals, list):
            errors.append("handle() must return a list")
        else:
            for proposal in proposals:
                if not isinstance(proposal, dict):
                    errors.append("proposal items must be dicts")
                    break
                action = proposal.get("action")
                if action not in allowed_action_names:
                    errors.append(f"Proposal contains disallowed action: {action}")
                payload = proposal.get("payload")
                if not isinstance(payload, dict):
                    errors.append("Each proposal must include dict payload")
    except Exception as exc:  # pragma: no cover - runtime guard
        errors.append(f"Handler execution failed: {exc!r}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        sys.exit(1)
    print(f"Validation passed for plugin at {root}")


if __name__ == "__main__":
    main()
