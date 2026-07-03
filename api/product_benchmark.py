from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-benchmark"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "product_rollout_execution_smoke_receipt_current.json"
)
PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_public_benchmark_work_order_current.json"
PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT = (
    ROOT / "runs" / "public_benchmark_external_receipts_audit_current.json"
)
PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT = (
    ROOT / "runs" / "public_benchmark_receipt_attach_packet_current.json"
)
EXTERNAL_METRIC_SCORECARD_ARTIFACT = ROOT / "runs" / "external_metric_scorecard_current.json"
PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT = ROOT / "runs" / "product_trajectory_sla_contract_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
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


def _bool_true(value: Any) -> bool:
    return bool(value is True)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _split_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [
            part.strip()
            for part in value.replace(";", ",").split(",")
            if part.strip()
        ]
    return []


def _float_or_none(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "pass", "ready"}
    return bool(value)


def _blocked_public_benchmark_steps(rows: list[Any]) -> list[dict[str, Any]]:
    blocked_steps: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("ready") is True and str(row.get("status") or "") == "ready":
            continue
        blocked_steps.append(
            {
                "step_id": str(row.get("step_id") or ""),
                "status": str(row.get("status") or ""),
                "ready": _bool_true(row.get("ready")),
                "blocker": str(row.get("blocker") or ""),
                "evidence_artifact": str(row.get("evidence_artifact") or ""),
                "primary_metric": str(row.get("primary_metric") or ""),
                "secondary_metric": str(row.get("secondary_metric") or ""),
                "next_required_step": str(row.get("next_required_step") or ""),
            }
        )
    return blocked_steps


def _field_work_order_rows(rows: list[Any]) -> list[dict[str, Any]]:
    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        work_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "field_name": str(row.get("field_name") or ""),
                "pending_row_count": _int(row.get("pending_row_count")),
                "source_artifact": str(row.get("source_artifact") or ""),
                "operator_csv": str(row.get("operator_csv") or ""),
                "required_value": str(row.get("required_value") or ""),
                "approval_token_required": str(row.get("approval_token_required") or ""),
                "required_action": str(row.get("required_action") or ""),
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return work_rows


