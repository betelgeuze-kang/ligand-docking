from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from api.job_artifacts import create_attempt_results_dir, token_fingerprint
from api.job_store import SQLiteJobStore
from api.result_manifest import write_result_manifest
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    tier_alpha_adrb2_execution_evidence,
)
from api.validated_runner_runtime_qualification import (
    validated_runner_namespace_runtime_receipt_template,
)
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle
from tools.product import build_api_customer_flow_release_evidence as mod


MANIFEST_SIGNING_KEY = "unit-test-operator-managed-manifest-key"
MANIFEST_KEY_ID = "unit-test-operator-key-2026"
JOB_ID = "tier_alpha_adrb2_smoke_customer_flow"
WORKER_ID = "unit-worker"
REQUEST = {
    "runner_profile_id": "ligand_htvs_pipeline_default",
    "target_name": "ADRB2",
}


def _namespace_binding(
    receipt: dict[str, object],
    receipt_sha256: str,
) -> dict[str, object]:
    return {
        "validated_runner_namespace_runtime_qualified": True,
        "validated_runner_namespace_runtime_receipt_schema_version": receipt[
            "schema_version"
        ],
        "validated_runner_namespace_runtime_receipt_sha256": receipt_sha256,
        "validated_runner_namespace_runtime_receipt_issued_at_utc": receipt[
            "issued_at_utc"
        ],
        "validated_runner_namespace_runtime_receipt_expires_at_utc": receipt[
            "expires_at_utc"
        ],
    }


