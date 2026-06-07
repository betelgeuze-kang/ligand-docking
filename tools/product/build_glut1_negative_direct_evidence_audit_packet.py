#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NEGATIVE_HANDOFF_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_EXTERNAL_EVIDENCE_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_OUT_JSON = "runs/glut1_negative_direct_evidence_audit_packet_current.json"
DEFAULT_OUT_CSV = "runs/glut1_negative_direct_evidence_audit_packet_current.csv"
DEFAULT_OUT_MD = "runs/glut1_negative_direct_evidence_audit_packet_current.md"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _csv_join(values: list[str]) -> str:
    return ",".join(value for value in values if value)


def _source_rows_by_role(source_confirmation_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive_rows: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    for row in source_confirmation_payload.get("rows", []) or []:
        status = _text(row.get("public_provenance_status"))
        signal = _text(row.get("public_provenance_signal"))
        if "negative" in status or "negative" in signal:
            negative_rows.append(dict(row))
        else:
            positive_rows.append(dict(row))
    return positive_rows, negative_rows


def build_payload(
    negative_handoff_payload: dict[str, Any],
    source_confirmation_payload: dict[str, Any],
    external_evidence_seed_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    handoff_summary = dict((negative_handoff_payload or {}).get("summary", {}) or {})
    source_summary = dict((source_confirmation_payload or {}).get("summary", {}) or {})
    seed_summary = dict((external_evidence_seed_payload or {}).get("summary", {}) or {})
    negative_rows = [
        dict(row)
        for row in (negative_handoff_payload or {}).get("rows", []) or []
        if _text(row.get("row_type")) == "negative_review"
    ]
    caution_rows = [
        dict(row)
        for row in (negative_handoff_payload or {}).get("rows", []) or []
        if _text(row.get("row_type")) == "caution_signal"
    ]
    positive_source_rows, negative_source_rows = _source_rows_by_role(source_confirmation_payload or {})
    named_negative_ligands = [
        _text(row.get("candidate_name"))
        for row in negative_rows
        if _text(row.get("candidate_name"))
        and not _text(row.get("candidate_name")).startswith("glut1_placeholder")
    ]
    placeholder_ligands = [_text(row.get("current_ligand_id")) for row in negative_rows if _text(row.get("current_ligand_id"))]
    positive_candidates = [_text(row.get("candidate_name")) for row in positive_source_rows]
    caution_candidates = [_text(row.get("candidate_name")) for row in caution_rows]
    positive_activity_record_count = sum(_int(row.get("chembl_activity_record_count")) for row in positive_source_rows)
    direct_negative_count = 0
    authoritative_apply_count = 0

    rows = [
        {
            "audit_rank": 1,
            "audit_route": "placeholder_negative_slot_check",
            "candidate_name": _csv_join(placeholder_ligands),
            "result_count": len(negative_rows),
            "source_artifact": _text(handoff_summary.get("packet_artifact")),
            "audit_interpretation": "negative_slots_are_placeholder_rows_without_named_replacement_ligands",
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 2,
            "audit_route": "positive_source_context_contrast",
            "candidate_name": _csv_join(positive_candidates),
            "result_count": len(positive_source_rows),
            "source_artifact": _text(source_summary.get("packet_artifact")),
            "audit_interpretation": "source_confirmation_rows_are_binder_or_functional_inhibitor_context_not_negative_replacements",
            "positive_exact_target_pair_candidate_count": _int(source_summary.get("exact_target_pair_activity_count")),
            "positive_exact_target_pair_activity_record_count": positive_activity_record_count,
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 3,
            "audit_route": "caution_signal_exclusion_check",
            "candidate_name": _csv_join(caution_candidates),
            "result_count": len(caution_rows),
            "source_artifact": _text(handoff_summary.get("packet_artifact")),
            "audit_interpretation": "caution_tool_or_polypharmacology_rows_are_not_clean_negative_evidence",
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 4,
            "audit_route": "claim_safe_kcal_gap_check",
            "candidate_name": _text(source_summary.get("primary_focus_ligand")),
            "result_count": _int(source_summary.get("claim_safe_kcal_ready_count")),
            "source_artifact": _text(source_summary.get("packet_artifact")),
            "audit_interpretation": "no_claim_safe_glut1_binding_kcal_or_negative_affinity_row_is_curated",
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
    ]

    summary = {
        "target_id": "GLUT1",
        "as_of_date": as_of_date or date.today().isoformat(),
        "packet_artifact": "runs/glut1_negative_direct_evidence_audit_packet_current.md",
        "row_count": len(rows),
        "negative_slot_count": _int(handoff_summary.get("negative_slot_count")) or len(negative_rows),
        "placeholder_negative_candidate_count": len(placeholder_ligands),
        "candidate_named_negative_ligand_count": len(named_negative_ligands),
        "source_context_artifact": _text(source_summary.get("packet_artifact")),
        "source_context_primary_focus_ligand": _text(source_summary.get("primary_focus_ligand")),
        "source_context_positive_or_binder_candidate_count": len(positive_source_rows),
        "source_context_negative_evidence_row_count": len(negative_source_rows),
        "positive_direct_quantitative_binding_count": _int(source_summary.get("direct_quantitative_binding_count")),
        "positive_exact_target_pair_candidate_count": _int(source_summary.get("exact_target_pair_activity_count")),
        "positive_exact_target_pair_activity_record_count": positive_activity_record_count,
        "claim_safe_kcal_ready_count": _int(source_summary.get("claim_safe_kcal_ready_count")),
        "caution_signal_count": len(caution_rows) or _int(seed_summary.get("caution_only_candidate_count")),
        "direct_negative_quantitative_row_found_count": direct_negative_count,
        "authoritative_negative_apply_allowed_count": authoritative_apply_count,
        "audit_decision": "keep_placeholder_negative_slots_review_only_no_authoritative_negative_promotion",
        "next_required_step": (
            "Keep GLUT1 core_non_binder_01 through core_non_binder_03 review-only: current rows are placeholders, "
            "the available source-confirmation rows are positive binder/function-inhibitor context, and no direct "
            "quantitative GLUT1 negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Negative Direct Evidence Audit Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- placeholder_negative_candidate_count: `{s['placeholder_negative_candidate_count']}`",
        f"- candidate_named_negative_ligand_count: `{s['candidate_named_negative_ligand_count']}`",
        f"- source_context_artifact: `{s['source_context_artifact']}`",
        f"- source_context_primary_focus_ligand: `{s['source_context_primary_focus_ligand']}`",
        f"- source_context_positive_or_binder_candidate_count: `{s['source_context_positive_or_binder_candidate_count']}`",
        f"- source_context_negative_evidence_row_count: `{s['source_context_negative_evidence_row_count']}`",
        f"- positive_direct_quantitative_binding_count: `{s['positive_direct_quantitative_binding_count']}`",
        f"- positive_exact_target_pair_candidate_count: `{s['positive_exact_target_pair_candidate_count']}`",
        f"- positive_exact_target_pair_activity_record_count: `{s['positive_exact_target_pair_activity_record_count']}`",
        f"- claim_safe_kcal_ready_count: `{s['claim_safe_kcal_ready_count']}`",
        f"- caution_signal_count: `{s['caution_signal_count']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- audit_decision: `{s['audit_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Audit Rows",
        "",
        "| audit_rank | audit_route | candidate_name | result_count | audit_interpretation |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['audit_rank']} | `{row['audit_route']}` | `{row['candidate_name']}` | "
            f"{row['result_count']} | `{row['audit_interpretation']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the GLUT1 negative direct-evidence audit packet.")
    parser.add_argument("--negative-handoff-json", default=DEFAULT_NEGATIVE_HANDOFF_JSON)
    parser.add_argument("--source-confirmation-json", default=DEFAULT_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--external-evidence-seed-json", default=DEFAULT_EXTERNAL_EVIDENCE_SEED_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_handoff_json),
        _load_json(args.source_confirmation_json),
        _load_json(args.external_evidence_seed_json),
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
