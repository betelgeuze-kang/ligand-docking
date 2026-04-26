from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from tools import build_local_delivery_verdict_gate as mod


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_artifacts(tmp_path: Path) -> dict[str, Path]:
    runs = tmp_path / "runs"
    artifacts = {
        "preflight_json": _write_json(
            runs / "local_delivery_preflight_current.json",
            {"summary": {"overall_ok": True, "dry_run": False}},
        ),
        "accuracy_gate_json": _write_json(
            runs / "accuracy_gate_local_delivery_preflight_current.json",
            {"summary": {"pass": True, "failed_metrics": [], "failed_targets": []}},
        ),
        "requirements_lock_json": _write_json(
            runs / "local_delivery_requirements_lock_current.json",
            {"summary": {"status_line": "complete: lock_lines=10", "missing_count": 0}},
        ),
        "environment_manifest_json": _write_json(
            runs / "local_delivery_environment_manifest_current.json",
            {"summary": {"requirements_lock_complete": True, "missing_requirement_count": 0}},
        ),
        "engine_provenance_json": _write_json(
            runs / "local_delivery_engine_provenance_current.json",
            {"summary": {"provenance_ok": True, "existing_engine_reused": True}},
        ),
        "commercialization_queue_json": _write_json(
            runs / "local_engine_commercialization_queue_current.json",
            {
                "summary": {
                    "blocked_count": 0,
                    "engine_blocker_count": 0,
                    "science_blocker_count": 0,
                    "nightly_stage6_execute_gate_pass": False,
                }
            },
        ),
        "nightly_gate_json": _write_json(
            runs / "nightly_gate_burndown_packet_current.json",
            {
                "summary": {
                    "nightly_gate_pass": True,
                    "primary_gate_value": 2.1,
                    "primary_gate_threshold": 2.5,
                }
            },
        ),
        "wetlab_selected_allatom_json": _write_json(
            runs / "wetlab_selected_allatom_gate_burndown_packet_current.json",
            {
                "summary": {
                    "selected_allatom_final_gate_pass": True,
                    "hard_block_count": 0,
                    "selected_allatom_best_mean_min_distance_A": 2.2,
                    "selected_allatom_selected_threshold_A": 2.5,
                }
            },
        ),
        "current_results_index_json": _write_json(
            runs / "wetlab_current_results_index_current.json",
            {
                "summary": {
                    "status": "wetlab_current_results_index_ready",
                    "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                    "partnering_stack_artifact_complete": True,
                }
            },
        ),
        "partnering_stack_json": _write_json(
            runs / "wetlab_partnering_stack_current.json",
            {
                "summary": {
                    "status": "wetlab_partnering_stack_ready",
                    "artifact_kind": "wetlab_partnering_stack",
                    "artifact_completeness": "full_partnering_stack",
                    "selected_allatom_best_mean_min_distance_A": 2.2,
                    "selected_allatom_best_mean_min_distance_A_source": (
                        "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
                    ),
                    "selected_allatom_selected_threshold_A": 2.5,
                    "selected_allatom_wetlab_gate_pass": True,
                    "selected_allatom_final_gate_pass": True,
                }
            },
        ),
        "status_report_md": tmp_path / "commercialization_status_report.md",
    }
    artifacts["status_report_md"].write_text("# Status\n", encoding="utf-8")
    return artifacts


def _payload(tmp_path: Path, **overrides):
    artifacts = _base_artifacts(tmp_path)
    for key, payload in overrides.pop("rewrite", {}).items():
        _write_json(artifacts[key], payload)
    artifacts.update(overrides)
    return mod.build_payload(claim_scope="kinase,gpcr,ion_channel", **artifacts)


def test_all_green_restricted_scope_is_delivery_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(tmp_path)

    summary = payload["summary"]
    assert summary["delivery_ready"] is True
    assert summary["verdict"] == "delivery_ready"
    assert summary["p0_blocker_count"] == 0
    assert summary["accuracy_gate_pass"] is True
    assert summary["accuracy_gate_check"]["status"] == "pass"
    assert summary["nightly_metric_value"] == 2.1
    assert summary["wetlab_metric_value"] == 2.2


