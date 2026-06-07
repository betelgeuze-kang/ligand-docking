#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON = "runs/aqp1_negative_slot_closure_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_NEGATIVE_ACQUISITION_JSON = "runs/aqp1_negative_evidence_acquisition_packet_current.json"
DEFAULT_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_slot_resolution_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_slot_resolution_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_slot_resolution_packet_current.md"

SLOT_ROLE_MAP = {
    "core_non_binder_01": {
        "slot_resolution_role": "primary_exact_source_reinvestigation",
        "primary_query_label": "pressure_induced_hemolysis_reinvestigation",
        "supporting_query_label": "",
        "exclusion_candidate_name": "",
    },
    "core_non_binder_02": {
        "slot_resolution_role": "acetazolamide_positive_boundary_exclusion",
        "primary_query_label": "acetazolamide_boundary_review",
        "supporting_query_label": "pressure_induced_hemolysis_reinvestigation",
        "exclusion_candidate_name": "acetazolamide",
    },
    "core_non_binder_03": {
        "slot_resolution_role": "tetraethylammonium_tool_reference_exclusion",
        "primary_query_label": "tetraethylammonium_boundary_review",
        "supporting_query_label": "pressure_induced_hemolysis_reinvestigation",
        "exclusion_candidate_name": "tetraethylammonium",
    },
}


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
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get(key)): dict(row)
        for row in rows
        if _text(row.get(key))
    }


def build_payload(
    negative_slot_closure_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    negative_acquisition_payload: dict[str, Any],
    negative_confirmation_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    slot_summary = dict((negative_slot_closure_payload or {}).get("summary", {}) or {})
    slot_rows = list((negative_slot_closure_payload or {}).get("rows", []) or [])
    exclusion_rows = list((negative_source_exclusion_payload or {}).get("rows", []) or [])
    acquisition_rows = list((negative_acquisition_payload or {}).get("rows", []) or [])
    confirmation_summary = dict((negative_confirmation_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    acquisition_by_label = _rows_by_key(acquisition_rows, "query_label")
    exclusion_by_name = _rows_by_key(exclusion_rows, "candidate_name")

    rows: list[dict[str, Any]] = []
    for rank, slot_row in enumerate(slot_rows, start=1):
        packet_step = _text(slot_row.get("packet_step"))
        role_cfg = SLOT_ROLE_MAP.get(packet_step, {})
        primary_query = acquisition_by_label.get(_text(role_cfg.get("primary_query_label")), {})
        supporting_query = acquisition_by_label.get(_text(role_cfg.get("supporting_query_label")), {})
        exclusion_row = exclusion_by_name.get(_text(role_cfg.get("exclusion_candidate_name")), {})
        rows.append(
            {
                "slot_resolution_rank": rank,
                "slot_rank": _int(slot_row.get("slot_rank")),
                "queue_priority_rank": _int(slot_row.get("queue_priority_rank")),
                "packet_step": packet_step,
                "current_ligand_id": _text(slot_row.get("current_ligand_id")),
                "slot_resolution_role": _text(role_cfg.get("slot_resolution_role")),
                "primary_query_label": _text(primary_query.get("query_label")),
                "primary_anchor_pmid": _text(primary_query.get("anchor_pmid")),
                "primary_anchor_title": _text(primary_query.get("anchor_title")),
                "primary_anchor_url": _text(primary_query.get("anchor_url")),
                "supporting_query_label": _text(supporting_query.get("query_label")),
                "supporting_anchor_pmid": _text(supporting_query.get("anchor_pmid")),
                "supporting_anchor_title": _text(supporting_query.get("anchor_title")),
                "supporting_anchor_url": _text(supporting_query.get("anchor_url")),
                "exclusion_candidate_name": _text(exclusion_row.get("candidate_name")),
                "exclusion_exact_target_pair_activity_count": _int(exclusion_row.get("exact_target_pair_activity_count")),
                "exclusion_activity_url": _text(exclusion_row.get("activity_url")),
                "exclusion_status": _text(exclusion_row.get("exclusion_status")),
                "confirmation_decision": _text(confirmation_summary.get("confirmation_decision"))
                or "keep_review_only_no_authoritative_negative_promotion",
                "reviewer_open_first": (
                    _text(primary_query.get("anchor_url"))
                    or _text(supporting_query.get("anchor_url"))
                    or _text(exclusion_row.get("activity_url"))
                ),
                "next_required_action": (
                    "keep_review_only_until_direct_negative_row_is_curated"
                ),
                "authoritative_apply_allowed": False,
            }
        )

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "top_packet_step": _text(rows[0].get("packet_step")) if rows else "",
        "primary_anchor_pmid": _text(rows[0].get("primary_anchor_pmid")) if rows else "",
        "acetazolamide_boundary_pmid": next(
            (
                _text(row.get("primary_anchor_pmid"))
                for row in rows
                if _text(row.get("packet_step")) == "core_non_binder_02"
            ),
            "",
        ),
        "tetraethylammonium_exact_target_pair_absent_count": sum(
            1
            for row in rows
            if _text(row.get("exclusion_candidate_name")) == "tetraethylammonium"
            and _int(row.get("exclusion_exact_target_pair_activity_count")) == 0
        ),
        "confirmation_decision": _text(confirmation_summary.get("confirmation_decision"))
        or "keep_review_only_no_authoritative_negative_promotion",
        "packet_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md",
        "next_required_step": (
            "Open core_non_binder_01 with PMID 23123479 first, keep core_non_binder_02 on the acetazolamide positive-boundary lane with PMID 40359885 plus exact-pair absence, "
            "and keep core_non_binder_03 on the tetraethylammonium tool-reference exclusion lane with exact-pair absence. Do not promote any slot until a direct transporter-specific quantitative negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Slot Resolution Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- top_packet_step: `{s['top_packet_step']}`",
        f"- primary_anchor_pmid: `{s['primary_anchor_pmid']}`",
        f"- acetazolamide_boundary_pmid: `{s['acetazolamide_boundary_pmid']}`",
        f"- tetraethylammonium_exact_target_pair_absent_count: `{s['tetraethylammonium_exact_target_pair_absent_count']}`",
        f"- confirmation_decision: `{s['confirmation_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Slot Rows",
        "",
        "| slot_resolution_rank | packet_step | slot_resolution_role | primary_anchor_pmid | exclusion_candidate_name | exclusion_exact_target_pair_activity_count |",
        "| ---: | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['slot_resolution_rank']} | `{row['packet_step']}` | `{row['slot_resolution_role']}` | "
            f"`{row['primary_anchor_pmid']}` | `{row['exclusion_candidate_name'] or '-'}` | "
            f"{row['exclusion_exact_target_pair_activity_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative slot resolution packet.")
    parser.add_argument("--negative-slot-closure-json", default=DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--negative-acquisition-json", default=DEFAULT_NEGATIVE_ACQUISITION_JSON)
    parser.add_argument("--negative-confirmation-json", default=DEFAULT_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_slot_closure_json),
        _load_json(args.negative_source_exclusion_json),
        _load_json(args.negative_acquisition_json),
        _load_json(args.negative_confirmation_json),
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