def _receipt_attach_lane_rows(rows: list[Any]) -> list[dict[str, Any]]:
    lane_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ready = bool(row.get("ready") is True and str(row.get("status") or "") == "ready")
        lane_rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "status": str(row.get("status") or ""),
                "ready": ready,
                "blocker": str(row.get("blocker") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "operator_csv": str(row.get("operator_csv") or ""),
                "row_count": _int(row.get("row_count")),
                "pending_value_count": _int(row.get("pending_value_count")),
                "pending_metadata_count": _int(row.get("pending_metadata_count")),
                "pending_license_count": _int(row.get("pending_license_count")),
                "pending_approval_token_count": _int(
                    row.get("pending_approval_token_count")
                ),
                "approval_token_required": str(row.get("approval_token_required") or ""),
                "next_required_step": str(row.get("next_required_step") or ""),
                "operator_action_required": not ready,
                "execution_enabled": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return lane_rows


def _metric_gate_pass(value: float | None, threshold: float | None) -> bool | None:
    if value is None or threshold is None:
        return None
    return value >= threshold


def _suite_scorecard_ready(row: dict[str, Any]) -> bool:
    status = str(row.get("scorecard_status") or "")
    value = _float_or_none(row.get("primary_metric_value"))
    threshold = _float_or_none(row.get("primary_metric_threshold"))
    gate_pass = _metric_gate_pass(value, threshold)
    return bool(
        row.get("work_order_status") == "ready"
        and _bool_value(row.get("local_artifact_preflight_ready"))
        and _bool_value(row.get("result_provenance_present"))
        and "pass" in status
        and not _split_text_list(row.get("scorecard_blockers"))
        and not _split_text_list(row.get("blocker"))
        and gate_pass is not False
    )


def _public_benchmark_suite_rows(rows: list[Any]) -> list[dict[str, Any]]:
    suite_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _float_or_none(row.get("primary_metric_value"))
        threshold = _float_or_none(row.get("primary_metric_threshold"))
        gate_pass = _metric_gate_pass(value, threshold)
        blockers = _split_text_list(row.get("scorecard_blockers")) + _split_text_list(
            row.get("blocker")
        )
        suite_rows.append(
            {
                "suite_id": str(row.get("suite_id") or ""),
                "benchmark_family": str(row.get("benchmark_family") or ""),
                "required_for_commercial_release": _bool_value(
                    row.get("required_for_commercial_release")
                ),
                "work_order_status": str(row.get("work_order_status") or ""),
                "scorecard_status": str(row.get("scorecard_status") or ""),
                "scorecard_ready": _suite_scorecard_ready(row),
                "primary_metric": str(row.get("primary_metric") or ""),
                "primary_metric_value": value,
                "primary_metric_threshold": threshold,
                "primary_metric_gate_pass": gate_pass,
                "scorecard_row_csv": str(row.get("scorecard_row_csv") or ""),
                "scorecard_artifact": str(row.get("scorecard_row") or row.get("result_artifact") or ""),
                "materialization_status": str(row.get("materialization_status") or ""),
                "materialization_manifest": str(row.get("materialization_manifest") or ""),
                "result_provenance_json": str(row.get("result_provenance_json") or ""),
                "result_provenance_present": _bool_value(row.get("result_provenance_present")),
                "local_artifact_preflight_ready": _bool_value(
                    row.get("local_artifact_preflight_ready")
                ),
                "missing_local_input_artifact_count": _int(
                    row.get("missing_local_input_artifact_count")
                ),
                "missing_local_output_artifact_count": _int(
                    row.get("missing_local_output_artifact_count")
                ),
                "blockers": blockers,
                "operator_action_required": not _suite_scorecard_ready(row),
                "recommended_next_action": (
                    "review_public_benchmark_scorecard"
                    if _suite_scorecard_ready(row)
                    else str(row.get("refresh_command") or row.get("scorecard_command") or "")
                ),
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
            }
        )
    return suite_rows


def _public_benchmark_scorecard_blocker_rows(
    suite_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocker_rows: list[dict[str, Any]] = []
    for row in suite_rows:
        if row["scorecard_ready"]:
            continue
        blockers = row["blockers"] or ["suite_scorecard_not_ready"]
        blocker_rows.append(
            {
                "blocker_id": f"public_benchmark_scorecard:{row['suite_id']}",
                "blocker_type": "suite_scorecard",
                "severity": "blocker",
                "suite_id": row["suite_id"],
                "scorecard_status": row["scorecard_status"],
                "primary_metric": row["primary_metric"],
                "primary_metric_value": row["primary_metric_value"],
                "primary_metric_threshold": row["primary_metric_threshold"],
                "primary_metric_gate_pass": row["primary_metric_gate_pass"],
                "blockers": blockers,
                "operator_action": row["recommended_next_action"],
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return blocker_rows


def _external_receipt_blocker_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    if not summary:
        return []
    blocker_rows: list[dict[str, Any]] = []
    blockers = _string_list(summary.get("blockers"))
    if not blockers and summary.get("external_benchmark_receipts_ready") is not True:
        blockers = ["external_benchmark_receipts_not_ready"]
    for blocker in blockers:
        blocker_id, _, reason = blocker.partition(":")
        blocker_rows.append(
            {
                "blocker_id": blocker_id or blocker,
                "blocker_type": "external_receipt",
                "severity": "blocker",
                "reason": reason or blocker,
                "operator_action": str(
                    summary.get("primary_blocker_next_required_step")
                    or summary.get("next_required_step")
                    or ""
                ),
                "claim_promotion_allowed": False,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return blocker_rows


def _receipt_attach_surface(
    packet: dict[str, Any],
    *,
    fallback_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _summary(packet)
    packet_present = bool(summary)
    embedded_fallback = False
    if not summary and isinstance(fallback_packet, dict):
        fallback_summary = _summary(fallback_packet)
        if fallback_summary:
            summary = fallback_summary
            packet = fallback_packet
            embedded_fallback = True
    rows = packet.get("field_work_order_rows") if isinstance(packet.get("field_work_order_rows"), list) else []
    lane_rows = _receipt_attach_lane_rows(
        packet.get("rows")
        if packet_present and isinstance(packet.get("rows"), list)
        else packet.get("receipt_attach_lane_rows")
        if isinstance(packet.get("receipt_attach_lane_rows"), list)
        else []
    )
    blocked_lane_rows = [row for row in lane_rows if row["operator_action_required"]]
    return {
        "receipt_attach_packet_artifact_path": str(PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT),
        "receipt_attach_packet_present": packet_present,
        "receipt_attach_embedded_in_audit": embedded_fallback,
        "receipt_attach_packet_status": str(summary.get("status") or ""),
        "receipt_attach_packet_ready": bool(summary.get("receipt_attach_packet_ready") is True),
        "receipt_attach_blocker_count": _int(
            summary.get("receipt_attach_blocker_count")
            if summary.get("receipt_attach_blocker_count") is not None
            else summary.get("blocker_count")
        ),
        "receipt_attach_blockers": _string_list(summary.get("blockers")),
        "receipt_attach_primary_blocker_id": str(
            summary.get("receipt_attach_primary_blocker_id")
            or summary.get("primary_blocker_id")
            or ""
        ),
        "receipt_attach_primary_blocker": str(
            summary.get("receipt_attach_primary_blocker")
            or summary.get("primary_blocker")
            or ""
        ),
        "receipt_attach_next_required_step": str(summary.get("next_required_step") or ""),
        "receipt_attach_lane_row_count": len(lane_rows),
        "receipt_attach_blocked_lane_count": len(blocked_lane_rows),
        "receipt_attach_primary_blocked_lane_row": (
            blocked_lane_rows[0] if blocked_lane_rows else {}
        ),
        "receipt_attach_lane_rows": lane_rows,
        "field_work_order_ready": bool(summary.get("field_work_order_ready") is True),
        "field_work_order_row_count": _int(summary.get("field_work_order_row_count")),
        "field_work_order_pending_field_count": _int(
            summary.get("field_work_order_pending_field_count")
        ),
        "field_work_order_primary_lane_id": str(
            summary.get("field_work_order_primary_lane_id") or ""
        ),
        "field_work_order_primary_field_name": str(
            summary.get("field_work_order_primary_field_name") or ""
        ),
        "field_work_order_primary_pending_row_count": _int(
            summary.get("field_work_order_primary_pending_row_count")
        ),
        "field_work_order_primary_required_value": str(
            summary.get("field_work_order_primary_required_value") or ""
        ),
        "field_work_order_primary_required_action": str(
            summary.get("field_work_order_primary_required_action") or ""
        ),
        "field_work_order_primary_approval_token_required": str(
            summary.get("field_work_order_primary_approval_token_required") or ""
        ),
        "field_work_order_primary_operator_csv": str(
            summary.get("field_work_order_primary_operator_csv") or ""
        ),
        "field_work_order_primary_source_artifact": str(
            summary.get("field_work_order_primary_source_artifact") or ""
        ),
        "field_work_order_rows": _field_work_order_rows(rows),
        "metric_source_receipt_csv": str(summary.get("metric_source_receipt_csv") or ""),
        "metric_source_receipt_row_count": _int(summary.get("metric_source_receipt_row_count")),
        "metric_source_receipt_blocked_row_count": _int(
            summary.get("metric_source_receipt_blocked_row_count")
        ),
        "metric_source_receipt_manual_field_pending_count": _int(
            summary.get("metric_source_receipt_manual_field_pending_count")
        ),
        "metric_source_receipt_approval_token_pending_count": _int(
            summary.get("metric_source_receipt_approval_token_pending_count")
        ),
    }


@router.get("/external-metrics")
async def get_product_external_metrics() -> dict[str, Any]:
    packet = _read_json_object(EXTERNAL_METRIC_SCORECARD_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_external_metric_scorecard",
            "artifact_path": str(EXTERNAL_METRIC_SCORECARD_ARTIFACT),
            "claim_scope": "",
            "claim_promotion_allowed": False,
            "row_count": 0,
            "blocked_row_count": 0,
            "evaluated_row_count": 0,
            "rows": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product external-metrics endpoint only; the local external metric scorecard artifact is missing. "
                "It does not compute DockQ/LDDT/MolProbity or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(EXTERNAL_METRIC_SCORECARD_ARTIFACT),
        "claim_scope": summary.get("claim_scope", ""),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "row_count": int(summary.get("row_count") or len(rows)),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "evaluated_row_count": int(summary.get("evaluated_row_count") or 0),
        "topology_fidelity_required": summary.get("topology_fidelity_required", ""),
        "rows": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/public-benchmark-external-receipts-audit")
async def get_product_public_benchmark_external_receipts_audit() -> dict[str, Any]:
    packet = _read_json_object(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT)
    receipt_attach_packet = _read_json_object(PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT)
    receipt_attach_surface = _receipt_attach_surface(
        receipt_attach_packet,
        fallback_packet=packet,
    )
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_public_benchmark_external_receipts_audit",
            "artifact_path": str(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT),
            "external_benchmark_receipts_ready": False,
            "claim_promotion_allowed": False,
            "step_count": 7,
            "ready_step_count": 0,
            "blocked_step_count": 7,
            "blocker_count": 1,
            "blockers": ["public_benchmark_external_receipts_audit_missing"],
            "primary_blocker_id": "public_benchmark_external_receipts_audit_missing",
            "primary_blocker": "public_benchmark_external_receipts_audit_missing",
            "receipt_blocked_row_count": 0,
            "receipt_manual_field_pending_count": 0,
            "receipt_approval_token_pending_count": 0,
            "phase2_harness_ready": False,
            "materialization_manifest_ready": False,
            "subset_dry_run_ready": False,
            "pose_rmsd_2a_5a_ready": False,
            "posebusters_validity_ready": False,
            "vina_gnina_same_input_comparison_ready": False,
            "benchmark_receipt_attach_ready": False,
            "benchmark_ledger_review_ready": False,
            "vina_gnina_comparison_adapter_score_evidence_ready": False,
            "vina_gnina_score_template_receipt_status": "",
            "vina_gnina_score_template_receipt_ready": False,
            "vina_gnina_score_template_filled_score_row_count": 0,
            "vina_gnina_score_value_pending_count": 0,
            "vina_gnina_license_ok_pending_count": 0,
            "vina_gnina_operator_metadata_pending_count": 0,
            "vina_gnina_approval_token_pending_count": 0,
            "vina_gnina_pending_field_count": 0,
            "vina_gnina_pending_field_counts": {},
            "benchmark_ledger_entry_count": 0,
            "benchmark_ledger_external_safe_count": 0,
            **receipt_attach_surface,
            "blocked_steps": [],
            "steps": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product public benchmark external receipts audit endpoint only; the local audit artifact "
                "is missing. It does not download data, run docking, run Vina/GNINA, approve receipts, "
                "or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT),
        "external_benchmark_receipts_ready": bool(summary.get("external_benchmark_receipts_ready") is True),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "step_count": int(summary.get("step_count") or 0),
        "ready_step_count": int(summary.get("ready_step_count") or 0),
        "blocked_step_count": int(summary.get("blocked_step_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "primary_blocker_id": summary.get("primary_blocker_id", ""),
        "primary_blocker": summary.get("primary_blocker", ""),
        "primary_blocker_next_required_step": summary.get("primary_blocker_next_required_step", ""),
        "next_required_step": summary.get("next_required_step", ""),
        "pose_count": int(summary.get("pose_count") or 0),
        "pose_success_rate": summary.get("pose_success_rate"),
        "posebusters_valid_rate": summary.get("posebusters_valid_rate"),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "receipt_blocked_row_count": int(summary.get("receipt_blocked_row_count") or 0),
        "receipt_manual_field_pending_count": int(summary.get("receipt_manual_field_pending_count") or 0),
        "receipt_approval_token_pending_count": int(summary.get("receipt_approval_token_pending_count") or 0),
        "phase2_harness_ready": _bool_true(summary.get("phase2_harness_ready")),
        "phase2_harness_audit_status": summary.get("phase2_harness_audit_status", ""),
        "materialization_manifest_ready": _bool_true(summary.get("materialization_manifest_ready")),
        "subset_dry_run_ready": _bool_true(summary.get("subset_dry_run_ready")),
        "pose_rmsd_2a_5a_ready": _bool_true(summary.get("pose_rmsd_2a_5a_ready")),
        "posebusters_validity_ready": _bool_true(summary.get("posebusters_validity_ready")),
        "vina_gnina_same_input_comparison_ready": _bool_true(
            summary.get("vina_gnina_same_input_comparison_ready")
        ),
        "benchmark_receipt_attach_ready": _bool_true(summary.get("benchmark_receipt_attach_ready")),
        "benchmark_ledger_review_ready": _bool_true(summary.get("benchmark_ledger_review_ready")),
        "scorecard_status": summary.get("scorecard_status", ""),
        "vina_gnina_comparison_adapter_contract_ready": bool(
            summary.get("vina_gnina_comparison_adapter_contract_ready") is True
        ),
        "vina_gnina_comparison_adapter_score_evidence_ready": bool(
            summary.get("vina_gnina_comparison_adapter_score_evidence_ready") is True
        ),
        "comparison_adapter_same_input_row_count_match": bool(
            summary.get("comparison_adapter_same_input_row_count_match") is True
        ),
        "vina_gnina_score_template_csv": summary.get("vina_gnina_score_template_csv", ""),
        "vina_gnina_score_template_receipt_json": summary.get(
            "vina_gnina_score_template_receipt_json", ""
        ),
        "vina_gnina_score_template_receipt_status": summary.get(
            "vina_gnina_score_template_receipt_status", ""
        ),
        "vina_gnina_score_template_receipt_ready": _bool_true(
            summary.get("vina_gnina_score_template_receipt_ready")
        ),
        "vina_gnina_score_template_validation_ready": _bool_true(
            summary.get("vina_gnina_score_template_validation_ready")
        ),
        "vina_gnina_score_template_filled_score_row_count": _int(
            summary.get("vina_gnina_score_template_filled_score_row_count")
        ),
        "vina_gnina_score_value_pending_count": _int(
            summary.get("vina_gnina_score_value_pending_count")
        ),
        "vina_gnina_license_ok_pending_count": _int(
            summary.get("vina_gnina_license_ok_pending_count")
        ),
        "vina_gnina_operator_metadata_pending_count": _int(
            summary.get("vina_gnina_operator_metadata_pending_count")
        ),
        "vina_gnina_approval_token_pending_count": _int(
            summary.get("vina_gnina_approval_token_pending_count")
        ),
        "vina_gnina_pending_field_count": _int(summary.get("vina_gnina_pending_field_count")),
        "vina_gnina_pending_field_counts": (
            summary.get("vina_gnina_pending_field_counts")
            if isinstance(summary.get("vina_gnina_pending_field_counts"), dict)
            else {}
        ),
        "benchmark_ledger_entry_count": _int(summary.get("benchmark_ledger_entry_count")),
        "benchmark_ledger_external_safe_count": _int(
            summary.get("benchmark_ledger_external_safe_count")
        ),
        **receipt_attach_surface,
        "blocked_steps": _blocked_public_benchmark_steps(rows),
        "steps": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/public-benchmark")
async def get_product_public_benchmark() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    receipts_summary = _summary(_read_json_object(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT))
    if not summary:
        return {
            "status": "missing_product_public_benchmark_work_order",
            "artifact_path": str(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT),
            "scorecard_panel_ready": False,
            "suite_row_count": 0,
            "suite_green_row_count": 0,
            "suite_blocked_row_count": 0,
            "scorecard_blocker_row_count": 1,
            "scorecard_blocker_rows": [
                {
                    "blocker_id": "product_public_benchmark_work_order_missing",
                    "blocker_type": "missing_artifact",
                    "severity": "blocker",
                    "operator_action": "build_product_public_benchmark_work_order",
                    "claim_promotion_allowed": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                }
            ],
            "external_receipts_status": "",
            "external_receipts_ready": False,
            "external_receipts_blocker_count": 0,
            "external_receipt_blocker_row_count": 0,
            "external_receipt_blocker_rows": [],
            "external_beta_claim_allowed": False,
            "public_benchmark_validation_ready": False,
            "open_suite_count": 0,
            "materialization_required_suite_count": 0,
            "scorecard_required_suite_count": 0,
            "continuous_validation_command_count": 0,
            "continuous_validation_command": "",
            "suite_run_command_count": 0,
            "suite_materialization_run_command_count": 0,
            "suite_scorecard_command_count": 0,
            "suite_result_provenance_command_count": 0,
            "suite_result_provenance_present_count": 0,
            "suite_threshold_count": 0,
            "suite_blocker_count": 0,
            "suite_materialization_manifest_count": 0,
            "suite_scorecard_row_csv_count": 0,
            "suite_required_output_count": 0,
            "suite_no_external_dependency_count": 0,
            "local_artifact_preflight_ready_suite_count": 0,
            "local_artifact_preflight_blocked_suite_count": 0,
            "missing_local_input_artifact_count": 0,
            "missing_local_output_artifact_count": 0,
            "missing_local_input_artifacts": [],
            "missing_local_output_artifacts": [],
            "requires_24h_server": False,
            "requires_competition_season": False,
            "requires_paid_vps": False,
            "suite_rows": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product public-benchmark endpoint only; the local public benchmark work-order artifact is missing or invalid. "
                "It does not download datasets, run docking, compute metrics, or mutate external state."
            ),
        }
    suite_rows = _public_benchmark_suite_rows(rows)
    scorecard_blocker_rows = _public_benchmark_scorecard_blocker_rows(suite_rows)
    external_receipt_blocker_rows = _external_receipt_blocker_rows(receipts_summary)
    scorecard_panel_ready = bool(
        summary.get("public_benchmark_validation_ready") is True
        and suite_rows
        and not scorecard_blocker_rows
    )
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT),
        "source_public_benchmark_status": summary.get("source_public_benchmark_status", ""),
        "source_public_benchmark_json": summary.get("source_public_benchmark_json", ""),
        "scorecard_panel_ready": scorecard_panel_ready,
        "suite_row_count": len(suite_rows),
        "suite_green_row_count": sum(1 for row in suite_rows if row["scorecard_ready"]),
        "suite_blocked_row_count": sum(1 for row in suite_rows if not row["scorecard_ready"]),
        "scorecard_blocker_row_count": len(scorecard_blocker_rows),
        "scorecard_blocker_rows": scorecard_blocker_rows,
        "external_receipts_status": str(receipts_summary.get("status") or ""),
        "external_receipts_ready": bool(
            receipts_summary.get("external_benchmark_receipts_ready") is True
        ),
        "external_receipts_blocker_count": _int(receipts_summary.get("blocker_count")),
        "external_receipt_blocker_row_count": len(external_receipt_blocker_rows),
        "external_receipt_blocker_rows": external_receipt_blocker_rows,
        "external_beta_claim_allowed": bool(
            receipts_summary.get("external_benchmark_receipts_ready") is True
            and receipts_summary.get("claim_promotion_allowed") is True
        ),
        "public_benchmark_validation_ready": bool(summary.get("public_benchmark_validation_ready") is True),
        "suite_count": int(summary.get("suite_count") or 0),
        "open_suite_count": int(summary.get("open_suite_count") or 0),
        "materialization_required_suite_count": int(summary.get("materialization_required_suite_count") or 0),
        "scorecard_required_suite_count": int(summary.get("scorecard_required_suite_count") or 0),
        "continuous_validation_command_count": int(summary.get("continuous_validation_command_count") or 0),
        "continuous_validation_command": summary.get("continuous_validation_command", ""),
        "scorecard_intake_sync_command": summary.get("scorecard_intake_sync_command", ""),
        "scorecard_row_csvs": list(summary.get("scorecard_row_csvs") or []),
        "suite_run_command_count": int(summary.get("suite_run_command_count") or 0),
        "suite_materialization_run_command_count": int(summary.get("suite_materialization_run_command_count") or 0),
        "suite_scorecard_command_count": int(summary.get("suite_scorecard_command_count") or 0),
        "suite_result_provenance_command_count": int(summary.get("suite_result_provenance_command_count") or 0),
        "suite_result_provenance_present_count": int(summary.get("suite_result_provenance_present_count") or 0),
        "suite_threshold_count": int(summary.get("suite_threshold_count") or 0),
        "suite_blocker_count": int(summary.get("suite_blocker_count") or 0),
        "suite_materialization_manifest_count": int(summary.get("suite_materialization_manifest_count") or 0),
        "suite_scorecard_row_csv_count": int(summary.get("suite_scorecard_row_csv_count") or 0),
        "suite_required_output_count": int(summary.get("suite_required_output_count") or 0),
        "suite_no_external_dependency_count": int(summary.get("suite_no_external_dependency_count") or 0),
        "local_artifact_preflight_ready_suite_count": int(
            summary.get("local_artifact_preflight_ready_suite_count") or 0
        ),
        "local_artifact_preflight_blocked_suite_count": int(
            summary.get("local_artifact_preflight_blocked_suite_count") or 0
        ),
        "missing_local_input_artifact_count": int(summary.get("missing_local_input_artifact_count") or 0),
        "missing_local_output_artifact_count": int(summary.get("missing_local_output_artifact_count") or 0),
        "missing_local_input_artifacts": list(summary.get("missing_local_input_artifacts") or []),
        "missing_local_output_artifacts": list(summary.get("missing_local_output_artifacts") or []),
        "requires_24h_server": bool(summary.get("requires_24h_server") is True),
        "requires_competition_season": bool(summary.get("requires_competition_season") is True),
        "requires_paid_vps": bool(summary.get("requires_paid_vps") is True),
        "requires_institution_registration": bool(summary.get("requires_institution_registration") is True),
        "download_executed": bool(summary.get("download_executed") is True),
        "suite_rows": suite_rows,
        "suites": rows,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/trajectory-sla-contract")
async def get_product_trajectory_sla_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_trajectory_sla_contract",
            "artifact_path": str(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT),
            "production_trajectory_sla_ready": False,
            "sla_claim_tier": "",
            "restricted_family_sla_allowed": False,
            "broad_platform_sla_allowed": False,
            "candidate_artifact_count": 0,
            "ready_run_count": 0,
            "qualified_ready_run_count": 0,
            "required_families": [],
            "ready_families": [],
            "qualified_ready_families": [],
            "missing_families": [],
            "missing_qualified_families": [],
            "minimum_ready_run_count": 0,
            "minimum_ready_rows_per_family": 0,
            "family_sla_matrix": [],
            "current_rocm_baseline_artifact": "",
            "current_rocm_baseline_ready": False,
            "current_rocm_baseline_family": "",
            "current_rocm_baseline_target_id": "",
            "current_rocm_baseline_production_trajectory_profile_enabled": False,
            "current_rocm_baseline_warning_count": 0,
            "current_rocm_baseline_claim_scope": "",
            "current_rocm_baseline_supports_restricted_family_sla": False,
            "current_rocm_baseline_supports_broad_platform_sla": False,
            "allowed_sla_claims": [],
            "blocked_sla_claims": ["missing_product_trajectory_sla_contract"],
            "customer_sla_disclosure_card": {},
            "customer_sla_disclosure_ready": False,
            "general_platform_sla_allowed": False,
            "restricted_sla_backed_by_historical_profile_artifacts": False,
            "rocm_baseline_profile_gap_acknowledged": False,
            "single_baseline_only": False,
            "trajectory_sla_rows": [],
            "next_required_step": "Run python3 tools/build_product_trajectory_sla_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "benchmark_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product trajectory-SLA-contract endpoint only; the local trajectory SLA artifact is missing. "
                "It does not launch docking, rerun trajectories, execute benchmarks, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT),
        "production_trajectory_sla_ready": bool(summary.get("production_trajectory_sla_ready") is True),
        "sla_claim_tier": summary.get("sla_claim_tier", ""),
        "restricted_family_sla_allowed": bool(summary.get("restricted_family_sla_allowed") is True),
        "broad_platform_sla_allowed": bool(summary.get("broad_platform_sla_allowed") is True),
        "candidate_artifact_count": int(summary.get("candidate_artifact_count") or 0),
        "ready_run_count": int(summary.get("ready_run_count") or 0),
        "qualified_ready_run_count": int(summary.get("qualified_ready_run_count") or 0),
        "required_families": list(summary.get("required_families") or []),
        "ready_families": list(summary.get("ready_families") or []),
        "qualified_ready_families": list(summary.get("qualified_ready_families") or []),
        "missing_families": list(summary.get("missing_families") or []),
        "missing_qualified_families": list(summary.get("missing_qualified_families") or []),
        "minimum_ready_run_count": int(summary.get("minimum_ready_run_count") or 0),
        "minimum_ready_rows_per_family": int(summary.get("minimum_ready_rows_per_family") or 0),
        "family_sla_matrix": list(summary.get("family_sla_matrix") or []),
        "current_rocm_baseline_artifact": summary.get("current_rocm_baseline_artifact", ""),
        "current_rocm_baseline_ready": bool(summary.get("current_rocm_baseline_ready") is True),
        "current_rocm_baseline_family": summary.get("current_rocm_baseline_family", ""),
        "current_rocm_baseline_target_id": summary.get("current_rocm_baseline_target_id", ""),
        "current_rocm_baseline_production_trajectory_profile_enabled": bool(
            summary.get("current_rocm_baseline_production_trajectory_profile_enabled") is True
        ),
        "current_rocm_baseline_warning_count": int(summary.get("current_rocm_baseline_warning_count") or 0),
        "current_rocm_baseline_claim_scope": summary.get("current_rocm_baseline_claim_scope", ""),
        "current_rocm_baseline_supports_restricted_family_sla": bool(
            summary.get("current_rocm_baseline_supports_restricted_family_sla") is True
        ),
        "current_rocm_baseline_supports_broad_platform_sla": bool(
            summary.get("current_rocm_baseline_supports_broad_platform_sla") is True
        ),
        "allowed_sla_claims": list(summary.get("allowed_sla_claims") or []),
        "blocked_sla_claims": list(summary.get("blocked_sla_claims") or []),
        "customer_sla_disclosure_card": summary.get("customer_sla_disclosure_card")
        if isinstance(summary.get("customer_sla_disclosure_card"), dict)
        else {},
        "customer_sla_disclosure_ready": bool(summary.get("customer_sla_disclosure_ready") is True),
        "general_platform_sla_allowed": bool(summary.get("general_platform_sla_allowed") is True),
        "restricted_sla_backed_by_historical_profile_artifacts": bool(
            summary.get("restricted_sla_backed_by_historical_profile_artifacts") is True
        ),
        "rocm_baseline_profile_gap_acknowledged": bool(
            summary.get("rocm_baseline_profile_gap_acknowledged") is True
        ),
        "single_baseline_only": bool(summary.get("single_baseline_only") is True),
        "trajectory_sla_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/rollout-execution-smoke-receipt")
async def get_product_rollout_execution_smoke_receipt() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_rollout_execution_smoke_receipt",
            "artifact_path": str(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT),
            "rollout_execution_smoke_receipt_ready": False,
            "source_rollout_execution_readiness_status": "",
            "source_authorized_for_separate_operator_execution": False,
            "source_rollout_executed": False,
            "receipt_csv": "",
            "receipt_csv_present": False,
            "operator_template_csv": "",
            "receipt_row_count": 0,
            "ready_receipt_row_count": 0,
            "blocker_count": 1,
            "blockers": [],
            "target_environment": "",
            "rollout_executed": False,
            "image_pushed": False,
            "service_restarted": False,
            "pager_provider_contacted": False,
            "ingress_certificate_verified_live": False,
            "receipt_external_state_mutated": False,
            "rollout_receipt_rows": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product rollout execution smoke receipt endpoint only; the local receipt artifact is missing "
                "or invalid. It does not build images, push containers, apply manifests, restart services, "
                "contact providers, verify certificates, roll back services, upload, delete, commit, push, or "
                "mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT),
        "rollout_execution_smoke_receipt_ready": bool(
            summary.get("rollout_execution_smoke_receipt_ready") is True
        ),
        "source_rollout_execution_readiness_status": summary.get(
            "source_rollout_execution_readiness_status", ""
        ),
        "source_authorized_for_separate_operator_execution": bool(
            summary.get("source_authorized_for_separate_operator_execution") is True
        ),
        "source_rollout_executed": bool(summary.get("source_rollout_executed") is True),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_csv_present": bool(summary.get("receipt_csv_present") is True),
        "operator_template_csv": summary.get("operator_template_csv", ""),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "ready_receipt_row_count": int(summary.get("ready_receipt_row_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "target_environment": summary.get("target_environment", ""),
        "rollout_executed": bool(summary.get("rollout_executed") is True),
        "image_pushed": bool(summary.get("image_pushed") is True),
        "service_restarted": bool(summary.get("service_restarted") is True),
        "pager_provider_contacted": bool(summary.get("pager_provider_contacted") is True),
        "ingress_certificate_verified_live": bool(
            summary.get("ingress_certificate_verified_live") is True
        ),
        "receipt_external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "rollout_receipt_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
