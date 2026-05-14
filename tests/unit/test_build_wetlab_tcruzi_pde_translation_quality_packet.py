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


def test_build_translation_quality_packet_surfaces_exhausted_candidate_pool() -> None:
    review_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "wetlab_final_gate_pass": True,
            "commercial_hard_gate_pass_v2": False,
            "best_ligand_id": "lig_best",
            "best_mean_min_distance_A": 2.12,
            "best_binding_energy_proxy": -0.1459,
            "translation_gate_focus_status": "fail",
            "translation_gate_focus_score": 54.7,
            "translation_gate_focus_failed_checks": [
                "binding_energy_proxy_too_weak_for_translation",
            ],
            "translation_gate_focus_warning_checks": [],
            "recommended_next_expensive_lane": "defer_expensive_lane",
        },
        "rows": [],
    }
    evidence_payload = {
        "summary": {
            "translation_score_candidate_row_count": 29448,
            "translation_energy_pass_count": 0,
            "translation_core_pass_count": 0,
            "translation_core_like_count": 70,
            "best_binding_energy_proxy": -0.3001,
            "best_core_like_binding_energy_proxy": -0.1364,
            "candidate_pool_energy_gap_closed": False,
        }
    }

    payload = build_payload(
        review_payload,
        source_review_json="review.json",
        translation_evidence_payload=evidence_payload,
        source_translation_evidence_json="probe.json",
    )

    summary = payload["summary"]
    assert summary["allatom_delivery_p0_green"] is False
    assert summary["commercial_hard_gate_pass"] is False
    assert summary["candidate_pool_row_count"] == 29448
    assert summary["candidate_pool_energy_pass_count"] == 0
    assert summary["candidate_pool_core_pass_count"] == 0
    assert summary["binding_energy_source_pool_exhausted"] is True
    assert summary["candidate_pool_geometry_stability_blocked"] is False
    assert summary["candidate_pool_energy_gap_closed"] is False
    assert summary["candidate_pool_core_gate_closed"] is False
    assert summary["next_required_step"].startswith("Generate a stronger three-bead binding candidate pool")

    action_by_check = {row["check_id"]: row for row in payload["rows"]}
    exhausted = action_by_check["binding_energy_proxy_source_pool_exhausted"]
    assert exhausted["evidence_status"] == "failed"
    assert exhausted["quality_axis"] == "binding_energy_proxy_candidate_pool"
    assert exhausted["action_code"] == "generate_stronger_three_bead_binding_candidate_pool"
    assert exhausted["candidate_pool_best_binding_energy_proxy"] == -0.3001
    assert payload["closure_gate_requirements"]["blocker_count"] == 2
    assert "binding_energy_proxy_candidate_pool" in payload["closure_gate_requirements"]["required_closed_axes"]


def test_build_translation_quality_packet_surfaces_geometry_stability_blocked_candidate_pool() -> None:
    review_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "wetlab_final_gate_pass": True,
            "commercial_hard_gate_pass_v2": False,
            "best_ligand_id": "lig_best",
            "best_mean_min_distance_A": 2.12,
            "best_binding_energy_proxy": -0.1459,
            "translation_gate_focus_status": "fail",
            "translation_gate_focus_score": 54.7,
            "translation_gate_focus_failed_checks": [
                "binding_energy_proxy_too_weak_for_translation",
            ],
            "translation_gate_focus_warning_checks": [],
            "recommended_next_expensive_lane": "defer_expensive_lane",
        },
        "rows": [],
    }
    evidence_payload = {
        "summary": {
            "translation_score_candidate_row_count": 29541,
            "translation_energy_pass_count": 6,
            "translation_energy_pass_unique_ligand_count": 6,
            "translation_core_pass_count": 0,
            "translation_core_pass_unique_ligand_count": 0,
            "translation_core_like_count": 85,
            "external_homolog_seed_candidate_row_count": 48,
            "external_homolog_seed_energy_pass_count": 6,
            "external_homolog_seed_core_pass_count": 0,
            "external_homolog_geomstab_rescore_candidate_row_count": 0,
            "external_homolog_geomstab_rescore_energy_pass_count": 0,
            "external_homolog_geomstab_rescore_core_pass_count": 0,
            "best_binding_energy_proxy": -0.8569,
            "best_core_like_binding_energy_proxy": -0.1918,
            "external_homolog_seed_best_binding_energy_proxy": -0.8569,
            "candidate_pool_energy_gap_closed": True,
            "candidate_pool_core_gate_closed": False,
        }
    }

    payload = build_payload(
        review_payload,
        source_review_json="review.json",
        translation_evidence_payload=evidence_payload,
        source_translation_evidence_json="probe.json",
    )

    summary = payload["summary"]
    assert summary["candidate_pool_energy_pass_count"] == 6
    assert summary["candidate_pool_energy_pass_unique_ligand_count"] == 6
    assert summary["candidate_pool_core_pass_count"] == 0
    assert summary["candidate_pool_core_pass_unique_ligand_count"] == 0
    assert summary["external_homolog_seed_row_count"] == 48
    assert summary["external_homolog_seed_energy_pass_count"] == 6
    assert summary["external_homolog_seed_best_binding_energy_proxy"] == -0.8569
    assert summary["binding_energy_source_pool_exhausted"] is False
    assert summary["candidate_pool_geometry_stability_blocked"] is True
    assert summary["contact_aware_rescue_attempted_without_core_pass"] is False
    assert summary["candidate_pool_energy_gap_closed"] is True
    assert summary["candidate_pool_core_gate_closed"] is False
    assert summary["next_required_step"].startswith("Run geometry and stability rescue")

    action_by_check = {row["check_id"]: row for row in payload["rows"]}
    geometry_blocker = action_by_check["candidate_pool_geometry_stability_blocked"]
    assert geometry_blocker["evidence_status"] == "failed"
    assert geometry_blocker["quality_axis"] == "candidate_pool_geometry_stability"
    assert geometry_blocker["action_code"] == "repair_energy_pass_candidate_geometry_stability"
    assert geometry_blocker["external_homolog_seed_energy_pass_count"] == 6
    assert payload["closure_gate_requirements"]["blocker_count"] == 2
    assert "candidate_pool_geometry_stability" in payload["closure_gate_requirements"]["required_closed_axes"]


