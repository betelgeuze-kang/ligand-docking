from __future__ import annotations

from pathlib import Path

import asyncio
import hashlib
import json

import pytest


def _write_fake_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_validated_runner',",
                "    'target_name': request.get('target_name'),",
                "    'runner_profile_id': request.get('runner_profile_id'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_evidence(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "input_contract_reviewed": True,
                "output_contract_reviewed": True,
                "claim_boundary_reviewed": True,
                "gate_policy_reviewed": True,
                "fake_result_emission_forbidden": True,
                "gate_policy_artifact": "runs/fake_gate_policy_current.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _profile_payload(profile_id: str, fake_runner: Path, evidence: Path) -> dict:
    return {
        "profile_id": profile_id,
        "enabled": True,
        "runner_script": str(fake_runner.resolve()),
        "arguments": [
            "--request-json",
            "{request_json_path}",
            "--out-json",
            "{result_file}",
        ],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "production_readiness": {
            "approved_by": "unit-test-operator",
            "approved_at_utc": "2026-06-06T00:00:00+00:00",
            "claim_scope": "unit-test-profile-only",
            "evidence_artifact": str(evidence),
            "runner_script_sha256": _sha256(fake_runner),
        },
    }


def test_api_task_executes_operator_approved_runner_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "smoke.json").write_text(
        json.dumps(_profile_payload("smoke", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    asyncio.run(
        run_simulation_async(
            "job_profile",
            {
                "target_name": "Chignolin",
                "runner_profile_id": "smoke",
                "runner_profile_params": {"ignored_by_adapter": True},
            },
        )
    )

    status = json.loads((tmp_path / "results" / "job_profile" / "status.json").read_text(encoding="utf-8"))
    result_file = Path(status["result_file"])
    execution_record = Path(status["runner_execution"])
    result = json.loads(result_file.read_text(encoding="utf-8"))

    assert status["status"] == "completed"
    assert status["runner_profile_id"] == "smoke"
    assert status["runner_profile_claim_scope"] == "unit-test-profile-only"
    assert status["result_file_sha256"]
    assert result["runner_kind"] == "fake_validated_runner"
    assert result["target_name"] == "Chignolin"
    assert execution_record.exists()
    assert "shell" not in json.loads(execution_record.read_text(encoding="utf-8"))


def test_api_task_remains_fail_closed_when_validated_runner_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", False)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(NotImplementedError, match="validated runner execution is disabled"):
        asyncio.run(
            run_simulation_async(
                "job_disabled",
                {"target_name": "Chignolin", "runner_profile_id": "smoke"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_disabled" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert "validated runner execution is disabled" in status["error"]


def test_validated_runner_rejects_profile_path_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(tmp_path / "profiles"))
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(ValueError, match="runner_profile_id"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_bad",
                {"target_name": "Chignolin", "runner_profile_id": "../bad"},
            )
        )


def test_validated_runner_rejects_enabled_profile_without_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "missing_evidence.json").write_text(
        json.dumps(
            {
                "profile_id": "missing_evidence",
                "enabled": True,
                "runner_script": str(fake_runner.resolve()),
                "arguments": ["--request-json", "{request_json_path}", "--out-json", "{result_file}"],
                "result_file_template": "{job_results_dir}/runner_result.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(PermissionError, match="production_readiness"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_missing_evidence",
                {"target_name": "Chignolin", "runner_profile_id": "missing_evidence"},
            )
        )


def test_worker_queue_executes_validated_runner_profile_and_signs_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from api.result_manifest import verify_result_manifest
    from api.tasks import run_simulation_async

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "worker_smoke.json").write_text(
        json.dumps(_profile_payload("worker_smoke", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    request = {
        "target_name": "Chignolin",
        "runner_profile_id": "worker_smoke",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
        "runner_profile_params": {
            "ligands": ["CCO"],
            "metadata": {"ligand_smiles": "CCN"},
        },
    }
    store.create_job("job_worker_profile", request, status="submitted")
    worker.write_status_file(
        worker.job_status_path("job_worker_profile"),
        {"job_id": "job_worker_profile", "status": "submitted"},
    )

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_profile",
            runner=run_simulation_async,
            heartbeat_interval_seconds=0.05,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result_file"]
    assert completed["result_manifest_path"]

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file"] == completed["result_file"]
    assert verify_result_manifest(manifest, signing_key=validated_runner.settings.api_result_manifest_signing_key)
    runner_request = (tmp_path / "results" / "job_worker_profile" / "request.json").read_text(
        encoding="utf-8"
    )
    assert "ATOM      1" not in runner_request
    assert "CCO" not in runner_request
    assert "CCN" not in runner_request
    assert "sha256" in runner_request


def test_validate_api_runner_profiles_cli_reports_ready_enabled_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from tools.product.validate_api_runner_profiles import validate_profiles

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "ready_profile.json").write_text(
        json.dumps(_profile_payload("ready_profile", fake_runner, evidence), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})

    payload = validate_profiles(profiles_dir)

    assert payload["status"] == "pass"
    assert payload["enabled_profile_count"] == 1
    assert payload["failed_profile_count"] == 0
    assert payload["rows"][0]["status"] == "ready"
