from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import asyncio
from contextlib import suppress
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat

from api.config import settings
from api.job_artifacts import (
    activate_attempt_results_dir,
    create_attempt_results_dir,
    reset_attempt_results_dir,
    resolve_job_results_dir,
    token_fingerprint,
)
from api.job_store import (
    EXECUTION_REQUEST_TRANSFORM_ID,
    SQLiteJobStore,
    canonical_request_sha256,
)
from api.result_manifest import write_result_manifest
from api.tasks import run_simulation_async
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle

SimulationRunner = Callable[[str, dict[str, Any]], Awaitable[None]]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class JobIntegrityError(RuntimeError):
    """Raised when durable request provenance does not bind the runner input."""


class JobLeaseLostError(RuntimeError):
    """Raised when a worker no longer owns a live lease for the job."""


@dataclass(frozen=True)
class InitialStatusFileReceipt:
    path: str
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int
    content_sha256: str
    directory: str
    directory_device: int
    directory_inode: int


def _sync_docking_ledger_if_needed(
    *,
    job_id: str,
    request_data: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
    worker_id: str = "",
) -> None:
    params = request_data.get("runner_profile_params", {})
    if not isinstance(params, dict):
        return
    docking_job_id = str(params.get("docking_job_id", "") or "").strip()
    if not docking_job_id:
        return
    try:
        from pathlib import Path

        from api.docking_dispatch import sync_ledger_from_simulation_result

        jobs_dir = Path(settings.results_storage_path) / "product_docking_jobs"
        sync_ledger_from_simulation_result(
            jobs_dir,
            docking_job_id,
            status=status,
            result_file=result_file,
            error=error,
            worker_id=worker_id,
        )
    except Exception:
        return


def job_results_dir(job_id: str) -> str:
    return str(resolve_job_results_dir(job_id, settings.results_storage_path))


def job_status_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "status.json")


def job_manifest_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "result_manifest.json")


def job_evidence_bundle_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "evidence_bundle.json")


def read_status_file(status_file_path: str) -> dict[str, Any]:
    if not os.path.exists(status_file_path):
        return {}
    with open(status_file_path, "r", encoding="utf-8") as sf:
        return json.load(sf)


def read_json_object_file(file_path: str) -> dict[str, Any]:
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_status_file(status_file_path: str, status_data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(status_file_path), exist_ok=True)
    with open(status_file_path, "w", encoding="utf-8") as sf:
        json.dump(status_data, sf)


def create_initial_status_file(job_id: str) -> InitialStatusFileReceipt:
    """Create the admission status file exclusively before publishing a DB job."""

    results_root = Path(settings.results_storage_path)
    results_root.mkdir(parents=True, exist_ok=True)
    results_dir = Path(job_results_dir(job_id))
    results_dir.mkdir(mode=0o700, exist_ok=False)
    directory_stat = results_dir.stat(follow_symlinks=False)
    status_path = Path(job_status_path(job_id))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    file_stat: os.stat_result | None = None
    encoded_status = json.dumps(
        {"job_id": job_id, "status": "submitted"}
    ).encode("utf-8")
    try:
        fd = os.open(status_path, flags, 0o600)
        file_stat = os.fstat(fd)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(encoded_status)
            handle.flush()
            os.fsync(handle.fileno())
            file_stat = os.fstat(handle.fileno())
    except Exception:
        if fd >= 0:
            os.close(fd)
        if file_stat is not None:
            with suppress(OSError):
                current = status_path.lstat()
                if (
                    stat.S_ISREG(current.st_mode)
                    and current.st_dev == file_stat.st_dev
                    and current.st_ino == file_stat.st_ino
                ):
                    status_path.unlink()
        with suppress(OSError):
            results_dir.rmdir()
        raise
    assert file_stat is not None
    return InitialStatusFileReceipt(
        path=str(status_path),
        device=file_stat.st_dev,
        inode=file_stat.st_ino,
        size=file_stat.st_size,
        modified_ns=file_stat.st_mtime_ns,
        changed_ns=file_stat.st_ctime_ns,
        content_sha256=hashlib.sha256(encoded_status).hexdigest(),
        directory=str(results_dir),
        directory_device=directory_stat.st_dev,
        directory_inode=directory_stat.st_ino,
    )


