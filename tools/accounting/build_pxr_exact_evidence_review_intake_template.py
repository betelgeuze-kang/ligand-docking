#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_RECONCILIATION_JSON = RUNS / "pxr_authoritative_reconciliation_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_exact_evidence_review_intake_template_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_exact_evidence_review_intake_template_current.md"
DEFAULT_FILL_READINESS_JSON = RUNS / "pxr_packet_fill_readiness_current.json"
DEFAULT_BLOCKED_GATE_JSON = RUNS / "pxr_blocked_row_promotion_gate_current.json"
DEFAULT_SCOPE_BREADTH_JSON = RUNS / "product_scope_breadth_contract_current.json"

TRUE_FALSE_PLACEHOLDER = "OPERATOR_FILL_TRUE_OR_FALSE"
KCAL_PLACEHOLDER = "OPERATOR_FILL_EXACT_HUMAN_NR1I2_PXR_KCAL_OR_KEEP_BLOCKED"
SOURCE_PLACEHOLDER = "OPERATOR_FILL_EXACT_SOURCE_URL_OR_DOI_OR_KEEP_BLOCKED"
ASSAY_PLACEHOLDER = "OPERATOR_FILL_ASSAY_TYPE_AND_ENDPOINT"
DECISION_PLACEHOLDER = "OPERATOR_FILL_RESOLVE_CONFLICT_OR_KEEP_DEFERRED"
REVIEW_DECISION_PLACEHOLDER = "OPERATOR_FILL_APPROVE_FOR_DRAFT_OR_KEEP_BLOCKED"

CLAIM_BOUNDARY = (
    "PXR exact evidence review intake template only; pre-fills blocked human NR1I2/PXR rows into a reviewer "
    "completion CSV for exact quantitative kcal/source, assay endpoint, target match, and conflict/defer decisions. "
    "It does not authoritatively apply rows, promote PXR scope, run docking, upload, submit, email, delete, or "
    "mutate external state."
)

PXR_REQUIRED_CLAIM_GUARDRAILS = [
    "human_NR1I2_PXR_target_match_required",
    "activity_proxy_conflict_must_be_resolved_or_deferred",
    "review_only_or_deferred_rows_do_not_authorize_pxr_promotion",
    "authoritative_apply_requested_only_when_direct_or_claim_safe",
    "scope_promotion_allowed_false_until_gate_green",
]

NEXT_REVIEW_RETURN_ARTIFACTS = [
    DEFAULT_OUT_CSV.as_posix(),
    DEFAULT_FILL_READINESS_JSON.as_posix(),
    DEFAULT_BLOCKED_GATE_JSON.as_posix(),
    DEFAULT_RECONCILIATION_JSON.as_posix(),
    DEFAULT_SCOPE_BREADTH_JSON.as_posix(),
]


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _requires_conflict_decision(row: dict[str, Any]) -> bool:
    text = " ".join(
        [
            _text(row.get("request_mode")),
            _text(row.get("review_bucket")),
            _text(row.get("fail_closed_blockers")),
        ]
    ).lower()
    return any(marker in text for marker in ("conflict", "defer", "activity_proxy_conflicts"))


def _evidence_mode(row: dict[str, Any]) -> str:
    label = _text(row.get("current_label"))
    request_mode = _text(row.get("request_mode"))
    if "binder" == label:
        return "exact_human_nr1i2_pxr_quantitative_binder_value_required"
    if "conflict" in request_mode:
        return "exact_human_nr1i2_pxr_conflict_resolution_or_negative_value_required"
    return "exact_human_nr1i2_pxr_negative_or_inactive_quantitative_value_required"


def _stable_review_id(prefix: str, row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, str]:
    payload = {field: _text(row.get(field)) for field in fields}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}", digest