def _signed_manifest(
    result_root: Path,
    binding: dict[str, object],
) -> tuple[Path, Path, str]:
    store = SQLiteJobStore(result_root / f"{JOB_ID}.sqlite3")
    store.create_job(JOB_ID, REQUEST)
    acquired = store.acquire_next_job(WORKER_ID)
    assert acquired is not None
    attempt_token = str(acquired["attempt_token"])
    attempt_count = int(acquired["attempt_count"])
    attempt_token_sha256 = token_fingerprint(attempt_token)
    attempt_dir = create_attempt_results_dir(
        storage_root=result_root,
        job_id=JOB_ID,
        worker_id=WORKER_ID,
        attempt_token=attempt_token,
        attempt_count=attempt_count,
    )
    result = attempt_dir / "htvs_summary.json"
    result.write_text('{"status":"ok"}\n', encoding="utf-8")
    manifest = result.parent / "result_manifest.json"
    execution_evidence = tier_alpha_adrb2_execution_evidence(JOB_ID)
    worker_provenance = {
        "worker_id": WORKER_ID,
        "attempt_count": attempt_count,
        "attempt_token_sha256": attempt_token_sha256,
        "validated_runner_runtime_qualification": dict(binding),
        EXECUTION_EVIDENCE_PROVENANCE_KEY: execution_evidence,
    }
    manifest_payload = write_result_manifest(
        manifest,
        job_id=JOB_ID,
        request=REQUEST,
        request_sha256=str(acquired["request_sha256"]),
        execution_request_sha256=str(acquired["execution_request_sha256"]),
        execution_request_transform_id=str(
            acquired["execution_request_transform_id"]
        ),
        status="completed",
        result_file=str(result),
        signing_key=MANIFEST_SIGNING_KEY,
        key_id=MANIFEST_KEY_ID,
        worker_provenance=worker_provenance,
    )
    evidence_path = attempt_dir / "evidence_bundle.json"
    evidence = write_api_evidence_bundle(
        evidence_path,
        job_id=JOB_ID,
        request=REQUEST,
        result_manifest=manifest_payload,
        result_payload={"status": "ok"},
        status_payload={"status": "completed"},
    )
    status = {
        "job_id": JOB_ID,
        "status": "completed",
        "result_file": str(result),
        "result_manifest": str(manifest),
        "evidence_bundle": str(evidence_path),
        "evidence_bundle_sha256": evidence.fingerprint(),
        "worker_provenance": worker_provenance,
        EXECUTION_EVIDENCE_PROVENANCE_KEY: execution_evidence,
        **binding,
    }
    published_status = attempt_dir / "published_status.json"
    published_status.write_text(
        json.dumps(status, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    completed = store.update_job(
        JOB_ID,
        status="completed",
        result_file=str(result),
        result_manifest_path=str(manifest),
        evidence_bundle_path=str(evidence_path),
        evidence_bundle_sha256=evidence.fingerprint(),
        published_status_path=str(published_status),
        published_worker_id=WORKER_ID,
        published_attempt_count=attempt_count,
        published_attempt_token_sha256=attempt_token_sha256,
        expected_worker_id=WORKER_ID,
        expected_attempt_token=attempt_token,
    )
    assert completed is not None

    ledger_root = result_root / "product_docking_jobs"
    ledger_root.mkdir()
    (ledger_root / f"{JOB_ID}.json").write_text(
        json.dumps(
            {
                "job_id": JOB_ID,
                "worker_state": "completed_fail_closed",
                "simulation_sync_status": "completed",
                "simulation_result_file": str(result),
                "last_event_type": "worker_dispatch_completed",
                "event_history": [
                    {
                        "event_type": "worker_dispatch_completed",
                        "actor": WORKER_ID,
                        "worker_state": "completed_fail_closed",
                        "simulation_status": "completed",
                        "simulation_result_file": str(result),
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return result, manifest, hashlib.sha256(manifest.read_bytes()).hexdigest()


def _ready_packets(
    tmp_path: Path,
) -> tuple[dict[str, dict], dict[str, object]]:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    receipt = validated_runner_namespace_runtime_receipt_template(
        issued_at=now - dt.timedelta(minutes=1),
        expires_at=now + dt.timedelta(hours=1),
    )
    receipt_path = tmp_path / "namespace-runtime-receipt.json"
    raw_receipt = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    receipt_path.write_bytes(raw_receipt)
    receipt_path.chmod(0o600)
    receipt_sha256 = hashlib.sha256(raw_receipt).hexdigest()
    binding = _namespace_binding(receipt, receipt_sha256)
    result_root = tmp_path / "runtime-results"
    result, manifest, manifest_sha256 = _signed_manifest(result_root, binding)
    packets = {
        "e2e": {
            "summary": {
                "status": "api_docking_dispatch_e2e_ready",
                "wiring_ready": True,
                "evidence_mode": "live_job",
            },
            "ledger_worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
        },
        "restricted": {
            "summary": {
                "status": "restricted_unattended_execution_runtime_ready",
                "restricted_unattended_execution_ready": True,
                "restricted_unattended_execution_runtime_ready": True,
                "general_platform_claim_allowed": False,
                "tier_alpha_smoke_manifest_binding_verified": True,
                "tier_alpha_smoke_manifest_independently_verified": True,
                "tier_alpha_smoke_manifest_verification_reason": "verified",
                "tier_alpha_smoke_manifest_sha256": manifest_sha256,
                "tier_alpha_smoke_receipt_binding_matches": True,
                "tier_alpha_smoke_runtime_verified": True,
                **binding,
            }
        },
        "smoke": {
            "summary": {
                "status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "evidence_mode": "live_job",
                "api_validated_runner_enabled": True,
                **binding,
            },
            "job_id": JOB_ID,
            "dispatch_outcome": {
                "dispatched": True,
                "reason": "eligible",
                "enqueue": {"sqlite_status": "submitted"},
            },
            "worker_ran": True,
            "sqlite_job_status": "completed",
            "ledger_worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
            "result_file": str(result),
            "result_manifest": str(manifest),
            "result_manifest_sha256": manifest_sha256,
            "result_manifest_exists": True,
            "result_manifest_key_id": MANIFEST_KEY_ID,
            "htvs_summary_exists": True,
        },
        "bundle": {"summary": {"status": "product_bundle_contract_ready", "bundle_validation_passed": True}},
        "delivery": {
            "summary": {
                "status": "product_delivery_evidence_contract_ready",
                "bundle_validation_passed": True,
                "delivery_ready_claim_allowed": True,
            }
        },
        "pilot": {
            "summary": {
                "status": "product_pilot_packet_ready",
                "bundle_validation_passed": True,
                "pilot_delivery_ready": True,
            }
        },
    }
    verification = {
        "namespace_runtime_receipt_json": receipt_path,
        "namespace_runtime_receipt_sha256": receipt_sha256,
        "namespace_runtime_now": now + dt.timedelta(seconds=1),
        "result_manifest_root": result_root,
        "result_manifest_signing_key": MANIFEST_SIGNING_KEY,
        "result_manifest_expected_key_id": MANIFEST_KEY_ID,
    }
    return packets, verification


def _build(
    packets: dict[str, dict],
    verification: dict[str, object],
) -> dict[str, object]:
    return mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=packets["smoke"],
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
        **verification,
    )


def test_api_customer_flow_release_evidence_ready(tmp_path: Path) -> None:
    packets, verification = _ready_packets(tmp_path)

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=packets["smoke"],
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
        **verification,
    )

    summary = payload["summary"]
    assert summary["status"] == "api_customer_flow_release_evidence_ready"
    assert summary["formal_release_evidence_ready"] is True
    assert summary["result_manifest_signature_verified"] is True
    assert summary["bundle_validation_ready"] is True
    assert summary["restricted_unattended_runtime_ready"] is True
    assert payload["blockers"] == []


def test_api_customer_flow_release_evidence_uses_operator_environment_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packets, verification = _ready_packets(tmp_path)
    receipt_path = verification.pop("namespace_runtime_receipt_json")
    receipt_sha256 = verification.pop("namespace_runtime_receipt_sha256")
    result_root = verification.pop("result_manifest_root")
    verification.pop("result_manifest_signing_key")
    verification.pop("result_manifest_expected_key_id")
    monkeypatch.setenv(
        "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH",
        str(receipt_path),
    )
    monkeypatch.setenv(
        "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256",
        str(receipt_sha256),
    )
    monkeypatch.setenv("RESULTS_STORAGE_PATH", str(result_root))
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", MANIFEST_SIGNING_KEY)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", MANIFEST_KEY_ID)

    summary = _build(packets, verification)["summary"]

    assert summary["formal_release_evidence_ready"] is True
    assert summary["namespace_runtime_receipt_verified"] is True
    assert summary["result_manifest_verification_reason"] == "verified"


def test_api_customer_flow_release_evidence_ignores_unsigned_verified_flag(
    tmp_path: Path,
) -> None:
    packets, verification = _ready_packets(tmp_path)
    manifest_path = Path(packets["smoke"]["result_manifest"])
    manifest_path.write_text("{}\n", encoding="utf-8")
    forged_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    packets["smoke"]["result_manifest_sha256"] = forged_sha256
    packets["smoke"]["result_manifest_signature_verified"] = True
    packets["restricted"]["summary"][
        "tier_alpha_smoke_manifest_sha256"
    ] = forged_sha256

    summary = _build(packets, verification)["summary"]

    assert summary["formal_release_evidence_ready"] is False
    assert summary["result_manifest_signature_verified"] is False
    assert summary["result_manifest_verification_reason"] == (
        "result_manifest_identity_mismatch"
    )


def test_api_customer_flow_release_evidence_rejects_default_signing_key(
    tmp_path: Path,
) -> None:
    packets, verification = _ready_packets(tmp_path)
    verification["result_manifest_signing_key"] = (
        "tier-alpha-local-smoke-signing-key"
    )
    verification["result_manifest_expected_key_id"] = "tier-alpha-local"

    summary = _build(packets, verification)["summary"]

    assert summary["formal_release_evidence_ready"] is False
    assert summary["result_manifest_signature_verified"] is False
    assert summary["result_manifest_verification_reason"] == (
        "result_manifest_signing_key_unqualified"
    )


def test_api_customer_flow_release_evidence_rejects_result_and_receipt_tamper(
    tmp_path: Path,
) -> None:
    packets, verification = _ready_packets(tmp_path)
    Path(packets["smoke"]["result_file"]).write_text(
        '{"status":"tampered"}\n',
        encoding="utf-8",
    )
    packets["restricted"]["summary"][
        "validated_runner_namespace_runtime_receipt_sha256"
    ] = "0" * 64

    summary = _build(packets, verification)["summary"]

    assert summary["formal_release_evidence_ready"] is False
    assert summary["result_manifest_verification_reason"] == (
        "result_file_sha256_mismatch"
    )
    assert summary["namespace_runtime_receipt_binding_verified"] is False
    assert "validated_runner_namespace_runtime_receipt_sha256" in summary[
        "restricted_receipt_binding_mismatches"
    ]


def test_api_customer_flow_release_evidence_accepts_signed_recovered_live_job(tmp_path: Path) -> None:
    packets, verification = _ready_packets(tmp_path)
    smoke = packets["smoke"]
    smoke["summary"]["evidence_mode"] = "live_job_recovered_from_completed_artifacts"
    smoke["recovered_from_completed_artifacts"] = True
    smoke["result_manifest_signature_verified"] = True
    smoke["result_manifest_status"] = "completed"
    smoke["runner_execution_ok"] = True
    smoke["worker_dispatch_enqueued"] = True
    smoke["ledger_progress_state"] = "worker_dispatch_completed"
    smoke["dispatch_outcome"] = {
        "dispatched": True,
        "reason": "completed_artifact_recovered_after_parent_wait",
        "job_id": JOB_ID,
    }

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=smoke,
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
        **verification,
    )

    summary = payload["summary"]
    assert summary["status"] == "api_customer_flow_release_evidence_ready"
    assert summary["tier_alpha_evidence_mode"] == "live_job_recovered_from_completed_artifacts"
    assert summary["tier_alpha_recovered_live_artifacts_ready"] is True
    assert summary["tier_alpha_worker_dispatch_enqueued"] is True
    assert payload["blockers"] == []


def test_api_customer_flow_release_evidence_blocks_incomplete_recovered_live_job(tmp_path: Path) -> None:
    packets, verification = _ready_packets(tmp_path)
    smoke = packets["smoke"]
    smoke["summary"]["evidence_mode"] = "live_job_recovered_from_completed_artifacts"
    smoke["recovered_from_completed_artifacts"] = True
    smoke["result_manifest_signature_verified"] = True
    smoke["result_manifest_status"] = "completed"
    smoke["runner_execution_ok"] = True
    smoke["worker_dispatch_enqueued"] = False
    smoke["ledger_progress_state"] = "worker_dispatch_completed"
    smoke["dispatch_outcome"] = {
        "dispatched": True,
        "reason": "completed_artifact_recovered_after_parent_wait",
        "job_id": JOB_ID,
    }

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=smoke,
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
        **verification,
    )

    assert payload["summary"]["status"] == "blocked_api_customer_flow_release_evidence"
    assert "worker_lease_and_runner_profile_ready" in payload["summary"]["blocked_check_ids"]


def test_api_customer_flow_release_evidence_blocks_synthetic_only_e2e(tmp_path: Path) -> None:
    packets, verification = _ready_packets(tmp_path)
    packets["e2e"]["summary"]["evidence_mode"] = "synthetic_wiring_proof"

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=packets["smoke"],
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
        **verification,
    )

    assert payload["summary"]["status"] == "blocked_api_customer_flow_release_evidence"
    assert payload["summary"]["blocked_check_ids"] == ["api_dispatch_live_job_ready"]


def test_api_customer_flow_release_evidence_cli_writes_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packets, verification = _ready_packets(tmp_path)
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", MANIFEST_SIGNING_KEY)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", MANIFEST_KEY_ID)
    paths = {name: tmp_path / f"{name}.json" for name in packets}
    for name, packet in packets.items():
        paths[name].write_text(json.dumps(packet) + "\n", encoding="utf-8")
    out_json = tmp_path / "api_flow.json"
    out_csv = tmp_path / "api_flow.csv"
    out_md = tmp_path / "api_flow.md"

    mod.main(
        [
            "--e2e-json",
            str(paths["e2e"]),
            "--restricted-json",
            str(paths["restricted"]),
            "--smoke-json",
            str(paths["smoke"]),
            "--product-bundle-json",
            str(paths["bundle"]),
            "--delivery-evidence-json",
            str(paths["delivery"]),
            "--pilot-json",
            str(paths["pilot"]),
            "--namespace-runtime-receipt-json",
            str(verification["namespace_runtime_receipt_json"]),
            "--namespace-runtime-receipt-sha256",
            str(verification["namespace_runtime_receipt_sha256"]),
            "--result-manifest-root",
            str(verification["result_manifest_root"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "api_customer_flow_release_evidence_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    assert "API Customer Flow Release Evidence" in out_md.read_text(encoding="utf-8")
