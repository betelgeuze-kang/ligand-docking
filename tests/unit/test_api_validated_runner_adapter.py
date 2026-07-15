from __future__ import annotations

from pathlib import Path

import asyncio
import hashlib
import json
import sys

import pytest


def test_validated_runner_child_environment_excludes_service_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    secret_names = [
        "PRODUCT_API_TOKEN",
        "PRODUCT_API_ADMIN_TOKEN",
        "API_RESULT_MANIFEST_SIGNING_KEY",
        "DOCKING_PRIVATE_PAYLOAD_KEYS",
        "AWS_SECRET_ACCESS_KEY",
        "UNRELATED_SERVICE_TOKEN",
        "LC_API_TOKEN",
    ]
    for name in secret_names:
        monkeypatch.setenv(name, f"secret-for-{name}")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    probe = (
        "import json,os; "
        f"names={secret_names!r}; "
        "print(json.dumps({'secret_presence': {name: name in os.environ for name in names}, "
        "'cuda_visible': os.environ.get('CUDA_VISIBLE_DEVICES', '')}, sort_keys=True))"
    )

    completed = validated_runner._run_profile_command(
        [sys.executable, "-c", probe],
        timeout_seconds=10,
    )

    assert completed["returncode"] == 0
    payload = json.loads(completed["stdout"])
    assert payload["secret_presence"] == {name: False for name in secret_names}
    assert payload["cuda_visible"] == "0"


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
                "p.add_argument('--evidence-bundle', required=False, default='')",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_validated_runner',",
                "    'target_name': request.get('target_name'),",
                "    'runner_profile_id': request.get('runner_profile_id'),",
                "    'evidence_bundle_path': args.evidence_bundle,",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_slow_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, time",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "args = p.parse_args()",
                "time.sleep(10)",
                "Path(args.out_json).write_text(json.dumps({'ok': True}) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_native_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_native_bundle_runner',",
                "    'target_name': request.get('target_name'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
                "bundle = {",
                "    'bundle_id': 'native_' + request.get('target_name', 'job'),",
                "    'project_id': request.get('target_name', 'job'),",
                "    'ranked_shortlist': [],",
                "    'trajectory_summary': {'frame_count': 0},",
                "    'backmapped_poses': [],",
                "    'interaction_report': {},",
                "    'topology_report': {",
                "        'status': 'not_assessed',",
                "        'topology_fidelity': 'placeholder_alanine',",
                "        'claim_blockers': ['topology_validity_not_assessed'],",
                "    },",
                "    'ai_residual_report': {'residual_mode': 'disabled', 'uncertainty': 1.0, 'abstained': True},",
                "    'failure_flags': ['delivery_bundle_validation_not_attached'],",
                "    'source_hashes': {",
                "        'input_hash': 'i' * 64,",
                "        'config_hash': 'c' * 64,",
                "        'model_hash': 'm' * 64,",
                "        'executable_hash': 'e' * 64,",
                "    },",
                "    'viewer_assets': [],",
                "    'wetlab_handoff_table': [],",
                "    'verdict': {",
                "        'claim_safe': False,",
                "        'verdict_label': 'native_runner_review_only',",
                "        'claim_scope': 'restricted_local_delivery_proxy_refinement_only',",
                "        'topology_fidelity': 'placeholder_alanine',",
                "        'accuracy_claim_grade': 'restricted-local-delivery',",
                "        'failure_flags': ['delivery_bundle_validation_not_attached'],",
                "    },",
                "}",
                "Path(args.evidence_bundle).write_text(json.dumps(bundle, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_invalid_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_invalid_bundle_runner',",
                "    'target_name': request.get('target_name'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
                "Path(args.evidence_bundle).write_text(json.dumps({'bundle_id': 'x'}) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_no_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_no_bundle_runner',",
                "    'target_name': request.get('target_name'),",
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
        "execution_mode": "smoke",
        "customer_submission_allowed": False,
        "synthetic_input_allowed": True,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
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