def _template_row(row: dict[str, Any]) -> dict[str, Any]:
    conflict_required = _requires_conflict_decision(row)
    review_row_id, source_fingerprint = _stable_review_id(
        "pxr_review",
        row,
        (
            "rank",
            "packet_step",
            "candidate_name",
            "current_label",
            "review_bucket",
            "request_mode",
            "readiness_missing_fields",
            "workbook_replacement_ligand_id",
            "fail_closed_blockers",
        ),
    )
    return {
        "review_row_id": review_row_id,
        "source_row_fingerprint": source_fingerprint,
        "rank": _text(row.get("rank")),
        "packet_step": _text(row.get("packet_step")),
        "candidate_name": _text(row.get("candidate_name")),
        "current_label": _text(row.get("current_label")),
        "review_bucket": _text(row.get("review_bucket")),
        "request_mode": _text(row.get("request_mode")),
        "readiness_missing_fields": _text(row.get("readiness_missing_fields")),
        "workbook_replacement_ligand_id": _text(row.get("workbook_replacement_ligand_id")),
        "fail_closed_blockers": _text(row.get("fail_closed_blockers")),
        "required_evidence_mode": _evidence_mode(row),
        "target_species": "human",
        "target_gene": "NR1I2",
        "target_alias": "PXR",
        "target_match_confirmed": TRUE_FALSE_PLACEHOLDER,
        "replacement_reference_binding_kcal_mol": KCAL_PLACEHOLDER,
        "replacement_source_url_or_doi": SOURCE_PLACEHOLDER,
        "assay_type_and_endpoint": ASSAY_PLACEHOLDER,
        "assay_is_direct_or_claim_safe": TRUE_FALSE_PLACEHOLDER,
        "conflict_resolution_decision": DECISION_PLACEHOLDER if conflict_required else "",
        "review_decision": REVIEW_DECISION_PLACEHOLDER,
        "authoritative_apply_requested": TRUE_FALSE_PLACEHOLDER,
        "reviewer_notes": "",
        "conflict_resolution_required": conflict_required,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
    }


