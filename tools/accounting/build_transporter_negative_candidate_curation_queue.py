#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_CANDIDATE_HARVEST_JSON = RUNS / "transporter_negative_candidate_harvest_current.json"
DEFAULT_NEGATIVE_QUEUE_JSON = RUNS / "transporter_negative_evidence_closure_queue_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_candidate_curation_queue_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_negative_candidate_curation_queue_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_negative_candidate_curation_queue_current.md"

TARGET_ID = "GLUT1"
EVIDENCE_CLASS = "chembl_quantitative_weak_or_no_binding_lower_bound"


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


def _candidate_rows(candidate_harvest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in candidate_harvest.get("rows", []) or []
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("evidence_class")) == EVIDENCE_CLASS
    ]
    return sorted(
        rows,
        key=lambda row: (
            _int(row.get("target_candidate_rank")),
            _int(row.get("global_candidate_rank")),
            _text(row.get("molecule_chembl_id")),
        ),
    )


def _negative_slots(negative_queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in negative_queue.get("rows", []) or []
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("packet_step")).startswith("core_non_binder")
    ]
    if rows:
        return sorted(rows, key=lambda row: (_int(row.get("queue_rank")), _text(row.get("queue_id"))))
    return [
        {
            "queue_rank": idx,
            "queue_id": f"{TARGET_ID}__core_non_binder_0{idx}",
            "packet_step": f"core_non_binder_0{idx}",
            "target_id": TARGET_ID,
            "review_bucket": "negative_candidate",
        }
        for idx in range(1, 4)
    ]


def _standard_text(row: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            _text(row.get("standard_type")),
            _text(row.get("standard_relation")),
            _text(row.get("standard_value")),
            _text(row.get("standard_units")),
        ]
        if part
    )


