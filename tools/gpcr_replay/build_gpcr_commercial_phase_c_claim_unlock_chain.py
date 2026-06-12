#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PRODUCT_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_chembl20_product_gate_repair_v1.json"
DEFAULT_PROFILE_OUT_PREFIX = "runs/product_gpcr_adrb2_after_approval"
DEFAULT_PLANNED_ARTIFACT = "runs/product_gpcr_adrb2_after_approval_summary.json"
DEFAULT_BUNDLE_TAG = "product_gpcr_adrb2"
DEFAULT_BUNDLE_DIR = "runs/local_delivery"
DEFAULT_BUNDLE_VALIDATION_JSON = "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json"
DEFAULT_OUT_JSON = "runs/gpcr_commercial_phase_c_claim_unlock_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_commercial_phase_c_claim_unlock_chain_current.md"


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


def build_packet(
    *,
    profile_json: str | Path = DEFAULT_PRODUCT_PROFILE_JSON,
    profile_out_prefix: str = DEFAULT_PROFILE_OUT_PREFIX,
    planned_artifact_path: str = DEFAULT_PLANNED_ARTIFACT,
    bundle_tag: str = DEFAULT_BUNDLE_TAG,
    bundle_dir: str = DEFAULT_BUNDLE_DIR,
    bundle_validation_json: str | Path = DEFAULT_BUNDLE_VALIDATION_JSON,
    skip_cameo: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []

    _run(
        [
            sys.executable,
            "tools/build_product_execution_work_order.py",
            "--profile-json",
            str(profile_json),
            "--profile-out-prefix",
            profile_out_prefix,
            "--planned-artifact-path",
            planned_artifact_path,
            "--bundle-tag",
            bundle_tag,
            "--out-dir",
            bundle_dir,
        ]
    )
    work_order_lane = _lane("product_execution_work_order", "runs/product_execution_work_order_current.json")
    if work_order_lane["status"] != "product_execution_work_order_ready":
        blockers.append("phase_c:product_execution_work_order_not_ready")

    _run([sys.executable, "tools/build_product_execution_preflight.py"])
    preflight_lane = _lane("product_execution_preflight", "runs/product_execution_preflight_current.json")
    if preflight_lane["status"] != "product_execution_preflight_ready":
        blockers.append("phase_c:product_execution_preflight_not_ready")

    _run([sys.executable, "tools/build_product_execution_approval_gate.py"])
    approval_lane = _lane("product_execution_approval_gate", "runs/product_execution_approval_gate_current.json")
    if approval_lane["status"] != "product_execution_operator_approval_gate_ready":
        blockers.append("phase_c:product_execution_approval_gate_not_ready")
    if not approval_lane["summary"].get("authorized_for_execution"):
        blockers.append("phase_c:product_execution_not_operator_authorized")

    bundle_rel = f"{bundle_dir.rstrip('/')}/bundle_{bundle_tag}"
    if _resolve(bundle_rel).is_dir() and _resolve(bundle_validation_json).exists():
        _run([sys.executable, "tools/validate_local_delivery_bundle.py", "--bundle-dir", bundle_rel])

    _run([sys.executable, "tools/build_product_bundle_contract.py"])
    bundle_lane = _lane("product_bundle_contract", "runs/product_bundle_contract_current.json")
    if bundle_lane["status"] != "product_bundle_contract_ready":
        blockers.append("phase_c:product_bundle_contract_not_ready")
    if not bundle_lane["summary"].get("bundle_validation_passed"):
        blockers.append("phase_c:product_bundle_validation_not_passed")

    _run([sys.executable, "tools/accounting/build_wetlab_selected_allatom_gate_burndown_packet.py"])
    wetlab_lane = _lane(
        "wetlab_selected_allatom_gate_burndown",
        "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
    )

    _run([sys.executable, "tools/build_product_delivery_evidence_contract.py"])
    delivery_lane = _lane("product_delivery_evidence_contract", "runs/product_delivery_evidence_contract_current.json")
    if delivery_lane["status"] != "product_delivery_evidence_contract_ready":
        blockers.append("phase_c:product_delivery_evidence_contract_not_ready")
    if not delivery_lane["summary"].get("delivery_ready_claim_allowed"):
        blockers.append("phase_c:delivery_ready_claim_not_allowed")

    _run(
        [
            sys.executable,
            "tools/build_product_pilot_packet_contract.py",
            "--bundle-validation-json",
            str(bundle_validation_json),
        ]
    )
    pilot_lane = _lane("product_pilot_packet_contract", "runs/product_pilot_packet_contract_current.json")
    if not pilot_lane["summary"].get("pilot_delivery_ready"):
        blockers.append("phase_c:pilot_delivery_not_ready")

    _run([sys.executable, "tools/build_gpcr_active_scorer_promotion_decision_packet.py"])
    scorer_lane = _lane(
        "gpcr_active_scorer_promotion_decision",
        "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
    )
    if not scorer_lane["summary"].get("active_scorer_apply_allowed"):
        blockers.extend(f"phase_c:scorer:{item}" for item in scorer_lane["summary"].get("blockers") or [])

    cameo_lanes: dict[str, Any] = {}
    cameo_official_results_pending = False
    if not skip_cameo:
        cameo_steps = [
            ("cameo_validation_operations_dossier", "tools/build_cameo_validation_operations_dossier.py"),
            ("cameo_official_results_intake_gate", "tools/build_cameo_official_results_intake_gate.py"),
            (
                "cameo_performance_scorecard",
                "tools/build_cameo_performance_scorecard.py",
                ["--results-csv", "runs/cameo_official_results_operator_intake.csv"],
            ),
            ("cameo_validation_readiness_gate", "tools/build_cameo_validation_readiness_gate.py"),
            ("cameo_architecture_validation_contract", "tools/build_cameo_architecture_validation_contract.py"),
            ("cameo_evidence_integrity_contract", "tools/build_cameo_evidence_integrity_contract.py"),
        ]
        cameo_artifacts = {
            "cameo_validation_operations_dossier": "runs/cameo_validation_operations_dossier_current.json",
            "cameo_official_results_intake_gate": "runs/cameo_official_results_intake_gate_current.json",
            "cameo_performance_scorecard": "runs/cameo_performance_scorecard_current.json",
            "cameo_validation_readiness_gate": "runs/cameo_validation_readiness_gate_current.json",
            "cameo_architecture_validation_contract": "runs/cameo_architecture_validation_contract_current.json",
            "cameo_evidence_integrity_contract": "runs/cameo_evidence_integrity_contract_current.json",
        }
        for step in cameo_steps:
            lane_id = step[0]
            script = step[1]
            extra = list(step[2]) if len(step) > 2 else []
            _run([sys.executable, script, *extra])
            lane = _lane(lane_id, cameo_artifacts[lane_id])
            cameo_lanes[lane_id] = lane
            if lane_id == "cameo_official_results_intake_gate" and lane["status"] != "cameo_official_results_intake_ready":
                cameo_official_results_pending = True
                blockers.append("phase_c:cameo_official_results_intake_not_ready")
            if lane_id == "cameo_performance_scorecard" and lane["status"] != "cameo_performance_evidence_ready":
                cameo_official_results_pending = True
                blockers.append("phase_c:cameo_performance_scorecard_not_ready")
            if lane_id == "cameo_architecture_validation_contract" and not lane["summary"].get(
                "cameo_architecture_validation_ready"
            ):
                blockers.append("phase_c:cameo_architecture_validation_not_ready")

    _run([sys.executable, "tools/product/build_goal_product_status_refresh_chain.py"])
    goal_lane = _lane("goal_product_status_refresh_chain", "runs/goal_product_status_refresh_chain_current.json")

    product_delivery_unlock_ready = not any(
        item.startswith("phase_c:") and "cameo" not in item for item in blockers
    )
    cameo_official_validation_ready = not any("cameo" in item for item in blockers)
    if product_delivery_unlock_ready and cameo_official_validation_ready:
        status = "gpcr_commercial_phase_c_claim_unlock_complete_claim_locked"
    elif product_delivery_unlock_ready:
        status = "gpcr_commercial_phase_c_product_delivery_unlock_complete_claim_locked"
    else:
        status = "blocked_gpcr_commercial_phase_c_claim_unlock"

    summary = {
        "packet_type": "gpcr_commercial_phase_c_claim_unlock_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "product_delivery_unlock_ready": product_delivery_unlock_ready,
        "delivery_ready_claim_allowed": bool(delivery_lane["summary"].get("delivery_ready_claim_allowed")),
        "pilot_delivery_ready": bool(pilot_lane["summary"].get("pilot_delivery_ready")),
        "active_scorer_apply_allowed": bool(scorer_lane["summary"].get("active_scorer_apply_allowed")),
        "operator_execution_authorized": bool(approval_lane["summary"].get("authorized_for_execution")),
        "cameo_official_validation_ready": cameo_official_validation_ready,
        "cameo_official_results_pending": cameo_official_results_pending,
        "bundle_tag": bundle_tag,
        "bundle_validation_json": str(_resolve(bundle_validation_json)),
        "lanes": {
            "product_execution_work_order": work_order_lane,
            "product_execution_preflight": preflight_lane,
            "product_execution_approval_gate": approval_lane,
            "product_bundle_contract": bundle_lane,
            "wetlab_selected_allatom_gate_burndown": wetlab_lane,
            "product_delivery_evidence_contract": delivery_lane,
            "product_pilot_packet_contract": pilot_lane,
            "gpcr_active_scorer_promotion_decision": scorer_lane,
            "goal_product_status_refresh_chain": goal_lane,
            "cameo": cameo_lanes,
        },
        "blockers": sorted(set(blockers)),
        "next_required_step": (
            "Product delivery unlock, operator authorization, bundle validation, active scorer promotion decision, "
            "and CAMEO official validation refreshed under claim lock."
            if not blockers
            else "Resolve listed Phase C blockers; CAMEO official results still require operator-provided CAMEO assessment rows with provenance."
            if cameo_official_results_pending
            else "Resolve listed Phase C blockers without threshold relaxation or fake pass."
        ),
    }
    return {"summary": summary}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Commercial Phase C Claim Unlock Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- product_delivery_unlock_ready: `{summary.get('product_delivery_unlock_ready')}`",
        f"- delivery_ready_claim_allowed: `{summary.get('delivery_ready_claim_allowed')}`",
        f"- active_scorer_apply_allowed: `{summary.get('active_scorer_apply_allowed')}`",
        f"- cameo_official_validation_ready: `{summary.get('cameo_official_validation_ready')}`",
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
    parser = argparse.ArgumentParser(description="Run Phase C product delivery unlock, scorer promotion, and CAMEO validation refresh.")
    parser.add_argument("--profile-json", default=DEFAULT_PRODUCT_PROFILE_JSON)
    parser.add_argument("--profile-out-prefix", default=DEFAULT_PROFILE_OUT_PREFIX)
    parser.add_argument("--planned-artifact-path", default=DEFAULT_PLANNED_ARTIFACT)
    parser.add_argument("--bundle-tag", default=DEFAULT_BUNDLE_TAG)
    parser.add_argument("--bundle-dir", default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--bundle-validation-json", default=DEFAULT_BUNDLE_VALIDATION_JSON)
    parser.add_argument("--skip-cameo", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        profile_json=args.profile_json,
        profile_out_prefix=args.profile_out_prefix,
        planned_artifact_path=args.planned_artifact_path,
        bundle_tag=args.bundle_tag,
        bundle_dir=args.bundle_dir,
        bundle_validation_json=args.bundle_validation_json,
        skip_cameo=args.skip_cameo,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
