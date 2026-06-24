from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.docking_outbox import get_outbox_event
from api.job_store import get_configured_job_store, reset_configured_job_store_for_tests
from betelgeuze_product.private_payload_store import PrivatePayloadStore


def _test_key() -> str:
    return base64.urlsafe_b64encode(b"secure-api-test-key-000000000000"[:32]).decode("ascii")


@pytest.fixture(autouse=True)
def _reset_job_store() -> None:
    reset_configured_job_store_for_tests()
    yield
    reset_configured_job_store_for_tests()


def test_secure_submission_encrypts_inputs_and_enqueues_restricted_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as docking_dispatch
    import api.product_secure as product_secure

    results_dir = tmp_path / "results"
    profiles_dir = Path("config/api_validated_runner_profiles").resolve()
    for settings_obj in (product_secure.settings, docking_dispatch.settings):
        monkeypatch.setattr(settings_obj, "results_storage_path", str(results_dir))
        monkeypatch.setattr(
            settings_obj,
            "api_job_store_path",
            str(results_dir / "api_jobs.sqlite3"),
        )
        monkeypatch.setattr(settings_obj, "api_validated_runner_enabled", True)
        monkeypatch.setattr(
            settings_obj,
            "api_validated_runner_profiles_path",
            str(profiles_dir),
        )
        monkeypatch.setattr(
            settings_obj,
            "docking_private_payload_store_path",
            str(results_dir / "private_payloads"),
        )
        monkeypatch.setattr(
            settings_obj,
            "docking_private_payload_fernet_keys",
            _test_key(),
        )
        monkeypatch.setattr(
            settings_obj,
            "docking_private_payload_key_id",
            "secure-api-test-v1",
        )
        monkeypatch.setattr(
            settings_obj,
            "docking_private_payload_ttl_seconds",
            3600,
        )

    monkeypatch.setattr(
        product_secure,
        "build_customer_production_dispatch_manifest",
        lambda **kwargs: {
            "job_id": kwargs["job_id"],
            "target_id": kwargs["target_id"],
            "family": kwargs["family"],
            "runner_profile_id": "ligand_htvs.restricted-production",
            "ligand_model_hint": "auto",
            "runner_execution_contract_explicit": True,
            "execution_mode": "restricted-production",
            "customer_submission_allowed": True,
            "synthetic_input_allowed": False,
            "production_claim_allowed": False,
            "customer_pose_emission_allowed": False,
            "engine_roadmap_ready": True,
            "dispatch_ready": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
        },
    )

    app = FastAPI()
    app.include_router(product_secure.router)
    client = TestClient(app)
    request_payload = {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_content": (
            "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
        ),
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        "metadata": {"customer_id": "customer-1", "user_id": "user-1"},
    }

    response = client.post("/product/docking/jobs", json=request_payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["validation_status"] == "pass"
    assert body["execution_mode"] == "restricted-production"
    assert body["private_payload_ref_present"] is True
    assert body["private_payload_store_ready"] is True
    assert body["input_materialization_ready"] is True
    assert body["worker_dispatch_enqueued"] is True
    assert body["worker_dispatch_reason"] == "eligible"
    assert "private_payload_ref" not in body
    assert "CCO" not in response.text
    assert "ATOM      1" not in response.text

    job_id = body["job_id"]
    ledger_path = results_dir / "product_docking_jobs" / f"{job_id}.json"
    ledger_text = ledger_path.read_text(encoding="utf-8")
    ledger = json.loads(ledger_text)
    assert "CCO" not in ledger_text
    assert "ATOM      1" not in ledger_text
    assert ledger["private_payload_ref"]
    assert ledger["worker_dispatch_enqueued"] is True

    private_store = PrivatePayloadStore.from_settings(product_secure.settings)
    restored = private_store.get(
        ledger["private_payload_ref"],
        expected_job_id=job_id,
        expected_request_sha256=ledger["request_sha256"],
    )
    assert restored["ligands"][0]["smiles"] == "CCO"
    assert restored["pdb_content"].startswith("ATOM")

    queue_store = get_configured_job_store(product_secure.settings.api_job_store_path)
    queued = queue_store.get_job(job_id)
    assert queued is not None
    assert queued["status"] == "submitted"
    assert queued["request"]["runner_profile_id"] == "ligand_htvs.restricted-production"
    queued_text = json.dumps(queued["request"], sort_keys=True)
    assert "CCO" not in queued_text
    assert "ATOM      1" not in queued_text
    assert ledger["private_payload_ref"] in queued_text

    outbox_event = get_outbox_event(
        queue_store,
        body["worker_dispatch_outbox_event_id"],
    )
    assert outbox_event is not None
    assert outbox_event["status"] == "delivered"
