#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GAP_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_ROLLUP_JSON = "runs/family_expansion_status_rollup_current.json"
DEFAULT_PLACEHOLDER_JSON = "runs/transporter_placeholder_burndown_queue_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_KEEP_GREEN_TREND_JSON = "runs/keep_green_regression_trend_packet_current.json"
DEFAULT_OUT_JSON = "runs/platform_gap_taxonomy_packet_current.json"
DEFAULT_OUT_CSV = "runs/platform_gap_taxonomy_packet_current.csv"
DEFAULT_OUT_MD = "runs/platform_gap_taxonomy_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "ok", "pass", "passed"}


def _find_rollup_row(rollup_payload: dict[str, Any], family: str) -> dict[str, Any]:
    for row in rollup_payload.get("rows", []) or []:
        if _text(row.get("family")).lower() == family.lower():
            return dict(row)
    return {}


def build_payload(
    gap_payload: dict[str, Any],
    rollup_payload: dict[str, Any],
    placeholder_payload: dict[str, Any],
    local_engine_queue_payload: dict[str, Any],
    keep_green_trend_payload: dict[str, Any],
) -> dict[str, Any]:
    gap = _summary(gap_payload)
    placeholder = _summary(placeholder_payload)
    engine = _summary(local_engine_queue_payload)
    trend = _summary(keep_green_trend_payload)
    ca2_row = _find_rollup_row(rollup_payload, "ca2")
    pxr_row = _find_rollup_row(rollup_payload, "pxr")
    aqp1_row = _find_rollup_row(rollup_payload, "aqp1")
    ligand_claim_safe = _bool(gap.get("ligand_scaleup_claim_safe"))
    ligand_suite_count = _int(gap.get("ligand_scaleup_suite_count"))
    ligand_commercialization_ready_suite_count = _int(
        gap.get("ligand_scaleup_commercialization_ready_suite_count")
    )
    ligand_pending_suite_count = max(0, ligand_suite_count - ligand_commercialization_ready_suite_count)

    rows = [
        {
            "gap_rank": 1,
            "gap_id": "keep_green_repeated_history",
            "scope": "restricted_local_delivery",
            "family_or_lane": "nightly,viewer,wetlab,refresh",
            "gap_class": "keep_green_history",
            "current_status": _text(trend.get("commercial_trend_status")) or "missing_trend_packet",
            "current_blocker_count": 0 if _bool(trend.get("all_current_green")) else 1,
            "expansion_blocker_count": _int(trend.get("insufficient_history_lane_count")),
            "primary_metric": "repeated_history_ready_lane_count",
            "primary_value": f"{_int(trend.get('repeated_history_ready_lane_count'))}/{_int(trend.get('lane_count'))}",
            "source_artifact": _text(trend.get("packet_artifact")) or DEFAULT_KEEP_GREEN_TREND_JSON,
            "next_required_step": _text(trend.get("next_required_step")),
        },
        {
            "gap_rank": 2,
            "gap_id": "ligand_scaleup_regression_guardrail",
            "scope": "expanded_commercialization",
            "family_or_lane": "gpcr,ion_channel,kinase scaleup",
            "gap_class": "scaleup_regression_guardrail",
            "current_status": _text(gap.get("ligand_scaleup_claim_safe_status")),
            "current_blocker_count": 0,
            "expansion_blocker_count": 1 if not _bool(gap.get("ligand_scaleup_claim_safe")) else 0,
            "primary_metric": "commercialization_ready_suite_count",
            "primary_value": f"{_int(gap.get('ligand_scaleup_commercialization_ready_suite_count'))}/{_int(gap.get('ligand_scaleup_suite_count'))}",
            "source_artifact": "runs/commercialization_gap_burndown_current.json",
            "next_required_step": _text(gap.get("ligand_scaleup_next_required_step")),
        },
        {
            "gap_rank": 3,
            "gap_id": "ligand_scaleup_suite_completion",
            "scope": "expanded_commercialization",
            "family_or_lane": "gpcr,ion_channel,kinase scaleup",
            "gap_class": "scaleup_suite_completion",
            "current_status": "suite_completion_pending" if ligand_pending_suite_count else "suite_completion_ready",
            "current_blocker_count": 0,
            "expansion_blocker_count": ligand_pending_suite_count if ligand_claim_safe else 0,
            "primary_metric": "commercialization_ready_suite_count",
            "primary_value": f"{ligand_commercialization_ready_suite_count}/{ligand_suite_count}",
            "source_artifact": "runs/ligand_scaleup_suite_status_current.md",
            "next_required_step": _text(gap.get("ligand_scaleup_next_required_step")),
        },
        {
            "gap_rank": 4,
            "gap_id": "transporter_negative_placeholder_rows",
            "scope": "parked_science_expansion",
            "family_or_lane": "transporter",
            "gap_class": "evidence_blocked_placeholder_rows",
            "current_status": _text(engine.get("top_priority_status")) or "parked",
            "current_blocker_count": 0,
            "expansion_blocker_count": _int(placeholder.get("evidence_blocked_placeholder_rows")),
            "primary_metric": "evidence_blocked_placeholder_rows",
            "primary_value": _int(placeholder.get("evidence_blocked_placeholder_rows")),
            "source_artifact": _text(placeholder.get("packet_artifact")) or "runs/transporter_placeholder_burndown_queue_current.md",
            "next_required_step": _text(placeholder.get("next_required_step")),
        },
        {
            "gap_rank": 5,
            "gap_id": "aqp1_claim_safe_kcal_gap",
            "scope": "parked_science_expansion",
            "family_or_lane": "AQP1",
            "gap_class": "claim_safe_kcal_gap",
            "current_status": "review_only_functional_activity",
            "current_blocker_count": 0,
            "expansion_blocker_count": 1,
            "primary_metric": "ready_like_count",
            "primary_value": _int(aqp1_row.get("ready_like_count")),
            "source_artifact": "runs/family_expansion_status_rollup_current.json",
            "next_required_step": _text(aqp1_row.get("next_required_step")),
        },
        {
            "gap_rank": 6,
            "gap_id": "ca2_pxr_review_only_evidence_policy",
            "scope": "expanded_family_claims",
            "family_or_lane": "CA2,PXR",
            "gap_class": "review_only_evidence_policy",
            "current_status": "source_linked_review_policy",
            "current_blocker_count": 0,
            "expansion_blocker_count": _int(ca2_row.get("ready_like_count")) + _int(pxr_row.get("ready_like_count")),
            "primary_metric": "source_linked_total",
            "primary_value": _int(ca2_row.get("source_linked_count")) + _int(pxr_row.get("source_linked_count")),
            "source_artifact": "runs/family_expansion_status_rollup_current.json",
            "next_required_step": "; ".join(
                part for part in [_text(ca2_row.get("next_required_step")), _text(pxr_row.get("next_required_step"))] if part
            ),
        },
    ]

    current_delivery_blocker_count = sum(_int(row.get("current_blocker_count")) for row in rows)
    expansion_blocker_count = sum(_int(row.get("expansion_blocker_count")) for row in rows)
    non_transporter_gap_count = sum(1 for row in rows if _text(row.get("family_or_lane")).lower() != "transporter")
    top_expansion_gap = next((row for row in rows if _int(row.get("expansion_blocker_count")) > 0), rows[0])
    summary = {
        "packet_ready": True,
        "packet_artifact": "runs/platform_gap_taxonomy_packet_current.md",
        "platform_gap_count": len(rows),
        "current_delivery_blocker_count": current_delivery_blocker_count,
        "expansion_blocker_count": expansion_blocker_count,
        "non_transporter_gap_count": non_transporter_gap_count,
        "transporter_specific_split_resolved": non_transporter_gap_count > 0,
        "top_expansion_gap_id": _text(top_expansion_gap.get("gap_id")),
        "top_expansion_gap_class": _text(top_expansion_gap.get("gap_class")),
        "top_expansion_gap_scope": _text(top_expansion_gap.get("scope")),
        "placeholder_driven_rows": _int(placeholder.get("placeholder_driven_rows")),
        "evidence_blocked_placeholder_rows": _int(placeholder.get("evidence_blocked_placeholder_rows")),
        "ligand_scaleup_commercialization_ready_suite_count": ligand_commercialization_ready_suite_count,
        "ligand_scaleup_suite_count": ligand_suite_count,
        "ligand_scaleup_suite_completion_pending_count": ligand_pending_suite_count,
        "ligand_scaleup_claim_safe_status": _text(gap.get("ligand_scaleup_claim_safe_status")),
        "ligand_scaleup_gpcr_guardrail_frontier_status": _text(
            gap.get("ligand_scaleup_gpcr_guardrail_frontier_status")
        ),
        "keep_green_insufficient_history_lane_count": _int(trend.get("insufficient_history_lane_count")),
        "next_required_step": (
            "Keep the restricted local delivery claim green, but treat broader commercialization as blocked by "
            f"`{_text(top_expansion_gap.get('gap_id'))}` first; keep transporter negative evidence parked outside the delivery scope."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Platform Gap Taxonomy Packet",
        "",
        f"- packet_ready: `{s['packet_ready']}`",
        f"- platform_gap_count: `{s['platform_gap_count']}`",
        f"- current_delivery_blocker_count: `{s['current_delivery_blocker_count']}`",
        f"- expansion_blocker_count: `{s['expansion_blocker_count']}`",
        f"- non_transporter_gap_count: `{s['non_transporter_gap_count']}`",
        f"- transporter_specific_split_resolved: `{s['transporter_specific_split_resolved']}`",
        f"- top_expansion_gap_id: `{s['top_expansion_gap_id']}`",
        f"- top_expansion_gap_class: `{s['top_expansion_gap_class']}`",
        f"- top_expansion_gap_scope: `{s['top_expansion_gap_scope']}`",
        f"- ligand_scaleup_claim_safe_status: `{s['ligand_scaleup_claim_safe_status']}`",
        f"- ligand_scaleup_gpcr_guardrail_frontier_status: `{s['ligand_scaleup_gpcr_guardrail_frontier_status']}`",
        f"- ligand_scaleup_suite_completion_pending_count: `{s['ligand_scaleup_suite_completion_pending_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Gap Rows",
        "",
        "| gap_rank | gap_id | scope | family_or_lane | gap_class | current_blocker_count | expansion_blocker_count | primary_value |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['gap_rank']} | `{row['gap_id']}` | `{row['scope']}` | `{row['family_or_lane']}` | "
            f"`{row['gap_class']}` | {row['current_blocker_count']} | {row['expansion_blocker_count']} | `{row['primary_value']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build platform-wide commercialization gap taxonomy packet.")
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--rollup-json", default=DEFAULT_ROLLUP_JSON)
    parser.add_argument("--placeholder-json", default=DEFAULT_PLACEHOLDER_JSON)
    parser.add_argument("--local-engine-queue-json", default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON)
    parser.add_argument("--keep-green-trend-json", default=DEFAULT_KEEP_GREEN_TREND_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.gap_json),
        _load_json(args.rollup_json),
        _load_json(args.placeholder_json),
        _load_json(args.local_engine_queue_json),
        _load_json(args.keep_green_trend_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
