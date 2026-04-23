from pathlib import Path

import pandas as pd

from tools import run_ligand_htvs_pipeline as htvs_pipeline
from tools import run_ligand_stress_validation as mod


def test_augment_eval_positive_count_adds_rows(tmp_path: Path):
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    out_labels_csv = tmp_path / "labels_aug.csv"
    out_split_csv = tmp_path / "split_aug.csv"

    labels = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "is_binder": 1, "reference_binding_kcal_mol": -9.2, "source": "ref"},
            {"target": "HIV1_PROTEASE", "ligand_id": "b2", "is_binder": 1, "reference_binding_kcal_mol": -8.8, "source": "ref"},
            {"target": "HIV1_PROTEASE", "ligand_id": "d1", "is_binder": 0, "reference_binding_kcal_mol": -1.1, "source": "ref"},
        ]
    )
    split = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "role": "far_ood_eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "b2", "role": "far_ood_eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "d1", "role": "far_ood_eval"},
        ]
    )
    labels.to_csv(labels_csv, index=False)
    split.to_csv(split_csv, index=False)

    stats = mod._augment_eval_positive_count(
        labels_csv=str(labels_csv),
        split_csv=str(split_csv),
        out_labels_csv=str(out_labels_csv),
        out_split_csv=str(out_split_csv),
        min_positive_count=5,
        eval_roles=["far_ood_eval"],
    )
    assert bool(stats["applied"]) is True
    assert int(stats["positive_count_before"]) == 2
    assert int(stats["positive_count_after"]) == 5
    assert int(stats["added_rows"]) == 3

    out_labels = pd.read_csv(out_labels_csv)
    out_split = pd.read_csv(out_split_csv)
    merged = out_labels.merge(out_split, on=["target", "ligand_id"], how="left")
    pos_eval = merged[(merged["role"] == "far_ood_eval") & (merged["is_binder"].astype(int) == 1)]
    assert int(len(pos_eval)) == 5


def test_augment_eval_positive_count_noop_when_satisfied(tmp_path: Path):
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    out_labels_csv = tmp_path / "labels_aug.csv"
    out_split_csv = tmp_path / "split_aug.csv"

    labels = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "is_binder": 1},
            {"target": "HIV1_PROTEASE", "ligand_id": "b2", "is_binder": 1},
            {"target": "HIV1_PROTEASE", "ligand_id": "b3", "is_binder": 1},
        ]
    )
    split = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "role": "far_ood_eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "b2", "role": "far_ood_eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "b3", "role": "far_ood_eval"},
        ]
    )
    labels.to_csv(labels_csv, index=False)
    split.to_csv(split_csv, index=False)

    stats = mod._augment_eval_positive_count(
        labels_csv=str(labels_csv),
        split_csv=str(split_csv),
        out_labels_csv=str(out_labels_csv),
        out_split_csv=str(out_split_csv),
        min_positive_count=2,
        eval_roles=["far_ood_eval"],
    )
    assert bool(stats["applied"]) is False
    assert int(stats["added_rows"]) == 0
    assert int(stats["positive_count_before"]) == 3
    assert int(stats["positive_count_after"]) == 3


def test_augment_eval_positive_count_handles_labels_with_existing_role(tmp_path: Path):
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    out_labels_csv = tmp_path / "labels_aug.csv"
    out_split_csv = tmp_path / "split_aug.csv"

    labels = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "is_binder": 1, "role": "legacy_role"},
            {"target": "HIV1_PROTEASE", "ligand_id": "d1", "is_binder": 0, "role": "legacy_role"},
        ]
    )
    split = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "ligand_id": "b1", "role": "far_ood_eval"},
            {"target": "HIV1_PROTEASE", "ligand_id": "d1", "role": "far_ood_eval"},
        ]
    )
    labels.to_csv(labels_csv, index=False)
    split.to_csv(split_csv, index=False)

    stats = mod._augment_eval_positive_count(
        labels_csv=str(labels_csv),
        split_csv=str(split_csv),
        out_labels_csv=str(out_labels_csv),
        out_split_csv=str(out_split_csv),
        min_positive_count=2,
        eval_roles=["far_ood_eval"],
    )
    assert bool(stats["applied"]) is True
    assert int(stats["positive_count_before"]) == 1
    assert int(stats["positive_count_after"]) == 2


