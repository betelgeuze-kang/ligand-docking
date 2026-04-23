from __future__ import annotations

from tools import build_wetlab_tcruzi_pde_rescue_operator_packet as operator_mod
from tools import build_wetlab_tcruzi_pde_promoted_top4_review_packet as packet_mod
from tools import build_wetlab_tcruzi_pde_rescue_only_branch_summary as mod


def test_build_wetlab_tcruzi_pde_rescue_only_branch_summary_promotes_dedicated_branch() -> None:
    review_surface_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "decision": "promote_rescue_only_branch_keep_default_closed",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "near_threshold_A": 3.0,
            "branch_to_rescue_only": True,
            "default_lane_reopen_allowed": False,
        },
        "rows": [
            {
                "ligand_id": "ligand_strict",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 0.6724,
                "binding_energy_proxy": -9.1,
                "stability_score": 0.88,
                "contact_fraction": 0.81,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q1",
            },
            {
                "ligand_id": "ligand_near_1",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7565,
                "binding_energy_proxy": -8.4,
                "stability_score": 0.74,
                "contact_fraction": 0.67,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q2",
            },
            {
                "ligand_id": "ligand_near_2",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7927,
                "binding_energy_proxy": -8.0,
                "stability_score": 0.72,
                "contact_fraction": 0.62,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q3",
            },
            {
                "ligand_id": "ligand_near_3",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.9151,
                "binding_energy_proxy": -7.6,
                "stability_score": 0.68,
                "contact_fraction": 0.58,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q4",
            },
        ],
    }
    three_bead_slice_payload = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "slice_candidate_count": 8,
            "execution_mode": "local_refine_scoring_executed",
            "scoring_status": "pass",
        }
    }
    review_packet_payload = packet_mod.build_payload(review_surface_payload, three_bead_slice_payload)
    review_packet_payload["summary"].update(
        {
            "packet_ready_for_operator_review": True,
            "wetlab_final_gate_pass": False,
            "claim_gate_available": True,
            "claim_ready_for_allatom": False,
        }
    )
    operator_packet_payload = operator_mod.build_payload(review_packet_payload)
    branch_runner_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_runner_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "branch_label": "tcruzi_pde_rescue_only_branch",
            "branch_state": "adopted_from_generic_rescue_lane",
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "promoted_top4_packet_ready": True,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "source_runner_status": "wetlab_hard_target_rescue_runner_ready",
            "source_slice_status": "wetlab_rescue_three_bead_slice_ready",
            "execution_mode": "adopted_from_generic_rescue_lane",
            "scoring_status": "pass",
        }
    }

    payload = mod.build_payload(
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
        operator_packet_payload=operator_packet_payload,
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
    assert summary["target_id"] == "T. cruzi PDE"
    assert summary["shard_id"] == "20_of_20"
    assert summary["branch_label"] == "tcruzi_pde_rescue_only_branch"
    assert summary["branch_state"] == "promoted_top4_packet_ready_default_lane_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_rescue_only"] is True
    assert summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert summary["selected_threshold_A"] == 2.5
    assert summary["review_packet_ready"] is True
    assert summary["promoted_top4_packet_ready"] is True
    assert summary["promoted_candidate_count"] == 4
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["near_candidate_count"] == 3
    assert summary["best_ligand_id"] == "ligand_strict"
    assert summary["best_mean_min_distance_A"] == 0.672
    assert summary["runner_status"] == "wetlab_tcruzi_pde_rescue_only_branch_runner_ready"
    assert summary["operator_packet_ready"] is True
    assert summary["operator_packet_scope"] == "partner_operator_rescue_only_review"
    assert summary["three_bead_scoring_status"] == "pass"
    assert summary["execution_mode"] == "adopted_from_generic_rescue_lane"
    assert summary["next_required_step"].startswith(
        "Operate T. cruzi PDE through the dedicated rescue-only branch"
    )

    assert [row["step_id"] for row in rows] == [
        "rescue_review_surface",
        "promoted_top4_review_packet",
        "rescue_operator_packet",
        "rescue_only_branch_runner",
        "three_bead_slice",
    ]
    assert rows[1]["signal"] == "4 promoted; operator_review=yes; final_gate=no"
    assert rows[1]["packet_ready_for_operator_review"] is True
    assert rows[1]["wetlab_final_gate_pass"] is False
    assert rows[2]["signal"] == "partner_operator_rescue_only_review"
    assert rows[2]["packet_ready_for_operator_review"] is True
    assert rows[2]["wetlab_final_gate_pass"] is False
    assert rows[0]["signal"] == "promote_rescue_only_branch_keep_default_closed"
    assert rows[3]["signal"] == "adopted_from_generic_rescue_lane"
    assert rows[4]["signal"] == "pass"


def test_build_wetlab_tcruzi_pde_rescue_only_branch_summary_keeps_legacy_packet_ready_review_only() -> None:
    review_surface_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "decision": "promote_rescue_only_branch_keep_default_closed",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "near_threshold_A": 3.0,
            "branch_to_rescue_only": True,
            "default_lane_reopen_allowed": False,
        },
        "rows": [
            {
                "ligand_id": "ligand_strict",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 0.6724,
                "binding_energy_proxy": -9.1,
                "stability_score": 0.88,
                "contact_fraction": 0.81,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q1",
            },
            {
                "ligand_id": "ligand_near_1",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7565,
                "binding_energy_proxy": -8.4,
                "stability_score": 0.74,
                "contact_fraction": 0.67,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q2",
            },
        ],
    }
    three_bead_slice_payload = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "slice_candidate_count": 8,
            "execution_mode": "local_refine_scoring_executed",
            "scoring_status": "pass",
        }
    }
    review_packet_payload = packet_mod.build_payload(review_surface_payload, three_bead_slice_payload)
    review_packet_payload["summary"].pop("packet_ready_for_operator_review", None)
    review_packet_payload["summary"].update(
        {
            "wetlab_final_gate_pass": False,
            "claim_gate_available": True,
            "claim_ready_for_allatom": False,
        }
    )
    operator_packet_payload = operator_mod.build_payload(review_packet_payload)
    branch_runner_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_runner_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "branch_label": "tcruzi_pde_rescue_only_branch",
            "branch_state": "adopted_from_generic_rescue_lane",
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "promoted_top4_packet_ready": True,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "source_runner_status": "wetlab_hard_target_rescue_runner_ready",
            "source_slice_status": "wetlab_rescue_three_bead_slice_ready",
            "execution_mode": "adopted_from_generic_rescue_lane",
            "scoring_status": "pass",
        }
    }

    payload = mod.build_payload(
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
        operator_packet_payload=operator_packet_payload,
    )

    summary = payload["summary"]
    assert summary["review_packet_ready_for_operator_review"] is True
    assert summary["review_packet_ready_source"] == "packet_ready"
    assert summary["review_packet_final_gate_pass"] is False
    assert summary["review_packet_final_gate_source"] == "wetlab_final_gate_pass"
    assert summary["review_packet_final_gate_legacy_fallback"] is False
    assert summary["branch_ready_for_operator_review"] is True
    assert summary["branch_ready_for_final_wetlab"] is False
    assert "operator-review only" in summary["next_required_step"]
    assert "legacy packet readiness" not in summary["next_required_step"]
