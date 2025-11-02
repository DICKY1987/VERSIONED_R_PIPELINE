# tools/context_broker.py
"""
Reference Context Broker
- Scans a repository and selects files for LLM context
- Computes stable, reproducible scores per file
- Respects budgets (tokens/files), pin/ban globs, and category caps
- Emits context_manifest.json

Usage:
  python tools/context_broker.py --root . --out context_manifest.json --keywords "orchestrator" "state" --task-type edit

Notes:
- Token approximation: tokens ~= ceil(bytes / 4)
- Sorting is stable: by (-score, size_bytes asc, path asc)
"""
from __future__ import annotations
import argparse, fnmatch, hashlib, json, math, os, sys, time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

DEFAULT_CONFIG = {
  "version": "1.1.0",
  "budgets": {"max_tokens": 180000, "max_files": 200},
  "strategy": {
    "pipeline": ["structural-seed","lexical","recency","size-penalty"],
    "weights": {"lexical": 0.4, "structural": 0.3, "recency": 0.2, "size_penalty": 0.1}
  },
  "chunking": {"chunk_tokens": 800, "overlap_tokens": 80, "dedupe_by_sha256": True},
  "provider_windows": {"claude_code": 180000, "gpt": 128000},
  "category_caps": {"code": 60, "tests": 30, "docs": 10},
  "pin_globs": ["src/**/core/**"],
  "ban_globs": ["**/.git/**","**/*.pem","**/secrets/**","**/__pycache__/**","**/.runs/**"],
  "emit_manifest": True
}

CODE_EXTS = {".py",".ps1",".psm1",".psd1",".js",".ts",".tsx",".jsx",".java",".cs",".go",".rs",".cpp",".c",".h",".sh",".bash",".zsh",".sql",".json",".yaml",".yml",".toml",".ini",".md",".rst",".txt",".ps1xml"}

@dataclass
class SelectionParams:
    task_type: str
    target_files: List[str]
    keywords: List[str]
    include_tests: bool = True

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def approx_tokens(num_bytes: int) -> int:
    return max(1, math.ceil(num_bytes / 4))

def is_banned(path: Path, ban_globs: List[str]) -> bool:
    s = str(path).replace("\\","/")
    return any(fnmatch.fnmatch(s, g) for g in ban_globs)

def categorize(path: Path) -> str:
    s = str(path).lower()
    if "test" in s or "/tests/" in s or s.endswith("_test.py"):
        return "tests"
    if path.suffix.lower() in {".md",".rst",".txt"}:
        return "docs"
    return "code"

def lexical_score(text: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.0
    text_l = text.lower()
    return sum(text_l.count(k.lower()) for k in keywords)

def recency_score(mtime: float, now: float) -> float:
    # Newer files get higher score; 0..1 scale with half-life ~30 days
    days = max(0.0, (now - mtime) / 86400.0)
    return 1.0 / (1.0 + (days / 30.0))

def structural_seed(path: Path, target_files: List[str], pin_globs: List[str]) -> float:
    s = str(path).replace("\\","/")
    bonus = 0.0
    if any(Path(tf).resolve() == path.resolve() for tf in target_files):
        bonus += 5.0
    if any(fnmatch.fnmatch(s, g) for g in pin_globs):
        bonus += 1.0
    return bonus

def stable_score_for_file(path: Path, params: SelectionParams, cfg: dict, now: float) -> Tuple[float, Dict[str, float]]:
    weights = cfg["strategy"]["weights"]
    size_bytes = path.stat().st_size
    text = ""
    try:
        if size_bytes <= 2_000_000:  # cap read size
            text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        text = ""

    s_struct = structural_seed(path, params.target_files, cfg["pin_globs"])
    s_lex = lexical_score(text, params.keywords)
    s_rec = recency_score(path.stat().st_mtime, now)
    size_penalty = size_bytes / 1024.0  # KB

    score = (
        weights.get("structural",0)*s_struct +
        weights.get("lexical",0)*s_lex +
        weights.get("recency",0)*s_rec -
        weights.get("size_penalty",0)*size_penalty
    )
    breakdown = {"structural": s_struct, "lexical": s_lex, "recency": s_rec, "size_penalty": size_penalty}
    return score, breakdown

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Root directory to scan")
    ap.add_argument("--out", default="context_manifest.json", help="Output manifest path")
    ap.add_argument("--task-type", default="edit", help="Task type (edit, analyze, plan, test)")
    ap.add_argument("--target", action="append", default=[], help="Target file (repeatable)")
    ap.add_argument("--keywords", nargs="*", default=[], help="Keyword list")
    ap.add_argument("--config", help="Optional JSON config file matching the context_broker schema")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    cfg = DEFAULT_CONFIG
    if args.config:
        import json
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    params = SelectionParams(task_type=args.task_type, target_files=[str(Path(t).resolve()) for t in args.target], keywords=args.keywords)
    now = time.time()

    # Collect candidates
    candidates: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in CODE_EXTS:
            continue
        if is_banned(p, cfg["ban_globs"]):
            continue
        cat = categorize(p)
        if cat == "tests" and not params.include_tests:
            continue
        candidates.append(p)

    # Score all candidates
    scored = []
    for p in candidates:
        score, breakdown = stable_score_for_file(p, params, cfg, now)
        size_bytes = p.stat().st_size
        tokens = approx_tokens(size_bytes)
        cat = categorize(p)
        scored.append({
            "path": str(p),
            "category": cat,
            "score": round(score, 6),
            "breakdown": breakdown,
            "size_bytes": size_bytes,
            "tokens": tokens,
            "mtime_iso": datetime_from_epoch(p.stat().st_mtime),
            "sha256": sha256_file(p)
        })

    # Category caps
    caps = cfg["category_caps"]
    by_cat = {"code": [], "tests": [], "docs": []}
    for item in scored:
        by_cat[item["category"]].append(item)

    # Stable sort: (-score, size_bytes asc, path asc)
    def sort_key(item):
        return (-item["score"], item["size_bytes"], item["path"])

    for k in by_cat:
        by_cat[k].sort(key=sort_key)
    selected = []
    for cat in ("code","tests","docs"):
        cap = caps.get(cat, 0)
        selected.extend(by_cat[cat][:cap])

    # Enforce budgets
    selected.sort(key=sort_key)
    max_files = cfg.get("budgets",{}).get("max_files", len(selected))
    max_tokens = cfg.get("budgets",{}).get("max_tokens", 999_999_999)

    out = []
    tok_sum = 0
    for item in selected:
        if len(out) >= max_files:
            break
        if tok_sum + item["tokens"] > max_tokens:
            continue
        out.append(item)
        tok_sum += item["tokens"]

    manifest = {
        "manifest_version": "1.0.0",
        "generated_at": datetime_from_epoch(time.time()),
        "root": str(root),
        "selection_params": {
            "task_type": params.task_type,
            "target_files": params.target_files,
            "keywords": params.keywords
        },
        "config_fingerprint": sha256_text(json.dumps(cfg, sort_keys=True)),
        "total_files": len(out),
        "total_tokens": tok_sum,
        "files": out
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {args.out} with {len(out)} files, ~{tok_sum} tokens.")

def datetime_from_epoch(ts: float) -> str:
    import datetime as _dt
    return _dt.datetime.utcfromtimestamp(ts).replace(tzinfo=_dt.timezone.utc).isoformat()

def sha256_file(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_text(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

if __name__ == "__main__":
    main()
