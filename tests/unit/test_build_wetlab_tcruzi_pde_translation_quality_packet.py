from __future__ import annotations

from tools.build_wetlab_tcruzi_pde_translation_quality_packet import build_payload


def test_build_translation_quality_packet_keeps_p0_green_but_translation_blocked() -> None:
    review_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "wetlab_final_gate_pass": True,
            "commercial_hard_gate_pass_v2": True,
            "best_ligand_id": "lig_best",
            "best_mean_min_distance_A": 2.12,
            "best_binding_energy_proxy": -0.1459,
            "translation_gate_focus_status": "borderline",
            "translation_gate_focus_score": 68.1,
            "translation_gate_focus_failed_checks": [
                "binding_energy_proxy_too_weak_for_translation",
            ],
            "translation_gate_focus_warning_checks": [
                "backmapping_consistency_not_observed",
                "local_minimization_survival_not_observed",
                "pose_preservation_rmsd_not_observed",
                "replicate_pass_fraction_not_observed",
            ],
            "recommended_next_expensive_lane": "defer_expensive_lane",
        },
        "rows": [
            {
                "ligand_id": "lig_best",
                "packet_rank": 1,
                "mean_min_distance_A": 2.12,
                "binding_energy_proxy": -0.1459,
            }
        ],
    }

    payload = build_payload(review_payload, source_review_json="review.json")

    summary = payload["summary"]
    assert summary["allatom_delivery_p0_green"] is True
    assert summary["translation_quality_ready"] is False
    assert summary["claim_scope"] == "post_p0_quality_followup_only"
    assert summary["claim_promotion_allowed"] is False
    assert summary["claim_policy_status"] == "blocked_post_p0_quality_followup"
    assert summary["primary_blocker"] == "binding_energy_proxy_too_weak_for_translation"
    assert summary["measurement_gap_count"] == 4
    assert summary["failed_quality_axes"] == ["binding_energy_proxy"]
    assert summary["missing_quality_axes"] == [
        "backmapping_consistency",
        "local_minimization_survival",
        "pose_preservation_rmsd",
        "replicate_pass_fraction",
    ]
    assert summary["next_required_step"] == "Close translation-quality evidence before broad wetlab or scale-up claims."
    closure = payload["closure_gate_requirements"]
    assert closure["status"] == "blocked"
    assert closure["claim_promotion_allowed"] is False
    assert closure["expensive_lane_allowed"] is False
    assert closure["blocker_count"] == 5
    assert closure["measurement_gap_count"] == 4
    assert closure["next_gate"] == "translation_quality_closure"
    assert closure["required_closed_axes"] == [
        "backmapping_consistency",
        "binding_energy_proxy",
        "local_minimization_survival",
        "pose_preservation_rmsd",
        "replicate_pass_fraction",
    ]
    assert closure["required_next_calculations"] == [
        "strengthen_binding_energy_proxy",
        "measure_backmapping_consistency",
        "measure_local_minimization_survival",
        "measure_pose_preservation_rmsd",
        "collect_replicate_pass_fraction",
    ]

    action_by_check = {row["check_id"]: row for row in payload["rows"]}
    assert action_by_check["binding_energy_proxy_too_weak_for_translation"]["evidence_status"] == "failed"
    assert action_by_check["binding_energy_proxy_too_weak_for_translation"]["action_code"] == "strengthen_binding_energy_proxy"
    assert action_by_check["pose_preservation_rmsd_not_observed"]["action_code"] == "measure_pose_preservation_rmsd"
    assert action_by_check["backmapping_consistency_not_observed"]["action_code"] == "measure_backmapping_consistency"
    assert action_by_check["local_minimization_survival_not_observed"]["action_code"] == "measure_local_minimization_survival"
    assert action_by_check["replicate_pass_fraction_not_observed"]["evidence_status"] == "missing"
