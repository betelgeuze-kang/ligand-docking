from tools import build_wetlab_rescue_only_branch_templates as mod


def test_build_wetlab_rescue_only_branch_templates_exposes_pde_branch() -> None:
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

    payload = mod.build_payload(branch_summary, packet)
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "wetlab_rescue_only_branch_templates_ready"
    assert summary["template_target_count"] == 1
    assert summary["additional_rescue_only_branch_target_count"] == 0
    assert summary["focus_target_id"] == "T. cruzi PDE"
    assert summary["focus_template_label"] == "three_bead_rescue_only_branch"
    assert summary["focus_surface_label"] == "pde_rescue_only_branch"
    assert summary["first_additional_rescue_only_branch_target"] == ""
    assert row["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert row["selected_threshold_A"] == 2.5
    assert payload["structured"]["tcruzi_pde_rescue_operator_packet_artifact"] == "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md"
    assert payload["structured"]["additional_rescue_only_branch_target_artifacts"] == []


def test_build_wetlab_rescue_only_branch_templates_includes_additional_rescue_only_branch_targets() -> None:
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
    additional_branch_summary = {
        "summary": {
            "status": "wetlab_cruzain_rescue_only_branch_summary_ready",
            "target_id": "Cruzain",
            "branch_label": "cruzain_rescue_only_branch",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.3,
            "promoted_candidate_count": 6,
            "under_2p5_candidate_count": 2,
            "near_candidate_count": 4,
            "best_ligand_id": "cruzain_lig_001",
            "best_mean_min_distance_A": 1.234,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "next_required_step": "Operate Cruzain through the dedicated rescue-only branch.",
        }
    }
    additional_packet = {
        "summary": {
            "status": "wetlab_cruzain_promoted_top6_review_packet_ready",
            "target_id": "Cruzain",
            "best_ligand_id": "cruzain_lig_001",
            "best_mean_min_distance_A": 1.234,
        }
    }

    payload = mod.build_payload(
        branch_summary,
        packet,
        additional_rescue_only_branch_target_entries=[
            {
                "branch_summary_payload": additional_branch_summary,
                "promoted_top4_review_packet_payload": additional_packet,
                "template_label": "three_bead_rescue_only_branch",
                "surface_label": "cruzain_rescue_only_branch",
                "review_unit_label": "promoted_top6_three_bead_rescue_review",
                "source_surface": "cruzain_rescue_only_branch_summary",
                "branch_summary_artifact": "runs/wetlab_cruzain_rescue_only_branch_summary_current.md",
                "review_packet_artifact": "runs/wetlab_cruzain_promoted_top6_review_packet_current.md",
                "rescue_operator_packet_artifact": "runs/wetlab_cruzain_rescue_operator_packet_current.md",
            }
        ],
    )

    summary = payload["summary"]
    rows = payload["rows"]
    structured = payload["structured"]

    assert summary["template_target_count"] == 2
    assert summary["additional_rescue_only_branch_target_count"] == 1
    assert summary["focus_target_id"] == "T. cruzi PDE"
    assert summary["first_additional_rescue_only_branch_target"] == "Cruzain"
    assert summary["next_required_step"] == "Operate T. cruzi PDE through the dedicated rescue-only branch."
    assert [row["target_id"] for row in rows] == ["T. cruzi PDE", "Cruzain"]
    assert rows[1]["surface_label"] == "cruzain_rescue_only_branch"
    assert rows[1]["review_unit_label"] == "promoted_top6_three_bead_rescue_review"
    assert structured["additional_rescue_only_branch_target_artifacts"] == [
        {
            "target_id": "Cruzain",
            "template_label": "three_bead_rescue_only_branch",
            "surface_label": "cruzain_rescue_only_branch",
            "branch_summary_artifact": "runs/wetlab_cruzain_rescue_only_branch_summary_current.md",
            "review_packet_artifact": "runs/wetlab_cruzain_promoted_top6_review_packet_current.md",
            "rescue_operator_packet_artifact": "runs/wetlab_cruzain_rescue_operator_packet_current.md",
        }
    ]
