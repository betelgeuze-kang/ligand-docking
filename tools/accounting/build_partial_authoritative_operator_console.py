#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CA2_DAY_PLAN_JSON = "runs/ca2_evidence_closure_day_plan_current.json"
DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_NEXT_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_PXR_POLICY_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_OUT_JSON = "runs/partial_authoritative_operator_console_current.json"
DEFAULT_OUT_CSV = "runs/partial_authoritative_operator_console_current.csv"
DEFAULT_OUT_MD = "runs/partial_authoritative_operator_console_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_family_rows(
    ca2_day_plan: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    pxr_slice: dict[str, Any],
    pxr_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    ca2_summary = dict(ca2_day_plan.get("summary", {}) or {})
    ca2_readiness_s = dict(ca2_readiness.get("summary", {}) or {})
    pxr_readiness_s = dict(pxr_readiness.get("summary", {}) or {})
    pxr_slice_s = dict(pxr_slice.get("summary", {}) or {})
    pxr_policy_s = dict(pxr_policy.get("summary", {}) or {})

    return [
        {
            "family_rank": 1,
            "family": "ca2",
            "lane": "partial_authoritative",
            "ready_row_count": int(ca2_summary.get("ready_row_count", ca2_readiness_s.get("ready_row_count", 0)) or 0),
            "blocked_row_count": int(ca2_summary.get("blocked_row_count", ca2_readiness_s.get("blocked_row_count", 0)) or 0),
            "handoff_row_count": int(ca2_summary.get("today_focus_count", 0) or 0),
            "primary_blocker": str(ca2_summary.get("ship_blocker", ca2_readiness_s.get("most_common_missing_field", ""))).strip(),
            "day_scope": "today_core_negative_closure",
            "operator_note": str(ca2_summary.get("next_required_step", "")).strip(),
            "policy_note": "Keep OOD negatives parked while core review-only negatives are closed.",
        },
        {
            "family_rank": 2,
            "family": "pxr",
            "lane": "partial_authoritative",
            "ready_row_count": int(pxr_readiness_s.get("ready_for_apply_row_count", 0) or 0),
            "blocked_row_count": int(pxr_readiness_s.get("blocked_row_count", 0) or 0),
            "handoff_row_count": int(pxr_slice_s.get("row_count", 0) or 0),
            "primary_blocker": str(pxr_readiness_s.get("most_common_missing_field", "")).strip(),
            "day_scope": "pending_policy_triage",
            "operator_note": str(pxr_slice_s.get("next_required_step", "")).strip(),
            "policy_note": str(pxr_policy_s.get("policy_line", "")).strip(),
        },
    ]


def _build_console_rows(ca2_day_plan: dict[str, Any], pxr_slice: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in ca2_day_plan.get("today_focus_rows", []) or []:
        rows.append(
            {
                "console_rank": 0,
                "family": "ca2",
                "band": "today",
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("ligand", "")).strip(),
                "binder": 0,
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "next_required_action": "manual_negative_evidence_review",
                "recommended_resolution": str(row.get("recommended_resolution", "")).strip(),
            }
        )

    for row in pxr_slice.get("rows", []) or []:
        rows.append(
            {
                "console_rank": 0,
                "family": "pxr",
                "band": "today",
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "binder": int(row.get("replacement_is_binder", 0) or 0),
                "assay_type_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "recommended_resolution": "review_only" if str(row.get("next_required_action", "")).strip() == "manual_negative_evidence_review" else "defer_or_manual_curated_search",
            }
        )

    family_order = {"ca2": 0, "pxr": 1}
    rows.sort(key=lambda row: (family_order.get(row["family"], 9), row["priority_rank"], row["packet_step"]))
    for idx, row in enumerate(rows, start=1):
        row["console_rank"] = idx
    return rows


def build_payload(
    ca2_day_plan: dict[str, Any],
    ca2_readiness: dict[str, Any],
    pxr_readiness: dict[str, Any],
    pxr_slice: dict[str, Any],
    pxr_policy: dict[str, Any],
) -> dict[str, Any]:
    family_rows = _build_family_rows(ca2_day_plan, ca2_readiness, pxr_readiness, pxr_slice, pxr_policy)
    console_rows = _build_console_rows(ca2_day_plan, pxr_slice)

    summary = {
        "family_count": len(family_rows),
        "console_row_count": len(console_rows),
        "partial_authoritative_family_count": 2,
        "ready_row_count_total": sum(int(row["ready_row_count"]) for row in family_rows),
        "blocked_row_count_total": sum(int(row["blocked_row_count"]) for row in family_rows),
        "handoff_row_count_total": sum(int(row["handoff_row_count"]) for row in family_rows),
        "next_required_step": "Use CA2 for core negative evidence closure and PXR for pending-policy triage; keep both families inside partial-authoritative scope only.",
    }
    return {"summary": summary, "family_rows": family_rows, "console_rows": console_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Partial-Authoritative Operator Console",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- console_row_count: `{s['console_row_count']}`",
        f"- partial_authoritative_family_count: `{s['partial_authoritative_family_count']}`",
        f"- ready_row_count_total: `{s['ready_row_count_total']}`",
        f"- blocked_row_count_total: `{s['blocked_row_count_total']}`",
        f"- handoff_row_count_total: `{s['handoff_row_count_total']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Family Status",
        "",
        "| family | lane | ready_row_count | blocked_row_count | handoff_row_count | primary_blocker | day_scope |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['lane']}` | {row['ready_row_count']} | {row['blocked_row_count']} | "
            f"{row['handoff_row_count']} | `{row['primary_blocker']}` | `{row['day_scope']}` |"
        )
    lines.extend(
        [
            "",
            "## Operator Console",
            "",
            "| console_rank | family | priority_rank | packet_step | ligand | binder | assay_type_honesty | next_required_action | recommended_resolution |",
            "| ---: | --- | ---: | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in payload["console_rows"]:
        lines.append(
            f"| {row['console_rank']} | `{row['family']}` | {row['priority_rank']} | `{row['packet_step']}` | "
            f"`{row['ligand']}` | {row['binder']} | `{row['assay_type_honesty']}` | "
            f"`{row['next_required_action']}` | `{row['recommended_resolution']}` |"
        )
    lines.extend(
        [
            "",
            "## Handoff Notes",
            "",
        ]
    )
    for row in payload["family_rows"]:
        lines.append(f"- `{row['family']}`: {row['operator_note']}")
        lines.append(f"- `{row['family']}` policy: {row['policy_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2/PXR partial-authoritative operator console.")
    parser.add_argument("--ca2-day-plan-json", default=DEFAULT_CA2_DAY_PLAN_JSON)
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--pxr-next-slice-json", default=DEFAULT_PXR_NEXT_SLICE_JSON)
    parser.add_argument("--pxr-policy-json", default=DEFAULT_PXR_POLICY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_day_plan_json),
        _load_json(args.ca2_readiness_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.pxr_next_slice_json),
        _load_json(args.pxr_policy_json),
    )

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["console_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
