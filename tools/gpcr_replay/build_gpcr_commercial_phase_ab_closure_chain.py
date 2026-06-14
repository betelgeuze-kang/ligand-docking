#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.gpcr_replay.build_gpcr_active_scorer_promotion_decision_packet import (
    scorecard_metric_ready_under_claim_lock,
)

ROOT = Path(__file__).resolve().parents[2]

OPERATIONAL_RERUN_RANKING_SUMMARY_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
)
ACCURACY_PARITY_RANK_RESCUE_EVIDENCE_JSON = "runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json"
CROSSFIT_REPEAT_RANKING_SUMMARY_JSON = (
    "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json"
)
CROSSFIT_REPEAT_TAG = "gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1"
DEFAULT_OUT_JSON = "runs/gpcr_commercial_phase_ab_closure_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_commercial_phase_ab_closure_chain_current.md"
DEFAULT_PRODUCT_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_chembl20_product_gate_repair_v1.json"
DEFAULT_PROFILE_OUT_PREFIX = "runs/product_gpcr_adrb2_after_approval"
DEFAULT_PLANNED_ARTIFACT_PATH = "runs/product_gpcr_adrb2_after_approval_summary.json"
DEFAULT_BUNDLE_TAG = "product_gpcr_adrb2"


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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _lane(name: str, path_like: str | Path) -> dict[str, Any]:
    payload = _read_json(path_like)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "lane": name,
        "status": str(summary.get("status") or "").strip(),
        "artifact": str(_resolve(path_like)),
        "summary": summary,
    }


OPERATOR_PENDING_BUNDLE_BLOCKERS = {
    "work_order_not_ready",
    "execution_preflight_not_ready",
}


def _product_work_order_cmd() -> list[str]:
    return [
        sys.executable,
        "tools/build_product_execution_work_order.py",
        "--profile-json",
        DEFAULT_PRODUCT_PROFILE_JSON,
        "--profile-out-prefix",
        DEFAULT_PROFILE_OUT_PREFIX,
        "--planned-artifact-path",
        DEFAULT_PLANNED_ARTIFACT_PATH,
        "--bundle-tag",
        DEFAULT_BUNDLE_TAG,
    ]


