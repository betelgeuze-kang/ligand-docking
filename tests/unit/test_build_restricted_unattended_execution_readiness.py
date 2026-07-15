from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import pytest

from api.job_artifacts import create_attempt_results_dir, token_fingerprint
from api.job_store import SQLiteJobStore
from api.result_manifest import write_result_manifest
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    tier_alpha_adrb2_execution_evidence,
)
from api.validated_runner_runtime_qualification import (
    RECEIPT_PATH_ENV,
    RECEIPT_SHA256_ENV,
    validated_runner_namespace_runtime_receipt_template,
)
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle
from tools.product import build_restricted_unattended_execution_readiness as mod


NOW = dt.datetime(2026, 7, 16, tzinfo=dt.timezone.utc)
MANIFEST_SIGNING_KEY = "unit-test-operator-managed-manifest-key"
MANIFEST_KEY_ID = "unit-test-operator-key-2026"
SMOKE_JOB_ID = "tier_alpha_adrb2_smoke_unit"
SMOKE_WORKER_ID = "unit-worker"
SMOKE_REQUEST = {
    "runner_profile_id": "ligand_htvs_pipeline_default",
    "target_name": "ADRB2",
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_namespace_receipt(
    path: Path,
    *,
    issued_minutes_ago: int = 1,
) -> tuple[dict[str, Any], str]:
    payload = validated_runner_namespace_runtime_receipt_template(
        issued_at=NOW - dt.timedelta(minutes=issued_minutes_ago),
        expires_at=NOW + dt.timedelta(hours=1),
    )
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return payload, hashlib.sha256(raw).hexdigest()


def _namespace_binding(
    receipt: dict[str, Any],
    receipt_sha256: str,
) -> dict[str, Any]:
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


def _write_wiring_inputs(runs: Path) -> None:
    _write_json(
        runs / "api_docking_dispatch_e2e_evidence_current.json",
        {
            "summary": {
                "status": "api_docking_dispatch_e2e_ready",
                "wiring_ready": True,
                "evidence_mode": "live_job",
            },
            "ledger_worker_state": "completed_fail_closed",
        },
    )
    _write_json(
        runs / "api_runner_profile_promotion_readiness_current.json",
        {"summary": {"status": "api_runner_profile_promotion_ready"}},
    )
    _write_json(
        runs / "local_delivery_verdict_gate_current.json",
        {"summary": {"delivery_ready": True, "verdict": "delivery_ready"}},
    )
    _write_json(
        runs / "architecture_validation_package_report_current.json",
        {"summary": {"package_a_complete": True}},
    )


def _write_preflight(
    runs: Path,
    binding: dict[str, Any],
    *,
    status: str = "product_image_smoke_preflight_ready",
    product_receipt_binding_matches: bool = True,
) -> None:
    _write_json(
        runs / "product_image_smoke_preflight_current.json",
        {
            "summary": {
                "status": status,
                "preflight_ready": status == "product_image_smoke_preflight_ready",
                "customer_execution_enabled": False,
                "product_receipt_namespace_binding_matches": (
                    product_receipt_binding_matches
                ),
                **binding,
            }
        },
    )


def _write_completed_winner(
    result_root: Path,
    binding: dict[str, Any],
    *,
    signing_key: str = MANIFEST_SIGNING_KEY,
    key_id: str = MANIFEST_KEY_ID,
    created_at: dt.datetime | None = None,
    execution_evidence: dict[str, Any] | None = None,
) -> tuple[Path, Path, str]:
    store = SQLiteJobStore(result_root / f"{SMOKE_JOB_ID}.sqlite3")
    store.create_job(SMOKE_JOB_ID, SMOKE_REQUEST)
    acquired = store.acquire_next_job(SMOKE_WORKER_ID)
    assert acquired is not None
    attempt_token = str(acquired["attempt_token"])
    attempt_count = int(acquired["attempt_count"])
    attempt_token_sha256 = token_fingerprint(attempt_token)
    attempt_dir = create_attempt_results_dir(
        storage_root=result_root,
        job_id=SMOKE_JOB_ID,
        worker_id=SMOKE_WORKER_ID,
        attempt_token=attempt_token,
        attempt_count=attempt_count,
    )
    result_path = attempt_dir / "htvs_summary.json"
    result_path.write_text('{"status":"completed"}\n', encoding="utf-8")
    manifest_path = attempt_dir / "result_manifest.json"
    validated_execution_evidence = (
        execution_evidence
        if execution_evidence is not None
        else tier_alpha_adrb2_execution_evidence(SMOKE_JOB_ID)
    )
    worker_provenance = {
        "worker_id": SMOKE_WORKER_ID,
        "attempt_count": attempt_count,
        "attempt_token_sha256": attempt_token_sha256,
        "validated_runner_runtime_qualification": dict(binding),
        EXECUTION_EVIDENCE_PROVENANCE_KEY: validated_execution_evidence,
    }
    manifest = write_result_manifest(
        manifest_path,
        job_id=SMOKE_JOB_ID,
        request=SMOKE_REQUEST,
        request_sha256=str(acquired["request_sha256"]),
        execution_request_sha256=str(acquired["execution_request_sha256"]),
        execution_request_transform_id=str(
            acquired["execution_request_transform_id"]
        ),
        status="completed",
        result_file=str(result_path),
        signing_key=signing_key,
        key_id=key_id,
        worker_provenance=worker_provenance,
    )
    manifest["created_at_utc"] = (
        created_at or NOW - dt.timedelta(seconds=30)
    ).astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    manifest.pop("signature", None)
    canonical = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    manifest["signature"] = hmac.new(
        signing_key.encode(),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    _write_json(manifest_path, manifest)

    evidence_path = attempt_dir / "evidence_bundle.json"
    evidence = write_api_evidence_bundle(
        evidence_path,
        job_id=SMOKE_JOB_ID,
        request=SMOKE_REQUEST,
        result_manifest=manifest,
        result_payload={"status": "completed"},
        status_payload={"status": "completed"},
    )
    status = {
        "job_id": SMOKE_JOB_ID,
        "status": "completed",
        "result_file": str(result_path),
        "result_manifest": str(manifest_path),
        "evidence_bundle": str(evidence_path),
        "evidence_bundle_sha256": evidence.fingerprint(),
        "worker_provenance": worker_provenance,
        EXECUTION_EVIDENCE_PROVENANCE_KEY: validated_execution_evidence,
        **binding,
    }
    published_status_path = attempt_dir / "published_status.json"
    _write_json(published_status_path, status)
    completed = store.update_job(
        SMOKE_JOB_ID,
        status="completed",
        result_file=str(result_path),
        result_manifest_path=str(manifest_path),
        evidence_bundle_path=str(evidence_path),
        evidence_bundle_sha256=evidence.fingerprint(),
        published_status_path=str(published_status_path),
        published_worker_id=SMOKE_WORKER_ID,
        published_attempt_count=attempt_count,
        published_attempt_token_sha256=attempt_token_sha256,
        expected_worker_id=SMOKE_WORKER_ID,
        expected_attempt_token=attempt_token,
    )
    assert completed is not None

    ledger_root = result_root / "product_docking_jobs"
    ledger_root.mkdir()
    _write_json(
        ledger_root / f"{SMOKE_JOB_ID}.json",
        {
            "job_id": SMOKE_JOB_ID,
            "worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
            "simulation_result_file": str(result_path),
            "last_event_type": "worker_dispatch_completed",
            "event_history": [
                {
                    "event_type": "worker_dispatch_completed",
                    "actor": SMOKE_WORKER_ID,
                    "worker_state": "completed_fail_closed",
                    "simulation_status": "completed",
                    "simulation_result_file": str(result_path),
                }
            ],
        },
    )
    return (
        result_path,
        manifest_path,
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    )


def _configure_manifest_verification(monkeypatch, runs: Path) -> Path:
    result_root = runs / "runtime-results"
    monkeypatch.setenv("RESULTS_STORAGE_PATH", str(result_root))
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", MANIFEST_SIGNING_KEY)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", MANIFEST_KEY_ID)
    return result_root


def _write_smoke(
    runs: Path,
    binding: dict[str, Any],
    *,
    signing_key: str = MANIFEST_SIGNING_KEY,
    key_id: str = MANIFEST_KEY_ID,
    write_manifest: bool = True,
    execution_evidence: dict[str, Any] | None = None,
) -> Path:
    result_root = runs / "runtime-results"
    result_path = result_root / SMOKE_JOB_ID / "htvs_summary.json"
    manifest_path = result_root / SMOKE_JOB_ID / "result_manifest.json"
    manifest_sha256 = "0" * 64
    if write_manifest:
        result_path, manifest_path, manifest_sha256 = _write_completed_winner(
            result_root,
            binding,
            signing_key=signing_key,
            key_id=key_id,
            execution_evidence=execution_evidence,
        )
    _write_json(
        runs / "tier_alpha_adrb2_dispatch_smoke_current.json",
        {
            "summary": {
                "status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "api_validated_runner_enabled": True,
                "validated_runner_namespace_runtime_manifest_binding_verified": True,
                **binding,
            },
            "ledger_worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
            "job_id": SMOKE_JOB_ID,
            "result_manifest": str(manifest_path),
            "result_manifest_sha256": manifest_sha256,
            "result_file": str(result_path),
            "htvs_summary_exists": True,
            "result_manifest_signature_verified": True,
            "result_manifest_status": "completed",
        },
    )
    return result_root


def test_build_restricted_unattended_execution_readiness_requires_live_flag_and_authenticated_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, namespace_receipt_sha256 = _write_namespace_receipt(
        namespace_receipt
    )
    binding = _namespace_binding(receipt_payload, namespace_receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)
    _write_smoke(runs, binding)
    monkeypatch.delenv("API_VALIDATED_RUNNER_ENABLED", raising=False)

    payload = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )
    summary = payload["summary"]
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["restricted_unattended_execution_runtime_ready"] is False
    assert summary["validated_runner_namespace_runtime_qualified"] is True
    assert summary["validated_runner_namespace_runtime_receipt_sha256"] == (
        namespace_receipt_sha256
    )
    assert summary["namespace_preflight_runtime_verified"] is True
    assert summary["tier_alpha_smoke_manifest_binding_verified"] is True
    assert summary["tier_alpha_smoke_manifest_independently_verified"] is True
    assert summary["tier_alpha_smoke_manifest_verification_reason"] == "verified"
    assert summary["tier_alpha_smoke_runtime_verified"] is True
    assert summary["execution_enabled_at_runtime"] is False
    assert summary["customer_execution_enabled"] is False
    assert summary["status"] == "restricted_unattended_execution_wiring_ready"

    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")
    live_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert live_summary["tier_alpha_smoke_runtime_verified"] is True
    assert live_summary["execution_enabled_at_runtime"] is True
    assert live_summary["restricted_unattended_execution_runtime_ready"] is True
    assert live_summary["status"] == "restricted_unattended_execution_runtime_ready"


