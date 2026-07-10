from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest


def _write_profile_fixture(
    tmp_path: Path,
    *,
    profile_id: str,
    execution_mode: str,
    customer_allowed: bool,
    result_template: str = "{job_results_dir}/runner_result.json",
) -> tuple[Path, Path]:
    runner = tmp_path / f"{profile_id}_runner.py"
    runner.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "out = Path(sys.argv[sys.argv.index('--out') + 1])\n"
        "out.write_text('{}\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    evidence = tmp_path / f"{profile_id}_evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "input_contract_reviewed": True,
                "output_contract_reviewed": True,
                "claim_boundary_reviewed": True,
                "gate_policy_reviewed": True,
                "fake_result_emission_forbidden": True,
                "gate_policy_artifact": "test-only",
            }
        ),
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    profile = {
        "profile_id": profile_id,
        "enabled": True,
        "execution_mode": execution_mode,
        "customer_submission_allowed": customer_allowed,
        "synthetic_input_allowed": execution_mode == "smoke",
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
        "runner_script": str(runner),
        "arguments": ["--out", "{result_file}"],
        "result_file_template": result_template,
        "production_readiness": {
            "approved_by": "unit-test",
            "approved_at_utc": "2026-07-10T00:00:00+00:00",
            "claim_scope": "unit-test-only",
            "evidence_artifact": str(evidence),
            "runner_script_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        },
    }
    (profiles / f"{profile_id}.json").write_text(json.dumps(profile), encoding="utf-8")
    return profiles, runner


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profiles: Path,
    runner: Path,
) -> None:
    import api.validated_runner as validated_runner

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles))
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner)})


def test_customer_cannot_execute_internal_smoke_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    profiles, runner = _write_profile_fixture(
        tmp_path,
        profile_id="internal_smoke",
        execution_mode="smoke",
        customer_allowed=False,
    )
    _configure(monkeypatch, tmp_path, profiles, runner)

    with pytest.raises(PermissionError, match="not authorized for customer submission"):
        validated_runner.authorize_runner_profile_execution(
            {"runner_profile_id": "internal_smoke"}
        )

    authorized = validated_runner.authorize_runner_profile_execution(
        {"runner_profile_id": "internal_smoke"},
        execution_origin=validated_runner.EXECUTION_ORIGIN_INTERNAL,
    )
    assert authorized["execution_contract"]["execution_mode"] == "smoke"


def test_restricted_profile_requires_explicit_customer_permission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    profiles, runner = _write_profile_fixture(
        tmp_path,
        profile_id="customer_restricted",
        execution_mode="restricted-production",
        customer_allowed=True,
    )
    _configure(monkeypatch, tmp_path, profiles, runner)

    authorized = validated_runner.authorize_runner_profile_execution(
        {"runner_profile_id": "customer_restricted"}
    )
    assert authorized["execution_contract"]["customer_submission_allowed"] is True


def test_runner_result_template_cannot_escape_job_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    profiles, runner = _write_profile_fixture(
        tmp_path,
        profile_id="escaping",
        execution_mode="restricted-production",
        customer_allowed=True,
        result_template="{job_results_dir}/../escaped.json",
    )
    _configure(monkeypatch, tmp_path, profiles, runner)

    with pytest.raises(PermissionError, match="escapes configured root"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job-escape",
                {"runner_profile_id": "escaping"},
            )
        )
    assert not (tmp_path / "results" / "escaped.json").exists()


def test_runner_result_template_cannot_traverse_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    profiles, runner = _write_profile_fixture(
        tmp_path,
        profile_id="symlinked",
        execution_mode="restricted-production",
        customer_allowed=True,
    )
    _configure(monkeypatch, tmp_path, profiles, runner)
    job_dir = tmp_path / "results" / "job-symlink"
    job_dir.mkdir(parents=True)
    outside = tmp_path / "outside-result.json"
    (job_dir / "runner_result.json").symlink_to(outside)

    with pytest.raises(PermissionError, match="symbolic link"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job-symlink",
                {"runner_profile_id": "symlinked"},
            )
        )
    assert not outside.exists()


def test_job_store_persists_tenant_owner(tmp_path: Path) -> None:
    from api.job_store import SQLiteJobStore

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    created = store.create_job(
        "tenant-job",
        {"runner_profile_id": "x"},
        tenant_id="tenant-a",
    )
    assert created["tenant_id"] == "tenant-a"
    assert store.get_job("tenant-job")["tenant_id"] == "tenant-a"  # type: ignore[index]

    with pytest.raises(ValueError, match="simple"):
        store.create_job("../escape", {"runner_profile_id": "x"})

    store.create_job(
        "tenant-job",
        {"runner_profile_id": "replacement"},
        tenant_id="tenant-b",
    )
    assert store.get_job("tenant-job")["tenant_id"] == "tenant-a"  # type: ignore[index]


def test_task_rejects_unsafe_job_id_before_creating_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.tasks as tasks

    results_root = tmp_path / "results"
    monkeypatch.setattr(tasks.settings, "results_storage_path", str(results_root))

    with pytest.raises(ValueError, match="simple"):
        asyncio.run(
            tasks.run_simulation_async(
                "../escaped-job",
                {"runner_profile_id": "irrelevant", "target_name": "ADRB2"},
            )
        )

    assert not (tmp_path / "escaped-job").exists()