def cleanup_initial_status_file(receipt: InitialStatusFileReceipt) -> bool:
    """Remove only the exact file created by ``create_initial_status_file``."""

    path = Path(receipt.path)
    try:
        current = path.lstat()
    except OSError:
        return False
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_dev != receipt.device
        or current.st_ino != receipt.inode
        or current.st_size != receipt.size
        or current.st_mtime_ns != receipt.modified_ns
        or current.st_ctime_ns != receipt.changed_ns
    ):
        return False
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.content_sha256:
            return False
    except OSError:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    directory = Path(receipt.directory)
    try:
        current_dir = directory.stat(follow_symlinks=False)
        if (
            stat.S_ISDIR(current_dir.st_mode)
            and current_dir.st_dev == receipt.directory_device
            and current_dir.st_ino == receipt.directory_inode
        ):
            directory.rmdir()
    except OSError:
        pass
    return True


def write_job_result_manifest(
    *,
    job_id: str,
    request_data: dict[str, Any],
    request_sha256: str = "",
    execution_request_sha256: str = "",
    execution_request_transform_id: str = "",
    status: str,
    result_file: str = "",
    error: str = "",
    worker_provenance: dict[str, Any] | None = None,
) -> str:
    manifest_path = job_manifest_path(job_id)
    write_result_manifest(
        manifest_path,
        job_id=job_id,
        request=request_data,
        status=status,
        request_sha256=request_sha256 or None,
        execution_request_sha256=execution_request_sha256 or None,
        execution_request_transform_id=execution_request_transform_id or None,
        result_file=result_file,
        error=error,
        signing_key=settings.api_result_manifest_signing_key,
        key_id=settings.api_result_manifest_key_id,
        worker_provenance=worker_provenance,
    )
    return manifest_path


def write_job_evidence_bundle(
    *,
    job_id: str,
    request_data: dict[str, Any],
    result_manifest_path: str,
    status_data: dict[str, Any],
    request_sha256: str = "",
    execution_request_sha256: str = "",
    execution_request_transform_id: str = "",
) -> tuple[str, str]:
    adopted_native = adopt_validated_runner_native_evidence_bundle(
        job_id=job_id,
        status_data=status_data,
        request_sha256=request_sha256,
        execution_request_sha256=execution_request_sha256,
        execution_request_transform_id=execution_request_transform_id,
    )
    if adopted_native is not None:
        return adopted_native
    result_manifest = read_json_object_file(result_manifest_path)
    result_payload = {}
    result_file = str(result_manifest.get("result_file", "") or status_data.get("result_file", "") or "")
    if result_file:
        result_payload = read_json_object_file(result_file)
    runner_execution = {}
    runner_execution_path = str(status_data.get("runner_execution", "") or "")
    if runner_execution_path:
        runner_execution = read_json_object_file(runner_execution_path)
    bundle_path = job_evidence_bundle_path(job_id)
    bundle = write_api_evidence_bundle(
        bundle_path,
        job_id=job_id,
        request=request_data,
        result_manifest=result_manifest,
        result_payload=result_payload,
        runner_execution=runner_execution,
        status_payload=status_data,
    )
    return bundle_path, bundle.fingerprint()


