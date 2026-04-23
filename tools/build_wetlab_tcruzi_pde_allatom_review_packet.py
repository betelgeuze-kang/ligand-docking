#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_allatom_refinement_utils import (
    _extract_commercial_v2_optional_fields,
    compute_commercial_grade_schema_v2,
    compute_commercial_grade_schema_v1,
    compute_final_wetlab_gate_summary,
    compute_wetlab_gate_summary,
    resolve_optional_claim_gate_summary,
)
from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_RUNNER_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md"


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def build_payload(
    lane_payload: dict[str, Any],
    runner_payload: dict[str, Any],
    *,
    claim_readiness_json: str = "",
    equivalence_gate_json: str = "",
) -> dict[str, Any]:
    lane_summary = dict(lane_payload.get("summary", {}) or {})
    runner_summary = dict(runner_payload.get("summary", {}) or {})
    lane_rows = {
        _text((row or {}).get("ligand_id")): dict(row or {})
        for row in (lane_payload.get("rows", []) or [])
        if _text((row or {}).get("ligand_id"))
    }
    allatom_summary_json = _text(runner_summary.get("allatom_summary_json"))
    scoring_payload = load_json(allatom_summary_json) if allatom_summary_json else {}
    topk_rows = [dict(row or {}) for row in (scoring_payload.get("topk", []) or [])]
    promoted_rows = []
    for idx, row in enumerate(topk_rows[:4], start=1):
        ligand_id = _text(row.get("ligand_id"))
        lane_row = lane_rows.get(ligand_id, {})
        promoted_rows.append(
            {
                "row_kind": "tcruzi_pde_allatom_review_packet_row",
                "packet_rank": idx,
                "target_id": TARGET_ID,
                "shard_id": _text(lane_summary.get("shard_id")),
                "ligand_id": ligand_id,
                "compound_name": _text(lane_row.get("compound_name")),
                "compound_name_human_readable": _text(lane_row.get("compound_name_human_readable")),
                "compound_name_resolution": _text(lane_row.get("compound_name_resolution"), default="unresolved"),
                "smiles": _text(lane_row.get("smiles")),
                "source_three_bead_priority_rank": _safe_int(lane_row.get("source_three_bead_priority_rank")),
                "source_rescue_review_band": _text(lane_row.get("source_rescue_review_band")),
                "source_three_bead_contact_fraction": _safe_float(lane_row.get("source_three_bead_contact_fraction")),
                "source_three_bead_trajectory_frames": _safe_int(lane_row.get("source_three_bead_trajectory_frames")),
                "mean_min_distance_A": round(_safe_float(row.get("mean_min_distance_A")), 3),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "binding_energy_mmpbsa_kcal_mol_proxy": _safe_float(row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
                "binding_energy_mmpbsa_std": _safe_float(row.get("binding_energy_mmpbsa_std")),
                "stability_score": _safe_float(row.get("stability_score")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "trajectory_frames": _safe_int(row.get("trajectory_frames")),
                "ligand_model": _text(row.get("ligand_model")),
                "backmapped_pdb": _text(row.get("backmapped_pdb")),
                "score_json": _text(row.get("score_json")),
                "selection_score_col": _text(row.get("selection_score_col")) or _text(runner_summary.get("selection_score_col")),
                "selection_score_value": row.get("selection_score_value"),
                "translation_gate_version": _text(lane_row.get("translation_gate_version")),
                "translation_gate_band_bucket": _text(lane_row.get("translation_gate_band_bucket")),
                "translation_gate_score": row.get("translation_gate_score", lane_row.get("translation_gate_score")),
                "translation_gate_status": _text(lane_row.get("translation_gate_status")),
                "translation_gate_pass": bool(lane_row.get("translation_gate_pass", False)),
                "translation_gate_required_check_count": _safe_int(lane_row.get("translation_gate_required_check_count")),
                "translation_gate_required_pass_count": _safe_int(lane_row.get("translation_gate_required_pass_count")),
                "translation_gate_optional_check_count": _safe_int(lane_row.get("translation_gate_optional_check_count")),
                "translation_gate_optional_pass_count": _safe_int(lane_row.get("translation_gate_optional_pass_count")),
                "translation_gate_failed_checks": list(lane_row.get("translation_gate_failed_checks", []) or []),
                "translation_gate_warning_checks": list(lane_row.get("translation_gate_warning_checks", []) or []),
                "translation_gate_passed_checks": list(lane_row.get("translation_gate_passed_checks", []) or []),
                "translation_gate_requires_pose_tightening": bool(lane_row.get("translation_gate_requires_pose_tightening", False)),
                "translation_gate_reason": _text(lane_row.get("translation_gate_reason")),
                "stronger_physics_shortlist_version": _text(lane_row.get("stronger_physics_shortlist_version")),
                "shortlist_tier": _text(lane_row.get("shortlist_tier")),
                "shortlist_promising": bool(lane_row.get("shortlist_promising", False)),
                "recommended_next_expensive_lane": _text(lane_row.get("recommended_next_expensive_lane")),
                "recommended_next_expensive_lane_priority": _safe_int(lane_row.get("recommended_next_expensive_lane_priority")),
                "recommended_next_expensive_lane_reason": _text(lane_row.get("recommended_next_expensive_lane_reason")),
                "review_action": (
                    "strict_promote_rescue_only_branch"
                    if 0 < _safe_float(row.get("mean_min_distance_A")) <= 2.5
                    else "near_band_manual_review_rescue_only_branch"
                    if _safe_float(row.get("mean_min_distance_A")) <= 3.0
                    else "retain_rescue_only_branch_manual_review"
                ),
                **_extract_commercial_v2_optional_fields(dict(row or {})),
            }
        )
    best_row = promoted_rows[0] if promoted_rows else {}
    strict_threshold = 2.5
    near_threshold = 3.0
    gate_summary = compute_wetlab_gate_summary(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
    )
    claim_gate_summary = resolve_optional_claim_gate_summary(
        target_id=TARGET_ID,
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
        runner_payload=runner_payload,
    )
    final_gate_summary = compute_final_wetlab_gate_summary(
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
    )
    commercial_schema_v1 = compute_commercial_grade_schema_v1(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    promoted_rows = list(commercial_schema_v1.get("rows", []) or promoted_rows)
    commercial_schema_v2 = compute_commercial_grade_schema_v2(
        promoted_rows=promoted_rows,
        selected_threshold_A=_safe_float(lane_summary.get("selected_threshold_A"), strict_threshold),
        strict_threshold_A=strict_threshold,
        near_threshold_A=near_threshold,
        wetlab_gate_summary=gate_summary,
        claim_gate_summary=claim_gate_summary,
        final_gate_summary=final_gate_summary,
    )
    promoted_rows = list(commercial_schema_v2.get("rows", []) or promoted_rows)
    best_row = promoted_rows[0] if promoted_rows else {}
    wetlab_gate_pass = bool(gate_summary.get("wetlab_gate_pass"))
    wetlab_final_gate_pass = bool(final_gate_summary.get("wetlab_final_gate_pass"))
    packet_ready_for_operator_review = bool(gate_summary.get("packet_ready_for_operator_review"))
    wetlab_gate_mode = _text(gate_summary.get("wetlab_gate_mode"))
    translation_gate_focus_status = _text(runner_summary.get("selected_translation_gate_focus_status")) or _text(best_row.get("translation_gate_status"))
    translation_gate_focus_score = runner_summary.get("selected_translation_gate_focus_score")
    if translation_gate_focus_score in {"", None}:
        translation_gate_focus_score = best_row.get("translation_gate_score")
    translation_gate_focus_reason = _text(runner_summary.get("selected_translation_gate_focus_reason")) or _text(best_row.get("translation_gate_reason"))
    translation_gate_focus_failed_checks = list(runner_summary.get("selected_translation_gate_focus_failed_checks", []) or best_row.get("translation_gate_failed_checks", []) or [])
    translation_gate_focus_warning_checks = list(runner_summary.get("selected_translation_gate_focus_warning_checks", []) or best_row.get("translation_gate_warning_checks", []) or [])
    recommended_next_expensive_lane = _text(runner_summary.get("recommended_next_expensive_lane")) or _text(best_row.get("recommended_next_expensive_lane"))
    recommended_next_expensive_lane_reason = _text(runner_summary.get("recommended_next_expensive_lane_reason")) or _text(best_row.get("recommended_next_expensive_lane_reason"))
    focus_shortlist_tier = _text(runner_summary.get("focus_shortlist_tier")) or _text(best_row.get("shortlist_tier"))
    selected_shortlist_promising_count = _safe_int(runner_summary.get("selected_shortlist_promising_count"), sum(1 for row in promoted_rows if bool(row.get("shortlist_promising", False))))
    selected_shortlist_tier1_gold_count = _safe_int(runner_summary.get("selected_shortlist_tier1_gold_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier1_gold"))
    selected_shortlist_tier2_silver_count = _safe_int(runner_summary.get("selected_shortlist_tier2_silver_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier2_silver"))
    selected_shortlist_tier3_bronze_count = _safe_int(runner_summary.get("selected_shortlist_tier3_bronze_count"), sum(1 for row in promoted_rows if _text(row.get("shortlist_tier")) == "tier3_bronze"))
    claim_gate_required_for_final_wetlab = bool(
        claim_gate_summary.get("claim_gate_required_for_final_wetlab", False)
    )
    claim_gate_primary_action = _text(claim_gate_summary.get("claim_gate_primary_action"))
    if wetlab_final_gate_pass:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet, keep the default lane closed, and only advance this rescue-only packet as wetlab-ready after operator sign-off on the "
            f"{wetlab_gate_mode} gate pass."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and claim_gate_required_for_final_wetlab:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as final wetlab-ready until the semi-hard claim/equivalence requirement is cleared; "
            f"next action: {claim_gate_primary_action or 'produce_claim_equivalence_packet'}."
        )
    elif packet_ready_for_operator_review and wetlab_gate_pass and bool(claim_gate_summary.get("claim_gate_available")):
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as final wetlab-ready because the optional claim/equivalence gate did not pass."
        )
    elif packet_ready_for_operator_review:
        next_required_step = (
            "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, and do not treat this rescue-only packet as wetlab-ready because the "
            f"{wetlab_gate_mode} gate did not pass."
        )
    else:
        next_required_step = (
            "The PDE pseudo all-atom rescue review packet has no promoted rows yet; do not treat it as wetlab-ready."
        )
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
            "target_id": TARGET_ID,
            "shard_id": _text(lane_summary.get("shard_id")),
            "surface_label": "tcruzi_pde_allatom_review_packet",
            "packet_scope": "partner_operator_allatom_rescue_review",
            "packet_ready": bool(promoted_rows),
            "packet_ready_for_operator_review": packet_ready_for_operator_review,
            "wetlab_gate_pass": wetlab_gate_pass,
            "wetlab_gate_mode": wetlab_gate_mode,
            "wetlab_gate_band_candidate_count": _safe_int(gate_summary.get("wetlab_gate_band_candidate_count")),
            "wetlab_gate_failed_metrics": list(gate_summary.get("wetlab_gate_failed_metrics", []) or []),
            "wetlab_gate_failed_metric_count": _safe_int(gate_summary.get("wetlab_gate_failed_metric_count")),
            "wetlab_gate_reason": _text(gate_summary.get("wetlab_gate_reason")),
            "wetlab_gate_thresholds": dict(gate_summary.get("wetlab_gate_thresholds", {}) or {}),
            "translation_gate_version": _text(runner_summary.get("selected_translation_gate_version")) or _text(best_row.get("translation_gate_version")),
            "translation_gate_focus_status": translation_gate_focus_status,
            "translation_gate_focus_score": translation_gate_focus_score,
            "translation_gate_focus_reason": translation_gate_focus_reason,
            "translation_gate_focus_failed_checks": translation_gate_focus_failed_checks,
            "translation_gate_focus_warning_checks": translation_gate_focus_warning_checks,
            "stronger_physics_shortlist_version": _text(runner_summary.get("selected_stronger_physics_shortlist_version")) or _text(best_row.get("stronger_physics_shortlist_version")),
            "shortlist_promising_count": selected_shortlist_promising_count,
            "shortlist_tier1_gold_count": selected_shortlist_tier1_gold_count,
            "shortlist_tier2_silver_count": selected_shortlist_tier2_silver_count,
            "shortlist_tier3_bronze_count": selected_shortlist_tier3_bronze_count,
            "focus_shortlist_tier": focus_shortlist_tier,
            "recommended_next_expensive_lane": recommended_next_expensive_lane,
            "recommended_next_expensive_lane_reason": recommended_next_expensive_lane_reason,
            "recommended_next_expensive_lane_counts": list(runner_summary.get("recommended_next_expensive_lane_counts", []) or []),
            "claim_gate_available": bool(claim_gate_summary.get("claim_gate_available")),
            "claim_gate_source": _text(claim_gate_summary.get("claim_gate_source")),
            "claim_gate_policy_version": _text(claim_gate_summary.get("policy_version")),
            "claim_gate_semantics_version": _text(claim_gate_summary.get("claim_gate_semantics_version")),
            "claim_gate_requirement_mode": _text(claim_gate_summary.get("claim_gate_requirement_mode")),
            "claim_gate_requirement_provenance": _text(
                claim_gate_summary.get("claim_gate_requirement_provenance")
            ),
            "claim_gate_target_group": _text(claim_gate_summary.get("claim_gate_target_group")),
            "claim_gate_required_for_final_wetlab": claim_gate_required_for_final_wetlab,
            "claim_gate_required_for_commercial_readiness": bool(
                claim_gate_summary.get("claim_gate_required_for_commercial_readiness", False)
            ),
            "claim_gate_requirement_reason": _text(
                claim_gate_summary.get("claim_gate_requirement_reason")
            ),
            "claim_gate_requirement_actions": list(
                claim_gate_summary.get("claim_gate_requirement_actions", []) or []
            ),
            "claim_gate_status": _text(claim_gate_summary.get("claim_gate_status")),
            "claim_gate_satisfied": claim_gate_summary.get("claim_gate_satisfied"),
            "claim_gate_status_reason": _text(claim_gate_summary.get("claim_gate_status_reason")),
            "claim_gate_primary_action": claim_gate_primary_action,
            "claim_gate_action_rollup": _text(claim_gate_summary.get("claim_gate_action_rollup")),
            "claim_gate_blocking_metrics": list(
                claim_gate_summary.get("claim_gate_blocking_metrics", []) or []
            ),
            "claim_gate_missing_metrics_detail": list(
                claim_gate_summary.get("claim_gate_missing_metrics_detail", []) or []
            ),
            "pass_core_gate": claim_gate_summary.get("pass_core_gate"),
            "claim_ready_for_allatom": claim_gate_summary.get("claim_ready_for_allatom"),
            "core_failed_metrics": claim_gate_summary.get("core_failed_metrics"),
            "core_missing_metrics": claim_gate_summary.get("core_missing_metrics"),
            "claim_failed_metrics": claim_gate_summary.get("claim_failed_metrics"),
            "claim_missing_metrics": claim_gate_summary.get("claim_missing_metrics"),
            "wetlab_final_gate_mode": _text(final_gate_summary.get("wetlab_final_gate_mode")),
            "wetlab_final_gate_pass": wetlab_final_gate_pass,
            "wetlab_final_gate_failed_metrics": list(final_gate_summary.get("wetlab_final_gate_failed_metrics", []) or []),
            "wetlab_final_gate_missing_metrics": list(
                final_gate_summary.get("wetlab_final_gate_missing_metrics", []) or []
            ),
            "wetlab_final_gate_failed_metric_count": _safe_int(final_gate_summary.get("wetlab_final_gate_failed_metric_count")),
            "wetlab_final_gate_missing_metric_count": _safe_int(
                final_gate_summary.get("wetlab_final_gate_missing_metric_count")
            ),
            "wetlab_final_gate_reason": _text(final_gate_summary.get("wetlab_final_gate_reason")),
            "wetlab_final_gate_blocking_domain": _text(
                final_gate_summary.get("wetlab_final_gate_blocking_domain")
            ),
            "wetlab_final_gate_required_next_actions": list(
                final_gate_summary.get("wetlab_final_gate_required_next_actions", []) or []
            ),
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "selected_command_kind": _text(lane_summary.get("selected_command_kind")),
            "selected_threshold_A": _safe_float(lane_summary.get("selected_threshold_A"), 2.5),
            "selected_ligand_model": _text(lane_summary.get("allatom_ligand_model"), default="3bead_implicit_hbond"),
            "strict_threshold_A": strict_threshold,
            "near_threshold_A": near_threshold,
            "promoted_candidate_count": len(promoted_rows),
            "under_2p5_candidate_count": _safe_int(gate_summary.get("strict_candidate_count")),
            "near_candidate_count": _safe_int(gate_summary.get("near_candidate_count")),
            "best_ligand_id": _text(best_row.get("ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(best_row.get("mean_min_distance_A")), 3),
            "best_binding_energy_proxy": _safe_float(best_row.get("binding_energy_proxy")),
            "best_binding_energy_mmpbsa_kcal_mol_proxy": _safe_float(best_row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
            "best_binding_energy_mmpbsa_std": _safe_float(best_row.get("binding_energy_mmpbsa_std")),
            "best_stability_score": _safe_float(best_row.get("stability_score")),
            "best_compound_name": _text(best_row.get("compound_name")),
            "best_compound_name_human_readable": _text(best_row.get("compound_name_human_readable")),
            "best_compound_name_resolution": _text(best_row.get("compound_name_resolution"), default="unresolved"),
            "best_smiles": _text(best_row.get("smiles")),
            "allatom_scoring_status": _text(runner_summary.get("scoring_status")),
            "execution_mode": _text(runner_summary.get("execution_mode")),
            "next_required_step": next_required_step,
            **dict(commercial_schema_v1.get("summary", {}) or {}),
            **dict(commercial_schema_v2.get("summary", {}) or {}),
        },
        "structured": {
            "allatom_rescue_lane_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "allatom_rescue_runner_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_current.md",
            "allatom_scores_csv": _text(runner_summary.get("allatom_scores_csv")),
            "allatom_summary_json": allatom_summary_json,
            "allatom_claim_readiness_json": _text(claim_gate_summary.get("claim_readiness_json")),
            "allatom_equivalence_gate_json": _text(claim_gate_summary.get("equivalence_gate_json")),
            "allatom_equivalence_gate_csv": _text(claim_gate_summary.get("equivalence_gate_csv")),
        },
        "rows": promoted_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE pseudo all-atom review packet.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--runner-json", default=DEFAULT_RUNNER_JSON)
    parser.add_argument("--claim-readiness-json", default="")
    parser.add_argument("--equivalence-gate-json", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.lane_json),
        load_json(args.runner_json),
        claim_readiness_json=str(args.claim_readiness_json),
        equivalence_gate_json=str(args.equivalence_gate_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE All-Atom Review Packet", payload)


if __name__ == "__main__":
    main()