def build_payload(candidate_harvest: dict[str, Any], negative_queue: dict[str, Any]) -> dict[str, Any]:
    harvest_summary = dict(candidate_harvest.get("summary", {}) or {})
    negative_queue_summary = dict(negative_queue.get("summary", {}) or {})
    candidates = _candidate_rows(candidate_harvest)
    slots = _negative_slots(negative_queue)
    rows: list[dict[str, Any]] = []
    source_artifact = _text(harvest_summary.get("packet_artifact")) or "runs/transporter_negative_candidate_harvest_current.md"

    for curation_rank, (slot, candidate) in enumerate(zip(slots, candidates), start=1):
        rows.append(
            {
                "curation_rank": curation_rank,
                "slot_queue_rank": _int(slot.get("queue_rank")),
                "slot_queue_id": _text(slot.get("queue_id")),
                "slot_packet_step": _text(slot.get("packet_step")),
                "target_id": TARGET_ID,
                "target_chembl_id": _text(candidate.get("target_chembl_id")),
                "molecule_chembl_id": _text(candidate.get("molecule_chembl_id")),
                "molecule_pref_name": _text(candidate.get("molecule_pref_name")),
                "canonical_smiles": _text(candidate.get("canonical_smiles")),
                "document_chembl_id": _text(candidate.get("document_chembl_id")),
                "document_year": _text(candidate.get("document_year")),
                "assay_chembl_id": _text(candidate.get("assay_chembl_id")),
                "assay_description": _text(candidate.get("assay_description")),
                "standard_type": _text(candidate.get("standard_type")),
                "standard_relation": _text(candidate.get("standard_relation")),
                "standard_value": _text(candidate.get("standard_value")),
                "standard_units": _text(candidate.get("standard_units")),
                "standard_text": _standard_text(candidate),
                "evidence_class": _text(candidate.get("evidence_class")),
                "source_database": "ChEMBL",
                "candidate_source_artifact": source_artifact,
                "candidate_harvest_rank": _int(candidate.get("target_candidate_rank")),
                "curation_status": "queued_for_manual_review",
                "required_manual_fields": (
                    "molecule_identity_confirmed;source_primary_reference_checked;assay_target_context_checked;"
                    "negative_semantics_checked;split_assignment_chosen;reference_meta_packet_updated;reviewer_approval"
                ),
                "missing_before_apply": (
                    "manual_ligand_identity;source_provenance;assay_semantics_review;train_test_split_assignment;"
                    "reference_meta_packet;reviewer_approval"
                ),
                "candidate_apply_allowed": False,
                "authoritative_negative_apply_allowed": False,
                "claim_promotion_allowed": False,
                "aqp1_first_blocker_open": True,
                "promotion_blocker": "aqp1_first_blocker_and_manual_glut1_candidate_curation_required",
                "next_required_action": (
                    "Confirm molecule identity, primary ChEMBL document provenance, assay target/context, negative semantics, "
                    "and split/reference metadata before this row can replace a GLUT1 negative placeholder."
                ),
            }
        )

    aqp1_first_blocker_open = (
        _text(negative_queue_summary.get("top_target_id")) == "AQP1"
        or _int(harvest_summary.get("aqp1_quantitative_lower_bound_candidate_count")) == 0
    )
    summary = {
        "curation_queue_ready": bool(rows),
        "packet_artifact": "runs/transporter_negative_candidate_curation_queue_current.md",
        "source_harvest_artifact": source_artifact,
        "target_id": TARGET_ID,
        "source_database": "ChEMBL",
        "evidence_class": EVIDENCE_CLASS,
        "available_quantitative_lower_bound_candidate_count": len(candidates),
        "target_negative_slot_count": len(slots),
        "queue_row_count": len(rows),
        "slot_cover_ready_count": len(rows),
        "slot_cover_missing_count": max(0, len(slots) - len(rows)),
        "unused_candidate_count": max(0, len(candidates) - len(rows)),
        "aqp1_first_blocker_open": aqp1_first_blocker_open,
        "aqp1_quantitative_lower_bound_candidate_count": _int(
            harvest_summary.get("aqp1_quantitative_lower_bound_candidate_count")
        ),
        "candidate_apply_allowed": False,
        "authoritative_negative_apply_allowed_count": 0,
        "negative_evidence_closure_allowed": False,
        "claim_promotion_allowed": False,
        "queue_status": (
            "glut1_curation_queue_ready_aqp1_first_blocker_still_open"
            if rows and len(rows) == len(slots) and aqp1_first_blocker_open
            else "glut1_curation_queue_partial_aqp1_first_blocker_still_open"
            if rows and aqp1_first_blocker_open
            else "glut1_curation_queue_unavailable"
        ),
        "next_required_step": (
            "Use this as GLUT1 prework only: curate the queued ChEMBL lower-bound Kd rows into molecule/source/split/reference/meta "
            "packets, keep candidate_apply_allowed=false, and do not promote transporter negative evidence while AQP1 remains the first blocker."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Negative Candidate Curation Queue",
        "",
        f"- curation_queue_ready: `{s['curation_queue_ready']}`",
        f"- target_id: `{s['target_id']}`",
        f"- source_database: `{s['source_database']}`",
        f"- evidence_class: `{s['evidence_class']}`",
        f"- source_harvest_artifact: `{s['source_harvest_artifact']}`",
        f"- available_quantitative_lower_bound_candidate_count: `{s['available_quantitative_lower_bound_candidate_count']}`",
        f"- target_negative_slot_count: `{s['target_negative_slot_count']}`",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- slot_cover_ready_count: `{s['slot_cover_ready_count']}`",
        f"- slot_cover_missing_count: `{s['slot_cover_missing_count']}`",
        f"- unused_candidate_count: `{s['unused_candidate_count']}`",
        f"- aqp1_first_blocker_open: `{s['aqp1_first_blocker_open']}`",
        f"- candidate_apply_allowed: `{s['candidate_apply_allowed']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- queue_status: `{s['queue_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Curation Rows",
        "",
        "| rank | slot | molecule | standard | document | assay | apply_allowed | missing_before_apply |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['curation_rank']} | `{row['slot_queue_id']}` | `{row['molecule_chembl_id']}` | "
            f"`{row['standard_text'] or '-'}` | `{row['document_chembl_id'] or '-'}` | "
            f"`{row['assay_chembl_id'] or '-'}` | `{row['candidate_apply_allowed']}` | "
            f"`{row['missing_before_apply']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GLUT1 pre-apply curation queue from harvested negative candidates.")
    parser.add_argument("--candidate-harvest-json", default=str(DEFAULT_CANDIDATE_HARVEST_JSON))
    parser.add_argument("--negative-queue-json", default=str(DEFAULT_NEGATIVE_QUEUE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.candidate_harvest_json), _load_json(args.negative_queue_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