def adopt_validated_runner_native_evidence_bundle(
    *,
    job_id: str,
    status_data: dict[str, Any],
    request_sha256: str = "",
    execution_request_sha256: str = "",
    execution_request_transform_id: str = "",
) -> tuple[str, str] | None:
    """Adopt a validated-runner-native EvidenceBundle as the final worker bundle.

    Returns ``(bundle_path, fingerprint)`` when a validated native bundle is recorded
    in the status file. Returns ``None`` when the runner did not produce or validate
    a native bundle so the caller can fall back to the API-generated review bundle.
    """
    if str(status_data.get("evidence_bundle_source", "") or "").strip() != "validated_runner_native":
        return None
    bundle_path_value = str(status_data.get("evidence_bundle", "") or "").strip()
    bundle_sha_value = str(status_data.get("evidence_bundle_sha256", "") or "").strip()
    if not bundle_path_value or not bundle_sha_value:
        return None
    if len(bundle_sha_value) != 64:
        return None
    bundle_path = Path(bundle_path_value)
    if not bundle_path.exists() or not bundle_path.is_file():
        return None
    payload = read_json_object_file(str(bundle_path))
    if not payload:
        return None
    try:
        from betelgeuze_ai_md.contracts import EvidenceBundle
        from betelgeuze_ai_md.contracts.errors import ContractValidationError

        bundle = EvidenceBundle(**payload)
    except (ContractValidationError, TypeError):
        return None
    if bundle.fingerprint() != bundle_sha_value:
        return None
    if request_sha256 or execution_request_sha256 or execution_request_transform_id:
        enriched_payload = bundle.to_dict()
        source_hashes = dict(enriched_payload.get("source_hashes") or {})
        source_hashes["input_hash"] = execution_request_sha256
        enriched_payload["source_hashes"] = source_hashes
        enriched_payload["request_provenance"] = {
            "admission_request_sha256": request_sha256,
            "execution_request_sha256": execution_request_sha256,
            "execution_request_transform_id": execution_request_transform_id,
        }
        try:
            bundle = EvidenceBundle(**enriched_payload)
        except (ContractValidationError, TypeError):
            return None
    final_path = Path(job_evidence_bundle_path(job_id))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(final_path), bundle.fingerprint()


def _durable_request_provenance(record: dict[str, Any]) -> tuple[str, str, str]:
    admission_sha256 = str(record.get("request_sha256", "") or "").lower()
    execution_sha256 = str(record.get("execution_request_sha256", "") or "").lower()
    transform_id = str(record.get("execution_request_transform_id", "") or "").strip()
    if _SHA256_RE.fullmatch(admission_sha256) is None:
        raise JobIntegrityError("durable admission request fingerprint is invalid")
    if _SHA256_RE.fullmatch(execution_sha256) is None:
        raise JobIntegrityError("durable execution request fingerprint is invalid")
    if transform_id != EXECUTION_REQUEST_TRANSFORM_ID:
        raise JobIntegrityError("durable execution request transform is unsupported")
    return admission_sha256, execution_sha256, transform_id


def _verify_execution_request(
    execution_sha256: str,
    request_data: dict[str, Any],
) -> None:
    observed_sha256 = canonical_request_sha256(request_data)
    if not hmac.compare_digest(observed_sha256, execution_sha256):
        raise JobIntegrityError("execution request integrity verification failed")


def _require_live_worker_lease(
    store: SQLiteJobStore,
    *,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    lease_seconds: int,
) -> dict[str, Any]:
    record = store.heartbeat_job(
        job_id,
        worker_id,
        attempt_token=attempt_token,
        lease_seconds=lease_seconds,
    )
    if record is None:
        raise JobLeaseLostError(f"worker lease lost for job {job_id}")
    return record


def _write_status_best_effort(path: str, payload: dict[str, Any]) -> None:
    try:
        write_status_file(path, payload)
    except (OSError, TypeError, ValueError):
        return


def _publish_canonical_status_best_effort(
    path: str,
    payload: dict[str, Any],
) -> None:
    """Atomically publish a terminal winner mirror after its durable CAS."""

    target = Path(path)
    temp = target.with_name(f".{target.name}.{secrets.token_hex(16)}.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_status_file(str(temp), payload)
        with temp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (OSError, TypeError, ValueError):
        with suppress(OSError):
            temp.unlink()


def _worker_attempt_provenance(
    *,
    worker_id: str,
    attempt_token: str,
    attempt_count: int,
) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "attempt_count": attempt_count,
        "attempt_token_sha256": token_fingerprint(attempt_token),
    }