def build_packet(
    *,
    operational_ranking_summary_json: str | Path = ACCURACY_PARITY_RANK_RESCUE_EVIDENCE_JSON,
    independent_repeat_ranking_json: str | Path = CROSSFIT_REPEAT_RANKING_SUMMARY_JSON,
    independent_repeat_tag: str = CROSSFIT_REPEAT_TAG,
    skip_phase_b: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []

    _run([sys.executable, "tools/build_gpcr_guarded_operational_gate_refresh_chain.py"])
    operational_lane = _lane(
        "guarded_operational_gate_refresh",
        "runs/gpcr_guarded_operational_gate_refresh_chain_current.json",
    )
    if operational_lane["status"] != "guarded_operational_gate_refresh_complete_claim_locked":
        blockers.extend([f"phase_a:{item}" for item in operational_lane["summary"].get("blockers") or []])

    _run(
        [
            sys.executable,
            "tools/build_accuracy_parity_scorecard.py",
            "--gpcr-ranking-json",
            str(operational_ranking_summary_json),
        ]
    )
    scorecard_lane = _lane("accuracy_parity_scorecard", "runs/accuracy_parity_scorecard_current.json")
    scorecard_readiness = scorecard_metric_ready_under_claim_lock(
        _read_json("runs/accuracy_parity_scorecard_current.json")
    )
    if not scorecard_readiness["metric_ready"]:
        blockers.append("phase_a:accuracy_parity_scorecard_not_green")

    _run(
        [
            sys.executable,
            "tools/build_gpcr_a1_accuracy_repair_queue.py",
            "--ranking-json",
            str(operational_ranking_summary_json),
        ]
    )
    a1_lane = _lane("gpcr_a1_accuracy_repair_queue", "runs/gpcr_a1_accuracy_repair_queue_current.json")
    if not a1_lane["summary"].get("full_guarded_100k_review_passed"):
        blockers.append("phase_a:a1_full_guarded_100k_review_not_passed")

    _run(
        [
            sys.executable,
            "tools/build_gpcr_a1_independent_repeat_packet.py",
            "--ranking-json",
            str(independent_repeat_ranking_json),
            "--repeat-tag",
            str(independent_repeat_tag),
        ]
    )
    repeat_lane = _lane("gpcr_a1_independent_repeat_packet", "runs/gpcr_a1_independent_repeat_packet_current.json")
    if repeat_lane["status"] != "independent_repeat_passed_claim_locked":
        blockers.extend([f"phase_a:repeat:{item}" for item in repeat_lane["summary"].get("blockers") or []])

    _run([sys.executable, "tools/build_gpcr_frozen_ranking_quality_repair_chain.py", "--skip-htr2a", "--skip-oprm1"])
    repair_lane = _lane(
        "gpcr_frozen_ranking_quality_repair_chain",
        "runs/gpcr_frozen_ranking_quality_repair_chain_current.json",
    )
    if repair_lane["status"] != "ranking_quality_repair_chain_complete_claim_locked":
        blockers.extend([f"phase_a:repair:{item}" for item in repair_lane["summary"].get("blockers") or []])

    phase_b_lanes: dict[str, Any] = {}
    phase_b_operator_approval_pending = False
    if not skip_phase_b:
        product_steps = [
            ("product_operational_quality_contract", "tools/build_product_operational_quality_contract.py"),
            ("product_execution_work_order", _product_work_order_cmd()),
            ("product_execution_preflight", "tools/build_product_execution_preflight.py"),
            ("product_bundle_contract", "tools/build_product_bundle_contract.py"),
            ("product_delivery_evidence_contract", "tools/build_product_delivery_evidence_contract.py"),
            ("product_pilot_packet_contract", "tools/build_product_pilot_packet_contract.py"),
            ("product_scope_breadth_contract", "tools/build_product_scope_breadth_contract.py"),
            ("product_capability_surface_contract", "tools/build_product_capability_surface_contract.py"),
            ("product_commercial_independence_gate", "tools/build_product_commercial_independence_gate.py"),
            ("goal_readiness_rollup", "tools/build_goal_readiness_rollup.py"),
        ]
        for lane_id, script in product_steps:
            cmd = [sys.executable, script] if isinstance(script, str) else list(script)
            _run(cmd)
            artifact = {
                "product_operational_quality_contract": "runs/product_operational_quality_contract_current.json",
                "product_execution_work_order": "runs/product_execution_work_order_current.json",
                "product_execution_preflight": "runs/product_execution_preflight_current.json",
                "product_bundle_contract": "runs/product_bundle_contract_current.json",
                "product_delivery_evidence_contract": "runs/product_delivery_evidence_contract_current.json",
                "product_pilot_packet_contract": "runs/product_pilot_packet_contract_current.json",
                "product_scope_breadth_contract": "runs/product_scope_breadth_contract_current.json",
                "product_capability_surface_contract": "runs/product_capability_surface_contract_current.json",
                "product_commercial_independence_gate": "runs/product_commercial_independence_gate_current.json",
                "goal_readiness_rollup": "runs/goal_readiness_rollup_current.json",
            }[lane_id]
            lane = _lane(lane_id, artifact)
            phase_b_lanes[lane_id] = lane
            if lane_id == "product_operational_quality_contract" and not lane["summary"].get("operational_quality_ready"):
                blockers.append("phase_b:operational_quality_not_ready")
            if lane_id == "product_bundle_contract" and lane["status"] != "product_bundle_contract_ready":
                bundle_payload = _read_json(artifact)
                bundle_codes = {
                    str(item.get("code"))
                    for item in bundle_payload.get("blockers") or []
                    if isinstance(item, dict) and item.get("code")
                }
                if bundle_codes and bundle_codes.issubset(OPERATOR_PENDING_BUNDLE_BLOCKERS):
                    phase_b_operator_approval_pending = True
                else:
                    blockers.append("phase_b:product_bundle_contract_not_ready")
            if lane_id == "product_capability_surface_contract" and lane["summary"].get("restricted_scope_claim_guard_ready") is not True:
                blockers.append("phase_b:restricted_scope_claim_guard_not_ready")
            if lane_id == "product_commercial_independence_gate" and lane["status"] != "product_commercial_independence_gate_ready":
                blockers.append("phase_b:commercial_independence_gate_not_ready")

    status = "gpcr_commercial_phase_ab_closure_complete_claim_locked"
    if blockers:
        status = "blocked_gpcr_commercial_phase_ab_closure_claim_locked"

    summary = {
        "packet_type": "gpcr_commercial_phase_ab_closure_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "phase_a_claim_closure_ready": not any(item.startswith("phase_a:") for item in blockers),
        "phase_b_product_delivery_ready": not any(item.startswith("phase_b:") for item in blockers),
        "phase_b_operator_approval_pending": phase_b_operator_approval_pending,
        "accuracy_parity_metric_ready": bool(scorecard_readiness["metric_ready"]),
        "accuracy_parity_metric_blockers": scorecard_readiness["metric_blockers"],
        "accuracy_parity_claim_scope_lock_only": bool(scorecard_readiness["claim_scope_lock_only"]),
        "accuracy_parity_ligand_ranking_status": scorecard_readiness["ligand_ranking_status"],
        "accuracy_parity_ligand_ranking_blockers": scorecard_readiness["ligand_ranking_blockers"],
        "operational_ranking_summary_json": str(_resolve(operational_ranking_summary_json)),
        "independent_repeat_ranking_json": str(_resolve(independent_repeat_ranking_json)),
        "independent_repeat_tag": independent_repeat_tag,
        "lanes": {
            "phase_a": {
                "guarded_operational_gate_refresh": operational_lane,
                "accuracy_parity_scorecard": scorecard_lane,
                "gpcr_a1_accuracy_repair_queue": a1_lane,
                "gpcr_a1_independent_repeat_packet": repeat_lane,
                "gpcr_frozen_ranking_quality_repair_chain": repair_lane,
            },
            "phase_b": phase_b_lanes,
        },
        "blockers": sorted(set(blockers)),
        "next_required_step": (
            "Phase A GPCR claim-closure artifacts and Phase B product delivery contracts refreshed under claim lock. "
            "Formal operator approval, bundle execution, and external validation remain separate before any promotion."
            if not blockers
            else "Resolve listed Phase A/B blockers without threshold relaxation or fake pass."
        ),
    }
    return {"summary": summary}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Commercial Phase A/B Closure Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- phase_a_claim_closure_ready: `{summary.get('phase_a_claim_closure_ready')}`",
        f"- phase_b_product_delivery_ready: `{summary.get('phase_b_product_delivery_ready')}`",
        f"- accuracy_parity_metric_ready: `{summary.get('accuracy_parity_metric_ready')}`",
        f"- accuracy_parity_claim_scope_lock_only: `{summary.get('accuracy_parity_claim_scope_lock_only')}`",
        f"- claim_promotion_allowed: `false`",
        "",
        "## Blockers",
        "",
    ]
    if summary.get("blockers"):
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase A GPCR claim closure, then Phase B product delivery contract refresh."
    )
    parser.add_argument("--operational-ranking-summary-json", default=ACCURACY_PARITY_RANK_RESCUE_EVIDENCE_JSON)
    parser.add_argument("--independent-repeat-ranking-json", default=CROSSFIT_REPEAT_RANKING_SUMMARY_JSON)
    parser.add_argument("--independent-repeat-tag", default=CROSSFIT_REPEAT_TAG)
    parser.add_argument("--skip-phase-b", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        operational_ranking_summary_json=args.operational_ranking_summary_json,
        independent_repeat_ranking_json=args.independent_repeat_ranking_json,
        independent_repeat_tag=args.independent_repeat_tag,
        skip_phase_b=args.skip_phase_b,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
