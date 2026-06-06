#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE_CONTRACT_JSON = "runs/product_scope_breadth_contract_current.json"
DEFAULT_OUT_JSON = "runs/product_scope_breadth_work_order_current.json"
DEFAULT_OUT_CSV = "runs/product_scope_breadth_work_order_current.csv"
DEFAULT_OUT_MD = "runs/product_scope_breadth_work_order_current.md"

DOMAIN_ACTIONS = {
    "transporter": {
        "owner_lane": "scientific_scope",
        "acceptance_criteria": "placeholder_driven_rows=0, p0_open=0, claim_safe_binders>=1, authoritative_binders>=1, and donor_policy_reopen_ready=true",
        "verification_command": "python3 tools/build_transporter_local_crosscheck_triage_packet.py && python3 tools/build_transporter_slot_assignment_candidate_workbook.py && python3 tools/build_transporter_manual_review_intake_template.py && python3 tools/product/build_transporter_blocker_capture_sheet.py && python3 tools/build_transporter_binder_promotion_gate.py && python3 tools/product/build_transporter_donor_policy_reopen_checklist.py && python3 tools/build_transporter_p0_closure_packet.py && python3 tools/build_transporter_p0_evidence_acquisition_packet.py && python3 tools/build_product_scope_breadth_evidence_intake_readiness.py && python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py && python3 tools/build_product_scope_breadth_evidence_priority_packet.py && python3 tools/build_product_scope_breadth_contract.py && python3 tools/build_general_protein_ligand_claim_blocker_packet.py && python3 tools/build_product_scope_breadth_closure_checklist.py && python3 tools/build_product_ai_architecture_execution_backlog.py && python3 tools/build_product_ai_architecture_gap_closure.py",
        "risk": "negative placeholders are closed, but six AQP1/GLUT1 core P0 closure rows, unresolved ligand evidence slots, and donor policy still block transporter delivery scope",
    },
    "pxr": {
        "owner_lane": "scientific_scope",
        "acceptance_criteria": "PXR packet-fill readiness has blocked_row_count=0 and ready_for_apply_row_count equals queue_row_count after unresolved-evidence intake",
        "verification_command": "python3 tools/validate_pxr_packet_fill_readiness.py && python3 tools/build_pxr_blocked_evidence_request_packet.py && python3 tools/build_pxr_blocked_row_promotion_gate.py && python3 tools/build_pxr_authoritative_reconciliation_packet.py && python3 tools/product/build_pxr_unresolved_evidence_capture_intake.py && python3 tools/build_pxr_exact_evidence_review_intake_template.py && python3 tools/build_product_scope_breadth_evidence_intake_readiness.py && python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py && python3 tools/build_product_scope_breadth_evidence_priority_packet.py && python3 tools/build_product_scope_breadth_contract.py && python3 tools/build_general_protein_ligand_claim_blocker_packet.py && python3 tools/build_product_scope_breadth_closure_checklist.py && python3 tools/build_product_ai_architecture_execution_backlog.py && python3 tools/build_product_ai_architecture_gap_closure.py",
        "risk": "PXR has capture/intake acceptance, but authoritative reconciliation still shows six blocked rows, zero claim-safe quantitative rows, and no authoritative full-packet scope promotion",
    },
    "idp_broad": {
        "owner_lane": "scientific_scope",
        "acceptance_criteria": "broader_promotion_blocked=false, controlled_target_count>=8, and additional_anchor_backed_target_count>0",
        "verification_command": "python3 tools/build_idp_anchor_curation_queue.py && python3 tools/build_product_scope_breadth_contract.py",
        "risk": "controlled IDP scaffold is useful but still explicitly blocks broader promotion",
    },
    "all_atom": {
        "owner_lane": "scientific_scope",
        "acceptance_criteria": "claim_readiness_ready=true, strict_release_targets_supported=true, and missing_inputs empty in current all-atom handoff",
        "verification_command": "python3 tools/build_product_scope_breadth_contract.py",
        "risk": "older all-atom readiness exists, but current handoff is missing strict summary/accuracy inputs",
    },
    "general_protein_ligand": {
        "owner_lane": "product_claims",
        "acceptance_criteria": "all breadth domains ready, allowed_scope_families has at least 6 entries, and general_protein_ligand_platform_ready=true",
        "verification_command": "python3 tools/build_product_capability_surface_contract.py && python3 tools/build_product_scope_breadth_contract.py && python3 tools/build_general_protein_ligand_claim_blocker_packet.py && python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py && python3 tools/build_product_scope_breadth_evidence_priority_packet.py && python3 tools/build_product_scope_breadth_closure_checklist.py",
        "risk": "broad platform wording is unsafe until transporter/PXR evidence, allowed scope family count, and explicit general platform claim flags are all green",
    },
}

