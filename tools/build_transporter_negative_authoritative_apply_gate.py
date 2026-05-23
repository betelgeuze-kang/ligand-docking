#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_NEGATIVE_QUEUE_JSON = RUNS / "transporter_negative_evidence_closure_queue_current.json"
DEFAULT_AQP1_PRIMARY_EVIDENCE_JSON = RUNS / "aqp1_negative_primary_functional_evidence_current.json"
DEFAULT_AQP1_INTAKE_GATE_JSON = RUNS / "aqp1_negative_evidence_intake_gate_current.json"
DEFAULT_GLUT1_CURATION_QUEUE_JSON = RUNS / "transporter_negative_candidate_curation_queue_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_authoritative_apply_gate_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_negative_authoritative_apply_gate_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_negative_authoritative_apply_gate_current.md"

TARGET_SLOT_COUNT = {"AQP1": 3, "GLUT1": 3}


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "pass", "passed"}
    return bool(value)


def _negative_slots(negative_queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in negative_queue.get("rows", []) or []
        if _text(row.get("packet_step")).startswith("core_non_binder")
        and _text(row.get("target_id")) in TARGET_SLOT_COUNT
    ]
    if rows:
        return sorted(rows, key=lambda row: (_int(row.get("queue_rank")), _text(row.get("queue_id"))))
    return [
        {
            "queue_rank": idx,
            "queue_id": f"AQP1__core_non_binder_0{idx}",
            "target_id": "AQP1",
            "packet_step": f"core_non_binder_0{idx}",
        }
        for idx in range(1, 4)
    ] + [
        {
            "queue_rank": idx + 3,
            "queue_id": f"GLUT1__core_non_binder_0{idx}",
            "target_id": "GLUT1",
            "packet_step": f"core_non_binder_0{idx}",
        }
        for idx in range(1, 4)
    ]


def _rows_by_slot(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("slot_queue_id")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("slot_queue_id"))
    }


def _aqp1_apply_row(slot: dict[str, Any], evidence_row: dict[str, Any], intake_complete: bool) -> dict[str, Any]:
    source_id = _text(evidence_row.get("source_id"))
    split_ready = bool(_text(evidence_row.get("split_id")) and _text(evidence_row.get("reference_meta_id")))
    primary_source = _text(evidence_row.get("primary_source")).lower()
    semantic_ok = _text(evidence_row.get("negative_semantics")).lower() in {
        "no_transport_effect",
        "no_effect",
        "no_flux_change",
    }
    apply_allowed = (
        intake_complete
        and split_ready
        and "primary_journal_article" in primary_source
        and "23123479" in source_id
        and semantic_ok
    )
    return {
        "slot_queue_rank": _int(slot.get("queue_rank")),
        "slot_queue_id": _text(slot.get("queue_id")),
        "target_id": "AQP1",
        "packet_step": _text(slot.get("packet_step")),
        "candidate_name": _text(evidence_row.get("candidate_name")),
        "molecule_id": _text(evidence_row.get("molecule_id")),
        "source_database": "J-STAGE/PubMed",
        "source_id": source_id,
        "assay_context": _text(evidence_row.get("assay_context")),
        "endpoint": _text(evidence_row.get("endpoint")),
        "standard_type": _text(evidence_row.get("standard_type")),
        "standard_relation": _text(evidence_row.get("standard_relation")),
        "standard_value": _text(evidence_row.get("standard_value")),
        "standard_units": _text(evidence_row.get("standard_units")),
        "negative_semantics": _text(evidence_row.get("negative_semantics")),
        "split_id": _text(evidence_row.get("split_id")),
        "reference_meta_id": _text(evidence_row.get("reference_meta_id")),
        "evidence_basis": "primary_functional_no_effect",
        "curation_status": "source_identity_split_reference_meta_curated" if apply_allowed else "awaiting_aqp1_intake_gate",
        "authoritative_negative_apply_allowed": apply_allowed,
        "claim_promotion_allowed": False,
        "promotion_blocker": "" if apply_allowed else "aqp1_primary_functional_intake_not_complete",
    }


