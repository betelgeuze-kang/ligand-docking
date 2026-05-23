#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_REQUEST_JSON = RUNS / "aqp1_negative_evidence_request_packet_current.json"
DEFAULT_INTAKE_CSV = RUNS / "aqp1_negative_evidence_intake_current.csv"
DEFAULT_TEMPLATE_CSV = RUNS / "aqp1_negative_evidence_intake_template_current.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_negative_evidence_intake_gate_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_negative_evidence_intake_gate_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_negative_evidence_intake_gate_current.md"

TARGET_ID = "AQP1"
TARGET_ACCESSION = "P29972"
TARGET_CHEMBL_ID = "CHEMBL4523210"
KNOWN_REVIEW_ONLY_PMIDS: set[str] = set()
EXCLUDED_SHORTCUT_FRAGMENTS = (
    "tetraethylammonium",
    "dimethyl sulfoxide",
    "dmso",
)
EXCLUDED_SHORTCUT_CONTEXT_FRAGMENTS = (
    "boundary_context",
    "boundary-only",
    "boundary only",
    "caution-reference",
    "caution reference",
    "solvent_context",
    "tool_reference",
)
ALLOWED_STANDARD_RELATIONS = {">", ">=", "=", "<=", "<"}
ACCEPTED_NEGATIVE_SEMANTICS = {
    "below_activity_threshold",
    "inactive",
    "lower_bound_inactive",
    "no_effect",
    "no_flux_change",
    "no_transport_effect",
    "non_binder",
    "not_inhibitor",
    "weak_activity",
    "weak_binding",
    "weak_no_effect",
    "weak_or_no_effect",
}
ACCEPTED_CURATOR_DECISIONS = {
    "ready_for_authoritative_negative_review",
    "review_ready",
}
REQUIRED_EVIDENCE_FIELDS = (
    "candidate_name",
    "molecule_id",
    "target_id",
    "target_accession",
    "target_chembl_id",
    "target_organism",
    "assay_context",
    "endpoint",
    "standard_type",
    "standard_relation",
    "standard_value",
    "standard_units",
    "concentration_or_curve_range",
    "replicate_or_error_model",
    "primary_source",
    "source_id",
    "split_id",
    "reference_meta_id",
    "negative_semantics",
    "curator_decision",
)


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
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def _semantic_key(value: Any) -> str:
    return _norm(value).replace("-", "_").replace("/", "_").replace(" ", "_")


def _has_evidence_data(row: dict[str, Any]) -> bool:
    evidence_fields = [field for field in REQUIRED_EVIDENCE_FIELDS if field not in {"target_id", "target_accession", "target_chembl_id", "target_organism"}]
    return any(_text(row.get(field)) for field in evidence_fields)


def _is_number(value: Any) -> bool:
    try:
        parsed = float(_text(value))
    except ValueError:
        return False
    return math.isfinite(parsed)


def _contains_excluded_shortcut(row: dict[str, Any]) -> bool:
    combined = _norm(
        " ".join(
            _text(row.get(field))
            for field in (
                "candidate_name",
                "molecule_id",
                "assay_context",
                "primary_source",
                "source_id",
            )
        )
    )
    if any(fragment in combined for fragment in EXCLUDED_SHORTCUT_FRAGMENTS):
        return True
    return any(fragment in combined for fragment in EXCLUDED_SHORTCUT_CONTEXT_FRAGMENTS)


def _uses_review_only_context(row: dict[str, Any]) -> bool:
    combined = _norm(f"{row.get('primary_source', '')} {row.get('source_id', '')}")
    if "review-only" in combined or "review only" in combined:
        return True
    return any(pmid in combined for pmid in KNOWN_REVIEW_ONLY_PMIDS)


def _slot_rows(request_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in request_payload.get("rows", []) or []]
    return rows or [
        {
            "request_rank": idx,
            "slot_queue_id": f"{TARGET_ID}__core_non_binder_0{idx}",
            "packet_step": f"core_non_binder_0{idx}",
            "target_id": TARGET_ID,
            "target_uniprot_accession": TARGET_ACCESSION,
            "target_chembl_id": TARGET_CHEMBL_ID,
            "candidate_scope": f"independent_exact_aqp1_nonbinder_candidate_0{idx}",
        }
        for idx in range(1, 4)
    ]


