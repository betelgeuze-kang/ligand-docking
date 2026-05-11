#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON = "runs/aqp1_negative_slot_closure_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_NEGATIVE_ACQUISITION_JSON = "runs/aqp1_negative_evidence_acquisition_packet_current.json"
DEFAULT_NEGATIVE_EXACT_SOURCE_OUTCOME_JSON = "runs/aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_evidence_confirmation_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_evidence_confirmation_packet_current.md"

PRIMARY_ANCHOR_PMID = "23123479"
PRIMARY_ANCHOR_TITLE = "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes."
BOUNDARY_POSITIVE_PMID = "40359885"
BOUNDARY_POSITIVE_TITLE = "Acetazolamide as an aquaporin 1 inhibitor mitigates rheumatoid arthritis by reducing angiogenesis via the modulation of the FAK-PI3K/Akt signaling pathway."


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


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _count_rows(rows: list[dict[str, Any]], key: str, expected: Any) -> int:
    return sum(1 for row in rows if row.get(key) == expected)


def build_payload(
    negative_slot_closure_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    negative_acquisition_payload: dict[str, Any],
    negative_exact_source_outcome_payload: dict[str, Any] | None = None,
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    slot_summary = dict((negative_slot_closure_payload or {}).get("summary", {}) or {})
    slot_rows = list((negative_slot_closure_payload or {}).get("rows", []) or [])
    exclusion_summary = dict((negative_source_exclusion_payload or {}).get("summary", {}) or {})
    acquisition_summary = dict((negative_acquisition_payload or {}).get("summary", {}) or {})
    exact_source_summary = dict((negative_exact_source_outcome_payload or {}).get("summary", {}) or {})
    exact_source_rows = list((negative_exact_source_outcome_payload or {}).get("rows", []) or [])
    today = as_of_date or date.today().isoformat()

    primary_anchor_pmid = (
        _text(acquisition_summary.get("primary_anchor_pmid"))
        or _text(exact_source_summary.get("source_pmid"))
        or PRIMARY_ANCHOR_PMID
    )
    primary_anchor_url = (
        _text(acquisition_summary.get("primary_anchor_url"))
        or f"https://pubmed.ncbi.nlm.nih.gov/{primary_anchor_pmid}/"
    )
    primary_anchor_title = PRIMARY_ANCHOR_TITLE
    boundary_positive_url = f"https://pubmed.ncbi.nlm.nih.gov/{BOUNDARY_POSITIVE_PMID}/"
    exact_source_row_count = _int(exact_source_summary.get("row_count")) or len(exact_source_rows)
    almost_unaffected_candidate_count = _int(
        exact_source_summary.get("almost_unaffected_candidate_count")
    ) or _count_rows(exact_source_rows, "hemolysis_outcome", "almost_unaffected_at_200_mpa")
    direct_negative_quantitative_row_found_count = _int(
        exact_source_summary.get("direct_negative_quantitative_row_found_count")
    ) or sum(
        1
        for row in exact_source_rows
        if _bool(row.get("direct_transporter_specific_quantitative_negative_row_found"))
    )
    authoritative_negative_apply_allowed_count = _int(
        exact_source_summary.get("authoritative_negative_apply_allowed_count")
    ) or sum(1 for row in exact_source_rows if _bool(row.get("authoritative_negative_apply_allowed")))
    exact_source_endpoint = _text(exact_source_summary.get("source_endpoint")) or "hemolysis_at_200_mpa"
    small_inhibitor_signal_candidate = _text(exact_source_summary.get("small_inhibitor_signal_candidate"))

    rows: list[dict[str, Any]] = []
    for rank, slot_row in enumerate(slot_rows, start=1):
        rows.append(
            {
                "confirmation_rank": rank,
                "slot_rank": _int(slot_row.get("slot_rank")),
                "queue_priority_rank": _int(slot_row.get("queue_priority_rank")),
                "packet_step": _text(slot_row.get("packet_step")),
                "current_ligand_id": _text(slot_row.get("current_ligand_id")),
                "review_bucket": _text(slot_row.get("review_bucket")),
                "closure_status": _text(slot_row.get("closure_status")),
                "confirmation_scope": "review_only_negative_confirmation",
                "primary_anchor_pmid": primary_anchor_pmid,
                "primary_anchor_title": primary_anchor_title,
                "primary_anchor_url": primary_anchor_url,
                "positive_boundary_pmid": BOUNDARY_POSITIVE_PMID,
                "positive_boundary_title": BOUNDARY_POSITIVE_TITLE,
                "positive_boundary_url": boundary_positive_url,
                "exclusion_primary_focus_ligand": _text(exclusion_summary.get("primary_focus_ligand")),
                "exact_target_pair_absent_count": _int(exclusion_summary.get("exact_target_pair_absent_count")),
                "primary_anchor_outcome_row_count": exact_source_row_count,
                "primary_anchor_source_endpoint": exact_source_endpoint,
                "primary_anchor_almost_unaffected_candidate_count": almost_unaffected_candidate_count,
                "primary_anchor_small_inhibitor_signal_candidate": small_inhibitor_signal_candidate,
                "primary_anchor_direct_negative_quantitative_row_found_count": direct_negative_quantitative_row_found_count,
                "primary_anchor_authoritative_negative_apply_allowed_count": authoritative_negative_apply_allowed_count,
                "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
                "decision_rationale": (
                    "Use the 2012 reinvestigation outcome rows as the exact-source confirmation anchor, treat the 2025 acetazolamide paper as positive boundary context only, "
                    "and keep ChEMBL exact-pair absence confined to exclusion-context support rather than promoting any authoritative negative replacement row."
                ),
                "acceptance_gate": (
                    "Accept only a direct transporter-specific quantitative negative row with unambiguous ligand identity, human-relevant target context, and claim-safe provenance."
                ),
                "rejection_gate": (
                    "Reject exact-pair-absent caution references, contested system-effect papers, and positive-boundary literature as authoritative negative replacement rows."
                ),
                "capture_instruction": (
                    "Keep the slot review-only, cite PMID 23123479 as the first confirmation anchor, keep PMID 40359885 as boundary-only context, and leave replacement_reference_binding_kcal_mol blank."
                ),
                "authoritative_apply_allowed": False,
            }
        )

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "top_packet_step": _text(rows[0].get("packet_step")) if rows else "",
        "primary_focus_ligand": _text(rows[0].get("current_ligand_id")) if rows else "",
        "primary_confirmation_scope": "review_only_negative_confirmation",
        "primary_anchor_pmid": primary_anchor_pmid,
        "primary_anchor_url": primary_anchor_url,
        "boundary_positive_pmid": BOUNDARY_POSITIVE_PMID,
        "boundary_positive_url": boundary_positive_url,
        "exact_target_pair_absent_count": _int(exclusion_summary.get("exact_target_pair_absent_count")),
        "primary_anchor_outcome_row_count": exact_source_row_count,
        "primary_anchor_source_endpoint": exact_source_endpoint,
        "primary_anchor_almost_unaffected_candidate_count": almost_unaffected_candidate_count,
        "primary_anchor_small_inhibitor_signal_candidate": small_inhibitor_signal_candidate,
        "primary_anchor_direct_negative_quantitative_row_found_count": direct_negative_quantitative_row_found_count,
        "primary_anchor_authoritative_negative_apply_allowed_count": authoritative_negative_apply_allowed_count,
        "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
        "packet_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
        "next_required_step": (
            "Use PMID 23123479 as the AQP1 negative exact-source confirmation anchor, keep PMID 40359885 as positive-boundary context only, "
            "and leave core_non_binder_01 through core_non_binder_03 review-only until a direct transporter-specific quantitative negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Evidence Confirmation Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- top_packet_step: `{s['top_packet_step']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- primary_confirmation_scope: `{s['primary_confirmation_scope']}`",
        f"- primary_anchor_pmid: `{s['primary_anchor_pmid']}`",
        f"- boundary_positive_pmid: `{s['boundary_positive_pmid']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- primary_anchor_outcome_row_count: `{s['primary_anchor_outcome_row_count']}`",
        f"- primary_anchor_source_endpoint: `{s['primary_anchor_source_endpoint']}`",
        f"- primary_anchor_almost_unaffected_candidate_count: `{s['primary_anchor_almost_unaffected_candidate_count']}`",
        f"- primary_anchor_small_inhibitor_signal_candidate: `{s['primary_anchor_small_inhibitor_signal_candidate']}`",
        f"- primary_anchor_direct_negative_quantitative_row_found_count: `{s['primary_anchor_direct_negative_quantitative_row_found_count']}`",
        f"- primary_anchor_authoritative_negative_apply_allowed_count: `{s['primary_anchor_authoritative_negative_apply_allowed_count']}`",
        f"- confirmation_decision: `{s['confirmation_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Confirmation Rows",
        "",
        "| confirmation_rank | packet_step | current_ligand_id | primary_anchor_pmid | primary_anchor_outcome_row_count | positive_boundary_pmid | confirmation_decision |",
        "| ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['confirmation_rank']} | `{row['packet_step']}` | `{row['current_ligand_id']}` | "
            f"`{row['primary_anchor_pmid']}` | {row['primary_anchor_outcome_row_count']} | "
            f"`{row['positive_boundary_pmid']}` | `{row['confirmation_decision']}` |"
        )
    lines.extend(["", "## Reviewer Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['packet_step']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['packet_step']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative evidence confirmation packet.")
    parser.add_argument("--negative-slot-closure-json", default=DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--negative-acquisition-json", default=DEFAULT_NEGATIVE_ACQUISITION_JSON)
    parser.add_argument("--negative-exact-source-outcome-json", default=DEFAULT_NEGATIVE_EXACT_SOURCE_OUTCOME_JSON)
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
        _load_json(args.negative_exact_source_outcome_json),
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
