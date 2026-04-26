from __future__ import annotations

import json
import sys
import time

import pytest

from tools import run_local_delivery_preflight as preflight


def test_build_run_plan_uses_standardized_outputs(monkeypatch) -> None:
    monkeypatch.delenv("TORCH_BLAS_PREFER_HIPBLASLT", raising=False)
    args = preflight.build_parser().parse_args([])
    plan = preflight.build_run_plan(args)

    assert [step["label"] for step in plan] == [
        "accuracy_gate",
        "local_ci",
        "requirements_lock",
        "environment_manifest",
        "engine_provenance",
        "family_refresh",
        "engine_queue",
        "commercialization_report",
        "verdict_gate",
    ]
    accuracy_cmd = plan[0]["cmd"]
    assert accuracy_cmd[:2] == [sys.executable, str(preflight.ROOT / "tools" / "run_preflight_gate.py")]
    assert accuracy_cmd[-2:] == ["--label", "local_delivery_preflight_current"]
    requirements_cmd = plan[2]["cmd"]
    assert requirements_cmd[:2] == [
        sys.executable,
        str(preflight.ROOT / "tools" / "build_local_delivery_requirements_lock.py"),
    ]
    assert "--out-txt" in requirements_cmd
    environment_cmd = plan[3]["cmd"]
    assert environment_cmd[:2] == [
        sys.executable,
        str(preflight.ROOT / "tools" / "build_local_delivery_environment_manifest.py"),
    ]
    assert environment_cmd[environment_cmd.index("--manifest-label") + 1] == "local_delivery_preflight_current"
    assert environment_cmd[environment_cmd.index("--requirements-lock-json") + 1] == str(
        preflight.DEFAULT_REQUIREMENTS_LOCK_OUT_JSON
    )
    assert plan[3]["env"] == {"TORCH_BLAS_PREFER_HIPBLASLT": "0"}
    assert str(preflight.DEFAULT_ENVIRONMENT_OUT_JSON) in plan[3]["expected_artifacts"]
    engine_provenance_cmd = plan[4]["cmd"]
    assert engine_provenance_cmd[:2] == [
        sys.executable,
        str(preflight.ROOT / "tools" / "build_local_delivery_engine_provenance.py"),
    ]
    assert engine_provenance_cmd[engine_provenance_cmd.index("--out-json") + 1] == str(
        preflight.DEFAULT_ENGINE_PROVENANCE_OUT_JSON
    )
    verdict_cmd = plan[-1]["cmd"]
    report_cmd = plan[-2]["cmd"]
    assert "--local-engine-queue-json" in report_cmd
    assert report_cmd[report_cmd.index("--local-engine-queue-json") + 1] == str(preflight.DEFAULT_QUEUE_OUT_JSON)
    assert verdict_cmd[:2] == [
        sys.executable,
        str(preflight.ROOT / "tools" / "build_local_delivery_verdict_gate.py"),
    ]
    assert verdict_cmd[verdict_cmd.index("--preflight-json") + 1] == str(preflight.DEFAULT_OUT_JSON)


def test_build_run_plan_preserves_explicit_hipblaslt_override(monkeypatch) -> None:
    monkeypatch.setenv("TORCH_BLAS_PREFER_HIPBLASLT", "1")
    args = preflight.build_parser().parse_args([])
    plan = preflight.build_run_plan(args)
    environment_step = next(step for step in plan if step["label"] == "environment_manifest")

    assert environment_step["env"] == {"TORCH_BLAS_PREFER_HIPBLASLT": "1"}