def _glut1_apply_row(slot: dict[str, Any], curation_row: dict[str, Any], aqp1_closed: bool) -> dict[str, Any]:
    exact_target = _text(curation_row.get("target_chembl_id")) == "CHEMBL2535"
    lower_bound = _text(curation_row.get("standard_type")) == "Kd" and _text(
        curation_row.get("standard_relation")
    ) == ">" and _float(curation_row.get("standard_value")) >= 100000
    has_source = bool(_text(curation_row.get("document_chembl_id")) and _text(curation_row.get("assay_chembl_id")))
    has_identity = bool(_text(curation_row.get("molecule_chembl_id")) and _text(curation_row.get("canonical_smiles")))
    apply_allowed = aqp1_closed and exact_target and lower_bound and has_source and has_identity
    return {
        "slot_queue_rank": _int(slot.get("queue_rank")),
        "slot_queue_id": _text(slot.get("queue_id")),
        "target_id": "GLUT1",
        "packet_step": _text(slot.get("packet_step")),
        "candidate_name": _text(curation_row.get("molecule_pref_name")) or _text(curation_row.get("molecule_chembl_id")),
        "molecule_id": _text(curation_row.get("molecule_chembl_id")),
        "source_database": "ChEMBL",
        "source_id": (
            f"document:{_text(curation_row.get('document_chembl_id'))}; "
            f"assay:{_text(curation_row.get('assay_chembl_id'))}"
        ),
        "assay_context": _text(curation_row.get("assay_description")),
        "endpoint": "human_erythrocyte_glucose_transporter_binding_kd_lower_bound",
        "standard_type": _text(curation_row.get("standard_type")),
        "standard_relation": _text(curation_row.get("standard_relation")),
        "standard_value": _text(curation_row.get("standard_value")),
        "standard_units": _text(curation_row.get("standard_units")),
        "negative_semantics": "weak_binding_lower_bound",
        "split_id": f"glut1_negative_chEMBL_lower_bound_split_v1_row_{_int(curation_row.get('curation_rank'))}",
        "reference_meta_id": f"glut1_negative_reference_meta_chEMBL1125913_row_{_int(curation_row.get('curation_rank'))}",
        "evidence_basis": "chembl_exact_target_quantitative_lower_bound",
        "curation_status": "source_identity_split_reference_meta_curated" if apply_allowed else "awaiting_aqp1_first_blocker_closure",
        "authoritative_negative_apply_allowed": apply_allowed,
        "claim_promotion_allowed": False,
        "promotion_blocker": "" if apply_allowed else "aqp1_first_blocker_or_glut1_source_curation_incomplete",
    }