def test_build_translation_quality_packet_carries_geometry_stability_rescore_counts() -> None:
    payload = build_payload(
        {
            "summary": {
                "wetlab_final_gate_pass": True,
                "commercial_hard_gate_pass_v2": False,
                "translation_gate_focus_status": "fail",
                "translation_gate_focus_failed_checks": ["binding_energy_proxy_too_weak_for_translation"],
            },
            "rows": [],
        },
        translation_evidence_payload={
            "summary": {
                "translation_score_candidate_row_count": 29547,
                "translation_energy_pass_count": 12,
                "translation_energy_pass_unique_ligand_count": 6,
                "translation_core_pass_count": 0,
                "translation_core_pass_unique_ligand_count": 0,
                "external_homolog_geomstab_rescore_candidate_row_count": 6,
                "external_homolog_geomstab_rescore_energy_pass_count": 6,
                "external_homolog_geomstab_rescore_core_pass_count": 0,
                "external_homolog_geomstab_rescore_best_binding_energy_proxy": -0.8569,
                "external_homolog_adress_rescue_candidate_row_count": 6,
                "external_homolog_adress_rescue_energy_pass_count": 2,
                "external_homolog_adress_rescue_core_pass_count": 0,
                "external_homolog_adress_rescue_best_binding_energy_proxy": -0.8373,
                "candidate_pool_energy_gap_closed": True,
                "candidate_pool_core_gate_closed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["candidate_pool_energy_pass_count"] == 12
    assert summary["candidate_pool_energy_pass_unique_ligand_count"] == 6
    assert summary["external_homolog_geomstab_rescore_row_count"] == 6
    assert summary["external_homolog_geomstab_rescore_energy_pass_count"] == 6
    assert summary["external_homolog_geomstab_rescore_core_pass_count"] == 0
    assert summary["external_homolog_geomstab_rescore_best_binding_energy_proxy"] == -0.8569
    assert summary["external_homolog_adress_rescue_row_count"] == 6
    assert summary["external_homolog_adress_rescue_energy_pass_count"] == 2
    assert summary["external_homolog_adress_rescue_core_pass_count"] == 0
    assert summary["external_homolog_adress_rescue_best_binding_energy_proxy"] == -0.8373
    assert summary["candidate_pool_geometry_stability_blocked"] is True
    assert summary["adress_rescue_attempted_without_core_pass"] is True
    assert summary["contact_aware_rescue_attempted_without_core_pass"] is False
    assert summary["next_required_step"].startswith("Add a contact-aware pocket objective")

    action = {row["check_id"]: row for row in payload["rows"]}["candidate_pool_geometry_stability_blocked"]
    assert action["candidate_pool_energy_pass_unique_ligand_count"] == 6
    assert action["external_homolog_geomstab_rescore_row_count"] == 6
    assert action["external_homolog_adress_rescue_energy_pass_count"] == 2


def test_build_translation_quality_packet_marks_contact_rescue_failed_before_promotion() -> None:
    payload = build_payload(
        {
            "summary": {
                "wetlab_final_gate_pass": True,
                "commercial_hard_gate_pass_v2": False,
                "translation_gate_focus_status": "fail",
                "translation_gate_focus_failed_checks": ["binding_energy_proxy_too_weak_for_translation"],
            },
            "rows": [],
        },
        translation_evidence_payload={
            "summary": {
                "translation_score_candidate_row_count": 29559,
                "translation_energy_pass_count": 15,
                "translation_energy_pass_unique_ligand_count": 6,
                "translation_core_pass_count": 0,
                "translation_core_pass_unique_ligand_count": 0,
                "external_homolog_adress_rescue_candidate_row_count": 6,
                "external_homolog_adress_rescue_energy_pass_count": 2,
                "external_homolog_adress_rescue_core_pass_count": 0,
                "external_homolog_contact_rescue_candidate_row_count": 6,
                "external_homolog_contact_rescue_energy_pass_count": 1,
                "external_homolog_contact_rescue_core_pass_count": 0,
                "external_homolog_contact_rescue_best_binding_energy_proxy": -0.644,
                "candidate_pool_energy_gap_closed": True,
                "candidate_pool_core_gate_closed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["candidate_pool_energy_pass_count"] == 15
    assert summary["external_homolog_contact_rescue_row_count"] == 6
    assert summary["external_homolog_contact_rescue_energy_pass_count"] == 1
    assert summary["external_homolog_contact_rescue_core_pass_count"] == 0
    assert summary["external_homolog_contact_rescue_best_binding_energy_proxy"] == -0.644
    assert summary["adress_rescue_attempted_without_core_pass"] is True
    assert summary["contact_aware_rescue_attempted_without_core_pass"] is True
    assert summary["claim_promotion_allowed"] is False
    assert summary["next_required_step"].startswith("Contact-aware GPU rescue also failed")

    action = {row["check_id"]: row for row in payload["rows"]}["candidate_pool_geometry_stability_blocked"]
    assert action["external_homolog_contact_rescue_row_count"] == 6
    assert action["external_homolog_contact_rescue_energy_pass_count"] == 1
    assert action["external_homolog_contact_rescue_best_binding_energy_proxy"] == -0.644


def test_build_translation_quality_packet_marks_bindingdb_similarity_failed_before_promotion() -> None:
    payload = build_payload(
        {
            "summary": {
                "wetlab_final_gate_pass": True,
                "commercial_hard_gate_pass_v2": False,
                "translation_gate_focus_status": "fail",
                "translation_gate_focus_failed_checks": ["binding_energy_proxy_too_weak_for_translation"],
            },
            "rows": [],
        },
        translation_evidence_payload={
            "summary": {
                "translation_score_candidate_row_count": 29568,
                "translation_energy_pass_count": 16,
                "translation_energy_pass_unique_ligand_count": 7,
                "translation_core_pass_count": 0,
                "translation_core_pass_unique_ligand_count": 0,
                "external_homolog_contact_rescue_candidate_row_count": 6,
                "external_homolog_contact_rescue_energy_pass_count": 1,
                "external_homolog_contact_rescue_core_pass_count": 0,
                "external_bindingdb_similarity_candidate_row_count": 9,
                "external_bindingdb_similarity_energy_pass_count": 1,
                "external_bindingdb_similarity_core_pass_count": 0,
                "external_bindingdb_similarity_best_binding_energy_proxy": -0.5995,
                "candidate_pool_energy_gap_closed": True,
                "candidate_pool_core_gate_closed": False,
            }
        },
    )

    summary = payload["summary"]
    assert summary["candidate_pool_energy_pass_count"] == 16
    assert summary["external_bindingdb_similarity_row_count"] == 9
    assert summary["external_bindingdb_similarity_energy_pass_count"] == 1
    assert summary["external_bindingdb_similarity_core_pass_count"] == 0
    assert summary["external_bindingdb_similarity_best_binding_energy_proxy"] == -0.5995
    assert summary["bindingdb_similarity_seed_attempted_without_core_pass"] is True
    assert summary["claim_promotion_allowed"] is False
    assert summary["next_required_step"].startswith("BindingDB similarity seed expansion also failed")

    action = {row["check_id"]: row for row in payload["rows"]}["candidate_pool_geometry_stability_blocked"]
    assert action["external_bindingdb_similarity_row_count"] == 9
    assert action["external_bindingdb_similarity_energy_pass_count"] == 1
    assert action["external_bindingdb_similarity_best_binding_energy_proxy"] == -0.5995


def test_build_translation_quality_packet_treats_false_string_as_blocked() -> None:
    payload = build_payload(
        {
            "summary": {
                "wetlab_final_gate_pass": "true",
                "commercial_hard_gate_pass_v2": "false",
                "translation_gate_focus_status": "pass",
            },
            "rows": [],
        }
    )

    assert payload["summary"]["wetlab_final_gate_pass"] is True
    assert payload["summary"]["commercial_hard_gate_pass"] is False
    assert payload["summary"]["allatom_delivery_p0_green"] is False
    assert payload["summary"]["translation_quality_ready"] is False
