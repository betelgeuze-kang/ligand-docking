#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_EXACT_REVIEW_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_BLOCKED_GATE_JSON = RUNS / "pxr_blocked_row_promotion_gate_current.json"
DEFAULT_RECONCILIATION_JSON = RUNS / "pxr_authoritative_reconciliation_packet_current.json"
DEFAULT_PUBLIC_RECHECK_JSON = RUNS / "pxr_public_evidence_recheck_packet_current.json"
DEFAULT_DIRECT_REPLACEMENT_JSON = RUNS / "pxr_direct_binding_replacement_candidate_packet_current.json"
DEFAULT_DIRECT_REPLACEMENT_APPLY_DRAFT_JSON = RUNS / "pxr_direct_binding_replacement_apply_draft_current.json"
DEFAULT_OUT_JSON = RUNS / "pxr_source_modality_triage_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_source_modality_triage_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_source_modality_triage_current.md"

CLAIM_BOUNDARY = (
    "PXR source-modality triage only; classifies blocked human NR1I2/PXR rows by evidence modality and "
    "claim-safety for scope-gate use. It does not promote PXR scope, fill operator placeholders, apply rows, "
    "run docking, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


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
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _source_modality(row: dict[str, Any]) -> str:
    mode = " ".join(
        [
            _text(row.get("request_mode")),
            _text(row.get("required_evidence_mode")),
            _text(row.get("fail_closed_blockers")),
            _text(row.get("review_bucket")),
        ]
    ).lower()
    if "activity_proxy_conflicts" in mode or "conflict" in mode or "defer" in mode:
        return "activity_proxy_or_conflict_surrogate"
    if "inactive" in mode or "negative" in mode:
        return "negative_or_inactive_quantitative_review"
    if _text(row.get("current_label")) == "binder":
        return "binder_signal_quantitative_gap"
    return "operator_review_placeholder"


def _claim_safe(row: dict[str, Any]) -> bool:
    return (
        row.get("scope_promotion_allowed") is True
        and row.get("authoritative_apply_allowed") is True
        and not _text(row.get("readiness_missing_fields"))
        and not _text(row.get("fail_closed_blockers"))
        and not _text(row.get("replacement_reference_binding_kcal_mol")).startswith("OPERATOR_FILL")
        and not _text(row.get("replacement_source_url_or_doi")).startswith("OPERATOR_FILL")
        and _text(row.get("target_match_confirmed")).lower() == "true"
        and _text(row.get("assay_is_direct_or_claim_safe")).lower() == "true"
    )


def _triage_row(
    row: dict[str, Any],
    gate_by_ligand: dict[str, dict[str, Any]],
    recheck_by_ligand: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate = _text(row.get("candidate_name"))
    gate = gate_by_ligand.get(candidate.lower(), {})
    recheck = recheck_by_ligand.get(candidate.lower(), {})
    modality = _source_modality(row)
    claim_safe = _claim_safe(row)
    conflict_required = row.get("conflict_resolution_required") is True
    return {
        "review_row_id": _text(row.get("review_row_id")),
        "candidate_name": candidate,
        "packet_step": _text(row.get("packet_step")),
        "target_gene": _text(row.get("target_gene")) or "NR1I2",
        "target_alias": _text(row.get("target_alias")) or "PXR",
        "target_species": _text(row.get("target_species")) or "human",
        "current_label": _text(row.get("current_label")),
        "source_modality": modality,
        "required_evidence_mode": _text(row.get("required_evidence_mode")),
        "request_mode": _text(row.get("request_mode")),
        "replacement_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "replacement_source_url_or_doi": _text(row.get("replacement_source_url_or_doi")),
        "target_match_confirmed": _text(row.get("target_match_confirmed")),
        "assay_is_direct_or_claim_safe": _text(row.get("assay_is_direct_or_claim_safe")),
        "conflict_resolution_required": conflict_required,
        "conflict_resolution_decision": _text(row.get("conflict_resolution_decision")),
        "readiness_missing_fields": _text(row.get("readiness_missing_fields")),
        "fail_closed_blockers": _text(row.get("fail_closed_blockers")),
        "gate_promotion_blocker": _text(gate.get("promotion_blocker")),
        "gate_evidence_signal": _text(gate.get("evidence_signal")),
        "public_recheck_decision": _text(recheck.get("public_recheck_decision")),
        "public_recheck_blocker": _text(recheck.get("public_recheck_blocker")),
        "public_recheck_chembl_activity_record_count": _int(
            recheck.get("chembl_activity_record_count")
        ),
        "public_recheck_chembl_direct_binding_record_count": _int(
            recheck.get("chembl_direct_binding_record_count")
        ),
        "public_recheck_chembl_functional_activity_record_count": _int(
            recheck.get("chembl_functional_activity_record_count")
        ),
        "public_recheck_bindingdb_pxr_like_record_count": _int(
            recheck.get("bindingdb_pxr_like_record_count")
        ),
        "public_direct_or_claim_safe_binding_kcal_ready": (
            recheck.get("public_direct_or_claim_safe_binding_kcal_ready") is True
        ),
        "direct_or_claim_safe_quantitative_evidence_ready": claim_safe,
        "accepted_for_scope_promotion": claim_safe,
        "rejection_reason": ""
        if claim_safe
        else (
            "activity_proxy_conflict_requires_exact_human_nr1i2_pxr_resolution"
            if conflict_required or "conflict" in modality
            else "exact_human_nr1i2_pxr_quantitative_kcal_and_operator_review_required"
        ),
    }


def build_payload(
    *,
    exact_review_packet: dict[str, Any],
    blocked_gate_packet: dict[str, Any],
    reconciliation_packet: dict[str, Any],
    public_recheck_packet: dict[str, Any] | None = None,
    direct_replacement_packet: dict[str, Any] | None = None,
    direct_replacement_apply_draft_packet: dict[str, Any] | None = None,
    exact_review_path: str = DEFAULT_EXACT_REVIEW_JSON.as_posix(),
    blocked_gate_path: str = DEFAULT_BLOCKED_GATE_JSON.as_posix(),
    reconciliation_path: str = DEFAULT_RECONCILIATION_JSON.as_posix(),
    public_recheck_path: str = DEFAULT_PUBLIC_RECHECK_JSON.as_posix(),
    direct_replacement_path: str = DEFAULT_DIRECT_REPLACEMENT_JSON.as_posix(),
    direct_replacement_apply_draft_path: str = DEFAULT_DIRECT_REPLACEMENT_APPLY_DRAFT_JSON.as_posix(),
) -> dict[str, Any]:
    exact = _summary(exact_review_packet)
    gate = _summary(blocked_gate_packet)
    reconciliation = _summary(reconciliation_packet)
    public_recheck = _summary(public_recheck_packet or {})
    direct_replacement = _summary(direct_replacement_packet or {})
    direct_replacement_apply_draft = _summary(direct_replacement_apply_draft_packet or {})
    gate_by_ligand = {
        _text(row.get("ligand")).lower(): row
        for row in _rows(blocked_gate_packet)
        if _text(row.get("ligand"))
    }
    recheck_by_ligand = {
        _text(row.get("candidate_name")).lower(): row
        for row in _rows(public_recheck_packet or {})
        if _text(row.get("candidate_name"))
    }
    rows = [_triage_row(row, gate_by_ligand, recheck_by_ligand) for row in _rows(exact_review_packet)]
    exact_review_complete = bool(
        exact.get("pxr_exact_review_intake_ready") is True
        and _int(exact.get("expected_blocked_row_count")) == 0
        and _int(exact.get("kcal_placeholder_count")) == 0
        and _int(exact.get("review_decision_placeholder_count")) == 0
    )
    conflict_rows = [row for row in rows if row["conflict_resolution_required"] is True]
    claim_safe_rows = [row for row in rows if row["direct_or_claim_safe_quantitative_evidence_ready"] is True]
    activity_proxy_rows = [
        row for row in rows if row["source_modality"] == "activity_proxy_or_conflict_surrogate"
    ]
    negative_review_rows = [
        row for row in rows if row["source_modality"] == "negative_or_inactive_quantitative_review"
    ]
    public_recheck_ready_rows = [
        row for row in rows if row["public_direct_or_claim_safe_binding_kcal_ready"] is True
    ]
    next_row = rows[0] if rows else {}
    summary = {
        "packet_type": "pxr_source_modality_triage",
        "status": (
            "pxr_source_modality_triage_ready"
            if (rows and len(claim_safe_rows) == len(rows)) or exact_review_complete
            else "blocked_pxr_source_modality_triage"
        ),
        "source_modality_guard_ready": bool(rows) or exact_review_complete,
        "triage_artifact": DEFAULT_OUT_JSON.as_posix(),
        "exact_review_artifact": exact_review_path,
        "blocked_gate_artifact": blocked_gate_path,
        "reconciliation_artifact": reconciliation_path,
        "public_recheck_artifact": public_recheck_path,
        "direct_replacement_artifact": direct_replacement_path,
        "direct_replacement_apply_draft_artifact": direct_replacement_apply_draft_path,
        "row_count": len(rows),
        "exact_review_intake_ready": exact.get("pxr_exact_review_intake_ready") is True,
        "blocked_gate_promotion_ready": gate.get("promotion_ready") is True,
        "reconciliation_packet_ready": reconciliation.get("reconciliation_packet_ready") is True,
        "public_evidence_recheck_ready": public_recheck.get("public_evidence_recheck_ready") is True,
        "public_recheck_candidate_count": _int(public_recheck.get("candidate_count")),
        "public_recheck_chembl_direct_binding_total_record_count": _int(
            public_recheck.get("chembl_direct_binding_total_record_count")
        ),
        "public_recheck_chembl_functional_activity_total_record_count": _int(
            public_recheck.get("chembl_functional_activity_total_record_count")
        ),
        "public_recheck_bindingdb_pxr_like_total_record_count": _int(
            public_recheck.get("bindingdb_pxr_like_total_record_count")
        ),
        "public_recheck_direct_or_claim_safe_binding_kcal_ready_count": len(public_recheck_ready_rows),
        "public_recheck_all_candidates_remain_blocked": (
            public_recheck.get("all_candidates_remain_blocked") is True
        ),
        "public_recheck_first_blocked_candidate_name": _text(
            public_recheck.get("first_blocked_candidate_name")
        ),
        "public_recheck_first_blocked_reason": _text(public_recheck.get("first_blocked_reason")),
        "direct_replacement_candidate_packet_ready": (
            direct_replacement.get("replacement_candidate_packet_ready") is True
        ),
        "direct_replacement_candidate_count": _int(direct_replacement.get("direct_binding_candidate_count")),
        "direct_replacement_selected_candidate_count": _int(
            direct_replacement.get("selected_replacement_candidate_count")
        ),
        "direct_replacement_selected_claim_safe_candidate_count": _int(
            direct_replacement.get("selected_claim_safe_candidate_count")
        ),
        "direct_replacement_first_ligand_id": _text(
            direct_replacement.get("first_replacement_ligand_id")
        ),
        "direct_replacement_first_molecule_chembl_id": _text(
            direct_replacement.get("first_replacement_molecule_chembl_id")
        ),
        "direct_replacement_first_reference_binding_kcal_mol": _text(
            direct_replacement.get("first_replacement_reference_binding_kcal_mol")
        ),
        "direct_replacement_first_source": _text(direct_replacement.get("first_replacement_source")),
        "direct_replacement_apply_draft_ready": (
            direct_replacement_apply_draft.get("draft_ready") is True
        ),
        "direct_replacement_apply_draft_status": _text(
            direct_replacement_apply_draft.get("status")
        ),
        "direct_replacement_apply_draft_workbook_row_count": _int(
            direct_replacement_apply_draft.get("workbook_row_count")
        ),
        "direct_replacement_apply_draft_blocked_row_count_before_draft": _int(
            direct_replacement_apply_draft.get("blocked_row_count_before_draft")
        ),
        "direct_replacement_apply_draft_overlay_row_count": _int(
            direct_replacement_apply_draft.get("direct_binding_overlay_row_count")
        ),
        "direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": _int(
            direct_replacement_apply_draft.get("ready_for_apply_row_count_after_draft")
        ),
        "direct_replacement_apply_draft_blocked_row_count_after_draft": _int(
            direct_replacement_apply_draft.get("blocked_row_count_after_draft")
        ),
        "direct_replacement_apply_draft_first_overlay_ligand_id": _text(
            direct_replacement_apply_draft.get("first_overlay_replacement_ligand_id")
        ),
        "direct_replacement_apply_draft_authoritative_fields_touched": (
            direct_replacement_apply_draft.get("authoritative_replacement_fields_touched") is True
        ),
        "conflict_resolution_required_count": len(conflict_rows),
        "activity_proxy_or_conflict_surrogate_row_count": len(activity_proxy_rows),
        "negative_or_inactive_quantitative_review_row_count": len(negative_review_rows),
        "direct_or_claim_safe_quantitative_ready_count": len(claim_safe_rows),
        "claim_safe_quantitative_ready_count": _int(gate.get("claim_safe_quantitative_ready_count")),
        "authoritative_apply_allowed_count": _int(gate.get("authoritative_apply_allowed_count")),
        "kcal_placeholder_count": _int(exact.get("kcal_placeholder_count")),
        "source_placeholder_count": _int(exact.get("source_placeholder_count")),
        "target_match_placeholder_count": _int(exact.get("target_match_placeholder_count")),
        "accepted_for_scope_promotion_count": sum(
            1 for row in rows if row["accepted_for_scope_promotion"] is True
        ),
        "next_review_row_id": _text(next_row.get("review_row_id")),
        "next_review_candidate_name": _text(next_row.get("candidate_name")),
        "next_review_source_modality": _text(next_row.get("source_modality")),
        "next_review_rejection_reason": _text(next_row.get("rejection_reason")),
        "triage_decision": (
            "pxr_exact_review_closed_no_blocked_rows_remain"
            if exact_review_complete
            else
            "keep_blocked_until_all_pxr_rows_have_exact_human_nr1i2_pxr_direct_or_claim_safe_quantitative_evidence"
        ),
        "next_required_step": (
            "PXR exact-review blocked rows are closed; rerun product scope breadth and goal completion gates."
            if exact_review_complete
            else
            "Keep PXR domain promotion blocked until each PXR review row has exact human NR1I2/PXR quantitative "
            "kcal/source evidence, target match, direct-or-claim-safe assay confirmation, conflict resolution where "
            "required, and authoritative apply allowed by the blocked-row gate."
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "scope_promotion_allowed": exact_review_complete,
        "claim_boundary": CLAIM_BOUNDARY,
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
        "# PXR Source-Modality Triage",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- conflict_resolution_required_count: `{s['conflict_resolution_required_count']}`",
        f"- activity_proxy_or_conflict_surrogate_row_count: `{s['activity_proxy_or_conflict_surrogate_row_count']}`",
        f"- direct_or_claim_safe_quantitative_ready_count: `{s['direct_or_claim_safe_quantitative_ready_count']}`",
        f"- public_evidence_recheck_ready: `{s['public_evidence_recheck_ready']}`",
        f"- public_recheck_chembl_direct_binding_total_record_count: `{s['public_recheck_chembl_direct_binding_total_record_count']}`",
        f"- public_recheck_bindingdb_pxr_like_total_record_count: `{s['public_recheck_bindingdb_pxr_like_total_record_count']}`",
        f"- public_recheck_direct_or_claim_safe_binding_kcal_ready_count: `{s['public_recheck_direct_or_claim_safe_binding_kcal_ready_count']}`",
        f"- direct_replacement_candidate_packet_ready: `{s['direct_replacement_candidate_packet_ready']}`",
        f"- direct_replacement_selected_claim_safe_candidate_count: `{s['direct_replacement_selected_claim_safe_candidate_count']}`",
        f"- direct_replacement_first_ligand_id: `{s['direct_replacement_first_ligand_id']}`",
        f"- direct_replacement_apply_draft_ready: `{s['direct_replacement_apply_draft_ready']}`",
        f"- direct_replacement_apply_draft_blocked_row_count_after_draft: `{s['direct_replacement_apply_draft_blocked_row_count_after_draft']}`",
        f"- kcal_placeholder_count: `{s['kcal_placeholder_count']}`",
        f"- triage_decision: `{s['triage_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| row id | candidate | source modality | public recheck | claim safe | rejection reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | `{row['candidate_name']}` | `{row['source_modality']}` | "
            f"`{row['public_recheck_blocker']}` | "
            f"`{row['direct_or_claim_safe_quantitative_evidence_ready']}` | `{row['rejection_reason']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR source-modality triage packet.")
    parser.add_argument("--exact-review-json", default=DEFAULT_EXACT_REVIEW_JSON.as_posix())
    parser.add_argument("--blocked-gate-json", default=DEFAULT_BLOCKED_GATE_JSON.as_posix())
    parser.add_argument("--reconciliation-json", default=DEFAULT_RECONCILIATION_JSON.as_posix())
    parser.add_argument("--public-recheck-json", default=DEFAULT_PUBLIC_RECHECK_JSON.as_posix())
    parser.add_argument("--direct-replacement-json", default=DEFAULT_DIRECT_REPLACEMENT_JSON.as_posix())
    parser.add_argument(
        "--direct-replacement-apply-draft-json",
        default=DEFAULT_DIRECT_REPLACEMENT_APPLY_DRAFT_JSON.as_posix(),
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON.as_posix())
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV.as_posix())
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD.as_posix())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        exact_review_packet=_read_json(args.exact_review_json),
        blocked_gate_packet=_read_json(args.blocked_gate_json),
        reconciliation_packet=_read_json(args.reconciliation_json),
        public_recheck_packet=_read_json(args.public_recheck_json),
        direct_replacement_packet=_read_json(args.direct_replacement_json),
        direct_replacement_apply_draft_packet=_read_json(args.direct_replacement_apply_draft_json),
        exact_review_path=args.exact_review_json,
        blocked_gate_path=args.blocked_gate_json,
        reconciliation_path=args.reconciliation_json,
        public_recheck_path=args.public_recheck_json,
        direct_replacement_path=args.direct_replacement_json,
        direct_replacement_apply_draft_path=args.direct_replacement_apply_draft_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
