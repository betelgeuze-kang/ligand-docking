#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_ACQUISITION_JSON = RUNS / "transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_PRIORITY_JSON = RUNS / "product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_CROSSCHECK_DIR = RUNS / "life_science_skill_crosscheck"
DEFAULT_OUT_JSON = RUNS / "transporter_local_crosscheck_triage_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_local_crosscheck_triage_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_local_crosscheck_triage_packet_current.md"

QUANTITATIVE_TYPES = {"AC50", "EC50", "IC50", "KD", "KI"}
DIRECT_TYPES = {"KD", "KI"}
TARGET_HINTS = {
    "AQP1": ("aqp1", "p29972", "aquaporin-1", "aquaporin_1"),
    "GLUT1_4PYP": ("glut1", "p11166", "slc2a1", "4pyp", "glucose transporter"),
}

CLAIM_BOUNDARY = (
    "Transporter local crosscheck triage packet only; inspects local public-data crosscheck files for quantitative "
    "candidate pools and slot-level blockers. It does not assign replacement ligands, compute authoritative labels, "
    "write config CSVs, run docking, authoritatively apply rows, reopen donor policy, widen product scope, upload, "
    "submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return not lowered or "placeholder" in lowered


def _crosscheck_files(crosscheck_dir: str | Path, target_id: str) -> list[Path]:
    path = _resolve(crosscheck_dir)
    if not path.exists() or not path.is_dir():
        return []
    hints = TARGET_HINTS.get(target_id, ())
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and any(hint in item.name.lower() for hint in hints)
    )


