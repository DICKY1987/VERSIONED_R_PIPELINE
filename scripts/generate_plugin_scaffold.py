#!/usr/bin/env python3
"""Plugin Scaffold Generator (Python)
Version: 1.0.0
Date: 2025-11-02
Parallel implementation of PowerShell version
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

CONTRACT_DEFAULT = Path("./core/OPERATING_CONTRACT.md")

YAML_BLOCKS = {
    "events": r"```yaml\s*lifecycle_events:(.*?)```",
    "actions": r"```yaml\s*allowed_actions_contract:(.*?)```",
}

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)

HANDLER_TEMPLATE = """\
"""
Plugin handler for {name} ({version}).
Only edit code between BEGIN/END AUTO SECTION markers.
Contract version at generation: {contract_version}
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List

# BEGIN AUTO SECTION

def handle(event: dict) -> List[Dict[str, Any]]:
    """Return a list of proposals: {{"action": <str>, "payload": <dict>}}."""
    return []

# END AUTO SECTION
"""

README_TEMPLATE = """\
# Plugin: {name}

*Handles*: `{handles_event}`
*Version*: `{version}`

## Development
- Edit only between **BEGIN AUTO SECTION** and **END AUTO SECTION** in `handler.py`.
- Run `python scripts/validate_plugin.py --path {plugin_dir}` before committing.

## Inputs
{inputs}
## Outputs
{outputs}
"""

HEALTHCHECK_TEMPLATE = """\
# Healthcheck for {name}

- Validate contract compatibility
- Dry-run with sample event payload

```python
from importlib import util
import json
spec = util.spec_from_file_location("{name}_handler", r"{handler_path}")
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps(mod.handle({{"name": "{handles_event}", "inputs": {{"path": "README.md", "size": 12, "sha256": "deadbeef", "mime": "text/markdown"}}}}), indent=2))
```
"""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_yaml_block(md: str, which: str) -> Dict[str, Any]:
    pattern = YAML_BLOCKS[which]
    match = re.search(pattern, md, re.S)
    if not match:
        msg = f"Cannot find YAML block: {which}"
        raise ValueError(msg)
    block = match.group(1)
    key = "lifecycle_events" if which == "events" else "allowed_actions_contract"
    payload = yaml.safe_load(f"{key}:{block}")
    return payload


def parse_front_matter(md: str) -> Dict[str, Any]:
    match = FRONT_MATTER_RE.search(md)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def kebab_ok(name: str) -> bool:
    return re.fullmatch(r"[a-z0-9-]+", name) is not None


def semver_ok(ver: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+", ver) is not None


def normalise_list(items: Any) -> str:
    if not items:
        return "- (none specified)"
    return "\n".join(f"- {entry}" for entry in items)


def ensure_contract(path: Path) -> str:
    if not path.exists():
        msg = f"Contract file not found: {path}"
        raise FileNotFoundError(msg)
    return read_text(path)


def build_manifest(spec: Dict[str, Any], contract_version: str | None) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "name": spec["name"],
        "version": spec["version"],
        "handles_event": spec["handles_event"],
        "generated_at": iso_now(),
    }
    if contract_version:
        manifest["contract_version"] = contract_version
    return manifest


def build_policy_snapshot(spec: Dict[str, Any], allowed_actions: list[str], allowed_events: list[str]) -> Dict[str, Any]:
    return {
        "policy": spec.get("policy", {}),
        "contract_allowed_actions": allowed_actions,
        "contract_allowed_events": allowed_events,
    }


def build_ledger_contract() -> Dict[str, Any]:
    return {
        "required": [
            "ulid",
            "ts",
            "event",
            "policy_version",
            "inputs",
            "actions",
            "status",
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--spec", required=True, help="Path to plugin.spec.json")
    parser.add_argument(
        "-c",
        "--contract",
        default=str(CONTRACT_DEFAULT),
        help="Path to OPERATING_CONTRACT.md",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec)
    plug_dir = spec_path.parent
    plug_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(read_text(spec_path))
    for key in ("name", "version", "handles_event"):
        if key not in spec:
            parser.error(f"Spec missing required field: {key}")

    if not kebab_ok(spec["name"]):
        parser.error("spec.name must be kebab-case [a-z0-9-]+")
    if not semver_ok(spec["version"]):
        parser.error("spec.version must be SemVer X.Y.Z")

    contract_path = Path(args.contract)
    contract_md = ensure_contract(contract_path)
    front_matter = parse_front_matter(contract_md)
    contract_version = front_matter.get("contract_version")

    events = extract_yaml_block(contract_md, "events")["lifecycle_events"]
    allowed_events = [event["name"] for event in events]
    if spec["handles_event"] not in allowed_events:
        parser.error(f"handles_event '{spec['handles_event']}' not allowed by contract")

    actions = extract_yaml_block(contract_md, "actions")["allowed_actions_contract"]
    allowed_action_names = list(actions.keys())

    manifest = build_manifest(spec, contract_version)
    policy_snapshot = build_policy_snapshot(spec, allowed_action_names, allowed_events)
    ledger_contract = build_ledger_contract()

    (plug_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (plug_dir / "policy_snapshot.json").write_text(
        json.dumps(policy_snapshot, indent=2),
        encoding="utf-8",
    )
    (plug_dir / "ledger_contract.json").write_text(
        json.dumps(ledger_contract, indent=2),
        encoding="utf-8",
    )

    contract_version_label = contract_version or "unknown"
    handler_src = HANDLER_TEMPLATE.format(
        name=spec["name"],
        version=spec["version"],
        contract_version=contract_version_label,
    )
    (plug_dir / "handler.py").write_text(handler_src, encoding="utf-8")

    readme_src = README_TEMPLATE.format(
        name=spec["name"],
        handles_event=spec["handles_event"],
        version=spec["version"],
        plugin_dir=plug_dir.name,
        inputs=normalise_list(spec.get("inputs")),
        outputs=normalise_list(spec.get("outputs")),
    )
    (plug_dir / "README_PLUGIN.md").write_text(readme_src, encoding="utf-8")

    handler_path = (plug_dir / "handler.py").as_posix()
    healthcheck_src = HEALTHCHECK_TEMPLATE.format(
        name=spec["name"],
        handler_path=handler_path,
        handles_event=spec["handles_event"],
    )
    (plug_dir / "healthcheck.md").write_text(healthcheck_src, encoding="utf-8")

    print(f"Scaffold generated for plugin '{spec['name']}' at '{plug_dir}'")


if __name__ == "__main__":
    main()
