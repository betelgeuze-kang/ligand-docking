from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from api.config import settings
from api.path_security import confined_path
from api.request_privacy import sanitize_request_for_ledger
from api.runner_profile_contract import (
    EXECUTION_MODE_SMOKE,
    validate_runner_profile_execution_contract,
)
from betelgeuze_ai_md.contracts import EvidenceBundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError

ALLOWED_RUNNER_SCRIPTS = {
    "tools/run_ligand_htvs_pipeline.py",
    "tools/run_ligand_backmapping_scoring.py",
    "tools/run_ligand_topk_delivery.py",
    "tools/run_tier_beta_vertical_slice.py",
}

_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
EXECUTION_ORIGIN_CUSTOMER = "customer"
EXECUTION_ORIGIN_INTERNAL = "internal"
ALLOWED_EXECUTION_ORIGINS = {EXECUTION_ORIGIN_CUSTOMER, EXECUTION_ORIGIN_INTERNAL}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _results_dir(job_id: str) -> Path:
    value = str(job_id or "").strip()
    if not _JOB_ID_RE.fullmatch(value):
        raise ValueError("job_id must be a simple identifier")
    return confined_path(value, settings.results_storage_path, label="job results directory")


def _status_path(job_id: str) -> Path:
    return _results_dir(job_id) / "status.json"


def _write_status(job_id: str, payload: dict[str, Any]) -> None:
    path = _status_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_profile_id(profile_id: Any) -> str:
    value = str(profile_id or "").strip()
    if not _PROFILE_ID_RE.match(value):
        raise ValueError("runner_profile_id must be a simple allowlisted profile id")
    return value


def _load_profile(profile_id: str) -> dict[str, Any]:
    profiles_dir = Path(settings.api_validated_runner_profiles_path)
    profile_path = profiles_dir / f"{profile_id}.json"
    try:
        resolved = profile_path.resolve()
        profiles_root = profiles_dir.resolve()
        if profiles_root not in resolved.parents:
            raise ValueError("runner profile path escapes configured profile directory")
    except FileNotFoundError:
        raise FileNotFoundError(f"runner profile not found: {profile_id}") from None

    if not profile_path.exists():
        raise FileNotFoundError(f"runner profile not found: {profile_id}")
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runner profile must be a JSON object")
    if str(payload.get("profile_id", profile_id)) != profile_id:
        raise ValueError("runner profile_id does not match requested profile")
    if payload.get("enabled") is not True:
        raise PermissionError("runner profile is not enabled")
    return payload


def _render_template(value: str, context: dict[str, str]) -> str:
    try:
        return str(value).format(**context)
    except KeyError as exc:
        raise ValueError(f"unsupported runner profile placeholder: {exc}") from exc


def _runner_script(profile: dict[str, Any]) -> str:
    script = str(profile.get("runner_script", "") or "").strip()
    if script not in ALLOWED_RUNNER_SCRIPTS and str(Path(script).resolve()) not in ALLOWED_RUNNER_SCRIPTS:
        raise PermissionError(f"runner_script is not allowlisted: {script}")
    path = Path(script)
    if not path.is_absolute():
        path = _repo_root() / path
    if not path.exists():
        raise FileNotFoundError(f"runner_script missing: {script}")
    return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_nonempty_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "") or "").strip()
    if not value:
        raise PermissionError(f"runner profile production_readiness.{key} is required")
    return value


