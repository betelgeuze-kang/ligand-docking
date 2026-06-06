#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_TRANSPORTER_JSON = RUNS / "transporter_p0_evidence_acquisition_packet_current.json"
DEFAULT_PXR_JSON = RUNS / "pxr_authoritative_reconciliation_packet_current.json"
DEFAULT_PXR_EXACT_REVIEW_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_GENERAL_JSON = RUNS / "general_protein_ligand_claim_blocker_packet_current.json"
DEFAULT_AQP1_FUNCTIONAL_JSON = RUNS / "aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_AQP1_LEDGER_JSON = RUNS / "aqp1_candidate_evidence_ledger_current.json"
DEFAULT_OUT_JSON = RUNS / "product_scope_breadth_evidence_acquisition_queue_current.json"
DEFAULT_OUT_CSV = RUNS / "product_scope_breadth_evidence_acquisition_queue_current.csv"
DEFAULT_OUT_MD = RUNS / "product_scope_breadth_evidence_acquisition_queue_current.md"

CLAIM_BOUNDARY = (
    "Product scope breadth evidence acquisition queue only; consolidates existing transporter, PXR, and general "
    "protein-ligand blocker packets into a prioritized local acquisition queue. It does not acquire evidence, "
    "authoritatively apply rows, widen API scope, run docking, promote claims, upload, submit, email, delete, or mutate external state."
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
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _join_list(value: Any) -> str:
    return ";".join(str(item).strip() for item in _list(value) if str(item).strip())


def _rows_by_step(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_step: dict[str, dict[str, Any]] = {}
    for row in _rows(packet):
        step = _text(row.get("packet_step") or row.get("proposed_packet_step"))
        if step and step not in by_step:
            by_step[step] = row
    return by_step


def _queue_row(
    *,
    priority: int,
    domain: str,
    item_id: str,
    item_type: str,
    candidate_or_check: str,
    request_mode: str,
    blocker: str,
    required_action: str,
    source_artifact: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "domain": domain,
        "item_id": item_id,
        "item_type": item_type,
        "candidate_or_check": candidate_or_check,
        "request_mode": request_mode,
        "blocker": blocker,
        "required_action": required_action,
        "source_artifact": source_artifact,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
    }


def _attach_operator_completion_contract(row: dict[str, Any], completion_packet: dict[str, Any]) -> None:
    if not completion_packet or row.get("item_id") != _text(completion_packet.get("slot_id")):
        return
    row.update(
        {
            "operator_completion_packet_ready": completion_packet.get("packet_ready") is True,
            "operator_completion_contract_version": _text(completion_packet.get("completion_contract_version")),
            "operator_completion_slot_id": _text(completion_packet.get("slot_id")),
            "operator_completion_expected_evidence_type": _text(completion_packet.get("expected_evidence_type")),
            "operator_completion_required_exact_evidence_field_count": _int(
                completion_packet.get("required_exact_evidence_field_count")
            ),
            "operator_completion_required_exact_evidence_fields": _join_list(
                completion_packet.get("required_exact_evidence_fields")
            ),
            "operator_completion_required_operator_intake_columns": _join_list(
                completion_packet.get("required_operator_intake_columns")
            ),
            "operator_completion_required_claim_guardrails": _join_list(
                completion_packet.get("required_claim_guardrails")
            ),
            "operator_completion_operator_review_artifact": _text(completion_packet.get("operator_review_artifact")),
            "operator_completion_post_intake_synchronization_targets": _join_list(
                completion_packet.get("post_intake_synchronization_targets")
            ),
            "operator_completion_acceptance_gate_commands": _join_list(
                completion_packet.get("acceptance_gate_commands") or completion_packet.get("validation_commands")
            ),
            "operator_completion_artifact": "runs/transporter_p0_evidence_acquisition_packet_current.json#next_slot_completion_packet",
        }
    )


def _attach_aqp1_review_sidecar(
    row: dict[str, Any],
    *,
    aqp1_functional_by_step: dict[str, dict[str, Any]],
    aqp1_ledger_by_step: dict[str, dict[str, Any]],
) -> None:
    if row.get("domain") != "transporter" or not str(row.get("item_id", "")).startswith("AQP1."):
        return
    packet_step = str(row.get("item_id", "")).split(".", 1)[-1]
    functional = aqp1_functional_by_step.get(packet_step, {})
    ledger = aqp1_ledger_by_step.get(packet_step, {})
    if not functional and not ledger:
        return
    row.update(
        {
            "aqp1_review_sidecar_ready": True,
            "aqp1_functional_surrogate_artifact": DEFAULT_AQP1_FUNCTIONAL_JSON.as_posix(),
            "aqp1_candidate_ledger_artifact": DEFAULT_AQP1_LEDGER_JSON.as_posix(),
            "aqp1_review_candidate_name": _text(
                functional.get("candidate_name") or ledger.get("candidate_name")
            ),
            "aqp1_review_source_anchor": _text(
                functional.get("source_anchor") or ledger.get("anchor")
            ),
            "aqp1_review_source_url": _text(functional.get("source_url") or ledger.get("source_url")),
            "aqp1_review_target_uniprot": _text(functional.get("target_uniprot")),
            "aqp1_review_public_provenance_status": _text(
                functional.get("public_provenance_status")
            ),
            "aqp1_review_functional_measure": ";".join(
                part
                for part in [
                    _text(functional.get("functional_measure_kind")),
                    _text(functional.get("functional_measure_value")),
                    _text(functional.get("functional_measure_units")),
                ]
                if part
            ),
            "aqp1_review_functional_delta_g_surrogate_kcal_mol": _text(
                functional.get("functional_delta_g_surrogate_kcal_mol")
            ),
            "aqp1_review_assay_type_honesty": _text(functional.get("assay_type_honesty")),
            "aqp1_review_direct_binding_claim_allowed": _text(
                functional.get("direct_binding_claim_allowed")
            ),
            "aqp1_review_binding_kcal_claim_allowed": _text(
                functional.get("binding_kcal_claim_allowed")
            ),
            "aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": _text(
                functional.get("replacement_reference_binding_kcal_mol_must_remain_blank")
            ),
            "aqp1_review_claim_safe_functional_kcal_ready": _text(
                functional.get("claim_safe_functional_kcal_ready")
            ),
            "aqp1_review_ledger_review_bucket": _text(ledger.get("review_bucket")),
            "aqp1_review_ledger_promotion_policy": _text(ledger.get("promotion_policy")),
            "aqp1_review_ledger_caution": _text(ledger.get("caution")),
        }
    )


def _attach_pxr_exact_review_sidecar(
    row: dict[str, Any],
    *,
    pxr_exact_review_by_step: dict[str, dict[str, Any]],
) -> None:
    if row.get("domain") != "pxr":
        return
    exact_review = pxr_exact_review_by_step.get(_text(row.get("item_id")), {})
    if not exact_review:
        return
    row.update(
        {
            "pxr_exact_review_sidecar_ready": True,
            "pxr_exact_review_artifact": DEFAULT_PXR_EXACT_REVIEW_JSON.as_posix(),
            "pxr_exact_review_row_id": _text(exact_review.get("review_row_id")),
            "pxr_exact_review_target_species": _text(exact_review.get("target_species")),
            "pxr_exact_review_target_gene": _text(exact_review.get("target_gene")),
            "pxr_exact_review_target_alias": _text(exact_review.get("target_alias")),
            "pxr_exact_review_required_evidence_mode": _text(
                exact_review.get("required_evidence_mode")
            ),
            "pxr_exact_review_target_match_confirmed": _text(
                exact_review.get("target_match_confirmed")
            ),
            "pxr_exact_review_replacement_reference_binding_kcal_mol": _text(
                exact_review.get("replacement_reference_binding_kcal_mol")
            ),
            "pxr_exact_review_replacement_source_url_or_doi": _text(
                exact_review.get("replacement_source_url_or_doi")
            ),
            "pxr_exact_review_assay_type_and_endpoint": _text(
                exact_review.get("assay_type_and_endpoint")
            ),
            "pxr_exact_review_conflict_resolution_required": exact_review.get(
                "conflict_resolution_required"
            )
            is True,
            "pxr_exact_review_authoritative_apply_allowed": exact_review.get(
                "authoritative_apply_allowed"
            )
            is True,
            "pxr_exact_review_scope_promotion_allowed": exact_review.get(
                "scope_promotion_allowed"
            )
            is True,
        }
    )


def build_payload(
    *,
    transporter_payload: dict[str, Any],
    pxr_payload: dict[str, Any],
    general_payload: dict[str, Any],
    pxr_exact_review_payload: dict[str, Any] | None = None,
    aqp1_functional_payload: dict[str, Any] | None = None,
    aqp1_ledger_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    priority = 1
    transporter_completion_packet = _summary(transporter_payload).get("next_slot_completion_packet")
    transporter_completion_packet = (
        transporter_completion_packet if isinstance(transporter_completion_packet, dict) else {}
    )
    aqp1_functional_payload = aqp1_functional_payload or {}
    aqp1_ledger_payload = aqp1_ledger_payload or {}
    aqp1_functional_by_step = _rows_by_step(aqp1_functional_payload)
    aqp1_ledger_by_step = _rows_by_step(aqp1_ledger_payload)
    pxr_exact_review_payload = pxr_exact_review_payload or {}
    pxr_exact_review_by_step = _rows_by_step(pxr_exact_review_payload)

    for row in _rows(transporter_payload):
        queue_row = _queue_row(
            priority=priority,
            domain="transporter",
            item_id=f"{_text(row.get('target_id'))}.{_text(row.get('packet_step'))}",
            item_type="scientific_evidence_request",
            candidate_or_check=_text(row.get("replacement_ligand_id")) or _text(row.get("current_ligand_id")),
            request_mode=_text(row.get("request_mode")),
            blocker=_text(row.get("required_missing_fields")) or _text(row.get("evidence_state")),
            required_action=_text(row.get("next_required_action")),
            source_artifact=DEFAULT_TRANSPORTER_JSON.as_posix(),
        )
        _attach_operator_completion_contract(queue_row, transporter_completion_packet)
        _attach_aqp1_review_sidecar(
            queue_row,
            aqp1_functional_by_step=aqp1_functional_by_step,
            aqp1_ledger_by_step=aqp1_ledger_by_step,
        )
        rows.append(queue_row)
        priority += 1

    for row in _rows(pxr_payload):
        queue_row = _queue_row(
            priority=priority,
            domain="pxr",
            item_id=_text(row.get("packet_step")),
            item_type="scientific_evidence_request",
            candidate_or_check=_text(row.get("candidate_name")),
            request_mode=_text(row.get("request_mode")),
            blocker=_text(row.get("readiness_missing_fields")) or _text(row.get("fail_closed_blockers")),
            required_action=_text(row.get("next_required_action")),
            source_artifact=DEFAULT_PXR_JSON.as_posix(),
        )
        _attach_pxr_exact_review_sidecar(
            queue_row,
            pxr_exact_review_by_step=pxr_exact_review_by_step,
        )
        rows.append(queue_row)
        priority += 1

    for row in _rows(general_payload):
        if row.get("release_blocker") is not True:
            continue
        rows.append(
            _queue_row(
                priority=priority,
                domain="general_protein_ligand",
                item_id=_text(row.get("check_id")),
                item_type=_text(row.get("check_type")) or "product_claim_gate",
                candidate_or_check=_text(row.get("check_id")),
                request_mode="claim_gate_prerequisite_required",
                blocker=f"current={_text(row.get('current_value'))};required={_text(row.get('required_value'))}",
                required_action=_text(row.get("next_action")),
                source_artifact=DEFAULT_GENERAL_JSON.as_posix(),
            )
        )
        priority += 1

    scientific_rows = [row for row in rows if row["item_type"] == "scientific_evidence_request"]
    claim_gate_rows = [row for row in rows if row["domain"] == "general_protein_ligand"]
    transporter = _summary(transporter_payload)
    pxr = _summary(pxr_payload)
    general = _summary(general_payload)
    completion_contract_rows = [row for row in rows if row.get("operator_completion_packet_ready") is True]
    next_completion = completion_contract_rows[0] if completion_contract_rows else {}
    aqp1_sidecar_rows = [row for row in rows if row.get("aqp1_review_sidecar_ready") is True]
    next_aqp1_sidecar = next_completion if next_completion.get("aqp1_review_sidecar_ready") is True else (
        aqp1_sidecar_rows[0] if aqp1_sidecar_rows else {}
    )
    pxr_exact_review_rows = [row for row in rows if row.get("pxr_exact_review_sidecar_ready") is True]
    next_pxr_exact_review = pxr_exact_review_rows[0] if pxr_exact_review_rows else {}
    summary = {
        "packet_type": "product_scope_breadth_evidence_acquisition_queue",
        "queue_ready": True,
        "scope_breadth_ready": False,
        "queue_item_count": len(rows),
        "scientific_evidence_request_count": len(scientific_rows),
        "claim_gate_prerequisite_count": len(claim_gate_rows),
        "transporter_unresolved_slot_count": _int(transporter.get("unresolved_slot_count")),
        "pxr_reconciled_blocked_row_count": _int(pxr.get("reconciled_blocked_row_count")),
        "general_claim_blocker_count": _int(general.get("blocker_count")),
        "next_operator_completion_packet_ready": bool(completion_contract_rows),
        "next_operator_completion_slot_id": _text(
            next_completion.get("operator_completion_slot_id")
        ),
        "next_operator_completion_expected_evidence_type": _text(
            next_completion.get("operator_completion_expected_evidence_type")
        ),
        "next_operator_completion_required_exact_evidence_field_count": _int(
            next_completion.get("operator_completion_required_exact_evidence_field_count")
        ),
        "next_operator_completion_required_exact_evidence_fields": _text(
            next_completion.get("operator_completion_required_exact_evidence_fields")
        ),
        "next_operator_completion_required_operator_intake_columns": _text(
            next_completion.get("operator_completion_required_operator_intake_columns")
        ),
        "next_operator_completion_required_claim_guardrails": _text(
            next_completion.get("operator_completion_required_claim_guardrails")
        ),
        "next_operator_completion_operator_review_artifact": _text(
            next_completion.get("operator_completion_operator_review_artifact")
        ),
        "next_operator_completion_post_intake_synchronization_targets": _text(
            next_completion.get("operator_completion_post_intake_synchronization_targets")
        ),
        "next_operator_completion_acceptance_gate_commands": _text(
            next_completion.get("operator_completion_acceptance_gate_commands")
        ),
        "next_operator_completion_contract_artifact": _text(
            next_completion.get("operator_completion_artifact")
        ),
        "next_operator_completion_aqp1_review_sidecar_ready": bool(next_aqp1_sidecar),
        "next_operator_completion_aqp1_functional_surrogate_artifact": _text(
            next_aqp1_sidecar.get("aqp1_functional_surrogate_artifact")
        ),
        "next_operator_completion_aqp1_candidate_ledger_artifact": _text(
            next_aqp1_sidecar.get("aqp1_candidate_ledger_artifact")
        ),
        "next_operator_completion_aqp1_review_candidate_name": _text(
            next_aqp1_sidecar.get("aqp1_review_candidate_name")
        ),
        "next_operator_completion_aqp1_review_source_anchor": _text(
            next_aqp1_sidecar.get("aqp1_review_source_anchor")
        ),
        "next_operator_completion_aqp1_review_source_url": _text(
            next_aqp1_sidecar.get("aqp1_review_source_url")
        ),
        "next_operator_completion_aqp1_review_target_uniprot": _text(
            next_aqp1_sidecar.get("aqp1_review_target_uniprot")
        ),
        "next_operator_completion_aqp1_review_public_provenance_status": _text(
            next_aqp1_sidecar.get("aqp1_review_public_provenance_status")
        ),
        "next_operator_completion_aqp1_review_functional_measure": _text(
            next_aqp1_sidecar.get("aqp1_review_functional_measure")
        ),
        "next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": _text(
            next_aqp1_sidecar.get("aqp1_review_functional_delta_g_surrogate_kcal_mol")
        ),
        "next_operator_completion_aqp1_review_assay_type_honesty": _text(
            next_aqp1_sidecar.get("aqp1_review_assay_type_honesty")
        ),
        "next_operator_completion_aqp1_review_direct_binding_claim_allowed": _text(
            next_aqp1_sidecar.get("aqp1_review_direct_binding_claim_allowed")
        ),
        "next_operator_completion_aqp1_review_binding_kcal_claim_allowed": _text(
            next_aqp1_sidecar.get("aqp1_review_binding_kcal_claim_allowed")
        ),
        "next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": _text(
            next_aqp1_sidecar.get(
                "aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank"
            )
        ),
        "next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": _text(
            next_aqp1_sidecar.get("aqp1_review_claim_safe_functional_kcal_ready")
        ),
        "next_operator_completion_aqp1_review_ledger_review_bucket": _text(
            next_aqp1_sidecar.get("aqp1_review_ledger_review_bucket")
        ),
        "next_operator_completion_aqp1_review_ledger_promotion_policy": _text(
            next_aqp1_sidecar.get("aqp1_review_ledger_promotion_policy")
        ),
        "next_operator_completion_aqp1_review_ledger_caution": _text(
            next_aqp1_sidecar.get("aqp1_review_ledger_caution")
        ),
        "aqp1_review_sidecar_row_count": len(aqp1_sidecar_rows),
        "pxr_exact_review_sidecar_row_count": len(pxr_exact_review_rows),
        "next_pxr_exact_review_sidecar_ready": bool(next_pxr_exact_review),
        "next_pxr_exact_review_row_id": _text(next_pxr_exact_review.get("pxr_exact_review_row_id")),
        "next_pxr_exact_review_candidate_name": _text(next_pxr_exact_review.get("candidate_or_check")),
        "next_pxr_exact_review_required_evidence_mode": _text(
            next_pxr_exact_review.get("pxr_exact_review_required_evidence_mode")
        ),
        "next_pxr_exact_review_target_match_confirmed": _text(
            next_pxr_exact_review.get("pxr_exact_review_target_match_confirmed")
        ),
        "next_pxr_exact_review_replacement_reference_binding_kcal_mol": _text(
            next_pxr_exact_review.get("pxr_exact_review_replacement_reference_binding_kcal_mol")
        ),
        "next_pxr_exact_review_replacement_source_url_or_doi": _text(
            next_pxr_exact_review.get("pxr_exact_review_replacement_source_url_or_doi")
        ),
        "next_pxr_exact_review_authoritative_apply_allowed": next_pxr_exact_review.get(
            "pxr_exact_review_authoritative_apply_allowed"
        )
        is True,
        "next_pxr_exact_review_scope_promotion_allowed": next_pxr_exact_review.get(
            "pxr_exact_review_scope_promotion_allowed"
        )
        is True,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [
            DEFAULT_TRANSPORTER_JSON.as_posix(),
            DEFAULT_PXR_JSON.as_posix(),
            DEFAULT_PXR_EXACT_REVIEW_JSON.as_posix(),
            DEFAULT_GENERAL_JSON.as_posix(),
            DEFAULT_AQP1_FUNCTIONAL_JSON.as_posix(),
            DEFAULT_AQP1_LEDGER_JSON.as_posix(),
        ],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Work scientific evidence requests first, then regenerate transporter/PXR gates and only revisit general platform flags after domain gates are green."
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
        "# Product Scope Breadth Evidence Acquisition Queue",
        "",
        f"- queue_ready: `{s['queue_ready']}`",
        f"- scope_breadth_ready: `{s['scope_breadth_ready']}`",
        f"- queue_item_count: `{s['queue_item_count']}`",
        f"- scientific_evidence_request_count: `{s['scientific_evidence_request_count']}`",
        f"- claim_gate_prerequisite_count: `{s['claim_gate_prerequisite_count']}`",
        f"- transporter_unresolved_slot_count: `{s['transporter_unresolved_slot_count']}`",
        f"- pxr_reconciled_blocked_row_count: `{s['pxr_reconciled_blocked_row_count']}`",
        f"- general_claim_blocker_count: `{s['general_claim_blocker_count']}`",
        f"- next_operator_completion_packet_ready: `{s['next_operator_completion_packet_ready']}`",
        f"- next_operator_completion_slot_id: `{s['next_operator_completion_slot_id'] or '-'}`",
        f"- next_operator_completion_expected_evidence_type: `{s['next_operator_completion_expected_evidence_type'] or '-'}`",
        f"- next_operator_completion_required_exact_evidence_field_count: `{s['next_operator_completion_required_exact_evidence_field_count']}`",
        f"- next_operator_completion_required_exact_evidence_fields: `{s['next_operator_completion_required_exact_evidence_fields'] or '-'}`",
        f"- next_operator_completion_required_operator_intake_columns: `{s['next_operator_completion_required_operator_intake_columns'] or '-'}`",
        f"- next_operator_completion_required_claim_guardrails: `{s['next_operator_completion_required_claim_guardrails'] or '-'}`",
        f"- next_operator_completion_operator_review_artifact: `{s['next_operator_completion_operator_review_artifact'] or '-'}`",
        f"- next_operator_completion_post_intake_synchronization_targets: `{s['next_operator_completion_post_intake_synchronization_targets'] or '-'}`",
        f"- next_operator_completion_acceptance_gate_commands: `{s['next_operator_completion_acceptance_gate_commands'] or '-'}`",
        f"- next_operator_completion_aqp1_review_sidecar_ready: `{s['next_operator_completion_aqp1_review_sidecar_ready']}`",
        f"- next_operator_completion_aqp1_review_candidate_name: `{s['next_operator_completion_aqp1_review_candidate_name'] or '-'}`",
        f"- next_operator_completion_aqp1_review_source_anchor: `{s['next_operator_completion_aqp1_review_source_anchor'] or '-'}`",
        f"- next_operator_completion_aqp1_review_source_url: `{s['next_operator_completion_aqp1_review_source_url'] or '-'}`",
        f"- next_operator_completion_aqp1_review_target_uniprot: `{s['next_operator_completion_aqp1_review_target_uniprot'] or '-'}`",
        f"- next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol: `{s['next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol'] or '-'}`",
        f"- next_operator_completion_aqp1_review_assay_type_honesty: `{s['next_operator_completion_aqp1_review_assay_type_honesty'] or '-'}`",
        f"- next_operator_completion_aqp1_review_direct_binding_claim_allowed: `{s['next_operator_completion_aqp1_review_direct_binding_claim_allowed'] or '-'}`",
        f"- next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank: `{s['next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank'] or '-'}`",
        f"- pxr_exact_review_sidecar_row_count: `{s['pxr_exact_review_sidecar_row_count']}`",
        f"- next_pxr_exact_review_sidecar_ready: `{s['next_pxr_exact_review_sidecar_ready']}`",
        f"- next_pxr_exact_review_row_id: `{s['next_pxr_exact_review_row_id'] or '-'}`",
        f"- next_pxr_exact_review_candidate_name: `{s['next_pxr_exact_review_candidate_name'] or '-'}`",
        f"- next_pxr_exact_review_required_evidence_mode: `{s['next_pxr_exact_review_required_evidence_mode'] or '-'}`",
        f"- next_pxr_exact_review_target_match_confirmed: `{s['next_pxr_exact_review_target_match_confirmed'] or '-'}`",
        f"- next_pxr_exact_review_replacement_reference_binding_kcal_mol: `{s['next_pxr_exact_review_replacement_reference_binding_kcal_mol'] or '-'}`",
        f"- next_pxr_exact_review_replacement_source_url_or_doi: `{s['next_pxr_exact_review_replacement_source_url_or_doi'] or '-'}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Queue",
        "",
        "| priority | domain | item | type | candidate/check | mode | blocker | action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['domain']}` | `{row['item_id']}` | `{row['item_type']}` | "
            f"`{row['candidate_or_check'] or '-'}` | `{row['request_mode'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['required_action']} |"
        )
    completion_row = next((row for row in payload["rows"] if row.get("operator_completion_packet_ready") is True), {})
    if completion_row:
        lines.extend(
            [
                "",
                "## Next Operator Completion Contract",
                "",
                f"- slot: `{completion_row['operator_completion_slot_id']}`",
                f"- evidence_type: `{completion_row['operator_completion_expected_evidence_type']}`",
                f"- required_exact_evidence_fields: `{completion_row['operator_completion_required_exact_evidence_fields']}`",
                f"- guardrails: `{completion_row['operator_completion_required_claim_guardrails']}`",
                f"- sync_targets: `{completion_row['operator_completion_post_intake_synchronization_targets']}`",
                f"- acceptance_gates: `{completion_row['operator_completion_acceptance_gate_commands']}`",
                f"- aqp1_sidecar_ready: `{completion_row.get('aqp1_review_sidecar_ready') is True}`",
                f"- aqp1_candidate: `{completion_row.get('aqp1_review_candidate_name', '-')}`",
                f"- aqp1_source: `{completion_row.get('aqp1_review_source_anchor', '-')}` `{completion_row.get('aqp1_review_source_url', '-')}`",
                f"- aqp1_functional_delta_g_surrogate_kcal_mol: `{completion_row.get('aqp1_review_functional_delta_g_surrogate_kcal_mol', '-')}`",
                f"- aqp1_claim_guard: `direct_binding_claim_allowed={completion_row.get('aqp1_review_direct_binding_claim_allowed', '-')};replacement_reference_binding_kcal_mol_must_remain_blank={completion_row.get('aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank', '-')}`",
            ]
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope breadth evidence acquisition queue.")
    parser.add_argument("--transporter-json", default=str(DEFAULT_TRANSPORTER_JSON))
    parser.add_argument("--pxr-json", default=str(DEFAULT_PXR_JSON))
    parser.add_argument("--pxr-exact-review-json", default=str(DEFAULT_PXR_EXACT_REVIEW_JSON))
    parser.add_argument("--general-json", default=str(DEFAULT_GENERAL_JSON))
    parser.add_argument("--aqp1-functional-json", default=str(DEFAULT_AQP1_FUNCTIONAL_JSON))
    parser.add_argument("--aqp1-ledger-json", default=str(DEFAULT_AQP1_LEDGER_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        transporter_payload=_load_json(args.transporter_json),
        pxr_payload=_load_json(args.pxr_json),
        general_payload=_load_json(args.general_json),
        pxr_exact_review_payload=_load_json(args.pxr_exact_review_json),
        aqp1_functional_payload=_load_json(args.aqp1_functional_json),
        aqp1_ledger_payload=_load_json(args.aqp1_ledger_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
