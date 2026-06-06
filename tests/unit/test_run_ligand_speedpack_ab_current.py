from pathlib import Path
import json

from tools import run_ligand_speedpack_ab_current as mod


def test_build_speedpack_candidate_generates_strict_light_profiles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    trpv1_profile = config_dir / "trpv1.json"
    trpv1_profile.write_text(
        json.dumps(
            {
                "description": "trpv1 baseline",
                "hard_decoy_synth_total_decoys": 10000,
                "full": {"traj_frames": 120},
            }
        ),
        encoding="utf-8",
    )
    gpcr_profile = config_dir / "gpcr.json"
    gpcr_profile.write_text(
        json.dumps(
            {
                "description": "gpcr baseline",
                "hard_decoy_synth_total_decoys": 10000,
            }
        ),
        encoding="utf-8",
    )

    source_spec = config_dir / "source_spec.json"
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl20-full",
                            },
                            {
                                "task_id": "ion_trpv1_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl50-full",
                            },
                            {
                                "task_id": "gpcr_smoke",
                                "kind": "ligand_stress",
                                "domain": "gpcr",
                                "profile_json": str(gpcr_profile),
                                "ligand_sizes": "64",
                                "date_tag_suffix": "gpcr-smoke",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    built = mod._build_speedpack_candidate(
        source_spec_json="config/source_spec.json",
        out_dir=tmp_path / "runs" / "ab",
        selected_task_ids=["ion_trpv1_chembl20_full"],
        include_smoke=False,
        ligand_size_override="",
        strict_auto=True,
        task_bundle="",
    )

    assert Path(built["candidate_spec_json"]).exists()
    assert built["set_ids"] == ["set1_core_blind"]
    assert len(built["task_rows"]) == 1
    assert built["selection"]["requested_bundle"] == ""
    assert built["selection"]["bundle_task_ids"] == []
    assert built["selection"]["runnable_task_ids"] == ["ion_trpv1_chembl20_full"]
    row = built["task_rows"][0]
    assert row["task_id"] == "ion_trpv1_chembl20_full"
    assert row["ligand_sizes_before"] == "10000"
    assert row["ligand_sizes_after"] == "10000"
    assert row["is_smoke"] is False

    assert len(built["profile_rows"]) == 1
    prow = built["profile_rows"][0]
    assert prow["traj_prod_stage2_preset"] == "auto"
    assert prow["traj_prod_stage2_preset_strict"] is True
    assert prow["traj_prod_speedpack"] is True
    assert prow["traj_prod_early_stop_enabled"] is True
    assert prow["traj_prod_light_artifacts"] is True
    assert prow["traj_frame_output_format"] == "manifest_only"
    assert prow["traj_prod_speedpack_frame_cap_full"] == 72
    assert prow["full_traj_frames"] == 72
    assert prow["gate_min_frames"] == 72

    payload = json.loads(Path(prow["generated_profile_json"]).read_text(encoding="utf-8"))
    assert payload["traj_prod_stage2_preset"] == "auto"
    assert payload["traj_prod_stage2_preset_strict"] is True
    assert payload["traj_prod_speedpack"] is True
    assert payload["traj_prod_early_stop_enabled"] is True
    assert payload["traj_prod_light_artifacts"] is True
    assert payload["traj_frame_output_format"] == "manifest_only"
    assert payload["full"]["traj_frames"] == 72
    assert payload["gate"]["min_frames"] == 72
    assert payload["retry"]["max_attempts"] == 2


def test_run_ligand_speedpack_ab_current_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    trpv1_profile = config_dir / "trpv1.json"
    trpv1_profile.write_text(json.dumps({"description": "trpv1 baseline"}), encoding="utf-8")
    source_spec = config_dir / "source_spec.json"
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl20-full",
                            },
                            {
                                "task_id": "ion_trpv1_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl50-full",
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

    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_subprocess)

    rc = mod.main(
        [
            "--tag",
            "2026-03-23_ligand_speedpack_ab_v1",
            "--source-spec-json",
            "config/source_spec.json",
            "--task-bundle",
            "trpv1_full",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--dry-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["comparison_kind"] == "equal_size_speedpack_ab"
    assert payload["requested_task_bundle"] == "trpv1_full"
    assert payload["bundle_task_ids"] == ["ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"]
    assert payload["selected_task_ids"] == ["ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"]
    assert payload["runnable_task_ids"] == ["ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"]
    assert payload["baseline_run_root_found"] is True
    assert payload["selected_scope_summary"]["selected_task_count"] == 2
    assert payload["selected_scope_summary"]["selected_full_task_count"] == 2
    assert payload["selected_scope_summary"]["domains_touched"] == ["ion_channel"]
    assert payload["guardrail_summary"][0]["guardrail_id"] == "no_pass_to_fail"
    assert payload["comparison_enabled"] is True
    assert payload["comparison_skip_reason"] == ""
    assert payload["refresh_current_artifacts"] is False
    assert payload["refresh_result"] == {"enabled": False, "ok": None}
    assert payload["run_cmd"][1].endswith("tools/run_external_validation_blind_sets.py")
    assert payload["compare_cmd"][1].endswith("tools/compare_biorxiv_external_validation_runs.py")
    assert payload["compare_cmd"][-2:] == ["--task-scope", "candidate"]
    assert len(payload["profile_rows"]) == 1
    assert payload["profile_rows"][0]["traj_prod_stage2_preset_strict"] is True


def test_run_ligand_speedpack_ab_current_preflight_rejects_unknown_bundle(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    trpv1_profile = config_dir / "trpv1.json"
    trpv1_profile.write_text(json.dumps({"description": "trpv1 baseline"}), encoding="utf-8")
    source_spec = config_dir / "source_spec.json"
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rc = mod.main(
        [
            "--source-spec-json",
            "config/source_spec.json",
            "--task-bundle",
            "unknown_bundle",
            "--task-ids",
            "",
            "--dry-run",
        ]
    )

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "unknown task bundle: unknown_bundle" in payload["selection_errors"]
    assert "trpv1_full" in payload["available_task_bundles"]


def test_run_ligand_speedpack_ab_current_preflight_warns_when_smoke_bundle_is_dropped(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    trpv1_profile = config_dir / "trpv1.json"
    trpv1_profile.write_text(json.dumps({"description": "trpv1 baseline"}), encoding="utf-8")
    source_spec = config_dir / "source_spec.json"
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set3_operational_smoke",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_smoke",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "64",
                            }
                        ],
                    },
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                            },
                            {
                                "task_id": "ion_trpv1_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
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

    def _unexpected_subprocess(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_subprocess)

    rc = mod.main(
        [
            "--source-spec-json",
            "config/source_spec.json",
            "--task-bundle",
            "trpv1_all",
            "--task-ids",
            "",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--dry-run",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "include_smoke=false" in payload["selection_warnings"][0]
    assert payload["selected_scope_summary"]["selected_full_task_count"] == 2
    assert payload["selected_scope_summary"]["selected_smoke_task_count"] == 0


def test_run_ligand_speedpack_ab_current_real_run_can_refresh_current_artifacts(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    trpv1_profile = config_dir / "trpv1.json"
    trpv1_profile.write_text(json.dumps({"description": "trpv1 baseline"}), encoding="utf-8")
    source_spec = config_dir / "source_spec.json"
    source_spec.write_text(
        json.dumps(
            {
                "sets": [
                    {
                        "set_id": "set1_core_blind",
                        "tasks": [
                            {
                                "task_id": "ion_trpv1_chembl20_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl20-full",
                            },
                            {
                                "task_id": "ion_trpv1_chembl50_full",
                                "kind": "ligand_stress",
                                "domain": "ion_channel",
                                "profile_json": str(trpv1_profile),
                                "ligand_sizes": "10000",
                                "date_tag_suffix": "trpv1-chembl50-full",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    current_meta = runs_dir / "biorxiv_external_validation_package_current.json"
    baseline_root = (tmp_path / "runs" / "baseline_run").resolve()
    current_meta.write_text(
        json.dumps({"run_root": str(baseline_root)}),
        encoding="utf-8",
    )

    runtime_current = tmp_path / "runs" / "ligand_speedpack_ab_runtime_current.json"
    runtime_current.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "baseline_sla_summary_json": str((tmp_path / "runs" / "baseline_sla.json").resolve()),
                        "candidate_sla_summary_json": str((tmp_path / "runs" / "candidate_sla.json").resolve()),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    calls = []

    class _Result:
        def __init__(self, code: int = 0):
            self.returncode = code

    def _fake_run(cmd, cwd=None):
        calls.append((cmd, cwd))
        return _Result(0)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    rc = mod.main(
        [
            "--tag",
            "2026-03-23_ligand_speedpack_ab_v1",
            "--source-spec-json",
            "config/source_spec.json",
            "--task-bundle",
            "trpv1_full",
            "--current-package-meta-json",
            "runs/biorxiv_external_validation_package_current.json",
            "--refresh-current-artifacts",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["refresh_current_artifacts"] is True
    assert payload["refresh_result"]["enabled"] is True
    assert payload["refresh_result"]["ok"] is True
    assert payload["refresh_result"]["single_task_sla_refresh"] is True
    assert payload["refresh_result"]["runtime_cmd"][1].endswith("tools/product/extract_ligand_scaleup_results.py")
    assert payload["refresh_result"]["summary_cmd"][1].endswith("tools/build_ligand_speedpack_ab_summary.py")
    assert len(calls) == 4
    assert calls[0][0][1].endswith("tools/run_external_validation_blind_sets.py")
    assert calls[1][0][1].endswith("tools/compare_biorxiv_external_validation_runs.py")
    assert calls[1][0][-2:] == ["--task-scope", "candidate"]
    assert calls[2][0][1].endswith("tools/product/extract_ligand_scaleup_results.py")
    assert calls[3][0][1].endswith("tools/build_ligand_speedpack_ab_summary.py")
