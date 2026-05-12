from pathlib import Path
import json
from types import SimpleNamespace

from tools import build_ligand_scaleup_1m_pilot as build_mod
from tools import ligand_scaleup_pilot_helper as helper_mod
from tools import run_ligand_scaleup_1m_pilot_current as run_mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_ligand_scaleup_1m_pilot(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    gpcr_profile = config_dir / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3.json"
    gpcr_profile.write_text(
        json.dumps(
            {
                "description": "gpcr baseline",
                "hard_decoy_synth_total_decoys": 10_000,
            }
        ),
        encoding="utf-8",
    )
    kinase_profile = config_dir / "kinase.json"
    kinase_profile.write_text(
        json.dumps(
            {
                "description": "kinase baseline",
                "hard_decoy_synth_total_decoys": 150_000,
            }
        ),
        encoding="utf-8",
    )
    base_spec = config_dir / "base_spec.json"
    base_spec.write_text(
        json.dumps(
            {
                "protocol_id": "base",
                "protocol_title": "Base",
                "protocol_version": "v1",
                "global_governance": {"claim_scope": []},
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "profile_json": str(gpcr_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "gpcr-core-full",
                            },
                            {
                                "task_id": "idp_release_current",
                                "domain": "idp",
                                "kind": "idp_reference_current_full",
                            }
                        ],
                    },
                    {
                        "set_id": "set3_operational_smoke",
                        "tasks": [
                            {
                                "task_id": "kinase_smoke",
                                "kind": "ligand_stress",
                                "profile_json": str(kinase_profile),
                                "ligand_sizes": "64",
                                "date_tag_suffix": "kinase-smoke",
                            },
                            {
                                "task_id": "idp_smoke_current",
                                "domain": "idp",
                                "kind": "idp_smoke_current",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = build_mod.build_pilot_payload(
        base_spec_path=base_spec,
        out_config_dir=config_dir,
        preset=build_mod.PRESET,
        runner_script_name="tools/run_ligand_scaleup_1m_pilot_current.py",
        root=tmp_path,
    )

    pilot_spec_path = config_dir / "external_validation_biorxiv_scaleup_1m_pilot_v1.json"
    assert pilot_spec_path.exists()
    pilot_spec = json.loads(pilot_spec_path.read_text(encoding="utf-8"))
    gpcr_task = pilot_spec["sets"][0]["tasks"][0]
    assert [task["kind"] for row in pilot_spec["sets"] for task in row["tasks"]] == [
        "ligand_stress",
        "ligand_stress",
    ]
    assert pilot_spec["sets"][0]["non_ligand_task_count_omitted"] == 1
    assert pilot_spec["sets"][1]["non_ligand_task_count_omitted"] == 1
    assert gpcr_task["ligand_sizes"] == "1000000"
    assert gpcr_task["date_tag_suffix"].endswith("-prod1m")
    gpcr_pilot_profile_path = Path(gpcr_task["profile_json"])
    if not gpcr_pilot_profile_path.is_absolute():
        gpcr_pilot_profile_path = tmp_path / gpcr_pilot_profile_path
    gpcr_pilot_profile = json.loads(gpcr_pilot_profile_path.read_text(encoding="utf-8"))
    assert gpcr_pilot_profile["traj_frame_output_format"] == "manifest_only"
    assert gpcr_pilot_profile["hard_decoy_synth_generation_mode"] == "enumerate"
    assert gpcr_pilot_profile["hard_decoy_synth_global_unique"] is False
    assert gpcr_pilot_profile["hard_decoy_synth_relax_3d"] is False
    assert gpcr_pilot_profile["csv_relax_3d"] is False
    assert gpcr_pilot_profile["csv_relax_workers"] == 0
    assert gpcr_pilot_profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert gpcr_pilot_profile["ranking_probability_score_col"] == "binding_score_composite_v7_residual_active"
    assert gpcr_pilot_profile["residual_prototype_enabled"] is True
    assert gpcr_pilot_profile["residual_prototype_mode"] == "apply"
    assert gpcr_pilot_profile["residual_prototype_candidate"] == "gpcr_core_family_balanced_beta_blocker_rescue_v3"
    assert (
        gpcr_pilot_profile["residual_prototype_spec_json"]
        == "config/gpcr_residual_prototype_spec_core_family_balanced_beta_blocker_rescue_v3.json"
    )
    assert gpcr_pilot_profile["target_specific_candidate"] is True
    assert gpcr_pilot_profile["broad_gpcr_claim_allowed"] is False
    assert gpcr_pilot_profile["threshold_relaxation_allowed"] is False
    kinase_smoke = pilot_spec["sets"][1]["tasks"][0]
    assert kinase_smoke["ligand_sizes"] == "64"
    assert kinase_smoke["profile_json"] != str(kinase_profile)
    kinase_smoke_profile_path = Path(kinase_smoke["profile_json"])
    if not kinase_smoke_profile_path.is_absolute():
        kinase_smoke_profile_path = tmp_path / kinase_smoke_profile_path
    kinase_smoke_profile = json.loads(kinase_smoke_profile_path.read_text(encoding="utf-8"))
    assert kinase_smoke_profile["hard_decoy_synth_generation_mode"] == "enumerate"
    assert kinase_smoke_profile["hard_decoy_synth_global_unique"] is False
    assert kinase_smoke_profile["hard_decoy_synth_relax_3d"] is False
    assert kinase_smoke_profile["csv_relax_3d"] is False

    assert payload["target_scale_label"] == "1M"
    assert payload["target_scale_slug"] == "1m"
    assert payload["profile_count"] == 2
    assert payload["non_ligand_task_count_removed"] == 2
    assert payload["comparison_label_default"].endswith("_vs_current")
    gpcr_row = next(row for row in payload["profile_rows"] if row["source_profile_json"] == str(gpcr_profile))
    assert gpcr_row["applies_to"] == "full"
    assert gpcr_row["traj_prod_profile_intent"] == "scaleup_1m_pilot"
    assert gpcr_row["traj_prod_stage2_preset"] == "auto"
    assert gpcr_row["traj_prod_stage2_preset_strict"] is True
    assert gpcr_row["traj_prod_speedpack"] is True
    assert gpcr_row["traj_prod_early_stop_enabled"] is True
    assert gpcr_row["traj_prod_light_artifacts"] is True
    assert gpcr_row["traj_frame_output_format"] == "manifest_only"
    assert gpcr_row["hard_decoy_synth_total_decoys"] == 1_000_000
    assert gpcr_row["hard_decoy_synth_generation_mode"] == "enumerate"
    assert gpcr_row["hard_decoy_synth_global_unique"] is False
    assert gpcr_row["hard_decoy_synth_relax_3d"] is False
    assert gpcr_row["csv_relax_3d"] is False
    assert gpcr_row["csv_relax_workers"] == 0
    assert gpcr_row["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert gpcr_row["ranking_probability_score_col"] == "binding_score_composite_v7_residual_active"
    assert gpcr_row["residual_prototype_enabled"] is True
    assert gpcr_row["residual_prototype_candidate"] == "gpcr_core_family_balanced_beta_blocker_rescue_v3"
    smoke_profile_row = next(row for row in payload["profile_rows"] if row["source_profile_json"] == str(kinase_profile))
    assert smoke_profile_row["applies_to"] == "smoke"
    assert smoke_profile_row["hard_decoy_synth_generation_mode"] == "enumerate"
    assert smoke_profile_row["hard_decoy_synth_global_unique"] is False
    assert smoke_profile_row["hard_decoy_synth_relax_3d"] is False
    assert smoke_profile_row["csv_relax_3d"] is False

    set1_row = next(row for row in payload["set_rows"] if row["set_id"] == "set1_core_blind")
    assert set1_row["full_task_count_target"] == 1
    assert set1_row["full_task_count_1m"] == 1
    task_row = next(row for row in payload["task_rows"] if row["task_id"] == "gpcr_core_full")
    assert task_row["ligand_sizes_before"] == "10000"
    assert task_row["ligand_sizes_after"] == "1000000"
    assert task_row["profile_changed"] is True
    assert task_row["pilot_shape_class"] == "full_1m"
    smoke_row = next(row for row in payload["task_rows"] if row["task_id"] == "kinase_smoke")
    assert smoke_row["ligand_sizes_before"] == "64"
    assert smoke_row["ligand_sizes_after"] == "64"
    assert smoke_row["profile_changed"] is True
    assert smoke_row["pilot_shape_class"] == "smoke_baseline"
    assert payload["full_task_ids_target"] == ["gpcr_core_full"]
    assert payload["full_task_ids_1m"] == ["gpcr_core_full"]
    assert payload["smoke_task_ids_baseline"] == ["kinase_smoke"]
    assert payload["baseline_ligand_sizes"]["set1_core_blind::gpcr_core_full"] == "10000"
    assert payload["pilot_ligand_sizes"]["set1_core_blind::gpcr_core_full"] == "1000000"
    assert payload["comparison_kind"] == "size_shift_operational_regression"
    assert payload["smoke_uses_baseline_decoys"] is True
    assert payload["scope_summary"]["full_set_ids"] == ["set1_core_blind"]
    assert payload["scope_summary"]["smoke_set_ids"] == ["set3_operational_smoke"]
    assert payload["scope_summary"]["full_task_count_target"] == 1
    assert payload["scope_summary"]["full_task_count_1m"] == 1
    assert payload["drift_audit"]["ok"] is True
    assert payload["drift_audit"]["nonstandard_ligand_size_count"] == 0
    assert payload["drift_audit"]["full_task_non_target_count"] == 0
    assert payload["drift_audit"]["profile_missing_manifest_only_frame_output_count"] == 0
    assert payload["drift_audit"]["profile_csv_relax_3d_enabled_count"] == 0
    assert payload["drift_audit"]["profile_missing_intent_count"] == 0
    assert payload["launch_readiness"]["ready"] is True
    assert payload["launch_readiness"]["status"] == "ready"
    assert payload["launch_readiness"]["blocking_issue_count"] == 0
    assert len(payload["guardrail_rows"]) == 4
    assert payload["guardrail_rows"][0]["guardrail_id"] == "no_pass_to_fail"
    _contains_tokens(payload["preflight_notes"][0], "full", "ligand_stress", "1000000")
    assert any("prod1m" in note for note in payload["preflight_notes"])
    assert "--dry-run" in payload["runner_dry_run_command"]


def test_run_ligand_scaleup_1m_pilot_current_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    pilot_spec = config_dir / "pilot_spec.json"
    pilot_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set3_operational_smoke",
                        "tasks": [
                            {
                                "task_id": "gpcr_smoke",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "64",
                                "date_tag_suffix": "gpcr-smoke",
                            }
                        ],
                    },
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "1000000",
                                "date_tag_suffix": "gpcr-core-full-prod1m",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    current_meta = runs_dir / "biorxiv_external_validation_package_current.json"
    current_meta.write_text(
        json.dumps({"run_root": str((tmp_path / "runs" / "baseline_run").resolve())}),
        encoding="utf-8",
    )

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(run_mod.subprocess, "run", _unexpected_subprocess)

    rc = run_mod.main(
        [
            "--tag",
            "2026-03-23_scaleup_1m_pilot_v1",
            "--sets",
            "set3_operational_smoke,set1_core_blind",
            "--set-spec-json",
            "config/pilot_spec.json",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--dry-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["baseline_run_root_found"] is True
    assert payload["target_scale_label"] == "1M"
    assert payload["selected_ligand_stress_task_count"] == 2
    assert payload["selected_full_task_count_target"] == 1
    assert payload["selected_full_task_count_1m"] == 1
    assert payload["selected_smoke_task_count"] == 1
    assert payload["selected_scope_summary"]["full_set_ids"] == ["set1_core_blind"]
    assert payload["selected_scope_summary"]["smoke_set_ids"] == ["set3_operational_smoke"]
    assert payload["selected_scope_summary"]["domains_touched"] == ["gpcr"]
    assert payload["selected_drift_audit"]["ok"] is True
    assert payload["selected_drift_audit"]["nonstandard_ligand_size_count"] == 0
    assert payload["selected_drift_audit"]["full_task_non_target_count"] == 0
    assert payload["selected_drift_audit"]["profile_missing_manifest_only_frame_output_count"] == 0
    assert payload["guardrail_summary"][0]["guardrail_id"] == "no_pass_to_fail"
    assert payload["compare_label"] == "2026-03-23_scaleup_1m_pilot_v1_vs_current"
    assert payload["comparison_kind"] == "size_shift_operational_regression"
    assert payload["run_cmd"][1].endswith("tools/run_external_validation_blind_sets.py")
    assert payload["compare_cmd"][1].endswith("tools/compare_biorxiv_external_validation_runs.py")
    assert payload["comparison_enabled"] is True
    assert payload["comparison_skip_reason"] == ""
    assert payload["launch_readiness"]["ready"] is True
    assert payload["launch_readiness"]["blocking_issue_count"] == 0
    assert payload["post_run_refresh"]["enabled"] is True
    assert payload["post_run_refresh"]["attempted"] is False
    assert len(payload["post_run_refresh"]["plan"]["steps"]) == 3


def test_run_ligand_scaleup_1m_pilot_current_dry_run_without_baseline(tmp_path: Path, monkeypatch, capsys) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    pilot_spec = config_dir / "pilot_spec.json"
    pilot_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "1000000",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    monkeypatch.setattr(run_mod.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no subprocess in dry-run")))

    rc = run_mod.main(
        [
            "--set-spec-json",
            "config/pilot_spec.json",
            "--current-package-meta-json",
            "runs/missing_current_package.json",
            "--dry-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["baseline_run_root_found"] is False
    assert payload["compare_cmd"] == []
    assert payload["comparison_skipped"] is True
    assert payload["selected_drift_audit"]["ok"] is True
    assert payload["comparison_enabled"] is False
    assert payload["comparison_skip_reason"] == "baseline_run_root_not_found"
    assert payload["launch_readiness"]["ready"] is False
    _contains_tokens(payload["launch_readiness"]["blocking_issues"][0], "baseline", "run", "root", "resolved")
    assert payload["post_run_refresh"]["enabled"] is True
    assert len(payload["post_run_refresh"]["plan"]["steps"]) == 3


def test_run_ligand_scaleup_1m_pilot_current_dry_run_skip_compare(tmp_path: Path, monkeypatch, capsys) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    pilot_spec = config_dir / "pilot_spec.json"
    pilot_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "1000000",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    current_meta = runs_dir / "biorxiv_external_validation_package_current.json"
    current_meta.write_text(
        json.dumps({"run_root": str((tmp_path / "runs" / "baseline_run").resolve())}),
        encoding="utf-8",
    )

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    monkeypatch.setattr(run_mod.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no subprocess in dry-run")))

    rc = run_mod.main(
        [
            "--set-spec-json",
            "config/pilot_spec.json",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--skip-compare",
            "--dry-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["comparison_enabled"] is False
    assert payload["comparison_skipped"] is True
    assert payload["comparison_skip_reason"] == "skip_compare"
    assert payload["compare_cmd"] == []
    assert payload["launch_readiness"]["ready"] is False
    _contains_tokens(payload["launch_readiness"]["blocking_issues"][0], "comparison", "explicitly", "disabled")
    assert payload["post_run_refresh"]["enabled"] is True
    assert len(payload["post_run_refresh"]["plan"]["steps"]) == 3


def test_helper_outputs_surface_launch_readiness_and_blockers(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    gpcr_profile = config_dir / "gpcr.json"
    gpcr_profile.write_text(
        json.dumps(
            {
                "description": "gpcr baseline",
                "hard_decoy_synth_total_decoys": 10_000,
            }
        ),
        encoding="utf-8",
    )
    base_spec = config_dir / "base_spec.json"
    base_spec.write_text(
        json.dumps(
            {
                "protocol_id": "base",
                "protocol_title": "Base",
                "protocol_version": "v1",
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "profile_json": str(gpcr_profile),
                                "ligand_sizes": "10000",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = build_mod.build_pilot_payload(
        base_spec_path=base_spec,
        out_config_dir=config_dir,
        preset=build_mod.PRESET,
        runner_script_name="tools/run_ligand_scaleup_1m_pilot_current.py",
        root=tmp_path,
    )

    out_json = tmp_path / "pilot.json"
    out_csv = tmp_path / "pilot.csv"
    out_task_csv = tmp_path / "pilot_tasks.csv"
    out_md = tmp_path / "pilot.md"
    helper_mod.write_builder_outputs(
        payload=payload,
        out_json=out_json,
        out_csv=out_csv,
        out_task_csv=out_task_csv,
        out_md=out_md,
        preset=build_mod.PRESET,
    )
    md_text = out_md.read_text(encoding="utf-8")
    assert "## Launch Readiness" in md_text
    assert "- ready: `True`" in md_text
    assert "- status: `ready`" in md_text
    assert "manifest_only" in md_text

    run_payload = helper_mod.build_run_current_payload(
        tag="2026-03-23_scaleup_1m_pilot_v1",
        selected_sets=["set1_core_blind"],
        set_spec_json=str(payload["pilot_spec_json"]),
        baseline_run_root="",
        out_root="runs/external_validation_blind_runs",
        comparison_out_root="runs",
        compare_label="compare_v_current",
        skip_compare=False,
        preset=build_mod.PRESET,
        root=tmp_path,
    )
    assert run_payload["launch_readiness"]["ready"] is False
    assert any(
        all(token in issue.lower() for token in ("baseline", "run", "root", "resolved"))
        for issue in run_payload["launch_readiness"]["blocking_issues"]
    )


def test_run_ligand_scaleup_1m_pilot_current_refreshes_current_summaries_when_compare_skipped(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    pilot_spec = config_dir / "pilot_spec.json"
    pilot_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "1000000",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (runs_dir / "biorxiv_external_validation_package_current.json").write_text(
        json.dumps({"run_root": str((tmp_path / "runs" / "baseline_run").resolve())}),
        encoding="utf-8",
    )

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_mod.subprocess, "run", _fake_run)

    rc = run_mod.main(
        [
            "--tag",
            "2026-03-23_scaleup_1m_pilot_v1",
            "--set-spec-json",
            "config/pilot_spec.json",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--skip-compare",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["comparison_skipped"] is True
    assert payload["reason"] == "skip_compare"
    assert payload["post_run_refresh"]["enabled"] is True
    assert payload["post_run_refresh"]["attempted"] is True
    assert payload["post_run_refresh"]["ok"] is True
    assert payload["post_run_refresh"]["step_count"] == 3
    assert [row["step_id"] for row in payload["post_run_refresh"]["steps"]] == [
        "refresh_scaleup_kpi_table",
        "refresh_scaleup_1m_pilot_artifacts",
        "refresh_scaleup_benchmark_summary",
    ]
    assert [Path(cmd[1]).name for cmd in calls] == [
        "run_external_validation_blind_sets.py",
        "build_ligand_scaleup_kpi_table.py",
        "build_ligand_scaleup_1m_pilot.py",
        "build_ligand_scaleup_benchmark_summary.py",
    ]


def test_run_current_payload_blocks_existing_non_manifest_only_full_profiles(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    stale_profile = config_dir / "gpcr_prod1m.json"
    stale_profile.write_text(
        json.dumps({"traj_frame_output_format": "npz_bundle"}),
        encoding="utf-8",
    )
    pilot_spec = config_dir / "pilot_spec.json"
    pilot_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "kind": "ligand_stress",
                                "profile_json": "config/gpcr_prod1m.json",
                                "ligand_sizes": "1000000",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = helper_mod.build_run_current_payload(
        tag="2026-03-23_scaleup_1m_pilot_v1",
        selected_sets=["set1_core_blind"],
        set_spec_json="config/pilot_spec.json",
        baseline_run_root=str(tmp_path / "runs" / "baseline_run"),
        out_root="runs/external_validation_blind_runs",
        comparison_out_root="runs",
        compare_label="compare_v_current",
        skip_compare=False,
        preset=build_mod.PRESET,
        root=tmp_path,
    )

    assert payload["selected_drift_audit"]["ok"] is False
    assert payload["selected_drift_audit"]["selected_full_profile_manifest_only_inspected_count"] == 1
    assert payload["selected_drift_audit"]["profile_missing_manifest_only_frame_output_count"] == 1
    assert payload["launch_readiness"]["ready"] is False
    assert any("manifest-only" in issue for issue in payload["launch_readiness"]["blocking_issues"])