def test_build_restricted_readiness_rejects_signed_non_winner_attempt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, receipt_sha256 = _write_namespace_receipt(namespace_receipt)
    binding = _namespace_binding(receipt_payload, receipt_sha256)
    _write_preflight(runs, binding)
    result_root = _configure_manifest_verification(monkeypatch, runs)
    _write_smoke(runs, binding)

    smoke_path = runs / "tier_alpha_adrb2_dispatch_smoke_current.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    winner_manifest = json.loads(
        Path(smoke["result_manifest"]).read_text(encoding="utf-8")
    )
    loser_dir = (
        result_root
        / SMOKE_JOB_ID
        / ".attempts"
        / f"attempt-000002-{'c' * 64}-{'d' * 64}"
    )
    loser_dir.mkdir()
    loser_result = loser_dir / "htvs_summary.json"
    loser_result.write_text('{"status":"completed","attempt":"loser"}\n')
    loser_manifest = loser_dir / "result_manifest.json"
    winner_manifest["result_file"] = str(loser_result)
    winner_manifest["result_file_sha256"] = hashlib.sha256(
        loser_result.read_bytes()
    ).hexdigest()
    winner_manifest.pop("signature", None)
    winner_manifest["signature"] = hmac.new(
        MANIFEST_SIGNING_KEY.encode(),
        json.dumps(
            winner_manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    _write_json(loser_manifest, winner_manifest)
    smoke["result_file"] = str(loser_result)
    smoke["result_manifest"] = str(loser_manifest)
    smoke["result_manifest_sha256"] = hashlib.sha256(
        loser_manifest.read_bytes()
    ).hexdigest()
    _write_json(smoke_path, smoke)
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")

    summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]

    assert summary["tier_alpha_smoke_manifest_independently_verified"] is False
    assert summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "published_winner_path_mismatch"
    )
    assert summary["restricted_unattended_execution_runtime_ready"] is False


