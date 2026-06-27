import json
import zipfile
from pathlib import Path

import pytest

from tools import build_local_delivery_bundle as b
from tools import build_local_delivery_verdict_gate as gate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _patch_workspace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(b, "_load_verdict_gate_builder", lambda: gate)


def _write_canonical_inputs(tmp_path: Path, *, include_queue_csv: bool = True) -> dict[str, Path]:
    runs = tmp_path / "runs"
    paths = {
        "status_report": tmp_path / "commercialization_status_report.md",
        "preflight_json": runs / "local_delivery_preflight_current.json",
        "preflight_md": runs / "local_delivery_preflight_current.md",
        "local_ci_summary_json": runs / "local_ci_tests_summary.json",
        "accuracy_gate_json": runs / "accuracy_gate_local_delivery_preflight_current.json",
        "queue_json": runs / "local_engine_commercialization_queue_current.json",
        "queue_csv": runs / "local_engine_commercialization_queue_current.csv",
        "queue_md": runs / "local_engine_commercialization_queue_current.md",
        "environment_json": runs / "local_delivery_environment_manifest_current.json",
        "environment_md": runs / "local_delivery_environment_manifest_current.md",
        "requirements_lock_json": runs / "local_delivery_requirements_lock_current.json",
        "requirements_lock_md": runs / "local_delivery_requirements_lock_current.md",
        "requirements_lock_txt": runs / "local_delivery_requirements_lock_current.txt",
        "engine_provenance_json": runs / "local_delivery_engine_provenance_current.json",
        "engine_provenance_md": runs / "local_delivery_engine_provenance_current.md",
        "nightly_gate_json": runs / "nightly_gate_burndown_packet_current.json",
        "wetlab_selected_allatom_json": runs / "wetlab_selected_allatom_gate_burndown_packet_current.json",
        "current_results_index_json": runs / "wetlab_current_results_index_current.json",
        "partnering_stack_json": runs / "wetlab_partnering_stack_current.json",
        "rescue_attempt_validation_json": runs / "wetlab_tcruzi_pde_allatom_rescue_attempt_validation_current.json",
        "verdict_gate_json": runs / "local_delivery_verdict_gate_current.json",
        "verdict_gate_md": runs / "local_delivery_verdict_gate_current.md",
    }

    _write_text(paths["status_report"], "# local delivery status\n")
    _write_json(
        paths["preflight_json"],
        {
            "summary": {
                "overall_ok": True,
                "next_required_step": "Proceed with the scoped local delivery bundle.",
            }
        },
    )
    _write_text(paths["preflight_md"], "# preflight\n")
    _write_json(paths["local_ci_summary_json"], {"summary": {"ok": True}})
    _write_json(paths["accuracy_gate_json"], {"summary": {"pass": True, "failed_metrics": [], "failed_targets": []}})
    _write_json(paths["queue_json"], {"summary": {"status_line": "queue=ready"}})
    if include_queue_csv:
        _write_text(paths["queue_csv"], "lane,status\nprimary,ready\n")
    _write_text(paths["queue_md"], "# queue\n")
    _write_json(
        paths["environment_json"],
        {
            "summary": {
                "git_commit": "abc123def456",
                "requirements_lock_complete": True,
                "status_line": "python=3.12 | accelerator=cpu",
            }
        },
    )
    _write_text(paths["environment_md"], "# environment\n")
    _write_json(
        paths["requirements_lock_json"],
        {
            "summary": {
                "missing_count": 0,
                "loose_source_requirement_count": 0,
                "missing_input_file_count": 0,
                "status_line": "complete: lock_lines=2",
            }
        },
    )
    _write_text(paths["requirements_lock_md"], "# requirements lock\n")
    _write_text(paths["requirements_lock_txt"], "numpy==2.1.0\npytest==8.3.5\n")
    _write_json(
        paths["engine_provenance_json"],
        {
            "summary": {
                "existing_engine_reused": True,
                "required_surface_count": 6,
                "present_surface_count": 6,
                "missing_surface_count": 0,
                "status_line": "existing_engine_reused=true | surfaces=6/6 present",
            }
        },
    )
    _write_text(paths["engine_provenance_md"], "# engine provenance\n")
    _write_json(
        paths["nightly_gate_json"],
        {
            "summary": {
                "stage6_gate_failed": False,
                "nightly_gate_pass": True,
                "primary_gate_value": 2.1,
                "primary_gate_threshold": 2.5,
            }
        },
    )
    _write_json(
        paths["wetlab_selected_allatom_json"],
        {
            "summary": {
                "selected_allatom_final_gate_pass": True,
                "selected_allatom_wetlab_gate_pass": True,
                "hard_block_count": 0,
                "semi_hard_block_count": 0,
                "primary_burndown_value": 2.2,
                "primary_burndown_threshold": 2.5,
            }
        },
    )
    _write_json(
        paths["current_results_index_json"],
        {
            "summary": {
                "status": "wetlab_current_results_index_ready",
                "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                "partnering_stack_artifact_complete": True,
            }
        },
    )
    _write_json(
        paths["partnering_stack_json"],
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
    )
    _write_json(
        paths["rescue_attempt_validation_json"],
        {
            "summary": {
                "rescue_attempt_validation": "pass",
                "overall_ok": True,
                "failed_check_count": 0,
                "hard_fail_count": 0,
                "warning_count": 0,
                "attempt_id": "rescue-attempt-test",
                "execution_mode": "local_fixture",
                "scoring_status": "pass",
                "input_fingerprint_recomputed_ok": True,
                "required_artifact_missing_count": 0,
                "path_boundary_fail_count": 0,
            }
        },
    )
    _write_text(paths["verdict_gate_md"], "# verdict gate\n")
    _write_verdict_gate(paths, delivery_ready=True)
    return paths


