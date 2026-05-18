from __future__ import annotations

import json
from pathlib import Path

from tools import wetlab_rescue_only_branch_builder as mod
from tools.wetlab_target_render_utils import load_json


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_rescue_only_branch_supports_non_pde_target_templates(tmp_path: Path) -> None:
    template = mod.RescueOnlyBranchTemplate(
        branch_key="cruzain",
        target_id="Cruzain",
        branch_label="cruzain_rescue_only_branch",
        review_unit_label="promoted top-6 packet",
        review_surface_artifact="runs/wetlab_cruzain_rescue_review_surface_current.md",
        review_surface_title="Wet-Lab Cruzain Rescue Review Surface",
        review_packet_artifact="runs/wetlab_cruzain_promoted_top6_review_packet_current.md",
        review_packet_title="Wet-Lab Cruzain Promoted Top-6 Review Packet",
        branch_runner_artifact="runs/wetlab_cruzain_rescue_only_branch_runner_current.md",
        branch_runner_title="Wet-Lab Cruzain Rescue-Only Branch Runner",
        branch_summary_artifact="runs/wetlab_cruzain_rescue_only_branch_summary_current.md",
        branch_summary_title="Wet-Lab Cruzain Rescue-Only Branch Summary",
        review_packet_step_id="promoted_top6_review_packet",
        review_packet_signal_suffix="promoted",
        review_packet_ready_alias="promoted_top6_packet_ready",
        review_packet_candidate_count_alias="promoted_candidate_count",
        ready_branch_state="promoted_top6_packet_ready_default_lane_closed",
    )

    review_surface_json = tmp_path / "review_surface.json"
    runner_json = tmp_path / "hard_target_runner.json"
    slice_json = tmp_path / "three_bead_slice.json"
    review_packet_md = tmp_path / "review_packet.md"
    branch_summary_md = tmp_path / "branch_summary.md"
    out_md = tmp_path / "branch_runner.md"

    _write_json(
        review_surface_json,
        {
            "summary": {
                "status": "wetlab_cruzain_rescue_review_surface_ready",
                "target_id": "Cruzain",
                "shard_id": "04_of_20",
                "selected_command_kind": "three_bead_rescue_local_refine",
                "selected_threshold_A": 2.3,
                "branch_to_rescue_only": True,
                "decision": "promote_rescue_only_branch_keep_default_closed",
            }
        },
    )
    _write_json(
        runner_json,
        {
            "summary": {
                "status": "wetlab_hard_target_rescue_runner_ready",
                "target_id": "Cruzain",
                "shard_id": "04_of_20",
            }
        },
    )
    _write_json(
        slice_json,
        {
            "summary": {
                "status": "wetlab_rescue_three_bead_slice_ready",
                "target_id": "Cruzain",
                "shard_id": "04_of_20",
                "selected_command_kind": "three_bead_rescue_local_refine",
                "execution_mode": "local_refine_scoring_executed",
                "scoring_status": "pass",
            }
        },
    )

    def _packet_builder(review_surface_payload: dict, three_bead_slice_payload: dict | None) -> dict:
        return {
            "summary": {
                "status": "wetlab_cruzain_promoted_top6_review_packet_ready",
                "target_id": review_surface_payload["summary"]["target_id"],
                "shard_id": review_surface_payload["summary"]["shard_id"],
                "selected_command_kind": "three_bead_rescue_local_refine",
                "strict_threshold_A": 2.3,
                "review_packet_ready": True,
                "review_packet_candidate_count": 6,
                "strict_candidate_count": 2,
                "near_candidate_count": 3,
                "best_ligand_id": "cruzain_lig_001",
                "best_mean_min_distance_A": 1.234,
                "packet_ready": True,
            },
            "rows": [
                {"ligand_id": "cruzain_lig_001"},
                {"ligand_id": "cruzain_lig_002"},
            ],
        }

    payload = mod.run_rescue_only_branch(
        template=template,
        review_packet_builder=_packet_builder,
        review_surface_json=str(review_surface_json),
        hard_target_rescue_runner_json=str(runner_json),
        three_bead_slice_json=str(slice_json),
        review_packet_md=str(review_packet_md),
        branch_summary_md=str(branch_summary_md),
        out_md=str(out_md),
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_cruzain_rescue_only_branch_runner_ready"
    assert summary["target_id"] == "Cruzain"
    assert summary["branch_label"] == "cruzain_rescue_only_branch"
    assert summary["review_packet_ready"] is True
    assert summary["promoted_top6_packet_ready"] is True
    assert summary["review_packet_candidate_count"] == 6
    assert summary["promoted_candidate_count"] == 6
    assert summary["strict_candidate_count"] == 2
    assert summary["near_candidate_count"] == 3
    assert summary["next_required_step"].startswith(
        "Operate Cruzain through the dedicated rescue-only branch"
    )

    branch_summary_payload = load_json(str(branch_summary_md.with_suffix(".json")))
    branch_summary = branch_summary_payload["summary"]
    assert branch_summary["status"] == "wetlab_cruzain_rescue_only_branch_summary_ready"
    assert branch_summary["branch_state"] == "promoted_top6_packet_ready_default_lane_closed"
    assert branch_summary["selected_threshold_A"] == 2.3
    assert branch_summary["best_ligand_id"] == "cruzain_lig_001"
    assert branch_summary["best_mean_min_distance_A"] == 1.234
    assert branch_summary["promoted_candidate_count"] == 6
    assert branch_summary_payload["rows"][1]["step_id"] == "promoted_top6_review_packet"
    assert branch_summary_payload["rows"][1]["signal"].startswith("6 promoted")
    assert "promoted top-6 packet" in branch_summary["next_required_step"]
