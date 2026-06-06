#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_CANDIDATE_WORKBOOK_JSON = RUNS / "transporter_slot_assignment_candidate_workbook_current.json"
DEFAULT_P0_EVIDENCE_ACQUISITION_JSON = RUNS / "transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_AQP1_WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_WORKBOOK_JSON = RUNS / "glut1_packet_replacement_workbook_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_manual_review_intake_template_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_manual_review_intake_template_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_manual_review_intake_template_current.md"

TRUE_FALSE_PLACEHOLDER = "OPERATOR_FILL_TRUE_OR_FALSE"
REVIEW_DECISION_PLACEHOLDER = "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED"
DIRECT_BINDING_PLACEHOLDER = "OPERATOR_FILL_EXACT_DIRECT_BINDING_SOURCE_OR_KEEP_BLOCKED"
NEGATIVE_VALUE_PLACEHOLDER = "OPERATOR_FILL_EXACT_NEGATIVE_KCAL_OR_KEEP_BLOCKED"

CLAIM_BOUNDARY = (
    "Transporter manual review intake template only; pre-fills candidate workbook rows into a reviewer completion "
    "CSV for ligand identity, scaffold, source provenance, split/meta sync, direct-binding evidence, and negative "
    "quantitative value decisions. It does not write config CSVs, authoritatively apply rows, reopen donor policy, "
    "run docking, widen product scope, upload, submit, email, delete, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _workbook_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("workbook_rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _p0_rows_by_item_id(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_item: dict[str, dict[str, Any]] = {}
    for row in _rows(packet):
        item_id = ".".join(
            item
            for item in [
                _text(row.get("target_id")),
                _text(row.get("packet_step")),
            ]
            if item
        )
        if item_id and item_id not in by_item:
            by_item[item_id] = row
    return by_item


def _replacement_rows_by_item_id(
    aqp1_workbook_packet: dict[str, Any],
    glut1_workbook_packet: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    by_item: dict[str, dict[str, Any]] = {}
    for prefix, packet in (("AQP1", aqp1_workbook_packet), ("GLUT1_4PYP", glut1_workbook_packet)):
        for row in _workbook_rows(packet):
            item_id = ".".join(item for item in [prefix, _text(row.get("packet_step"))] if item)
            if item_id and item_id not in by_item:
                by_item[item_id] = row
    return by_item


def _apply_p0_slot_overlay(
    row: dict[str, Any],
    *,
    p0_by_item_id: dict[str, dict[str, Any]],
    replacement_by_item_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item_id = _text(row.get("item_id"))
    p0 = p0_by_item_id.get(item_id, {})
    replacement = replacement_by_item_id.get(item_id, {})
    if not p0:
        return row
    updated = dict(row)
    original_ligand_id = _text(updated.get("replacement_ligand_id"))
    replacement_ligand_id = _text(replacement.get("replacement_ligand_id"))
    p0_ligand_id = _text(p0.get("replacement_ligand_id"))
    if replacement_ligand_id:
        updated["replacement_ligand_id"] = replacement_ligand_id
    elif p0_ligand_id:
        updated["replacement_ligand_id"] = p0_ligand_id
    for field in (
        "replacement_is_binder",
        "replacement_reference_binding_kcal_mol",
        "replacement_role",
        "replacement_smiles",
        "replacement_scaffold",
    ):
        value = _text(replacement.get(field))
        if value or field == "replacement_reference_binding_kcal_mol":
            updated[field] = value
    source = _text(replacement.get("replacement_source")) or _text(p0.get("source_signal"))
    if source:
        updated["replacement_source"] = source
    required_missing_fields = _text(p0.get("required_missing_fields")) or _text(
        replacement.get("required_missing_fields")
    )
    if required_missing_fields:
        updated["manual_review_blockers"] = ";".join(
            part
            for part in [
                _text(updated.get("manual_review_blockers")),
                f"p0_required_missing_fields={required_missing_fields}",
            ]
            if part
        )
    updated["p0_slot_overlay_applied"] = True
    updated["p0_slot_overlay_source_artifact"] = DEFAULT_P0_EVIDENCE_ACQUISITION_JSON.as_posix()
    updated["p0_slot_overlay_candidate_original"] = original_ligand_id
    updated["p0_slot_overlay_candidate_ligand_id"] = _text(updated.get("replacement_ligand_id"))
    updated["p0_slot_overlay_source_signal"] = _text(p0.get("source_signal"))
    updated["p0_slot_overlay_request_mode"] = _text(p0.get("request_mode"))
    updated["p0_slot_overlay_evidence_state"] = _text(p0.get("evidence_state"))
    updated["p0_slot_overlay_required_missing_fields"] = required_missing_fields
    updated["p0_slot_overlay_claim_safe_step_ready"] = p0.get("claim_safe_step_ready") is True
    updated["p0_slot_overlay_authoritative_apply_allowed"] = p0.get("authoritative_apply_allowed") is True
    updated["p0_slot_overlay_scope_promotion_allowed"] = p0.get("scope_promotion_allowed") is True
    return updated


def _requires_direct_binding(row: dict[str, Any]) -> bool:
    bucket = _text(row.get("slot_triage_bucket"))
    mode = _text(row.get("candidate_mode"))
    return bucket in {"functional_quantitative_only_direct_gap_open", "keep_review_only_direct_binding_gap"} or (
        "functional_quantitative" in mode
    )


def _requires_negative_value(row: dict[str, Any]) -> bool:
    return "inactive_nonquantitative" in _text(row.get("candidate_mode")) or (
        "replacement_reference_binding_kcal_mol" in _text(row.get("required_missing_fields")).split(",")
        and _text(row.get("replacement_is_binder")) == "0"
    )


def _stable_review_id(prefix: str, row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, str]:
    payload = {field: _text(row.get(field)) for field in fields}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}", digest


def _review_requirements(row: dict[str, Any]) -> str:
    requirements = [
        "manual_ligand_identity_confirmation",
        "manual_scaffold_confirmation",
        "source_provenance_confirmation",
        "split_meta_sync_confirmation",
    ]
    if _requires_direct_binding(row):
        requirements.append("exact_direct_binding_source_or_keep_blocked")
    if _requires_negative_value(row):
        requirements.append("exact_negative_quantitative_value_or_keep_blocked")
    return ",".join(requirements)


def _template_row(row: dict[str, Any]) -> dict[str, Any]:
    direct_required = _requires_direct_binding(row)
    negative_required = _requires_negative_value(row)
    review_row_id, source_fingerprint = _stable_review_id(
        "transporter_review",
        row,
        (
            "target_id",
            "target_reference_id",
            "item_id",
            "packet_step",
            "replacement_ligand_id",
            "replacement_is_binder",
            "replacement_reference_binding_kcal_mol",
            "replacement_source",
            "candidate_mode",
            "slot_triage_bucket",
        ),
    )
    return {
        "review_row_id": review_row_id,
        "source_row_fingerprint": source_fingerprint,
        "priority": _text(row.get("priority")),
        "target_id": _text(row.get("target_id")),
        "target_reference_id": _text(row.get("target_reference_id")),
        "item_id": _text(row.get("item_id")),
        "packet_step": _text(row.get("packet_step")),
        "slot_triage_bucket": _text(row.get("slot_triage_bucket")),
        "candidate_mode": _text(row.get("candidate_mode")),
        "replacement_ligand_id": _text(row.get("replacement_ligand_id")),
        "replacement_is_binder": _text(row.get("replacement_is_binder")),
        "replacement_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "replacement_source": _text(row.get("replacement_source")),
        "replacement_smiles": _text(row.get("replacement_smiles")),
        "replacement_scaffold": _text(row.get("replacement_scaffold")),
        "candidate_activity_type": _text(row.get("candidate_activity_type")),
        "candidate_activity_value": _text(row.get("candidate_activity_value")),
        "candidate_activity_units": _text(row.get("candidate_activity_units")),
        "candidate_document_id": _text(row.get("candidate_document_id")),
        "candidate_source_file": _text(row.get("candidate_source_file")),
        "manual_review_blockers": _text(row.get("manual_review_blockers")),
        "review_requirements": _review_requirements(row),
        "manual_ligand_identity_confirmed": TRUE_FALSE_PLACEHOLDER,
        "manual_scaffold_confirmed": TRUE_FALSE_PLACEHOLDER,
        "manual_source_provenance_confirmed": TRUE_FALSE_PLACEHOLDER,
        "manual_split_meta_sync_confirmed": TRUE_FALSE_PLACEHOLDER,
        "direct_binding_source_url_or_doi": DIRECT_BINDING_PLACEHOLDER if direct_required else "",
        "negative_reference_binding_kcal_mol": NEGATIVE_VALUE_PLACEHOLDER if negative_required else "",
        "review_decision": REVIEW_DECISION_PLACEHOLDER,
        "authoritative_apply_requested": TRUE_FALSE_PLACEHOLDER,
        "reviewer_notes": "",
        "direct_binding_evidence_required": direct_required,
        "negative_quantitative_value_required": negative_required,
        "p0_slot_overlay_applied": row.get("p0_slot_overlay_applied") is True,
        "p0_slot_overlay_source_artifact": _text(row.get("p0_slot_overlay_source_artifact")),
        "p0_slot_overlay_candidate_original": _text(row.get("p0_slot_overlay_candidate_original")),
        "p0_slot_overlay_candidate_ligand_id": _text(row.get("p0_slot_overlay_candidate_ligand_id")),
        "p0_slot_overlay_source_signal": _text(row.get("p0_slot_overlay_source_signal")),
        "p0_slot_overlay_request_mode": _text(row.get("p0_slot_overlay_request_mode")),
        "p0_slot_overlay_evidence_state": _text(row.get("p0_slot_overlay_evidence_state")),
        "p0_slot_overlay_required_missing_fields": _text(row.get("p0_slot_overlay_required_missing_fields")),
        "p0_slot_overlay_claim_safe_step_ready": row.get("p0_slot_overlay_claim_safe_step_ready") is True,
        "p0_slot_overlay_authoritative_apply_allowed": row.get("p0_slot_overlay_authoritative_apply_allowed") is True,
        "p0_slot_overlay_scope_promotion_allowed": row.get("p0_slot_overlay_scope_promotion_allowed") is True,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_payload(
    *,
    candidate_workbook_packet: dict[str, Any],
    candidate_workbook_path: str = DEFAULT_CANDIDATE_WORKBOOK_JSON.as_posix(),
    p0_evidence_acquisition_packet: dict[str, Any] | None = None,
    aqp1_workbook_packet: dict[str, Any] | None = None,
    glut1_workbook_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workbook = _summary(candidate_workbook_packet)
    workbook_ready = _bool(workbook.get("candidate_workbook_ready"))
    expected_review_rows = _int(workbook.get("candidate_ready_for_manual_review_count"))
    source_rows = [row for row in _rows(candidate_workbook_packet) if _bool(row.get("candidate_ready_for_manual_review"))]
    p0_by_item_id = _p0_rows_by_item_id(p0_evidence_acquisition_packet or {})
    replacement_by_item_id = _replacement_rows_by_item_id(
        aqp1_workbook_packet or {},
        glut1_workbook_packet or {},
    )
    rows = [
        _template_row(
            _apply_p0_slot_overlay(
                row,
                p0_by_item_id=p0_by_item_id,
                replacement_by_item_id=replacement_by_item_id,
            )
        )
        for row in source_rows
    ]
    direct_binding_required = [row for row in rows if row["direct_binding_evidence_required"]]
    negative_value_required = [row for row in rows if row["negative_quantitative_value_required"]]
    manual_confirmation_required = [
        row for row in rows if "manual_ligand_identity_and_scaffold_confirmation_required" in row["manual_review_blockers"]
    ]
    overlay_rows = [row for row in rows if row.get("p0_slot_overlay_applied") is True]
    overlay_candidate_changed_rows = [
        row
        for row in overlay_rows
        if _text(row.get("p0_slot_overlay_candidate_original"))
        and _text(row.get("p0_slot_overlay_candidate_original")) != _text(row.get("replacement_ligand_id"))
    ]
    unique_review_row_ids = {row["review_row_id"] for row in rows}
    row_count_matches_workbook = bool(expected_review_rows == 0 or len(rows) == expected_review_rows)
    unique_review_row_ids_ready = bool(len(unique_review_row_ids) == len(rows))
    ready = bool(workbook_ready and rows and row_count_matches_workbook and unique_review_row_ids_ready)
    blockers: list[str] = []
    if not workbook_ready:
        blockers.append("candidate_workbook_ready")
    if not rows:
        blockers.append("manual_review_rows")
    if not row_count_matches_workbook:
        blockers.append("manual_review_row_count_matches_workbook")
    if rows and not unique_review_row_ids_ready:
        blockers.append("unique_review_row_ids")
    first_review_row = rows[0] if rows else {}

    summary = {
        "packet_type": "transporter_manual_review_intake_template",
        "status": "transporter_manual_review_intake_template_ready" if ready else "blocked_transporter_manual_review_intake_template",
        "manual_review_intake_ready": ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "candidate_workbook_artifact": candidate_workbook_path,
        "candidate_workbook_ready": workbook_ready,
        "candidate_workbook_row_count": _int(workbook.get("candidate_row_count")),
        "expected_manual_review_row_count": expected_review_rows,
        "manual_review_template_row_count": len(rows),
        "manual_review_row_count_matches_workbook": row_count_matches_workbook,
        "unique_review_row_id_count": len(unique_review_row_ids),
        "unique_review_row_ids_ready": unique_review_row_ids_ready,
        "direct_binding_evidence_required_count": len(direct_binding_required),
        "negative_quantitative_value_required_count": len(negative_value_required),
        "manual_confirmation_required_count": len(manual_confirmation_required),
        "p0_slot_overlay_row_count": len(overlay_rows),
        "p0_slot_overlay_candidate_changed_count": len(overlay_candidate_changed_rows),
        "p0_slot_overlay_first_item_id": _text(overlay_rows[0].get("item_id")) if overlay_rows else "",
        "p0_slot_overlay_first_candidate_ligand_id": _text(overlay_rows[0].get("replacement_ligand_id"))
        if overlay_rows
        else "",
        "p0_slot_overlay_first_source": _text(overlay_rows[0].get("replacement_source")) if overlay_rows else "",
        "p0_slot_overlay_claim_safe_step_ready_count": sum(
            1 for row in overlay_rows if row.get("p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_row_id": _text(first_review_row.get("review_row_id")),
        "first_review_item_id": _text(first_review_row.get("item_id")),
        "first_review_target_id": _text(first_review_row.get("target_id")),
        "first_review_candidate_ligand_id": _text(first_review_row.get("replacement_ligand_id")),
        "first_review_replacement_source": _text(first_review_row.get("replacement_source")),
        "first_review_replacement_reference_binding_kcal_mol": _text(
            first_review_row.get("replacement_reference_binding_kcal_mol")
        ),
        "first_review_direct_binding_evidence_required": bool(
            first_review_row.get("direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": _text(
            first_review_row.get("direct_binding_source_url_or_doi")
        ),
        "first_review_negative_quantitative_value_required": bool(
            first_review_row.get("negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": _text(
            first_review_row.get("negative_reference_binding_kcal_mol")
        ),
        "first_review_review_decision": _text(first_review_row.get("review_decision")),
        "first_review_authoritative_apply_requested": _text(
            first_review_row.get("authoritative_apply_requested")
        ),
        "first_review_manual_review_blockers": _text(first_review_row.get("manual_review_blockers")),
        "first_review_review_requirements": _text(first_review_row.get("review_requirements")),
        "first_review_p0_slot_overlay_required_missing_fields": _text(
            first_review_row.get("p0_slot_overlay_required_missing_fields")
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            first_review_row.get("p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            first_review_row.get("p0_slot_overlay_authoritative_apply_allowed") is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            first_review_row.get("p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "review_decision_placeholder": REVIEW_DECISION_PLACEHOLDER,
        "review_decision_placeholder_count": sum(1 for row in rows if row["review_decision"] == REVIEW_DECISION_PLACEHOLDER),
        "authoritative_apply_requested_placeholder_count": sum(
            1 for row in rows if row["authoritative_apply_requested"] == TRUE_FALSE_PLACEHOLDER
        ),
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Complete this review template, keep review-only/functional surrogate rows blocked unless exact direct-binding evidence is added, "
            "then regenerate transporter P0 closure and binder promotion gates."
            if ready
            else "Regenerate the transporter candidate workbook before manual review intake."
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
        "# Transporter Manual Review Intake Template",
        "",
        f"- status: `{s['status']}`",
        f"- manual_review_intake_ready: `{s['manual_review_intake_ready']}`",
        f"- manual_review_template_row_count: `{s['manual_review_template_row_count']}`",
        f"- unique_review_row_ids_ready: `{s['unique_review_row_ids_ready']}`",
        f"- direct_binding_evidence_required_count: `{s['direct_binding_evidence_required_count']}`",
        f"- negative_quantitative_value_required_count: `{s['negative_quantitative_value_required_count']}`",
        f"- manual_confirmation_required_count: `{s['manual_confirmation_required_count']}`",
        f"- p0_slot_overlay_row_count: `{s['p0_slot_overlay_row_count']}`",
        f"- p0_slot_overlay_candidate_changed_count: `{s['p0_slot_overlay_candidate_changed_count']}`",
        f"- p0_slot_overlay_first_item_id: `{s['p0_slot_overlay_first_item_id'] or '-'}`",
        f"- p0_slot_overlay_first_candidate_ligand_id: `{s['p0_slot_overlay_first_candidate_ligand_id'] or '-'}`",
        f"- p0_slot_overlay_first_source: `{s['p0_slot_overlay_first_source'] or '-'}`",
        f"- review_decision_placeholder_count: `{s['review_decision_placeholder_count']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        "",
        "## Review Rows",
        "",
        "| row id | priority | target | item | mode | requirements | decision |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | {row['priority']} | `{row['target_id']}` | `{row['item_id']}` | `{row['candidate_mode']}` | "
            f"`{row['review_requirements']}` | `{row['review_decision']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter manual review intake template.")
    parser.add_argument("--candidate-workbook-json", default=str(DEFAULT_CANDIDATE_WORKBOOK_JSON))
    parser.add_argument("--p0-evidence-acquisition-json", default=str(DEFAULT_P0_EVIDENCE_ACQUISITION_JSON))
    parser.add_argument("--aqp1-workbook-json", default=str(DEFAULT_AQP1_WORKBOOK_JSON))
    parser.add_argument("--glut1-workbook-json", default=str(DEFAULT_GLUT1_WORKBOOK_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        candidate_workbook_packet=_read_json(args.candidate_workbook_json),
        candidate_workbook_path=args.candidate_workbook_json,
        p0_evidence_acquisition_packet=_read_json(args.p0_evidence_acquisition_json),
        aqp1_workbook_packet=_read_json(args.aqp1_workbook_json),
        glut1_workbook_packet=_read_json(args.glut1_workbook_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
