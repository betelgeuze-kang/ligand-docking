from __future__ import annotations

import pytest

from tools import build_wetlab_rescue_only_branch_templates as templates_mod
from tools import wetlab_rescue_only_branch_builder as branch_mod


@pytest.mark.parametrize(
    (
        "target_id",
        "branch_key",
        "branch_label",
        "review_surface_artifact",
        "review_packet_artifact",
        "operator_packet_artifact",
        "branch_summary_artifact",
        "branch_runner_artifact",
        "shard_id",
    ),
    [
        (
            "Cathepsin K",
            "cathepsin_k",
            "cathepsin_k_rescue_only_branch",
            "runs/wetlab_cathepsin_k_rescue_review_surface_current.md",
            "runs/wetlab_cathepsin_k_promoted_top4_review_packet_current.md",
            "runs/wetlab_cathepsin_k_rescue_operator_packet_current.md",
            "runs/wetlab_cathepsin_k_rescue_only_branch_summary_current.md",
            "runs/wetlab_cathepsin_k_rescue_only_branch_runner_current.md",
            "05_of_20",
        ),
        (
            "Dengue NS2B-NS3 protease",
            "dengue_ns2b_ns3_protease",
            "dengue_ns2b_ns3_protease_rescue_only_branch",
            "runs/wetlab_dengue_ns2b_ns3_rescue_review_surface_current.md",
            "runs/wetlab_dengue_ns2b_ns3_promoted_top4_review_packet_current.md",
            "runs/wetlab_dengue_ns2b_ns3_rescue_operator_packet_current.md",
            "runs/wetlab_dengue_ns2b_ns3_rescue_only_branch_summary_current.md",
            "runs/wetlab_dengue_ns2b_ns3_rescue_only_branch_runner_current.md",
            "09_of_20",
        ),
    ],
)
def test_build_rescue_only_branch_summary_payload_supports_non_pde_operator_packets(
    target_id: str,
    branch_key: str,
    branch_label: str,
    review_surface_artifact: str,
    review_packet_artifact: str,
    operator_packet_artifact: str,
    branch_summary_artifact: str,
    branch_runner_artifact: str,
    shard_id: str,
) -> None:
    template = branch_mod.RescueOnlyBranchTemplate(
        branch_key=branch_key,
        target_id=target_id,
        branch_label=branch_label,
        review_unit_label="promoted top-4 packet",
        review_surface_artifact=review_surface_artifact,
        review_surface_title=f"Wet-Lab {target_id} Rescue Review Surface",
        review_packet_artifact=review_packet_artifact,
        review_packet_title=f"Wet-Lab {target_id} Promoted Top-4 Review Packet",
        operator_packet_artifact=operator_packet_artifact,
        operator_packet_title=f"Wet-Lab {target_id} Rescue Operator Packet",
        branch_runner_artifact=branch_runner_artifact,
        branch_runner_title=f"Wet-Lab {target_id} Rescue-Only Branch Runner",
        branch_summary_artifact=branch_summary_artifact,
        branch_summary_title=f"Wet-Lab {target_id} Rescue-Only Branch Summary",
        review_packet_step_id="promoted_top4_review_packet",
        review_packet_signal_suffix="promoted",
        review_packet_ready_alias="promoted_top4_packet_ready",
        review_packet_candidate_count_alias="promoted_candidate_count",
        strict_candidate_count_alias="under_2p5_candidate_count",
        ready_branch_state="promoted_top4_packet_ready_default_lane_closed",
    )

    review_surface_payload = {
        "summary": {
            "status": f"wetlab_{branch_key}_rescue_review_surface_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "decision": "promote_rescue_only_branch_keep_default_closed",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "branch_to_rescue_only": True,
            "default_lane_reopen_allowed": False,
        },
        "rows": [
            {
                "ligand_id": f"{branch_key}_ligand_001",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 1.234,
            }
        ],
    }
    review_packet_payload = {
        "summary": {
            "status": f"wetlab_{branch_key}_promoted_top4_review_packet_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "review_packet_ready": True,
            "review_packet_candidate_count": 4,
            "strict_candidate_count": 1,
            "near_candidate_count": 3,
            "best_ligand_id": f"{branch_key}_ligand_001",
            "best_mean_min_distance_A": 1.234,
            "packet_ready": True,
        },
        "rows": [
            {"ligand_id": f"{branch_key}_ligand_001"},
            {"ligand_id": f"{branch_key}_ligand_002"},
        ],
    }
    branch_runner_payload = {
        "summary": {
            "status": f"wetlab_{branch_key}_rescue_only_branch_runner_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "branch_label": branch_label,
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
    three_bead_slice_payload = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "execution_mode": "local_refine_scoring_executed",
            "scoring_status": "pass",
        }
    }
    operator_packet_payload = {
        "summary": {
            "status": f"wetlab_{branch_key}_rescue_operator_packet_ready",
            "target_id": target_id,
            "packet_scope": "partner_operator_rescue_only_review",
            "packet_ready": True,
            "review_unit_kind": "promoted_top4_rescue_unit_only",
            "promoted_candidate_count": 4,
            "manual_review_candidate_count": 3,
            "strict_candidate_count": 1,
            "next_required_step": f"Use the {target_id} rescue operator packet as the partner/operator review surface.",
        }
    }

    payload = branch_mod.build_rescue_only_branch_summary_payload(
        template,
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
        operator_packet_payload=operator_packet_payload,
    )

    summary = payload["summary"]
    rows = payload["rows"]
    structured = payload["structured"]

    assert summary["status"] == template.summary_status
    assert summary["target_id"] == target_id
    assert summary["branch_label"] == branch_label
    assert summary["branch_state"] == "promoted_top4_packet_ready_default_lane_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_rescue_only"] is True
    assert summary["review_unit_label"] == "promoted top-4 packet"
    assert summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert summary["selected_threshold_A"] == 2.5
    assert summary["review_packet_ready"] is True
    assert summary["promoted_top4_packet_ready"] is True
    assert summary["review_packet_candidate_count"] == 4
    assert summary["promoted_candidate_count"] == 4
    assert summary["strict_candidate_count"] == 1
    assert summary["near_candidate_count"] == 3
    assert summary["best_ligand_id"] == f"{branch_key}_ligand_001"
    assert summary["best_mean_min_distance_A"] == 1.234
    assert summary["runner_status"] == f"wetlab_{branch_key}_rescue_only_branch_runner_ready"
    assert summary["operator_packet_ready"] is True
    assert summary["operator_packet_scope"] == "partner_operator_rescue_only_review"
    assert summary["three_bead_scoring_status"] == "pass"
    assert summary["execution_mode"] == "adopted_from_generic_rescue_lane"
    assert summary["next_required_step"].startswith(
        f"Operate {target_id} through the dedicated rescue-only branch"
    )

    assert [row["step_id"] for row in rows] == [
        "rescue_review_surface",
        "promoted_top4_review_packet",
        "rescue_operator_packet",
        "rescue_only_branch_runner",
        "three_bead_slice",
    ]
    assert rows[1]["artifact"] == review_packet_artifact
    assert rows[2]["artifact"] == operator_packet_artifact
    assert rows[2]["signal"] == "partner_operator_rescue_only_review"
    assert structured[template.operator_packet_structured_key] == operator_packet_artifact
    assert structured[template.review_packet_structured_key] == review_packet_artifact