def test_local_delivery_preflight_dry_run_writes_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TORCH_BLAS_PREFER_HIPBLASLT", raising=False)
    out_json = tmp_path / "local_delivery_preflight.json"
    out_md = tmp_path / "local_delivery_preflight.md"
    local_ci_json = tmp_path / "local_ci.json"
    requirements_json = tmp_path / "requirements_lock.json"
    requirements_md = tmp_path / "requirements_lock.md"
    requirements_txt = tmp_path / "requirements_lock.txt"
    engine_provenance_json = tmp_path / "engine_provenance.json"
    engine_provenance_md = tmp_path / "engine_provenance.md"
    environment_json = tmp_path / "environment.json"
    environment_md = tmp_path / "environment.md"
    queue_json = tmp_path / "queue.json"
    queue_md = tmp_path / "queue.md"
    report_md = tmp_path / "report.md"
    verdict_json = tmp_path / "verdict_gate.json"
    verdict_md = tmp_path / "verdict_gate.md"

    preflight.main(
        [
            "--dry-run",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--local-ci-out-json",
            str(local_ci_json),
            "--requirements-lock-out-json",
            str(requirements_json),
            "--requirements-lock-out-md",
            str(requirements_md),
            "--requirements-lock-out-txt",
            str(requirements_txt),
            "--engine-provenance-out-json",
            str(engine_provenance_json),
            "--engine-provenance-out-md",
            str(engine_provenance_md),
            "--environment-out-json",
            str(environment_json),
            "--environment-out-md",
            str(environment_md),
            "--queue-out-json",
            str(queue_json),
            "--queue-out-md",
            str(queue_md),
            "--report-out-md",
            str(report_md),
            "--verdict-gate-out-json",
            str(verdict_json),
            "--verdict-gate-out-md",
            str(verdict_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is True
    assert payload["summary"]["dry_run"] is True
    assert payload["summary"]["step_count"] == 9
    assert payload["summary"]["accuracy_gate_artifact"] == "runs/accuracy_gate_local_delivery_preflight_current.json"
    assert payload["summary"]["accuracy_gate_check"]["status"] == "dry_run"
    assert payload["summary"]["requirements_lock_json"] == str(requirements_json)
    assert payload["summary"]["requirements_lock_md"] == str(requirements_md)
    assert payload["summary"]["requirements_lock_txt"] == str(requirements_txt)
    assert payload["summary"]["requirements_lock_check"]["status"] == "dry_run"
    assert payload["summary"]["engine_provenance_json"] == str(engine_provenance_json)
    assert payload["summary"]["engine_provenance_md"] == str(engine_provenance_md)
    assert payload["summary"]["engine_provenance_ok"] is None
    assert payload["summary"]["environment_manifest_json"] == str(environment_json)
    assert payload["summary"]["environment_manifest_md"] == str(environment_md)
    assert payload["summary"]["verdict_gate_json"] == str(verdict_json)
    assert payload["summary"]["verdict_gate_md"] == str(verdict_md)
    assert payload["summary"]["verdict_gate_delivery_ready"] is None
    assert payload["summary"]["verdict_gate_required_ok"] is True
    assert payload["summary"]["verdict_gate_fingerprint_check"]["status"] == "pending_bundle_check"
    assert payload["summary"]["verdict_gate_fingerprint_check"]["comparison_performed"] is False
    assert payload["summary"]["verdict_gate_fingerprint_check"]["required_for_delivery_ready_verdict"] is True
    assert payload["steps"][3]["env"] == {"TORCH_BLAS_PREFER_HIPBLASLT": "0"}
    assert payload["summary"]["expected_artifact_count"] == 0
    assert "dry run only" in payload["summary"]["next_required_step"].lower()
    assert out_md.exists()
    markdown = out_md.read_text(encoding="utf-8")
    assert "verdict_gate_fingerprint_check_status" in markdown
    assert "pending_bundle_check" in markdown


def test_local_delivery_preflight_fails_on_incomplete_requirements_lock(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    requirements_json = tmp_path / "requirements_lock.json"
    requirements_json.write_text(
        json.dumps(
            {
                "summary": {
                    "missing_count": 1,
                    "loose_source_requirement_count": 1,
                    "missing_input_file_count": 0,
                    "unpinned_count": 1,
                    "status_line": "incomplete: installed=1/2 missing=1 loose_sources=1 missing_files=0",
                    "missing_package_install_targets": ["fastapi"],
                    "loose_source_requirements": ["./local-package"],
                    "unpinned_pin_suggestions": [
                        {
                            "current_requirement": "numpy",
                            "installed_version": "2.1.0",
                            "suggested_requirement": "numpy==2.1.0",
                            "source": "requirements.txt:1",
                        }
                    ],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        if label == "accuracy_gate":
            (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "accuracy_gate_local_delivery_preflight_current.json").write_text(
                json.dumps({"summary": {"pass": True, "failed_metrics": []}}),
                encoding="utf-8",
            )
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 0,
            "ok": True,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"
    out_md = tmp_path / "local_delivery_preflight.md"

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(
            [
                "--skip-verdict-gate",
                "--requirements-lock-out-json",
                str(requirements_json),
                "--out-json",
                str(out_json),
                "--out-md",
                str(out_md),
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is False
    assert payload["summary"]["first_failed_step"] == "requirements_lock_completeness"
    assert payload["summary"]["requirements_lock_check"]["missing_package_install_targets"] == ["fastapi"]
    assert payload["summary"]["requirements_lock_check"]["loose_source_requirements"] == ["./local-package"]
    assert "fastapi" in payload["summary"]["next_required_step"]
    markdown = out_md.read_text(encoding="utf-8")
    assert "numpy==2.1.0" in markdown


def test_requirements_lock_summary_allows_optional_deferred_missing(tmp_path) -> None:
    requirements_json = tmp_path / "requirements_lock.json"
    requirements_json.write_text(
        json.dumps(
            {
                "summary": {
                    "requirements_lock_complete": True,
                    "missing_count": 0,
                    "loose_source_requirement_count": 0,
                    "missing_input_file_count": 0,
                    "optional_missing_count": 2,
                    "optional_deferred_install_targets": ["fastapi", "GPUtil"],
                    "optional_profiles": {
                        "api": {
                            "missing_count": 1,
                            "missing_package_install_targets": ["fastapi"],
                            "delivery_blocking": False,
                        }
                    },
                    "status_line": "complete_with_unpinned_inputs: lock_lines=1 unpinned_inputs=1",
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    check = preflight._requirements_lock_summary(requirements_json)

    assert check["complete"] is True
    assert check["action_required"] is False
    assert check["optional_missing_count"] == 2
    assert check["optional_deferred_install_targets"] == ["fastapi", "GPUtil"]
    assert check["missing_package_install_targets"] == []


def test_local_delivery_preflight_exposes_accuracy_gate_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        failed = label == "accuracy_gate"
        if label == "accuracy_gate":
            (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "accuracy_gate_local_delivery_preflight_current.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "pass": False,
                            "failed_targets": ["gpcr"],
                            "failed_metrics": [
                                {
                                    "scope": "performance",
                                    "target": "gpcr",
                                    "metric": "speedup_on_vs_off",
                                    "value": 7.2,
                                    "threshold": 10.0,
                                    "operator": ">=",
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 2 if failed else 0,
            "ok": not failed,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "accuracy failed" if failed else "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"
    out_md = tmp_path / "local_delivery_preflight.md"

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(["--out-json", str(out_json), "--out-md", str(out_md)])

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    check = payload["summary"]["accuracy_gate_check"]
    assert payload["summary"]["overall_ok"] is False
    assert payload["summary"]["first_failed_step"] == "accuracy_gate"
    assert check["status"] == "fail"
    assert check["failed_metric_count"] == 1
    assert check["primary_failed_metric"]["metric"] == "speedup_on_vs_off"
    assert "speedup_on_vs_off" in check["reason"]
    markdown = out_md.read_text(encoding="utf-8")
    assert "accuracy_gate_check_status" in markdown
    assert "speedup_on_vs_off" in markdown


def test_local_delivery_preflight_records_first_failed_step(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    calls: list[str] = []

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        calls.append(label)
        if label == "accuracy_gate":
            (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "accuracy_gate_local_delivery_preflight_current.json").write_text(
                json.dumps({"summary": {"pass": True, "failed_metrics": []}}),
                encoding="utf-8",
            )
        if label == "verdict_gate":
            assert out_json.exists()
        failed = label == "local_ci"
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 2 if failed else 0,
            "ok": not failed,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "boom" if failed else "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(
            [
                "--out-json",
                str(out_json),
                "--out-md",
                str(tmp_path / "local_delivery_preflight.md"),
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is False
    assert payload["summary"]["first_failed_step"] == "local_ci"
    assert calls == [
        "accuracy_gate",
        "local_ci",
        "requirements_lock",
        "environment_manifest",
        "engine_provenance",
        "family_refresh",
        "engine_queue",
        "commercialization_report",
        "verdict_gate",
    ]


def test_local_delivery_preflight_fails_when_verdict_gate_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    calls: list[str] = []

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        calls.append(label)
        if label == "accuracy_gate":
            (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "accuracy_gate_local_delivery_preflight_current.json").write_text(
                json.dumps({"summary": {"pass": True, "failed_metrics": []}}),
                encoding="utf-8",
            )
        failed = label == "verdict_gate"
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 2 if failed else 0,
            "ok": not failed,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "P0 blocked" if failed else "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(
            [
                "--out-json",
                str(out_json),
                "--out-md",
                str(tmp_path / "local_delivery_preflight.md"),
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is False
    assert payload["summary"]["first_failed_step"] == "verdict_gate"
    assert payload["summary"]["verdict_gate_required_ok"] is False
    assert payload["summary"]["verdict_gate_fingerprint_check"]["status"] == "pending_bundle_check"
    assert payload["summary"]["verdict_gate_fingerprint_check"]["comparison_performed"] is False
    markdown = (tmp_path / "local_delivery_preflight.md").read_text(encoding="utf-8")
    assert "verdict_gate_fingerprint_check_status" in markdown
    assert calls[-1] == "verdict_gate"


def test_local_delivery_preflight_allows_generated_blocked_verdict_as_separate_p0(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    verdict_json = tmp_path / "verdict_gate.json"
    verdict_md = tmp_path / "verdict_gate.md"

    def _write_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        if label == "accuracy_gate":
            _write_json(
                runs / "accuracy_gate_local_delivery_preflight_current.json",
                {"summary": {"pass": True, "failed_metrics": [], "failed_targets": []}},
            )
        if label == "requirements_lock":
            _write_json(
                tmp_path / "requirements_lock.json",
                {"summary": {"requirements_lock_complete": True, "missing_count": 0}},
            )
        if label == "engine_provenance":
            _write_json(
                tmp_path / "engine_provenance.json",
                {"summary": {"existing_engine_reused": True, "provenance_ok": True}},
            )
        if label == "verdict_gate":
            provisional = json.loads(out_json.read_text(encoding="utf-8"))
            assert provisional["summary"]["overall_ok"] is True
            assert provisional["summary"]["verdict_gate_pending"] is True
            assert provisional["summary"]["verdict_gate_required_ok"] is True
            time.sleep(0.001)
            _write_json(
                verdict_json,
                {
                    "summary": {
                        "delivery_ready": False,
                        "verdict": "blocked",
                        "p0_blocker_count": 2,
                        "status_line": "blocked: 2 P0 blocker(s) remain.",
                    },
                    "source_artifacts": [
                        {
                            "label": "preflight",
                            "required": True,
                            "present": True,
                            "size_bytes": 10,
                            "sha256": "a" * 64,
                        }
                    ],
                    "p0_blockers": [
                        {"code": "wetlab_selected_allatom_not_green", "severity": "hard"},
                        {"code": "commercialization_queue_not_clear", "severity": "hard"},
                    ],
                },
            )
            verdict_md.write_text("# blocked\n", encoding="utf-8")
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 2 if label == "verdict_gate" else 0,
            "ok": label != "verdict_gate",
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "blocked verdict" if label == "verdict_gate" else "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"

    preflight.main(
        [
            "--requirements-lock-out-json",
            str(tmp_path / "requirements_lock.json"),
            "--engine-provenance-out-json",
            str(tmp_path / "engine_provenance.json"),
            "--verdict-gate-out-json",
            str(verdict_json),
            "--verdict-gate-out-md",
            str(verdict_md),
            "--out-json",
            str(out_json),
            "--out-md",
            str(tmp_path / "local_delivery_preflight.md"),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is True
    assert payload["summary"]["first_failed_step"] == ""
    assert payload["summary"]["verdict_gate_delivery_ready"] is False
    assert payload["summary"]["verdict_gate_required_ok"] is True
    assert payload["summary"]["verdict_gate_p0_blocker_count"] == 2
    assert payload["summary"]["verdict_gate_pending"] is False
    assert payload["summary"]["verdict_gate_fingerprint_check"]["source_artifacts_all_fingerprinted"] is True
    assert "Preflight evidence is green" in payload["summary"]["next_required_step"]


def test_local_delivery_preflight_fails_when_verdict_gate_is_skipped(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "ROOT", tmp_path)

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        if label == "accuracy_gate":
            (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "accuracy_gate_local_delivery_preflight_current.json").write_text(
                json.dumps({"summary": {"pass": True, "failed_metrics": []}}),
                encoding="utf-8",
            )
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 0,
            "ok": True,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)
    out_json = tmp_path / "local_delivery_preflight.json"

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(
            [
                "--skip-verdict-gate",
                "--out-json",
                str(out_json),
                "--out-md",
                str(tmp_path / "local_delivery_preflight.md"),
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_ok"] is False
    assert payload["summary"]["first_failed_step"] == "verdict_gate"
    assert payload["summary"]["verdict_gate_delivery_ready"] is False
    assert payload["summary"]["verdict_gate_required_ok"] is False


def test_local_delivery_preflight_records_partial_artifact_diagnostics(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TORCH_BLAS_PREFER_HIPBLASLT", raising=False)
    local_ci_json = tmp_path / "local_ci.json"
    environment_json = tmp_path / "environment.json"
    environment_md = tmp_path / "environment.md"
    out_json = tmp_path / "local_delivery_preflight.json"

    def _fake_run_step(
        label: str,
        cmd: list[str],
        dry_run: bool = False,
        env: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
    ) -> dict[str, object]:
        if label == "environment_manifest":
            assert env == {"TORCH_BLAS_PREFER_HIPBLASLT": "0"}
            environment_json.write_text('{"summary": {"ok": true}}\n', encoding="utf-8")
            environment_md.write_text("# env\n", encoding="utf-8")
        failed = label == "local_ci"
        return {
            "label": label,
            "cmd": list(cmd),
            "env": dict(env or {}),
            "expected_artifacts": list(expected_artifacts or []),
            "returncode": 2 if failed else 0,
            "ok": not failed,
            "dry_run": dry_run,
            "stdout_tail": "",
            "stderr_tail": "local ci failed" if failed else "",
        }

    monkeypatch.setattr(preflight, "_run_step", _fake_run_step)

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(
            [
                "--skip-accuracy-gate",
                "--skip-requirements-lock",
                "--skip-engine-provenance",
                "--skip-refresh",
                "--skip-queue",
                "--skip-report",
                "--skip-verdict-gate",
                "--local-ci-out-json",
                str(local_ci_json),
                "--environment-out-json",
                str(environment_json),
                "--environment-out-md",
                str(environment_md),
                "--out-json",
                str(out_json),
                "--out-md",
                str(tmp_path / "local_delivery_preflight.md"),
            ]
        )

    assert exc_info.value.code == 2
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    diagnostics = {
        (row["step_label"], row["path"]): row for row in payload["artifact_diagnostics"]
    }
    assert diagnostics[("local_ci", str(local_ci_json))]["present"] is False
    assert diagnostics[("environment_manifest", str(environment_json))]["nonempty"] is True
    assert diagnostics[("environment_manifest", str(environment_md))]["nonempty"] is True
    assert payload["summary"]["expected_artifact_count"] == 3
    assert payload["summary"]["present_expected_artifact_count"] == 2
    assert payload["summary"]["missing_expected_artifact_count"] == 1