def test_nightly_gate_fail_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "nightly_gate_json": {
                "summary": {
                    "stage6_gate_failed": True,
                    "primary_gate_value": 2.7,
                    "primary_gate_threshold": 2.5,
                }
            }
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["nightly_gate_pass"] is False
    assert any(blocker["code"] == "nightly_gate_not_green" for blocker in payload["p0_blockers"])


def test_accuracy_gate_fail_blocks_delivery_with_structured_reason(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "accuracy_gate_json": {
                "summary": {
                    "pass": False,
                    "failed_targets": ["kinase"],
                    "failed_metrics": [
                        {
                            "scope": "performance",
                            "target": "kinase",
                            "metric": "avg_speedup_on_vs_off",
                            "value": 8.5,
                            "threshold": 12.0,
                            "operator": ">=",
                        }
                    ],
                }
            }
        },
    )

    check = payload["summary"]["accuracy_gate_check"]
    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["accuracy_gate_pass"] is False
    assert check["status"] == "fail"
    assert check["failed_metric_count"] == 1
    assert check["primary_failed_metric"]["metric"] == "avg_speedup_on_vs_off"
    assert "avg_speedup_on_vs_off" in check["reason"]
    assert any(blocker["code"] == "accuracy_gate_not_green" for blocker in payload["p0_blockers"])
    markdown = mod.render_markdown(payload)
    assert "accuracy_gate_check_status" in markdown
    assert "avg_speedup_on_vs_off" in markdown


def test_missing_accuracy_gate_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    artifacts["accuracy_gate_json"].unlink()

    payload = mod.build_payload(claim_scope="kinase", **artifacts)

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["accuracy_gate_check"]["status"] == "missing"
    assert any(blocker["code"] == "missing_required_artifact" for blocker in payload["p0_blockers"])
    assert any(blocker["code"] == "accuracy_gate_not_green" for blocker in payload["p0_blockers"])


