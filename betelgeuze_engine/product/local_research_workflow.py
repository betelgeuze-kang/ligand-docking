"""Local development orchestration of existing streaming and resumable consumers.

No training, ranking fusion, external solver, or automatic GPU fallback. This
consumer evaluates supplied rigid poses, not de-novo docking or MD. The assay
CSV is a separate catalogue: no identity/same-state relationship is inferred.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import resource
import stat
import sys
import time
from typing import Any

from .rocm_diagnostic import diagnose_rocm

SCHEMA = "local_research_workflow_request_v1"
MAX_REQUEST_BYTES = 1024 * 1024


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _decode(raw: bytes | str):
    return json.loads(raw, object_pairs_hook=_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("input_must_be_regular_file")
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
        def identity(st):
            return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
        if identity(before) != identity(after) or identity(after) != identity(path.stat()):
            raise ValueError("input_changed_during_read")
    return digest.hexdigest()


def _snapshot_request(request: dict) -> dict:
    snapshot = _decode(_json(request))
    if (type(snapshot) is not dict or set(snapshot) != {
            "schema_version", "backend", "prepared_request", "assay_shadow"}
            or snapshot["schema_version"] != SCHEMA
            or snapshot["backend"] not in ("cpu", "hip_safe", "hip_fast")):
        raise ValueError("invalid_workflow_contract")
    prepared = snapshot["prepared_request"]
    if (type(prepared) is not dict
            or prepared.get("schema_version") != "prepared_rigid_pose_cross_request_v1"
            or type(prepared.get("poses")) is not list
            or not 1 <= len(prepared["poses"]) <= 32):
        raise ValueError("explicit_rigid_request_required")
    selector = snapshot["assay_shadow"]
    if selector is not None:
        if type(selector) is not dict or set(selector) != {
                "ligand_csv", "input_sha256", "checkpoint", "checkpoint_sha256", "chunk_size"}:
            raise ValueError("invalid_shadow_contract")
        for name in ("input_sha256", "checkpoint_sha256"):
            value = selector[name]
            if (type(value) is not str or len(value) != 64
                    or any(ch not in "0123456789abcdef" for ch in value)):
                raise ValueError("invalid_shadow_digest")
        for name in ("ligand_csv", "checkpoint"):
            if type(selector[name]) is not str or not Path(selector[name]).is_absolute():
                raise ValueError("shadow_requires_absolute_paths")
        if type(selector["chunk_size"]) is not int or not 1 <= selector["chunk_size"] <= 4096:
            raise ValueError("invalid_shadow_chunk_size")
    return snapshot


def _input_refs(value):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256", "source_id"}:
            yield value["path"]
        else:
            for child in value.values():
                yield from _input_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _input_refs(child)


def _atomic(path: Path, text: str) -> None:
    """Only used inside a private owned run/attempt directory under its lock."""
    tmp = path.with_name(path.name + ".partial")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("artifact_symlink_rejected")
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _html_report(report: dict) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    sections = ["<!doctype html><html><head><meta charset='utf-8'>",
                "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">",
                "<title>Local research run</title></head><body><h1>Local research run</h1>",
                "<p>Supplied rigid-pose evaluation; not docking recovery, MD or scientific qualification.</p>",
                "<p>Status: " + esc(report["status"]) + "</p>",
                "<p>Requested backend: " + esc(report["backend_requested"]) +
                "; executed physics backend: " + esc(report["backend_executed"]) + "</p>"]
    for key in ("physics", "assay_shadow", "cost", "artifacts"):
        sections.extend(["<h2>" + esc(key) + "</h2><pre>",
                         esc(json.dumps(report.get(key), indent=2, allow_nan=False)), "</pre>"])
    sections.append("<p>Assay catalogue and prepared physical states are not verified as identical. No scores were combined.</p></body></html>\n")
    return "".join(sections)


def _artifact(path: Path) -> dict:
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": _hash_file(path)}


def _shadow_status(selector: dict, output: Path) -> dict:
    from .public_assay_streaming import run_pre_docking_shadow
    # A missing or changed shadow model must not prevent independent physics.
    if _hash_file(Path(selector["ligand_csv"])) != selector["input_sha256"]:
        raise ValueError("shadow_input_digest_mismatch")
    if _hash_file(Path(selector["checkpoint"])) != selector["checkpoint_sha256"]:
        raise ValueError("shadow_checkpoint_digest_mismatch")
    result = run_pre_docking_shadow(
        ligand_csv=selector["ligand_csv"], ligand_sdf="", docking_request_json="",
        resume_stage3_only=False, checkpoint=selector["checkpoint"],
        checkpoint_sha256=selector["checkpoint_sha256"], output_json=str(output),
        chunk_size=selector["chunk_size"])
    if _hash_file(Path(selector["checkpoint"])) != selector["checkpoint_sha256"]:
        raise ValueError("shadow_checkpoint_changed")
    if result.get("input_sha256") != selector["input_sha256"]:
        raise ValueError("shadow_input_changed")
    return {key: result.get(key) for key in (
        "status", "requested_rows", "evaluated_rows", "unsupported_rows", "sidecar_status")}


def run_workflow(request: dict, *, run_dir: Path, resume: bool = False,
                 probe_rocm: bool = False) -> dict:
    """New private run; each resume writes a new attempt without deleting history.

    Only rigid-physics completions are reused by the existing PoseJournal. Shadow
    prediction is rerun every attempt (bounded memory); it never changes poses.
    """
    started, cpu = time.perf_counter(), time.process_time()
    if type(resume) is not bool or type(probe_rocm) is not bool:
        raise ValueError("execution_flags_must_be_boolean")
    snapshot = _snapshot_request(request)
    run_dir = Path(run_dir).absolute()
    for path in [*_input_refs(snapshot["prepared_request"]),
                 *([snapshot["assay_shadow"][k] for k in ("ligand_csv", "checkpoint")]
                   if snapshot["assay_shadow"] else [])]:
        if Path(path).resolve().is_relative_to(run_dir.resolve()):
            raise ValueError("run_directory_must_not_contain_source_inputs")
    if not resume:
        run_dir.mkdir(mode=0o700)
    directory_fd = os.open(run_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock_fd = None
    try:
        st = os.fstat(directory_fd)
        if st.st_uid != os.geteuid() or st.st_mode & 0o077:
            raise ValueError("run_directory_must_be_private_and_owned")
        lock_fd = os.open(".workflow.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                          0o600, dir_fd=directory_fd)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
            raise ValueError("invalid_workflow_lock")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        binding = {"request": snapshot,
                   "workflow_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        contract = run_dir / "request.json"
        if resume:
            fd = os.open(contract, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("invalid_request_binding")
                previous = stream.read(MAX_REQUEST_BYTES + 1)
            if len(previous) > MAX_REQUEST_BYTES or _decode(previous) != binding:
                raise ValueError("workflow_resume_contract_mismatch")
        else:
            text = _json(binding)
            if len(text.encode()) > MAX_REQUEST_BYTES:
                raise ValueError("workflow_request_exceeds_capacity")
            _atomic(contract, text + "\n")
        # Create-only attempt directories preserve incomplete and completed runs.
        index = 1
        while True:
            attempt = run_dir / f"attempt-{index:06d}"
            try:
                attempt.mkdir(mode=0o700)
                break
            except FileExistsError:
                index += 1
                if index > 10000:
                    raise ValueError("too_many_workflow_attempts")
        report = {
            "schema_version": "local_research_workflow_report_v1", "status": "running",
            "attempt": index, "backend_requested": snapshot["backend"],
            "backend_executed": None, "resume_requested": resume,
            "request_sha256": hashlib.sha256(_json(snapshot).encode()).hexdigest(),
            "supplied_pose_count": len(snapshot["prepared_request"]["poses"]),
            "rocm_observation": diagnose_rocm(probe=probe_rocm),
            "physics": {"status": "not_run", "denominator": None},
            "assay_shadow": {"status": "disabled" if snapshot["assay_shadow"] is None else "not_run"},
            "artifacts": {}, "cost": {}, "combined_score": None,
            "same_prepared_or_assay_state_verified": False,
            "customer_execution": False, "scientifically_validated": False,
            "external_solver_called": False, "model_promoted": False,
        }
        _atomic(attempt / "report.json", _json(report) + "\n")
        if snapshot["backend"] != "cpu":
            # Prepared cross evaluation has no native HIP adapter. A passing
            # Torch probe may NOT authorize/relabel that different calculation.
            report.update(status="blocked_backend", exit_code=2,
                          reason="prepared_rigid_physics_supports_cpu_only_no_fallback")
        else:
            selector = snapshot["assay_shadow"]
            tick = time.perf_counter()
            if selector is not None:
                try:
                    report["assay_shadow"] = _shadow_status(selector, attempt / "assay-shadow.json")
                    if report["assay_shadow"]["sidecar_status"] == "written":
                        report["artifacts"]["assay_shadow"] = _artifact(attempt / "assay-shadow.json")
                except Exception as exc:
                    report["assay_shadow"] = {"status": "failed", "error_type": type(exc).__name__}
            report["cost"]["assay_stage_wall_seconds"] = time.perf_counter() - tick
            tick = time.perf_counter()
            try:
                from tools.product.score_prepared_cross_interactions import evaluate_request, _write_report_json
                journal = run_dir / "physics-checkpoint"
                result = evaluate_request(snapshot["prepared_request"], checkpoint_dir=journal,
                                          resume=resume and journal.exists())
                completion = result["resume_observation"]
                new_rows = result["rows"][completion["restored_rows"]:]
                report["backend_executed"] = ("cpu" if any(
                    row.get("evaluation_completed") is True for row in new_rows) else None)
                report["physics"] = {"status": "completed", "denominator": result["denominator"],
                                      "result_backend": "cpu", "resume_observation": completion,
                                      "preparation_observation": result.get("preparation_observation")}
                # The existing bounded-row JSON encoder preserves all numerical
                # outputs. Never put large assay rows into the summary report.
                output = attempt / "physics.json"
                with output.open("x", encoding="utf-8") as stream:
                    _write_report_json(result, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                report["artifacts"]["physics"] = _artifact(output)
            except Exception as exc:
                report["physics"] = {"status": "failed", "error_type": type(exc).__name__, "denominator": None}
            report["cost"]["physics_and_output_wall_seconds"] = time.perf_counter() - tick
            good_physics = (report["physics"]["status"] == "completed"
                            and report["physics"]["denominator"]["failed"] == 0)
            shadow = report["assay_shadow"]
            good_shadow = (shadow["status"] == "disabled" or
                           (shadow.get("status") == "completed" and shadow.get("sidecar_status") == "written"
                            and shadow.get("unsupported_rows") == 0))
            report.update(status="completed" if good_physics and good_shadow else "partial_or_failed",
                          exit_code=0 if good_physics and good_shadow else 2)
        report["cost"].update(
            wall_seconds=time.perf_counter() - started, cpu_seconds=time.process_time() - cpu,
            peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            peak_rss_unit="KiB" if sys.platform.startswith("linux") else "platform_native",
            peak_rss_scope="process_lifetime_high_water_not_stage_or_gpu_memory",
            timing_scope="workflow_call_through_artifact_hashes_excludes_final_report_and_process_startup")
        _atomic(attempt / "report.json", _json(report) + "\n")
        _atomic(attempt / "report.html", _html_report(report))
        return report
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(directory_fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--diagnose-only", action="store_true")
    parser.add_argument("--probe-rocm", action="store_true")
    args = parser.parse_args(argv)
    if args.diagnose_only:
        if args.request or args.run_dir or args.resume:
            parser.error("diagnose-only does not accept a research request")
        report = diagnose_rocm(probe=args.probe_rocm)
        print(_json(report))
        return 0 if report["status"] in {"not_probed", "torch_hip_probe_passed"} else 2
    if args.request is None or args.run_dir is None:
        parser.error("request and run-dir are required")
    try:
        fd = os.open(args.request, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("request_must_be_regular_file")
            raw = stream.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("request_exceeds_capacity")
        result = run_workflow(_decode(raw), run_dir=args.run_dir, resume=args.resume, probe_rocm=args.probe_rocm)
        print(_json({"status": result["status"], "attempt": result["attempt"], "exit_code": result["exit_code"]}))
        return result["exit_code"]
    except Exception as exc:
        # Do not echo paths, private molecular payloads or exception messages.
        print(_json({"status": "failed", "error_type": type(exc).__name__, "exit_code": 2}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
