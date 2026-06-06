#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_GAP_MATRIX_JSON = RUNS / "aqp1_negative_evidence_gap_matrix_current.json"
DEFAULT_NEGATIVE_QUEUE_JSON = RUNS / "transporter_negative_evidence_closure_queue_current.json"
DEFAULT_EXACT_SOURCE_JSON = RUNS / "aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "aqp1_negative_evidence_request_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_negative_evidence_request_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_negative_evidence_request_packet_current.md"

TARGET_ID = "AQP1"
DEFAULT_TARGET_UNIPROT = "P29972"
DEFAULT_TARGET_CHEMBL = "CHEMBL4523210"
ACCEPTABLE_ASSAY_MODES = (
    "human_aqp1_water_permeability_or_flux;human_aqp1_oocyte_or_proteoliposome_transport;"
    "human_erythrocyte_aqp1_attributed_transport;exact_target_pair_binding_or_functional_no_effect"
)
REQUIRED_FIELDS = (
    "molecule_identity;target_id;target_organism;assay_context;endpoint;standard_relation;standard_value;"
    "standard_units;concentration_or_curve_range;replicate_or_error_model;primary_source;split_assignment;reference_meta"
)
EXCLUDED_SHORTCUTS = "tetraethylammonium_tool_reference;acetazolamide_boundary_context;dimethyl_sulfoxide_solvent_context"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _aqp1_slots(negative_queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in negative_queue_payload.get("rows", []) or []
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("packet_step")).startswith("core_non_binder")
    ]
    if rows:
        return sorted(rows, key=lambda row: (_int(row.get("queue_rank")), _text(row.get("queue_id"))))
    return [
        {
            "queue_rank": idx,
            "queue_id": f"{TARGET_ID}__core_non_binder_0{idx}",
            "target_id": TARGET_ID,
            "packet_step": f"core_non_binder_0{idx}",
        }
        for idx in range(1, 4)
    ]


def _primary_probe(exact_source_payload: dict[str, Any]) -> dict[str, str]:
    summary = dict(exact_source_payload.get("summary", {}) or {})
    candidate = _text(summary.get("primary_negative_probe_candidate")) or "sodium nitroprusside"
    source_pmid = _text(summary.get("source_pmid")) or "23123479"
    return {"candidate": candidate, "source_pmid": source_pmid}