def test_nightly_downstream_execute_pass_stays_blocked_until_top_level_gate_is_green(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "commercialization_queue_json": {
                "summary": {
                    "blocked_count": 0,
                    "engine_blocker_count": 0,
                    "science_blocker_count": 0,
                    "nightly_stage6_execute_gate_pass": True,
                    "nightly_stage6_execute_gate_mean_min_distance_A": 2.2689,
                }
            },
            "nightly_gate_json": {
                "summary": {
                    "stage6_gate_failed": True,
                    "status": "waiting_for_stage6_reentry",
                    "latest_failed_stage": "stage3_backmapping_scoring",
                    "latest_error_code": "HTVS_SMOKE_FAILED",
                    "next_required_step": "Recover upstream nightly failures first.",
                    "primary_gate_value": 2.656,
                    "primary_gate_threshold": 2.5,
                }
            },
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["nightly_downstream_execute_gate_pass"] is True
    assert payload["summary"]["nightly_downstream_execute_metric"] == 2.2689
    assert payload["summary"]["nightly_downstream_execute_source"] == ""
    assert payload["summary"]["nightly_top_level_status"] == "waiting_for_stage6_reentry"
    assert payload["summary"]["nightly_top_level_latest_failed_stage"] == "stage3_backmapping_scoring"
    assert payload["summary"]["nightly_top_level_error_code"] == "HTVS_SMOKE_FAILED"
    assert payload["summary"]["nightly_top_level_next_required_step"] == "Recover upstream nightly failures first."
    assert payload["summary"]["nightly_top_level_promotion_pending"] is True
    blocker = next(blocker for blocker in payload["p0_blockers"] if blocker["code"] == "nightly_gate_not_green")
    assert "downstream execute evidence is green" in blocker["reason"]
    assert "latest_failed_stage=stage3_backmapping_scoring" in blocker["reason"]
    markdown = mod.render_markdown(payload)
    assert "nightly_top_level_status" in markdown
    assert "waiting_for_stage6_reentry" in markdown


def test_wetlab_selected_allatom_fail_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "wetlab_selected_allatom_json": {
                "summary": {
                    "selected_allatom_final_gate_pass": False,
                    "hard_block_count": 1,
                    "primary_burndown_value": 3.1,
                    "primary_burndown_threshold": 2.5,
                }
            }
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["wetlab_selected_allatom_pass"] is False
    assert payload["summary"]["wetlab_hard_block_count"] == 1
    assert payload["summary"]["wetlab_primary_burndown_code"] == ""
    assert any(blocker["code"] == "wetlab_selected_allatom_not_green" for blocker in payload["p0_blockers"])


def test_wetlab_selected_allatom_blocker_reason_includes_hard_and_missing_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "wetlab_selected_allatom_json": {
                "summary": {
                    "selected_allatom_final_gate_pass": False,
                    "hard_block_count": 2,
                    "semi_hard_block_count": 2,
                    "missing_metric_count": 1,
                    "primary_burndown_code": "recompute_mean_min_distance_A",
                    "primary_burndown_action": "tighten_pose_geometry_under_strict_gate",
                    "primary_burndown_metric": "mean_min_distance_A",
                    "primary_burndown_value": 3.705,
                    "primary_burndown_threshold": 2.5,
                    "primary_burndown_delta": 1.205,
                    "next_required_step": "Start with recompute_mean_min_distance_A.",
                }
            }
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["wetlab_hard_block_count"] == 2
    assert payload["summary"]["wetlab_semi_hard_block_count"] == 2
    assert payload["summary"]["wetlab_missing_metric_count"] == 1
    assert payload["summary"]["wetlab_primary_burndown_code"] == "recompute_mean_min_distance_A"
    assert payload["summary"]["wetlab_primary_burndown_action"] == "tighten_pose_geometry_under_strict_gate"
    assert payload["summary"]["wetlab_primary_burndown_metric"] == "mean_min_distance_A"
    assert payload["summary"]["wetlab_primary_burndown_delta_A"] == 1.205
    assert payload["summary"]["wetlab_next_required_step"] == "Start with recompute_mean_min_distance_A."
    blocker = next(
        blocker for blocker in payload["p0_blockers"] if blocker["code"] == "wetlab_selected_allatom_not_green"
    )
    assert "hard_block_count=2" in blocker["reason"]
    assert "missing_metric_count=1" in blocker["reason"]
    assert "recompute_mean_min_distance_A" in blocker["reason"]
    assert "delta_A=1.205" in blocker["reason"]
    markdown = mod.render_markdown(payload)
    assert "wetlab_primary_burndown_delta_A" in markdown
    assert "Start with recompute_mean_min_distance_A." in markdown


def test_partnering_stack_placeholder_or_incomplete_blocks_delivery_when_other_wetlab_evidence_looks_green(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "current_results_index_json": {
                "summary": {
                    "status": "wetlab_current_results_index_ready",
                    "partnering_stack_artifact_status": "ok",
                    "partnering_stack_artifact_complete": False,
                }
            },
            "partnering_stack_json": {"summary": {"status": "ok"}},
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["partnering_stack_artifact_complete"] is False
    assert any(blocker["code"] == "partnering_stack_placeholder_or_incomplete" for blocker in payload["p0_blockers"])


def test_minimal_partnering_stack_ready_marker_is_still_incomplete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")

    payload = _payload(
        tmp_path,
        rewrite={
            "current_results_index_json": {
                "summary": {
                    "status": "wetlab_current_results_index_ready",
                    "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                    "partnering_stack_artifact_complete": True,
                }
            },
            "partnering_stack_json": {"summary": {"status": "wetlab_partnering_stack_ready"}},
        },
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["partnering_stack_source_artifact_complete"] is False
    assert any(blocker["code"] == "partnering_stack_placeholder_or_incomplete" for blocker in payload["p0_blockers"])


def test_full_partnering_stack_does_not_increase_current_p0_blockers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    runs = tmp_path / "runs"
    current_results_index_json = _write_json(
        runs / "wetlab_current_results_index_current.json",
        {
            "summary": {
                "status": "wetlab_current_results_index_ready",
                "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                "partnering_stack_artifact_complete": True,
            }
        },
    )
    partnering_stack_json = _write_json(
        runs / "wetlab_partnering_stack_current.json",
        {
            "summary": {
                "status": "wetlab_partnering_stack_ready",
                "artifact_kind": "wetlab_partnering_stack",
                "artifact_completeness": "full_partnering_stack",
                "selected_allatom_best_mean_min_distance_A": 3.375,
                "selected_allatom_best_mean_min_distance_A_source": (
                    "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
                ),
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_pass": False,
            }
        },
    )

    payload = _payload(
        tmp_path,
        rewrite={
            "commercialization_queue_json": {"summary": {"blocked_count": 1}},
            "wetlab_selected_allatom_json": {
                "summary": {
                    "selected_allatom_final_gate_pass": False,
                    "hard_block_count": 1,
                    "selected_allatom_best_mean_min_distance_A": 3.375,
                    "selected_allatom_selected_threshold_A": 2.5,
                }
            },
        },
        current_results_index_json=current_results_index_json,
        partnering_stack_json=partnering_stack_json,
    )

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["p0_blocker_count"] == 2
    assert payload["summary"]["wetlab_metric_value"] == 3.375
    assert payload["summary"]["wetlab_metric_delta_A"] == 0.875
    assert payload["summary"]["partnering_stack_artifact_complete"] is True
    assert payload["summary"]["partnering_stack_source_artifact_complete"] is True
    assert not any(blocker["code"] == "partnering_stack_placeholder_or_incomplete" for blocker in payload["p0_blockers"])


def test_broad_or_transporter_claim_scope_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)

    broad = mod.build_payload(claim_scope="all drug targets", **artifacts)
    transporter = mod.build_payload(claim_scope="transporter", **artifacts)

    assert broad["summary"]["delivery_ready"] is False
    assert broad["summary"]["claim_scope_ok"] is False
    assert transporter["summary"]["delivery_ready"] is False
    assert transporter["summary"]["claim_scope_ok"] is False


def test_missing_required_artifact_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    artifacts["nightly_gate_json"].unlink()

    payload = mod.build_payload(claim_scope="kinase", **artifacts)

    assert payload["summary"]["delivery_ready"] is False
    assert any(blocker["code"] == "missing_required_artifact" for blocker in payload["p0_blockers"])


def test_source_artifacts_include_auditable_fingerprints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    artifacts["nightly_gate_json"].unlink()

    payload = mod.build_payload(claim_scope="kinase", **artifacts)
    by_label = {artifact["label"]: artifact for artifact in payload["source_artifacts"]}
    preflight_bytes = artifacts["preflight_json"].read_bytes()

    assert payload["generated_at_local"]
    assert payload["summary"]["generated_at_local"] == payload["generated_at_local"]
    assert payload["summary"]["source_artifact_count"] == 11
    assert payload["summary"]["source_artifact_missing_count"] == 1
    assert payload["summary"]["source_artifact_invalid_count"] == 0
    assert payload["summary"]["source_artifacts_all_fingerprinted"] is False
    assert by_label["preflight"]["present"] is True
    assert by_label["preflight"]["status"] == "present"
    assert by_label["preflight"]["json_valid"] is True
    assert by_label["preflight"]["parse_error"] == ""
    assert by_label["preflight"]["size_bytes"] == len(preflight_bytes)
    assert by_label["preflight"]["sha256"] == hashlib.sha256(preflight_bytes).hexdigest()
    assert by_label["preflight"]["mtime_ns"] == artifacts["preflight_json"].stat().st_mtime_ns
    assert by_label["preflight"]["mtime_epoch"] > 0
    assert by_label["preflight"]["mtime_local"]
    assert by_label["nightly_gate"]["present"] is False
    assert by_label["nightly_gate"]["status"] == "missing"
    assert by_label["nightly_gate"]["size_bytes"] == 0
    assert by_label["nightly_gate"]["sha256"] == ""
    assert by_label["nightly_gate"]["mtime_ns"] == 0
    assert by_label["nightly_gate"]["mtime_epoch"] == 0.0
    assert by_label["nightly_gate"]["mtime_local"] == ""

    markdown = mod.render_markdown(payload)
    assert "Artifact Fingerprints" in markdown
    assert "sha256_prefix" in markdown
    assert by_label["preflight"]["sha256"][:12] in markdown


def test_invalid_required_json_still_records_fingerprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    invalid_text = "{not valid json"
    artifacts["requirements_lock_json"].write_text(invalid_text, encoding="utf-8")

    payload = mod.build_payload(claim_scope="kinase", **artifacts)
    requirements_artifact = next(
        artifact for artifact in payload["source_artifacts"] if artifact["label"] == "requirements_lock"
    )

    assert payload["summary"]["delivery_ready"] is False
    assert any(blocker["code"] == "invalid_required_artifact" for blocker in payload["p0_blockers"])
    assert payload["summary"]["source_artifact_invalid_count"] == 1
    assert requirements_artifact["present"] is True
    assert requirements_artifact["status"] == "invalid_json"
    assert requirements_artifact["json_valid"] is False
    assert requirements_artifact["parse_error"]
    assert requirements_artifact["size_bytes"] == len(invalid_text.encode("utf-8"))
    assert requirements_artifact["sha256"] == hashlib.sha256(invalid_text.encode("utf-8")).hexdigest()
    assert requirements_artifact["mtime_ns"] == artifacts["requirements_lock_json"].stat().st_mtime_ns


def test_missing_status_report_blocks_delivery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    artifacts["status_report_md"].unlink()

    payload = mod.build_payload(claim_scope="kinase", **artifacts)

    assert payload["summary"]["delivery_ready"] is False
    assert payload["summary"]["status_report_present"] is False
    assert any(blocker["code"] == "missing_status_report" for blocker in payload["p0_blockers"])


def test_cli_writes_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    out_json = tmp_path / "runs" / "verdict.json"
    out_md = tmp_path / "runs" / "verdict.md"

    argv = [
        sys.executable,
        str(Path(mod.__file__).resolve()),
        "--claim-scope",
        "kinase,gpcr",
        "--preflight-json",
        str(artifacts["preflight_json"]),
        "--accuracy-gate-json",
        str(artifacts["accuracy_gate_json"]),
        "--requirements-lock-json",
        str(artifacts["requirements_lock_json"]),
        "--environment-manifest-json",
        str(artifacts["environment_manifest_json"]),
        "--engine-provenance-json",
        str(artifacts["engine_provenance_json"]),
        "--commercialization-queue-json",
        str(artifacts["commercialization_queue_json"]),
        "--status-report-md",
        str(artifacts["status_report_md"]),
        "--nightly-gate-json",
        str(artifacts["nightly_gate_json"]),
        "--wetlab-selected-allatom-json",
        str(artifacts["wetlab_selected_allatom_json"]),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ]
    subprocess.run(argv, cwd=tmp_path, check=True)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["summary"]["delivery_ready"] is True
    assert "# Local Delivery Verdict Gate" in markdown
    assert "P0 Blockers" in markdown


def test_main_returns_nonzero_when_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "RUNS", tmp_path / "runs")
    artifacts = _base_artifacts(tmp_path)
    _write_json(
        artifacts["nightly_gate_json"],
        {"summary": {"stage6_gate_failed": True, "primary_gate_value": 2.7, "primary_gate_threshold": 2.5}},
    )

    rc = mod.main(
        [
            "--claim-scope",
            "kinase,gpcr",
            "--preflight-json",
            str(artifacts["preflight_json"]),
            "--accuracy-gate-json",
            str(artifacts["accuracy_gate_json"]),
            "--requirements-lock-json",
            str(artifacts["requirements_lock_json"]),
            "--environment-manifest-json",
            str(artifacts["environment_manifest_json"]),
            "--engine-provenance-json",
            str(artifacts["engine_provenance_json"]),
            "--commercialization-queue-json",
            str(artifacts["commercialization_queue_json"]),
            "--nightly-gate-json",
            str(artifacts["nightly_gate_json"]),
            "--wetlab-selected-allatom-json",
            str(artifacts["wetlab_selected_allatom_json"]),
            "--out-json",
            str(tmp_path / "runs" / "blocked.json"),
            "--out-md",
            str(tmp_path / "runs" / "blocked.md"),
        ]
    )

    assert rc == 2
