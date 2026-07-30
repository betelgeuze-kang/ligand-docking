from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, is_dataclass
from typing import Any


def parse_finite_json_float(value: str) -> float:
    """Parse a JSON floating-point token and reject overflow to infinity."""
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"non-finite JSON number is forbidden: {value}")
    return numeric


def to_plain(value: Any) -> Any:
    """Convert dataclasses and tuples to deterministic JSON-compatible objects."""
    if is_dataclass(value):
        return to_plain(asdict(value))
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_plain(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
