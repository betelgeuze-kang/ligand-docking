from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-gpcr-hard-decoy"])

ROOT = Path(__file__).resolve().parents[1]
GPCR_HARD_DECOY_SUITE_ARTIFACT = ROOT / "runs" / "gpcr_hard_decoy_suite_current.json"
GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_ARTIFACT = (
    ROOT / "runs" / "gpcr_hard_decoy_claim_unlock_audit_current.json"
)

# Default required target set (matches betelgeuze_product.gpcr_hard_decoy_suite).
_DEFAULT_REQUIRED_TARGET_IDS = ["DRD2", "HTR2A", "OPRM1"]

_CLAIM_BOUNDARY_MISSING = (
    "GPCR hard-decoy endpoint only; the local report artifact is missing or invalid. "
    "It does not run scoring, generate decoys, relax thresholds, or promote broad-GPCR claims. "
    "broad GPCR/router remains locked."
)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return []


def _int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int(val) for key, val in value.items()}


def _promotion_work_order_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "lane_id": str(row.get("lane_id") or ""),
                "blocker": str(row.get("blocker") or ""),
                "required_action": str(row.get("required_action") or ""),
                "source_artifact": str(row.get("source_artifact") or ""),
                "operator_action_required": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
                "claim_boundary": str(row.get("claim_boundary") or ""),
            }
        )
    return rows


