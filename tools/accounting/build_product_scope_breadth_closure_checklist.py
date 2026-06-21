#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_TRANSPORTER_WORKBOOK_JSON = RUNS / "transporter_slot_assignment_candidate_workbook_current.json"
DEFAULT_TRANSPORTER_MANUAL_REVIEW_JSON = RUNS / "transporter_manual_review_intake_template_current.json"
DEFAULT_PXR_RECONCILIATION_JSON = RUNS / "pxr_authoritative_reconciliation_packet_current.json"
DEFAULT_PXR_EXACT_REVIEW_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_GENERAL_BLOCKER_JSON = RUNS / "general_protein_ligand_claim_blocker_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "product_scope_breadth_closure_checklist_current.json"
DEFAULT_OUT_CSV = RUNS / "product_scope_breadth_closure_checklist_current.csv"
DEFAULT_OUT_MD = RUNS / "product_scope_breadth_closure_checklist_current.md"

CLAIM_BOUNDARY = (
    "Product scope breadth closure checklist only; consolidates transporter slot-assignment, PXR reconciliation, "
    "and general product-claim blockers into ordered close conditions. It does not acquire evidence, write config "
    "CSVs, authoritatively apply rows, widen API scope, set platform flags, run docking, promote claims, upload, "
    "submit, email, delete, or mutate external state."
)

TRANSPORTER_SCOPE_CLOSURE_VERIFICATION_COMMAND = " && ".join(
    [
        "python3 tools/build_transporter_local_crosscheck_triage_packet.py",
        "python3 tools/build_transporter_slot_assignment_candidate_workbook.py",
        "python3 tools/build_transporter_manual_review_intake_template.py",
        "python3 tools/product/build_transporter_blocker_capture_sheet.py",
        "python3 tools/build_transporter_binder_promotion_gate.py",
        "python3 tools/product/build_transporter_donor_policy_reopen_checklist.py",
        "python3 tools/build_transporter_p0_closure_packet.py",
        "python3 tools/build_transporter_p0_evidence_acquisition_packet.py",
        "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py",
        "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
        "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
        "python3 tools/build_product_scope_breadth_contract.py",
        "python3 tools/build_general_protein_ligand_claim_blocker_packet.py",
        "python3 tools/build_product_scope_breadth_work_order.py",
        "python3 tools/build_product_scope_breadth_closure_checklist.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
    ]
)

PXR_SCOPE_CLOSURE_VERIFICATION_COMMAND = " && ".join(
    [
        "python3 tools/validate_pxr_packet_fill_readiness.py",
        "python3 tools/build_pxr_blocked_evidence_request_packet.py",
        "python3 tools/build_pxr_blocked_row_promotion_gate.py",
        "python3 tools/build_pxr_authoritative_reconciliation_packet.py",
        "python3 tools/product/build_pxr_unresolved_evidence_capture_intake.py",
        "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
        "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py",
        "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
        "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
        "python3 tools/build_product_scope_breadth_contract.py",
        "python3 tools/build_general_protein_ligand_claim_blocker_packet.py",
        "python3 tools/build_product_scope_breadth_work_order.py",
        "python3 tools/build_product_scope_breadth_closure_checklist.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
    ]
)

