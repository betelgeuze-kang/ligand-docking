#!/usr/bin/env python3
"""Deterministic, result-independent 512-to-64 proposal funnel reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

PROFILE_SCHEMA = "betelgeuze.engine_v2_sampling_funnel_profile/1.0.0"
INPUT_SCHEMA = "betelgeuze.engine_v2_sampling_funnel_input/1.0.0"
OUTPUT_SCHEMA = "betelgeuze.engine_v2_sampling_funnel_result/1.0.0"
FORBIDDEN_FRAGMENTS = ("rmsd", "posebuster", "native_pose", "downstream_rank")
CANDIDATE_FIELDS = {
    "pool_index",
    "lane",
    "status",
    "failure_code",
    "source_sha256",
    "proposal_sha256",
    "coordinate_sha256",
    "minimum_vdw_ratio",
    "pocket_escape_angstrom",
    "shape_penalty",
    "anchor_penalty",
    "embedding",
}


class FunnelError(ValueError):
    """The sampling-funnel input or frozen profile is invalid."""


def _object_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise FunnelError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_no_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FunnelError(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise FunnelError("JSON root must be object")
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise FunnelError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value: Any, name: str, lo: float = -math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FunnelError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < lo:
        raise FunnelError(f"{name} is out of range")
    return result


def _profile(path: Path) -> dict[str, Any]:
    profile = _load(path)
    if profile.get("schema_id") != PROFILE_SCHEMA:
        raise FunnelError("profile schema changed")
    if profile.get("input_denominator") != 512:
        raise FunnelError("input denominator changed")
    if profile.get("output_denominator") != 64:
        raise FunnelError("output denominator changed")
    quotas = profile.get("lane_quotas")
    if type(quotas) is not dict or sum(quotas.values()) != 64:
        raise FunnelError("lane quotas must total 64")
    if any(type(value) is not int or value <= 0 for value in quotas.values()):
        raise FunnelError("lane quotas must be positive integers")
    authority = profile.get("authority")
    if type(authority) is not dict or any(
        value is not False for value in authority.values()
    ):
        raise FunnelError("funnel authority escalated")
    return profile


def _candidate(
    raw: Any,
    index: int,
    lanes: set[str],
) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != CANDIDATE_FIELDS:
        raise FunnelError(f"candidate {index} field set")
    if raw["pool_index"] != index:
        raise FunnelError(f"candidate {index} reordered")
    lane = raw["lane"]
    if lane not in lanes:
        raise FunnelError(f"candidate {index} unknown lane")
    for key in raw:
        lowered = key.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
            raise FunnelError(f"candidate {index} contains result-dependent field")
    status = raw["status"]
    if status == "typed_failure":
        if type(raw["failure_code"]) is not str or not raw["failure_code"]:
            raise FunnelError(f"candidate {index} failure code")
        for key in (
            "source_sha256",
            "proposal_sha256",
            "coordinate_sha256",
            "minimum_vdw_ratio",
            "pocket_escape_angstrom",
            "shape_penalty",
            "anchor_penalty",
            "embedding",
        ):
            if raw[key] is not None:
                raise FunnelError(f"candidate {index} failure contains {key}")
        return raw
    if status != "generated" or raw["failure_code"] is not None:
        raise FunnelError(f"candidate {index} status")
    for key in ("source_sha256", "proposal_sha256", "coordinate_sha256"):
        if (
            type(raw[key]) is not str
            or len(raw[key]) != 64
            or any(character not in "0123456789abcdef" for character in raw[key])
        ):
            raise FunnelError(f"candidate {index} {key}")
    parsed = dict(raw)
    for key in (
        "minimum_vdw_ratio",
        "pocket_escape_angstrom",
        "shape_penalty",
        "anchor_penalty",
    ):
        parsed[key] = _number(raw[key], f"candidate {index} {key}", 0.0)
    embedding = raw["embedding"]
    if type(embedding) is not list or len(embedding) != 7:
        raise FunnelError(f"candidate {index} embedding")
    parsed["embedding"] = tuple(
        _number(value, f"embedding {index}") for value in embedding
    )
    return parsed


def _quality(row: dict[str, Any]) -> tuple[float, float, float, int]:
    return (
        row["shape_penalty"] + row["anchor_penalty"],
        row["shape_penalty"],
        row["anchor_penalty"],
        row["pool_index"],
    )


def _distance(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return math.sqrt(
        sum((left - right) ** 2 for left, right in zip(first, second, strict=True))
    )


def _select_lane(
    rows: list[dict[str, Any]],
    quota: int,
    multiplier: int,
) -> list[dict[str, Any]]:
    eligible = sorted(rows, key=_quality)[: quota * multiplier]
    if not eligible:
        return []
    selected = [eligible.pop(0)]
    while eligible and len(selected) < quota:
        chosen = max(
            eligible,
            key=lambda row: (
                min(
                    _distance(row["embedding"], picked["embedding"])
                    for picked in selected
                ),
                tuple(-value for value in _quality(row)),
            ),
        )
        eligible.remove(chosen)
        selected.append(chosen)
    return selected


def run(profile_path: Path, input_path: Path) -> dict[str, Any]:
    profile = _profile(profile_path)
    document = _load(input_path)
    if (
        document.get("schema_id") != INPUT_SCHEMA
        or document.get("profile_id") != profile["profile_id"]
    ):
        raise FunnelError("input identity changed")
    rows = document.get("candidates")
    if type(rows) is not list or len(rows) != 512:
        raise FunnelError("exactly 512 candidate rows required")
    lanes = set(profile["lane_quotas"])
    parsed = [_candidate(raw, index, lanes) for index, raw in enumerate(rows)]
    observations: list[dict[str, Any]] = []
    by_lane: dict[str, list[dict[str, Any]]] = {lane: [] for lane in lanes}
    for row in parsed:
        decision = "typed_failure"
        if row["status"] == "generated":
            if row["minimum_vdw_ratio"] < profile["hard_minimum_vdw_ratio"]:
                decision = "hard_reject_vdw"
            elif (
                row["pocket_escape_angstrom"]
                > profile["maximum_pocket_escape_angstrom"]
            ):
                decision = "hard_reject_pocket"
            else:
                decision = "eligible"
                by_lane[row["lane"]].append(row)
        observations.append(
            {
                "pool_index": row["pool_index"],
                "lane": row["lane"],
                "status": row["status"],
                "failure_code": row["failure_code"],
                "decision": decision,
            }
        )

    selected_rows: list[dict[str, Any]] = []
    lane_summary: dict[str, dict[str, int]] = {}
    for lane in sorted(lanes):
        quota = profile["lane_quotas"][lane]
        chosen = _select_lane(
            by_lane[lane], quota, profile["quality_prefilter_multiplier"]
        )
        for output_index in range(quota):
            if output_index < len(chosen):
                row = chosen[output_index]
                selected_rows.append(
                    {
                        "lane": lane,
                        "status": "selected",
                        "failure_code": None,
                        "source_pool_index": row["pool_index"],
                        "source_sha256": row["source_sha256"],
                        "proposal_sha256": row["proposal_sha256"],
                        "coordinate_sha256": row["coordinate_sha256"],
                    }
                )
            else:
                selected_rows.append(
                    {
                        "lane": lane,
                        "status": "typed_failure",
                        "failure_code": "lane_quota_unfilled",
                        "source_pool_index": None,
                        "source_sha256": None,
                        "proposal_sha256": None,
                        "coordinate_sha256": None,
                    }
                )
        lane_summary[lane] = {
            "quota": quota,
            "eligible_count": len(by_lane[lane]),
            "selected_count": len(chosen),
            "shortfall_count": quota - len(chosen),
        }
    if len(selected_rows) != 64:
        raise FunnelError("internal output denominator failure")
    output: dict[str, Any] = {
        "schema_id": OUTPUT_SCHEMA,
        "profile_id": profile["profile_id"],
        "input_denominator": 512,
        "output_denominator": 64,
        "input_sha256": _digest(document),
        "profile_sha256": _digest(profile),
        "observations": observations,
        "selected_rows": selected_rows,
        "lane_summary": lane_summary,
        "authority": {
            "fresh_128_execution_authorized": False,
            "scientific_claim_authorized": False,
            "benchmark_claim_authorized": False,
            "product_authorized": False,
            "rank_mutation_authorized": False,
        },
    }
    output["receipt_sha256"] = _digest(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output must be absent")
    try:
        result = run(args.profile, args.input)
    except FunnelError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "receipt_sha256": result["receipt_sha256"],
                "authority_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