def _profile_payload_with_evidence_bundle(
    profile_id: str, fake_runner: Path, evidence: Path
) -> dict:
    payload = _profile_payload(profile_id, fake_runner, evidence)
    payload["evidence_bundle_template"] = "{job_results_dir}/evidence_bundle.json"
    payload["arguments"] = [
        "--request-json",
        "{request_json_path}",
        "--out-json",
        "{result_file}",
        "--evidence-bundle",
        "{evidence_bundle}",
    ]
    return payload


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


def test_validated_runner_timeout_records_fail_closed_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    slow_runner = tmp_path / "slow_validated_runner.py"
    _write_slow_runner(slow_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "slow.json").write_text(
        json.dumps(_profile_payload("slow", slow_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(slow_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 1)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(RuntimeError, match="validated runner failed"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_slow",
                {"target_name": "Chignolin", "runner_profile_id": "slow"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_slow" / "status.json").read_text(encoding="utf-8"))
    execution_record = json.loads(Path(status["runner_execution"]).read_text(encoding="utf-8"))

    assert status["status"] == "failed"
    assert status["error"] == "validated_runner_timeout:1s"
    assert execution_record["timed_out"] is True
    assert execution_record["timeout_seconds"] == 1
    assert execution_record["process_group_killed_on_timeout"] is True
    assert execution_record["returncode"] != 0


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
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file"] == completed["result_file"]
    assert verify_result_manifest(manifest, signing_key=validated_runner.settings.api_result_manifest_signing_key)
    status = json.loads((tmp_path / "results" / "job_worker_profile" / "status.json").read_text(encoding="utf-8"))
    evidence_bundle = Path(status["evidence_bundle"])
    assert evidence_bundle.exists()
    assert len(status["evidence_bundle_sha256"]) == 64
    bundle = json.loads(evidence_bundle.read_text(encoding="utf-8"))
    assert bundle["verdict"]["claim_safe"] is False
    assert bundle["source_hashes"]["executable_hash"] == _sha256(fake_runner)
    assert "delivery_bundle_validation_not_attached" in bundle["failure_flags"]
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
    assert payload["enabled_native_evidence_bundle_missing_count"] == 1
    assert payload["first_enabled_native_evidence_bundle_missing_profile_id"] == "ready_profile"
    assert payload["rows"][0]["status"] == "ready"
    assert payload["rows"][0]["evidence_bundle_template_declared"] is False
    assert payload["rows"][0]["evidence_bundle_template"] == ""


def test_validate_api_runner_profiles_reports_native_evidence_bundle_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from tools.product.validate_api_runner_profiles import validate_profiles

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "native_profile.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("native_profile", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (profiles_dir / "disabled.json").write_text(
        json.dumps({"profile_id": "disabled", "enabled": False}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})

    payload = validate_profiles(profiles_dir)
    rows = {row["profile_id"]: row for row in payload["rows"]}

    assert payload["status"] == "pass"
    assert payload["enabled_native_evidence_bundle_missing_count"] == 0
    assert payload["first_enabled_native_evidence_bundle_missing_profile_id"] == ""
    assert rows["native_profile"]["status"] == "ready"
    assert rows["native_profile"]["evidence_bundle_template_declared"] is True
    assert "{job_results_dir}/evidence_bundle.json" == rows["native_profile"]["evidence_bundle_template"]
    assert rows["disabled"]["status"] == "disabled_skip"
    assert rows["disabled"]["evidence_bundle_template_declared"] is False
    assert rows["disabled"]["evidence_bundle_template"] == ""


def test_validated_runner_validates_native_evidence_bundle_and_records_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from betelgeuze_ai_md.contracts import EvidenceBundle

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "native_profile.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("native_profile", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    status_payload = asyncio.run(
        validated_runner.execute_validated_runner_profile(
            "job_native_bundle",
            {"target_name": "Chignolin", "runner_profile_id": "native_profile"},
        )
    )

    assert status_payload["status"] == "completed"
    native_bundle_path = Path(status_payload["evidence_bundle"])
    assert native_bundle_path.exists()
    assert status_payload["evidence_bundle_source"] == "validated_runner_native"
    raw_payload = json.loads(native_bundle_path.read_text(encoding="utf-8"))
    expected_fingerprint = EvidenceBundle(**raw_payload).fingerprint()
    assert status_payload["evidence_bundle_sha256"] == expected_fingerprint
    assert len(status_payload["evidence_bundle_sha256"]) == 64

    execution_record = json.loads(
        (tmp_path / "results" / "job_native_bundle" / "runner_execution.json").read_text(encoding="utf-8")
    )
    assert execution_record["evidence_bundle_template"] == "{job_results_dir}/evidence_bundle.json"
    assert execution_record["native_evidence_bundle"] == str(native_bundle_path)
    assert execution_record["native_evidence_bundle_sha256"] == expected_fingerprint


def test_validated_runner_fail_closed_when_native_bundle_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "no_bundle_runner.py"
    _write_no_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "no_bundle.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("no_bundle", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(FileNotFoundError, match="native evidence bundle"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_no_bundle",
                {"target_name": "Chignolin", "runner_profile_id": "no_bundle"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_no_bundle" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"


def test_validated_runner_fail_closed_when_native_bundle_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "invalid_bundle_runner.py"
    _write_invalid_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "invalid_bundle.json").write_text(
        json.dumps(
            _profile_payload_with_evidence_bundle("invalid_bundle", fake_runner, evidence), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(PermissionError, match="EvidenceBundle validation"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_invalid_bundle",
                {"target_name": "Chignolin", "runner_profile_id": "invalid_bundle"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_invalid_bundle" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"


def test_worker_adopts_validated_native_evidence_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from betelgeuze_ai_md.contracts import EvidenceBundle
    from api.tasks import run_simulation_async

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "worker_native.json").write_text(
        json.dumps(
            _profile_payload_with_evidence_bundle("worker_native", fake_runner, evidence), sort_keys=True
        )
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
        "runner_profile_id": "worker_native",
    }
    store.create_job("job_worker_native", request, status="submitted")
    worker.write_status_file(
        worker.job_status_path("job_worker_native"),
        {"job_id": "job_worker_native", "status": "submitted"},
    )

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_native",
            runner=run_simulation_async,
            heartbeat_interval_seconds=0.05,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64

    status = json.loads(
        (tmp_path / "results" / "job_worker_native" / "status.json").read_text(encoding="utf-8")
    )
    native_bundle_path = Path(status["evidence_bundle"])
    assert native_bundle_path.exists()
    assert native_bundle_path.name == "evidence_bundle.json"
    raw_payload = json.loads(native_bundle_path.read_text(encoding="utf-8"))
    expected_fingerprint = EvidenceBundle(**raw_payload).fingerprint()
    assert completed["evidence_bundle_sha256"] == expected_fingerprint
    assert status["evidence_bundle_sha256"] == expected_fingerprint
    assert status["evidence_bundle_source"] == "validated_runner_native"
    assert "delivery_bundle_validation_not_attached" in raw_payload["failure_flags"]


def test_validated_runner_without_template_keeps_fallback_no_native_bundle_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "fallback.json").write_text(
        json.dumps(_profile_payload("fallback", fake_runner, evidence), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    status_payload = asyncio.run(
        validated_runner.execute_validated_runner_profile(
            "job_fallback",
            {"target_name": "Chignolin", "runner_profile_id": "fallback"},
        )
    )

    assert status_payload["status"] == "completed"
    assert "evidence_bundle" not in status_payload
    assert "evidence_bundle_sha256" not in status_payload

    execution_record = json.loads(
        (tmp_path / "results" / "job_fallback" / "runner_execution.json").read_text(encoding="utf-8")
    )
    assert execution_record["evidence_bundle_template"] == ""
    assert execution_record["native_evidence_bundle"] == ""
    assert execution_record["native_evidence_bundle_sha256"] == ""