def _validate_evidence_artifact(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = _repo_root() / path
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"runner profile evidence artifact missing: {path_value}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PermissionError("runner profile evidence artifact must be a JSON object")
    required_true = (
        "input_contract_reviewed",
        "output_contract_reviewed",
        "claim_boundary_reviewed",
        "gate_policy_reviewed",
        "fake_result_emission_forbidden",
    )
    missing = [key for key in required_true if payload.get(key) is not True]
    if missing:
        raise PermissionError(f"runner profile evidence artifact has unmet checks: {missing}")
    gate_artifact = str(payload.get("gate_policy_artifact", "") or "").strip()
    if not gate_artifact:
        raise PermissionError("runner profile evidence artifact requires gate_policy_artifact")
    return payload


def validate_profile_readiness(profile: dict[str, Any], *, runner_script_path: str) -> dict[str, Any]:
    readiness = profile.get("production_readiness")
    if not isinstance(readiness, dict):
        raise PermissionError("enabled runner profile requires production_readiness block")

    approved_by = _require_nonempty_text(readiness, "approved_by")
    approved_at_utc = _require_nonempty_text(readiness, "approved_at_utc")
    claim_scope = _require_nonempty_text(readiness, "claim_scope")
    evidence_artifact = _require_nonempty_text(readiness, "evidence_artifact")
    expected_hash = _require_nonempty_text(readiness, "runner_script_sha256")
    observed_hash = _sha256_file(Path(runner_script_path))
    if observed_hash != expected_hash:
        raise PermissionError("runner profile runner_script_sha256 does not match allowlisted runner")

    evidence_payload = _validate_evidence_artifact(evidence_artifact)
    return {
        "approved_by": approved_by,
        "approved_at_utc": approved_at_utc,
        "claim_scope": claim_scope,
        "evidence_artifact": evidence_artifact,
        "runner_script_sha256": observed_hash,
        "gate_policy_artifact": str(evidence_payload.get("gate_policy_artifact", "") or ""),
    }


def authorize_runner_profile_execution(
    request_data: dict[str, Any],
    *,
    execution_origin: str = EXECUTION_ORIGIN_CUSTOMER,
) -> dict[str, Any]:
    """Authorize a profile at the final execution boundary.

    The origin is supplied by a trusted Python call site and is deliberately
    never read from request JSON, preventing customer-controlled promotion to
    an internal smoke execution.
    """

    if not settings.api_validated_runner_enabled:
        raise NotImplementedError(
            "API validated runner execution is disabled; set API_VALIDATED_RUNNER_ENABLED=1 and provide an "
            "operator-approved runner profile."
        )
    origin = str(execution_origin or "").strip().lower()
    if origin not in ALLOWED_EXECUTION_ORIGINS:
        raise PermissionError("invalid trusted execution origin")

    profile_id = _safe_profile_id(request_data.get("runner_profile_id"))
    profile = _load_profile(profile_id)
    script = _runner_script(profile)
    readiness = validate_profile_readiness(profile, runner_script_path=script)
    execution_contract = validate_runner_profile_execution_contract(profile, require_explicit=True)
    if origin == EXECUTION_ORIGIN_CUSTOMER and execution_contract["customer_submission_allowed"] is not True:
        raise PermissionError(f"runner profile is not authorized for customer submission: {profile_id}")
    if origin == EXECUTION_ORIGIN_INTERNAL and execution_contract["execution_mode"] == EXECUTION_MODE_SMOKE:
        if execution_contract["synthetic_input_allowed"] is not True:
            raise PermissionError(f"smoke runner profile does not allow synthetic/internal input: {profile_id}")
    return {
        "profile_id": profile_id,
        "profile": profile,
        "runner_script": script,
        "readiness": readiness,
        "execution_contract": execution_contract,
        "execution_origin": origin,
    }


def _run_profile_command(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    # Runner output can contain customer structure details or third-party
    # diagnostics.  Spool it outside memory, retain only non-content metadata,
    # and never copy raw stdout/stderr into the public job ledger.
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(mode="w+b") as stderr_file:
        proc = subprocess.Popen(
            command,
            cwd=str(_repo_root()),
            stdout=stdout_file,
            stderr=stderr_file,
            shell=False,
            start_new_session=True,
        )
        timed_out = False
        try:
            proc.communicate(timeout=max(1, int(timeout_seconds)))
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()

        def summarize(handle: Any) -> dict[str, Any]:
            handle.flush()
            handle.seek(0)
            digest = hashlib.sha256()
            byte_count = 0
            newline_count = 0
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                byte_count += len(chunk)
                newline_count += chunk.count(b"\n")
            return {
                "sha256": digest.hexdigest(),
                "byte_count": byte_count,
                "line_count": newline_count,
                "content_retained": False,
            }

        stdout_summary = summarize(stdout_file)
        stderr_summary = summarize(stderr_file)
    return {
        "returncode": int(proc.returncode if proc.returncode is not None else -9),
        "timed_out": timed_out,
        "stdout_summary": stdout_summary,
        "stderr_summary": stderr_summary,
    }


async def execute_validated_runner_profile(
    job_id: str,
    request_data: dict[str, Any],
    *,
    execution_origin: str = EXECUTION_ORIGIN_CUSTOMER,
) -> dict[str, Any]:
    authorization = authorize_runner_profile_execution(
        request_data,
        execution_origin=execution_origin,
    )
    profile_id = str(authorization["profile_id"])
    profile = dict(authorization["profile"])
    results_dir = _results_dir(job_id)
    results_dir.mkdir(parents=True, exist_ok=True)
    request_json_path = results_dir / "request.json"
    request_json_path.write_text(
        json.dumps(sanitize_request_for_ledger(request_data), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result_file_template = str(profile.get("result_file_template", "{job_results_dir}/runner_result.json") or "")
    evidence_bundle_template = str(profile.get("evidence_bundle_template", "") or "").strip()
    has_evidence_bundle_template = bool(evidence_bundle_template)
    context = {
        "job_id": job_id,
        "job_results_dir": str(results_dir),
        "request_json_path": str(request_json_path),
        "result_file": _render_template(result_file_template, {"job_id": job_id, "job_results_dir": str(results_dir), "request_json_path": str(request_json_path)}),
    }
    context["result_file"] = _render_template(result_file_template, context)
    context["result_file"] = str(
        confined_path(context["result_file"], results_dir, label="runner result file")
    )
    if has_evidence_bundle_template:
        context["evidence_bundle"] = _render_template(
            evidence_bundle_template,
            {
                "job_id": job_id,
                "job_results_dir": str(results_dir),
                "request_json_path": str(request_json_path),
                "result_file": context["result_file"],
            },
        )
        context["evidence_bundle"] = str(
            confined_path(
                context["evidence_bundle"],
                results_dir,
                label="runner evidence bundle",
            )
        )

    args = profile.get("arguments", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError("runner profile arguments must be a list of strings")

    script = str(authorization["runner_script"])
    readiness_record = dict(authorization["readiness"])
    command = [sys.executable, script] + [_render_template(item, context) for item in args]

    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    timeout_seconds = int(settings.api_validated_runner_timeout_seconds)
    completed = await asyncio.to_thread(
        _run_profile_command,
        command,
        timeout_seconds=timeout_seconds,
    )
    duration = max(time.time() - t0, 0.0)
    ended = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    result_file = confined_path(
        context["result_file"],
        results_dir,
        label="runner result file",
    )
    evidence_bundle_path_value = context.get("evidence_bundle", "")
    evidence_bundle_path = (
        confined_path(
            evidence_bundle_path_value,
            results_dir,
            label="runner evidence bundle",
        )
        if evidence_bundle_path_value
        else None
    )
    execution_record = {
        "adapter_version": "api_validated_runner_v1",
        "job_id": job_id,
        "profile_id": profile_id,
        "runner_script": str(profile.get("runner_script", "")),
        "profile_readiness": readiness_record,
        "execution_contract": dict(authorization["execution_contract"]),
        "execution_origin": str(authorization["execution_origin"]),
        "command_executable": command[0],
        "command_argument_count": max(0, len(command) - 1),
        "command_sha256": hashlib.sha256(
            json.dumps(command, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest(),
        "returncode": int(completed["returncode"]),
        "ok": bool(completed["returncode"] == 0),
        "timed_out": bool(completed["timed_out"]),
        "timeout_seconds": timeout_seconds,
        "process_group_killed_on_timeout": bool(completed["timed_out"]),
        "started_at_utc": started,
        "ended_at_utc": ended,
        "duration_sec": float(duration),
        "stdout_summary": dict(completed["stdout_summary"]),
        "stderr_summary": dict(completed["stderr_summary"]),
        "result_file": str(result_file),
        "evidence_bundle_template": evidence_bundle_template or "",
        "native_evidence_bundle": str(evidence_bundle_path) if evidence_bundle_path else "",
        "native_evidence_bundle_sha256": "",
        "claim_boundary": (
            "Validated runner adapter only. It executes an operator-approved local profile and records provenance; "
            "scientific claim scope remains governed by the profile and downstream gates."
        ),
    }
    execution_record_path = results_dir / "runner_execution.json"
    execution_record_path.write_text(json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    if completed["returncode"] != 0:
        error = (
            f"validated_runner_timeout:{timeout_seconds}s"
            if completed["timed_out"]
            else f"validated_runner_failed:returncode={completed['returncode']}"
        )
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "status": "failed",
                "error": error,
                "runner_execution": str(execution_record_path),
            },
        )
        raise RuntimeError(f"validated runner failed for profile {profile_id}; see {execution_record_path}")
    if not result_file.exists() or not result_file.is_file():
        raise FileNotFoundError(f"validated runner did not produce expected result_file: {result_file}")

    native_bundle_record: dict[str, str] = {}
    if has_evidence_bundle_template:
        if evidence_bundle_path is None or not evidence_bundle_path.exists() or not evidence_bundle_path.is_file():
            error = (
                f"validated_runner_missing_native_evidence_bundle:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            execution_record_path.write_text(
                json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                },
            )
            raise FileNotFoundError(
                f"validated runner did not produce expected native evidence bundle: {evidence_bundle_path_value}"
            )
        try:
            raw_payload = json.loads(evidence_bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            error = (
                f"validated_runner_native_evidence_bundle_not_json:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            execution_record_path.write_text(
                json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                },
            )
            raise PermissionError(
                f"native evidence bundle is not valid JSON: {evidence_bundle_path_value}"
            ) from exc
        if not isinstance(raw_payload, dict):
            error = (
                f"validated_runner_native_evidence_bundle_not_object:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            execution_record_path.write_text(
                json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                },
            )
            raise PermissionError(
                f"native evidence bundle must be a JSON object: {evidence_bundle_path_value}"
            )
        try:
            bundle = EvidenceBundle(**raw_payload)
        except (ContractValidationError, TypeError) as exc:
            error = (
                f"validated_runner_native_evidence_bundle_invalid:{exc}"
            )
            execution_record["native_evidence_bundle_error"] = error
            execution_record_path.write_text(
                json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                },
            )
            raise PermissionError(
                f"native evidence bundle failed EvidenceBundle validation: {exc}"
            ) from exc
        bundle_fingerprint = bundle.fingerprint()
        native_bundle_record = {
            "evidence_bundle": str(evidence_bundle_path),
            "evidence_bundle_sha256": bundle_fingerprint,
            "evidence_bundle_source": "validated_runner_native",
        }
        execution_record["native_evidence_bundle"] = str(evidence_bundle_path)
        execution_record["native_evidence_bundle_sha256"] = bundle_fingerprint
        execution_record_path.write_text(
            json.dumps(execution_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    status_payload = {
        "job_id": job_id,
        "status": "completed",
        "runner_profile_id": profile_id,
        "runner_profile_claim_scope": readiness_record["claim_scope"],
        "result_file": str(result_file),
        "result_file_sha256": _sha256_file(result_file),
        "runner_execution": str(execution_record_path),
    }
    status_payload.update(native_bundle_record)
    _write_status(job_id, status_payload)
    return status_payload
