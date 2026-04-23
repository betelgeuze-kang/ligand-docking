from tools import build_wetlab_tcruzi_pde_rescue_operator_packet as mod


def test_build_wetlab_tcruzi_pde_rescue_operator_packet_builds_top4_only_operator_view() -> None:
    review_packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "promoted_candidate_count": 4,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "best_ligand_id": "lig-001",
            "best_compound_name": "Strict Lead",
            "best_compound_name_human_readable": "Strict Lead",
            "best_compound_name_resolution": "human_readable",
            "best_smiles": "CCO",
            "best_mean_min_distance_A": 0.672,
            "next_required_step": "Use the promoted top-4 packet.",
        },
        "rows": [
            {
                "packet_rank": 1,
                "ligand_id": "lig-001",
                "compound_name": "Strict Lead",
                "compound_name_human_readable": "Strict Lead",
                "compound_name_resolution": "human_readable",
                "smiles": "CCO",
                "promotion_band": "under_2p5",
                "mean_min_distance_A": 0.672,
                "review_action": "strict_promote_rescue_only_branch",
                "binding_energy_proxy": -7.2,
                "stability_score": 0.81,
                "contact_fraction": 0.72,
            },
            {
                "packet_rank": 2,
                "ligand_id": "lig-002",
                "compound_name": "chembl_cache_fake123",
                "compound_name_human_readable": "",
                "compound_name_resolution": "cache_placeholder",
                "smiles": "CCC",
                "promotion_band": "near_band",
                "mean_min_distance_A": 2.88,
                "review_action": "near_band_manual_review_rescue_only_branch",
            },
        ],
    }
    branch_summary = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "target_id": "wrong target",
            "shard_id": "01_of_20",
            "selected_command_kind": "branch_summary_override",
            "selected_threshold_A": 9.9,
            "next_required_step": "This branch summary should not drive the operator packet.",
        }
    }

    payload = mod.build_payload(review_packet, branch_summary)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_pde_rescue_operator_packet_ready"
    assert summary["packet_scope"] == "partner_operator_rescue_only_review"
    assert summary["review_unit_kind"] == "promoted_top4_rescue_unit_only"
    assert summary["packet_ready_for_operator_review"] is True
    assert summary["promoted_unit_source_status"] == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
    assert summary["partner_track_id"] == "DNDi_IPK"
    assert summary["partner_track_label"] == "DNDi / Institut Pasteur Korea"
    assert summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert summary["selected_threshold_A"] == 2.5
    assert summary["near_threshold_A"] == 3.0
    assert summary["strict_candidate_count"] == 1
    assert summary["manual_review_candidate_count"] == 3
    assert summary["best_compound_name"] == "Strict Lead"
    assert summary["best_compound_name_human_readable"] == "Strict Lead"
    assert summary["best_compound_name_resolution"] == "human_readable"
    assert summary["best_smiles"] == "CCO"
    assert summary["outbound_partner_send_allowed_now"] is False
    assert summary["next_required_step"].startswith(
        "Use this PDE rescue operator packet as the partner/operator review surface"
    )
    assert len(rows) == 2
    assert rows[0]["compound_name"] == "Strict Lead"
    assert rows[0]["compound_name_resolution"] == "human_readable"
    assert rows[0]["operator_review_bucket"] == "strict_promote_candidate_review"
    assert rows[0]["operator_decision_hint"] == "promote_rescue_only_branch"
    assert rows[0]["partner_track_id"] == "DNDi_IPK"
    assert rows[0]["partner_review_status"] == "internal_rescue_review_only"
    assert rows[0]["outbound_send_allowed_now"] == "no"
    assert rows[1]["compound_name"] == "chembl_cache_fake123"
    assert rows[1]["compound_name_resolution"] == "cache_placeholder"
    assert rows[1]["operator_review_bucket"] == "near_band_manual_candidate_review"
    assert rows[1]["operator_decision_hint"] == "manual_review_rescue_only_branch"
