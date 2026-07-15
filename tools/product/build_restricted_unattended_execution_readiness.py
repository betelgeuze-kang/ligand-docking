#!/usr/bin/env python3
"""Gate restricted-scope unattended API execution readiness (Tier α)."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
from urllib.parse import quote

from api.artifact_access import (
    open_confined_regular_file,
    read_confined_json_object,
    verify_completed_result_artifacts,
)
from api.deployment_secret_policy import (
    result_manifest_key_id_is_operator_managed,
    result_manifest_signing_key_is_operator_managed,
)
from api.result_manifest import verify_result_manifest
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    tier_alpha_adrb2_execution_evidence,
    validate_validated_runner_execution_evidence,
)
from api.validated_runner_runtime_qualification import (
    NamespaceRuntimeQualification,
    verify_validated_runner_namespace_runtime,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_E2E_JSON = "runs/api_docking_dispatch_e2e_evidence_current.json"
DEFAULT_PROMOTION_JSON = "runs/api_runner_profile_promotion_readiness_current.json"
DEFAULT_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_ARCH_JSON = "runs/architecture_validation_package_report_current.json"
DEFAULT_SMOKE_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_NAMESPACE_PREFLIGHT_JSON = "runs/product_image_smoke_preflight_current.json"
DEFAULT_OUT_JSON = "runs/restricted_unattended_execution_readiness_current.json"

_MAX_RESULT_MANIFEST_BYTES = 1024 * 1024
_MAX_RESULT_FILE_BYTES = 64 * 1024 * 1024
_MAX_JOB_STORE_BYTES = 128 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ATTEMPT_DIRECTORY_RE = re.compile(
    r"^attempt-[0-9]{6}-[0-9a-f]{64}-[0-9a-f]{64}$"
)

CLAIM_BOUNDARY = (
    "Restricted unattended execution readiness only; it aggregates local wiring, profile promotion, "
    "delivery verdict, and architecture validation signals for gpcr/ion_channel/kinase scope. "
    "It does not enable execution globally, widen scope, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


_NAMESPACE_BINDING_FIELDS = (
    (
        "validated_runner_namespace_runtime_receipt_schema_version",
        "schema_version",
    ),
    ("validated_runner_namespace_runtime_receipt_sha256", "receipt_sha256"),
    (
        "validated_runner_namespace_runtime_receipt_issued_at_utc",
        "issued_at_utc",
    ),
    (
        "validated_runner_namespace_runtime_receipt_expires_at_utc",
        "expires_at_utc",
    ),
)
_NAMESPACE_BINDING_KEYS = (
    "validated_runner_namespace_runtime_qualified",
    *tuple(field for field, _ in _NAMESPACE_BINDING_FIELDS),
)


def _parse_utc_timestamp(value: Any) -> dt.datetime | None:
    if type(value) is not str or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        return None
    return parsed.astimezone(dt.timezone.utc)


def _resolve_manifest_root(path_like: str | Path | None) -> Path | None:
    if path_like is None:
        configured = os.environ.get("RESULTS_STORAGE_PATH", "").strip()
        if not configured:
            return None
        path_like = configured
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return Path(os.path.abspath(str(path)))


def _tier_alpha_job_artifact_path(
    *,
    root: Path,
    job_id: str,
    supplied: Any,
    filename: str,
) -> Path | None:
    if type(supplied) is not str or not supplied:
        return None
    path = Path(supplied).expanduser()
    if not path.is_absolute():
        return None
    path = Path(os.path.abspath(str(path)))
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return None
    canonical_parts = (job_id, filename)
    attempt_parts_valid = bool(
        len(relative_parts) == 4
        and relative_parts[0] == job_id
        and relative_parts[1] == ".attempts"
        and _ATTEMPT_DIRECTORY_RE.fullmatch(relative_parts[2]) is not None
        and relative_parts[3] == filename
    )
    if relative_parts != canonical_parts and not attempt_parts_valid:
        return None
    return path


def _read_completed_job_winner(
    *,
    root: Path,
    job_id: str,
) -> tuple[dict[str, Any], str]:
    """Read the exact smoke job row from its confined SQLite winner store."""

    database_path = root / f"{job_id}.sqlite3"
    try:
        _, database_handle = open_confined_regular_file(
            root,
            database_path,
            label="Tier alpha smoke job store",
        )
        with database_handle:
            before = os.fstat(database_handle.fileno())
            if before.st_size > _MAX_JOB_STORE_BYTES:
                return {}, "job_store_too_large"
            uri = f"file:{quote(str(database_path))}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=5.0) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA query_only=ON")
                row = connection.execute(
                    "SELECT * FROM simulation_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
            after = database_path.stat(follow_symlinks=False)
    except Exception:
        # HTTPException from the confined opener is intentionally normalized to
        # a stable verifier reason; no filesystem detail is exposed downstream.
        return {}, "job_store_open_failed"

    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        return {}, "job_store_changed_during_verification"
    if row is None:
        return {}, "job_store_winner_missing"
    record = dict(row)
    if record.get("status") != "completed" or not str(
        record.get("published_status_path", "") or ""
    ).strip():
        return {}, "job_store_winner_incomplete"
    return record, "verified"


def _verify_published_winner_and_ledger(
    *,
    root: Path,
    job_id: str,
    smoke: dict[str, Any],
    supplied_manifest_path: Path,
    supplied_result_path: Path,
    signing_key: str,
    expected_key_id: str,
) -> tuple[bool, str]:
    record, record_reason = _read_completed_job_winner(root=root, job_id=job_id)
    if not record:
        return False, record_reason

    job_result_root = root / job_id
    published_status_path = str(record.get("published_status_path", "") or "")
    try:
        status = read_confined_json_object(
            job_result_root,
            published_status_path,
            label="Tier alpha published winner status",
            maximum_bytes=16 * 1024 * 1024,
        )
    except Exception:
        return False, "published_status_open_failed"
    if not isinstance(status, dict):
        return False, "published_status_invalid"

    try:
        verified = verify_completed_result_artifacts(
            job_id=job_id,
            record=record,
            status_data=status,
            result_root=job_result_root,
            signing_key=signing_key,
            expected_key_id=expected_key_id,
        )
        try:
            winner_paths_match = bool(
                verified.manifest_path == supplied_manifest_path
                and verified.result_path == supplied_result_path
            )
        finally:
            verified.close()
    except Exception:
        return False, "published_winner_artifact_verification_failed"
    if not winner_paths_match:
        return False, "published_winner_path_mismatch"

    ledger_root = root / "product_docking_jobs"
    try:
        ledger = read_confined_json_object(
            ledger_root,
            ledger_root / f"{job_id}.json",
            label="Tier alpha docking ledger",
            maximum_bytes=16 * 1024 * 1024,
        )
    except Exception:
        return False, "docking_ledger_open_failed"
    if not isinstance(ledger, dict):
        return False, "docking_ledger_invalid"
    events = ledger.get("event_history")
    terminal_event = events[-1] if isinstance(events, list) and events else None
    if not (
        ledger.get("job_id") == job_id
        and ledger.get("worker_state") == "completed_fail_closed"
        and ledger.get("simulation_sync_status") == "completed"
        and ledger.get("simulation_result_file") == str(supplied_result_path)
        and ledger.get("last_event_type") == "worker_dispatch_completed"
        and isinstance(terminal_event, dict)
        and terminal_event.get("event_type") == "worker_dispatch_completed"
        and terminal_event.get("actor") == record.get("published_worker_id")
        and terminal_event.get("worker_state") == "completed_fail_closed"
        and terminal_event.get("simulation_status") == "completed"
        and terminal_event.get("simulation_result_file")
        == str(supplied_result_path)
        and smoke.get("ledger_worker_state") == ledger.get("worker_state")
        and smoke.get("simulation_sync_status")
        == ledger.get("simulation_sync_status")
    ):
        return False, "docking_ledger_binding_failed"
    return True, "verified"


def verify_tier_alpha_smoke_result_manifest(
    *,
    smoke: dict[str, Any],
    verification: NamespaceRuntimeQualification,
    result_manifest_root: str | Path | None,
    signing_key: str | None,
    expected_key_id: str | None,
    now: dt.datetime | None,
) -> tuple[bool, str, str]:
    """Independently open, hash, and authenticate the smoke result manifest."""

    if not verification.qualified:
        return False, "namespace_runtime_not_qualified", ""

    job_id = smoke.get("job_id")
    if type(job_id) is not str or _JOB_ID_RE.fullmatch(job_id) is None:
        return False, "smoke_job_id_invalid", ""

    root = _resolve_manifest_root(result_manifest_root)
    if root is None:
        return False, "result_manifest_root_missing", ""
    unsafe_roots = {
        Path("/"),
        Path(os.path.abspath(str(ROOT))),
        Path(os.path.abspath(str(Path.home()))),
    }
    if root in unsafe_roots:
        return False, "result_manifest_root_unsafe", ""
    if not smoke.get("result_manifest"):
        return False, "result_manifest_path_missing", ""
    supplied_path = _tier_alpha_job_artifact_path(
        root=root,
        job_id=job_id,
        supplied=smoke.get("result_manifest"),
        filename="result_manifest.json",
    )
    if supplied_path is None:
        return False, "result_manifest_path_not_canonical", ""

    try:
        _, handle = open_confined_regular_file(
            root,
            supplied_path,
            label="Tier alpha smoke result manifest",
        )
        with handle:
            raw_manifest = handle.read(_MAX_RESULT_MANIFEST_BYTES + 1)
    except Exception:
        return False, "result_manifest_open_failed", ""
    if len(raw_manifest) > _MAX_RESULT_MANIFEST_BYTES:
        return False, "result_manifest_too_large", ""
    manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
    claimed_sha256 = smoke.get("result_manifest_sha256")
    if (
        type(claimed_sha256) is not str
        or _SHA256_RE.fullmatch(claimed_sha256) is None
        or claimed_sha256 != manifest_sha256
    ):
        return False, "result_manifest_sha256_mismatch", manifest_sha256
    try:
        manifest = json.loads(raw_manifest)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "result_manifest_json_invalid", manifest_sha256
    if not isinstance(manifest, dict):
        return False, "result_manifest_root_invalid", manifest_sha256

    resolved_signing_key = (
        signing_key
        if signing_key is not None
        else os.environ.get("API_RESULT_MANIFEST_SIGNING_KEY", "")
    )
    if not result_manifest_signing_key_is_operator_managed(resolved_signing_key):
        return False, "result_manifest_signing_key_unqualified", manifest_sha256
    resolved_key_id = (
        expected_key_id
        if expected_key_id is not None
        else os.environ.get("API_RESULT_MANIFEST_KEY_ID", "")
    )
    if not result_manifest_key_id_is_operator_managed(resolved_key_id):
        return False, "result_manifest_key_id_unqualified", manifest_sha256
    if (
        manifest.get("manifest_version") != "api_result_manifest_v1"
        or manifest.get("signature_algorithm") != "hmac-sha256"
        or type(manifest.get("job_id")) is not str
        or manifest.get("job_id") != job_id
        or manifest.get("status") != "completed"
        or type(manifest.get("signature_key_id")) is not str
        or manifest.get("signature_key_id") != resolved_key_id
    ):
        return False, "result_manifest_identity_mismatch", manifest_sha256
    if not verify_result_manifest(manifest, signing_key=resolved_signing_key):
        return False, "result_manifest_signature_invalid", manifest_sha256

    result_path = _tier_alpha_job_artifact_path(
        root=root,
        job_id=job_id,
        supplied=manifest.get("result_file"),
        filename="htvs_summary.json",
    )
    smoke_result_path = _tier_alpha_job_artifact_path(
        root=root,
        job_id=job_id,
        supplied=smoke.get("result_file"),
        filename="htvs_summary.json",
    )
    if (
        result_path is None
        or smoke_result_path is None
        or result_path != smoke_result_path
        or result_path.parent != supplied_path.parent
    ):
        return False, "result_file_path_mismatch", manifest_sha256
    try:
        _, result_handle = open_confined_regular_file(
            root,
            result_path,
            label="Tier alpha smoke result file",
        )
        with result_handle:
            raw_result = result_handle.read(_MAX_RESULT_FILE_BYTES + 1)
    except Exception:
        return False, "result_file_open_failed", manifest_sha256
    if len(raw_result) > _MAX_RESULT_FILE_BYTES:
        return False, "result_file_too_large", manifest_sha256
    result_sha256 = hashlib.sha256(raw_result).hexdigest()
    signed_result_sha256 = manifest.get("result_file_sha256")
    if (
        type(signed_result_sha256) is not str
        or _SHA256_RE.fullmatch(signed_result_sha256) is None
        or signed_result_sha256 != result_sha256
    ):
        return False, "result_file_sha256_mismatch", manifest_sha256

    worker_provenance = manifest.get("worker_provenance")
    if not isinstance(worker_provenance, dict):
        return False, "result_manifest_worker_provenance_missing", manifest_sha256
    qualification = worker_provenance.get(
        "validated_runner_runtime_qualification"
    )
    if (
        not isinstance(qualification, dict)
        or set(qualification) != set(_NAMESPACE_BINDING_KEYS)
        or namespace_runtime_binding_mismatches(qualification, verification)
    ):
        return False, "result_manifest_receipt_binding_mismatch", manifest_sha256

    signed_execution_evidence = worker_provenance.get(
        EXECUTION_EVIDENCE_PROVENANCE_KEY
    )
    try:
        validated_execution_evidence = (
            validate_validated_runner_execution_evidence(
                signed_execution_evidence
            )
        )
    except ValueError:
        return False, "result_manifest_execution_evidence_invalid", manifest_sha256
    if validated_execution_evidence != tier_alpha_adrb2_execution_evidence(job_id):
        return False, "result_manifest_execution_purpose_mismatch", manifest_sha256

    created_at = _parse_utc_timestamp(manifest.get("created_at_utc"))
    issued_at = _parse_utc_timestamp(verification.issued_at_utc)
    expires_at = _parse_utc_timestamp(verification.expires_at_utc)
    verification_now = now or dt.datetime.now(dt.timezone.utc)
    if verification_now.tzinfo is None:
        verification_now = verification_now.replace(tzinfo=dt.timezone.utc)
    verification_now = verification_now.astimezone(dt.timezone.utc)
    if (
        created_at is None
        or issued_at is None
        or expires_at is None
        or not issued_at <= created_at <= expires_at
        or created_at > verification_now
    ):
        return False, "result_manifest_timestamp_outside_receipt", manifest_sha256

    winner_verified, winner_reason = _verify_published_winner_and_ledger(
        root=root,
        job_id=job_id,
        smoke=smoke,
        supplied_manifest_path=supplied_path,
        supplied_result_path=result_path,
        signing_key=resolved_signing_key,
        expected_key_id=resolved_key_id,
    )
    if not winner_verified:
        return False, winner_reason, manifest_sha256
    return True, "verified", manifest_sha256


def namespace_runtime_binding_mismatches(
    summary: dict[str, Any],
    verification: NamespaceRuntimeQualification,
) -> list[str]:
    mismatches: list[str] = []
    if summary.get("validated_runner_namespace_runtime_qualified") is not True:
        mismatches.append("validated_runner_namespace_runtime_qualified")
    for field, qualification_field in _NAMESPACE_BINDING_FIELDS:
        observed = summary.get(field)
        expected = getattr(verification, qualification_field)
        if type(observed) is not str or observed != expected:
            mismatches.append(field)
    return mismatches


def build_restricted_unattended_execution_readiness(
    *,
    e2e_json: str = DEFAULT_E2E_JSON,
    promotion_json: str = DEFAULT_PROMOTION_JSON,
    verdict_json: str = DEFAULT_VERDICT_JSON,
    arch_json: str = DEFAULT_ARCH_JSON,
    smoke_json: str = DEFAULT_SMOKE_JSON,
    namespace_preflight_json: str = DEFAULT_NAMESPACE_PREFLIGHT_JSON,
    namespace_runtime_receipt_json: str | Path | None = None,
    namespace_runtime_receipt_sha256: str | None = None,
    namespace_runtime_now: dt.datetime | None = None,
    result_manifest_root: str | Path | None = None,
    result_manifest_signing_key: str | None = None,
    result_manifest_expected_key_id: str | None = None,
) -> dict[str, Any]:
    e2e = _read_json(e2e_json)
    e2e_summary = _summary(e2e)
    promotion = _summary(_read_json(promotion_json))
    verdict = _summary(_read_json(verdict_json))
    arch = _summary(_read_json(arch_json))
    smoke = _read_json(smoke_json)
    smoke_summary = _summary(smoke)
    namespace_preflight = _summary(_read_json(namespace_preflight_json))
    resolved_namespace_runtime_receipt: str | Path | None = (
        namespace_runtime_receipt_json
    )
    if resolved_namespace_runtime_receipt is not None:
        receipt_path = Path(resolved_namespace_runtime_receipt)
        if not receipt_path.is_absolute():
            receipt_path = _resolve(receipt_path)
        resolved_namespace_runtime_receipt = receipt_path
    namespace_runtime_verification: NamespaceRuntimeQualification = (
        verify_validated_runner_namespace_runtime(
            receipt_path=resolved_namespace_runtime_receipt,
            expected_sha256=namespace_runtime_receipt_sha256,
            now=namespace_runtime_now,
        )
    )
    namespace_runtime_qualified = namespace_runtime_verification.qualified

    namespace_preflight_binding_mismatches = namespace_runtime_binding_mismatches(
        namespace_preflight,
        namespace_runtime_verification,
    )
    namespace_preflight_binding_matches = bool(
        namespace_runtime_qualified and not namespace_preflight_binding_mismatches
    )
    namespace_preflight_status_ready = (
        namespace_preflight.get("status")
        == "product_image_smoke_preflight_ready"
        and namespace_preflight.get("preflight_ready") is True
    )
    namespace_preflight_customer_execution_disabled = (
        namespace_preflight.get("customer_execution_enabled") is False
    )
    namespace_preflight_product_receipt_binding_matches = (
        namespace_preflight.get("product_receipt_namespace_binding_matches") is True
    )
    namespace_preflight_runtime_verified = bool(
        namespace_runtime_qualified
        and namespace_preflight_status_ready
        and namespace_preflight_customer_execution_disabled
        and namespace_preflight_product_receipt_binding_matches
        and namespace_preflight_binding_matches
    )

    smoke_binding_mismatches = namespace_runtime_binding_mismatches(
        smoke_summary,
        namespace_runtime_verification,
    )
    smoke_binding_matches = bool(
        namespace_runtime_qualified and not smoke_binding_mismatches
    )
    (
        smoke_manifest_independently_verified,
        smoke_manifest_verification_reason,
        smoke_manifest_sha256,
    ) = verify_tier_alpha_smoke_result_manifest(
        smoke=smoke,
        verification=namespace_runtime_verification,
        result_manifest_root=result_manifest_root,
        signing_key=result_manifest_signing_key,
        expected_key_id=result_manifest_expected_key_id,
        now=namespace_runtime_now,
    )
    smoke_manifest_binding_verified = bool(
        smoke_manifest_independently_verified
        and smoke_binding_matches
    )
    smoke_runtime = bool(
        namespace_preflight_runtime_verified
        and smoke_summary.get("status")
        == "tier_alpha_adrb2_dispatch_smoke_pass"
        and smoke_summary.get("api_validated_runner_enabled") is True
        and smoke.get("ledger_worker_state") == "completed_fail_closed"
        and smoke.get("simulation_sync_status") == "completed"
        and smoke_manifest_binding_verified
    )

    runtime_flag_enabled = (
        os.environ.get("API_VALIDATED_RUNNER_ENABLED", "0").strip() == "1"
    )
    runtime_runner_enabled = bool(runtime_flag_enabled and smoke_runtime)

    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "gate_id": "api_dispatch_e2e_wiring",
            "status": "pass" if e2e_summary.get("wiring_ready") is True else "blocked",
            "observed": f"e2e_status={e2e_summary.get('status')};ledger={e2e.get('ledger_worker_state')}",
            "required": "api_docking_dispatch_e2e_ready with completed_fail_closed ledger state",
        }
    )
    rows.append(
        {
            "gate_id": "runner_profile_promotion",
            "status": "pass" if _text(promotion.get("status")) == "api_runner_profile_promotion_ready" else "blocked",
            "observed": _text(promotion.get("status")),
            "required": "api_runner_profile_promotion_ready",
        }
    )
    rows.append(
        {
            "gate_id": "local_delivery_verdict",
            "status": "pass" if _bool(verdict.get("delivery_ready")) else "blocked",
            "observed": _text(verdict.get("verdict")),
            "required": "delivery_ready=true",
        }
    )
    package_a = _bool(arch.get("package_a_complete"))
    rows.append(
        {
            "gate_id": "architecture_validation_package_a",
            "status": "pass" if package_a else "blocked",
            "observed": f"package_a_complete={arch.get('package_a_complete')}",
            "required": "package_a_complete=true",
        }
    )
    rows.append(
        {
            "gate_id": "runtime_api_validated_runner_enabled",
            "status": "pass" if runtime_runner_enabled else "operator_pending",
            "observed": (
                f"API_VALIDATED_RUNNER_ENABLED={os.environ.get('API_VALIDATED_RUNNER_ENABLED', '0')};"
                f"smoke_runtime={smoke_runtime};"
                f"namespace_receipt={namespace_runtime_verification.reason}"
            ),
            "required": (
                "API_VALIDATED_RUNNER_ENABLED=1, an independently verified namespace receipt, "
                "an exactly paired ready product preflight, and a passing Tier alpha smoke bound "
                "to an independently opened and authenticated result manifest"
            ),
        }
    )

    hard_blocked = [row for row in rows if row["status"] == "blocked"]
    wiring_ready = e2e_summary.get("wiring_ready") is True and not hard_blocked
    runtime_live = wiring_ready and runtime_runner_enabled

    return {
        "summary": {
            "packet_type": "restricted_unattended_execution_readiness",
            "status": (
                "restricted_unattended_execution_runtime_ready"
                if runtime_live
                else "restricted_unattended_execution_wiring_ready"
                if wiring_ready
                else "blocked_restricted_unattended_execution_readiness"
            ),
            "restricted_unattended_execution_ready": wiring_ready,
            "restricted_unattended_execution_runtime_ready": runtime_live,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "general_platform_claim_allowed": False,
            "execution_enabled_at_runtime": runtime_runner_enabled,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "runtime_flag_enabled": runtime_flag_enabled,
            "validated_runner_namespace_runtime_qualified": (
                namespace_runtime_qualified
            ),
            "validated_runner_namespace_runtime_receipt_schema_version": (
                namespace_runtime_verification.schema_version
            ),
            "validated_runner_namespace_runtime_receipt_sha256": (
                namespace_runtime_verification.receipt_sha256
            ),
            "validated_runner_namespace_runtime_receipt_verification_reason": (
                namespace_runtime_verification.reason
            ),
            "validated_runner_namespace_runtime_receipt_issued_at_utc": (
                namespace_runtime_verification.issued_at_utc
            ),
            "validated_runner_namespace_runtime_receipt_expires_at_utc": (
                namespace_runtime_verification.expires_at_utc
            ),
            "namespace_preflight_status": _text(namespace_preflight.get("status")),
            "namespace_preflight_status_ready": namespace_preflight_status_ready,
            "namespace_preflight_receipt_binding_matches": (
                namespace_preflight_binding_matches
            ),
            "namespace_preflight_receipt_binding_mismatches": (
                namespace_preflight_binding_mismatches
            ),
            "namespace_preflight_customer_execution_disabled": (
                namespace_preflight_customer_execution_disabled
            ),
            "namespace_preflight_product_receipt_binding_matches": (
                namespace_preflight_product_receipt_binding_matches
            ),
            "namespace_preflight_runtime_verified": (
                namespace_preflight_runtime_verified
            ),
            "tier_alpha_smoke_manifest_binding_verified": (
                smoke_manifest_binding_verified
            ),
            "tier_alpha_smoke_manifest_independently_verified": (
                smoke_manifest_independently_verified
            ),
            "tier_alpha_smoke_manifest_verification_reason": (
                smoke_manifest_verification_reason
            ),
            "tier_alpha_smoke_manifest_sha256": smoke_manifest_sha256,
            "tier_alpha_smoke_receipt_binding_matches": smoke_binding_matches,
            "tier_alpha_smoke_receipt_binding_mismatches": (
                smoke_binding_mismatches
            ),
            "tier_alpha_smoke_runtime_verified": smoke_runtime,
            "customer_execution_enabled": False,
            "claim_promotion_allowed": False,
            "gate_count": len(rows),
            "blocked_gate_count": len(hard_blocked),
            "operator_pending_gate_count": sum(1 for row in rows if row["status"] == "operator_pending"),
            "claim_boundary": CLAIM_BOUNDARY,
            "next_action": (
                "Qualify a namespace-capable host runtime, then enable and run the live ADRB2 dispatch smoke."
                if wiring_ready and not runtime_runner_enabled
                else "Repair blocked gates before unattended execution promotion."
                if hard_blocked
                else "Maintain restricted-scope dispatch SLA and profile rollback path."
            ),
        },
        "rows": rows,
        "tier_alpha_smoke_artifact": smoke_json if smoke else "",
        "e2e_ledger_worker_state": e2e.get("ledger_worker_state"),
        "e2e_evidence_mode": e2e_summary.get("evidence_mode"),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build restricted unattended execution readiness gate.")
    parser.add_argument("--e2e-json", default=DEFAULT_E2E_JSON)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--verdict-json", default=DEFAULT_VERDICT_JSON)
    parser.add_argument("--arch-json", default=DEFAULT_ARCH_JSON)
    parser.add_argument("--smoke-json", default=DEFAULT_SMOKE_JSON)
    parser.add_argument(
        "--namespace-preflight-json",
        default=DEFAULT_NAMESPACE_PREFLIGHT_JSON,
    )
    parser.add_argument("--namespace-runtime-receipt-json", default=None)
    parser.add_argument("--namespace-runtime-receipt-sha256", default=None)
    parser.add_argument(
        "--result-manifest-root",
        default=None,
        help=(
            "Trusted results-storage root containing the published Tier alpha "
            "winner attempt; "
            "defaults to RESULTS_STORAGE_PATH and fails closed when neither is set"
        ),
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_restricted_unattended_execution_readiness(
        e2e_json=args.e2e_json,
        promotion_json=args.promotion_json,
        verdict_json=args.verdict_json,
        arch_json=args.arch_json,
        smoke_json=args.smoke_json,
        namespace_preflight_json=args.namespace_preflight_json,
        namespace_runtime_receipt_json=args.namespace_runtime_receipt_json,
        namespace_runtime_receipt_sha256=args.namespace_runtime_receipt_sha256,
        result_manifest_root=args.result_manifest_root,
    )
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
