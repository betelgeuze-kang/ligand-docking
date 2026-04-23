#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional


VALID_SPEED_MODES = {"balanced", "fast", "ultra", "turbo", "extreme", "warp", "titan", "max"}


def _safe_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_speed_profile_section(defaults_json: str, section: str) -> Dict[str, Any]:
    payload = _read_json_if_exists(defaults_json)
    if not payload:
        return {}

    section_i = str(section).strip()
    root = payload.get("sections", payload)
    if isinstance(root, dict):
        sec = root.get(section_i)
        if isinstance(sec, dict):
            return dict(sec)

    # Backward-compatible shape:
    # {"speed_mode": "...", ...}
    if all(k in payload for k in ("speed_mode", "speed_mode_replicas", "speed_profile_max_replicas")):
        return dict(payload)
    return {}


def _normalize_mode(raw_mode: Any, fallback_mode: str) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode in VALID_SPEED_MODES:
        return mode
    return str(fallback_mode).strip().lower()


def _normalize_profile(raw: Mapping[str, Any], fallback: Mapping[str, Any]) -> Dict[str, Any]:
    mode = _normalize_mode(raw.get("speed_mode"), fallback.get("speed_mode", "balanced"))
    replicas = _safe_int(raw.get("speed_mode_replicas"), _safe_int(fallback.get("speed_mode_replicas"), 0))
    max_replicas = _safe_int(
        raw.get("speed_profile_max_replicas"),
        _safe_int(fallback.get("speed_profile_max_replicas"), 0),
    )
    return {
        "speed_mode": mode,
        "speed_mode_replicas": max(int(replicas), 0),
        "speed_profile_max_replicas": max(int(max_replicas), 0),
    }


def resolve_speed_profile(
    *,
    explicit_mode: Any,
    explicit_replicas: Any,
    explicit_max_replicas: Any,
    section_defaults: Optional[Mapping[str, Any]],
    fallback: Mapping[str, Any],
) -> Dict[str, Any]:
    defaults_i = dict(section_defaults or {})
    merged = {
        "speed_mode": defaults_i.get("speed_mode", fallback.get("speed_mode", "balanced")),
        "speed_mode_replicas": defaults_i.get(
            "speed_mode_replicas",
            fallback.get("speed_mode_replicas", 0),
        ),
        "speed_profile_max_replicas": defaults_i.get(
            "speed_profile_max_replicas",
            fallback.get("speed_profile_max_replicas", 0),
        ),
    }
    if str(explicit_mode or "").strip():
        merged["speed_mode"] = explicit_mode
    if _safe_int(explicit_replicas, -1) >= 0:
        merged["speed_mode_replicas"] = int(explicit_replicas)
    if _safe_int(explicit_max_replicas, -1) >= 0:
        merged["speed_profile_max_replicas"] = int(explicit_max_replicas)
    return _normalize_profile(merged, fallback)


def parse_retry_ladder_string(spec: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    src = str(spec or "").strip()
    if not src:
        return out
    for token in src.split(","):
        part = str(token).strip()
        if not part:
            continue
        bits = [x.strip() for x in part.split(":")]
        if len(bits) != 3:
            continue
        mode = _normalize_mode(bits[0], "")
        if mode not in VALID_SPEED_MODES:
            continue
        replicas = _safe_int(bits[1], -1)
        max_replicas = _safe_int(bits[2], -1)
        if replicas < 0 or max_replicas < 0:
            continue
        out.append(
            {
                "speed_mode": mode,
                "speed_mode_replicas": int(replicas),
                "speed_profile_max_replicas": int(max_replicas),
            }
        )
    return out


def resolve_retry_ladder(
    *,
    explicit_ladder: str,
    section_defaults: Optional[Mapping[str, Any]],
    fallback_ladder: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    parsed = parse_retry_ladder_string(explicit_ladder)
    if parsed:
        return parsed

    defaults_i = dict(section_defaults or {})
    raw = defaults_i.get("retry_ladder", [])
    out: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            out.append(_normalize_profile(row, {"speed_mode": "balanced", "speed_mode_replicas": 0, "speed_profile_max_replicas": 0}))
    if out:
        return out

    return [
        _normalize_profile(
            dict(item),
            {"speed_mode": "balanced", "speed_mode_replicas": 0, "speed_profile_max_replicas": 0},
        )
        for item in list(fallback_ladder)
    ]