def _verdict_gate_payload(paths: dict[str, Path]) -> dict:
    return gate.build_payload(
        claim_scope="kinase,gpcr,ion_channel",
        preflight_json=paths["preflight_json"],
        accuracy_gate_json=paths["accuracy_gate_json"],
        requirements_lock_json=paths["requirements_lock_json"],
        environment_manifest_json=paths["environment_json"],
        engine_provenance_json=paths["engine_provenance_json"],
        commercialization_queue_json=paths["queue_json"],
        status_report_md=paths["status_report"],
        nightly_gate_json=paths["nightly_gate_json"],
        wetlab_selected_allatom_json=paths["wetlab_selected_allatom_json"],
        current_results_index_json=paths["current_results_index_json"],
        partnering_stack_json=paths["partnering_stack_json"],
        rescue_attempt_validation_json=paths["rescue_attempt_validation_json"],
    )


def _write_verdict_gate(paths: dict[str, Path], *, delivery_ready: bool) -> None:
    payload = _verdict_gate_payload(paths)
    if not delivery_ready:
        payload["summary"].update(
            {
                "delivery_ready": False,
                "verdict": "blocked",
                "p0_blocker_count": 1,
                "hard_blocker_count": max(1, int(payload["summary"].get("hard_blocker_count", 0) or 0)),
                "status_line": "delivery_ready=false: P0 blocker remains for the restricted local scope.",
            }
        )
    _write_json(paths["verdict_gate_json"], payload)


def _write_family_scorecard(path: Path, *, status: str = "pass", acceptance_pass: bool = True) -> None:
    _write_json(
        path,
        {
            "summary": {
                "family": "kinase",
                "scorecard_level_status": status,
                "acceptance_overall_pass": acceptance_pass,
            }
        },
    )


def _parse_args(extra_args: list[str] | None = None):
    return b.build_parser().parse_args(
        [
            "--bundle-tag",
            "test_bundle",
            "--request-summary",
            "Scoped kinase local delivery request for 2026-04-23.",
            "--delivery-scope",
            "kinase / ion_channel / gpcr",
            "--claim-scope",
            "Restricted local-delivery scope for kinase / ion_channel / gpcr only.",
            "--verdict",
            "Delivery-ready only for the attached restricted local-delivery scope.",
            "--rerun-command",
            "python3 tools/run_local_delivery_preflight.py && python3 tools/build_local_delivery_bundle.py",
            *(extra_args or []),
        ]
    )