def test_profile_traj_prod_args_default_off():
    cli = mod._profile_traj_prod_args({})
    assert cli[:2] == ["--traj-prod-stage2-preset", "off"]
    assert "--no-traj-prod-stage2-preset-strict" in cli
    assert "--no-traj-prod-speedpack" in cli
    assert "--no-traj-prod-early-stop-enabled" in cli
    assert cli[cli.index("--traj-prod-profile-intent") + 1] == ""
    assert "--traj-prod-light-artifacts" in cli
    assert cli[cli.index("--traj-prod-light-progress-every-jobs") + 1] == "250"


def test_profile_traj_prod_args_include_preset_and_speedpack_controls():
    cli = mod._profile_traj_prod_args(
        {
            "traj_prod_stage2_preset": "auto",
            "traj_prod_stage2_preset_strict": True,
            "traj_prod_speedpack": True,
            "traj_prod_adaptive_frame_budget": False,
            "traj_prod_frame_budget_tiers": "0.90:1.00,0.75:0.80,0.00:0.50",
            "traj_prod_min_frames_smoke": 72,
            "traj_prod_min_frames_full": 144,
            "traj_prod_early_stop_enabled": True,
            "traj_prod_early_stop_min_frames_smoke": 80,
            "traj_prod_early_stop_min_frames_full": 160,
            "traj_prod_early_stop_window": 10,
            "traj_prod_early_stop_contact_drift": 0.02,
            "traj_prod_early_stop_min_distance_drift_A": 0.14,
            "traj_prod_early_stop_max_mean_min_distance_A": 5.8,
            "traj_prod_profile_intent": "scaleup_100k_pilot",
            "traj_prod_light_artifacts": False,
            "traj_prod_light_progress_every_jobs": 400,
        }
    )
    assert cli[cli.index("--traj-prod-stage2-preset") + 1] == "auto"
    assert "--traj-prod-stage2-preset-strict" in cli
    assert "--traj-prod-speedpack" in cli
    assert "--no-traj-prod-adaptive-frame-budget" in cli
    assert cli[cli.index("--traj-prod-min-frames-full") + 1] == "144"
    assert "--traj-prod-early-stop-enabled" in cli
    assert cli[cli.index("--traj-prod-early-stop-window") + 1] == "10"
    assert cli[cli.index("--traj-prod-profile-intent") + 1] == "scaleup_100k_pilot"
    assert "--no-traj-prod-light-artifacts" in cli
    assert cli[cli.index("--traj-prod-light-progress-every-jobs") + 1] == "400"


def test_profile_traj_prod_args_are_accepted_by_pipeline_parser():
    cli = mod._profile_traj_prod_args(
        {
            "traj_prod_stage2_preset": "auto",
            "traj_prod_stage2_preset_strict": True,
            "traj_prod_speedpack": True,
            "traj_prod_adaptive_frame_budget": True,
            "traj_prod_frame_budget_tiers": "0.90:1.00,0.75:0.80,0.00:0.50",
            "traj_prod_min_frames_smoke": 72,
            "traj_prod_min_frames_full": 144,
            "traj_prod_early_stop_enabled": True,
            "traj_prod_early_stop_min_frames_smoke": 80,
            "traj_prod_early_stop_min_frames_full": 160,
            "traj_prod_early_stop_window": 10,
            "traj_prod_early_stop_contact_drift": 0.02,
            "traj_prod_early_stop_min_distance_drift_A": 0.14,
            "traj_prod_early_stop_max_mean_min_distance_A": 5.8,
            "traj_prod_profile_intent": "scaleup_100k_pilot",
            "traj_prod_light_artifacts": True,
            "traj_prod_light_progress_every_jobs": 333,
        }
    )
    parsed = htvs_pipeline.build_parser().parse_args(
        [
            "--out-prefix",
            "runs/demo_speedpack",
            "--ligand-csv",
            "config/demo_ligands.csv",
            "--targets",
            "ADRB2_GPCR_BLIND",
            "--eval-split-csv",
            "config/demo_split.csv",
            "--ranking-labels-csv",
            "config/demo_labels.csv",
            *cli,
        ]
    )
    assert parsed.traj_prod_stage2_preset == "auto"
    assert parsed.traj_prod_stage2_preset_strict is True
    assert parsed.traj_prod_profile_intent == "scaleup_100k_pilot"
    assert parsed.traj_prod_speedpack is True
    assert parsed.traj_prod_early_stop_enabled is True
    assert parsed.traj_prod_light_artifacts is True
    assert parsed.traj_prod_light_progress_every_jobs == 333