def _require_attempt_artifact_path(
    path_value: str,
    *,
    attempt_results_dir: Path,
    label: str,
) -> None:
    if not path_value:
        return
    try:
        resolved_path = Path(path_value).resolve(strict=True)
        resolved_attempt_dir = attempt_results_dir.resolve(strict=True)
    except OSError as exc:
        raise JobIntegrityError(f"{label} is unavailable for the live attempt") from exc
    if resolved_attempt_dir not in resolved_path.parents:
        raise JobIntegrityError(f"{label} escapes the live attempt artifact directory")


async def run_job_once(
    store: SQLiteJobStore,
    *,
    job_id: str,
    request_data: dict[str, Any],
    runner: SimulationRunner = run_simulation_async,
    worker_id: str = "",
    attempt_token: str = "",
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
    retry_on_failure: bool = False,
) -> dict[str, Any]:
    """Run one job with request-integrity and exact-attempt publication."""

    canonical_status_file_path = str(
        Path(settings.results_storage_path) / job_id / "status.json"
    )
    status_file_path = canonical_status_file_path
    durable_record: dict[str, Any] = {}
    admission_sha256 = ""
    execution_sha256 = ""
    transform_id = ""
    status_data: dict[str, Any] = {}
    attempt_count = 0
    attempt_results_dir: Path | None = None
    artifact_binding_token = None
    worker_provenance: dict[str, Any] | None = None

    try:
        if worker_id:
            if not attempt_token:
                raise JobLeaseLostError(
                    f"worker attempt token is required for job {job_id}"
                )
            durable_record = _require_live_worker_lease(
                store,
                job_id=job_id,
                worker_id=worker_id,
                attempt_token=attempt_token,
                lease_seconds=lease_seconds,
            )
            attempt_count = int(durable_record.get("attempt_count", 0) or 0)
            attempt_results_dir = create_attempt_results_dir(
                storage_root=settings.results_storage_path,
                job_id=job_id,
                worker_id=worker_id,
                attempt_token=attempt_token,
                attempt_count=attempt_count,
            )
            artifact_binding_token = activate_attempt_results_dir(
                job_id,
                attempt_results_dir,
            )
            status_file_path = job_status_path(job_id)
            worker_provenance = _worker_attempt_provenance(
                worker_id=worker_id,
                attempt_token=attempt_token,
                attempt_count=attempt_count,
            )
        else:
            durable_record = store.update_job(job_id, status="running") or {}
        if not durable_record:
            raise JobIntegrityError("durable simulation job is missing")

        admission_sha256, execution_sha256, transform_id = _durable_request_provenance(
            durable_record
        )
        _verify_execution_request(execution_sha256, request_data)

        status_data = read_status_file(
            canonical_status_file_path if worker_id else status_file_path
        )
        status_data.update({"job_id": job_id, "status": "running"})
        if worker_provenance is not None:
            status_data["worker_provenance"] = worker_provenance
        write_status_file(status_file_path, status_data)

        if worker_id:
            await _run_with_periodic_heartbeat(
                store,
                job_id=job_id,
                worker_id=worker_id,
                attempt_token=attempt_token,
                runner=runner,
                request_data=request_data,
                lease_seconds=lease_seconds,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
            )
            _require_live_worker_lease(
                store,
                job_id=job_id,
                worker_id=worker_id,
                attempt_token=attempt_token,
                lease_seconds=lease_seconds,
            )
        else:
            await runner(job_id, request_data)

        status_data = read_status_file(status_file_path)
        if worker_provenance is not None:
            status_data["worker_provenance"] = worker_provenance
        result_file = str(status_data.get("result_file", "") or "")
        if attempt_results_dir is not None:
            if not result_file:
                raise JobIntegrityError("runner did not record a result file")
            for artifact_key in ("result_file", "runner_execution", "evidence_bundle"):
                _require_attempt_artifact_path(
                    str(status_data.get(artifact_key, "") or ""),
                    attempt_results_dir=attempt_results_dir,
                    label=artifact_key.replace("_", " "),
                )
        manifest_path = write_job_result_manifest(
            job_id=job_id,
            request_data=request_data,
            request_sha256=admission_sha256,
            execution_request_sha256=execution_sha256,
            execution_request_transform_id=transform_id,
            status="completed",
            result_file=result_file,
            worker_provenance=worker_provenance,
        )
        bundle_path, bundle_hash = write_job_evidence_bundle(
            job_id=job_id,
            request_data=request_data,
            result_manifest_path=manifest_path,
            status_data=status_data,
            request_sha256=admission_sha256,
            execution_request_sha256=execution_sha256,
            execution_request_transform_id=transform_id,
        )
        status_data.update(
            {
                "job_id": job_id,
                "status": "completed",
                "result_manifest": manifest_path,
                "evidence_bundle": bundle_path,
                "evidence_bundle_sha256": bundle_hash,
            }
        )
        published_status_path = status_file_path
        if attempt_results_dir is not None:
            _require_attempt_artifact_path(
                manifest_path,
                attempt_results_dir=attempt_results_dir,
                label="result manifest",
            )
            _require_attempt_artifact_path(
                bundle_path,
                attempt_results_dir=attempt_results_dir,
                label="evidence bundle",
            )
            published_status_path = str(attempt_results_dir / "published_status.json")
        if worker_id:
            _require_live_worker_lease(
                store,
                job_id=job_id,
                worker_id=worker_id,
                attempt_token=attempt_token,
                lease_seconds=lease_seconds,
            )
        write_status_file(status_file_path, status_data)
        if published_status_path != status_file_path:
            write_status_file(published_status_path, status_data)
        completed = store.update_job(
            job_id,
            status="completed",
            result_file=result_file,
            result_manifest_path=manifest_path,
            evidence_bundle_path=bundle_path,
            evidence_bundle_sha256=bundle_hash,
            published_status_path=(published_status_path if worker_id else None),
            published_worker_id=(worker_id if worker_id else None),
            published_attempt_count=(attempt_count if worker_id else None),
            published_attempt_token_sha256=(
                token_fingerprint(attempt_token) if worker_id else None
            ),
            expected_worker_id=worker_id or None,
            expected_attempt_token=attempt_token or None,
        )
        if completed is None:
            raise JobLeaseLostError(f"worker lease lost before completing job {job_id}")
        if worker_id:
            _publish_canonical_status_best_effort(
                canonical_status_file_path,
                status_data,
            )
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="completed",
            result_file=result_file,
            worker_id=worker_id,
        )
        return completed
    except JobLeaseLostError:
        # A stale worker must not publish retry/terminal state for a new owner.
        raise
    except Exception as exc:
        error = str(exc)
        current = store.get_job(job_id) or durable_record
        can_retry = bool(
            retry_on_failure
            and worker_id
            and not isinstance(exc, JobIntegrityError)
            and str(current.get("status", "")) == "running"
            and str(current.get("worker_id", "")) == worker_id
            and hmac.compare_digest(
                str(current.get("attempt_token", "") or ""),
                attempt_token,
            )
            and int(current.get("attempt_count", 0) or 0)
            < int(current.get("max_attempts", 0) or 0)
        )
        if can_retry:
            released = store.release_job_for_retry(
                job_id,
                worker_id,
                attempt_token=attempt_token,
                error=error,
            )
            if released is None:
                raise JobLeaseLostError(f"worker lease lost while releasing job {job_id}") from exc
            if released.get("status") == "retry_ready":
                retry_status = dict(status_data)
                retry_status.update(
                    {"job_id": job_id, "status": "retry_ready", "error": error}
                )
                _write_status_best_effort(status_file_path, retry_status)
                return released

        # Failure artifacts are best effort.  A broken filesystem must not keep
        # the authoritative SQLite row running forever.
        manifest_path = ""
        if (
            admission_sha256
            and execution_sha256
            and transform_id
            and (not worker_id or attempt_results_dir is not None)
        ):
            try:
                manifest_path = write_job_result_manifest(
                    job_id=job_id,
                    request_data=request_data,
                    request_sha256=admission_sha256,
                    execution_request_sha256=execution_sha256,
                    execution_request_transform_id=transform_id,
                    status="failed",
                    error=error,
                    worker_provenance=worker_provenance,
                )
            except (OSError, TypeError, ValueError):
                manifest_path = ""
        failed_status = dict(status_data)
        failed_status.update({"job_id": job_id, "status": "failed", "error": error})
        if manifest_path:
            failed_status["result_manifest"] = manifest_path
        if not worker_id or attempt_results_dir is not None:
            _write_status_best_effort(status_file_path, failed_status)
        published_status_path = ""
        if attempt_results_dir is not None:
            published_status_path = str(attempt_results_dir / "published_status.json")
            _write_status_best_effort(published_status_path, failed_status)

        failed = store.update_job(
            job_id,
            status="failed",
            error=error,
            result_manifest_path=manifest_path or None,
            published_status_path=(published_status_path or None),
            published_worker_id=(worker_id if published_status_path else None),
            published_attempt_count=(attempt_count if published_status_path else None),
            published_attempt_token_sha256=(
                token_fingerprint(attempt_token) if published_status_path else None
            ),
            expected_worker_id=worker_id or None,
            expected_attempt_token=attempt_token or None,
        )
        if failed is None:
            raise JobLeaseLostError(f"worker lease lost before failing job {job_id}") from exc
        if worker_id:
            _publish_canonical_status_best_effort(
                canonical_status_file_path,
                failed_status,
            )
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="failed",
            error=error,
            worker_id=worker_id,
        )
        return failed
    finally:
        if artifact_binding_token is not None:
            reset_attempt_results_dir(artifact_binding_token)