def test_build_restricted_unattended_execution_readiness_flag_does_not_bypass_paired_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, namespace_receipt_sha256 = _write_namespace_receipt(
        namespace_receipt
    )
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")
    monkeypatch.setenv(RECEIPT_PATH_ENV, str(namespace_receipt))
    monkeypatch.setenv(RECEIPT_SHA256_ENV, namespace_receipt_sha256)

    payload = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_now=NOW
    )
    summary = payload["summary"]
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["restricted_unattended_execution_runtime_ready"] is False
    assert summary["runtime_flag_enabled"] is True
    assert summary["validated_runner_namespace_runtime_qualified"] is True
    assert summary[
        "validated_runner_namespace_runtime_receipt_verification_reason"
    ] == "qualified"
    assert summary["namespace_preflight_runtime_verified"] is False
    assert summary["execution_enabled_at_runtime"] is False
    assert summary["customer_execution_enabled"] is False
    assert summary["status"] == "restricted_unattended_execution_wiring_ready"

    binding = _namespace_binding(receipt_payload, namespace_receipt_sha256)
    _write_preflight(runs, binding)
    paired_receipt_only = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert paired_receipt_only["validated_runner_namespace_runtime_qualified"] is True
    assert paired_receipt_only["namespace_preflight_runtime_verified"] is True
    assert paired_receipt_only["runtime_flag_enabled"] is True
    assert paired_receipt_only["restricted_unattended_execution_runtime_ready"] is False
    assert paired_receipt_only["execution_enabled_at_runtime"] is False

    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "true")
    alias_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert alias_summary["runtime_flag_enabled"] is False
    assert alias_summary["restricted_unattended_execution_runtime_ready"] is False


