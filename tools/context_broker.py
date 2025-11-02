"""ACMS Context Broker implementation.

This script fulfils the Phase 4 deliverable described in
``ACMS_BUILD_EXECUTION_CONTRACT.yaml`` by providing a deterministic
context-selection mechanism for LLM tooling (Aider & Claude Code).

Key capabilities:
* Scans a repository for candidate files using a reproducible filter.
* Scores files with structural, lexical, recency, and size heuristics.
* Enforces configurable token/file budgets and category caps.
* Emits a stable JSON manifest that downstream agents can consume.

The default configuration is sourced from ``.context-broker.yaml`` if
present; otherwise the compiled-in defaults are used. The configuration
shape is validated by ``schemas/context_broker.schema.json``.
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("acms.context_broker")

# File extensions that are considered eligible for context selection.
CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".ps1",
    ".ps1xml",
    ".psd1",
    ".psm1",
    ".py",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}

DEFAULT_CONFIG: Dict[str, object] = {
    "context_broker": {
        "version": "1.1.0",
        "description": "Deterministic configuration for ACMS context selection",
        "budgets": {"max_tokens": 180000, "max_files": 180},
        "strategy": {
            "pipeline": ["structural", "lexical", "recency", "size_penalty"],
            "weights": {
                "structural": 0.35,
                "lexical": 0.35,
                "recency": 0.2,
                "size_penalty": 0.1,
            },
        },
        "chunking": {"chunk_tokens": 800, "overlap_tokens": 80, "dedupe_by_sha256": True},
        "provider_windows": {"aider": 80000, "claude_code": 180000},
        "category_caps": {"code": 80, "tests": 40, "docs": 20},
        "pin_globs": ["core/**", "tools/**"],
        "ban_globs": [
            "**/.git/**",
            "**/.runs/**",
            "**/__pycache__/**",
            "**/*.pem",
            "**/secrets/**",
            "**/.tox/**",
        ],
        "emit_manifest": True,
        "default_include_tests": True,
        "default_task_type": "edit",
    }
}

CONFIG_CANDIDATES = (".context-broker.yaml", ".context-broker.yml", ".context-broker.json")


@dataclass(frozen=True)
class SelectionParams:
    """Parameters describing the context-selection request."""

    task_type: str
    target_files: List[Path]
    keywords: List[str]
    max_tokens: int
    max_files: int
    include_tests: bool


@dataclass(frozen=True)
class FileScore:
    """Information collected for each file candidate."""

    path: Path
    category: str
    tokens: int
    size_bytes: int
    score: float
    breakdown: Dict[str, float]
    sha256: str
    is_mandatory: bool = False


@dataclass
class ContextManifest:
    """JSON-serialisable manifest describing the selected context."""

    manifest_version: str
    generated_at: str
    root: str
    selection_params: Dict[str, object]
    config_fingerprint: str
    total_files: int
    total_tokens: int
    truncated: bool
    files: List[Dict[str, object]] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return dataclasses.asdict(self)


class ConfigLoader:
    """Load broker configuration from YAML or JSON."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def load(self, explicit_path: Optional[str]) -> Dict[str, object]:
        if explicit_path:
            path = Path(explicit_path)
            if not path.is_absolute():
                path = self.repo_root / path
            logger.debug("Loading config from explicit path %s", path)
            return self._load_file(path)

        for candidate in CONFIG_CANDIDATES:
            path = self.repo_root / candidate
            if path.exists():
                logger.debug("Loading config from %s", path)
                return self._load_file(path)

        logger.debug("No config file located, using default configuration")
        return DEFAULT_CONFIG

    def _load_file(self, path: Path) -> Dict[str, object]:
        if not path.exists():
            raise FileNotFoundError(path)

        try:
            if path.suffix in {".json"}:
                return json.loads(path.read_text(encoding="utf-8"))
            return self._load_yaml(path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to parse config %s (%s); falling back to defaults", path, exc)
            return DEFAULT_CONFIG

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, object]:
        try:
            import yaml  # type: ignore
        except Exception:  # pragma: no cover - PyYAML optional dependency
            logger.warning("PyYAML not available; default configuration will be used")
            return DEFAULT_CONFIG

        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)