def build_payload(
    negative_queue: dict[str, Any],
    aqp1_primary_evidence: dict[str, Any],
    aqp1_intake_gate: dict[str, Any],
    glut1_curation_queue: dict[str, Any],
) -> dict[str, Any]:
    aqp1_evidence_by_slot = _rows_by_slot(aqp1_primary_evidence)
    glut1_curation_by_slot = _rows_by_slot(glut1_curation_queue)
    aqp1_intake_summary = dict(aqp1_intake_gate.get("summary", {}) or {})
    aqp1_intake_complete = _bool(aqp1_intake_summary.get("intake_gate_complete"))
    rows: list[dict[str, Any]] = []

    for slot in _negative_slots(negative_queue):
        queue_id = _text(slot.get("queue_id"))
        target_id = _text(slot.get("target_id"))
        if target_id == "AQP1":
            rows.append(_aqp1_apply_row(slot, aqp1_evidence_by_slot.get(queue_id, {}), aqp1_intake_complete))

    aqp1_apply_count = sum(
        1 for row in rows if row["target_id"] == "AQP1" and row["authoritative_negative_apply_allowed"]
    )
    aqp1_closed = aqp1_apply_count >= TARGET_SLOT_COUNT["AQP1"]

    for slot in _negative_slots(negative_queue):
        queue_id = _text(slot.get("queue_id"))
        if _text(slot.get("target_id")) == "GLUT1":
            rows.append(_glut1_apply_row(slot, glut1_curation_by_slot.get(queue_id, {}), aqp1_closed))

    apply_allowed_count = sum(1 for row in rows if row["authoritative_negative_apply_allowed"])
    required_count = sum(TARGET_SLOT_COUNT.values())
    target_counts = {
        target_id: sum(1 for row in rows if row["target_id"] == target_id and row["authoritative_negative_apply_allowed"])
        for target_id in TARGET_SLOT_COUNT
    }
    summary = {
        "negative_apply_gate_ready": True,
        "packet_artifact": str(DEFAULT_OUT_MD),
        "required_negative_slot_count": required_count,
        "apply_allowed_count": apply_allowed_count,
        "apply_blocked_count": max(0, required_count - apply_allowed_count),
        "all_negative_slots_apply_allowed": apply_allowed_count >= required_count,
        "aqp1_apply_allowed_count": target_counts["AQP1"],
        "aqp1_required_negative_slot_count": TARGET_SLOT_COUNT["AQP1"],
        "aqp1_negative_evidence_closed": target_counts["AQP1"] >= TARGET_SLOT_COUNT["AQP1"],
        "glut1_apply_allowed_count": target_counts["GLUT1"],
        "glut1_required_negative_slot_count": TARGET_SLOT_COUNT["GLUT1"],
        "glut1_negative_evidence_closed": target_counts["GLUT1"] >= TARGET_SLOT_COUNT["GLUT1"],
        "negative_evidence_closure_allowed": apply_allowed_count >= required_count,
        "claim_promotion_allowed": False,
        "closure_status": (
            "transporter_negative_evidence_closed"
            if apply_allowed_count >= required_count
            else "transporter_negative_evidence_partially_closed"
        ),
        "next_required_step": (
            "Transporter negative placeholders can be burned down; keep broader delivery wording separate from this evidence closure."
            if apply_allowed_count >= required_count
            else "Finish AQP1 intake and GLUT1 source curation before burning down transporter negative placeholders."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Negative Authoritative Apply Gate",
        "",
        f"- negative_apply_gate_ready: `{s['negative_apply_gate_ready']}`",
        f"- required_negative_slot_count: `{s['required_negative_slot_count']}`",
        f"- apply_allowed_count: `{s['apply_allowed_count']}`",
        f"- apply_blocked_count: `{s['apply_blocked_count']}`",
        f"- all_negative_slots_apply_allowed: `{s['all_negative_slots_apply_allowed']}`",
        f"- aqp1_apply_allowed_count: `{s['aqp1_apply_allowed_count']}/{s['aqp1_required_negative_slot_count']}`",
        f"- glut1_apply_allowed_count: `{s['glut1_apply_allowed_count']}/{s['glut1_required_negative_slot_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- closure_status: `{s['closure_status']}`",
        "",
        "## Apply Rows",
        "",
        "| slot | target | candidate | standard | evidence_basis | apply_allowed | blocker |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        standard = " ".join(
            part
            for part in [
                row["standard_type"],
                row["standard_relation"],
                row["standard_value"],
                row["standard_units"],
            ]
            if part
        )
        lines.append(
            f"| `{row['slot_queue_id']}` | `{row['target_id']}` | `{row['candidate_name'] or '-'}` | "
            f"`{standard or '-'}` | `{row['evidence_basis']}` | "
            f"`{row['authoritative_negative_apply_allowed']}` | `{row['promotion_blocker'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter negative authoritative apply gate.")
    parser.add_argument("--negative-queue-json", default=str(DEFAULT_NEGATIVE_QUEUE_JSON))
    parser.add_argument("--aqp1-primary-evidence-json", default=str(DEFAULT_AQP1_PRIMARY_EVIDENCE_JSON))
    parser.add_argument("--aqp1-intake-gate-json", default=str(DEFAULT_AQP1_INTAKE_GATE_JSON))
    parser.add_argument("--glut1-curation-queue-json", default=str(DEFAULT_GLUT1_CURATION_QUEUE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_queue_json),
        _load_json(args.aqp1_primary_evidence_json),
        _load_json(args.aqp1_intake_gate_json),
        _load_json(args.glut1_curation_queue_json),
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