def test_profile_residual_prototype_args_are_accepted_by_pipeline_parser():
    cli = mod._profile_residual_prototype_args(
        {
            "residual_prototype_enabled": True,
            "residual_prototype_mode": "shadow_only",
            "residual_prototype_family": "gpcr",
            "residual_prototype_spec_json": "runs/gpcr_residual_prototype_spec_current.json",
            "residual_prototype_runtime_hook_ready": True,
            "residual_prototype_max_abs_delta_score": 1.5,
            "residual_prototype_yellow_band_abs_delta_score": 0.75,
        }
    )
    parsed = htvs_pipeline.build_parser().parse_args(
        [
            "--out-prefix",
            "runs/demo_residual",
            "--ligand-csv",
            "config/demo_ligands.csv",
            "--targets",
            "ADRB2_GPCR_BLIND",
            "--eval-split-csv",
            "config/demo_split.csv",
            "--ranking-labels-csv",
            "config/demo_labels.csv",
            *cli,
        ]
    )
    assert parsed.stage3_residual_prototype_enabled is True
    assert parsed.stage3_residual_prototype_mode == "shadow_only"
    assert parsed.stage3_residual_prototype_family == "gpcr"
    assert parsed.stage3_residual_prototype_runtime_hook_ready is True
    assert parsed.stage3_residual_prototype_spec_json.endswith("gpcr_residual_prototype_spec_current.json")
    assert parsed.stage3_residual_prototype_max_abs_delta_score == 1.5
    assert parsed.stage3_residual_prototype_yellow_band_abs_delta_score == 0.75


def test_extract_traj_prod_audit_fields_prefers_stage8_operational_summary():
    payload = {
        "traj_prod": {
            "enabled": True,
            "profile_intent": "fallback_intent",
            "requested_preset": "auto",
            "resolved_preset": "default",
            "strict": True,
            "speedpack": True,
            "adaptive_frame_budget": True,
            "early_stop": True,
            "light_artifacts": True,
            "light_progress_every_jobs": 250,
            "warnings": ["fallback warning"],
        },
        "stages": {
            "stage8_sla": {
                "traj_stage2_engine_summary": {
                    "prod_mode": True,
                    "prod_light_artifacts": True,
                    "prod_frame_budget_applied_count": 7,
                    "prod_early_stop_batch_count": 2,
                    "prod_early_stop_row_count": 6,
                    "mean_sim_frames_count": 141.5,
                    "mean_frames_effective_cap": 152.0,
                    "job_batch_derate_count": 3,
                    "target_tail_csv_present": False,
                    "manifest_chunks_dir_present": False,
                    "summary_md_present": False,
                },
                "traj_prod_operational_summary": {
                    "enabled": True,
                    "profile_intent": "scaleup_100k_pilot",
                    "requested_preset": "auto",
                    "resolved_preset": "ion_trpv1",
                    "strict_enabled": True,
                    "strict_status": "warn",
                    "warning_count": 1,
                    "warnings": ["preset drift warning"],
                    "speedpack": True,
                    "adaptive_frame_budget": True,
                    "early_stop": True,
                    "light_artifacts": True,
                    "light_progress_every_jobs": 333,
                    "hinted_families": ["ion_trpv1"],
                    "effective_writer_workers": 3,
                    "effective_writer_max_pending": 256,
                    "effective_frame_budget_tiers": "0.92:1.00,0.78:0.88,0.62:0.74,0.00:0.60",
                    "effective_min_frames": 168,
                    "effective_early_stop_min_frames": 184,
                    "effective_early_stop_window": 14,
                }
            }
        },
    }
    out = mod._extract_traj_prod_audit_fields(payload)
    assert out["traj_prod_profile_intent"] == "scaleup_100k_pilot"
    assert out["traj_prod_resolved_preset"] == "ion_trpv1"
    assert out["traj_prod_strict_status"] == "warn"
    assert out["traj_prod_warning_count"] == 1
    assert out["traj_prod_effective_writer_workers"] == 3.0
    assert out["traj_prod_effective_early_stop_min_frames"] == 184.0
    assert out["traj_stage2_engine_prod_mode"] is True
    assert out["traj_stage2_engine_prod_light_artifacts"] is True
    assert out["traj_stage2_engine_prod_frame_budget_applied_count"] == 7.0
    assert out["traj_stage2_engine_prod_early_stop_row_count"] == 6.0
    assert out["traj_stage2_engine_target_tail_csv_present"] is False