async def process_next_job_once(
    store: SQLiteJobStore,
    *,
    worker_id: str,
    runner: SimulationRunner = run_simulation_async,
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
    retry_on_failure: bool = True,
) -> dict[str, Any] | None:
    acquired = store.acquire_next_job(worker_id, lease_seconds=lease_seconds)
    if acquired is None:
        return None
    return await run_job_once(
        store,
        job_id=str(acquired["job_id"]),
        request_data=dict(acquired.get("request") or {}),
        runner=runner,
        worker_id=worker_id,
        attempt_token=str(acquired.get("attempt_token", "") or ""),
        lease_seconds=lease_seconds,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        retry_on_failure=retry_on_failure,
    )


async def _run_with_periodic_heartbeat(
    store: SQLiteJobStore,
    *,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    runner: SimulationRunner,
    request_data: dict[str, Any],
    lease_seconds: int,
    heartbeat_interval_seconds: float | None,
) -> None:
    interval = heartbeat_interval_seconds
    if interval is None:
        interval = max(1.0, min(float(lease_seconds) / 3.0, float(settings.api_worker_heartbeat_interval_seconds)))

    runner_task = asyncio.create_task(runner(job_id, request_data))
    try:
        while True:
            try:
                await asyncio.wait_for(asyncio.shield(runner_task), timeout=max(0.05, float(interval)))
                return
            except (TimeoutError, asyncio.TimeoutError):
                _require_live_worker_lease(
                    store,
                    job_id=job_id,
                    worker_id=worker_id,
                    attempt_token=attempt_token,
                    lease_seconds=lease_seconds,
                )
    finally:
        if not runner_task.done():
            runner_task.cancel()
            with suppress(asyncio.CancelledError):
                await runner_task
