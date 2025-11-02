"""Documentation Generator
Version: 1.0.0
Date: 2025-11-02
Purpose: Auto-generate API docs
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List


def _run_command(command: List[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Run a subprocess command and return the completed process."""
    process = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(
            "Command failed: {cmd}\nSTDOUT: {stdout}\nSTDERR: {stderr}".format(
                cmd=" ".join(command), stdout=process.stdout, stderr=process.stderr
            )
        )
    return process


def build_docs(config_file: Path, site_dir: Path, strict: bool) -> None:
    """Execute MkDocs build with optional strict mode."""
    project_root = config_file.parent
    args = ["mkdocs", "build", "--clean", "-f", str(config_file), "-d", str(site_dir)]
    if strict:
        args.append("--strict")

    try:
        _run_command(args, cwd=project_root)
        return
    except FileNotFoundError:
        pass
    except RuntimeError as exc:
        raise RuntimeError("mkdocs build failed") from exc

    fallback_args = [sys.executable, "-m", "mkdocs", "build", "--clean", "-f", str(config_file), "-d", str(site_dir)]
    if strict:
        fallback_args.append("--strict")
    try:
        _run_command(fallback_args, cwd=project_root)
    except FileNotFoundError as exc:
        raise RuntimeError("MkDocs is not installed in the current environment") from exc
    except RuntimeError as exc:
        raise RuntimeError("mkdocs build failed") from exc


def record_ledger(output_path: Path, *, config: Path, site_dir: Path) -> None:
    """Append a JSONL ledger entry describing the documentation build."""
    entry = {
        "event": "docs.build",
        "config": str(config),
        "site_dir": str(site_dir),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(entry) + "\n")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ACMS documentation using MkDocs")
    parser.add_argument(
        "--config-file",
        default="mkdocs.yml",
        type=Path,
        help="Path to the MkDocs configuration file",
    )
    parser.add_argument(
        "--site-dir",
        default=Path("site"),
        type=Path,
        help="Directory for rendered documentation",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable MkDocs strict mode",
    )
    parser.add_argument(
        "--ledger",
        default=Path(".acms/ledgers/docs.jsonl"),
        type=Path,
        help="Path to the JSONL ledger file",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config_path = args.config_file.resolve()
    site_dir = (args.site_dir if isinstance(args.site_dir, Path) else Path(args.site_dir)).resolve()
    ledger_path = (args.ledger if isinstance(args.ledger, Path) else Path(args.ledger)).resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"MkDocs configuration not found: {config_path}")

    site_dir.mkdir(parents=True, exist_ok=True)

    build_docs(config_path, site_dir, args.strict)
    record_ledger(ledger_path, config=config_path, site_dir=site_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