def build_template_rows(request_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_row in _slot_rows(request_payload):
        rows.append(
            {
                "slot_queue_id": _text(request_row.get("slot_queue_id")),
                "request_rank": _text(request_row.get("request_rank")),
                "packet_step": _text(request_row.get("packet_step")),
                "target_id": _text(request_row.get("target_id")) or TARGET_ID,
                "target_accession": _text(request_row.get("target_uniprot_accession")) or TARGET_ACCESSION,
                "target_chembl_id": _text(request_row.get("target_chembl_id")) or TARGET_CHEMBL_ID,
                "target_organism": "Homo sapiens",
                "candidate_scope": _text(request_row.get("candidate_scope")),
                "candidate_name": "",
                "molecule_id": "",
                "assay_context": "",
                "endpoint": "",
                "standard_type": "",
                "standard_relation": "",
                "standard_value": "",
                "standard_units": "",
                "concentration_or_curve_range": "",
                "replicate_or_error_model": "",
                "primary_source": "",
                "source_id": "",
                "split_id": "",
                "reference_meta_id": "",
                "negative_semantics": "",
                "curator_decision": "",
                "curator_notes": "",
            }
        )
    return rows


def _validate_row(row: dict[str, Any], request_slots: dict[str, dict[str, Any]], duplicate_slots: set[str]) -> dict[str, Any]:
    slot_id = _text(row.get("slot_queue_id"))
    issue_codes: list[str] = []
    missing_fields = [field for field in REQUIRED_EVIDENCE_FIELDS if not _text(row.get(field))]
    issue_codes.extend(f"missing_{field}" for field in missing_fields)

    if not slot_id:
        issue_codes.append("missing_slot_queue_id")
    elif slot_id not in request_slots:
        issue_codes.append("unknown_slot_queue_id")
    elif slot_id in duplicate_slots:
        issue_codes.append("duplicate_slot_queue_id")

    if _norm(row.get("target_id")) != TARGET_ID.lower():
        issue_codes.append("target_id_mismatch")
    if TARGET_ACCESSION.lower() not in _norm(row.get("target_accession")):
        issue_codes.append("target_accession_mismatch")
    if _norm(row.get("target_chembl_id")) != TARGET_CHEMBL_ID.lower():
        issue_codes.append("target_chembl_id_mismatch")
    organism = _norm(row.get("target_organism"))
    if organism and not ("human" in organism or "homo sapiens" in organism):
        issue_codes.append("target_organism_not_human")
    if _text(row.get("standard_relation")) and _text(row.get("standard_relation")) not in ALLOWED_STANDARD_RELATIONS:
        issue_codes.append("unsupported_standard_relation")
    if _text(row.get("standard_value")) and not _is_number(row.get("standard_value")):
        issue_codes.append("standard_value_not_numeric")
    if _text(row.get("negative_semantics")) and _semantic_key(row.get("negative_semantics")) not in ACCEPTED_NEGATIVE_SEMANTICS:
        issue_codes.append("unsupported_negative_semantics")
    if _text(row.get("curator_decision")) and _semantic_key(row.get("curator_decision")) not in ACCEPTED_CURATOR_DECISIONS:
        issue_codes.append("unsupported_curator_decision")
    if _contains_excluded_shortcut(row):
        issue_codes.append("excluded_shortcut_context")
    if _uses_review_only_context(row):
        issue_codes.append("review_only_source_context")

    row_valid = len(issue_codes) == 0
    return {
        "row_index": 0,
        "slot_queue_id": slot_id,
        "request_rank": _text(request_slots.get(slot_id, {}).get("request_rank")),
        "packet_step": _text(row.get("packet_step")) or _text(request_slots.get(slot_id, {}).get("packet_step")),
        "candidate_scope": _text(row.get("candidate_scope")) or _text(request_slots.get(slot_id, {}).get("candidate_scope")),
        "candidate_name": _text(row.get("candidate_name")),
        "molecule_id": _text(row.get("molecule_id")),
        "target_id": _text(row.get("target_id")),
        "target_accession": _text(row.get("target_accession")),
        "target_chembl_id": _text(row.get("target_chembl_id")),
        "target_organism": _text(row.get("target_organism")),
        "assay_context": _text(row.get("assay_context")),
        "endpoint": _text(row.get("endpoint")),
        "standard_type": _text(row.get("standard_type")),
        "standard_relation": _text(row.get("standard_relation")),
        "standard_value": _text(row.get("standard_value")),
        "standard_units": _text(row.get("standard_units")),
        "primary_source": _text(row.get("primary_source")),
        "source_id": _text(row.get("source_id")),
        "intake_row_has_data": _has_evidence_data(row),
        "required_missing_fields": "; ".join(missing_fields),
        "issue_codes": "; ".join(dict.fromkeys(issue_codes)),
        "row_valid_for_authoritative_negative_review": row_valid,
        "authoritative_negative_apply_allowed": False,
        "claim_promotion_allowed": False,
    }


def build_payload(
    request_payload: dict[str, Any],
    intake_rows: list[dict[str, Any]],
    *,
    intake_csv: str = str(DEFAULT_INTAKE_CSV),
    template_csv: str = str(DEFAULT_TEMPLATE_CSV),
) -> dict[str, Any]:
    request_summary = dict(request_payload.get("summary", {}) or {})
    slot_rows = _slot_rows(request_payload)
    request_slots = {_text(row.get("slot_queue_id")): dict(row) for row in slot_rows if _text(row.get("slot_queue_id"))}
    slot_counts = Counter(_text(row.get("slot_queue_id")) for row in intake_rows if _text(row.get("slot_queue_id")))
    duplicate_slots = {slot for slot, count in slot_counts.items() if count > 1}

    rows = []
    for idx, row in enumerate(intake_rows, start=1):
        validated = _validate_row(row, request_slots, duplicate_slots)
        validated["row_index"] = idx
        rows.append(validated)

    valid_slot_ids = {
        row["slot_queue_id"]
        for row in rows
        if row["row_valid_for_authoritative_negative_review"] and row["slot_queue_id"] in request_slots
    }
    required_row_count = int(request_summary.get("required_assignable_negative_row_count", 0) or len(request_slots) or 3)
    valid_row_count = len(valid_slot_ids)
    missing_count = max(0, required_row_count - valid_row_count)
    error_count = sum(1 for row in rows if _text(row.get("issue_codes")))
    intake_complete = valid_row_count >= required_row_count
    summary = {
        "intake_gate_ready": True,
        "packet_artifact": "runs/aqp1_negative_evidence_intake_gate_current.md",
        "request_artifact": _text(request_summary.get("packet_artifact")) or "runs/aqp1_negative_evidence_request_packet_current.md",
        "intake_csv_artifact": intake_csv,
        "template_csv_artifact": template_csv,
        "target_id": _text(request_summary.get("target_id")) or TARGET_ID,
        "target_uniprot_accession": _text(request_summary.get("target_uniprot_accession")) or TARGET_ACCESSION,
        "target_chembl_id": _text(request_summary.get("target_chembl_id")) or TARGET_CHEMBL_ID,
        "request_row_count": len(request_slots),
        "intake_row_count": len(rows),
        "intake_row_with_data_count": sum(1 for row in rows if row["intake_row_has_data"]),
        "valid_intake_row_count": valid_row_count,
        "required_assignable_negative_row_count": required_row_count,
        "missing_valid_intake_row_count": missing_count,
        "validation_error_row_count": error_count,
        "duplicate_slot_queue_id_count": len(duplicate_slots),
        "unknown_slot_queue_id_count": sum(1 for row in rows if "unknown_slot_queue_id" in _text(row.get("issue_codes"))),
        "review_ready_row_count": valid_row_count,
        "intake_gate_complete": intake_complete,
        "split_reference_meta_update_required": intake_complete,
        "authoritative_negative_apply_allowed_count": 0,
        "negative_evidence_closure_allowed": False,
        "claim_promotion_allowed": False,
        "public_reinterpretation_exhausted": bool(request_summary.get("public_reinterpretation_exhausted", True)),
        "internal_wetlab_or_primary_source_required": bool(
            request_summary.get("internal_wetlab_or_primary_source_required", True)
        ),
        "intake_status": (
            "ready_for_split_reference_meta_review"
            if intake_complete
            else "awaiting_exact_aqp1_quantitative_negative_evidence_rows"
        ),
        "next_required_step": (
            "Fill the intake CSV with exact human AQP1 quantitative weak/no-effect rows, then rerun this gate."
            if not intake_complete
            else "Review the validated rows and update split/reference/meta packets before any authoritative negative apply."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Evidence Intake Gate",
        "",
        f"- intake_gate_ready: `{s['intake_gate_ready']}`",
        f"- request_artifact: `{s['request_artifact']}`",
        f"- intake_csv_artifact: `{s['intake_csv_artifact']}`",
        f"- template_csv_artifact: `{s['template_csv_artifact']}`",
        f"- target_id: `{s['target_id']}`",
        f"- target_uniprot_accession: `{s['target_uniprot_accession']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- valid_intake_rows: `{s['valid_intake_row_count']}/{s['required_assignable_negative_row_count']}`",
        f"- intake_row_with_data_count: `{s['intake_row_with_data_count']}`",
        f"- missing_valid_intake_row_count: `{s['missing_valid_intake_row_count']}`",
        f"- validation_error_row_count: `{s['validation_error_row_count']}`",
        f"- duplicate_slot_queue_id_count: `{s['duplicate_slot_queue_id_count']}`",
        f"- unknown_slot_queue_id_count: `{s['unknown_slot_queue_id_count']}`",
        f"- intake_gate_complete: `{s['intake_gate_complete']}`",
        f"- split_reference_meta_update_required: `{s['split_reference_meta_update_required']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- intake_status: `{s['intake_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Row Gate",
        "",
        "| row | slot | candidate | source | valid_for_review | issues |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_index']} | `{row['slot_queue_id']}` | `{row['candidate_name'] or '-'}` | "
            f"`{row['source_id'] or '-'}` | `{row['row_valid_for_authoritative_negative_review']}` | "
            f"`{row['issue_codes'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AQP1 exact negative-evidence intake rows before claim promotion.")
    parser.add_argument("--request-json", default=str(DEFAULT_REQUEST_JSON))
    parser.add_argument("--intake-csv", default=str(DEFAULT_INTAKE_CSV))
    parser.add_argument("--template-csv", default=str(DEFAULT_TEMPLATE_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request_payload = _load_json(args.request_json)
    template_rows = build_template_rows(request_payload)
    template_csv = _resolve(args.template_csv)
    write_csv_rows(template_csv, template_rows)

    intake_path = _resolve(args.intake_csv)
    intake_rows = _read_csv(intake_path) if intake_path.exists() else template_rows
    payload = build_payload(
        request_payload,
        intake_rows,
        intake_csv=str(Path(args.intake_csv)),
        template_csv=str(Path(args.template_csv)),
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
