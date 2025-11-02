"""
JSONL Ledger Writer
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
Append-only audit logging
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, MutableMapping, Optional
import json
import threading

__all__ = ["Ledger", "LedgerRecord", "load_ledger"]


class LedgerRecord(dict):
    """Typed mapping representing a single ledger entry."""

    timestamp: str
    event_type: str
    correlation_id: Optional[str]


def _json_default(value: Any) -> Any:  # pragma: no cover - formatting helper
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _normalise_mapping(data: Mapping[str, Any]) -> MutableMapping[str, Any]:
    normalised: MutableMapping[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            normalised[str(key)] = _normalise_mapping(value)
        elif isinstance(value, (list, tuple, set)):
            normalised[str(key)] = [
                _normalise_mapping(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            normalised[str(key)] = value
    return normalised


@dataclass
class Ledger:
    """Append-only JSONL ledger with deterministic ordering."""

    path: Path | str
    ensure_directory: bool = True
    sort_keys: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.ensure_directory:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        event_type: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        correlation_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> LedgerRecord:
        """Record an event in the ledger and return the stored entry."""

        record: LedgerRecord = LedgerRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            correlation_id=correlation_id,
        )

        if payload:
            record["payload"] = _normalise_mapping(payload)
        if metadata:
            record["metadata"] = _normalise_mapping(metadata)

        serialised = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=self.sort_keys,
            default=_json_default,
        )

        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(serialised)
                handle.write("\n")
        return record

    def iter_entries(self, limit: Optional[int] = None) -> Iterator[LedgerRecord]:
        """Yield recorded entries, preserving insertion order."""

        if not self.path.exists():
            return

        count = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if limit is not None and count >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                count += 1
                yield LedgerRecord(json.loads(line))

    def tail(self, limit: int = 10) -> Iterable[LedgerRecord]:
        """Return the most recent *limit* records."""

        entries = list(self.iter_entries())
        return entries[-limit:]

    def clear(self) -> None:
        """Erase the ledger contents while preserving the file."""

        with self._lock:
            self.path.write_text("", encoding="utf-8")


def load_ledger(path: Path | str) -> Ledger:
    """Helper that constructs a ledger for the supplied path."""

    return Ledger(path)