def build_payload(
    gap_matrix_payload: dict[str, Any],
    negative_queue_payload: dict[str, Any],
    exact_source_payload: dict[str, Any],
) -> dict[str, Any]:
    gap_summary = dict(gap_matrix_payload.get("summary", {}) or {})
    probe = _primary_probe(exact_source_payload)
    slots = _aqp1_slots(negative_queue_payload)
    target_uniprot = _text(gap_summary.get("target_uniprot_accession")) or DEFAULT_TARGET_UNIPROT
    target_chembl = _text(gap_summary.get("target_chembl_id")) or DEFAULT_TARGET_CHEMBL
    source_gap_matrix = _text(gap_summary.get("packet_artifact")) or "runs/aqp1_negative_evidence_gap_matrix_current.md"

    rows: list[dict[str, Any]] = []
    for idx, slot in enumerate(slots, start=1):
        candidate_scope = (
            probe["candidate"]
            if idx == 1
            else f"independent_exact_aqp1_nonbinder_candidate_0{idx - 1}"
        )
        rows.append(
            {
                "request_rank": idx,
                "slot_queue_rank": _int(slot.get("queue_rank")),
                "slot_queue_id": _text(slot.get("queue_id")),
                "packet_step": _text(slot.get("packet_step")),
                "target_id": TARGET_ID,
                "target_uniprot_accession": target_uniprot,
                "target_chembl_id": target_chembl,
                "candidate_scope": candidate_scope,
                "candidate_source_context": (
                    f"PMID:{probe['source_pmid']} review-only context"
                    if idx == 1
                    else "new public primary-source row or internal assay row required"
                ),
                "acceptable_assay_modes": ACCEPTABLE_ASSAY_MODES,
                "minimum_required_fields": REQUIRED_FIELDS,
                "excluded_shortcuts": EXCLUDED_SHORTCUTS,
                "minimum_acceptance_rule": (
                    "exact human AQP1 target-pair quantitative weak/no-effect evidence with negative semantics; "
                    "must include units and primary-source provenance"
                ),
                "requested_output_schema": (
                    "candidate_name,molecule_id,target_id,target_accession,assay_context,endpoint,"
                    "standard_type,standard_relation,standard_value,standard_units,source_id,split_id,reference_meta_id"
                ),
                "current_evidence_state": "missing_direct_quantitative_negative_row",
                "request_status": "open",
                "authoritative_negative_apply_allowed": False,
                "claim_promotion_allowed": False,
                "next_required_action": (
                    "Acquire or curate an exact target-pair quantitative AQP1 negative row for this slot; "
                    "do not use review-only, solvent-only, boundary, or caution-reference context."
                ),
            }
        )

    current_direct_negative_count = _int(gap_summary.get("direct_negative_quantitative_row_found_count"))
    slot_count = _int(gap_summary.get("negative_slot_count")) or len(rows)
    cover_ready_count = min(slot_count, current_direct_negative_count)
    cover_missing_count = max(0, slot_count - cover_ready_count)
    closure_allowed = bool(gap_summary.get("negative_evidence_closure_allowed", False)) or cover_ready_count >= slot_count
    summary = {
        "evidence_request_ready": True,
        "packet_artifact": "runs/aqp1_negative_evidence_request_packet_current.md",
        "source_gap_matrix_artifact": source_gap_matrix,
        "target_id": TARGET_ID,
        "target_uniprot_accession": target_uniprot,
        "target_chembl_id": target_chembl,
        "request_mode": "exact_target_pair_quantitative_negative_evidence_required",
        "request_row_count": len(rows),
        "required_assignable_negative_row_count": slot_count,
        "current_direct_negative_quantitative_row_found_count": current_direct_negative_count,
        "negative_slot_cover_ready_count": cover_ready_count,
        "negative_slot_cover_missing_count": cover_missing_count,
        "blocked_gap_route_count": _int(gap_summary.get("blocked_route_count")),
        "review_context_route_count": _int(gap_summary.get("review_context_route_count")),
        "public_reinterpretation_exhausted": not closure_allowed,
        "internal_wetlab_or_primary_source_required": not closure_allowed,
        "acceptable_assay_modes": ACCEPTABLE_ASSAY_MODES,
        "minimum_required_fields": REQUIRED_FIELDS,
        "excluded_shortcuts": EXCLUDED_SHORTCUTS,
        "authoritative_negative_apply_allowed_count": _int(
            gap_summary.get("authoritative_negative_apply_allowed_count")
        ),
        "negative_evidence_closure_allowed": closure_allowed,
        "claim_promotion_allowed": False,
        "request_status": "ready_for_public_or_internal_exact_evidence_acquisition",
        "next_required_step": (
            "AQP1 assignable negative rows are covered; run the intake and transporter authoritative apply gates."
            if closure_allowed
            else (
                "Use this packet as the AQP1 closure ask: fill three assignable negative rows with exact human AQP1 "
                "quantitative weak/no-effect evidence, then update split/reference/meta packets before any authoritative apply."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Evidence Request Packet",
        "",
        f"- evidence_request_ready: `{s['evidence_request_ready']}`",
        f"- source_gap_matrix_artifact: `{s['source_gap_matrix_artifact']}`",
        f"- target_id: `{s['target_id']}`",
        f"- target_uniprot_accession: `{s['target_uniprot_accession']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- request_mode: `{s['request_mode']}`",
        f"- request_row_count: `{s['request_row_count']}`",
        f"- required_assignable_negative_row_count: `{s['required_assignable_negative_row_count']}`",
        f"- current_direct_negative_quantitative_row_found_count: `{s['current_direct_negative_quantitative_row_found_count']}`",
        f"- negative_slot_cover: `{s['negative_slot_cover_ready_count']}/{s['required_assignable_negative_row_count']}`",
        f"- negative_slot_cover_missing_count: `{s['negative_slot_cover_missing_count']}`",
        f"- blocked_gap_route_count: `{s['blocked_gap_route_count']}`",
        f"- review_context_route_count: `{s['review_context_route_count']}`",
        f"- public_reinterpretation_exhausted: `{s['public_reinterpretation_exhausted']}`",
        f"- internal_wetlab_or_primary_source_required: `{s['internal_wetlab_or_primary_source_required']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- request_status: `{s['request_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Request Rows",
        "",
        "| rank | slot | candidate_scope | acceptable_assay_modes | minimum_acceptance_rule | status |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['request_rank']} | `{row['slot_queue_id']}` | `{row['candidate_scope']}` | "
            f"`{row['acceptable_assay_modes']}` | `{row['minimum_acceptance_rule']}` | `{row['request_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 exact negative-evidence request packet.")
    parser.add_argument("--gap-matrix-json", default=str(DEFAULT_GAP_MATRIX_JSON))
    parser.add_argument("--negative-queue-json", default=str(DEFAULT_NEGATIVE_QUEUE_JSON))
    parser.add_argument("--exact-source-json", default=str(DEFAULT_EXACT_SOURCE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.gap_matrix_json),
        _load_json(args.negative_queue_json),
        _load_json(args.exact_source_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
