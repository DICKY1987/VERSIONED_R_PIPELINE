"""Generate ACMS plugin scaffolds from a plugin specification."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, Mapping

REQUIRED_FIELDS = {
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
class PluginSpec:
    """Representation of a plugin specification file."""

    raw: Mapping[str, Any]

    @property
    def entry_point(self) -> str:
        return str(self.raw["entry_point"])

    @property
    def module_path(self) -> Path:
        module, *_ = self.entry_point.split(":", 1)
        parts = module.split(".")
        return Path(*parts).with_suffix(".py")

    @property
    def handler_name(self) -> str:
        _, _, attribute = self.entry_point.partition(":")
        return attribute or "PluginHandler"

    @property
    def name(self) -> str:
        return str(self.raw["name"])

    @property
    def version(self) -> str:
        return str(self.raw["version"])

    def to_json(self) -> str:
        return json.dumps(self.raw, indent=2, sort_keys=True) + "\n"


def load_spec(path: Path) -> PluginSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(
            f"Specification at {path} missing required fields: {sorted(missing)}"
        )
    return PluginSpec(raw=data)


def ensure_spec_path(spec: PluginSpec, source: Path, destination_root: Path) -> Path:
    destination_root.mkdir(parents=True, exist_ok=True)
    target = destination_root / "plugin.spec.json"
    if target.resolve() != source.resolve():
        target.write_text(spec.to_json(), encoding="utf-8")
    return target


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_readme(path: Path, spec: PluginSpec) -> None:
    content = dedent(
        f"""
        ---
        title: "{spec.name} Plugin"
        status: draft
        owner: TBD
        generated_at: {datetime.now(timezone.utc).isoformat()}
        ---

        # {spec.name} Plugin

        * **Version:** {spec.version}
        * **Lifecycle Event:** {spec.raw['lifecycle_event']}
        * **Entry Point:** {spec.entry_point}
        * **Timeout:** {spec.raw['timeout_seconds']} seconds

        This file was generated automatically from the canonical ``plugin.spec.json``
        using ``scripts/generate_plugin_scaffold.py``. Update the plugin
        specification and rerun the generator when requirements change.
        """
    ).strip()
    path.write_text(content + "\n", encoding="utf-8")


def write_healthcheck(path: Path, spec: PluginSpec) -> None:
    content = dedent(
        f"""
        # {spec.name} Plugin Healthcheck

        1. Execute ``python scripts/validate_plugin.py --path {path.parent.as_posix()}``.
        2. Run unit tests: ``pytest { (path.parent / 'tests').as_posix() }``.
        3. Review ledger entries produced during dry-run executions.
        4. Ensure coverage remains above the contract threshold.
        """
    ).strip()
    path.write_text(content + "\n", encoding="utf-8")


def write_handler(path: Path, spec: PluginSpec) -> None:
    handler = dedent(
        f"""
        """Auto-generated handler for the {spec.name} plugin."""
        from __future__ import annotations

        from dataclasses import dataclass
        from typing import Any, Dict


        @dataclass
        class {spec.handler_name}:
            """Entrypoint for the {spec.name} plugin."""

            def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
                """Execute plugin logic.

                Replace this implementation with the real plugin behaviour. The
                returned mapping must satisfy the declared output schema.
                """

                return {{
                    "status": "not-implemented",
                    "received": payload,
                }}
        """
    ).strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(handler + "\n", encoding="utf-8")


def write_tests(root: Path, spec: PluginSpec) -> None:
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    module_import = spec.entry_point.split(":", 1)[0]
    handler_name = spec.handler_name
    test_body = dedent(
        f"""
        """Smoke tests for the {spec.name} plugin scaffold."""
        from __future__ import annotations

        from importlib import import_module


        def test_handler_execute_returns_mapping() -> None:
            module = import_module("{module_import}")
            handler_cls = getattr(module, "{handler_name}")
            handler = handler_cls()
            result = handler.execute({{}})
            assert isinstance(result, dict)
        """
    ).strip()
    (tests_dir / "test_plugin_scaffold.py").write_text(test_body + "\n", encoding="utf-8")


def write_manifest(path: Path, spec: PluginSpec) -> None:
    payload = {
        "name": spec.name,
        "version": spec.version,
        "entry_point": spec.entry_point,
        "lifecycle_event": spec.raw["lifecycle_event"],
        "dependencies": spec.raw.get("dependencies", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(path, payload)


def write_policy_snapshot(path: Path, spec: PluginSpec) -> None:
    payload = {
        "plugin": spec.name,
        "version": spec.version,
        "policy_version": spec.raw.get("policy_version", "unspecified"),
        "quality_gates": {
            "coverage_min_percent": 80,
            "lint": ["black", "ruff", "mypy", "pylint"],
            "security": ["bandit", "gitleaks"],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(path, payload)


def write_ledger_contract(path: Path, spec: PluginSpec) -> None:
    payload = {
        "plugin": spec.name,
        "version": spec.version,
        "event": spec.raw["lifecycle_event"],
        "fields": [
            "timestamp",
            "ulid",
            "status",
            "summary",
            "inputs",
            "outputs",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(path, payload)


def generate_scaffold(spec_path: Path, output_dir: Path) -> None:
    spec = load_spec(spec_path)
    ensure_spec_path(spec, spec_path, output_dir)

    write_manifest(output_dir / "manifest.json", spec)
    write_policy_snapshot(output_dir / "policy_snapshot.json", spec)
    write_ledger_contract(output_dir / "ledger_contract.json", spec)
    write_readme(output_dir / "README_PLUGIN.md", spec)
    write_healthcheck(output_dir / "healthcheck.md", spec)
    write_handler(output_dir / spec.module_path, spec)
    write_tests(output_dir, spec)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to plugin.spec.json")
    parser.add_argument(
        "--out",
        dest="out",
        default=None,
        help="Optional output directory (defaults to spec parent)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    spec_path = Path(args.spec).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"Specification file not found: {spec_path}")

    output_dir = Path(args.out).expanduser().resolve() if args.out else spec_path.parent
    generate_scaffold(spec_path, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