def test_build_local_delivery_bundle_smoke(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)

    config_path = tmp_path / "profiles" / "delivery.yaml"
    artifact_path = tmp_path / "results" / "prediction.json"
    _write_text(config_path, "family: kinase\n")
    _write_json(artifact_path, {"score": 0.91})

    args = _parse_args(
        [
            "--config-path",
            str(config_path),
            "--artifact-path",
            str(artifact_path),
        ]
    )

    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_test_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    checksums = (bundle_dir / "checksums.sha256").read_text(encoding="utf-8")

    assert payload["bundle_dir"] == str(bundle_dir.resolve())
    assert payload["included_count"] == 24
    assert payload["missing_count"] == 0
    assert payload["archive_sha256"]
    assert zipfile.is_zipfile(bundle_dir / "bundle.zip")

    assert manifest["bundle_tag"] == "test_bundle"
    assert manifest["source_repo_commit"] == "abc123def456"
    assert manifest["preflight"]["overall_ok"] is True
    assert manifest["queue"]["artifacts"]["csv"]["present"] is True
    assert manifest["environment"]["artifacts"]["json"]["present"] is True
    assert manifest["environment"]["artifacts"]["requirements_lock_txt"]["present"] is True
    assert manifest["engine_provenance"]["artifacts"]["json"]["present"] is True
    assert manifest["engine_provenance"]["summary"]["existing_engine_reused"] is True
    assert manifest["local_delivery_verdict_gate"]["artifacts"]["json"]["present"] is True
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    source_artifact_labels = {
        artifact["label"] for artifact in manifest["local_delivery_verdict_gate"]["source_artifacts"]
    }
    assert source_artifact_labels == {
        "preflight",
        "accuracy_gate",
        "requirements_lock",
        "environment_manifest",
        "engine_provenance",
        "commercialization_queue",
        "nightly_gate",
        "wetlab_selected_allatom",
        "current_results_index",
        "partnering_stack",
        "rescue_attempt_validation",
        "status_report_md",
    }

    assert (bundle_dir / "commercialization_status_report.md").exists()
    assert (bundle_dir / "runs" / "local_delivery_preflight_current.json").exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "accuracy_gate"
        / "accuracy_gate_local_delivery_preflight_current.json"
    ).exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "nightly_gate"
        / "nightly_gate_burndown_packet_current.json"
    ).exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "wetlab_selected_allatom"
        / "wetlab_selected_allatom_gate_burndown_packet_current.json"
    ).exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "current_results_index"
        / "wetlab_current_results_index_current.json"
    ).exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "partnering_stack"
        / "wetlab_partnering_stack_current.json"
    ).exists()
    assert (
        bundle_dir
        / "artifacts"
        / "verdict_gate_source_artifacts"
        / "rescue_attempt_validation"
        / "wetlab_tcruzi_pde_allatom_rescue_attempt_validation_current.json"
    ).exists()
    assert (bundle_dir / "environment" / "environment_manifest.json").exists()
    assert (bundle_dir / "environment" / "requirements_lock.txt").exists()
    assert (bundle_dir / "environment" / "engine_provenance.json").exists()
    assert (bundle_dir / "runs" / "local_delivery_verdict_gate_current.json").exists()
    assert (bundle_dir / "config" / "delivery.yaml").exists()
    assert (bundle_dir / "artifacts" / "prediction.json").exists()

    assert "manifest.json" in checksums
    assert "bundle.zip" in checksums
    assert (bundle_dir / "manifest.md").read_text(encoding="utf-8").startswith("# Local Delivery Bundle")


def test_delivery_ready_verdict_succeeds_when_verdict_gate_green(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)

    args = _parse_args(["--bundle-tag", "green_gate_bundle", "--no-build-archive"])

    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_green_gate_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_md = (bundle_dir / "manifest.md").read_text(encoding="utf-8")
    assert payload["bundle_dir"] == str(bundle_dir.resolve())
    assert manifest["verdict"] == "Delivery-ready only for the attached restricted local-delivery scope."
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    assert manifest["verdict_gate_fingerprint_check"]["checked"] is True
    assert manifest["verdict_gate_fingerprint_check"]["ok"] is True
    assert manifest["verdict_gate_fingerprint_check"]["status"] == "pass"
    assert manifest["verdict_gate_fingerprint_check"]["comparison_performed"] is True
    assert manifest["verdict_gate_fingerprint_check"]["required_for_delivery_ready_verdict"] is True
    assert manifest["verdict_gate_fingerprint_check"]["reason"] == "fingerprints_match"
    assert manifest["verdict_gate_fingerprint_check"]["matched_count"] > 0
    assert manifest["verdict_gate_fingerprint_check"]["matched_count"] == 12
    assert manifest["verdict_gate_fingerprint_check"]["mismatch_count"] == 0
    assert manifest["verdict_gate_fingerprint_check"]["mismatches"] == []
    assert (
        manifest["verdict_gate_fingerprint_check"]["compared_label_count"]
        == manifest["verdict_gate_fingerprint_check"]["persisted_label_count"]
    )
    assert (
        manifest["verdict_gate_fingerprint_check"]["persisted_label_count"]
        == manifest["verdict_gate_fingerprint_check"]["fresh_label_count"]
    )
    assert manifest["verdict_gate_fingerprint_check"]["persisted_label_count"] == 12
    assert {
        row["label"] for row in manifest["local_delivery_verdict_gate"]["source_artifacts"]
    } == {
        "preflight",
        "accuracy_gate",
        "requirements_lock",
        "environment_manifest",
        "engine_provenance",
        "commercialization_queue",
        "nightly_gate",
        "wetlab_selected_allatom",
        "current_results_index",
        "partnering_stack",
        "rescue_attempt_validation",
        "status_report_md",
    }
    included_by_spec_key = {row["spec_key"]: row for row in manifest["included_files"]}
    assert included_by_spec_key["verdict_gate_source_artifact_current_results_index"]["bundle_path"] == (
        "artifacts/verdict_gate_source_artifacts/current_results_index/wetlab_current_results_index_current.json"
    )
    assert included_by_spec_key["verdict_gate_source_artifact_partnering_stack"]["bundle_path"] == (
        "artifacts/verdict_gate_source_artifacts/partnering_stack/wetlab_partnering_stack_current.json"
    )
    assert "- fingerprint_check_status: `pass`" in manifest_md
    assert "- fingerprint_check_ok: `True`" in manifest_md
    assert "- fingerprint_check_mismatch_count: `0`" in manifest_md