class ContextBroker:
    """Implements deterministic context selection for LLM tooling."""

    def __init__(self, repo_root: Path, config: Dict[str, object]):
        self.repo_root = repo_root.resolve()
        self.config = config
        self.config_body = config.get("context_broker", {})
        if not isinstance(self.config_body, dict):
            raise ValueError("context_broker configuration must be an object")

        self._ban_globs = [self._normalise_glob(g) for g in self.config_body.get("ban_globs", [])]
        self._pin_globs = [self._normalise_glob(g) for g in self.config_body.get("pin_globs", [])]
        logger.debug("ContextBroker initialised for %s", self.repo_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build_manifest(self, params: SelectionParams) -> ContextManifest:
        logger.debug("Building manifest for params: %s", params)
        mandatory_paths = {path.resolve() for path in params.target_files}
        candidate_scores = list(self._score_candidates(params, mandatory_paths))

        mandatory = [item for item in candidate_scores if item.is_mandatory]
        optional = [item for item in candidate_scores if not item.is_mandatory]

        selected, excluded, truncated = self._apply_budgets(
            mandatory, optional, params.max_tokens, params.max_files
        )

        manifest = ContextManifest(
            manifest_version="1.0.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            root=str(self.repo_root),
            selection_params={
                "task_type": params.task_type,
                "target_files": [self._relativise_path(p) for p in params.target_files],
                "keywords": params.keywords,
                "max_tokens": params.max_tokens,
                "max_files": params.max_files,
                "include_tests": params.include_tests,
            },
            config_fingerprint=self._fingerprint_config(),
            total_files=len(selected),
            total_tokens=sum(item.tokens for item in selected),
            truncated=truncated,
            files=[self._serialise_file(item) for item in selected],
            excluded=[self._relativise_path(item.path) for item in excluded],
        )
        logger.debug("Manifest built: %s", manifest)
        return manifest

    # ------------------------------------------------------------------
    # Scoring pipeline
    # ------------------------------------------------------------------
    def _score_candidates(
        self, params: SelectionParams, mandatory_paths: Iterable[Path]
    ) -> Iterable[FileScore]:
        mandatory_resolved = {path.resolve() for path in mandatory_paths}
        yielded: set[Path] = set()

        # Ensure mandatory files are yielded even if they are excluded by filters.
        for path in mandatory_resolved:
            if path.exists():
                logger.debug("Scoring mandatory file %s", path)
                score = self._score_file(path, params, is_mandatory=True)
                yielded.add(path)
                yield score
            else:
                logger.warning("Mandatory file does not exist: %s", path)

        for path in self._iter_candidate_files(params.include_tests):
            resolved = path.resolve()
            if resolved in yielded:
                continue
            score = self._score_file(resolved, params, is_mandatory=False)
            yielded.add(resolved)
            yield score

    def _iter_candidate_files(self, include_tests: bool) -> Iterable[Path]:
        for path in self.repo_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            if self._is_banned(path):
                continue
            if not include_tests and self._categorise(path) == "tests":
                continue
            yield path

    def _score_file(self, path: Path, params: SelectionParams, is_mandatory: bool) -> FileScore:
        category = self._categorise(path)
        size_bytes = self._safe_stat(path, "st_size", default=0)
        tokens = self._approx_tokens(size_bytes)
        text = self._read_file(path, size_limit=2_000_000)

        structural_score = self._structural_score(path, params.target_files)
        lexical_score = self._lexical_score(text, params.keywords)
        recency_score = self._recency_score(self._safe_stat(path, "st_mtime", default=time.time()))
        size_penalty = size_bytes / 1024.0  # kilobytes

        weights: Dict[str, float] = self.config_body.get("strategy", {}).get("weights", {})
        score = (
            weights.get("structural", 0.0) * structural_score
            + weights.get("lexical", 0.0) * lexical_score
            + weights.get("recency", 0.0) * recency_score
            - weights.get("size_penalty", 0.0) * size_penalty
        )

        breakdown = {
            "structural": structural_score,
            "lexical": lexical_score,
            "recency": recency_score,
            "size_penalty": size_penalty,
        }

        return FileScore(
            path=path,
            category=category,
            tokens=tokens,
            size_bytes=size_bytes,
            score=round(score, 6),
            breakdown=breakdown,
            sha256=self._sha256_file(path),
            is_mandatory=is_mandatory,
        )

    # ------------------------------------------------------------------
    # Budget enforcement
    # ------------------------------------------------------------------
    def _apply_budgets(
        self,
        mandatory: Sequence[FileScore],
        optional: Sequence[FileScore],
        max_tokens: int,
        max_files: int,
    ) -> Tuple[List[FileScore], List[FileScore], bool]:
        sorted_optional = sorted(
            optional,
            key=lambda item: (-item.score, item.size_bytes, self._normalise_path(item.path)),
        )

        selected: List[FileScore] = list(sorted(mandatory, key=lambda item: self._normalise_path(item.path)))
        excluded: List[FileScore] = []

        token_sum = sum(item.tokens for item in selected)
        truncated = token_sum > max_tokens or len(selected) > max_files

        caps: Dict[str, int] = self.config_body.get("category_caps", {})
        category_counts = {cat: 0 for cat in ("code", "tests", "docs")}
        for item in selected:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1

        for item in sorted_optional:
            if len(selected) >= max_files:
                excluded.append(item)
                continue
            if token_sum + item.tokens > max_tokens:
                excluded.append(item)
                truncated = True
                continue

            current_cat = item.category
            cap = caps.get(current_cat)
            if cap is not None and category_counts.get(current_cat, 0) >= cap:
                excluded.append(item)
                continue

            selected.append(item)
            category_counts[current_cat] = category_counts.get(current_cat, 0) + 1
            token_sum += item.tokens

        return selected, excluded, truncated

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _approx_tokens(size_bytes: int) -> int:
        return max(1, math.ceil(size_bytes / 4))

    def _categorise(self, path: Path) -> str:
        normalised = self._normalise_path(path)
        if "tests" in normalised or normalised.endswith("_test.py"):
            return "tests"
        if path.suffix.lower() in {".md", ".rst", ".txt"}:
            return "docs"
        return "code"

    def _is_banned(self, path: Path) -> bool:
        normalised = self._normalise_path(path)
        return any(fnmatch.fnmatch(normalised, glob) for glob in self._ban_globs)

    def _structural_score(self, path: Path, targets: Sequence[Path]) -> float:
        score = 0.0
        normalised = self._normalise_path(path)
        resolved_targets = {target.resolve() for target in targets}
        if path.resolve() in resolved_targets:
            score += 5.0
        if any(fnmatch.fnmatch(normalised, glob) for glob in self._pin_globs):
            score += 1.0
        return score

    @staticmethod
    def _lexical_score(text: str, keywords: Sequence[str]) -> float:
        if not text or not keywords:
            return 0.0
        text_lower = text.lower()
        return float(sum(text_lower.count(keyword.lower()) for keyword in keywords))

    @staticmethod
    def _recency_score(mtime: float) -> float:
        days = max(0.0, (time.time() - mtime) / 86400.0)
        return 1.0 / (1.0 + (days / 30.0))

    @staticmethod
    def _read_file(path: Path, size_limit: int) -> str:
        try:
            if path.stat().st_size > size_limit:
                return ""
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # pragma: no cover - IO errors handled gracefully
            return ""

    @staticmethod
    def _safe_stat(path: Path, attribute: str, default: float) -> float:
        try:
            stat = path.stat()
            return float(getattr(stat, attribute, default))
        except Exception:  # pragma: no cover - IO errors handled gracefully
            return float(default)

    def _sha256_file(self, path: Path) -> str:
        sha = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    sha.update(chunk)
        except Exception:  # pragma: no cover - IO errors handled gracefully
            return ""
        return sha.hexdigest()

    def _fingerprint_config(self) -> str:
        body = json.dumps(self.config, sort_keys=True)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _serialise_file(self, item: FileScore) -> Dict[str, object]:
        return {
            "path": self._relativise_path(item.path),
            "category": item.category,
            "tokens": item.tokens,
            "size_bytes": item.size_bytes,
            "score": item.score,
            "breakdown": item.breakdown,
            "sha256": item.sha256,
            "is_mandatory": item.is_mandatory,
        }

    def _relativise_path(self, path: Path) -> str:
        try:
            return self._normalise_path(path.relative_to(self.repo_root))
        except ValueError:
            return self._normalise_path(path)

    @staticmethod
    def _normalise_path(path: Path | str) -> str:
        return str(path).replace(os.sep, "/")

    @staticmethod
    def _normalise_glob(glob: str) -> str:
        return glob.replace("\\", "/")


# ----------------------------------------------------------------------
# CLI Entrypoint
# ----------------------------------------------------------------------

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a context manifest for LLM tools")
    parser.add_argument("--root", default=".", help="Repository root for scanning")
    parser.add_argument("--out", default=".runs/context_manifest.json", help="Output manifest path")
    parser.add_argument("--task-type", default=None, help="Task type (edit, plan, analyze, test)")
    parser.add_argument("--target", action="append", default=[], help="Target file path (repeatable)")
    parser.add_argument("--keywords", nargs="*", default=[], help="Keyword hints to boost lexical scores")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override token budget")
    parser.add_argument("--max-files", type=int, default=None, help="Override file count budget")
    parser.add_argument("--no-tests", dest="include_tests", action="store_false", help="Exclude tests from optional set")
    parser.add_argument("--include-tests", dest="include_tests", action="store_true", help="Force including test files")
    parser.add_argument("--config", help="Explicit configuration path (YAML or JSON)")
    parser.set_defaults(include_tests=None)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=os.environ.get("ACMS_LOG_LEVEL", "INFO"))
    args = parse_args(argv)

    repo_root = Path(args.root).resolve()
    if not repo_root.exists():
        raise SystemExit(f"Root directory not found: {repo_root}")

    config_loader = ConfigLoader(repo_root)
    config = config_loader.load(args.config)
    broker = ContextBroker(repo_root, config)

    body = broker.config_body
    budgets = body.get("budgets", {})
    max_tokens = args.max_tokens or int(budgets.get("max_tokens", 180000))
    max_files = args.max_files or int(budgets.get("max_files", 200))

    include_tests = args.include_tests
    if include_tests is None:
        include_tests = bool(body.get("default_include_tests", True))

    task_type = args.task_type or body.get("default_task_type", "edit")

    target_files = [
        (repo_root / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
        for target in args.target
    ]

    params = SelectionParams(
        task_type=task_type,
        target_files=target_files,
        keywords=args.keywords,
        max_tokens=max_tokens,
        max_files=max_files,
        include_tests=include_tests,
    )

    manifest = broker.build_manifest(params)
    output_path = Path(args.out)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest.to_dict(), handle, indent=2)
    logger.info("Wrote %s with %s files (~%s tokens)", output_path, manifest.total_files, manifest.total_tokens)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
