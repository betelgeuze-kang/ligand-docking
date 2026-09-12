"""Opt-in isolated native fixed64 diagnostic using its existing v3 owner.

Requires the exact hash of a caller-supplied, test-only native request. It never
constructs molecular authority, changes a backend, runs protected fixtures, or
relabels CPU prepared-cross work as HIP. Completion is not parity/qualification.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.machinery
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

SCHEMA = "local_native_backend_observation_v1"
INPUT_SCHEMA = "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"
BACKENDS = ("cpp_cpu_reference", "rust_cpu", "hip_safe", "hip_fast")
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
COUNTS = ("generated_count", "typed_failure_count", "initial_admitted_count", "refined_count",
          "post_admitted_count", "post_rejected_count", "scored_count", "valid_count", "cluster_count")
FLAGS = ("native_backend_qualified", "scientifically_validated", "customer_execution",
         "model_promoted", "parity_measured", "prepared_physics_backend_changed")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_native_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_native_json")))


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _request(raw: bytes, backend: str, device: int):
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("native_request_exceeds_capacity")
    value = _decode(raw)
    if (type(value) is not dict or len(value) != 53 or value.get("schema_id") != INPUT_SCHEMA
            or value.get("consumer") != "cli" or value.get("test_only") is not True
            or value.get("backend") != backend or type(value.get("device_ordinal")) is not int
            or value["device_ordinal"] != device):
        raise ValueError("native_request_contract_mismatch")
    # Nested molecular bounds, identities and permissions remain the native
    # owner's responsibility. Never rewrite a request to make it admissible.
    return value


def _snapshot(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_REQUEST_BYTES:
            raise ValueError("native_request_requires_bounded_regular_file")
        raw = stream.read(MAX_REQUEST_BYTES + 1)
        def identity(st):
            return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
        if (identity(before) != identity(os.fstat(stream.fileno()))
                or identity(before) != identity(os.stat(path, follow_symlinks=False))):
            raise ValueError("native_request_changed_during_snapshot")
    return raw


def _empty(backend, device, digest):
    return {"schema_version": SCHEMA, "status": "not_run", "exit_code": 2,
            "backend_requested": backend, "backend_observed": None, "device_ordinal_requested": device,
            "input_sha256": digest, "native_extension_sha256": None,
            "native_pipeline_completed": False, "candidate_denominator": None,
            "counts": None, "pipeline_receipt_sha256": None,
            "scope": "explicit_test_only_native_fixed64_request_not_scientific_qualification",
            **{key: False for key in FLAGS}}


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_native():
    module = importlib.import_module("betelgeuze_engine_v2_native")
    origin = getattr(module, "__file__", None)
    if (type(origin) is not str or not any(origin.endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES)
            or not callable(getattr(module, "native_fixed64_complete_pipeline_v3", None))):
        raise ImportError("compiled_native_v3_extension_required")
    return Path(origin), _file_digest(origin)


def _execute(raw: bytes, backend: str, device: int) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    result = _empty(backend, device, digest)
    try:
        request = _request(raw, backend, device)
    except Exception as exc:
        return {**result, "status": "request_rejected", "error_type": type(exc).__name__}
    try:
        origin, extension_digest = _load_native()
    except (ImportError, OSError) as exc:
        return {**result, "status": "native_extension_unavailable", "error_type": type(exc).__name__}
    try:
        from betelgeuze_engine_v2.docking.native_fixed64_consumers import NativeFixed64CliAdapter
        # This owner validates all 64 candidate rows, bounded v3 input receipts,
        # backend consistency and false authority flags. No alternate engine.
        evidence = NativeFixed64CliAdapter().run(request).to_dict()
        if evidence["backend"] != backend or _file_digest(origin) != extension_digest:
            raise ValueError("native_backend_or_extension_changed")
        counts = {key: evidence[key] for key in COUNTS}
        result.update(status="native_pipeline_completed", exit_code=0,
                      backend_observed=backend, native_extension_sha256=extension_digest,
                      native_pipeline_completed=True, candidate_denominator=64, counts=counts,
                      pipeline_receipt_sha256=evidence["pipeline_receipt_sha256"])
    except Exception as exc:
        result.update(status="native_request_rejected", error_type=type(exc).__name__)
    return result


def _packet(raw: bytes, backend: str, device: int, digest: str):
    packet = _decode(raw)
    template = _empty(backend, device, digest)
    statuses = {"request_rejected", "native_extension_unavailable", "native_request_rejected",
                "native_pipeline_completed"}
    if (type(packet) is not dict or set(packet) - (set(template) | {"error_type"})
            or not set(template).issubset(packet) or packet.get("status") not in statuses):
        raise ValueError("invalid_native_receipt")
    for key in ("schema_version", "backend_requested", "device_ordinal_requested", "input_sha256", "scope"):
        if type(packet[key]) is not type(template[key]) or packet[key] != template[key]:
            raise ValueError("cross_wired_native_receipt")
    if any(packet[key] is not False for key in FLAGS):
        raise ValueError("native_receipt_grants_authority")
    error = packet.get("error_type")
    if error is not None and (type(error) is not str or not error.isidentifier() or len(error) > 128):
        raise ValueError("invalid_native_error_type")
    if packet["status"] == "native_pipeline_completed":
        counts = packet["counts"]
        if (packet["native_pipeline_completed"] is not True or type(packet["exit_code"]) is not int
                or packet["exit_code"] != 0 or packet["backend_observed"] != backend
                or type(packet["candidate_denominator"]) is not int or packet["candidate_denominator"] != 64
                or not _digest(packet["pipeline_receipt_sha256"]) or not _digest(packet["native_extension_sha256"])
                or type(counts) is not dict or set(counts) != set(COUNTS)
                or any(type(n) is not int or not 0 <= n <= 64 for n in counts.values())):
            raise ValueError("invalid_native_success_receipt")
        if (counts["generated_count"] + counts["typed_failure_count"] != 64
                or not counts["cluster_count"] <= counts["valid_count"] <= counts["scored_count"]
                <= counts["post_admitted_count"] <= counts["refined_count"]
                <= counts["initial_admitted_count"] <= counts["generated_count"]
                or counts["post_admitted_count"] + counts["post_rejected_count"] != counts["refined_count"]):
            raise ValueError("invalid_native_denominator")
    else:
        if (packet["native_pipeline_completed"] is not False or type(packet["exit_code"]) is not int
                or packet["exit_code"] != 2 or any(packet[k] is not None for k in (
                    "backend_observed", "candidate_denominator", "counts", "pipeline_receipt_sha256",
                    "native_extension_sha256"))):
            raise ValueError("failed_native_request_claims_completion")
    return packet


def _command(input_fd: int, receipt_fd: int, backend: str, device: int):
    return [sys.executable, "-m", "betelgeuze_product.native_backend_diagnostic",
            "--worker", str(input_fd), str(receipt_fd), backend, str(device)]


def observe_native_request(path: Path, *, expected_sha256: str, backend: str,
                           device_ordinal: int = 0, timeout_seconds: float = 30.0) -> dict:
    """Run an explicitly requested native v3 diagnostic in a bounded child.

    No engine/library is loaded into the parent. Only a private input snapshot
    reaches the child; raw output/exceptions are discarded. The deadline starts
    after spawn, not a hard real-time bound on uninterruptible OS operations.
    """
    if (type(backend) is not str or backend not in BACKENDS or not _digest(expected_sha256)
            or type(device_ordinal) is not int or not 0 <= device_ordinal < 64
            or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0.1 <= timeout_seconds <= 120):
        raise ValueError("invalid_native_diagnostic_options")
    result = _empty(backend, device_ordinal, expected_sha256)
    result.update(isolation="separate_process", timeout_seconds=float(timeout_seconds))
    if sys.platform != "linux":
        return {**result, "status": "unsupported_platform"}
    try:
        raw = _snapshot(Path(path))
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("native_input_digest_mismatch")
        _request(raw, backend, device_ordinal)
    except Exception as exc:
        return {**result, "status": "request_rejected", "error_type": type(exc).__name__}
    process = None
    started = time.perf_counter()
    try:
        with tempfile.TemporaryFile(mode="w+b") as source, tempfile.TemporaryFile(mode="w+b") as receipt:
            source.write(raw)
            source.seek(0)
            process = subprocess.Popen(_command(source.fileno(), receipt.fileno(), backend, device_ordinal),
                                       cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                                       pass_fds=(source.fileno(), receipt.fileno()), start_new_session=True)
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["status"] = "native_probe_timeout"
            else:
                result["process_returncode"] = process.returncode
                if process.returncode != 0:
                    result["status"] = "native_probe_process_failed"
                else:
                    receipt.seek(0)
                    payload = receipt.read(MAX_RECEIPT_BYTES + 1)
                    if len(payload) > MAX_RECEIPT_BYTES:
                        raise ValueError("native_receipt_exceeds_capacity")
                    result.update(_packet(payload, backend, device_ordinal, expected_sha256))
    except Exception as exc:
        result.update(status="native_probe_failed", error_type=type(exc).__name__)
    finally:
        if process is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                result["cleanup"] = "pending_uninterruptible_child"
            else:
                result["cleanup"] = "child_reaped"
        result["wall_seconds"] = time.perf_counter() - started
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--backend", required=True, choices=BACKENDS)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        result = observe_native_request(args.request, expected_sha256=args.sha256, backend=args.backend,
                                        device_ordinal=args.device, timeout_seconds=args.timeout)
    except Exception as exc:
        result = {"status": "invalid_options", "error_type": type(exc).__name__, "exit_code": 2}
    print(_json(result))
    return result["exit_code"]


def _worker_main(argv):
    import resource
    if len(argv) != 4:
        return 2
    input_fd, receipt_fd = int(argv[0]), int(argv[1])
    backend, device = argv[2], int(argv[3])
    if input_fd < 3 or receipt_fd < 3 or input_fd == receipt_fd or backend not in BACKENDS or not 0 <= device < 64:
        return 2
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RECEIPT_BYTES, MAX_RECEIPT_BYTES))
    with os.fdopen(input_fd, "rb") as source:
        raw = source.read(MAX_REQUEST_BYTES + 1)
    packet = _json(_execute(raw, backend, device)).encode()
    if len(packet) > MAX_RECEIPT_BYTES:
        return 2
    with os.fdopen(receipt_fd, "wb") as receipt:
        receipt.write(packet)
        receipt.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker_main(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "--worker" else main())