def _next_review_completion_packet(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = next((dict(item) for item in rows if item.get("scope_promotion_allowed") is False), {})
    if not row:
        return {
            "packet_ready": False,
            "review_row_id": "",
            "operator_review_artifact": "",
            "validation_commands": [],
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    required_columns = [
        "review_row_id",
        "target_gene",
        "target_species",
        "candidate_name",
        "replacement_reference_binding_kcal_mol",
        "replacement_source_url_or_doi",
        "assay_type_and_endpoint",
        "assay_is_direct_or_claim_safe",
        "target_match_confirmed",
        "review_decision",
        "authoritative_apply_requested",
    ]
    if row.get("conflict_resolution_required") is True:
        required_columns.append("conflict_resolution_decision")
    return {
        "packet_ready": True,
        "review_row_id": _text(row.get("review_row_id")),
        "source_row_fingerprint": _text(row.get("source_row_fingerprint")),
        "packet_step": _text(row.get("packet_step")),
        "candidate_name": _text(row.get("candidate_name")),
        "workbook_replacement_ligand_id": _text(row.get("workbook_replacement_ligand_id")),
        "current_label": _text(row.get("current_label")),
        "target_gene": _text(row.get("target_gene")),
        "target_alias": _text(row.get("target_alias")),
        "target_species": _text(row.get("target_species")),
        "request_mode": _text(row.get("request_mode")),
        "required_evidence_mode": _text(row.get("required_evidence_mode")),
        "readiness_missing_fields": _text(row.get("readiness_missing_fields")),
        "fail_closed_blockers": _text(row.get("fail_closed_blockers")),
        "conflict_resolution_required": bool(row.get("conflict_resolution_required") is True),
        "required_operator_intake_columns": required_columns,
        "required_exact_evidence_fields": list(required_columns),
        "required_claim_guardrails": list(PXR_REQUIRED_CLAIM_GUARDRAILS),
        "required_claim_guardrail_count": len(PXR_REQUIRED_CLAIM_GUARDRAILS),
        "return_bundle_required_artifacts": list(NEXT_REVIEW_RETURN_ARTIFACTS),
        "return_bundle_required_artifact_count": len(NEXT_REVIEW_RETURN_ARTIFACTS),
        "placeholder_fields": [
            field
            for field in (
                "target_match_confirmed",
                "replacement_reference_binding_kcal_mol",
                "replacement_source_url_or_doi",
                "assay_type_and_endpoint",
                "assay_is_direct_or_claim_safe",
                "conflict_resolution_decision",
                "review_decision",
                "authoritative_apply_requested",
            )
            if str(row.get(field, "")).startswith("OPERATOR_FILL")
        ],
        "operator_review_artifact": DEFAULT_OUT_CSV.as_posix(),
        "completion_rule": (
            "Provide exact human NR1I2/PXR quantitative kcal/source evidence, confirm target match and assay type, "
            "resolve any activity-proxy conflict or keep the row deferred, and request authoritative apply only when "
            "the row is direct or claim-safe for the stated PXR label."
        ),
        "validation_commands": [
            "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
            "python3 tools/build_pxr_blocked_row_promotion_gate.py",
            "python3 tools/build_pxr_authoritative_reconciliation_packet.py",
            "python3 tools/build_product_scope_breadth_contract.py",
            "python3 tools/build_product_goal_completion_audit.py",
        ],
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _return_bundle_completion_matrix(next_packet: dict[str, Any]) -> list[dict[str, Any]]:
    if not next_packet.get("packet_ready"):
        return []
    review_row_id = _text(next_packet.get("review_row_id"))
    placeholder_fields = [str(item) for item in (next_packet.get("placeholder_fields") or [])]
    has_placeholder_fields = bool(placeholder_fields)
    artifact_rows = [
        (
            "operator_review_row",
            DEFAULT_OUT_CSV.as_posix(),
            [
                "target_match_confirmed",
                "replacement_reference_binding_kcal_mol",
                "replacement_source_url_or_doi",
                "assay_type_and_endpoint",
                "assay_is_direct_or_claim_safe",
                "review_decision",
                "authoritative_apply_requested",
            ],
            "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
            "Fill the next PXR exact-review row with human NR1I2/PXR quantitative evidence, source, assay, target match, and an explicit decision.",
        ),
        (
            "pxr_fill_readiness",
            DEFAULT_FILL_READINESS_JSON.as_posix(),
            [
                "replacement_reference_binding_kcal_mol",
                "replacement_source_url_or_doi",
                "assay_type_and_endpoint",
                "target_match_confirmed",
                "review_decision",
            ],
            "python3 tools/validate_pxr_packet_fill_readiness.py",
            "Validate PXR packet-fill readiness after the exact-review row is completed and workbook rows are synchronized.",
        ),
        (
            "pxr_blocked_row_promotion_gate",
            DEFAULT_BLOCKED_GATE_JSON.as_posix(),
            ["blocked_row_count", "conflict_resolution_decision", "authoritative_apply_allowed"],
            "python3 tools/build_pxr_blocked_row_promotion_gate.py",
            "Rerun the blocked-row promotion gate and confirm no unresolved PXR exact-evidence blockers remain.",
        ),
        (
            "pxr_authoritative_reconciliation",
            DEFAULT_RECONCILIATION_JSON.as_posix(),
            ["reconciliation_packet_ready", "reconciled_blocked_row_count", "authoritative_apply_allowed_count"],
            "python3 tools/build_pxr_authoritative_reconciliation_packet.py",
            "Reconcile the completed review evidence with the authoritative PXR packet before any scope claim changes.",
        ),
        (
            "scope_breadth_contract",
            DEFAULT_SCOPE_BREADTH_JSON.as_posix(),
            ["pxr_exact_review_rows_filled", "pxr_blocked_rows_zero", "pxr_authoritative_apply_allowed"],
            "python3 tools/build_product_scope_breadth_contract.py",
            "Rerun the scope breadth contract and keep PXR promotion blocked unless every PXR acceptance check is green.",
        ),
    ]
    matrix: list[dict[str, Any]] = []
    for artifact_id, artifact_path, required_fields, validation_command, next_action in artifact_rows:
        failed_check_ids = []
        if has_placeholder_fields:
            failed_check_ids.append("next_review_placeholder_fields")
        failed_check_ids.append(f"{artifact_id}_not_operator_verified")
        matrix.append(
            {
                "artifact_id": artifact_id,
                "status": "blocked",
                "artifact_path": artifact_path,
                "review_row_id": review_row_id,
                "required_fields_or_columns": required_fields,
                "failed_check_ids": failed_check_ids,
                "failed_check_count": len(failed_check_ids),
                "placeholder_fields": placeholder_fields,
                "validation_command": validation_command,
                "next_action": next_action,
                "release_blocker": True,
                "execution_enabled": False,
                "scope_widened": False,
                "external_state_mutated": False,
            }
        )
    return matrix


def build_payload(
    *,
    reconciliation_packet: dict[str, Any],
    reconciliation_path: str = DEFAULT_RECONCILIATION_JSON.as_posix(),
) -> dict[str, Any]:
    reconciliation = _summary(reconciliation_packet)
    source_rows = [
        row
        for row in _rows(reconciliation_packet)
        if not _bool(row.get("gate_authoritative_apply_allowed"))
    ]
    rows = [_template_row(row) for row in source_rows]
    expected_rows = _int(reconciliation.get("reconciled_blocked_row_count")) or _int(
        reconciliation.get("gate_blocked_row_count")
    )
    row_count_matches_reconciliation = bool(expected_rows == 0 or len(rows) == expected_rows)
    conflict_rows = [row for row in rows if row["conflict_resolution_required"]]
    binder_rows = [row for row in rows if row["current_label"] == "binder"]
    non_binder_rows = [row for row in rows if row["current_label"] == "non_binder"]
    unique_review_row_ids = {row["review_row_id"] for row in rows}
    unique_review_row_ids_ready = bool(len(unique_review_row_ids) == len(rows))
    no_blocked_rows_complete = bool(
        _bool(reconciliation.get("reconciliation_packet_ready"))
        and _bool(reconciliation.get("authoritative_promotion_allowed"))
        and expected_rows == 0
        and not rows
    )
    ready = bool(
        _bool(reconciliation.get("reconciliation_packet_ready"))
        and (rows or no_blocked_rows_complete)
        and row_count_matches_reconciliation
        and unique_review_row_ids_ready
        and (
            _int(reconciliation.get("authoritative_apply_allowed_count")) == 0
            or no_blocked_rows_complete
        )
    )
    blockers: list[str] = []
    if not _bool(reconciliation.get("reconciliation_packet_ready")):
        blockers.append("reconciliation_packet_ready")
    if not rows and not no_blocked_rows_complete:
        blockers.append("blocked_review_rows")
    if not row_count_matches_reconciliation:
        blockers.append("review_row_count_matches_reconciliation")
    if rows and not unique_review_row_ids_ready:
        blockers.append("unique_review_row_ids")
    next_review_completion = _next_review_completion_packet(rows)
    next_review_return_bundle_matrix = _return_bundle_completion_matrix(next_review_completion)
    next_review_return_bundle_blockers = [
        row for row in next_review_return_bundle_matrix if _text(row.get("status")) != "ready"
    ]
    next_review_return_bundle_first_blocker = (
        next_review_return_bundle_blockers[0] if next_review_return_bundle_blockers else {}
    )
    summary = {
        "packet_type": "pxr_exact_evidence_review_intake_template",
        "status": "pxr_exact_evidence_review_intake_template_ready" if ready else "blocked_pxr_exact_evidence_review_intake_template",
        "pxr_exact_review_intake_ready": ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "reconciliation_artifact": reconciliation_path,
        "reconciliation_packet_ready": _bool(reconciliation.get("reconciliation_packet_ready")),
        "expected_blocked_row_count": expected_rows,
        "review_template_row_count": len(rows),
        "review_row_count_matches_reconciliation": row_count_matches_reconciliation,
        "unique_review_row_id_count": len(unique_review_row_ids),
        "unique_review_row_ids_ready": unique_review_row_ids_ready,
        "binder_review_row_count": len(binder_rows),
        "non_binder_review_row_count": len(non_binder_rows),
        "conflict_resolution_required_count": len(conflict_rows),
        "kcal_placeholder_count": sum(1 for row in rows if row["replacement_reference_binding_kcal_mol"] == KCAL_PLACEHOLDER),
        "source_placeholder_count": sum(1 for row in rows if row["replacement_source_url_or_doi"] == SOURCE_PLACEHOLDER),
        "target_match_placeholder_count": sum(1 for row in rows if row["target_match_confirmed"] == TRUE_FALSE_PLACEHOLDER),
        "review_decision_placeholder_count": sum(1 for row in rows if row["review_decision"] == REVIEW_DECISION_PLACEHOLDER),
        "next_review_completion_packet_ready": next_review_completion["packet_ready"],
        "next_review_completion_packet": next_review_completion,
        "next_review_return_bundle_required_artifacts": list(NEXT_REVIEW_RETURN_ARTIFACTS),
        "next_review_return_bundle_required_artifact_count": len(NEXT_REVIEW_RETURN_ARTIFACTS),
        "next_review_return_bundle_completion_matrix": next_review_return_bundle_matrix,
        "next_review_return_bundle_completion_matrix_count": len(next_review_return_bundle_matrix),
        "next_review_return_bundle_blocker_count": len(next_review_return_bundle_blockers),
        "next_review_return_bundle_next_artifact_id": _text(
            next_review_return_bundle_first_blocker.get("artifact_id")
        ),
        "next_review_return_bundle_next_artifact_path": _text(
            next_review_return_bundle_first_blocker.get("artifact_path")
        ),
        "next_review_return_bundle_next_artifact_failed_check_ids": [
            str(item)
            for item in (next_review_return_bundle_first_blocker.get("failed_check_ids") or [])
        ],
        "next_review_row_id": _text(next_review_completion.get("review_row_id")),
        "next_review_candidate_name": _text(next_review_completion.get("candidate_name")),
        "next_review_packet_step": _text(next_review_completion.get("packet_step")),
        "next_review_required_evidence_mode": _text(next_review_completion.get("required_evidence_mode")),
        "next_review_operator_review_artifact": _text(next_review_completion.get("operator_review_artifact")),
        "authoritative_apply_allowed": no_blocked_rows_complete,
        "scope_promotion_allowed": no_blocked_rows_complete,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No PXR exact-review placeholders remain; rerun source-modality and product scope gates."
            if no_blocked_rows_complete
            else (
            "Complete exact human NR1I2/PXR kcal/source/assay/target-match review rows, then rerun PXR fill-readiness, "
            "blocked-row promotion, authoritative reconciliation, and scope breadth gates."
            if ready
            else "Regenerate PXR authoritative reconciliation before exact evidence review intake."
            )
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "next_review_completion_packet": next_review_completion,
        "next_review_return_bundle_completion_matrix": next_review_return_bundle_matrix,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# PXR Exact Evidence Review Intake Template",
        "",
        f"- status: `{s['status']}`",
        f"- pxr_exact_review_intake_ready: `{s['pxr_exact_review_intake_ready']}`",
        f"- review_template_row_count: `{s['review_template_row_count']}`",
        f"- unique_review_row_ids_ready: `{s['unique_review_row_ids_ready']}`",
        f"- binder_review_row_count: `{s['binder_review_row_count']}`",
        f"- non_binder_review_row_count: `{s['non_binder_review_row_count']}`",
        f"- conflict_resolution_required_count: `{s['conflict_resolution_required_count']}`",
        f"- kcal_placeholder_count: `{s['kcal_placeholder_count']}`",
        f"- next_review_completion_packet_ready: `{s['next_review_completion_packet_ready']}`",
        f"- next_review_return_bundle_required_artifact_count: `{s['next_review_return_bundle_required_artifact_count']}`",
        f"- next_review_return_bundle_blocker_count: `{s['next_review_return_bundle_blocker_count']}`",
        f"- next_review_return_bundle_next_artifact_id: `{s['next_review_return_bundle_next_artifact_id']}`",
        f"- next_review_return_bundle_next_artifact_path: `{s['next_review_return_bundle_next_artifact_path']}`",
        f"- next_review_row_id: `{s['next_review_row_id']}`",
        f"- next_review_candidate_name: `{s['next_review_candidate_name']}`",
        f"- next_review_operator_review_artifact: `{s['next_review_operator_review_artifact']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        "",
        "## Review Rows",
        "",
        "| row id | rank | step | candidate | label | mode | conflict | decision |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_row_id']}` | {row['rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['current_label']}` | "
            f"`{row['required_evidence_mode']}` | `{row['conflict_resolution_required']}` | `{row['review_decision']}` |"
        )
    lines.extend([
        "",
        "## Next Review Return Bundle",
        "",
        "| artifact | status | failed checks | validation command | next action |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in payload.get("next_review_return_bundle_completion_matrix", []):
        lines.append(
            f"| `{row['artifact_id']}` | `{row['status']}` | "
            f"`{','.join(str(item) for item in row['failed_check_ids'])}` | "
            f"`{row['validation_command']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR exact evidence review intake template.")
    parser.add_argument("--reconciliation-json", default=str(DEFAULT_RECONCILIATION_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        reconciliation_packet=_read_json(args.reconciliation_json),
        reconciliation_path=args.reconciliation_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
