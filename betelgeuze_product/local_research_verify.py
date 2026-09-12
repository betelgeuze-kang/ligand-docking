"""Read-only, bounded-memory verification of private local research artifacts.

This detects incomplete/corrupt files and inconsistent summaries against local
receipts. An owner able to rewrite both data and receipts can forge them: this
is not source authentication, scientific validation or resume authorization.
No engine, model, original input, SQLite journal or GPU is opened or executed.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any

MAX_REPORT_BYTES = 2 * 1024 * 1024
ARTIFACT_NAMES = {"physics": "physics.json", "assay_shadow": "assay-shadow.json", "html": "report.html"}
INTEGRITY_POLICY = "referenced_artifacts_including_html_sha256_v1"


class _Invalid(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise _Invalid(code)


def _identity(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _count(value):
    return type(value) is int and value >= 0


def _regular(st) -> None:
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "not_single_link_regular_file")


def _private(st) -> None:
    _require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid()
             and not st.st_mode & 0o077, "not_private_owned_directory")


def _read_or_hash(directory_fd, name, *, limit=None, expected=None):
    # All names come from fixed constants, never arbitrary receipt paths.
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory_fd)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        _regular(before)
        if limit is not None:
            _require(before.st_size <= limit, "receipt_exceeds_capacity")
        if expected is not None:
            _require(before.st_size == expected["bytes"], "artifact_size_mismatch")
        digest, size = hashlib.sha256(), 0
        data = bytearray() if limit is not None else None
        while True:
            block = stream.read(65536)
            if not block:
                break
            size += len(block)
            if limit is not None:
                _require(size <= limit, "receipt_exceeds_capacity")
                data.extend(block)
            if expected is not None:
                _require(size <= expected["bytes"], "artifact_size_mismatch")
            digest.update(block)
        _require(_identity(before) == _identity(os.fstat(stream.fileno()))
                 == _identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)),
                 "file_changed_during_verification")
        _require(size == before.st_size, "file_size_changed")
    observed = digest.hexdigest()
    if expected is not None:
        _require(observed == expected["sha256"], "artifact_digest_mismatch")
    return bytes(data) if data is not None else None, observed


def _check_summary(report: dict, request: dict) -> None:
    _require(report.get("schema_version") == "local_research_workflow_report_v1", "unknown_report_schema")
    _require(report.get("backend_requested") == request["backend"], "backend_request_mismatch")
    _require(report.get("backend_executed") in (None, "cpu"), "unsupported_executed_backend")
    _require(report.get("supplied_pose_count") == len(request["prepared_request"]["poses"]), "pose_count_mismatch")
    for key in ("customer_execution", "scientifically_validated", "external_solver_called", "model_promoted",
                "same_prepared_or_assay_state_verified"):
        _require(report.get(key) is False, "unsupported_report_claim")
    _require(report.get("combined_score") is None, "unsupported_combined_score")
    physics, shadow = report.get("physics"), report.get("assay_shadow")
    _require(type(physics) is dict and type(shadow) is dict, "invalid_stage_summary")
    if request["backend"] != "cpu":
        _require(report.get("status") == "blocked_backend" and report.get("backend_executed") is None
                 and physics.get("status") == "not_run" and report.get("exit_code") == 2,
                 "backend_block_summary_mismatch")
        return
    _require(physics.get("status") in ("completed", "failed"), "unfinished_physics")
    good_physics = False
    if physics["status"] == "completed":
        den, poses = physics.get("denominator"), physics.get("poses")
        _require(type(den) is dict and set(den) == {"requested", "evaluated", "failed", "skipped"}
                 and all(_count(v) for v in den.values()), "invalid_physics_denominator")
        _require(den["requested"] == len(request["prepared_request"]["poses"])
                 and den["requested"] == sum(den[k] for k in ("evaluated", "failed", "skipped")),
                 "physics_denominator_mismatch")
        _require(type(poses) is list and len(poses) == den["requested"]
                 and all(type(row) is dict for row in poses)
                 and [row.get("request_index") for row in poses] == list(range(len(poses))),
                 "pose_summary_mismatch")
        for key in ("evaluated", "failed", "skipped"):
            _require(sum(row.get("status") == key for row in poses) == den[key], "pose_status_mismatch")
        _require(physics.get("result_backend") == "cpu", "physics_backend_mismatch")
        good_physics = den["failed"] == den["skipped"] == 0
    else:
        _require(physics.get("denominator") is None, "failed_physics_has_denominator")
    if request["assay_shadow"] is None:
        _require(shadow.get("status") == "disabled", "unexpected_shadow_stage")
    else:
        _require(shadow.get("status") in ("failed", "not_evaluated", "completed"), "invalid_shadow_status")
    if shadow.get("status") == "completed":
        counts = [shadow.get(k) for k in ("requested_rows", "evaluated_rows", "unsupported_rows")]
        _require(all(_count(n) for n in counts) and counts[0] == counts[1] + counts[2],
                 "shadow_denominator_mismatch")
    good_shadow = (shadow.get("status") == "disabled" or
                   (shadow.get("status") == "completed" and shadow.get("sidecar_status") == "written"
                    and shadow.get("unsupported_rows") == 0))
    expected_status = "completed" if good_physics and good_shadow else "partial_or_failed"
    _require(report.get("status") == expected_status
             and report.get("exit_code") == (0 if expected_status == "completed" else 2),
             "overall_status_mismatch")


def verify_run(run_dir: Path, *, attempt: int | None = None) -> dict[str, Any]:
    """Verify one attempt (latest by default), without rerunning or repairing it.

    A valid partial/blocked result is returned as intact with its original status;
    it is never relabelled a successful calculation. Interrupted latest attempts
    are reported incomplete instead of silently choosing an older success.
    """
    from .local_research_workflow import (MAX_REQUEST_BYTES, PUBLICATION_POLICY, COMPLETION_SCHEMA,
                                          _decode, _json, _snapshot_request)

    result: dict[str, Any] = {
        "schema_version": "local_research_verification_v1", "status": "invalid", "exit_code": 2,
        "scope": "local_receipt_integrity_not_authentication_or_scientific_validation",
        "source_authenticated": False, "scientifically_validated": False, "resume_authorized": False,
        "execution_performed": False, "artifacts_verified": [], "html_verified": False,
        "summary_receipt_verified": False,
    }
    root_fd = lock_fd = attempt_fd = None
    try:
        _require(attempt is None or (type(attempt) is int and 1 <= attempt <= 10000), "invalid_attempt_number")
        root_fd = os.open(Path(run_dir).absolute(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        _private(os.fstat(root_fd))
        # Read-only and nonblocking: never create a missing lock or journal.
        lock_fd = os.open(".workflow.lock", os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=root_fd)
        _regular(os.fstat(lock_fd))
        fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if attempt is None:
            ids = [int(name[8:]) for name in os.listdir(root_fd) if re.fullmatch(r"attempt-[0-9]{6}", name)]
            _require(bool(ids) and max(ids) <= 10000, "no_valid_attempt")
            attempt = max(ids)
        result["attempt"] = attempt
        raw, binding_hash = _read_or_hash(root_fd, "request.json", limit=MAX_REQUEST_BYTES)
        binding = _decode(raw)
        _require(type(binding) is dict and set(binding) == {"request", "workflow_source_sha256"}
                 and _digest(binding.get("workflow_source_sha256")), "invalid_request_binding")
        request = _snapshot_request(binding["request"])
        attempt_fd = os.open(f"attempt-{attempt:06d}", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        _private(os.fstat(attempt_fd))
        raw, report_hash = _read_or_hash(attempt_fd, "report.json", limit=MAX_REPORT_BYTES)
        report = _decode(raw)
        _require(type(report) is dict and type(report.get("attempt")) is int and report.get("attempt") == attempt, "invalid_attempt_report")
        request_hash = hashlib.sha256(_json(request).encode()).hexdigest()
        _require(report.get("request_sha256") == request_hash, "request_report_digest_mismatch")
        result.update(report_sha256=report_hash, request_sha256=request_hash)
        if report.get("status") == "running":
            result.update(status="incomplete", reason="attempt_not_finalized")
            return result
        publication = report.get("publication_policy")
        _require(publication in (None, PUBLICATION_POLICY), "unknown_publication_policy")
        if publication == PUBLICATION_POLICY:
            try:
                completion_raw, completion_hash = _read_or_hash(attempt_fd, "complete.json", limit=4096)
            except FileNotFoundError:
                result.update(status="incomplete", reason="missing_final_completion_receipt")
                return result
            completion = _decode(completion_raw)
            _require(type(completion) is dict and set(completion) == {
                         "schema_version", "attempt", "report_sha256", "request_binding_sha256"}
                     and completion["schema_version"] == COMPLETION_SCHEMA
                     and type(completion["attempt"]) is int and completion["attempt"] == attempt
                     and completion["report_sha256"] == report_hash
                     and completion["request_binding_sha256"] == binding_hash,
                     "completion_receipt_mismatch")
            result["summary_receipt_verified"] = True
        else:
            # Legacy attempts never had this marker. Do not silently accept a
            # damaged modern report whose publication field disappeared.
            try:
                os.stat("complete.json", dir_fd=attempt_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise _Invalid("completion_marker_without_publication_policy")
        _check_summary(report, request)
        artifacts = report.get("artifacts")
        _require(type(artifacts) is dict and set(artifacts).issubset(ARTIFACT_NAMES), "invalid_artifact_inventory")
        _require(("physics" in artifacts) == (report["physics"]["status"] == "completed"), "physics_artifact_mismatch")
        _require(("assay_shadow" in artifacts) == (report["assay_shadow"].get("sidecar_status") == "written"),
                 "shadow_artifact_mismatch")
        policy = report.get("artifact_integrity_policy")
        _require(policy is None or policy == INTEGRITY_POLICY, "unknown_integrity_policy")
        if policy == INTEGRITY_POLICY:
            _require("html" in artifacts, "missing_html_receipt")
        for key, entry in artifacts.items():
            _require(type(entry) is dict and set(entry) == {"name", "bytes", "sha256"}
                     and entry["name"] == ARTIFACT_NAMES[key] and _count(entry["bytes"])
                     and _digest(entry["sha256"]), "invalid_artifact_entry")
            _read_or_hash(attempt_fd, ARTIFACT_NAMES[key], expected=entry)
            result["artifacts_verified"].append(ARTIFACT_NAMES[key])
        # Detect replaced receipts too; readers retain the same opened run directory.
        _, again = _read_or_hash(attempt_fd, "report.json", limit=MAX_REPORT_BYTES)
        _require(again == report_hash, "report_changed_during_verification")
        if publication == PUBLICATION_POLICY:
            _, again = _read_or_hash(attempt_fd, "complete.json", limit=4096)
            _require(again == completion_hash, "completion_changed_during_verification")
        raw, _ = _read_or_hash(root_fd, "request.json", limit=MAX_REQUEST_BYTES)
        _require(_decode(raw) == binding, "request_changed_during_verification")
        result.update(status="intact", exit_code=0, workflow_status=report["status"],
                      workflow_exit_code=report["exit_code"], html_verified="html" in artifacts)
    except BlockingIOError:
        result["reason"] = "run_is_active"
    except _Invalid as exc:
        result["reason"] = str(exc)  # only fixed codes created in this module
    except Exception as exc:
        result.update(reason="unreadable_or_invalid_run", error_type=type(exc).__name__)
    finally:
        for fd in (attempt_fd, lock_fd, root_fd):
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
    return result
