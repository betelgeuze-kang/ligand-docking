#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from betelgeuze_cameo.cli import build_all_status as build_cameo_cli_all_status
from betelgeuze_cleanup.cli import build_all_status as build_cleanup_cli_all_status
from betelgeuze_product.cli import build_all_status as build_product_cli_all_status

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_PRODUCT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_PRODUCT_PILOT_PACKET_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PRODUCT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_PRODUCT_OPERATIONAL_QUALITY_JSON = "runs/product_operational_quality_contract_current.json"
DEFAULT_CAMEO_READINESS_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_CAMEO_EVIDENCE_INTEGRITY_JSON = "runs/cameo_evidence_integrity_contract_current.json"
DEFAULT_CAMEO_REPAIR_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_CAMEO_INPUT_KIT_JSON = "runs/cameo_operator_input_kit_current/manifest.json"
DEFAULT_CAMEO_INPUT_VALIDATION_JSON = "runs/cameo_operator_input_validation_current.json"
DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON = "runs/cameo_repair_execution_preflight_current.json"
DEFAULT_CAMEO_CAPABILITY_PREFLIGHT_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_TRANSITION_CLEANUP_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON = "runs/transition_cleanup_execution_preflight_current.json"
DEFAULT_LIGAND_CLEANUP_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_CLEANUP_POSTCHECK_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_OUT_JSON = "runs/goal_readiness_rollup_current.json"
DEFAULT_OUT_CSV = "runs/goal_readiness_rollup_current.csv"
DEFAULT_OUT_MD = "runs/goal_readiness_rollup_current.md"

CLAIM_BOUNDARY = (
    "Goal readiness rollup only; it summarizes commercial-product, CAMEO-validation, and cleanup readiness artifacts. "
    "It does not run docking, submit CAMEO predictions, send email, delete files, archive files, upload, commit, push, "
    "or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _lane(
    *,
    lane_id: str,
    path: str,
    packet: dict[str, Any],
    observed_status: str,
    lane_status: str,
    blocker_count: int = 0,
    approval_token: str = "",
    reclaim_size_gb: float = 0.0,
    next_required_step: str = "",
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "artifact_path": path,
        "artifact_present": bool(packet),
        "observed_status": observed_status,
        "lane_status": lane_status,
        "blocker_count": blocker_count,
        "approval_token_required": approval_token,
        "reclaim_size_gb": reclaim_size_gb,
        "execution_enabled": False,
        "action_executed": False,
        "external_state_mutated": False,
        "next_required_step": next_required_step,
    }