def test_delivery_ready_verdict_uses_explicit_new_source_artifact_paths_for_fresh_check(
    tmp_path, monkeypatch
):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    custom_index = tmp_path / "custom_sources" / "current_results_index.json"
    custom_stack = tmp_path / "custom_sources" / "partnering_stack.json"
    _write_json(
        custom_index,
        {
            "summary": {
                "status": "wetlab_current_results_index_ready",
                "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                "partnering_stack_artifact_complete": True,
            }
        },
    )
    _write_json(
        custom_stack,
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
    )
    paths["current_results_index_json"] = custom_index
    paths["partnering_stack_json"] = custom_stack
    _write_verdict_gate(paths, delivery_ready=True)

    args = _parse_args(
        [
            "--bundle-tag",
            "custom_new_source_artifacts",
            "--current-results-index-json",
            str(custom_index),
            "--partnering-stack-json",
            str(custom_stack),
            "--no-build-archive",
        ]
    )

    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_custom_new_source_artifacts"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    source_rows = {
        row["logical_name"]: row
        for row in manifest["included_files"]
        if row["category"] == "verdict_gate_source_artifact"
    }
    assert manifest["verdict_gate_fingerprint_check"]["status"] == "pass"
    assert manifest["verdict_gate_fingerprint_check"]["persisted_label_count"] == 12
    assert source_rows["current_results_index"]["bundle_path"] == (
        "artifacts/verdict_gate_source_artifacts/current_results_index/current_results_index.json"
    )
    assert source_rows["partnering_stack"]["bundle_path"] == (
        "artifacts/verdict_gate_source_artifacts/partnering_stack/partnering_stack.json"
    )
    assert (
        bundle_dir / "artifacts" / "verdict_gate_source_artifacts" / "current_results_index" / "current_results_index.json"
    ).exists()
    assert (
        bundle_dir / "artifacts" / "verdict_gate_source_artifacts" / "partnering_stack" / "partnering_stack.json"
    ).exists()