def _claim_unlock_surface(packet: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(packet)
    work_order_rows = _promotion_work_order_rows(packet.get("promotion_work_order_rows"))
    primary_work_order = work_order_rows[0] if work_order_rows else {}
    effective_metrics = summary.get("effective_phase3_metrics")
    if not isinstance(effective_metrics, dict):
        effective_metrics = {}
    promotion_blockers = _string_list(summary.get("promotion_blockers"))
    promotion_work_order_lane_count = _int(summary.get("promotion_work_order_lane_count")) or len(
        {row["lane_id"] for row in work_order_rows if row["lane_id"]}
    )
    return {
        "claim_unlock_audit_artifact_path": str(GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_ARTIFACT),
        "claim_unlock_audit_present": bool(summary),
        "claim_unlock_audit_status": str(summary.get("status") or ""),
        "hard_decoy_metric_claim_unlock_ready": bool(
            summary.get("hard_decoy_metric_claim_unlock_ready") is True
        ),
        "phase3_exit_metric_conditions_ready": bool(
            summary.get("phase3_exit_metric_conditions_ready") is True
        ),
        "operator_claim_review_ready": bool(summary.get("operator_claim_review_ready") is True),
        "broad_promotion_remains_locked": bool(
            summary.get("broad_promotion_remains_locked") is not False
        ),
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "claim_unlock_claim_promotion_allowed": False,
        "effective_phase3_metric_source": str(effective_metrics.get("source") or ""),
        "effective_phase3_ranking_pr_auc_ci_low": _float_or_none(
            effective_metrics.get("ranking_pr_auc_ci_low")
        ),
        "effective_phase3_top20_hit_rate": _float_or_none(
            effective_metrics.get("top20_hit_rate")
        ),
        "effective_phase3_decoys_above_positive_count": _int(
            effective_metrics.get("decoys_above_positive_count")
        ),
        "effective_phase3_anchor_margin_nonnegative": bool(
            effective_metrics.get("anchor_margin_nonnegative") is True
        ),
        "promotion_blocker_count": _int(summary.get("promotion_blocker_count"))
        or len(promotion_blockers),
        "promotion_blockers": promotion_blockers,
        "promotion_work_order_ready": bool(summary.get("promotion_work_order_ready") is True),
        "promotion_work_order_row_count": _int(summary.get("promotion_work_order_row_count"))
        or len(work_order_rows),
        "promotion_work_order_lane_count": promotion_work_order_lane_count,
        "promotion_work_order_primary_lane_id": str(
            summary.get("promotion_work_order_primary_lane_id")
            or primary_work_order.get("lane_id")
            or ""
        ),
        "promotion_work_order_primary_blocker": str(
            summary.get("promotion_work_order_primary_blocker")
            or primary_work_order.get("blocker")
            or ""
        ),
        "promotion_work_order_primary_required_action": str(
            primary_work_order.get("required_action") or ""
        ),
        "promotion_work_order_primary_source_artifact": str(
            primary_work_order.get("source_artifact") or ""
        ),
        "promotion_work_order_rows": work_order_rows,
        "claim_unlock_next_required_step": str(summary.get("next_required_step") or ""),
    }


def _target_rows(targets: list[Any]) -> list[dict[str, Any]]:
    target_rows: list[dict[str, Any]] = []
    for row in targets:
        if not isinstance(row, dict):
            continue
        blockers = _string_list(row.get("blockers"))
        claim_safe = bool(row.get("claim_safe") is True)
        gate_status = str(row.get("gate_status") or "")
        anchor_margin = _float_or_none(row.get("anchor_margin_a"))
        target_rows.append(
            {
                "target_id": str(row.get("target_id") or ""),
                "gate_status": gate_status,
                "claim_safe": claim_safe,
                "metric_gate_pass": bool(claim_safe and gate_status == "green"),
                "ranking_pr_auc": _float_or_none(row.get("ranking_pr_auc")),
                "ranking_pr_auc_ci_low": _float_or_none(row.get("ranking_pr_auc_ci_low")),
                "top20_hit_rate": _float_or_none(row.get("top20_hit_rate")),
                "decoys_above_positive_count": _int(row.get("decoys_above_positive_count")),
                "positive_target_rank": _int(row.get("positive_target_rank")),
                "positive_count": _int(row.get("positive_count")),
                "retained_positive_count": _int(row.get("retained_positive_count")),
                "retained_target_row_count": _int(row.get("retained_target_row_count")),
                "anchor_margin_a": anchor_margin,
                "positive_not_out_anchored": bool(anchor_margin is not None and anchor_margin >= 0.0),
                "positive_anchor_distance_a": _float_or_none(row.get("positive_anchor_distance_a")),
                "top_decoy_anchor_distance_a": _float_or_none(
                    row.get("top_decoy_anchor_distance_a")
                ),
                "top_decoy_retained_count": _int(row.get("top_decoy_retained_count")),
                "decoy_class_counts": _int_dict(row.get("decoy_class_counts")),
                "root_cause_tags": _string_list(row.get("root_cause_tags")),
                "blockers": blockers,
                "operator_action_required": bool((not claim_safe) or gate_status != "green" or blockers),
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return target_rows


def _blocker_rows(summary: dict[str, Any], target_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocker_rows: list[dict[str, Any]] = []
    if summary.get("claim_locked") is True or summary.get("family_claim_safe") is not True:
        blocker_rows.append(
            {
                "blocker_id": "broad_gpcr_claim_locked",
                "target_id": "",
                "blocker_type": "family_claim_lock",
                "status": str(summary.get("status") or ""),
                "claim_locked": bool(summary.get("claim_locked") is True),
                "claim_safe": False,
                "reason": str(summary.get("claim_lock_reason") or "family_claim_safe_not_true"),
                "next_required_step": str(
                    summary.get("claim_lock_reason")
                    or "Clear all target gates and ledger review before broad GPCR/router promotion."
                ),
                "operator_action_required": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    for target_id in _string_list(summary.get("missing_required_target_ids")):
        blocker_rows.append(
            {
                "blocker_id": "missing_required_target",
                "target_id": target_id,
                "blocker_type": "missing_target_row",
                "status": "missing",
                "claim_locked": True,
                "claim_safe": False,
                "reason": "required target row missing",
                "next_required_step": "Add the required target row and rerun the hard-decoy suite.",
                "operator_action_required": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    for row in target_rows:
        if row["operator_action_required"] is not True:
            continue
        blocker_rows.append(
            {
                "blocker_id": "target_metric_gate_blocked",
                "target_id": row["target_id"],
                "blocker_type": "target_metric_gate",
                "status": row["gate_status"],
                "claim_locked": True,
                "claim_safe": False,
                "reason": ",".join(row["blockers"]) or "target metric gate not green",
                "next_required_step": "Repair target-specific hard-decoy ranking, decoy separation, or anchor support evidence.",
                "operator_action_required": True,
                "execution_enabled": False,
                "docking_results_emitted": False,
                "external_state_mutated": False,
                "claim_promotion_allowed": False,
            }
        )
    return blocker_rows


@router.get("/gpcr-hard-decoy-suite-report")
async def get_product_gpcr_hard_decoy_suite_report() -> dict[str, Any]:
    """Return the read-only GPCR hard-decoy suite gate surface.

    Exposes the family claim decision (from ``runs/gpcr_hard_decoy_suite_current.json``,
    built by ``tools/product/build_gpcr_hard_decoy_suite_report.py``) so broad-GPCR
    readiness has one inspectable answer: whether the broad GPCR/router claim is
    still locked and which required target blocks it. Fail-closed when the
    artifact is missing/invalid. This route never promotes a broad-GPCR claim.
    """

    artifact = _read_json_object(GPCR_HARD_DECOY_SUITE_ARTIFACT)
    claim_unlock_packet = _read_json_object(GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_ARTIFACT)
    claim_unlock_surface = _claim_unlock_surface(claim_unlock_packet)
    summary = artifact.get("summary") if isinstance(artifact.get("summary"), dict) else {}
    targets = artifact.get("targets") if isinstance(artifact.get("targets"), list) else []
    if not artifact or not summary:
        return {
            "status": "missing_gpcr_hard_decoy_suite_report",
            "artifact_path": str(GPCR_HARD_DECOY_SUITE_ARTIFACT),
            "schema_version": "",
            "family_claim_safe": False,
            "required_target_ids": list(_DEFAULT_REQUIRED_TARGET_IDS),
            "target_count": 0,
            "green_target_ids": [],
            "blocked_target_ids": [],
            "missing_required_target_ids": list(_DEFAULT_REQUIRED_TARGET_IDS),
            "first_blocked_required_target": _DEFAULT_REQUIRED_TARGET_IDS[0],
            "gate": {},
            "claim_locked": True,
            "claim_lock_reason": "gpcr_hard_decoy_suite_report_missing",
            "diagnostic_family_claim_safe_before_claim_lock": False,
            "diagnostic_status_before_claim_lock": "",
            "blocker_panel_ready": False,
            "target_metric_row_count": 0,
            "target_metric_green_row_count": 0,
            "target_rows": [],
            "blocker_row_count": 1,
            "blocker_rows": [
                {
                    "blocker_id": "gpcr_hard_decoy_suite_report_missing",
                    "target_id": "",
                    "blocker_type": "missing_artifact",
                    "status": "missing_gpcr_hard_decoy_suite_report",
                    "claim_locked": True,
                    "claim_safe": False,
                    "reason": "local GPCR hard-decoy suite artifact is missing or invalid",
                    "next_required_step": "Regenerate the GPCR hard-decoy suite report before any broad GPCR/router claim review.",
                    "operator_action_required": True,
                    "execution_enabled": False,
                    "docking_results_emitted": False,
                    "external_state_mutated": False,
                    "claim_promotion_allowed": False,
                }
            ],
            "claim_promotion_allowed": False,
            **claim_unlock_surface,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "targets": [],
            "claim_boundary": _CLAIM_BOUNDARY_MISSING,
        }
    target_rows = _target_rows(targets)
    blocker_rows = _blocker_rows(summary, target_rows)
    return {
        "status": summary.get("status"),
        "artifact_path": str(GPCR_HARD_DECOY_SUITE_ARTIFACT),
        "schema_version": summary.get("schema_version", ""),
        # Fail-closed: only a true value is treated as claim-safe.
        "family_claim_safe": bool(summary.get("family_claim_safe") is True),
        "required_target_ids": summary.get("required_target_ids", []),
        "target_count": int(summary.get("target_count") or 0),
        "green_target_ids": summary.get("green_target_ids", []),
        "blocked_target_ids": summary.get("blocked_target_ids", []),
        "missing_required_target_ids": summary.get("missing_required_target_ids", []),
        "first_blocked_required_target": summary.get("first_blocked_required_target", ""),
        "gate": summary.get("gate", {}),
        "claim_locked": bool(summary.get("claim_locked") is True),
        "claim_lock_reason": str(summary.get("claim_lock_reason") or ""),
        "diagnostic_family_claim_safe_before_claim_lock": bool(
            summary.get("diagnostic_family_claim_safe_before_claim_lock") is True
        ),
        "diagnostic_status_before_claim_lock": str(
            summary.get("diagnostic_status_before_claim_lock") or ""
        ),
        "blocker_panel_ready": True,
        "target_metric_row_count": len(target_rows),
        "target_metric_green_row_count": sum(1 for row in target_rows if row["metric_gate_pass"]),
        "target_rows": target_rows,
        "blocker_row_count": len(blocker_rows),
        "blocker_rows": blocker_rows,
        "claim_promotion_allowed": False,
        **claim_unlock_surface,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "targets": targets,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
