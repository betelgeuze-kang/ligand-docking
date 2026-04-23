from __future__ import annotations

from tools import build_wetlab_mapping_fix_retry_policy_templates as mod


def test_build_wetlab_mapping_fix_retry_policy_templates_groups_stage1_repair_targets() -> None:
    stage1_mapping_fix_lanes = {
        "summary": {
            "status": "wetlab_stage1_mapping_fix_lanes_ready",
            "target_count": 2,
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    mpro_lane = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_lane_ready",
            "target_id": "SARS-CoV-2 Mpro",
            "shard_id": "01_of_20",
            "recommended_retry_mode": "mapping_fix_required",
            "stage1_mapping_failed_count": 1,
            "stage6_distance_gate_failed_count": 19,
            "guard_limit": 3,
            "selected_command_kind": "throughput_preflight",
            "ready_for_mapping_fix_retry": True,
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    tcruzi_lane = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_lane_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "07_of_20",
            "recommended_retry_mode": "mapping_fix_required",
            "stage1_mapping_failed_count": 1,
            "stage6_distance_gate_failed_count": 19,
            "guard_limit": 3,
            "selected_command_kind": "throughput_preflight",
            "ready_for_mapping_fix_retry": True,
            "next_required_step": "Run the mapping-fix retry runner for T. cruzi PDE 07_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }

    payload = mod.build_payload(stage1_mapping_fix_lanes, mpro_lane, tcruzi_lane)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_mapping_fix_retry_policy_templates_ready"
    assert summary["template_target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert summary["ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert summary["focus_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["focus_template_label"] == "mapping_fix_branch_only"
    assert summary["focus_selected_command_kind"] == "throughput_preflight"
    assert summary["next_required_step"].startswith("Run the mapping-fix retry runner for SARS-CoV-2 Mpro")

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["SARS-CoV-2 Mpro"]["template_label"] == "mapping_fix_branch_only"
    assert rows["SARS-CoV-2 Mpro"]["default_lane_policy"] == "keep_default_closed_until_mapping_fix_clean_summary"
    assert rows["SARS-CoV-2 Mpro"]["autostart_policy"] == "manual_mapping_diagnostics_before_any_reopen"
    assert rows["SARS-CoV-2 Mpro"]["selected_threshold_A"] == 0.0
    assert rows["T. cruzi PDE"]["target_class"] == "pathogen_phosphodiesterase"


def test_build_wetlab_mapping_fix_retry_policy_templates_omits_targets_promoted_to_stage6_tuning() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_stage1_mapping_fix_lanes_ready", "next_required_step": "Review the explicit stage1 mapping-fix lanes before reopening mapping-fix retries."}},
        {"summary": {"status": "wetlab_mapping_fix_retry_lane_ready", "target_id": "SARS-CoV-2 Mpro", "ready_for_mapping_fix_retry": True}},
        {"summary": {"status": "wetlab_mapping_fix_retry_lane_ready", "target_id": "T. cruzi PDE", "ready_for_mapping_fix_retry": True}},
        {"summary": {"status": "wetlab_sarscov2_mpro_stage6_tuning_surface_ready", "target_id": "SARS-CoV-2 Mpro"}},
        {"summary": {"status": "wetlab_tcruzi_pde_stage6_tuning_surface_ready", "target_id": "T. cruzi PDE"}},
    )

    summary = payload["summary"]
    assert summary["template_target_count"] == 0
    assert summary["ready_target_count"] == 0
    assert payload["rows"] == []