def test_delivery_ready_verdict_fails_when_verdict_gate_blocked(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=False)

    args = _parse_args(["--bundle-tag", "blocked_gate_ready_claim", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert "delivery_ready=false" in message


def test_delivery_ready_verdict_fails_when_verdict_gate_markdown_missing(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)
    paths["verdict_gate_md"].unlink()

    args = _parse_args(["--bundle-tag", "missing_gate_md_ready_claim", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert "md_missing" in message


def test_delivery_ready_verdict_fails_when_current_p0_artifacts_are_red(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)
    _write_json(
        tmp_path / "runs" / "nightly_gate_burndown_packet_current.json",
        {"summary": {"stage6_gate_failed": True, "primary_gate_value": 2.7, "primary_gate_threshold": 2.5}},
    )

    args = _parse_args(["--bundle-tag", "stale_true_gate_ready_claim", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert "fresh_recheck" in message
    assert "delivery_ready=false" in message


def test_delivery_ready_verdict_fails_when_persisted_gate_fingerprint_is_stale(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)
    _write_json(
        paths["preflight_json"],
        {
            "summary": {
                "overall_ok": True,
                "dry_run": False,
                "next_required_step": "Proceed after a fresh but changed preflight record.",
            }
        },
    )

    args = _parse_args(["--bundle-tag", "stale_fingerprint_ready_claim", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert "fingerprint_mismatch" in message


@pytest.mark.parametrize(
    ("path_key", "expected_label"),
    [
        ("current_results_index_json", "current_results_index"),
        ("partnering_stack_json", "partnering_stack"),
    ],
)
def test_delivery_ready_verdict_fails_when_new_source_artifact_fingerprint_is_stale(
    tmp_path, monkeypatch, path_key, expected_label
):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)
    if path_key == "current_results_index_json":
        _write_json(
            paths[path_key],
            {
                "summary": {
                    "status": "wetlab_current_results_index_ready",
                    "partnering_stack_artifact_status": "wetlab_partnering_stack_ready",
                    "partnering_stack_artifact_complete": True,
                    "fresh_marker": "changed-after-persisted-gate",
                }
            },
        )
    else:
        _write_json(
            paths[path_key],
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
                    "fresh_marker": "changed-after-persisted-gate",
                }
            },
        )

    args = _parse_args(["--bundle-tag", f"stale_{expected_label}_ready_claim", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert f"fingerprint_mismatch:{expected_label}" in message


def test_delivery_ready_with_review_only_caveat_still_requires_green_gate(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=False)

    args = _parse_args(
        [
            "--bundle-tag",
            "ready_claim_with_review_only_caveat",
            "--verdict",
            "Delivery-ready for guarded local validation; transporter remains review-only.",
            "--no-build-archive",
        ]
    )

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert "delivery_ready=false" in message


@pytest.mark.parametrize(
    ("gate_payload", "expected_message"),
    [
        (None, "missing"),
        ("not json", "invalid_json"),
        ({"status": "no summary"}, "summary_missing_or_invalid"),
        ({"summary": {"delivery_ready": True}}, "source_artifacts_missing"),
    ],
)
def test_delivery_ready_verdict_fails_when_verdict_gate_missing_or_invalid(
    tmp_path, monkeypatch, gate_payload, expected_message
):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    if gate_payload is None:
        paths["verdict_gate_json"].unlink()
    elif isinstance(gate_payload, str):
        _write_text(paths["verdict_gate_json"], gate_payload)
    else:
        _write_json(paths["verdict_gate_json"], gate_payload)

    args = _parse_args(["--bundle-tag", f"bad_gate_{expected_message}", "--no-build-archive"])

    with pytest.raises(SystemExit) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "local_delivery_verdict_gate" in message
    assert expected_message in message


def test_negative_verdict_succeeds_when_verdict_gate_blocked(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=False)

    args = _parse_args(
        [
            "--bundle-tag",
            "blocked_gate_negative_verdict",
            "--verdict",
            "Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
            "--no-build-archive",
        ]
    )

    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_blocked_gate_negative_verdict"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    check = manifest["verdict_gate_fingerprint_check"]
    assert payload["bundle_dir"] == str(bundle_dir.resolve())
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is False
    assert check["required_for_delivery_ready_verdict"] is False
    assert manifest["verdict"].startswith("Blocked internal-review bundle only")


def test_negative_verdict_records_stale_verdict_gate_fingerprint_without_blocking(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    paths = _write_canonical_inputs(tmp_path)
    _write_verdict_gate(paths, delivery_ready=True)
    _write_json(
        paths["preflight_json"],
        {
            "summary": {
                "overall_ok": True,
                "dry_run": False,
                "next_required_step": "Proceed after a fresh but changed preflight record.",
            }
        },
    )

    args = _parse_args(
        [
            "--bundle-tag",
            "stale_fingerprint_negative_verdict",
            "--verdict",
            "Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
            "--no-build-archive",
        ]
    )

    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_stale_fingerprint_negative_verdict"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_md = (bundle_dir / "manifest.md").read_text(encoding="utf-8")
    check = manifest["verdict_gate_fingerprint_check"]
    assert payload["bundle_dir"] == str(bundle_dir.resolve())
    assert check["checked"] is True
    assert check["ok"] is False
    assert check["status"] == "mismatch"
    assert check["comparison_performed"] is True
    assert check["required_for_delivery_ready_verdict"] is False
    assert "fingerprint_mismatch" in check["reason"]
    assert check["matched_count"] > 0
    assert check["mismatch_count"] == len(check["mismatches"])
    assert check["mismatch_count"] > 0
    assert check["persisted_label_count"] == check["fresh_label_count"]
    assert check["mismatches"]
    assert "- fingerprint_check_status: `mismatch`" in manifest_md
    assert "- fingerprint_check_ok: `False`" in manifest_md
    assert "- fingerprint_check_mismatch_count: `" in manifest_md
    assert "fingerprint_mismatch" in manifest_md


def test_builder_copies_passing_family_scorecard_into_manifest(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    scorecard = tmp_path / "scorecards" / "kinase_scorecard.json"
    _write_family_scorecard(scorecard)

    args = _parse_args(
        [
            "--bundle-tag",
            "scorecard_pass",
            "--family-scorecard-json",
            str(scorecard),
            "--no-build-archive",
        ]
    )

    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_scorecard_pass"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_md = (bundle_dir / "manifest.md").read_text(encoding="utf-8")
    copied = bundle_dir / "artifacts" / "family_scorecards" / "kinase_scorecard.json"

    assert copied.exists()
    assert manifest["family_scorecards"] == [
        {
            "source_path": str(scorecard.resolve()),
            "bundle_path": "artifacts/family_scorecards/kinase_scorecard.json",
            "present": True,
            "sha256": b._sha256_file(copied),
            "summary": {
                "family": "kinase",
                "scorecard_level_status": "pass",
                "acceptance_overall_pass": True,
            },
        }
    ]
    assert "- family_scorecard_count: `1`" in manifest_md
    assert "- family_scorecard_blocked_count: `0`" in manifest_md


def test_delivery_ready_verdict_fails_with_blocked_family_scorecard(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    scorecard = tmp_path / "scorecards" / "kinase_scorecard.json"
    _write_family_scorecard(scorecard, status="blocked", acceptance_pass=False)

    args = _parse_args(
        [
            "--bundle-tag",
            "scorecard_blocked_ready",
            "--family-scorecard-json",
            str(scorecard),
            "--no-build-archive",
        ]
    )

    with pytest.raises(ValueError) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "family_scorecard blocks delivery-ready bundle verdict" in message
    assert "scorecard_level_status='blocked'" in message


def test_delivery_ready_verdict_fails_when_family_scorecard_acceptance_fails(
    tmp_path, monkeypatch
):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    scorecard = tmp_path / "scorecards" / "kinase_scorecard.json"
    _write_family_scorecard(scorecard, status="pass", acceptance_pass=False)

    args = _parse_args(
        [
            "--bundle-tag",
            "scorecard_acceptance_failed_ready",
            "--family-scorecard-json",
            str(scorecard),
            "--no-build-archive",
        ]
    )

    with pytest.raises(ValueError) as excinfo:
        b.build_bundle(args)

    message = str(excinfo.value)
    assert "family_scorecard blocks delivery-ready bundle verdict" in message
    assert "acceptance_overall_pass=False" in message


def test_internal_review_verdict_records_blocked_family_scorecard(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    scorecard = tmp_path / "scorecards" / "kinase_scorecard.json"
    _write_family_scorecard(scorecard, status="blocked", acceptance_pass=False)

    args = _parse_args(
        [
            "--bundle-tag",
            "scorecard_blocked_internal",
            "--verdict",
            "Blocked internal-review bundle only; not delivery-ready for the restricted local-delivery scope.",
            "--family-scorecard-json",
            str(scorecard),
            "--no-build-archive",
        ]
    )

    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_scorecard_blocked_internal"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_md = (bundle_dir / "manifest.md").read_text(encoding="utf-8")

    assert manifest["family_scorecards"][0]["present"] is True
    assert manifest["family_scorecards"][0]["summary"]["scorecard_level_status"] == "blocked"
    assert manifest["family_scorecards"][0]["summary"]["acceptance_overall_pass"] is False
    assert "- family_scorecard_blocked_count: `1`" in manifest_md


def test_build_local_delivery_bundle_override_and_missing_file_recorded(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    canonical = _write_canonical_inputs(tmp_path, include_queue_csv=False)

    override_report = tmp_path / "custom_status_report.md"
    config_path = tmp_path / "profiles" / "delivery.yaml"
    artifact_path = tmp_path / "results" / "prediction.json"
    _write_text(canonical["status_report"], "# default report\n")
    _write_text(override_report, "# override report\n")
    _write_text(config_path, "family: gpcr\n")
    _write_json(artifact_path, {"score": 0.77})
    canonical["status_report"] = override_report
    _write_verdict_gate(canonical, delivery_ready=True)

    args = _parse_args(
        [
            "--bundle-tag",
            "override_bundle",
            "--status-report-md",
            str(override_report),
            "--config-path",
            str(config_path),
            "--artifact-path",
            str(artifact_path),
        ]
    )

    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_override_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    copied_report = (bundle_dir / "commercialization_status_report.md").read_text(encoding="utf-8")

    assert payload["included_count"] == 23
    assert payload["missing_count"] == 1
    assert copied_report == "# override report\n"
    assert manifest["queue"]["artifacts"]["csv"]["present"] is False

    missing_rows = manifest["missing_files"]
    assert missing_rows == [
        {
            "spec_key": "queue_csv",
            "name": "local_engine_commercialization_queue_csv",
            "logical_name": "local_engine_commercialization_queue_csv",
            "category": "queue",
            "required": False,
            "requested_path": str((tmp_path / "runs" / "local_engine_commercialization_queue_current.csv").resolve()),
            "source_path": str((tmp_path / "runs" / "local_engine_commercialization_queue_current.csv").resolve()),
            "bundle_path": "runs/local_engine_commercialization_queue_current.csv",
            "reason": "source_missing",
        }
    ]


def _write_hbond_report(path: Path) -> None:
    _write_json(
        path,
        {
            "report_version": "hbond_backmap_report_v1",
            "status": "hbond_backmap_report_ready",
            "summary": {
                "report_version": "hbond_backmap_report_v1",
                "candidate_count": 64,
                "claim_safe_count": 62,
                "evidence_only_count": 2,
                "claim_safe_rate": 0.96875,
                "total_donor_sites": 76,
                "total_acceptor_sites": 131,
                "evidence_only_reason_counts": {"no_hbond_sites": 2},
            },
            "rows": [],
        },
    )


def test_hbond_backmap_report_present_is_additive_evidence(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    report_json = tmp_path / "runs" / "hbond_backmap_report_current.json"
    _write_hbond_report(report_json)

    args = _parse_args(
        [
            "--bundle-tag",
            "hbond_present_bundle",
            "--no-build-archive",
            "--hbond-backmap-report-json",
            str(report_json),
            "--hbond-backmap-report-md",
            str(tmp_path / "runs" / "hbond_backmap_report_current.md"),
            "--hbond-backmap-report-csv",
            str(tmp_path / "runs" / "hbond_backmap_report_current.csv"),
        ]
    )
    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_hbond_present_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["hbond_backmap_report"]

    # Additive evidence must not perturb the delivery gate.
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True

    assert section["artifact_id"] == "hbond_backmap_report"
    assert section["artifact_type"] == "interpretability_evidence"
    assert section["present"] is True
    assert section["required_for_delivery_ready"] is False
    assert section["execution_enabled"] is False
    assert section["external_state_mutated"] is False
    assert section["kpi"]["hbond_backmap_report_present"] is True
    assert section["kpi"]["hbond_backmap_candidate_count"] == 64
    assert section["kpi"]["hbond_backmap_claim_safe_count"] == 62
    assert section["kpi"]["hbond_backmap_evidence_only_count"] == 2
    assert section["kpi"]["hbond_backmap_claim_safe_rate"] == 0.96875
    assert section["kpi"]["hbond_backmap_total_donor_sites"] == 76
    assert section["kpi"]["hbond_backmap_total_acceptor_sites"] == 131


def test_hbond_backmap_report_missing_does_not_break_delivery(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    missing_report = tmp_path / "runs" / "hbond_backmap_report_current.json"

    args = _parse_args(
        [
            "--bundle-tag",
            "hbond_missing_bundle",
            "--no-build-archive",
            "--hbond-backmap-report-json",
            str(missing_report),
        ]
    )
    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_hbond_missing_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["hbond_backmap_report"]

    # Delivery readiness is unaffected by a missing additive H-Bond report.
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True

    assert section["present"] is False
    assert section["reason"] == "missing"
    assert section["warning"] == "hbond_backmap_report_missing"
    assert section["required_for_delivery_ready"] is False
    assert section["kpi"]["hbond_backmap_report_present"] is False
    assert section["kpi"]["hbond_backmap_claim_safe_rate"] == 0.0
    assert section["kpi"]["hbond_backmap_candidate_count"] == 0


def test_hbond_backmap_report_invalid_json_is_fail_closed(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    bad_report = tmp_path / "runs" / "hbond_backmap_report_current.json"
    _write_text(bad_report, "{ this is not valid json")

    args = _parse_args(
        [
            "--bundle-tag",
            "hbond_invalid_bundle",
            "--no-build-archive",
            "--hbond-backmap-report-json",
            str(bad_report),
        ]
    )
    payload = b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_hbond_invalid_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["hbond_backmap_report"]

    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    assert section["present"] is False
    assert section["reason"] == "invalid_json"
    assert section["warning"] == "hbond_backmap_report_invalid_json"
    # No positive claim may be fabricated from an invalid artifact.
    assert section["kpi"]["hbond_backmap_report_present"] is False
    assert section["kpi"]["hbond_backmap_claim_safe_rate"] == 0.0
    assert section["kpi"]["hbond_backmap_claim_safe_count"] == 0


def test_hbond_backmap_report_claim_boundary_preserved(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    report_json = tmp_path / "runs" / "hbond_backmap_report_current.json"
    _write_hbond_report(report_json)

    args = _parse_args(
        [
            "--bundle-tag",
            "hbond_boundary_bundle",
            "--no-build-archive",
            "--hbond-backmap-report-json",
            str(report_json),
        ]
    )
    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_hbond_boundary_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    boundary = manifest["hbond_backmap_report"]["claim_boundary"]

    assert "local interpretability evidence" in boundary
    assert "not a docking-accuracy or binding-affinity claim" in boundary


def _write_gpcr_hard_decoy_report(path: Path, *, family_claim_safe: bool = False) -> None:
    _write_json(
        path,
        {
            "packet_type": "gpcr_hard_decoy_suite_report",
            "schema_version": "gpcr_hard_decoy_suite_report_v1",
            "materializer_status": "materialized",
            "summary": {
                "schema_version": "gpcr_hard_decoy_suite_v1",
                "status": "gpcr_hard_decoy_family_ready" if family_claim_safe else "broad_family_locked",
                "family_claim_safe": family_claim_safe,
                "required_target_ids": ["DRD2", "HTR2A", "OPRM1"],
                "target_count": 3,
                "green_target_ids": ["HTR2A"],
                "blocked_target_ids": ["DRD2", "OPRM1"],
                "missing_required_target_ids": [],
                "first_blocked_required_target": "DRD2",
                "gate": {"ci_low_min": 0.45, "top20_min": 0.2},
            },
            "targets": [
                {"target_id": "DRD2", "gate_status": "blocked"},
                {"target_id": "HTR2A", "gate_status": "green"},
                {"target_id": "OPRM1", "gate_status": "blocked"},
            ],
        },
    )


def test_gpcr_hard_decoy_suite_present_is_additive_gate_evidence(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    report_json = tmp_path / "runs" / "gpcr_hard_decoy_suite_current.json"
    _write_gpcr_hard_decoy_report(report_json)

    args = _parse_args(
        [
            "--bundle-tag",
            "gpcr_present_bundle",
            "--no-build-archive",
            "--gpcr-hard-decoy-suite-json",
            str(report_json),
            "--gpcr-hard-decoy-suite-md",
            str(tmp_path / "runs" / "gpcr_hard_decoy_suite_current.md"),
            "--gpcr-hard-decoy-suite-csv",
            str(tmp_path / "runs" / "gpcr_hard_decoy_suite_current.csv"),
        ]
    )
    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_gpcr_present_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["gpcr_hard_decoy_suite"]

    # Additive gate evidence must not change the delivery-ready verdict.
    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    assert section["artifact_id"] == "gpcr_hard_decoy_suite_report"
    assert section["artifact_type"] == "broad_gpcr_gate_evidence"
    assert section["present"] is True
    assert section["required_for_delivery_ready"] is False
    assert section["execution_enabled"] is False
    assert section["external_state_mutated"] is False
    assert section["kpi"]["gpcr_hard_decoy_report_present"] is True
    assert section["kpi"]["gpcr_hard_decoy_family_claim_safe"] is False
    assert section["kpi"]["gpcr_hard_decoy_status"] == "broad_family_locked"
    assert section["kpi"]["gpcr_hard_decoy_target_count"] == 3
    assert section["kpi"]["gpcr_hard_decoy_green_target_count"] == 1
    assert section["kpi"]["gpcr_hard_decoy_blocked_target_count"] == 2
    assert section["kpi"]["gpcr_hard_decoy_missing_required_target_count"] == 0
    assert section["kpi"]["gpcr_hard_decoy_first_blocked_required_target"] == "DRD2"


def test_gpcr_hard_decoy_suite_missing_does_not_break_delivery(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    missing_report = tmp_path / "runs" / "gpcr_hard_decoy_suite_current.json"

    args = _parse_args(
        [
            "--bundle-tag",
            "gpcr_missing_bundle",
            "--no-build-archive",
            "--gpcr-hard-decoy-suite-json",
            str(missing_report),
        ]
    )
    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_gpcr_missing_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["gpcr_hard_decoy_suite"]

    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    assert section["present"] is False
    assert section["reason"] == "missing"
    assert section["warning"] == "gpcr_hard_decoy_suite_report_missing"
    assert section["required_for_delivery_ready"] is False
    assert section["kpi"]["gpcr_hard_decoy_report_present"] is False
    assert section["kpi"]["gpcr_hard_decoy_family_claim_safe"] is False
    assert section["kpi"]["gpcr_hard_decoy_target_count"] == 0


def test_gpcr_hard_decoy_suite_invalid_json_is_fail_closed(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    bad_report = tmp_path / "runs" / "gpcr_hard_decoy_suite_current.json"
    _write_text(bad_report, "{ broken json")

    args = _parse_args(
        [
            "--bundle-tag",
            "gpcr_invalid_bundle",
            "--no-build-archive",
            "--gpcr-hard-decoy-suite-json",
            str(bad_report),
        ]
    )
    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_gpcr_invalid_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section = manifest["gpcr_hard_decoy_suite"]

    assert manifest["local_delivery_verdict_gate"]["summary"]["delivery_ready"] is True
    assert section["present"] is False
    assert section["reason"] == "invalid_json"
    assert section["warning"] == "gpcr_hard_decoy_suite_report_invalid_json"
    # No broad-GPCR claim may be fabricated from an invalid artifact.
    assert section["kpi"]["gpcr_hard_decoy_family_claim_safe"] is False
    assert section["kpi"]["gpcr_hard_decoy_report_present"] is False


def test_gpcr_hard_decoy_suite_claim_boundary_preserved(tmp_path, monkeypatch):
    _patch_workspace(monkeypatch, tmp_path)
    _write_canonical_inputs(tmp_path)
    report_json = tmp_path / "runs" / "gpcr_hard_decoy_suite_current.json"
    _write_gpcr_hard_decoy_report(report_json)

    args = _parse_args(
        [
            "--bundle-tag",
            "gpcr_boundary_bundle",
            "--no-build-archive",
            "--gpcr-hard-decoy-suite-json",
            str(report_json),
        ]
    )
    b.build_bundle(args)

    bundle_dir = tmp_path / "runs" / "local_delivery" / "bundle_gpcr_boundary_bundle"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    boundary = manifest["gpcr_hard_decoy_suite"]["claim_boundary"]

    assert "does not run scoring" in boundary
    assert "promote broad-GPCR claims" in boundary
