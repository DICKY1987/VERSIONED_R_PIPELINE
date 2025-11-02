"""
ULID Generator
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
Unique, sortable IDs
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Iterator, Optional
import os

__all__ = [
    "new_ulid",
    "validate_ulid",
    "monotonic_ulids",
    "ulid_from_datetime",
]

_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIMESTAMP_LENGTH = 10
_RANDOMNESS_LENGTH = 16
_TOTAL_LENGTH = _TIMESTAMP_LENGTH + _RANDOMNESS_LENGTH
_TIMESTAMP_BITS = 48
_RANDOMNESS_BITS = 80

_MAX_TIMESTAMP = (1 << _TIMESTAMP_BITS) - 1
_MAX_RANDOMNESS = (1 << _RANDOMNESS_BITS) - 1


def _encode_base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD_BASE32[value & 0x1F])
        value >>= 5
    chars.reverse()
    return "".join(chars)


def _timestamp_ms(timestamp: Optional[datetime] = None) -> int:
    dt = timestamp or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _encode_ulid(timestamp_ms: int, randomness: int) -> str:
    if not 0 <= timestamp_ms <= _MAX_TIMESTAMP:
        raise ValueError("Timestamp out of ULID range")
    if not 0 <= randomness <= _MAX_RANDOMNESS:
        raise ValueError("Randomness out of ULID range")
    return _encode_base32(timestamp_ms, _TIMESTAMP_LENGTH) + _encode_base32(
        randomness, _RANDOMNESS_LENGTH
    )


def new_ulid(timestamp: Optional[datetime] = None, randomness: Optional[bytes] = None) -> str:
    """Return a freshly generated ULID string."""

    ts = _timestamp_ms(timestamp)
    rand_bytes = randomness or os.urandom(10)
    if len(rand_bytes) != 10:
        raise ValueError("ULID randomness must be exactly 10 bytes")
    rand_int = int.from_bytes(rand_bytes, "big")
    return _encode_ulid(ts, rand_int)


def validate_ulid(candidate: str) -> bool:
    """Return ``True`` when the supplied string is a valid ULID."""

    if len(candidate) != _TOTAL_LENGTH:
        return False
    try:
        timestamp_part = candidate[:_TIMESTAMP_LENGTH]
        random_part = candidate[_TIMESTAMP_LENGTH:]
        timestamp_value = 0
        for char in timestamp_part:
            timestamp_value = (timestamp_value << 5) | _CROCKFORD_BASE32.index(char)
        random_value = 0
        for char in random_part:
            random_value = (random_value << 5) | _CROCKFORD_BASE32.index(char)
    except ValueError:
        return False
    return timestamp_value <= _MAX_TIMESTAMP and random_value <= _MAX_RANDOMNESS


def monotonic_ulids() -> Iterator[str]:
    """Yield ULIDs that remain lexicographically sortable within the same millisecond."""

    last_timestamp = -1
    last_randomness = -1

    while True:
        current_timestamp = _timestamp_ms()
        if current_timestamp == last_timestamp:
            last_randomness = (last_randomness + 1) & _MAX_RANDOMNESS
        else:
            last_timestamp = current_timestamp
            last_randomness = int.from_bytes(os.urandom(10), "big")
        yield _encode_ulid(last_timestamp, last_randomness)


def ulid_from_datetime(sequence: Iterable[datetime]) -> Iterator[str]:
    """Convert an iterable of datetimes to ULID strings."""

    for dt in sequence:
        yield new_ulid(timestamp=dt)