def test_build_wetlab_rescue_only_branch_templates_includes_cathepsin_k_and_dengue_additional_entries() -> None:
    branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "target_id": "T. cruzi PDE",
            "branch_label": "tcruzi_pde_rescue_only_branch",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "best_ligand_id": "lig-001",
            "best_mean_min_distance_A": 0.672,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch.",
        }
    }
    packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
            "target_id": "T. cruzi PDE",
            "best_ligand_id": "lig-001",
            "best_mean_min_distance_A": 0.672,
        }
    }
    cathepsin_branch_summary = {
        "summary": {
            "status": "wetlab_cathepsin_k_rescue_only_branch_summary_ready",
            "target_id": "Cathepsin K",
            "branch_label": "cathepsin_k_rescue_only_branch",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "best_ligand_id": "cathepsin_k_lig_001",
            "best_mean_min_distance_A": 1.234,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "next_required_step": "Operate Cathepsin K through the dedicated rescue-only branch.",
        }
    }
    cathepsin_packet = {
        "summary": {
            "status": "wetlab_cathepsin_k_promoted_top4_review_packet_ready",
            "target_id": "Cathepsin K",
            "best_ligand_id": "cathepsin_k_lig_001",
            "best_mean_min_distance_A": 1.234,
        }
    }
    dengue_branch_summary = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_rescue_only_branch_summary_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "branch_label": "dengue_ns2b_ns3_protease_rescue_only_branch",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "best_ligand_id": "dengue_ns2b_ns3_lig_001",
            "best_mean_min_distance_A": 1.567,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "next_required_step": "Operate Dengue NS2B-NS3 protease through the dedicated rescue-only branch.",
        }
    }
    dengue_packet = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_promoted_top4_review_packet_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "best_ligand_id": "dengue_ns2b_ns3_lig_001",
            "best_mean_min_distance_A": 1.567,
        }
    }

    payload = templates_mod.build_payload(
        branch_summary,
        packet,
        additional_rescue_only_branch_target_entries=[
            {
                "branch_summary_payload": cathepsin_branch_summary,
                "promoted_top4_review_packet_payload": cathepsin_packet,
                "template_label": "three_bead_rescue_only_branch",
                "surface_label": "cathepsin_k_rescue_only_branch",
                "review_unit_label": "promoted_top4_three_bead_rescue_review",
                "source_surface": "cathepsin_k_rescue_only_branch_summary",
                "branch_summary_artifact": "runs/wetlab_cathepsin_k_rescue_only_branch_summary_current.md",
                "review_packet_artifact": "runs/wetlab_cathepsin_k_promoted_top4_review_packet_current.md",
                "rescue_operator_packet_artifact": "runs/wetlab_cathepsin_k_rescue_operator_packet_current.md",
            },
            {
                "branch_summary_payload": dengue_branch_summary,
                "promoted_top4_review_packet_payload": dengue_packet,
                "template_label": "three_bead_rescue_only_branch",
                "surface_label": "dengue_ns2b_ns3_protease_rescue_only_branch",
                "review_unit_label": "promoted_top4_three_bead_rescue_review",
                "source_surface": "dengue_ns2b_ns3_protease_rescue_only_branch_summary",
                "branch_summary_artifact": "runs/wetlab_dengue_ns2b_ns3_rescue_only_branch_summary_current.md",
                "review_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_promoted_top4_review_packet_current.md",
                "rescue_operator_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_rescue_operator_packet_current.md",
            },
        ],
    )

    summary = payload["summary"]
    rows = payload["rows"]
    structured = payload["structured"]

    assert summary["status"] == "wetlab_rescue_only_branch_templates_ready"
    assert summary["template_target_count"] == 3
    assert summary["additional_rescue_only_branch_target_count"] == 2
    assert summary["focus_target_id"] == "T. cruzi PDE"
    assert summary["focus_template_label"] == "three_bead_rescue_only_branch"
    assert summary["focus_surface_label"] == "pde_rescue_only_branch"
    assert summary["first_additional_rescue_only_branch_target"] == "Cathepsin K"
    assert [row["target_id"] for row in rows] == [
        "T. cruzi PDE",
        "Cathepsin K",
        "Dengue NS2B-NS3 protease",
    ]
    assert rows[1]["review_unit_label"] == "promoted_top4_three_bead_rescue_review"
    assert rows[1]["surface_label"] == "cathepsin_k_rescue_only_branch"
    assert rows[2]["review_unit_label"] == "promoted_top4_three_bead_rescue_review"
    assert rows[2]["surface_label"] == "dengue_ns2b_ns3_protease_rescue_only_branch"
    assert structured["additional_rescue_only_branch_target_artifacts"] == [
        {
            "target_id": "Cathepsin K",
            "template_label": "three_bead_rescue_only_branch",
            "surface_label": "cathepsin_k_rescue_only_branch",
            "branch_summary_artifact": "runs/wetlab_cathepsin_k_rescue_only_branch_summary_current.md",
            "review_packet_artifact": "runs/wetlab_cathepsin_k_promoted_top4_review_packet_current.md",
            "rescue_operator_packet_artifact": "runs/wetlab_cathepsin_k_rescue_operator_packet_current.md",
        },
        {
            "target_id": "Dengue NS2B-NS3 protease",
            "template_label": "three_bead_rescue_only_branch",
            "surface_label": "dengue_ns2b_ns3_protease_rescue_only_branch",
            "branch_summary_artifact": "runs/wetlab_dengue_ns2b_ns3_rescue_only_branch_summary_current.md",
            "review_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_promoted_top4_review_packet_current.md",
            "rescue_operator_packet_artifact": "runs/wetlab_dengue_ns2b_ns3_rescue_operator_packet_current.md",
        },
    ]
