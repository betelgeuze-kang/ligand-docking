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
    scorecard = _summary(_read_json(scorecard_json))
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
    if scorecard.get("status") != "green":
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