def test_build_restricted_unattended_execution_readiness_rejects_blocked_and_mismatched_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, namespace_receipt_sha256 = _write_namespace_receipt(
        namespace_receipt
    )
    binding = _namespace_binding(receipt_payload, namespace_receipt_sha256)
    _configure_manifest_verification(monkeypatch, runs)
    _write_smoke(runs, binding)
    _write_preflight(runs, binding, status="blocked_product_image_smoke_preflight")

    blocked_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert blocked_summary["restricted_unattended_execution_ready"] is True
    assert blocked_summary["namespace_preflight_status_ready"] is False
    assert blocked_summary["namespace_preflight_receipt_binding_matches"] is True
    assert blocked_summary["namespace_preflight_runtime_verified"] is False
    assert blocked_summary["restricted_unattended_execution_runtime_ready"] is False

    _write_preflight(runs, binding, product_receipt_binding_matches=False)
    unpaired_product_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert unpaired_product_summary["namespace_preflight_status_ready"] is True
    assert (
        unpaired_product_summary["namespace_preflight_receipt_binding_matches"]
        is True
    )
    assert (
        unpaired_product_summary[
            "namespace_preflight_product_receipt_binding_matches"
        ]
        is False
    )
    assert unpaired_product_summary["namespace_preflight_runtime_verified"] is False
    assert (
        unpaired_product_summary["restricted_unattended_execution_runtime_ready"]
        is False
    )

    mismatched_binding = dict(binding)
    mismatched_binding[
        "validated_runner_namespace_runtime_receipt_sha256"
    ] = "0" * 64
    _write_preflight(runs, mismatched_binding)
    mismatched_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert mismatched_summary["namespace_preflight_status_ready"] is True
    assert mismatched_summary["namespace_preflight_receipt_binding_matches"] is False
    assert "validated_runner_namespace_runtime_receipt_sha256" in mismatched_summary[
        "namespace_preflight_receipt_binding_mismatches"
    ]
    assert mismatched_summary["namespace_preflight_runtime_verified"] is False
    assert mismatched_summary["restricted_unattended_execution_runtime_ready"] is False


def test_build_restricted_unattended_execution_readiness_rejects_smoke_receipt_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, namespace_receipt_sha256 = _write_namespace_receipt(
        namespace_receipt
    )
    binding = _namespace_binding(receipt_payload, namespace_receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)

    replay_receipt = tmp_path / "replayed-namespace-runtime-receipt.json"
    replay_payload, replay_sha256 = _write_namespace_receipt(
        replay_receipt,
        issued_minutes_ago=2,
    )
    _write_smoke(runs, _namespace_binding(replay_payload, replay_sha256))

    summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=namespace_receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert summary["namespace_preflight_runtime_verified"] is True
    assert summary["tier_alpha_smoke_receipt_binding_matches"] is False
    assert summary["tier_alpha_smoke_manifest_binding_verified"] is False
    assert "validated_runner_namespace_runtime_receipt_sha256" in summary[
        "tier_alpha_smoke_receipt_binding_mismatches"
    ]
    assert summary["tier_alpha_smoke_runtime_verified"] is False
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["restricted_unattended_execution_runtime_ready"] is False
    assert summary["status"] == "restricted_unattended_execution_wiring_ready"


