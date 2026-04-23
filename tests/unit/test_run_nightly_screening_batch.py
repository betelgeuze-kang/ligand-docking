import json
from pathlib import Path

from tools import run_nightly_screening_batch as nightly


def test_nightly_batch_dry_run_writes_summary(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)

    assert summary["pass"] is True
    assert summary["dry_run"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 10
    assert summary["long_stability_gate_policy"] == "strict"
    assert summary["long_stability_status"] == {}
    assert summary["claim_status"] == {}
    assert summary["dashboard_status"] == {}
    for rec in summary["results"]:
        assert rec["ok"] is True
        assert rec["returncode"] == 0
        assert rec["dry_run"] is True
    assert "--stability-profile-json" in summary["results"][0]["cmd_str"]
    assert "--enforce-long-stability-gate" in summary["results"][0]["cmd_str"]
    assert any("visualize_experiment_dashboard.py" in str(rec.get("cmd_str", "")) for rec in summary["results"])

    summary_json = Path(summary["paths"]["batch_summary_json"])
    summary_md = Path(summary["paths"]["batch_summary_md"])
    assert summary_json.exists()
    assert summary_md.exists()
    saved = json.loads(summary_json.read_text(encoding="utf-8"))
    assert saved["pass"] is True
    assert "failure_latest_report" in saved


def test_nightly_batch_dry_run_without_claim_correction_has_legacy_step_count(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--no-run-claim-correction",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 9


def test_nightly_batch_dry_run_without_dashboard_removes_step(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--no-run-experiment-dashboard",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 9
    cmd_strs = [str(rec.get("cmd_str", "")) for rec in summary["results"]]
    assert not any("visualize_experiment_dashboard.py" in s for s in cmd_strs)


def test_nightly_batch_dry_run_rebench_runtime_flags_forwarded(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--no-rebench-use-ai-router",
            "--rebench-ai-runtime-mode",
            "onnx",
            "--no-rebench-ai-disable-exploration",
            "--rebench-ai-use-hip-graph",
            "--rebench-ai-graph-warmup-iters",
            "7",
            "--rebench-ai-router-checkpoint",
            "models/router_test.pth",
            "--rebench-ai-router-checkpoint-strict",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    rebench_cmd = next(str(rec.get("cmd_str", "")) for rec in summary["results"] if rec.get("name") == "rebench")
    assert "--no-use-ai-router" in rebench_cmd
    assert "--ai-runtime-mode onnx" in rebench_cmd
    assert "--speed-profile-preserve-runtime-mode" in rebench_cmd
    assert "--no-ai-disable-exploration" in rebench_cmd
    assert "--ai-use-hip-graph" in rebench_cmd
    assert "--ai-graph-warmup-iters 7" in rebench_cmd
    assert "--ai-router-checkpoint models/router_test.pth" in rebench_cmd
    assert "--ai-router-checkpoint-strict" in rebench_cmd


def test_nightly_batch_dry_run_auto_runtime_selection_status(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--auto-select-rebench-ai-runtime-mode",
            "--rebench-ai-runtime-mode",
            "onnx",
        ]
    )
    summary = nightly.run_batch(args)
    status = summary.get("rebench_ai_runtime_mode_status", {})
    assert status.get("enabled") is True
    assert status.get("selected_mode") == "onnx"
    assert status.get("selection_source") == "dry_run_fallback"


def test_nightly_batch_dry_run_can_disable_runtime_mode_preserve_flag(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--no-rebench-speed-profile-preserve-runtime-mode",
        ]
    )
    summary = nightly.run_batch(args)
    rebench_cmd = next(str(rec.get("cmd_str", "")) for rec in summary["results"] if rec.get("name") == "rebench")
    assert "--no-speed-profile-preserve-runtime-mode" in rebench_cmd


def test_nightly_batch_dry_run_dashboard_auto_compare_csv(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)
    prev_csv = out_runs / "feature_matrix_per_target_nightly_2026-02-18-prev.csv"
    prev_csv.write_text("target,step,energy\nChignolin,0,-10.0\n", encoding="utf-8")

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    dash_cmd = next(
        str(rec.get("cmd_str", ""))
        for rec in summary["results"]
        if str(rec.get("name", "")) == "build_experiment_dashboard"
    )
    assert "--compare-csv" in dash_cmd
    assert str(prev_csv) in dash_cmd


def test_nightly_batch_dry_run_with_special_cases_adds_step(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
            "--run-special-cases",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 11
    cmd_strs = [str(rec.get("cmd_str", "")) for rec in summary["results"]]
    assert any("run_special_case_pipeline.py" in s for s in cmd_strs)


def test_nightly_batch_links_attempts_csv_artifacts(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)
    (out_runs / "accuracy_revalidation_2026-02-16_r1_attempts.csv").write_text(
        "stage,attempt\nsmoke,1\n",
        encoding="utf-8",
    )
    (out_runs / "post_gate_pipeline_2026-02-16_r1_gate_attempts.csv").write_text(
        "attempt_index,pass\n1,1\n",
        encoding="utf-8",
    )

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    links = summary.get("attempts_csv_links", {})
    assert links.get("accuracy_revalidation_attempts_csv", "").endswith("_attempts.csv")
    assert links.get("post_gate_pipeline_attempts_csv", "").endswith("_gate_attempts.csv")


def test_collect_special_case_status_preserves_zero_exit_code(tmp_path):
    special_summary = tmp_path / "special_case_summary.json"
    special_summary.write_text(
        json.dumps(
            {
                "pass": True,
                "exit_code": 0,
                "failed_stage": None,
                "stages": {
                    "stage_metal": {"pass": True},
                    "stage_dna": {"pass": True},
                    "stage_membrane": {"pass": True},
                },
            }
        ),
        encoding="utf-8",
    )
    status = nightly._collect_special_case_status({"special_case_summary_json": str(special_summary)})
    assert status["pass"] is True
    assert status["exit_code"] == 0
    assert status["stage_pass"]["stage_metal"] is True


def test_nightly_batch_claim_initial_requirement_blocks_pass(monkeypatch, tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    def _fake_run_cmd(cmd, env=None, dry_run=False):
        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "dry_run": bool(dry_run),
            "returncode": 0,
            "ok": True,
        }

    monkeypatch.setattr(nightly, "_run_cmd", _fake_run_cmd)
    monkeypatch.setattr(
        nightly,
        "_collect_claim_status",
        lambda _paths: {"initial_claim_ready_for_allatom": False, "initial_claim_failed_metrics": 1},
    )

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
        ]
    )
    summary = nightly.run_batch(args)

    assert summary["claim_require_initial_ready"] is True
    assert summary["initial_claim_requirement_failed"] is True
    assert summary["pass"] is False
    assert summary["failed_step_index"] is not None


def test_nightly_batch_measured_proxy_requirement_blocks_pass(monkeypatch, tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    def _fake_run_cmd(cmd, env=None, dry_run=False):
        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "dry_run": bool(dry_run),
            "returncode": 0,
            "ok": True,
        }

    def _fake_collect_ood_status(paths):
        src = str(paths.get("ood_summary_json", ""))
        if "ood_measured20_validation_batch" in src:
            return {"pass": True, "proxy_rows_added": 2}
        return {"pass": True, "proxy_rows_added": 0}

    monkeypatch.setattr(nightly, "_run_cmd", _fake_run_cmd)
    monkeypatch.setattr(nightly, "_collect_ood_status", _fake_collect_ood_status)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--run-ood-measured20",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["measured_proxy_requirement_failed"] is True
    assert summary["pass"] is False
    assert summary["failed_step_index"] is not None


def test_nightly_batch_dashboard_metrics_requirement_blocks_pass(monkeypatch, tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    def _fake_run_cmd(cmd, env=None, dry_run=False):
        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "dry_run": bool(dry_run),
            "returncode": 0,
            "ok": True,
        }

    monkeypatch.setattr(nightly, "_run_cmd", _fake_run_cmd)
    monkeypatch.setattr(nightly, "_collect_dashboard_status", lambda _paths: {"metrics_count": 0, "run_count": 1})

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["dashboard_metrics_requirement_failed"] is True
    assert summary["pass"] is False
    assert summary["failed_step_index"] is not None


def test_nightly_batch_dry_run_with_measured20_adds_step(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--run-ood-measured20",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 11
    cmd_strs = [str(rec.get("cmd_str", "")) for rec in summary["results"]]
    measured_cmds = [s for s in cmd_strs if "ood_measured20_validation_batch_nightly_2026-02-16" in s]
    assert len(measured_cmds) == 1
    assert "--targets sources_all" in measured_cmds[0]
    assert "--require-real-afdb" in measured_cmds[0]
    assert "--max-proxy-rows 0" in measured_cmds[0]
    assert "--no-enable-proxy-manifest" in measured_cmds[0]


def test_nightly_batch_claim_profile_json_applies_overrides(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)
    claim_profile = tmp_path / "claim_profile.json"
    claim_profile.write_text(
        json.dumps(
            {
                "profile": {
                    "claim_kinetics_agg_method": "mean",
                    "claim_pmf_pseudocount": 2.0,
                    "claim_split_replicas": 7,
                }
            }
        ),
        encoding="utf-8",
    )

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--claim-profile-json",
            str(claim_profile),
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["claim_profile"]["loaded"] is True
    assert "claim_kinetics_agg_method" in summary["claim_profile"]["keys_applied"]
    build_cmd = next(rec["cmd_str"] for rec in summary["results"] if rec["name"] == "build_claim_inputs")
    assert "--kinetics-agg-method mean" in build_cmd
    assert "--pmf-pseudocount 2.0" in build_cmd
    assert "--split-replicas 7" in build_cmd


def test_nightly_batch_dry_run_with_measured40_adds_step(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--run-ood-measured40",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    assert summary["executed_steps"] == summary["total_steps"] == 11
    cmd_strs = [str(rec.get("cmd_str", "")) for rec in summary["results"]]
    measured_cmds = [s for s in cmd_strs if "ood_measured40_validation_batch_nightly_2026-02-16" in s]
    assert len(measured_cmds) == 1
    assert "--targets sources_all" in measured_cmds[0]
    assert "--require-real-afdb" in measured_cmds[0]
    assert "--max-proxy-rows 0" in measured_cmds[0]
    assert "--no-enable-proxy-manifest" in measured_cmds[0]


def test_nightly_batch_dry_run_active_learning_auto_hardcase_step(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--run-active-learning",
            "--dry-run",
            "--active-learning-curriculum-hardcase-manifest-csv",
            "",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is True
    by_name = {str(rec.get("name", "")): str(rec.get("cmd_str", "")) for rec in summary["results"]}
    assert "build_live_unseen_hardcase_manifest" in by_name
    assert "run_active_learning_cycle" in by_name
    active_cmd = by_name["run_active_learning_cycle"]
    assert "--curriculum-hardcase-manifest-csv" in active_cmd
    assert "active_learning_live_unseen_hardcase_manifest_nightly_2026-02-16.csv" in active_cmd


def test_nightly_batch_dry_run_post_publish_defaults_present(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["external_packet_status"]["requested"] is True
    assert summary["external_packet_status"]["dry_run"] is True
    assert summary["commercial_readiness_report_status"]["requested"] is True
    assert summary["commercial_readiness_report_status"]["dry_run"] is True
    assert summary["external_submission_status"]["requested"] is True
    assert summary["external_submission_status"]["dry_run"] is True
    assert summary["post_process_failures"] == []


def test_nightly_batch_commercial_readiness_enforce_fail_blocks_pass(monkeypatch, tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    def _fake_run_cmd(cmd, env=None, dry_run=False):
        rec = {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "dry_run": bool(dry_run),
            "returncode": 0,
            "ok": True,
        }
        cmd_str = rec["cmd_str"]
        if "build_commercial_readiness_report.py" in cmd_str:
            out_json = ""
            for i, tok in enumerate(cmd):
                if tok == "--out-json" and (i + 1) < len(cmd):
                    out_json = str(cmd[i + 1])
                    break
            if out_json:
                p = Path(out_json)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    json.dumps(
                        {
                            "summary": {
                                "readiness_score": 50.0,
                                "readiness_tier": "research_only",
                                "considered_checks": 5,
                                "passed_checks": 2,
                                "failed_checks": 3,
                                "critical_checks_pass": False,
                            }
                        }
                    ),
                    encoding="utf-8",
                )
        return rec

    monkeypatch.setattr(nightly, "_run_cmd", _fake_run_cmd)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--no-run-experiment-dashboard",
            "--no-run-external-packet",
            "--no-publish-external-submission",
            "--commercial-readiness-enforce-pass",
            "--commercial-readiness-min-score",
            "80",
            "--no-preflight-validate-inputs",
        ]
    )
    summary = nightly.run_batch(args)
    assert summary["pass"] is False
    assert summary["commercial_readiness_report_status"]["requested"] is True
    assert summary["commercial_readiness_report_status"]["ok"] is False
    assert summary["commercial_readiness_report_status"]["gate_failure"] == "commercial_readiness_enforce_pass_failed"
    names = [str(x.get("name", "")) for x in summary.get("post_process_failures", [])]
    assert "commercial_readiness_report" in names


def test_resolve_external_packet_accuracy_external_csv_prefers_full_target_coverage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    smoke_dir = tmp_path / "runs" / "smoke"
    full_dir = tmp_path / "runs" / "full"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)

    smoke_csv = smoke_dir / "candidate_smoke_accuracy_external.csv"
    smoke_csv.write_text(
        "target,reference_source,avg_rmsd\n"
        "A,openmm,1.0\n"
        "B,openmm,1.1\n"
        "C,openmm,1.2\n",
        encoding="utf-8",
    )

    full_csv = full_dir / "candidate_full_accuracy_external.csv"
    full_rows = ["target,reference_source,avg_rmsd"]
    for i in range(10):
        full_rows.append(f"T{i},openmm,1.{i}")
    full_csv.write_text("\n".join(full_rows) + "\n", encoding="utf-8")

    args = nightly.build_parser().parse_args([])
    args.external_packet_accuracy_external_csv = ""
    args.accuracy_external_csv = ""

    chosen, candidates = nightly._resolve_external_packet_accuracy_external_csv(
        args=args,
        paths={},
        strict_summary_json_path="",
    )
    assert Path(chosen).resolve() == full_csv.resolve()
    assert len(candidates) >= 2


def test_run_external_packet_uses_resolved_accuracy_external_csv(tmp_path, monkeypatch):
    acc_csv = tmp_path / "resolved_accuracy_external.csv"
    acc_csv.write_text(
        "target,reference_source,avg_rmsd\nChignolin,openmm,1.0\n",
        encoding="utf-8",
    )

    captured = {}

    def _fake_run_cmd(cmd, env=None, dry_run=False):
        captured["cmd"] = list(cmd)
        captured["cmd_str"] = " ".join(cmd)
        return {
            "cmd": list(cmd),
            "cmd_str": " ".join(cmd),
            "dry_run": bool(dry_run),
            "returncode": 0,
            "ok": True,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(nightly, "_run_cmd", _fake_run_cmd)

    args = nightly.build_parser().parse_args(["--no-preflight-validate-inputs"])
    args.external_packet_accuracy_external_csv = ""
    paths = {
        "feature_csv": str(tmp_path / "feature.csv"),
        "batch_summary_json": str(tmp_path / "batch_summary.json"),
        "claim_correction_prefix": str(tmp_path / "claim_correction"),
        "dashboard_json": str(tmp_path / "dashboard.json"),
        "dashboard_html": str(tmp_path / "dashboard.html"),
        "external_packet_json": str(tmp_path / "external_packet.json"),
    }
    status = nightly._run_external_packet(
        args=args,
        paths=paths,
        env={},
        external_packet_accuracy_external_csv_path=str(acc_csv),
    )
    assert status["ok"] is True
    cmd_str = str(captured.get("cmd_str", ""))
    assert "--accuracy-external-csv" in cmd_str
    assert str(acc_csv) in cmd_str


def test_nightly_batch_dry_run_ood_gate_defaults_hardened(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    ood_cmd = next(
        str(rec.get("cmd_str", ""))
        for rec in summary["results"]
        if str(rec.get("name", "")) == "ood_first_gate"
    )
    assert "--require-real-afdb" in ood_cmd
    assert "--max-proxy-rows 0" in ood_cmd
    assert "--no-enable-proxy-manifest" in ood_cmd


def test_nightly_batch_dry_run_includes_ood_dual_report_status(tmp_path):
    out_runs = tmp_path / "runs"
    out_runs.mkdir(parents=True, exist_ok=True)

    args = nightly.build_parser().parse_args(
        [
            "--date-tag",
            "2026-02-16",
            "--mode",
            "smoke",
            "--runs-dir",
            str(out_runs),
            "--public-out-dir",
            str(tmp_path / "public"),
            "--sources-csv",
            "config/structure_sources_10targets.csv",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--strict-summary-json",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_summary.json",
            "--accuracy-external-csv",
            "runs/openmm_2bead_strict_2026-02-17_candidate_fullrun_accuracy_external.csv",
            "--dry-run",
        ]
    )
    summary = nightly.run_batch(args)
    status = summary.get("ood_dual_report_status", {})
    assert status.get("requested") is True
    assert status.get("dry_run") is True
    assert status.get("ok") is True