CLAIM_BOUNDARY = (
    "Product scope breadth work order only; converts the current scope-breadth blockers into acceptance criteria and "
    "local verification commands. It does not widen API scope, run docking, change product claims, upload, submit, "
    "email, delete, or mutate external state."
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
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _domain_blocker_metrics(domain: str, summary: dict[str, Any]) -> str:
    if domain == "transporter":
        return (
            f"manual_review_placeholders={_int(summary.get('transporter_manual_review_decision_placeholder_count'))};"
            f"manual_review_rows={_int(summary.get('transporter_manual_review_template_row_count'))};"
            f"direct_binding_required={_int(summary.get('transporter_manual_review_direct_binding_evidence_required_count'))};"
            f"negative_quantitative_required={_int(summary.get('transporter_manual_review_negative_quantitative_value_required_count'))};"
            f"candidate_ready_for_apply={_int(summary.get('transporter_candidate_ready_for_apply_count'))};"
            f"candidate_assignment_required={_int(summary.get('transporter_candidate_assignment_required_count'))}"
        )
    if domain == "pxr":
        return (
            f"exact_review_rows={_int(summary.get('pxr_exact_review_template_row_count'))};"
            f"kcal_placeholders={_int(summary.get('pxr_exact_review_kcal_placeholder_count'))};"
            f"conflict_resolution_required={_int(summary.get('pxr_exact_review_conflict_resolution_required_count'))};"
            f"external_exact_evidence_required={_int(summary.get('external_primary_exact_evidence_required_count'))}"
        )
    if domain == "general_protein_ligand":
        families = ",".join(str(item) for item in summary.get("allowed_scope_families") or [])
        return (
            f"ready_domains={','.join(str(item) for item in summary.get('ready_domains') or [])};"
            f"missing_domains={','.join(str(item) for item in summary.get('missing_domains') or [])};"
            f"allowed_scope_families={families};"
            f"general_platform={summary.get('general_protein_ligand_platform_ready')}"
        )
    return ""


def _domain_acceptance_criteria(domain: str, summary: dict[str, Any], fallback: str) -> str:
    if domain == "transporter":
        return (
            "transporter manual_review_decision_placeholder_count=0, all required direct-binding and negative "
            "quantitative review rows resolved into claim-safe authoritative candidates, candidate_ready_for_apply>0, "
            "placeholder_driven_rows=0, p0_open=0, claim_safe_binders>=1, authoritative_binders>=1, and "
            "donor_policy_reopen_ready=true"
        )
    if domain == "pxr":
        return (
            "PXR exact-review kcal_placeholder_count=0, conflict_resolution_required_count=0 or explicitly deferred "
            "by a claim-safe guardrail, claim_safe_quantitative_ready_count>0, blocked_row_count=0, and "
            "ready_for_apply_row_count equals queue_row_count after unresolved-evidence intake"
        )
    if domain == "general_protein_ligand":
        return (
            "transporter/pxr/ca2/idp_broad/all_atom breadth domains ready, allowed_scope_families has at least 6 "
            "entries, and general_protein_ligand_platform_ready=true"
        )
    return fallback


def build_product_scope_breadth_work_order(
    *,
    scope_contract_packet: dict[str, Any],
    scope_contract_path: str = DEFAULT_SCOPE_CONTRACT_JSON,
) -> dict[str, Any]:
    summary = _summary(scope_contract_packet)
    rows_by_domain = {
        str(row.get("domain") or ""): row
        for row in scope_contract_packet.get("rows", []) or []
        if isinstance(row, dict) and str(row.get("domain") or "")
    }
    missing_domains = [str(item) for item in summary.get("missing_domains") or []]
    ready_domains = [str(item) for item in summary.get("ready_domains") or []]
    rows: list[dict[str, Any]] = []
    for priority, domain in enumerate(missing_domains, start=1):
        action = DOMAIN_ACTIONS.get(domain, {})
        contract_row = rows_by_domain.get(domain, {})
        rows.append(
            {
                "priority": priority,
                "domain": domain,
                "status": "open",
                "owner_lane": action.get("owner_lane", "scientific_scope"),
                "source_artifact": contract_row.get("artifact") or scope_contract_path,
                "observed": contract_row.get("observed") or "",
                "current_blocker_metrics": _domain_blocker_metrics(domain, summary),
                "acceptance_criteria": _domain_acceptance_criteria(
                    domain,
                    summary,
                    action.get("acceptance_criteria") or contract_row.get("requirement") or "",
                ),
                "next_action": contract_row.get("next_action") or action.get("acceptance_criteria") or contract_row.get("requirement") or "",
                "verification_command": action.get("verification_command") or "python3 tools/build_product_scope_breadth_contract.py",
                "risk_if_skipped": action.get("risk") or "scope breadth would be overstated",
                "execution_enabled": False,
                "scope_widened": False,
                "external_state_mutated": False,
            }
        )
    work_order_ready = bool(rows or summary.get("scope_breadth_ready") is True)
    out_summary = {
        "packet_type": "product_scope_breadth_work_order",
        "status": "product_scope_breadth_work_order_ready" if work_order_ready else "blocked_product_scope_breadth_work_order",
        "work_order_ready": work_order_ready,
        "scope_breadth_ready": summary.get("scope_breadth_ready") is True,
        "open_item_count": len(rows),
        "ready_domain_count": len(ready_domains),
        "ready_domains": ready_domains,
        "missing_domains": missing_domains,
        "transporter_manual_review_decision_placeholder_count": _int(
            summary.get("transporter_manual_review_decision_placeholder_count")
        ),
        "pxr_exact_review_kcal_placeholder_count": _int(summary.get("pxr_exact_review_kcal_placeholder_count")),
        "pxr_exact_review_conflict_resolution_required_count": _int(
            summary.get("pxr_exact_review_conflict_resolution_required_count")
        ),
        "source_artifacts": [scope_contract_path],
        "execution_enabled": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Scope breadth is already ready; explicit product/API widening remains a separate decision."
            if summary.get("scope_breadth_ready") is True
            else "Work open scope-breadth items in priority order, then regenerate the scope contract and architecture gap closure."
        ),
    }
    return {"summary": out_summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Scope Breadth Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- scope_breadth_ready: `{s['scope_breadth_ready']}`",
        f"- open_item_count: `{s['open_item_count']}`",
        f"- ready_domains: `{','.join(s['ready_domains'])}`",
        f"- missing_domains: `{','.join(s['missing_domains'])}`",
        f"- transporter_manual_review_decision_placeholder_count: `{s['transporter_manual_review_decision_placeholder_count']}`",
        f"- pxr_exact_review_kcal_placeholder_count: `{s['pxr_exact_review_kcal_placeholder_count']}`",
        f"- pxr_exact_review_conflict_resolution_required_count: `{s['pxr_exact_review_conflict_resolution_required_count']}`",
        "",
        "## Open Items",
        "",
        "| priority | domain | observed | blocker metrics | acceptance criteria | verification | risk |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['domain']}` | `{row['observed']}` | "
            f"`{row['current_blocker_metrics']}` | "
            f"`{row['acceptance_criteria']}` | `{row['verification_command']}` | {row['risk_if_skipped']} |"
        )
    if not payload["rows"]:
        lines.append("| 0 | `none` | `all ready` | `none` | `none` | none |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build scope-breadth work order from current scope contract.")
    parser.add_argument("--scope-contract-json", default=DEFAULT_SCOPE_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_scope_breadth_work_order(
        scope_contract_packet=_read_json(args.scope_contract_json),
        scope_contract_path=args.scope_contract_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