def test_summarize_traj_prod_observability_and_markdown_lines():
    rows = [
        {
            "traj_prod_enabled": True,
            "traj_prod_profile_intent": "scaleup_100k_pilot",
            "traj_prod_requested_preset": "auto",
            "traj_prod_resolved_preset": "ion_trpv1",
            "traj_prod_strict_status": "ok",
            "traj_prod_warning_count": 0,
            "traj_prod_hinted_families": ["ion_trpv1"],
            "traj_prod_effective_writer_workers": 3.0,
            "traj_prod_effective_writer_max_pending": 256.0,
            "traj_prod_effective_frame_budget_tiers": "0.92:1.00,0.78:0.88,0.62:0.74,0.00:0.60",
            "traj_prod_effective_min_frames": 168.0,
            "traj_prod_effective_early_stop_min_frames": 184.0,
            "traj_prod_effective_early_stop_window": 14.0,
            "traj_stage2_engine_prod_mode": True,
            "traj_stage2_engine_prod_light_artifacts": True,
            "traj_stage2_engine_prod_frame_budget_applied_count": 9.0,
            "traj_stage2_engine_prod_early_stop_batch_count": 2.0,
            "traj_stage2_engine_prod_early_stop_row_count": 8.0,
            "traj_stage2_engine_mean_sim_frames_count": 141.5,
            "traj_stage2_engine_mean_frames_effective_cap": 152.0,
            "traj_stage2_engine_job_batch_derate_count": 3.0,
            "traj_stage2_engine_target_tail_csv_present": False,
            "traj_stage2_engine_manifest_chunks_dir_present": False,
            "traj_stage2_engine_summary_md_present": False,
        },
        {
            "traj_prod_enabled": True,
            "traj_prod_profile_intent": "scaleup_100k_pilot",
            "traj_prod_requested_preset": "auto",
            "traj_prod_resolved_preset": "ion_trpv1",
            "traj_prod_strict_status": "warn",
            "traj_prod_warning_count": 1,
            "traj_prod_hinted_families": ["ion_trpv1"],
            "traj_prod_effective_writer_workers": 3.0,
            "traj_prod_effective_writer_max_pending": 256.0,
            "traj_prod_effective_frame_budget_tiers": "0.92:1.00,0.78:0.88,0.62:0.74,0.00:0.60",
            "traj_prod_effective_min_frames": 168.0,
            "traj_prod_effective_early_stop_min_frames": 184.0,
            "traj_prod_effective_early_stop_window": 14.0,
            "traj_stage2_engine_prod_mode": True,
            "traj_stage2_engine_prod_light_artifacts": True,
            "traj_stage2_engine_prod_frame_budget_applied_count": 10.0,
            "traj_stage2_engine_prod_early_stop_batch_count": 3.0,
            "traj_stage2_engine_prod_early_stop_row_count": 9.0,
            "traj_stage2_engine_mean_sim_frames_count": 139.0,
            "traj_stage2_engine_mean_frames_effective_cap": 149.0,
            "traj_stage2_engine_job_batch_derate_count": 4.0,
            "traj_stage2_engine_target_tail_csv_present": False,
            "traj_stage2_engine_manifest_chunks_dir_present": False,
            "traj_stage2_engine_summary_md_present": False,
        },
    ]
    observed = mod._summarize_traj_prod_observability(rows)
    assert observed["completed_runs"] == 2
    assert observed["warning_runs"] == 1
    assert observed["resolved_presets"] == ["ion_trpv1"]
    assert observed["effective_writer_workers"] == [3.0]
    assert observed["engine_prod_mode_runs"] == 2
    assert observed["engine_light_artifact_runs"] == 2
    assert observed["engine_frame_budget_applied_counts"] == [9.0, 10.0]
    assert observed["engine_early_stop_batch_counts"] == [2.0, 3.0]

    lines = mod._traj_prod_markdown_lines(
        {
            "enabled": True,
            "profile_intent": "scaleup_100k_pilot",
            "requested_preset": "auto",
            "strict": True,
            "speedpack": True,
            "adaptive_frame_budget": True,
            "early_stop": True,
            "light_artifacts": True,
            "light_progress_every_jobs": 333,
            "warnings": [],
        },
        observed,
    )
    text = "\n".join(lines)
    assert "## Production Stage2 Audit" in text
    assert "- observed_warning_runs: 1" in text
    assert "- observed_resolved_presets: `['ion_trpv1']`" in text
    assert "- observed_engine_prod_mode_runs: 2" in text
    assert "- observed_engine_frame_budget_applied_counts: `[9.0, 10.0]`" in text
