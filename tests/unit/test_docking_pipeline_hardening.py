from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from api.job_store import SQLiteJobStore
from api.runner_profile_contract import validate_runner_profile_execution_contract
from betelgeuze_product.job_orchestration import read_job_record, write_job_record
from tools.product.materialize_docking_htvs_request import (
    DockingMaterializationError,
    materialize_from_docking_request as materialize_htvs,
)
from tools.product.materialize_docking_backmapping_request import (
    materialize_from_docking_request as materialize_backmapping,
)


def _write_request(path: Path, params: dict) -> Path:
    path.write_text(
        json.dumps(
            {
                "target_name": "ADRB2",
                "runner_profile_params": params,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _redacted_ligand() -> dict:
    return {
        "ligand_id": "LIG-001",
        "source_kind": "smiles",
        "source_value_sha256": "a" * 64,
        "source_redacted": True,
    }


def _target_pdb() -> str:
    return (
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
        "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00  0.00           C\n"
    )


def test_htvs_materializer_rejects_redacted_hash_only_ligand(tmp_path: Path) -> None:
    request_path = _write_request(
        tmp_path / "request.json",
        {
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    with pytest.raises(
        DockingMaterializationError,
        match="ligand_source_unavailable_for_materialization",
    ):
        materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))


def test_htvs_materializer_error_exposes_structured_reason(tmp_path: Path) -> None:
    request_path = _write_request(
        tmp_path / "request.json",
        {
            "ligand_count": 1,
            "ligands": [{"ligand_id": "LIG-001", "sdf_path": "/tmp/x.sdf"}],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    with pytest.raises(DockingMaterializationError) as excinfo:
        materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    # The category (reason_code) is stable; the offending source kind is detail.
    assert excinfo.value.reason_code == "unsupported_ligand_source_for_htvs_materialization"
    assert excinfo.value.reason_detail == "sdf_path"
    # str() stays backward compatible for any legacy message matching.
    assert str(excinfo.value) == "unsupported_ligand_source_for_htvs_materialization:sdf_path"


def test_dispatch_outcome_exposes_structured_reason(tmp_path: Path) -> None:
    from api.docking_dispatch import dispatch_docking_job_if_eligible

    # A non-eligible record returns early; the outcome carries both the legacy
    # reason string and the structured reason_code/reason_detail.
    outcome = dispatch_docking_job_if_eligible({"status": "blocked"}, jobs_dir=tmp_path)
    assert outcome["dispatched"] is False
    assert outcome["reason"] == "status_not_accepted_fail_closed"
    assert outcome["reason_code"] == "status_not_accepted_fail_closed"
    assert outcome["reason_detail"] == ""


def test_backmapping_materializer_rejects_empty_ligand_input(tmp_path: Path) -> None:
    request_path = _write_request(
        tmp_path / "request.json",
        {
            "ligand_count": 1,
            "ligands": [],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    with pytest.raises(
        DockingMaterializationError,
        match="ligand_source_unavailable_for_materialization",
    ):
        materialize_backmapping(str(request_path), out_dir=str(tmp_path / "out"))


def test_backmapping_materializer_recovers_redacted_ligands_from_private_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Backmapping reuses the shared _resolve_materialization_inputs, so the
    # encrypted-store recovery applies here too: a redacted ledger/queue ligand
    # is recovered from the private payload store instead of failing closed.
    import betelgeuze_product.docking_private_payload as dpp
    from betelgeuze_product.private_payload_store import PrivatePayloadKeyring

    job_id = "job-backmap-recover-1"
    request_sha256 = "d" * 64
    store = dpp.build_store(
        keys_config=f"k1:{PrivatePayloadKeyring.generate_secret_b64()}",
        root_dir=tmp_path / "pp",
        ttl_seconds=3600,
    )
    dpp.store_docking_request(
        store,
        job_id=job_id,
        request_sha256=request_sha256,
        request={
            "family": "gpcr",
            "pdb_content": _target_pdb(),
            "ligands": [{"ligand_id": "LIG-001", "smiles": "CCO"}],
        },
    )
    monkeypatch.setattr(dpp, "configured_store", lambda: store)

    request_path = _write_request(
        tmp_path / "request.json",
        {
            "docking_job_id": job_id,
            "request_sha256": request_sha256,
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    materialized = materialize_backmapping(str(request_path), out_dir=str(tmp_path / "out"))

    assert materialized["input_materialization_ready"] is True
    assert materialized["synthetic_input_used"] is False
    assert materialized["ligand_count"] == 1
    assert len(materialized["target_structure_sha256"]) == 64
    assert Path(materialized["target_structure_path"]).is_file()
    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["ligand_id"] == "LIG-001"
    assert rows[0]["ligand_smiles"] == "CCO"
    assert rows[0]["synthetic_smoke_input"].lower() == "false"


def test_explicit_internal_smoke_uses_one_labelled_synthetic_ligand(tmp_path: Path) -> None:
    request_path = _write_request(
        tmp_path / "request.json",
        {
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
            "runner_execution_mode": "smoke",
            "runner_synthetic_input_allowed": True,
            "allow_synthetic_ligand_input": True,
        },
    )

    materialized = materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    assert materialized["input_materialization_ready"] is True
    assert materialized["synthetic_input_used"] is True
    assert materialized["ligand_count"] == 1
    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["ligand_id"] == "synthetic_smoke_ligand_1"
    assert rows[0]["ligand_smiles"] == "CCO"
    assert rows[0]["synthetic_smoke_input"].lower() == "true"


def test_htvs_materializer_recovers_redacted_ligands_from_private_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The ledger/queue carry only a redacted ligand, but the original request
    # is available in the encrypted private payload store. The materializer must
    # recover the real source (bound to job_id + request_sha256) instead of
    # failing closed.
    import betelgeuze_product.docking_private_payload as dpp
    from betelgeuze_product.private_payload_store import PrivatePayloadKeyring

    job_id = "job-recover-1"
    request_sha256 = "c" * 64
    store = dpp.build_store(
        keys_config=f"k1:{PrivatePayloadKeyring.generate_secret_b64()}",
        root_dir=tmp_path / "pp",
        ttl_seconds=3600,
    )
    dpp.store_docking_request(
        store,
        job_id=job_id,
        request_sha256=request_sha256,
        request={
            "family": "gpcr",
            "pdb_content": _target_pdb(),
            "ligands": [{"ligand_id": "LIG-001", "smiles": "CCO"}],
        },
    )
    monkeypatch.setattr(dpp, "configured_store", lambda: store)

    request_path = _write_request(
        tmp_path / "request.json",
        {
            "docking_job_id": job_id,
            "request_sha256": request_sha256,
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    materialized = materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))

    assert materialized["input_materialization_ready"] is True
    assert materialized["synthetic_input_used"] is False
    assert materialized["ligand_count"] == 1
    assert len(materialized["target_structure_sha256"]) == 64
    assert Path(materialized["target_structure_path"]).is_file()
    with Path(materialized["queue_csv"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["ligand_id"] == "LIG-001"
    assert rows[0]["ligand_smiles"] == "CCO"
    assert rows[0]["synthetic_smoke_input"].lower() == "false"


def test_htvs_materializer_fails_closed_when_private_store_binding_mismatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A stored payload under a DIFFERENT request_sha256 must not be recovered;
    # the materializer stays fail-closed.
    import betelgeuze_product.docking_private_payload as dpp
    from betelgeuze_product.private_payload_store import PrivatePayloadKeyring

    job_id = "job-recover-2"
    store = dpp.build_store(
        keys_config=f"k1:{PrivatePayloadKeyring.generate_secret_b64()}",
        root_dir=tmp_path / "pp",
        ttl_seconds=3600,
    )
    dpp.store_docking_request(
        store,
        job_id=job_id,
        request_sha256="a" * 64,
        request={"ligands": [{"ligand_id": "LIG-001", "smiles": "CCO"}]},
    )
    monkeypatch.setattr(dpp, "configured_store", lambda: store)

    request_path = _write_request(
        tmp_path / "request.json",
        {
            "docking_job_id": job_id,
            "request_sha256": "b" * 64,  # does not match the stored binding
            "ligand_count": 1,
            "ligands": [_redacted_ligand()],
            "runner_execution_mode": "restricted-production",
            "runner_synthetic_input_allowed": False,
            "allow_synthetic_ligand_input": False,
        },
    )

    with pytest.raises(
        DockingMaterializationError,
        match="ligand_source_unavailable_for_materialization",
    ):
        materialize_htvs(str(request_path), out_dir=str(tmp_path / "out"))


def test_create_job_if_absent_preserves_completed_row(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    request = {"target_name": "ADRB2", "runner_profile_id": "profile"}

    created_record, created = store.create_job_if_absent("job-1", request)
    assert created is True
    assert created_record["status"] == "submitted"
    store.update_job("job-1", status="completed", result_file="result.json")

    existing_record, created_again = store.create_job_if_absent("job-1", request)

    assert created_again is False
    assert existing_record["status"] == "completed"
    assert existing_record["result_file"] == "result.json"


def _ledger_record(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "accepted_fail_closed",
        "validation_status": "pass",
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "worker_state": "not_started_fail_closed",
        "queue_status": "queued_fail_closed",
        "cancellable": True,
        "retryable": True,
        "retry_limit_reached": False,
        "attempt_index": 1,
        "max_retry_attempts": 3,
        "event_history": [],
    }


def test_simulation_completion_sets_terminal_ledger_contract(tmp_path: Path) -> None:
    from api.docking_dispatch import sync_ledger_from_simulation_result

    jobs_dir = tmp_path / "jobs"
    write_job_record(jobs_dir, _ledger_record("job-complete"))

    result = sync_ledger_from_simulation_result(
        jobs_dir,
        "job-complete",
        status="completed",
        result_file="result.json",
        worker_id="worker-1",
    )
    ledger = read_job_record(jobs_dir, "job-complete")

    assert result["terminal_state"] is True
    assert ledger["status"] == "completed_fail_closed"
    assert ledger["queue_status"] == "completed_fail_closed"
    assert ledger["progress_percent"] == 100.0
    assert ledger["cancellable"] is False
    assert ledger["retryable"] is False
    assert ledger["status_transition_contract"]["terminal_state"] is True


def test_simulation_failure_sets_retryable_terminal_ledger_contract(tmp_path: Path) -> None:
    from api.docking_dispatch import sync_ledger_from_simulation_result

    jobs_dir = tmp_path / "jobs"
    write_job_record(jobs_dir, _ledger_record("job-failed"))

    sync_ledger_from_simulation_result(
        jobs_dir,
        "job-failed",
        status="failed",
        error="runner failed",
        worker_id="worker-1",
    )
    ledger = read_job_record(jobs_dir, "job-failed")

    assert ledger["status"] == "failed_fail_closed"
    assert ledger["queue_status"] == "failed_retryable_fail_closed"
    assert ledger["worker_state"] == "failed_retryable_fail_closed"
    assert ledger["cancellable"] is False
    assert ledger["retryable"] is True
    assert ledger["status_transition_contract"]["terminal_state"] is True


def _dispatch_record(*, profile_id: str, execution_mode: str, source_host: str) -> dict:
    return {
        "job_id": "dispatch-job",
        "status": "accepted_fail_closed",
        "queue_status": "queued_fail_closed",
        "validation_status": "pass",
        "engine_dispatch_ready": True,
        "scope_claim_allowed_for_request": True,
        "worker_dispatch_enqueued": False,
        "source_host": source_host,
        "ligand_count": 1,
        "materialization_ligands": [_redacted_ligand()],
        "engine_dispatch_manifest": {
            "runner_profile_id": profile_id,
            "execution_mode": execution_mode,
        },
    }


def test_customer_dispatch_rejects_smoke_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.docking_dispatch as docking_dispatch

    monkeypatch.setattr(docking_dispatch.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        docking_dispatch.settings,
        "api_validated_runner_profiles_path",
        "config/api_validated_runner_profiles",
    )
    eligible, reason = docking_dispatch.is_dispatch_eligible(
        _dispatch_record(
            profile_id="ligand_htvs_pipeline_default",
            execution_mode="smoke",
            source_host="203.0.113.10",
        )
    )

    assert eligible is False
    assert reason.startswith("runner_profile_not_customer_submission_allowed")


def test_internal_smoke_actor_is_explicitly_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.docking_dispatch as docking_dispatch

    monkeypatch.setattr(docking_dispatch.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        docking_dispatch.settings,
        "api_validated_runner_profiles_path",
        "config/api_validated_runner_profiles",
    )
    eligible, reason = docking_dispatch.is_dispatch_eligible(
        _dispatch_record(
            profile_id="ligand_htvs_pipeline_default",
            execution_mode="smoke",
            source_host="tier_alpha_dispatch_smoke",
        )
    )

    assert eligible is True
    assert reason == "eligible"


def test_restricted_production_requires_materializable_ligand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as docking_dispatch

    monkeypatch.setattr(docking_dispatch.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        docking_dispatch.settings,
        "api_validated_runner_profiles_path",
        "config/api_validated_runner_profiles",
    )
    eligible, reason = docking_dispatch.is_dispatch_eligible(
        _dispatch_record(
            profile_id="backmapping_scoring.production",
            execution_mode="restricted-production",
            source_host="203.0.113.10",
        )
    )

    assert eligible is False
    assert reason == "runner_input_materialization_not_ready"


def test_profile_execution_contract_rejects_mislabelled_smoke() -> None:
    with pytest.raises(PermissionError, match="cannot allow customer submissions"):
        validate_runner_profile_execution_contract(
            {
                "execution_mode": "smoke",
                "customer_submission_allowed": True,
                "synthetic_input_allowed": True,
                "production_claim_allowed": False,
                "customer_pose_emission_allowed": False,
            }
        )