def test_build_restricted_unattended_execution_readiness_rejects_forged_smoke_without_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, receipt_sha256 = _write_namespace_receipt(namespace_receipt)
    binding = _namespace_binding(receipt_payload, receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)
    _write_smoke(runs, binding, write_manifest=False)
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")

    summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert summary["tier_alpha_smoke_manifest_independently_verified"] is False
    assert summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "result_manifest_open_failed"
    )
    assert summary["tier_alpha_smoke_manifest_binding_verified"] is False
    assert summary["tier_alpha_smoke_runtime_verified"] is False
    assert summary["execution_enabled_at_runtime"] is False
    assert summary["restricted_unattended_execution_runtime_ready"] is False


def test_build_restricted_unattended_execution_readiness_rejects_default_key_and_symlink_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, receipt_sha256 = _write_namespace_receipt(namespace_receipt)
    binding = _namespace_binding(receipt_payload, receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)
    insecure_key = "tier-alpha-local-smoke-signing-key"
    insecure_key_id = "tier-alpha-local"
    _write_smoke(
        runs,
        binding,
        signing_key=insecure_key,
        key_id=insecure_key_id,
    )
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", insecure_key)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", insecure_key_id)
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")

    insecure_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert insecure_summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "result_manifest_signing_key_unqualified"
    )
    assert insecure_summary["restricted_unattended_execution_runtime_ready"] is False

    smoke_packet = json.loads(
        (runs / "tier_alpha_adrb2_dispatch_smoke_current.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_manifest = Path(smoke_packet["result_manifest"])
    real_manifest = tmp_path / "signed-manifest-copy.json"
    canonical_manifest.replace(real_manifest)
    os.symlink(real_manifest, canonical_manifest)
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", MANIFEST_SIGNING_KEY)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", MANIFEST_KEY_ID)
    smoke_packet["result_manifest_sha256"] = hashlib.sha256(
        real_manifest.read_bytes()
    ).hexdigest()
    _write_json(
        runs / "tier_alpha_adrb2_dispatch_smoke_current.json",
        smoke_packet,
    )

    symlink_summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert symlink_summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "result_manifest_open_failed"
    )
    assert symlink_summary["restricted_unattended_execution_runtime_ready"] is False


def test_build_restricted_unattended_execution_readiness_rejects_foreign_signed_manifest_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, receipt_sha256 = _write_namespace_receipt(namespace_receipt)
    binding = _namespace_binding(receipt_payload, receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)
    foreign_evidence = tier_alpha_adrb2_execution_evidence(SMOKE_JOB_ID)
    foreign_evidence["evidence_purpose"] = "foreign_non_smoke_job"
    _write_smoke(
        runs,
        binding,
        execution_evidence=foreign_evidence,
    )
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")

    summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert summary["tier_alpha_smoke_manifest_independently_verified"] is False
    assert summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "result_manifest_execution_purpose_mismatch"
    )
    assert summary["tier_alpha_smoke_runtime_verified"] is False
    assert summary["restricted_unattended_execution_runtime_ready"] is False


@pytest.mark.parametrize(
    ("placeholder_key", "placeholder_key_id"),
    [
        (
            "replace-with-operator-managed-secret",
            "product-local-tier-alpha",
        ),
        (
            "replace-with-operator-managed-signing-key",
            "product-k8s-local",
        ),
    ],
)
def test_build_restricted_unattended_execution_readiness_rejects_deployment_placeholders(
    tmp_path: Path,
    monkeypatch,
    placeholder_key: str,
    placeholder_key_id: str,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_wiring_inputs(runs)
    namespace_receipt = tmp_path / "namespace-runtime-receipt.json"
    receipt_payload, receipt_sha256 = _write_namespace_receipt(namespace_receipt)
    binding = _namespace_binding(receipt_payload, receipt_sha256)
    _write_preflight(runs, binding)
    _configure_manifest_verification(monkeypatch, runs)
    _write_smoke(
        runs,
        binding,
        signing_key=placeholder_key,
        key_id=placeholder_key_id,
    )
    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", placeholder_key)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", placeholder_key_id)
    monkeypatch.setenv("API_VALIDATED_RUNNER_ENABLED", "1")

    summary = mod.build_restricted_unattended_execution_readiness(
        namespace_runtime_receipt_json=namespace_receipt,
        namespace_runtime_receipt_sha256=receipt_sha256,
        namespace_runtime_now=NOW,
    )["summary"]
    assert summary["tier_alpha_smoke_manifest_verification_reason"] == (
        "result_manifest_signing_key_unqualified"
    )
    assert summary["restricted_unattended_execution_runtime_ready"] is False