def _product_lane(
    readiness_path: str,
    readiness_packet: dict[str, Any],
    preflight_path: str,
    preflight_packet: dict[str, Any],
    bundle_contract_path: str = "",
    bundle_contract_packet: dict[str, Any] | None = None,
    delivery_evidence_path: str = "",
    delivery_evidence_packet: dict[str, Any] | None = None,
    pilot_packet_path: str = "",
    pilot_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readiness = _summary(readiness_packet)
    preflight = _summary(preflight_packet)
    bundle_contract_packet = bundle_contract_packet or {}
    bundle_contract = _summary(bundle_contract_packet)
    delivery_evidence_packet = delivery_evidence_packet or {}
    delivery_evidence = _summary(delivery_evidence_packet)
    pilot_packet = pilot_packet or {}
    pilot = _summary(pilot_packet)
    bundle_contract_ok = not bundle_contract_packet or bundle_contract.get("status") == "product_bundle_contract_ready"
    delivery_evidence_ok = not delivery_evidence_packet or delivery_evidence.get("status") == "product_delivery_evidence_contract_ready"
    pilot_packet_ok = not pilot_packet or pilot.get("status") in {"product_pilot_packet_preflight_ready", "product_pilot_packet_ready"}
    ready = (
        readiness.get("status") == "product_handoff_ready"
        and preflight.get("status") == "product_execution_preflight_ready"
        and bundle_contract_ok
        and delivery_evidence_ok
        and pilot_packet_ok
    )
    blockers = (
        _int(readiness.get("blocker_count"))
        + _int(preflight.get("blocker_count"))
        + _int(bundle_contract.get("blocker_count"))
        + _int(delivery_evidence.get("blocker_count"))
        + _int(pilot.get("blocker_count"))
    )
    if not readiness_packet or not preflight_packet:
        lane_status = "blocked_missing_artifact"
    elif ready:
        lane_status = "operator_approval_pending"
    else:
        lane_status = "blocked"
    return _lane(
        lane_id="commercial_product_execution",
        path=";".join(
            part
            for part in (
                readiness_path,
                preflight_path,
                bundle_contract_path if bundle_contract_packet else "",
                delivery_evidence_path if delivery_evidence_packet else "",
                pilot_packet_path if pilot_packet else "",
            )
            if part
        ),
        packet=readiness_packet if readiness_packet and preflight_packet else {},
        observed_status=";".join(
            status
            for status in (
                _text(readiness.get("status")),
                _text(preflight.get("status")),
                _text(bundle_contract.get("status")) if bundle_contract_packet else "",
                _text(delivery_evidence.get("status")) if delivery_evidence_packet else "",
                _text(pilot.get("status")) if pilot_packet else "",
            )
            if status
        ),
        lane_status=lane_status,
        blocker_count=blockers if blockers else (0 if ready else 1),
        approval_token=_text(preflight.get("approval_token_required") or readiness.get("execution_approval_token_required")),
        next_required_step=_text(pilot.get("next_required_step") or bundle_contract.get("next_required_step") or preflight.get("next_required_step") or readiness.get("next_required_step")),
    ) | {
        "bundle_contract_status": _text(bundle_contract.get("status")),
        "bundle_contract_blocker_count": _int(bundle_contract.get("blocker_count")),
        "delivery_evidence_status": _text(delivery_evidence.get("status")),
        "delivery_ready_claim_allowed": bool(delivery_evidence.get("delivery_ready_claim_allowed") is True),
        "delivery_evidence_warning_count": _int(delivery_evidence.get("warning_count")),
        "pilot_packet_status": _text(pilot.get("status")),
        "pilot_delivery_ready": bool(pilot.get("pilot_delivery_ready") is True),
        "pilot_packet_warning_count": _int(pilot.get("warning_count")),
    }


def _product_architecture_lane(path: str, packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(packet)
    status = _text(summary.get("status"))
    local_surface_ready = bool(summary.get("local_architecture_surface_ready") is True)
    architecture_release_ready = bool(summary.get("architecture_release_ready") is True)
    blocked_lanes = _int(summary.get("blocked_lane_count"))
    approval_lanes = _int(summary.get("approval_required_lane_count"))
    if not packet:
        lane_status = "blocked_missing_artifact"
    elif architecture_release_ready:
        lane_status = "evidence_ready"
    elif blocked_lanes > 0 or not local_surface_ready:
        lane_status = "blocked"
    else:
        lane_status = "operator_approval_pending"
    lane = _lane(
        lane_id="product_architecture",
        path=path,
        packet=packet,
        observed_status=status,
        lane_status=lane_status,
        blocker_count=blocked_lanes if packet else 1,
        next_required_step=_text(summary.get("next_required_step")),
    )
    lane["local_architecture_surface_ready"] = local_surface_ready
    lane["architecture_release_ready"] = architecture_release_ready
    lane["structure_analysis_product_surface_ready"] = bool(summary.get("structure_analysis_product_surface_ready") is True)
    lane["ligand_docking_execution_contract_ready"] = bool(summary.get("ligand_docking_execution_contract_ready") is True)
    lane["commercial_independence_ready"] = bool(summary.get("commercial_independence_ready") is True)
    lane["cameo_architecture_validation_ready"] = bool(summary.get("cameo_architecture_validation_ready") is True)
    lane["cleanup_control_surface_ready"] = bool(summary.get("cleanup_control_surface_ready") is True)
    lane["casp17_transition_surface_ready"] = bool(summary.get("casp17_transition_surface_ready") is True)
    lane["architecture_approval_required_lane_count"] = approval_lanes
    return lane


def _cameo_lane(
    path: str,
    packet: dict[str, Any],
    repair_path: str = "",
    repair_packet: dict[str, Any] | None = None,
    input_kit_path: str = "",
    input_kit_packet: dict[str, Any] | None = None,
    input_validation_path: str = "",
    input_validation_packet: dict[str, Any] | None = None,
    repair_preflight_path: str = "",
    repair_preflight_packet: dict[str, Any] | None = None,
    capability_preflight_path: str = "",
    capability_preflight_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary(packet)
    repair_packet = repair_packet or {}
    repair_summary = _summary(repair_packet)
    input_kit_packet = input_kit_packet or {}
    input_kit_summary = _summary(input_kit_packet)
    input_validation_packet = input_validation_packet or {}
    input_validation_summary = _summary(input_validation_packet)
    repair_preflight_packet = repair_preflight_packet or {}
    repair_preflight_summary = _summary(repair_preflight_packet)
    capability_preflight_packet = capability_preflight_packet or {}
    capability_preflight_summary = _summary(capability_preflight_packet)
    status = _text(summary.get("status"))
    if not packet:
        lane_status = "blocked_missing_artifact"
    elif status == "cameo_validation_evidence_ready":
        lane_status = "evidence_ready"
    elif status == "cameo_validation_pending_official_results":
        lane_status = "external_results_pending"
    else:
        lane_status = "blocked"
    lane = _lane(
        lane_id="cameo_validation",
        path=";".join(part for part in (path, repair_path, input_kit_path, input_validation_path, repair_preflight_path, capability_preflight_path) if part),
        packet=packet,
        observed_status=status,
        lane_status=lane_status,
        blocker_count=_int(summary.get("blocker_count")) if packet else 1,
        next_required_step=_text(repair_preflight_summary.get("next_required_step") or input_validation_summary.get("next_required_step") or input_kit_summary.get("next_required_step") or repair_summary.get("next_required_step") or summary.get("next_required_step")),
    )
    lane["repair_work_order_status"] = _text(repair_summary.get("status"))
    lane["repair_operator_input_missing_count"] = _int(repair_summary.get("operator_input_missing_count"))
    lane["operator_input_kit_status"] = _text(input_kit_summary.get("status"))
    lane["operator_input_kit_template_count"] = _int(input_kit_summary.get("template_count"))
    lane["operator_input_validation_status"] = _text(input_validation_summary.get("status"))
    lane["operator_input_validation_blocker_count"] = _int(input_validation_summary.get("blocker_count"))
    lane["repair_execution_preflight_status"] = _text(repair_preflight_summary.get("status"))
    lane["repair_execution_preflight_blocker_count"] = _int(repair_preflight_summary.get("blocker_count"))
    lane["capability_preflight_status"] = _text(capability_preflight_summary.get("status"))
    lane["public_registration_allowed"] = bool(capability_preflight_summary.get("public_registration_allowed") is True)
    lane["public_registration_blocker_count"] = _int(capability_preflight_summary.get("public_registration_blocker_count"))
    lane["receiver_smoke_status"] = _text(capability_preflight_summary.get("source_receiver_smoke_status"))
    lane["api_dependency_status"] = _text(capability_preflight_summary.get("source_api_dependency_status"))
    lane["api_dependency_ready"] = bool(capability_preflight_summary.get("api_dependency_ready") is True)
    lane["api_dependency_blocker_count"] = _int(capability_preflight_summary.get("api_dependency_blocker_count"))
    lane["receiver_smoke_post_200_ok"] = bool(capability_preflight_summary.get("receiver_smoke_post_200_ok") is True)
    lane["receiver_smoke_blocker_count"] = _int(capability_preflight_summary.get("receiver_smoke_blocker_count"))
    return lane


def _cleanup_lane(
    lane_id: str,
    path: str,
    packet: dict[str, Any],
    status_ready: str,
    size_key: str,
    preflight_path: str = "",
    preflight_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary(packet)
    preflight_packet = preflight_packet or {}
    preflight_summary = _summary(preflight_packet)
    status = _text(summary.get("status"))
    preflight_status = _text(preflight_summary.get("status"))
    preflight_ready = not preflight_packet or (
        preflight_status == "transition_cleanup_execution_preflight_ready"
        and _int(preflight_summary.get("blocker_count")) == 0
    )
    if not packet:
        lane_status = "blocked_missing_artifact"
    elif status == status_ready and _int(summary.get("blocker_count")) == 0 and preflight_ready:
        lane_status = "operator_approval_pending"
    else:
        lane_status = "blocked"
    token = _text(summary.get("approval_token_required"))
    if lane_id == "transition_cleanup":
        token = "row_specific_approval_tokens"
    lane = _lane(
        lane_id=lane_id,
        path=";".join(part for part in (path, preflight_path if preflight_packet else "") if part),
        packet=packet,
        observed_status=";".join(status for status in (status, preflight_status if preflight_packet else "") if status),
        lane_status=lane_status,
        blocker_count=_int(summary.get("blocker_count")) + _int(preflight_summary.get("blocker_count")) if packet else 1,
        approval_token=token,
        reclaim_size_gb=_float(summary.get(size_key)),
        next_required_step=_text(preflight_summary.get("next_required_step") or summary.get("next_required_step")),
    )
    lane["transition_cleanup_preflight_status"] = preflight_status
    lane["transition_cleanup_preflight_blocker_count"] = _int(preflight_summary.get("blocker_count"))
    return lane


def _ligand_cleanup_lane(
    path: str,
    packet: dict[str, Any],
    preflight_path: str = "",
    preflight_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary(packet)
    preflight_packet = preflight_packet or {}
    preflight_summary = _summary(preflight_packet)
    status = _text(summary.get("status"))
    preflight_status = _text(preflight_summary.get("status"))
    work_order_ready = status == "cleanup_work_order_ready" and _int(summary.get("blocker_count")) == 0
    preflight_ready = not preflight_packet or (
        preflight_status == "ligand_heavy_cleanup_execution_preflight_ready"
        and _int(preflight_summary.get("blocker_count")) == 0
    )
    if not packet:
        lane_status = "blocked_missing_artifact"
    elif work_order_ready and preflight_ready:
        lane_status = "operator_approval_pending"
    else:
        lane_status = "blocked"
    lane = _lane(
        lane_id="ligand_heavy_cleanup",
        path=";".join(part for part in (path, preflight_path if preflight_packet else "") if part),
        packet=packet,
        observed_status=";".join(status for status in (status, preflight_status if preflight_packet else "") if status),
        lane_status=lane_status,
        blocker_count=_int(summary.get("blocker_count")) + _int(preflight_summary.get("blocker_count")) if packet else 1,
        approval_token=_text(preflight_summary.get("approval_token_required") or summary.get("approval_token_required")),
        reclaim_size_gb=_float(summary.get("candidate_size_gb")),
        next_required_step=_text(preflight_summary.get("next_required_step") or summary.get("next_required_step")),
    )
    lane["cleanup_execution_preflight_status"] = preflight_status
    lane["cleanup_execution_preflight_blocker_count"] = _int(preflight_summary.get("blocker_count"))
    return lane


def build_rollup(
    *,
    product_readiness_packet: dict[str, Any],
    product_preflight_packet: dict[str, Any],
    cameo_readiness_packet: dict[str, Any],
    transition_cleanup_packet: dict[str, Any],
    ligand_cleanup_packet: dict[str, Any],
    product_bundle_contract_packet: dict[str, Any] | None = None,
    product_delivery_evidence_packet: dict[str, Any] | None = None,
    product_pilot_packet: dict[str, Any] | None = None,
    product_architecture_packet: dict[str, Any] | None = None,
    product_operational_quality_packet: dict[str, Any] | None = None,
    cameo_repair_packet: dict[str, Any] | None = None,
    cameo_evidence_integrity_packet: dict[str, Any] | None = None,
    cameo_input_kit_packet: dict[str, Any] | None = None,
    cameo_input_validation_packet: dict[str, Any] | None = None,
    cameo_repair_preflight_packet: dict[str, Any] | None = None,
    cameo_capability_preflight_packet: dict[str, Any] | None = None,
    transition_cleanup_preflight_packet: dict[str, Any] | None = None,
    ligand_cleanup_preflight_packet: dict[str, Any] | None = None,
    cleanup_postcheck_packet: dict[str, Any] | None = None,
    product_cli_status_packet: dict[str, Any] | None = None,
    cameo_cli_status_packet: dict[str, Any] | None = None,
    cleanup_cli_status_packet: dict[str, Any] | None = None,
    product_readiness_path: str = DEFAULT_PRODUCT_READINESS_JSON,
    product_preflight_path: str = DEFAULT_PRODUCT_PREFLIGHT_JSON,
    product_bundle_contract_path: str = DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON,
    product_delivery_evidence_path: str = DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON,
    product_pilot_packet_path: str = DEFAULT_PRODUCT_PILOT_PACKET_JSON,
    product_architecture_path: str = DEFAULT_PRODUCT_ARCHITECTURE_JSON,
    product_operational_quality_path: str = DEFAULT_PRODUCT_OPERATIONAL_QUALITY_JSON,
    cameo_readiness_path: str = DEFAULT_CAMEO_READINESS_JSON,
    cameo_evidence_integrity_path: str = DEFAULT_CAMEO_EVIDENCE_INTEGRITY_JSON,
    cameo_repair_path: str = DEFAULT_CAMEO_REPAIR_JSON,
    cameo_input_kit_path: str = DEFAULT_CAMEO_INPUT_KIT_JSON,
    cameo_input_validation_path: str = DEFAULT_CAMEO_INPUT_VALIDATION_JSON,
    cameo_repair_preflight_path: str = DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON,
    cameo_capability_preflight_path: str = DEFAULT_CAMEO_CAPABILITY_PREFLIGHT_JSON,
    transition_cleanup_path: str = DEFAULT_TRANSITION_CLEANUP_JSON,
    transition_cleanup_preflight_path: str = DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON,
    ligand_cleanup_path: str = DEFAULT_LIGAND_CLEANUP_JSON,
    ligand_cleanup_preflight_path: str = DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON,
    cleanup_postcheck_path: str = DEFAULT_CLEANUP_POSTCHECK_JSON,
) -> dict[str, Any]:
    rows = [
        _product_lane(
            product_readiness_path,
            product_readiness_packet,
            product_preflight_path,
            product_preflight_packet,
            product_bundle_contract_path,
            product_bundle_contract_packet or {},
            product_delivery_evidence_path,
            product_delivery_evidence_packet or {},
            product_pilot_packet_path,
            product_pilot_packet or {},
        ),
        _product_architecture_lane(product_architecture_path, product_architecture_packet or {}),
        _cameo_lane(
            cameo_readiness_path,
            cameo_readiness_packet,
            cameo_repair_path,
            cameo_repair_packet or {},
            cameo_input_kit_path,
            cameo_input_kit_packet or {},
            cameo_input_validation_path,
            cameo_input_validation_packet or {},
            cameo_repair_preflight_path,
            cameo_repair_preflight_packet or {},
            cameo_capability_preflight_path,
            cameo_capability_preflight_packet or {},
        ),
        _cleanup_lane(
            "transition_cleanup",
            transition_cleanup_path,
            transition_cleanup_packet,
            "transition_cleanup_work_order_ready",
            "approval_gated_reclaim_size_gb",
            transition_cleanup_preflight_path,
            transition_cleanup_preflight_packet or {},
        ),
        _ligand_cleanup_lane(ligand_cleanup_path, ligand_cleanup_packet, ligand_cleanup_preflight_path, ligand_cleanup_preflight_packet or {}),
    ]
    blocked_count = sum(1 for row in rows if row["lane_status"].startswith("blocked"))
    operator_pending_count = sum(1 for row in rows if row["lane_status"] == "operator_approval_pending")
    external_pending_count = sum(1 for row in rows if row["lane_status"] == "external_results_pending")
    evidence_ready_count = sum(1 for row in rows if row["lane_status"] == "evidence_ready")
    cleanup_postcheck = _summary(cleanup_postcheck_packet or {})
    product_operational_quality = _summary(product_operational_quality_packet or {})
    cameo_evidence_integrity = _summary(cameo_evidence_integrity_packet or {})
    product_cli_status = product_cli_status_packet or {}
    cameo_cli_status = cameo_cli_status_packet or {}
    cleanup_cli_status = cleanup_cli_status_packet or {}
    cleanup_postcheck_ready = (
        _text(cleanup_postcheck.get("status")) == "cleanup_postcheck_contract_ready"
        and bool(cleanup_postcheck.get("postcheck_contract_ready") is True)
        and _int(cleanup_postcheck.get("row_count")) > 0
        and _int(cleanup_postcheck.get("blocked_row_count")) == 0
    )
    if blocked_count:
        status = "blocked_goal_readiness"
    elif operator_pending_count or external_pending_count:
        status = "goal_readiness_pending_operator_or_external_results"
    else:
        status = "goal_readiness_evidence_ready"
    summary = {
        "packet_type": "goal_readiness_rollup",
        "status": status,
        "lane_count": len(rows),
        "blocked_lane_count": blocked_count,
        "operator_approval_pending_count": operator_pending_count,
        "external_results_pending_count": external_pending_count,
        "evidence_ready_count": evidence_ready_count,
        "total_reclaim_size_gb": round(sum(_float(row.get("reclaim_size_gb")) for row in rows), 3),
        "product_architecture_status": _text(_summary(product_architecture_packet or {}).get("status")),
        "product_architecture_local_surface_ready": bool(_summary(product_architecture_packet or {}).get("local_architecture_surface_ready") is True),
        "product_architecture_release_ready": bool(_summary(product_architecture_packet or {}).get("architecture_release_ready") is True),
        "product_operational_quality_status": _text(product_operational_quality.get("status")),
        "product_operational_quality_ready": bool(
            product_operational_quality.get("operational_quality_ready") is True
            or product_cli_status.get("operational_quality_ready") is True
        ),
        "product_operational_quality_blocker_count": _int(product_operational_quality.get("blocker_count")),
        "product_operational_quality_artifact": product_operational_quality_path if product_operational_quality_packet else "",
        "cleanup_postcheck_contract_status": _text(cleanup_postcheck.get("status")),
        "cleanup_postcheck_contract_ready": cleanup_postcheck_ready,
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "cleanup_postcheck_json": cleanup_postcheck_path if cleanup_postcheck_packet else "",
        "product_cli_status_set_status": _text(product_cli_status.get("status")),
        "product_cli_approval_token_count": _int(product_cli_status.get("approval_token_count")),
        "product_cli_operations_blocked_stage_count": _int(product_cli_status.get("operations_blocked_stage_count")),
        "product_cli_operations_approval_required_stage_count": _int(
            product_cli_status.get("operations_approval_required_stage_count")
        ),
        "product_cli_capability_surface_ready": bool(product_cli_status.get("capability_surface_ready") is True),
        "product_cli_operational_quality_ready": bool(product_cli_status.get("operational_quality_ready") is True),
        "product_cli_architecture_release_ready": bool(product_cli_status.get("architecture_release_ready") is True),
        "product_cli_commercial_independence_ready": bool(product_cli_status.get("commercial_independence_ready") is True),
        "product_cli_authorized_for_execution": bool(product_cli_status.get("authorized_for_execution") is True),
        "product_cli_bundle_validation_passed": bool(product_cli_status.get("bundle_validation_passed") is True),
        "product_cli_delivery_ready_claim_allowed": bool(product_cli_status.get("delivery_ready_claim_allowed") is True),
        "cameo_cli_status_set_status": _text(cameo_cli_status.get("status")),
        "cameo_cli_approval_token_count": _int(cameo_cli_status.get("approval_token_count")),
        "cameo_cli_official_result_required": bool(cameo_cli_status.get("official_result_required") is True),
        "cameo_cli_official_results_accepted_count": _int(cameo_cli_status.get("official_results_accepted_count")),
        "cameo_cli_api_install_approval_required": bool(cameo_cli_status.get("api_install_approval_required") is True),
        "cameo_cli_receiver_smoke_status": _text(cameo_cli_status.get("receiver_smoke_status")),
        "cameo_evidence_integrity_status": _text(cameo_evidence_integrity.get("status")),
        "cameo_evidence_integrity_ready": bool(
            cameo_evidence_integrity.get("evidence_integrity_ready") is True
            or cameo_cli_status.get("evidence_integrity_ready") is True
        ),
        "cameo_evidence_integrity_blocker_count": _int(cameo_evidence_integrity.get("blocker_count")),
        "cameo_evidence_integrity_artifact": cameo_evidence_integrity_path if cameo_evidence_integrity_packet else "",
        "cameo_official_results_pending_honest": bool(
            cameo_evidence_integrity.get("official_results_pending_honest") is True
            or cameo_cli_status.get("official_results_pending_honest") is True
        ),
        "cameo_no_local_native_accuracy_substitution": bool(
            cameo_evidence_integrity.get("no_local_native_accuracy_substitution") is True
            or cameo_cli_status.get("no_local_native_accuracy_substitution") is True
        ),
        "cameo_cli_evidence_integrity_ready": bool(cameo_cli_status.get("evidence_integrity_ready") is True),
        "cameo_cli_official_results_pending_honest": bool(cameo_cli_status.get("official_results_pending_honest") is True),
        "cameo_cli_no_local_native_accuracy_substitution": bool(
            cameo_cli_status.get("no_local_native_accuracy_substitution") is True
        ),
        "cleanup_cli_status_set_status": _text(cleanup_cli_status.get("status")),
        "cleanup_cli_approval_token_count": _int(cleanup_cli_status.get("approval_token_count")),
        "cleanup_cli_approval_reclaim_size_gb": round(_float(cleanup_cli_status.get("approval_reclaim_size_gb")), 3),
        "cleanup_cli_postcheck_contract_ready": bool(cleanup_cli_status.get("postcheck_contract_ready") is True),
        "cleanup_cli_protected_payload_size_gb": round(_float(cleanup_cli_status.get("protected_payload_size_gb")), 3),
        "cleanup_cli_protected_policy_change_required_count": _int(
            cleanup_cli_status.get("protected_policy_change_required_count")
        ),
        "execution_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Repair blocked lanes before treating the full commercial/CAMEO/cleanup objective as ready."
            if status == "blocked_goal_readiness"
            else (
                "Collect operator approvals or official CAMEO results before executing pending lanes."
                if status == "goal_readiness_pending_operator_or_external_results"
                else "All tracked lanes are evidence-ready; perform a full completion audit before claiming the objective is complete."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Goal Readiness Rollup",
        "",
        f"- status: `{s['status']}`",
        f"- lane_count: `{s['lane_count']}`",
        f"- blocked_lane_count: `{s['blocked_lane_count']}`",
        f"- operator_approval_pending_count: `{s['operator_approval_pending_count']}`",
        f"- external_results_pending_count: `{s['external_results_pending_count']}`",
        f"- total_reclaim_size_gb: `{s['total_reclaim_size_gb']}`",
        f"- cleanup_postcheck_contract_status: `{s['cleanup_postcheck_contract_status']}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_row_count: `{s['cleanup_postcheck_row_count']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- cleanup_postcheck_global_refresh_command_count: `{s['cleanup_postcheck_global_refresh_command_count']}`",
        f"- product_cli_status_set_status: `{s['product_cli_status_set_status']}`",
        f"- product_cli_approval_token_count: `{s['product_cli_approval_token_count']}`",
        f"- product_cli_operations_blocked_stage_count: `{s['product_cli_operations_blocked_stage_count']}`",
        f"- product_operational_quality_status: `{s['product_operational_quality_status']}`",
        f"- product_operational_quality_ready: `{s['product_operational_quality_ready']}`",
        f"- product_operational_quality_blocker_count: `{s['product_operational_quality_blocker_count']}`",
        f"- cameo_cli_status_set_status: `{s['cameo_cli_status_set_status']}`",
        f"- cameo_cli_approval_token_count: `{s['cameo_cli_approval_token_count']}`",
        f"- cameo_cli_official_result_required: `{s['cameo_cli_official_result_required']}`",
        f"- cameo_evidence_integrity_status: `{s['cameo_evidence_integrity_status']}`",
        f"- cameo_evidence_integrity_ready: `{s['cameo_evidence_integrity_ready']}`",
        f"- cameo_evidence_integrity_blocker_count: `{s['cameo_evidence_integrity_blocker_count']}`",
        f"- cameo_official_results_pending_honest: `{s['cameo_official_results_pending_honest']}`",
        f"- cameo_no_local_native_accuracy_substitution: `{s['cameo_no_local_native_accuracy_substitution']}`",
        f"- cleanup_cli_status_set_status: `{s['cleanup_cli_status_set_status']}`",
        f"- cleanup_cli_approval_token_count: `{s['cleanup_cli_approval_token_count']}`",
        f"- cleanup_cli_approval_reclaim_size_gb: `{s['cleanup_cli_approval_reclaim_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Lanes",
        "",
        "| lane | lane_status | observed_status | blockers | reclaim_size_gb | artifact |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane_id']}` | `{row['lane_status']}` | `{row['observed_status']}` | "
            f"`{row['blocker_count']}` | `{row['reclaim_size_gb']}` | `{row['artifact_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a top-level goal readiness rollup.")
    parser.add_argument("--product-readiness-json", default=DEFAULT_PRODUCT_READINESS_JSON)
    parser.add_argument("--product-preflight-json", default=DEFAULT_PRODUCT_PREFLIGHT_JSON)
    parser.add_argument("--product-bundle-contract-json", default=DEFAULT_PRODUCT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--product-delivery-evidence-json", default=DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--product-pilot-packet-json", default=DEFAULT_PRODUCT_PILOT_PACKET_JSON)
    parser.add_argument("--product-architecture-json", default=DEFAULT_PRODUCT_ARCHITECTURE_JSON)
    parser.add_argument("--product-operational-quality-json", default=DEFAULT_PRODUCT_OPERATIONAL_QUALITY_JSON)
    parser.add_argument("--cameo-readiness-json", default=DEFAULT_CAMEO_READINESS_JSON)
    parser.add_argument("--cameo-evidence-integrity-json", default=DEFAULT_CAMEO_EVIDENCE_INTEGRITY_JSON)
    parser.add_argument("--cameo-repair-json", default=DEFAULT_CAMEO_REPAIR_JSON)
    parser.add_argument("--cameo-input-kit-json", default=DEFAULT_CAMEO_INPUT_KIT_JSON)
    parser.add_argument("--cameo-input-validation-json", default=DEFAULT_CAMEO_INPUT_VALIDATION_JSON)
    parser.add_argument("--cameo-repair-preflight-json", default=DEFAULT_CAMEO_REPAIR_PREFLIGHT_JSON)
    parser.add_argument("--cameo-capability-preflight-json", default=DEFAULT_CAMEO_CAPABILITY_PREFLIGHT_JSON)
    parser.add_argument("--transition-cleanup-json", default=DEFAULT_TRANSITION_CLEANUP_JSON)
    parser.add_argument("--transition-cleanup-preflight-json", default=DEFAULT_TRANSITION_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--ligand-cleanup-json", default=DEFAULT_LIGAND_CLEANUP_JSON)
    parser.add_argument("--ligand-cleanup-preflight-json", default=DEFAULT_LIGAND_CLEANUP_PREFLIGHT_JSON)
    parser.add_argument("--cleanup-postcheck-json", default=DEFAULT_CLEANUP_POSTCHECK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_rollup(
        product_readiness_packet=_read_json_if_present(args.product_readiness_json),
        product_preflight_packet=_read_json_if_present(args.product_preflight_json),
        product_bundle_contract_packet=_read_json_if_present(args.product_bundle_contract_json),
        product_delivery_evidence_packet=_read_json_if_present(args.product_delivery_evidence_json),
        product_pilot_packet=_read_json_if_present(args.product_pilot_packet_json),
        product_architecture_packet=_read_json_if_present(args.product_architecture_json),
        product_operational_quality_packet=_read_json_if_present(args.product_operational_quality_json),
        cameo_readiness_packet=_read_json_if_present(args.cameo_readiness_json),
        cameo_evidence_integrity_packet=_read_json_if_present(args.cameo_evidence_integrity_json),
        cameo_repair_packet=_read_json_if_present(args.cameo_repair_json),
        cameo_input_kit_packet=_read_json_if_present(args.cameo_input_kit_json),
        cameo_input_validation_packet=_read_json_if_present(args.cameo_input_validation_json),
        cameo_repair_preflight_packet=_read_json_if_present(args.cameo_repair_preflight_json),
        cameo_capability_preflight_packet=_read_json_if_present(args.cameo_capability_preflight_json),
        transition_cleanup_packet=_read_json_if_present(args.transition_cleanup_json),
        transition_cleanup_preflight_packet=_read_json_if_present(args.transition_cleanup_preflight_json),
        ligand_cleanup_packet=_read_json_if_present(args.ligand_cleanup_json),
        ligand_cleanup_preflight_packet=_read_json_if_present(args.ligand_cleanup_preflight_json),
        cleanup_postcheck_packet=_read_json_if_present(args.cleanup_postcheck_json),
        product_cli_status_packet=build_product_cli_all_status(),
        cameo_cli_status_packet=build_cameo_cli_all_status(),
        cleanup_cli_status_packet=build_cleanup_cli_all_status(),
        product_readiness_path=args.product_readiness_json,
        product_preflight_path=args.product_preflight_json,
        product_bundle_contract_path=args.product_bundle_contract_json,
        product_delivery_evidence_path=args.product_delivery_evidence_json,
        product_pilot_packet_path=args.product_pilot_packet_json,
        product_architecture_path=args.product_architecture_json,
        product_operational_quality_path=args.product_operational_quality_json,
        cameo_readiness_path=args.cameo_readiness_json,
        cameo_evidence_integrity_path=args.cameo_evidence_integrity_json,
        cameo_repair_path=args.cameo_repair_json,
        cameo_input_kit_path=args.cameo_input_kit_json,
        cameo_input_validation_path=args.cameo_input_validation_json,
        cameo_repair_preflight_path=args.cameo_repair_preflight_json,
        cameo_capability_preflight_path=args.cameo_capability_preflight_json,
        transition_cleanup_path=args.transition_cleanup_json,
        transition_cleanup_preflight_path=args.transition_cleanup_preflight_json,
        ligand_cleanup_path=args.ligand_cleanup_json,
        ligand_cleanup_preflight_path=args.ligand_cleanup_preflight_json,
        cleanup_postcheck_path=args.cleanup_postcheck_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