def _load_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _chembl_records(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for activity in payload.get("activities", []) or []:
        if not isinstance(activity, dict):
            continue
        standard_type = _text(activity.get("standard_type")).upper()
        standard_value = _float(activity.get("standard_value"))
        activity_comment = _text(activity.get("activity_comment"))
        is_quantitative = standard_type in QUANTITATIVE_TYPES and standard_value is not None
        is_not_active = activity_comment.lower() == "not active"
        if not (is_quantitative or is_not_active):
            continue
        assay = _text(activity.get("assay_description"))
        records.append(
            {
                "source_kind": "chembl_activity",
                "source_file": _source_path(path),
                "target_name": _text(activity.get("target_pref_name")),
                "target_organism": _text(activity.get("target_organism")),
                "molecule_id": _text(activity.get("molecule_chembl_id")),
                "molecule_name": _text(activity.get("molecule_pref_name")),
                "smiles": _text(activity.get("canonical_smiles")),
                "activity_type": standard_type or _text(activity.get("type")).upper(),
                "relation": _text(activity.get("standard_relation")) or _text(activity.get("relation")),
                "value": standard_value,
                "units": _text(activity.get("standard_units")),
                "document_id": _text(activity.get("document_chembl_id")),
                "document_year": _text(activity.get("document_year")),
                "activity_comment": activity_comment,
                "assay_description": assay,
                "direct_quantitative": is_quantitative and standard_type in DIRECT_TYPES,
                "functional_quantitative": is_quantitative and standard_type not in DIRECT_TYPES,
                "not_active_nonquantitative": is_not_active and not is_quantitative,
                "has_source_provenance": bool(_text(activity.get("document_chembl_id")) or _text(activity.get("document_journal"))),
            }
        )
    return records


def _bindingdb_records(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    affinities = ((payload.get("getLindsByUniprotsResponse") or {}).get("affinities") or [])
    records: list[dict[str, Any]] = []
    for affinity in affinities:
        if not isinstance(affinity, dict):
            continue
        affinity_type = _text(affinity.get("affinity_type")).upper()
        value = _float(affinity.get("affinity"))
        if affinity_type not in QUANTITATIVE_TYPES or value is None:
            continue
        records.append(
            {
                "source_kind": "bindingdb_affinity",
                "source_file": _source_path(path),
                "target_name": _text(affinity.get("query")),
                "target_organism": "",
                "molecule_id": _text(affinity.get("monomerid")),
                "molecule_name": "",
                "smiles": _text(affinity.get("smile")),
                "activity_type": affinity_type,
                "relation": "=",
                "value": value,
                "units": "nM",
                "document_id": _text(affinity.get("pmid")) or _text(affinity.get("doi")),
                "document_year": "",
                "activity_comment": "",
                "assay_description": "",
                "direct_quantitative": affinity_type in DIRECT_TYPES,
                "functional_quantitative": affinity_type not in DIRECT_TYPES,
                "not_active_nonquantitative": False,
                "has_source_provenance": bool(_text(affinity.get("pmid")) or _text(affinity.get("doi"))),
            }
        )
    return records


def _records_for_target(crosscheck_dir: str | Path, target_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in _crosscheck_files(crosscheck_dir, target_id):
        payload = _load_file(path)
        records.extend(_chembl_records(path, payload))
        records.extend(_bindingdb_records(path, payload))
    return records


def _record_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "quantitative_record_count": sum(1 for record in records if record["direct_quantitative"] or record["functional_quantitative"]),
        "direct_quantitative_record_count": sum(1 for record in records if record["direct_quantitative"]),
        "functional_quantitative_record_count": sum(1 for record in records if record["functional_quantitative"]),
        "not_active_nonquantitative_record_count": sum(1 for record in records if record["not_active_nonquantitative"]),
        "source_provenance_record_count": sum(1 for record in records if record["has_source_provenance"]),
    }


def _example(records: list[dict[str, Any]], predicate: str) -> dict[str, Any]:
    for record in records:
        if record.get(predicate):
            return record
    return {}


def _best_evidence(records: list[dict[str, Any]], triage_bucket: str) -> dict[str, Any]:
    if triage_bucket in {"named_candidate_manual_match_required", "candidate_assignment_required_from_local_pool"}:
        direct = _example(records, "direct_quantitative")
        if direct:
            return direct
    functional = _example(records, "functional_quantitative")
    if functional:
        return functional
    inactive = _example(records, "not_active_nonquantitative")
    if inactive:
        return inactive
    direct = _example(records, "direct_quantitative")
    return direct or {}


def _claim_safe_detail(row: dict[str, Any], counts: dict[str, int], triage_bucket: str) -> tuple[bool, str, str]:
    request_mode = _text(row.get("request_mode"))
    required_missing = _text(row.get("required_missing_fields"))
    if triage_bucket == "keep_review_only_direct_binding_gap":
        return (
            False,
            "review_only_guardrail_requires_explicit_direct_binding_source",
            "keep_blocked_until_exact_direct_binding_source_or_guardrail_decision",
        )
    if "direct_binding" in request_mode and counts["direct_quantitative_record_count"] == 0:
        return (
            False,
            "local_crosscheck_has_no_direct_binding_affinity_record",
            "curate_exact_direct_binding_source_or_keep_blocked",
        )
    if triage_bucket == "functional_quantitative_only_direct_gap_open":
        return (
            False,
            "functional_assay_quantitative_but_not_direct_binding_claim_safe",
            "keep_functional_surrogate_review_only_until_direct_binding_source",
        )
    if "negative" in request_mode and "reference_binding_kcal_mol" in required_missing:
        return (
            False,
            "negative_or_inactive_row_missing_exact_quantitative_value",
            "fill_exact_negative_quantitative_value_or_keep_blocked",
        )
    if triage_bucket == "external_exact_candidate_required":
        return (
            False,
            "local_crosscheck_insufficient_for_exact_target_pair_claim",
            "acquire_external_primary_exact_source",
        )
    if triage_bucket == "named_candidate_manual_match_required":
        return (
            False,
            "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed",
            "manual_match_candidate_to_exact_source_then_sync_reference_split_meta",
        )
    if triage_bucket == "candidate_assignment_required_from_local_pool":
        return (
            False,
            "local_pool_exists_but_slot_ligand_source_smiles_scaffold_not_assigned",
            "assign_candidate_from_local_pool_then_manual_confirm_and_sync",
        )
    return False, "operator_review_required_before_claim_safe_apply", "manual_review_or_keep_blocked"


def _target_id_from_item(item_id: str) -> str:
    if item_id.startswith("AQP1."):
        return "AQP1"
    if item_id.startswith("GLUT1_4PYP."):
        return "GLUT1_4PYP"
    return ""


def _slot_triage(row: dict[str, Any], records: list[dict[str, Any]]) -> tuple[str, str]:
    candidate = _text(row.get("candidate_or_check"))
    request_mode = _text(row.get("request_mode"))
    counts = _record_counts(records)
    candidate_missing = _is_placeholder(candidate)
    if "review_only" in request_mode or "functional_review_only" in request_mode:
        return "keep_review_only_direct_binding_gap", "Functional or review-only slot; reject direct-binding/kcal promotion until a clean direct-binding source is curated."
    if candidate_missing:
        if counts["direct_quantitative_record_count"] > 0 or counts["not_active_nonquantitative_record_count"] > 0:
            return "candidate_assignment_required_from_local_pool", "Local target-level pool exists, but this slot still needs explicit ligand/source/SMILES/scaffold assignment and synchronization."
        return "external_exact_candidate_required", "No slot-level replacement ligand is assigned and the local pool is insufficient for exact authoritative apply."
    if counts["direct_quantitative_record_count"] > 0:
        return "named_candidate_manual_match_required", "Named candidate must be manually matched to exact source identity before any kcal or authoritative apply."
    if counts["functional_quantitative_record_count"] > 0:
        return "functional_quantitative_only_direct_gap_open", "Local target-level functional quantitative evidence exists, but direct binding/kcal claim remains blocked."
    return "external_exact_candidate_required", "No local exact quantitative source pool is sufficient for this named slot."


def build_payload(
    *,
    acquisition_payload: dict[str, Any],
    priority_payload: dict[str, Any],
    crosscheck_dir: str | Path = DEFAULT_CROSSCHECK_DIR,
    acquisition_path: str = DEFAULT_ACQUISITION_JSON.as_posix(),
    priority_path: str = DEFAULT_PRIORITY_JSON.as_posix(),
) -> dict[str, Any]:
    priority_by_item = {
        _text(row.get("item_id")): row for row in _rows(priority_payload) if _text(row.get("domain")) == "transporter"
    }
    records_by_target: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for acquisition_row in _rows(acquisition_payload):
        target_id = _text(acquisition_row.get("target_id"))
        item_id = f"{target_id}.{_text(acquisition_row.get('packet_step'))}"
        target_id = target_id or _target_id_from_item(item_id)
        if target_id not in {"AQP1", "GLUT1_4PYP"}:
            continue
        records = records_by_target.setdefault(target_id, _records_for_target(crosscheck_dir, target_id))
        priority_row = priority_by_item.get(item_id, {})
        counts = _record_counts(records)
        slot_input = dict(acquisition_row)
        slot_input.update(priority_row)
        triage_bucket, triage_note = _slot_triage(slot_input, records)
        direct_example = _example(records, "direct_quantitative")
        functional_example = _example(records, "functional_quantitative")
        inactive_example = _example(records, "not_active_nonquantitative")
        best_evidence = _best_evidence(records, triage_bucket)
        claim_safe_ready, claim_blocker, operator_next_verdict = _claim_safe_detail(
            slot_input, counts, triage_bucket
        )
        rows.append(
            {
                "priority": _text(priority_row.get("priority")) or len(rows) + 1,
                "target_id": target_id,
                "item_id": item_id,
                "packet_step": _text(acquisition_row.get("packet_step")),
                "candidate_or_check": _text(priority_row.get("candidate_or_check")) or _text(acquisition_row.get("replacement_ligand_id")) or _text(acquisition_row.get("current_ligand_id")),
                "request_mode": _text(acquisition_row.get("request_mode")),
                "required_missing_fields": _text(acquisition_row.get("required_missing_fields")),
                "source_signal": _text(acquisition_row.get("source_signal")),
                "local_crosscheck_path_count": _int(priority_row.get("local_crosscheck_path_count")),
                "quantitative_record_count": counts["quantitative_record_count"],
                "direct_quantitative_record_count": counts["direct_quantitative_record_count"],
                "functional_quantitative_record_count": counts["functional_quantitative_record_count"],
                "not_active_nonquantitative_record_count": counts["not_active_nonquantitative_record_count"],
                "source_provenance_record_count": counts["source_provenance_record_count"],
                "direct_example": _text(direct_example.get("activity_type")),
                "direct_example_value": _text(direct_example.get("value")),
                "direct_example_units": _text(direct_example.get("units")),
                "direct_example_source": _text(direct_example.get("document_id")),
                "functional_example": _text(functional_example.get("activity_type")),
                "functional_example_value": _text(functional_example.get("value")),
                "functional_example_units": _text(functional_example.get("units")),
                "functional_example_source": _text(functional_example.get("document_id")),
                "inactive_example_source": _text(inactive_example.get("document_id")),
                "best_evidence_kind": _text(best_evidence.get("source_kind")),
                "best_evidence_source_file": _text(best_evidence.get("source_file")),
                "best_evidence_activity_type": _text(best_evidence.get("activity_type")),
                "best_evidence_value": _text(best_evidence.get("value")),
                "best_evidence_units": _text(best_evidence.get("units")),
                "best_evidence_document_id": _text(best_evidence.get("document_id")),
                "best_evidence_assay_description": _text(best_evidence.get("assay_description")),
                "claim_safe_local_evidence_ready": claim_safe_ready,
                "claim_safe_blocker": claim_blocker,
                "operator_next_verdict": operator_next_verdict,
                "slot_triage_bucket": triage_bucket,
                "slot_triage_note": triage_note,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    local_assignment = [row for row in rows if row["slot_triage_bucket"] == "candidate_assignment_required_from_local_pool"]
    named_manual = [row for row in rows if row["slot_triage_bucket"] == "named_candidate_manual_match_required"]
    functional_only = [row for row in rows if row["slot_triage_bucket"] == "functional_quantitative_only_direct_gap_open"]
    review_only = [row for row in rows if row["slot_triage_bucket"] == "keep_review_only_direct_binding_gap"]
    external = [row for row in rows if row["slot_triage_bucket"] == "external_exact_candidate_required"]
    claim_safe_rows = [row for row in rows if row["claim_safe_local_evidence_ready"]]
    blocked_claim_rows = [row for row in rows if not row["claim_safe_local_evidence_ready"]]
    direct_binding_claim_blocked = [
        row
        for row in rows
        if row["claim_safe_blocker"]
        in {
            "review_only_guardrail_requires_explicit_direct_binding_source",
            "local_crosscheck_has_no_direct_binding_affinity_record",
            "functional_assay_quantitative_but_not_direct_binding_claim_safe",
            "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed",
        }
    ]
    negative_value_blocked = [
        row for row in rows if row["claim_safe_blocker"] == "negative_or_inactive_row_missing_exact_quantitative_value"
    ]
    summary = {
        "packet_type": "transporter_local_crosscheck_triage_packet",
        "triage_packet_ready": True,
        "operator_review_evidence_matrix_ready": bool(rows),
        "triage_row_count": len(rows),
        "target_count": len(records_by_target),
        "candidate_assignment_required_count": len(local_assignment),
        "named_candidate_manual_match_required_count": len(named_manual),
        "functional_quantitative_only_direct_gap_open_count": len(functional_only),
        "review_only_direct_binding_gap_count": len(review_only),
        "external_exact_candidate_required_count": len(external),
        "local_crosscheck_can_close_slots_without_manual_assignment": False,
        "claim_safe_local_evidence_ready_count": len(claim_safe_rows),
        "claim_safe_local_evidence_blocked_count": len(blocked_claim_rows),
        "direct_binding_claim_blocked_count": len(direct_binding_claim_blocked),
        "negative_value_claim_blocked_count": len(negative_value_blocked),
        "top_claim_safe_blocker": blocked_claim_rows[0]["claim_safe_blocker"] if blocked_claim_rows else "",
        "top_operator_next_verdict": blocked_claim_rows[0]["operator_next_verdict"] if blocked_claim_rows else "",
        "authoritative_apply_allowed_count": 0,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [acquisition_path, priority_path, str(crosscheck_dir)],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the GLUT1 direct/negative local pool only after explicit ligand assignment and CSV synchronization; "
            "keep AQP1 direct-binding gaps and GLUT1 review-only rows blocked until exact source identity is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transporter Local Crosscheck Triage Packet",
        "",
        f"- triage_packet_ready: `{s['triage_packet_ready']}`",
        f"- operator_review_evidence_matrix_ready: `{s['operator_review_evidence_matrix_ready']}`",
        f"- triage_row_count: `{s['triage_row_count']}`",
        f"- claim_safe_local_evidence_ready_count: `{s['claim_safe_local_evidence_ready_count']}`",
        f"- claim_safe_local_evidence_blocked_count: `{s['claim_safe_local_evidence_blocked_count']}`",
        f"- direct_binding_claim_blocked_count: `{s['direct_binding_claim_blocked_count']}`",
        f"- negative_value_claim_blocked_count: `{s['negative_value_claim_blocked_count']}`",
        f"- candidate_assignment_required_count: `{s['candidate_assignment_required_count']}`",
        f"- named_candidate_manual_match_required_count: `{s['named_candidate_manual_match_required_count']}`",
        f"- functional_quantitative_only_direct_gap_open_count: `{s['functional_quantitative_only_direct_gap_open_count']}`",
        f"- review_only_direct_binding_gap_count: `{s['review_only_direct_binding_gap_count']}`",
        f"- external_exact_candidate_required_count: `{s['external_exact_candidate_required_count']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Triage Rows",
        "",
        "| priority | target | item | candidate | direct records | functional records | inactive records | claim safe | blocker | bucket |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['target_id']}` | `{row['item_id']}` | `{row['candidate_or_check'] or '-'}` | "
            f"{row['direct_quantitative_record_count']} | {row['functional_quantitative_record_count']} | "
            f"{row['not_active_nonquantitative_record_count']} | `{row['claim_safe_local_evidence_ready']}` | "
            f"`{row['claim_safe_blocker']}` | `{row['slot_triage_bucket']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter local crosscheck triage packet.")
    parser.add_argument("--acquisition-json", default=str(DEFAULT_ACQUISITION_JSON))
    parser.add_argument("--priority-json", default=str(DEFAULT_PRIORITY_JSON))
    parser.add_argument("--crosscheck-dir", default=str(DEFAULT_CROSSCHECK_DIR))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        acquisition_payload=_read_json(args.acquisition_json),
        priority_payload=_read_json(args.priority_json),
        crosscheck_dir=args.crosscheck_dir,
        acquisition_path=args.acquisition_json,
        priority_path=args.priority_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