GENERAL_SCOPE_CLOSURE_VERIFICATION_COMMAND = " && ".join(
    [
        "python3 tools/build_product_capability_surface_contract.py",
        "python3 tools/build_product_scope_breadth_contract.py",
        "python3 tools/build_general_protein_ligand_claim_blocker_packet.py",
        "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
        "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
        "python3 tools/build_product_scope_breadth_work_order.py",
        "python3 tools/build_product_scope_breadth_closure_checklist.py",
        "python3 tools/build_product_ai_architecture_execution_backlog.py",
        "python3 tools/build_product_ai_architecture_gap_closure.py",
    ]
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


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _transporter_close_action(row: dict[str, Any]) -> str:
    blockers = _text(row.get("manual_review_blockers"))
    missing = _text(row.get("required_missing_fields"))
    if "negative_quantitative_value_required" in blockers:
        return "Acquire exact quantitative negative value or keep inactive/nonquantitative row out of authoritative apply."
    if "review_only_or_functional_surrogate" in blockers:
        return "Keep review-only/functional surrogate blocked unless exact direct-binding evidence is curated."
    if missing:
        return "Fill missing replacement fields, then rerun transporter P0 closure and donor-policy gates."
    return "Manual reviewer must confirm ligand identity, scaffold, source, and split/meta synchronization before any apply."


def _transporter_blocker_class(row: dict[str, Any]) -> str:
    blockers = _text(row.get("manual_review_blockers"))
    missing = _text(row.get("required_missing_fields"))
    state = _text(row.get("candidate_mode"))
    if "negative_quantitative_value_required" in blockers:
        return "exact_negative_quantitative_value_missing"
    if "review_only_or_functional_surrogate" in blockers:
        return "direct_binding_evidence_missing"
    if "direct_quantitative_replacement_candidate" in state and "manual_ligand_identity" in blockers:
        return "manual_identity_scaffold_confirmation_required"
    if missing:
        return "required_replacement_fields_missing"
    return "manual_scientific_review_required"


def _transporter_claim_impact(row: dict[str, Any]) -> str:
    item_id = _text(row.get("item_id"))
    if "non_binder" in item_id:
        return "blocks transporter negative-control coverage and transporter domain promotion"
    return "blocks transporter binder coverage and transporter domain promotion"


def _transporter_acceptance(row: dict[str, Any]) -> str:
    if _text(row.get("slot_triage_bucket")) == "functional_quantitative_only_direct_gap_open":
        return "Exact direct-binding/kcal evidence replaces functional-surrogate-only blocker, with claim-safe source provenance."
    if "non_binder" in _text(row.get("packet_step")):
        return "Negative row has ligand/source/SMILES/scaffold plus exact quantitative inactive or non-binder value acceptable to transporter gates."
    return "Binder row has confirmed ligand identity, source provenance, scaffold, kcal, and synchronized reference/split/meta rows."


def _transporter_manual_review_subchecks(row: dict[str, Any]) -> str:
    blockers = _text(row.get("manual_review_blockers"))
    packet_step = _text(row.get("packet_step"))
    subchecks: list[str] = []
    if "review_only_or_functional_surrogate" in blockers:
        subchecks.append("direct_binding_or_claim_safe_kcal_confirmed=false")
    if "negative_quantitative_value_required" in blockers or "non_binder" in packet_step:
        subchecks.append("negative_quantitative_value_confirmed=false")
    if "manual_ligand_identity_and_scaffold_confirmation_required" in blockers:
        subchecks.extend(
            [
                "ligand_identity_confirmed=false",
                "source_provenance_confirmed=false",
                "scaffold_reviewed=false",
                "split_meta_synchronization_confirmed=false",
            ]
        )
    return ";".join(subchecks)


def _count_subchecks(value: str) -> int:
    return len([item for item in value.split(";") if item]) if value else 0


def _pxr_close_action(row: dict[str, Any]) -> str:
    mode = _text(row.get("request_mode"))
    if "binder" in mode:
        return "Acquire exact human NR1I2/PXR quantitative binder evidence and rerun PXR reconciliation."
    if "conflict_resolution" in mode:
        return "Resolve human PXR conflict with exact target-specific quantitative evidence or keep deferred."
    return "Acquire exact human NR1I2/PXR negative or inactive quantitative evidence and rerun fill-readiness."


def _pxr_blocker_class(row: dict[str, Any]) -> str:
    blockers = _text(row.get("fail_closed_blockers"))
    missing = _text(row.get("readiness_missing_fields"))
    mode = _text(row.get("request_mode"))
    if "review_only" in blockers or "review_only" in mode:
        return "review_only_not_authoritative"
    if "conflict" in blockers or "conflict" in mode:
        return "exact_human_pxr_conflict_resolution_required"
    if "replacement_reference_binding_kcal_mol" in missing or "quantitative" in blockers:
        return "exact_human_pxr_quantitative_value_missing"
    return "exact_human_pxr_authoritative_reconciliation_required"


def _pxr_claim_impact(row: dict[str, Any]) -> str:
    mode = _text(row.get("request_mode"))
    if "non_binder" in mode or "negative" in mode or "inactive" in mode:
        return "blocks PXR negative-control coverage and PXR domain promotion"
    if "conflict" in mode:
        return "blocks PXR conflict-safe claim wording and PXR domain promotion"
    return "blocks PXR binder coverage and PXR domain promotion"


def _general_close_action(row: dict[str, Any]) -> str:
    check_id = _text(row.get("check_id"))
    if check_id.startswith("domain_ready."):
        return "Wait for referenced scientific domain gate to become ready; do not satisfy by wording change."
    if check_id == "allowed_scope_family_count":
        return "Widen allowed scope families only after transporter and PXR evidence gates are green."
    if check_id == "explicit_general_platform_flag":
        return "Set explicit general platform flag only after evidence gates and API scope widening are complete."
    return _text(row.get("next_action"))


def _general_blocker_class(row: dict[str, Any]) -> str:
    check_id = _text(row.get("check_id"))
    if check_id.startswith("domain_ready."):
        return "scientific_domain_gate_not_ready"
    if check_id == "allowed_scope_family_count":
        return "allowed_scope_family_count_too_narrow"
    if check_id == "explicit_general_platform_flag":
        return "explicit_general_platform_flag_missing"
    return "product_claim_gate_not_ready"


def _general_claim_impact(row: dict[str, Any]) -> str:
    check_id = _text(row.get("check_id"))
    if check_id.startswith("domain_ready."):
        return f"blocks general protein-ligand wording until {check_id.removeprefix('domain_ready.')} scope is ready"
    if check_id == "allowed_scope_family_count":
        return "blocks API/product surface widening beyond restricted family list"
    if check_id == "explicit_general_platform_flag":
        return "blocks explicit broad platform claim even after evidence gates are green"
    return "blocks general protein-ligand commercial claim wording"


def _add_blocker_context(row: dict[str, Any], *, blocker_class: str, claim_impact: str) -> dict[str, Any]:
    row["blocker_class"] = blocker_class
    row["customer_claim_impact"] = claim_impact
    row["evidence_gate"] = "fail_closed_until_authoritative_evidence"
    return row


def _list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _claim_boundary_matrix(
    *,
    allowed_scope_families: list[str],
    missing_domains: list[str],
    transporter_direct_binding_missing_count: int,
    transporter_negative_quantitative_missing_count: int,
    pxr_reconciled_blocked_row_count: int,
    general_claim_gate_blocker_count: int,
) -> list[dict[str, Any]]:
    allowed_text = ",".join(allowed_scope_families) if allowed_scope_families else "none"
    missing_text = ",".join(missing_domains) if missing_domains else "none"
    pxr_claim_blocked = pxr_reconciled_blocked_row_count > 0
    return [
        {
            "claim_scope": "current_restricted_delivery_scope",
            "claim_status": "allowed" if allowed_scope_families else "blocked",
            "allowed_wording": f"restricted protein-ligand docking support for {allowed_text}",
            "blocked_wording": "general protein-ligand platform; blocked scientific-domain promotions unless separately ready",
            "required_evidence_to_expand": (
                "transporter scope gate green, any blocked PXR rows resolved, "
                "allowed scope families widened, explicit platform flag true"
            ),
        },
        {
            "claim_scope": "transporter_domain_promotion",
            "claim_status": "blocked",
            "allowed_wording": "manual-review evidence triage only",
            "blocked_wording": "delivery-ready transporter binder/non-binder coverage",
            "required_evidence_to_expand": (
                "direct_binding_missing=0;negative_quantitative_missing=0;"
                f"current_direct_binding_missing={transporter_direct_binding_missing_count};"
                f"current_negative_quantitative_missing={transporter_negative_quantitative_missing_count}"
            ),
        },
        {
            "claim_scope": "pxr_domain_promotion",
            "claim_status": "blocked" if pxr_claim_blocked else "allowed",
            "allowed_wording": (
                "PXR domain evidence-ready pending product decision"
                if not pxr_claim_blocked
                else "exact-evidence intake/reconciliation only"
            ),
            "blocked_wording": "delivery-ready PXR binder/non-binder/conflict-safe coverage",
            "required_evidence_to_expand": (
                f"pxr_reconciled_blocked_rows=0;current_pxr_reconciled_blocked_rows={pxr_reconciled_blocked_row_count}"
            ),
        },
        {
            "claim_scope": "general_protein_ligand_platform",
            "claim_status": "blocked",
            "allowed_wording": f"do not exceed current restricted families: {allowed_text}",
            "blocked_wording": "broad/general protein-ligand platform wording",
            "required_evidence_to_expand": (
                f"missing_domains={missing_text};general_claim_gate_blockers={general_claim_gate_blocker_count}"
            ),
        },
    ]


def build_payload(
    *,
    transporter_workbook_payload: dict[str, Any],
    pxr_reconciliation_payload: dict[str, Any],
    general_blocker_payload: dict[str, Any],
    transporter_path: str = DEFAULT_TRANSPORTER_WORKBOOK_JSON.as_posix(),
    transporter_manual_review_path: str = DEFAULT_TRANSPORTER_MANUAL_REVIEW_JSON.as_posix(),
    pxr_path: str = DEFAULT_PXR_RECONCILIATION_JSON.as_posix(),
    pxr_exact_review_path: str = DEFAULT_PXR_EXACT_REVIEW_JSON.as_posix(),
    general_path: str = DEFAULT_GENERAL_BLOCKER_JSON.as_posix(),
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    priority = 1

    for row in _rows(transporter_workbook_payload):
        manual_review_subchecks = _transporter_manual_review_subchecks(row)
        rows.append(
            _add_blocker_context(
                {
                    "priority": priority,
                    "domain": "transporter",
                    "item_id": _text(row.get("item_id")),
                    "closure_lane": "scientific_slot_assignment",
                    "current_state": _text(row.get("candidate_mode")),
                    "missing_fields": _text(row.get("required_missing_fields")),
                    "manual_review_blockers": _text(row.get("manual_review_blockers")),
                    "manual_review_subchecks": manual_review_subchecks,
                    "manual_review_subcheck_count": _count_subchecks(manual_review_subchecks),
                    "candidate_ligand_id": _text(row.get("replacement_ligand_id")),
                    "candidate_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
                    "candidate_source": _text(row.get("replacement_source")),
                    "candidate_scaffold": _text(row.get("replacement_scaffold")),
                    "candidate_activity_signal": (
                        f"{_text(row.get('candidate_activity_type'))}="
                        f"{_text(row.get('candidate_activity_value'))}"
                        f"{_text(row.get('candidate_activity_units'))}"
                    ).strip("="),
                    "acceptance_criteria": _transporter_acceptance(row),
                    "close_action": _transporter_close_action(row),
                    "verification_command": TRANSPORTER_SCOPE_CLOSURE_VERIFICATION_COMMAND,
                    "source_artifact": f"{transporter_path};{transporter_manual_review_path}",
                    "ready_for_apply": _bool(row.get("candidate_ready_for_apply")),
                    "authoritative_apply_allowed": False,
                    "scope_promotion_allowed": False,
                    "external_state_mutated": False,
                },
                blocker_class=_transporter_blocker_class(row),
                claim_impact=_transporter_claim_impact(row),
            )
        )
        priority += 1

    for row in _rows(pxr_reconciliation_payload):
        rows.append(
            _add_blocker_context(
                {
                    "priority": priority,
                    "domain": "pxr",
                    "item_id": _text(row.get("packet_step")),
                    "closure_lane": "exact_human_pxr_quantitative_evidence",
                    "current_state": _text(row.get("reconciliation_status")),
                    "missing_fields": _text(row.get("readiness_missing_fields")),
                    "manual_review_blockers": _text(row.get("fail_closed_blockers")),
                    "acceptance_criteria": "Exact human NR1I2/PXR quantitative evidence clears fill-readiness, claim-safe quantitative, and authoritative reconciliation gates.",
                    "close_action": _pxr_close_action(row),
                    "verification_command": PXR_SCOPE_CLOSURE_VERIFICATION_COMMAND,
                    "source_artifact": f"{pxr_path};{pxr_exact_review_path}",
                    "ready_for_apply": _bool(row.get("readiness_ready_for_apply")),
                    "authoritative_apply_allowed": False,
                    "scope_promotion_allowed": False,
                    "external_state_mutated": False,
                },
                blocker_class=_pxr_blocker_class(row),
                claim_impact=_pxr_claim_impact(row),
            )
        )
        priority += 1

    for row in _rows(general_blocker_payload):
        if row.get("release_blocker") is not True:
            continue
        rows.append(
            _add_blocker_context(
                {
                    "priority": priority,
                    "domain": "general_protein_ligand",
                    "item_id": _text(row.get("check_id")),
                    "closure_lane": _text(row.get("check_type")) or "product_claim_gate",
                    "current_state": f"current={_text(row.get('current_value'))};required={_text(row.get('required_value'))}",
                    "missing_fields": "",
                    "manual_review_blockers": "claim_gate_waits_on_scientific_scope",
                    "acceptance_criteria": _text(row.get("required_value")),
                    "close_action": _general_close_action(row),
                    "verification_command": GENERAL_SCOPE_CLOSURE_VERIFICATION_COMMAND,
                    "source_artifact": general_path,
                    "ready_for_apply": False,
                    "authoritative_apply_allowed": False,
                    "scope_promotion_allowed": False,
                    "external_state_mutated": False,
                },
                blocker_class=_general_blocker_class(row),
                claim_impact=_general_claim_impact(row),
            )
        )
        priority += 1

    transporter_s = _summary(transporter_workbook_payload)
    pxr_s = _summary(pxr_reconciliation_payload)
    general_s = _summary(general_blocker_payload)
    field_missing_rows = [row for row in rows if row["missing_fields"]]
    manual_review_rows = [row for row in rows if row["manual_review_blockers"]]
    manual_review_subcheck_count = sum(_int(row.get("manual_review_subcheck_count")) for row in rows)
    blocker_classes = sorted({row["blocker_class"] for row in rows})
    blocker_class_counts = {
        blocker_class: sum(1 for row in rows if row["blocker_class"] == blocker_class)
        for blocker_class in blocker_classes
    }
    allowed_scope_families = _list(general_s.get("allowed_scope_families"))
    missing_domains = _list(general_s.get("missing_domains"))
    transporter_direct_binding_missing_count = blocker_class_counts.get("direct_binding_evidence_missing", 0)
    transporter_negative_quantitative_missing_count = blocker_class_counts.get("exact_negative_quantitative_value_missing", 0)
    pxr_reconciled_blocked_row_count = _int(pxr_s.get("reconciled_blocked_row_count"))
    general_claim_gate_blocker_count = sum(1 for row in rows if row["domain"] == "general_protein_ligand")
    claim_boundary_matrix = _claim_boundary_matrix(
        allowed_scope_families=allowed_scope_families,
        missing_domains=missing_domains,
        transporter_direct_binding_missing_count=transporter_direct_binding_missing_count,
        transporter_negative_quantitative_missing_count=transporter_negative_quantitative_missing_count,
        pxr_reconciled_blocked_row_count=pxr_reconciled_blocked_row_count,
        general_claim_gate_blocker_count=general_claim_gate_blocker_count,
    )
    blocked_claim_scopes = [
        row["claim_scope"] for row in claim_boundary_matrix if row["claim_status"] == "blocked"
    ]
    summary = {
        "packet_type": "product_scope_breadth_closure_checklist",
        "status": "product_scope_breadth_closure_checklist_ready",
        "closure_checklist_ready": True,
        "scope_breadth_ready": False,
        "checklist_row_count": len(rows),
        "transporter_row_count": _int(transporter_s.get("candidate_row_count")),
        "transporter_candidate_ready_for_apply_count": _int(transporter_s.get("candidate_ready_for_apply_count")),
        "transporter_negative_value_review_required_count": _int(transporter_s.get("negative_value_review_required_count")),
        "pxr_reconciled_blocked_row_count": pxr_reconciled_blocked_row_count,
        "pxr_claim_safe_quantitative_ready_count": _int(pxr_s.get("claim_safe_quantitative_ready_count")),
        "general_claim_blocker_count": _int(general_s.get("blocker_count")),
        "field_missing_row_count": len(field_missing_rows),
        "manual_review_blocked_row_count": len(manual_review_rows),
        "manual_review_subcheck_count": manual_review_subcheck_count,
        "transporter_manual_review_subcheck_count": sum(
            _int(row.get("manual_review_subcheck_count")) for row in rows if row["domain"] == "transporter"
        ),
        "transporter_identity_scaffold_confirmation_required_count": sum(
            1
            for row in rows
            if row["domain"] == "transporter"
            and "ligand_identity_confirmed=false" in _text(row.get("manual_review_subchecks"))
        ),
        "transporter_direct_binding_or_kcal_confirmation_required_count": sum(
            1
            for row in rows
            if row["domain"] == "transporter"
            and "direct_binding_or_claim_safe_kcal_confirmed=false" in _text(row.get("manual_review_subchecks"))
        ),
        "transporter_negative_quantitative_confirmation_required_count": sum(
            1
            for row in rows
            if row["domain"] == "transporter"
            and "negative_quantitative_value_confirmed=false" in _text(row.get("manual_review_subchecks"))
        ),
        "ready_for_apply_count": sum(1 for row in rows if row["ready_for_apply"]),
        "blocker_classes": blocker_classes,
        "blocker_class_counts": blocker_class_counts,
        "transporter_direct_binding_missing_count": transporter_direct_binding_missing_count,
        "transporter_negative_quantitative_missing_count": transporter_negative_quantitative_missing_count,
        "pxr_quantitative_missing_count": blocker_class_counts.get("exact_human_pxr_quantitative_value_missing", 0),
        "pxr_conflict_resolution_count": blocker_class_counts.get("exact_human_pxr_conflict_resolution_required", 0),
        "general_claim_gate_blocker_count": general_claim_gate_blocker_count,
        "allowed_scope_families": allowed_scope_families,
        "allowed_scope_family_count": len(allowed_scope_families),
        "claim_blocked_domains": missing_domains,
        "claim_boundary_matrix": claim_boundary_matrix,
        "blocked_claim_scopes": blocked_claim_scopes,
        "blocked_claim_scope_count": len(blocked_claim_scopes),
        "claim_boundary_detail": (
            f"allowed_scope_families={','.join(allowed_scope_families) or 'none'};"
            f"blocked_claim_scopes={','.join(blocked_claim_scopes) or 'none'};"
            f"claim_blocked_domains={','.join(missing_domains) or 'none'};"
            f"general_platform_claim_allowed=False"
        ),
        "first_scientific_blocker": next(
            (
                row["item_id"]
                for row in rows
                if row["domain"] in {"transporter", "pxr"} and not row["ready_for_apply"]
            ),
            "none",
        ),
        "authoritative_apply_allowed_count": 0,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [transporter_path, transporter_manual_review_path, pxr_path, pxr_exact_review_path, general_path],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Close transporter/PXR scientific rows first; revisit general protein-ligand API scope and platform flag only after both scientific domains are ready."
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
        "# Product Scope Breadth Closure Checklist",
        "",
        f"- closure_checklist_ready: `{s['closure_checklist_ready']}`",
        f"- scope_breadth_ready: `{s['scope_breadth_ready']}`",
        f"- checklist_row_count: `{s['checklist_row_count']}`",
        f"- transporter_candidate_ready_for_apply_count: `{s['transporter_candidate_ready_for_apply_count']}`",
        f"- transporter_negative_value_review_required_count: `{s['transporter_negative_value_review_required_count']}`",
        f"- transporter_manual_review_subcheck_count: `{s['transporter_manual_review_subcheck_count']}`",
        f"- transporter_identity_scaffold_confirmation_required_count: `{s['transporter_identity_scaffold_confirmation_required_count']}`",
        f"- transporter_direct_binding_or_kcal_confirmation_required_count: `{s['transporter_direct_binding_or_kcal_confirmation_required_count']}`",
        f"- transporter_negative_quantitative_confirmation_required_count: `{s['transporter_negative_quantitative_confirmation_required_count']}`",
        f"- pxr_reconciled_blocked_row_count: `{s['pxr_reconciled_blocked_row_count']}`",
        f"- general_claim_blocker_count: `{s['general_claim_blocker_count']}`",
        f"- blocker_classes: `{','.join(s['blocker_classes'])}`",
        f"- claim_boundary_detail: `{s['claim_boundary_detail']}`",
        f"- first_scientific_blocker: `{s['first_scientific_blocker']}`",
        f"- ready_for_apply_count: `{s['ready_for_apply_count']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Checklist",
        "",
        "| priority | domain | item | class | claim impact | lane | candidate | missing | blockers | manual subchecks | close action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        candidate = row.get("candidate_ligand_id") or "-"
        lines.append(
            f"| {row['priority']} | `{row['domain']}` | `{row['item_id']}` | `{row['blocker_class']}` | "
            f"{row['customer_claim_impact']} | `{row['closure_lane']}` | "
            f"`{candidate}` | `{row['missing_fields'] or '-'}` | `{row['manual_review_blockers'] or '-'}` | "
            f"`{row.get('manual_review_subchecks') or '-'}` | {row['close_action']} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary Matrix",
            "",
            "| scope | status | allowed wording | blocked wording | required evidence |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in s["claim_boundary_matrix"]:
        lines.append(
            f"| `{row['claim_scope']}` | `{row['claim_status']}` | {row['allowed_wording']} | "
            f"{row['blocked_wording']} | {row['required_evidence_to_expand']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope breadth closure checklist.")
    parser.add_argument("--transporter-workbook-json", default=str(DEFAULT_TRANSPORTER_WORKBOOK_JSON))
    parser.add_argument("--transporter-manual-review-json", default=str(DEFAULT_TRANSPORTER_MANUAL_REVIEW_JSON))
    parser.add_argument("--pxr-reconciliation-json", default=str(DEFAULT_PXR_RECONCILIATION_JSON))
    parser.add_argument("--pxr-exact-review-json", default=str(DEFAULT_PXR_EXACT_REVIEW_JSON))
    parser.add_argument("--general-blocker-json", default=str(DEFAULT_GENERAL_BLOCKER_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        transporter_workbook_payload=_read_json(args.transporter_workbook_json),
        pxr_reconciliation_payload=_read_json(args.pxr_reconciliation_json),
        general_blocker_payload=_read_json(args.general_blocker_json),
        transporter_path=args.transporter_workbook_json,
        transporter_manual_review_path=args.transporter_manual_review_json,
        pxr_path=args.pxr_reconciliation_json,
        pxr_exact_review_path=args.pxr_exact_review_json,
        general_path=args.general_blocker_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
