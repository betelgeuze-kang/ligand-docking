import json
from pathlib import Path

from tools import run_openmm_2bead_strict_release as rel


def _write_manifest(path: Path) -> None:
    path.write_text(
        "target,path,engine,label,frame,representation\n"
        "Chignolin,/tmp/chignolin.npy,openmm,chignolin,-1,ca_sc_2bead\n",
        encoding="utf-8",
    )


def _write_profile(path: Path) -> None:
    payload = {
        "meta": {"created_at": "2026-02-15"},
        "targets": {
            "Chignolin": {
                "dt": 3e-6,
                "restraint_k": 5.0,
                "force_clip": 100.0,
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_args(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    profile = tmp_path / "profile.json"
    _write_manifest(manifest)
    _write_profile(profile)

    parser = rel.build_parser()
    return parser.parse_args(
        [
            "--targets",
            "Chignolin",
            "--skip-openmm-generate",
            "--external-manifest",
            str(manifest),
            "--profile-json",
            str(profile),
            "--no-prune-runs",
            "--no-publish-release",
            "--out-prefix",
            str(tmp_path / "runs" / "openmm_2bead_strict_test"),
            "--submission-dir",
            str(tmp_path / "submission"),
        ]
    )


def _patch_pass_mocks(monkeypatch):
    monkeypatch.setattr(
        rel,
        "validate_md_reference_set",
        lambda **kwargs: {
            "summary": {
                "ready": True,
                "md_ok_targets": 1,
                "expected_target_count": 1,
                "failed_targets": [],
            }
        },
    )
    monkeypatch.setattr(
        rel,
        "run_target_tuned_validation",
        lambda _args: {
            "summary": {
                "targets": 1,
                "passed_targets": 1,
                "failed_targets": [],
                "avg_rmsd_aligned_mean": 0.5,
                "avg_energy_drift_ratio_mean": 0.1,
            }
        },
    )
    monkeypatch.setattr(
        rel,
        "run_accuracy_gate",
        lambda _args: {
            "summary": {
                "pass": True,
                "failed_targets": [],
                "failed_metrics": [],
            },
            "parity_summary": {
                "avg_neighbor_jaccard": 1.0,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "overflow_events": [],
        },
    )
    monkeypatch.setattr(
        rel,
        "run_stage2_report",
        lambda _args: {
            "summary": {
                "avg_speedup_on_vs_off": 13.0,
            },
            "rows": [{"target": "Chignolin", "speedup_on_vs_off": 13.0}],
        },
    )
    monkeypatch.setattr(
        rel,
        "run_accuracy_report",
        lambda _args: {"summary": {"avg_rmsd_aligned": 1.1}},
    )
    monkeypatch.setattr(
        rel,
        "build_packet",
        lambda _args: {
            "meta": {"packet_version": "v2"},
            "global_summary": {
                "gate_pass": True,
                "speed": {"avg_speedup_on_vs_off": 13.0},
            },
        },
    )
    monkeypatch.setattr(rel, "classify_runs_files_main", lambda: None)


def test_run_openmm_2bead_strict_release_pass(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    _patch_pass_mocks(monkeypatch)

    payload = rel.run_release(args)

    assert payload["summary"]["pass"] is True
    assert payload["summary"]["failed_gates"] == []
    assert Path(payload["artifacts"]["summary_json"]).exists()
    assert Path(payload["artifacts"]["summary_csv"]).exists()
    assert Path(payload["artifacts"]["summary_md"]).exists()


def test_run_openmm_2bead_strict_release_fails_on_long_stability(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    _patch_pass_mocks(monkeypatch)
    monkeypatch.setattr(
        rel,
        "run_target_tuned_validation",
        lambda _args: {
            "summary": {
                "targets": 1,
                "passed_targets": 0,
                "failed_targets": ["Chignolin"],
            }
        },
    )

    try:
        rel.run_release(args)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "long_stability" in str(exc)


def test_run_openmm_2bead_strict_release_fails_on_accuracy_gate(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    _patch_pass_mocks(monkeypatch)
    monkeypatch.setattr(
        rel,
        "run_accuracy_gate",
        lambda _args: {
            "summary": {
                "pass": False,
                "failed_targets": ["Chignolin"],
                "failed_metrics": [{"metric": "neighbor_jaccard_mean"}],
            },
            "parity_summary": {
                "avg_neighbor_jaccard": 0.99,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "overflow_events": [],
        },
    )

    try:
        rel.run_release(args)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "accuracy_gate" in str(exc)


def test_run_openmm_2bead_strict_release_fails_on_speed(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    args.expected_target_count = 2
    _patch_pass_mocks(monkeypatch)
    monkeypatch.setattr(
        rel,
        "run_target_tuned_validation",
        lambda _args: {
            "summary": {
                "targets": 1,
                "passed_targets": 2,
                "failed_targets": [],
            }
        },
    )
    monkeypatch.setattr(
        rel,
        "run_stage2_report",
        lambda _args: {
            "summary": {
                "avg_speedup_on_vs_off": 8.0,
            },
            "rows": [{"target": "Chignolin", "speedup_on_vs_off": 8.0}],
        },
    )

    try:
        rel.run_release(args)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "speed" in str(exc)


def test_run_openmm_2bead_strict_release_summary_schema(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    _patch_pass_mocks(monkeypatch)

    payload = rel.run_release(args)

    assert "summary" in payload
    assert "pass" in payload["summary"]
    assert "failed_gates" in payload["summary"]
    assert "failed_targets" in payload["summary"]
    assert "gates" in payload
    assert "accuracy_gate" in payload["gates"]
    assert "long_stability" in payload["gates"]
    assert "speed" in payload["gates"]
    assert "md_reference_validation" in payload["gates"]
    assert "artifacts" in payload


def test_run_openmm_2bead_strict_release_forwards_ai_checkpoint_options(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    args.use_ai_router = True
    args.ai_router_checkpoint = "models/best_airouter_model_StrategicOrchestrator.pth"
    args.ai_router_checkpoint_strict = True
    args.accuracy_simulation_engine = "benchmark"
    args.accuracy_use_ai_router = True
    args.accuracy_ai_interval = 4
    args.accuracy_benchmark_warmup_steps = 0
    args.accuracy_benchmark_replicas = 1
    args.accuracy_benchmark_force_backend = "auto"
    args.accuracy_benchmark_neighbor_settings = (
        "grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64"
    )
    args.accuracy_benchmark_force_clip = 170.0
    args.accuracy_benchmark_ai_correction_clip = 85.0
    args.accuracy_ai_collect_aux = False

    captured = {}

    monkeypatch.setattr(
        rel,
        "validate_md_reference_set",
        lambda **kwargs: {
            "summary": {
                "ready": True,
                "md_ok_targets": 1,
                "expected_target_count": 1,
                "failed_targets": [],
            }
        },
    )
    monkeypatch.setattr(
        rel,
        "run_target_tuned_validation",
        lambda _args: {
            "summary": {
                "targets": 1,
                "passed_targets": 1,
                "failed_targets": [],
                "avg_rmsd_aligned_mean": 0.5,
                "avg_energy_drift_ratio_mean": 0.1,
            }
        },
    )

    def _fake_accuracy_gate(ns):
        captured["gate_use_ai_router"] = bool(getattr(ns, "use_ai_router"))
        captured["gate_ckpt"] = str(getattr(ns, "ai_router_checkpoint"))
        return {
            "summary": {"pass": True, "failed_targets": [], "failed_metrics": []},
            "parity_summary": {
                "avg_neighbor_jaccard": 1.0,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "overflow_events": [],
        }

    def _fake_stage2(ns):
        captured["stage2_use_ai_router"] = bool(getattr(ns, "use_ai_router"))
        captured["stage2_ckpt"] = str(getattr(ns, "ai_router_checkpoint"))
        return {
            "summary": {"avg_speedup_on_vs_off": 13.0},
            "rows": [{"target": "Chignolin", "speedup_on_vs_off": 13.0}],
        }

    def _fake_accuracy(ns):
        captured["acc_engine"] = str(getattr(ns, "simulation_engine"))
        captured["acc_use_ai_router"] = bool(getattr(ns, "use_ai_router"))
        captured["acc_ckpt"] = str(getattr(ns, "ai_router_checkpoint"))
        captured["acc_force_clip"] = float(getattr(ns, "benchmark_force_clip"))
        captured["acc_ai_clip"] = float(getattr(ns, "benchmark_ai_correction_clip"))
        return {"summary": {"avg_rmsd_aligned": 1.1}}

    monkeypatch.setattr(rel, "run_accuracy_gate", _fake_accuracy_gate)
    monkeypatch.setattr(rel, "run_stage2_report", _fake_stage2)
    monkeypatch.setattr(rel, "run_accuracy_report", _fake_accuracy)
    monkeypatch.setattr(
        rel,
        "build_packet",
        lambda _args: {
            "meta": {"packet_version": "v2"},
            "global_summary": {"gate_pass": True, "speed": {"avg_speedup_on_vs_off": 13.0}},
        },
    )
    monkeypatch.setattr(rel, "classify_runs_files_main", lambda: None)

    payload = rel.run_release(args)
    assert payload["summary"]["pass"] is True
    assert captured["gate_use_ai_router"] is True
    assert captured["stage2_use_ai_router"] is True
    assert captured["acc_engine"] == "benchmark"
    assert captured["acc_use_ai_router"] is True
    assert captured["gate_ckpt"] == "models/best_airouter_model_StrategicOrchestrator.pth"
    assert captured["stage2_ckpt"] == "models/best_airouter_model_StrategicOrchestrator.pth"
    assert captured["acc_ckpt"] == "models/best_airouter_model_StrategicOrchestrator.pth"
    assert captured["acc_force_clip"] == 170.0
    assert captured["acc_ai_clip"] == 85.0


def test_run_openmm_2bead_strict_release_minimal_archives_intermediate(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    args.artifact_level = "minimal"
    args.archive_intermediate = True

    monkeypatch.setattr(
        rel,
        "validate_md_reference_set",
        lambda **kwargs: {
            "summary": {
                "ready": True,
                "md_ok_targets": 1,
                "expected_target_count": 1,
                "failed_targets": [],
            }
        },
    )
    monkeypatch.setattr(
        rel,
        "run_target_tuned_validation",
        lambda _args: {
            "summary": {
                "targets": 1,
                "passed_targets": 1,
                "failed_targets": [],
                "avg_rmsd_aligned_mean": 0.5,
                "avg_energy_drift_ratio_mean": 0.1,
            }
        },
    )

    def _fake_accuracy_gate(ns):
        parity_target = Path(f"{ns.parity_prefix}_target.csv")
        parity_target.parent.mkdir(parents=True, exist_ok=True)
        parity_target.write_text("target,pass\nChignolin,1\n", encoding="utf-8")
        Path(f"{ns.parity_prefix}_sample.csv").write_text("sample,ok\n0,1\n", encoding="utf-8")
        Path(f"{ns.parity_prefix}_atom.csv").write_text("atom,ok\n0,1\n", encoding="utf-8")
        Path(f"{ns.parity_prefix}_pair.csv").write_text("pair,ok\n0,1\n", encoding="utf-8")
        Path(f"{ns.parity_prefix}.json").write_text("{}", encoding="utf-8")
        Path(f"{ns.stage2_prefix}.csv").write_text("target,speedup_on_vs_off\nChignolin,13.0\n", encoding="utf-8")
        Path(f"{ns.stage2_prefix}.json").write_text("{}", encoding="utf-8")
        out_json = Path(ns.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps({"summary": {"pass": True, "failed_targets": [], "failed_metrics": []}}),
            encoding="utf-8",
        )
        Path(ns.out_csv).write_text("target,pass\nChignolin,1\n", encoding="utf-8")
        return {
            "summary": {"pass": True, "failed_targets": [], "failed_metrics": []},
            "parity_summary": {
                "avg_neighbor_jaccard": 1.0,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "overflow_events": [],
        }

    def _fake_stage2(ns):
        report_csv = Path(ns.report_csv)
        report_csv.parent.mkdir(parents=True, exist_ok=True)
        report_csv.write_text("target,speedup_on_vs_off\nChignolin,13.0\n", encoding="utf-8")
        Path(ns.report_json).write_text(json.dumps({"summary": {"avg_speedup_on_vs_off": 13.0}}), encoding="utf-8")
        Path(ns.benchmark_csv).write_text("target,steps_per_sec\nChignolin,1000\n", encoding="utf-8")
        return {
            "summary": {"avg_speedup_on_vs_off": 13.0},
            "rows": [{"target": "Chignolin", "speedup_on_vs_off": 13.0}],
        }

    def _fake_accuracy(ns):
        out_csv = Path(ns.out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        out_csv.write_text("target,rmsd_aligned\nChignolin,1.0\n", encoding="utf-8")
        Path(ns.out_json).write_text(json.dumps({"summary": {"avg_rmsd_aligned": 1.0}}), encoding="utf-8")
        return {"summary": {"avg_rmsd_aligned": 1.0}}

    monkeypatch.setattr(rel, "run_accuracy_gate", _fake_accuracy_gate)
    monkeypatch.setattr(rel, "run_stage2_report", _fake_stage2)
    monkeypatch.setattr(rel, "run_accuracy_report", _fake_accuracy)
    monkeypatch.setattr(
        rel,
        "build_packet",
        lambda _args: {
            "meta": {"packet_version": "v2"},
            "global_summary": {"gate_pass": True, "speed": {"avg_speedup_on_vs_off": 13.0}},
        },
    )
    monkeypatch.setattr(rel, "classify_runs_files_main", lambda: None)

    payload = rel.run_release(args)

    assert payload["summary"]["pass"] is True
    policy = payload.get("artifact_policy", {})
    assert policy.get("level") == "minimal"
    assert int(policy.get("archived_files_count", 0)) >= 1

    submission_dir = Path(payload["artifacts"]["submission_dir"])
    copied_names = {p.name for p in submission_dir.iterdir() if p.is_file()}
    assert "openmm_2bead_strict_test_accuracy_gate_parity_target.csv" in copied_names
    assert "openmm_2bead_strict_test_accuracy_gate_parity_sample.csv" not in copied_names
    assert "openmm_2bead_strict_test_accuracy_gate_parity_atom.csv" not in copied_names
    assert "openmm_2bead_strict_test_accuracy_gate_parity_pair.csv" not in copied_names


def test_run_openmm_2bead_strict_release_publish_release(monkeypatch, tmp_path):
    args = _base_args(tmp_path)
    args.publish_release = True
    args.publish_release_tag = "test_tag"
    _patch_pass_mocks(monkeypatch)

    captured = {}

    def _fake_publish(**kwargs):
        captured.update(kwargs)
        return {
            "release_tag": kwargs.get("release_tag"),
            "copied_files": ["a", "b"],
        }

    monkeypatch.setattr(rel, "publish_release", _fake_publish)

    payload = rel.run_release(args)
    assert payload["summary"]["pass"] is True
    assert payload["publish_policy"]["enabled"] is True
    assert payload["publish_policy"]["summary"]["release_tag"] == "test_tag"
    assert captured.get("release_tag") == "test_tag"
