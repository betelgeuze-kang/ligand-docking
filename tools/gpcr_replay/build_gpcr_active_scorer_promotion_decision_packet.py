#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_active_scorer_promotion_decision_packet_current.md"
OPERATIONAL_SCORE_COL = "binding_score_composite_v7_residual_active"

CLAIM_BOUNDARY = (
    "GPCR active scorer promotion decision packet only; it records whether guarded operational ranking evidence, "
    "independent repeat, product execution approval, and validated local-delivery bundle evidence jointly allow "
    "promoting the operational score column out of shadow-only posture. It does not rerun docking, mutate router "
    "defaults, or authorize broad platform claims."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _ligand_ranking_row(packet: dict[str, Any]) -> dict[str, Any]:
    for row in _rows(packet):
        if _text(row.get("axis")) == "ligand_ranking":
            return row
    return {}


def scorecard_metric_ready_under_claim_lock(packet: dict[str, Any]) -> dict[str, Any]:
    """Separate ranking metric readiness from broad GPCR claim promotion."""
    summary = _summary(packet)
    ligand = _ligand_ranking_row(packet)
    metrics = ligand.get("metrics") if isinstance(ligand.get("metrics"), dict) else {}
    thresholds = ligand.get("thresholds") if isinstance(ligand.get("thresholds"), dict) else {}
    blockers = [str(item) for item in ligand.get("blockers") or []]
    metric_blockers: list[str] = []

    if _text(summary.get("status")) == "green":
        metric_ready = True
    else:
        pr_auc = _num(metrics.get("ranking_pr_auc"))
        pr_auc_ci_low = _num(metrics.get("ranking_pr_auc_ci_low"))
        topk = _num(metrics.get("ranking_topk_hit_rate"))
        pr_auc_min = _num(thresholds.get("ranking_pr_auc_min"))
        pr_auc_ci_low_min = _num(thresholds.get("ranking_pr_auc_ci_low_min"))
        topk_min = _num(thresholds.get("ranking_topk_hit_rate_min"))

        if _text(ligand.get("status")) != "restricted_pass":
            metric_blockers.append("ligand_ranking_not_restricted_pass")
        if blockers != ["broad_gpcr_claim_not_allowed"]:
            metric_blockers.append("ligand_ranking_has_non_scope_blockers")
        if _int(summary.get("blocked_row_count")) != 0:
            metric_blockers.append("accuracy_parity_blocked_rows_present")
        if _int(summary.get("missing_row_count")) != 0:
            metric_blockers.append("accuracy_parity_missing_rows_present")
        if pr_auc is None or pr_auc_min is None or pr_auc < pr_auc_min:
            metric_blockers.append("ranking_pr_auc_below_threshold")
        if pr_auc_ci_low is None or pr_auc_ci_low_min is None or pr_auc_ci_low < pr_auc_ci_low_min:
            metric_blockers.append("ranking_pr_auc_ci_low_below_threshold")
        if topk is None or topk_min is None or topk < topk_min:
            metric_blockers.append("ranking_topk_hit_rate_below_threshold")
        if _bool(metrics.get("gpcr_conditional_prior_boundary_ready")) is not True:
            metric_blockers.append("gpcr_conditional_prior_boundary_not_ready")
        if _bool(metrics.get("gpcr_oprm1_pose_repair_evidence_ready")) is not True:
            metric_blockers.append("gpcr_oprm1_pose_repair_not_ready")
        if _bool(metrics.get("crossfit_validation_ready")) is not True:
            metric_blockers.append("crossfit_validation_not_ready")

        metric_ready = not metric_blockers

    claim_scope_lock_only = (
        metric_ready
        and _text(summary.get("status")) == "blocked_accuracy_parity"
        and blockers == ["broad_gpcr_claim_not_allowed"]
        and _bool(ligand.get("claim_promotion_allowed")) is False
        and _bool(ligand.get("commercial_parity_claim_allowed")) is False
    )
    return {
        "metric_ready": metric_ready,
        "metric_blockers": sorted(set(metric_blockers)),
        "claim_scope_lock_only": claim_scope_lock_only,
        "ligand_ranking_status": _text(ligand.get("status")),
        "ligand_ranking_blockers": blockers,
        "status": _text(summary.get("status")),
    }


def build_packet(
    *,
    phase_ab_chain_json: str | Path = "runs/gpcr_commercial_phase_ab_closure_chain_current.json",
    operational_gate_json: str | Path = "runs/gpcr_guarded_operational_gate_refresh_chain_current.json",
    independent_repeat_json: str | Path = "runs/gpcr_a1_independent_repeat_packet_current.json",
    scorecard_json: str | Path = "runs/accuracy_parity_scorecard_current.json",
    approval_gate_json: str | Path = "runs/product_execution_approval_gate_current.json",
    bundle_contract_json: str | Path = "runs/product_bundle_contract_current.json",
    delivery_evidence_json: str | Path = "runs/product_delivery_evidence_contract_current.json",
    residual_registry_json: str | Path = "runs/residual_model_registry_current.json",
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    phase_ab = _summary(_read_json(phase_ab_chain_json))
    operational = _summary(_read_json(operational_gate_json))
    repeat = _summary(_read_json(independent_repeat_json))
    scorecard_packet = _read_json(scorecard_json)
    scorecard = _summary(scorecard_packet)
    scorecard_readiness = scorecard_metric_ready_under_claim_lock(scorecard_packet)
    approval = _summary(_read_json(approval_gate_json))
    bundle = _summary(_read_json(bundle_contract_json))
    delivery = _summary(_read_json(delivery_evidence_json))
    registry = _summary(_read_json(residual_registry_json))

    operational_payload = _read_json(operational_gate_json)
    operational_lanes = operational_payload.get("summary", {}).get("lanes", {})
    if not isinstance(operational_lanes, dict):
        operational_lanes = {}
    readiness_lane = operational_lanes.get("guarded_100k_rerun_readiness", {})
    readiness_summary = readiness_lane.get("summary") if isinstance(readiness_lane, dict) else {}
    if not isinstance(readiness_summary, dict):
        readiness_summary = {}

    blockers: list[str] = []
    if not _bool(phase_ab.get("phase_a_claim_closure_ready")):
        blockers.append("phase_a_claim_closure_not_ready")
    if not _bool(phase_ab.get("phase_b_product_delivery_ready")):
        blockers.append("phase_b_product_delivery_not_ready")
    if operational.get("status") != "guarded_operational_gate_refresh_complete_claim_locked":
        blockers.append("operational_gate_refresh_not_complete")
    if _text(readiness_summary.get("launch_status")) != "eligible":
        blockers.append("operational_launch_not_eligible")
    if repeat.get("status") != "independent_repeat_passed_claim_locked":
        blockers.append("independent_repeat_not_passed")
    if not _bool(scorecard_readiness.get("metric_ready")):
        blockers.append("accuracy_parity_scorecard_not_green")
    if not _bool(approval.get("authorized_for_execution")):
        blockers.append("product_execution_not_operator_authorized")
    if bundle.get("status") != "product_bundle_contract_ready":
        blockers.append("product_bundle_contract_not_ready")
    if not _bool(bundle.get("bundle_validation_passed")):
        blockers.append("product_bundle_validation_not_passed")
    if not _bool(delivery.get("delivery_ready_claim_allowed")):
        blockers.append("delivery_ready_claim_not_allowed")
    if not _bool(registry.get("production_promotion_allowed")):
        blockers.append("residual_registry_production_promotion_not_allowed")

    active_scorer_apply_allowed = not blockers
    status = (
        "gpcr_active_scorer_promotion_decision_ready_claim_locked"
        if active_scorer_apply_allowed
        else "blocked_gpcr_active_scorer_promotion_decision"
    )
    summary = {
        "packet_type": "gpcr_active_scorer_promotion_decision_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "active_scorer_apply_allowed": active_scorer_apply_allowed,
        "scorer_apply_allowed": active_scorer_apply_allowed,
        "operational_score_col": OPERATIONAL_SCORE_COL,
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "promotion_scope": "guarded_operational_gpcr_ranking_only",
        "phase_a_claim_closure_ready": _bool(phase_ab.get("phase_a_claim_closure_ready")),
        "phase_b_product_delivery_ready": _bool(phase_ab.get("phase_b_product_delivery_ready")),
        "accuracy_parity_metric_ready": bool(scorecard_readiness["metric_ready"]),
        "accuracy_parity_metric_blockers": scorecard_readiness["metric_blockers"],
        "accuracy_parity_claim_scope_lock_only": bool(scorecard_readiness["claim_scope_lock_only"]),
        "accuracy_parity_ligand_ranking_status": scorecard_readiness["ligand_ranking_status"],
        "accuracy_parity_ligand_ranking_blockers": scorecard_readiness["ligand_ranking_blockers"],
        "delivery_ready_claim_allowed": _bool(delivery.get("delivery_ready_claim_allowed")),
        "product_execution_authorized": _bool(approval.get("authorized_for_execution")),
        "residual_production_promotion_allowed": _bool(registry.get("production_promotion_allowed")),
        "blocker_count": len(blockers),
        "blockers": sorted(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Active scorer promotion is authorized for the guarded operational GPCR ranking lane only; keep broad "
            "router/platform claims false until separate review clears."
            if active_scorer_apply_allowed
            else "Resolve listed blockers before promoting the operational score column out of shadow-only posture."
        ),
    }
    return {"summary": summary}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Active Scorer Promotion Decision",
        "",
        f"- status: `{summary['status']}`",
        f"- active_scorer_apply_allowed: `{summary['active_scorer_apply_allowed']}`",
        f"- operational_score_col: `{summary['operational_score_col']}`",
        f"- accuracy_parity_metric_ready: `{summary['accuracy_parity_metric_ready']}`",
        f"- accuracy_parity_claim_scope_lock_only: `{summary['accuracy_parity_claim_scope_lock_only']}`",
        f"- delivery_ready_claim_allowed: `{summary['delivery_ready_claim_allowed']}`",
        f"- claim_promotion_allowed: `{summary['claim_promotion_allowed']}`",
        "",
        "## Blockers",
        "",
    ]
    if summary["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR active scorer promotion decision from Phase A/B + product evidence.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet()
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
