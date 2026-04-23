from __future__ import annotations

from tools import build_nightly_stage6_downstream_rerun_packet as mod


def test_build_nightly_stage6_downstream_rerun_packet() -> None:
    payload = mod.build_payload(
        rescored_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_rescored_gate_packet_current.md",
                "primary_applied_row_key": "HIV1_PROTEASE::aspirin",
                "companion_applied_row_key": "HIV1_PROTEASE::imatinib",
                "primary_anchor_row_key": "EGFR_KINASE::imatinib",
                "primary_canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                "rescored_gate_mean_min_distance_A": 2.2707623770833014,
                "gate_threshold_A": 2.5,
                "rescored_gate_pass": True,
                "downstream_rerun_ready": True,
            },
            "rows": [
                {
                    "topk_rank": 1,
                    "row_key": "EGFR_KINASE::imatinib",
                    "target": "EGFR_KINASE",
                    "ligand_id": "imatinib",
                    "lane_status": "kept_anchor_row",
                    "canonical_retry_preset_id": "",
                    "rescored_mean_min_distance_A": 2.284,
                    "gate_margin_A": 0.216,
                    "source_packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                },
                {
                    "topk_rank": 2,
                    "row_key": "EGFR_KINASE::aspirin",
                    "target": "EGFR_KINASE",
                    "ligand_id": "aspirin",
                    "lane_status": "kept_original_above_threshold_row",
                    "canonical_retry_preset_id": "",
                    "rescored_mean_min_distance_A": 3.014,
                    "gate_margin_A": -0.514,
                    "source_packet_artifact": "runs/nightly_stage6_tuning_packet_current.md",
                },
                {
                    "topk_rank": 3,
                    "row_key": "HIV1_PROTEASE::imatinib",
                    "target": "HIV1_PROTEASE",
                    "ligand_id": "imatinib",
                    "lane_status": "canonical_retry_replacement",
                    "canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                    "rescored_mean_min_distance_A": 2.215,
                    "gate_margin_A": 0.285,
                    "source_packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
                },
                {
                    "topk_rank": 4,
                    "row_key": "HIV1_PROTEASE::aspirin",
                    "target": "HIV1_PROTEASE",
                    "ligand_id": "aspirin",
                    "lane_status": "canonical_retry_replacement",
                    "canonical_retry_preset_id": "target_forced_adress_uncapped_probe",
                    "rescored_mean_min_distance_A": 1.604,
                    "gate_margin_A": 0.896,
                    "source_packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
                },
            ],
        },
        realization_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_realization_packet_current.md",
            }
        },
        base_profile_payload={
            "version": "ligand_htvs_nightly_strict_v1",
            "description": "Strict nightly profile.",
            "targets": "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE",
            "run_scope": "smoke_then_full",
            "retry": {"max_attempts": 3, "sleep_sec": 20},
        },
        dry_run_status_payload={
            "pass": False,
            "attempt_count": 1,
            "command": {"returncode": 2},
            "artifacts": {
                "status_json": "runs/nightly_stage6_downstream_rerun_current_status.json",
                "status_md": "runs/nightly_stage6_downstream_rerun_current_status.md",
                "pipeline_summary_json": "runs/nightly_stage6_downstream_rerun_current_summary.json",
                "pipeline_summary_md": "runs/nightly_stage6_downstream_rerun_current_summary.md",
            },
        },
        downstream_date_tag="2026-04-22_stage6_downstream_rerun",
    )

    summary = payload["summary"]
    profile = payload["downstream_profile"]
    assert summary["status"] == "nightly_stage6_downstream_rerun_packet_ready"
    assert summary["target_subset"] == "EGFR_KINASE,HIV1_PROTEASE"
    assert summary["row_count"] == 4
    assert summary["gate_distance_override_csv_artifact"] == "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
    assert summary["gate_distance_override_row_count"] == 2
    assert summary["primary_focus_row_key"] == "HIV1_PROTEASE::aspirin"
    assert summary["companion_focus_row_key"] == "HIV1_PROTEASE::imatinib"
    assert summary["anchor_row_key"] == "EGFR_KINASE::imatinib"
    assert summary["downstream_rerun_ready"] is True
    assert summary["dry_run_status_present"] is True
    assert summary["dry_run_command_validated"] is True
    assert "--dry-run" in summary["runner_dry_run_command"]
    assert "--no-dry-run" in summary["runner_execute_command"]
    assert "EGFR_KINASE,HIV1_PROTEASE" in summary["runner_dry_run_command"]
    assert profile["targets"] == "EGFR_KINASE,HIV1_PROTEASE"
    assert profile["run_scope"] == "smoke"
    assert profile["require_ood_eval"] is False
    assert profile["retry"] == {"max_attempts": 1, "sleep_sec": 0}
    assert profile["gate_distance_override_csv"] == "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
    assert profile["stage6_downstream_rerun_metadata"]["primary_applied_row_key"] == "HIV1_PROTEASE::aspirin"
    assert payload["gate_distance_override_rows"][0]["row_key"] == "HIV1_PROTEASE::aspirin"
    assert payload["rows"][0]["row_key"] == "EGFR_KINASE::imatinib"
    assert payload["rows"][2]["selected_for_downstream_rerun"] is True
