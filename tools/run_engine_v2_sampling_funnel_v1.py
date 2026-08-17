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
    "pool_index", "lane", "status", "failure_code", "source_sha256",
    "proposal_sha256", "coordinate_sha256", "minimum_vdw_ratio",
    "pocket_escape_angstrom", "shape_penalty", "anchor_penalty", "embedding",
}


class FunnelError(ValueError):
    pass


def object_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise FunnelError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    if type(value) is not dict:
        raise FunnelError("JSON root must be object")
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def number(value: Any, name: str, lo: float = -math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FunnelError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < lo:
        raise FunnelError(f"{name} is out of range")
    return result


def profile(path: Path) -> dict[str, Any]:
    p = load(path)
    if p.get("schema_id") != PROFILE_SCHEMA:
        raise FunnelError("profile schema changed")
    if p.get("input_denominator") != 512 or p.get("output_denominator") != 64:
        raise FunnelError("funnel denominators changed")
    quotas = p.get("lane_quotas")
    if type(quotas) is not dict or sum(quotas.values()) != 64:
        raise FunnelError("lane quotas must total 64")
    if any(type(v) is not int or v <= 0 for v in quotas.values()):
        raise FunnelError("lane quotas must be positive integers")
    authority = p.get("authority")
    if type(authority) is not dict or any(v is not False for v in authority.values()):
        raise FunnelError("funnel authority escalated")
    return p


def candidate(raw: Any, index: int, lanes: set[str]) -> dict[str, Any]:
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
            "source_sha256", "proposal_sha256", "coordinate_sha256",
            "minimum_vdw_ratio", "pocket_escape_angstrom",
            "shape_penalty", "anchor_penalty", "embedding",
        ):
            if raw[key] is not None:
                raise FunnelError(f"candidate {index} failure contains {key}")
        return raw
    if status != "generated" or raw["failure_code"] is not None:
        raise FunnelError(f"candidate {index} status")
    for key in ("source_sha256", "proposal_sha256", "coordinate_sha256"):
        if type(raw[key]) is not str or len(raw[key]) != 64:
            raise FunnelError(f"candidate {index} {key}")
    parsed = dict(raw)
    for key in (
        "minimum_vdw_ratio", "pocket_escape_angstrom",
        "shape_penalty", "anchor_penalty",
    ):
        parsed[key] = number(raw[key], f"candidate {index} {key}", 0.0)
    embedding = raw["embedding"]
    if type(embedding) is not list or len(embedding) != 7:
        raise FunnelError(f"candidate {index} embedding")
    parsed["embedding"] = tuple(number(x, f"embedding {index}") for x in embedding)
    return parsed


def quality(row: dict[str, Any]) -> tuple[float, float, float, int]:
    return (
        row["shape_penalty"] + row["anchor_penalty"],
        row["shape_penalty"], row["anchor_penalty"], row["pool_index"],
    )


def distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def select_lane(rows: list[dict[str, Any]], quota: int, multiplier: int) -> list[dict[str, Any]]:
    eligible = sorted(rows, key=quality)[: quota * multiplier]
    if not eligible:
        return []
    selected = [eligible.pop(0)]
    while eligible and len(selected) < quota:
        chosen = max(
            eligible,
            key=lambda row: (
                min(distance(row["embedding"], picked["embedding"]) for picked in selected),
                tuple(-x if isinstance(x, float) else -x for x in quality(row)),
            ),
        )
        eligible.remove(chosen)
        selected.append(chosen)
    return selected


def run(profile_path: Path, input_path: Path) -> dict[str, Any]:
    p = profile(profile_path)
    doc = load(input_path)
    if doc.get("schema_id") != INPUT_SCHEMA or doc.get("profile_id") != p["profile_id"]:
        raise FunnelError("input identity changed")
    rows = doc.get("candidates")
    if type(rows) is not list or len(rows) != 512:
        raise FunnelError("exactly 512 candidate rows required")
    lanes = set(p["lane_quotas"])
    parsed = [candidate(raw, i, lanes) for i, raw in enumerate(rows)]
    observations = []
    by_lane: dict[str, list[dict[str, Any]]] = {lane: [] for lane in lanes}
    for row in parsed:
        decision = "typed_failure"
        if row["status"] == "generated":
            if row["minimum_vdw_ratio"] < p["hard_minimum_vdw_ratio"]:
                decision = "hard_reject_vdw"
            elif row["pocket_escape_angstrom"] > p["maximum_pocket_escape_angstrom"]:
                decision = "hard_reject_pocket"
            else:
                decision = "eligible"
                by_lane[row["lane"]].append(row)
        observations.append({
            "pool_index": row["pool_index"], "lane": row["lane"],
            "status": row["status"], "failure_code": row["failure_code"],
            "decision": decision,
        })

    selected_rows = []
    lane_summary = {}
    for lane in sorted(lanes):
        quota = p["lane_quotas"][lane]
        chosen = select_lane(by_lane[lane], quota, p["quality_prefilter_multiplier"])
        for output_index in range(quota):
            if output_index < len(chosen):
                row = chosen[output_index]
                selected_rows.append({
                    "lane": lane, "status": "selected", "failure_code": None,
                    "source_pool_index": row["pool_index"],
                    "source_sha256": row["source_sha256"],
                    "proposal_sha256": row["proposal_sha256"],
                    "coordinate_sha256": row["coordinate_sha256"],
                })
            else:
                selected_rows.append({
                    "lane": lane, "status": "typed_failure",
                    "failure_code": "lane_quota_unfilled",
                    "source_pool_index": None, "source_sha256": None,
                    "proposal_sha256": None, "coordinate_sha256": None,
                })
        lane_summary[lane] = {
            "quota": quota,
            "eligible_count": len(by_lane[lane]),
            "selected_count": len(chosen),
            "shortfall_count": quota - len(chosen),
        }
    if len(selected_rows) != 64:
        raise FunnelError("internal output denominator failure")
    output = {
        "schema_id": OUTPUT_SCHEMA, "profile_id": p["profile_id"],
        "input_denominator": 512, "output_denominator": 64,
        "input_sha256": digest(doc), "profile_sha256": digest(p),
        "observations": observations, "selected_rows": selected_rows,
        "lane_summary": lane_summary,
        "authority": {
            "fresh_128_execution_authorized": False,
            "scientific_claim_authorized": False,
            "benchmark_claim_authorized": False,
            "product_authorized": False,
            "rank_mutation_authorized": False,
        },
    }
    output["receipt_sha256"] = digest(output)
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
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"ok": True, "receipt_sha256": result["receipt_sha256"], "authority_granted": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
