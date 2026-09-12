"""Local capability observation, never a native docking qualification receipt."""
from __future__ import annotations

import importlib
import os
import platform
import shutil
from typing import Any


def diagnose_rocm(*, probe: bool = False) -> dict[str, Any]:
    """Without probe, do not import Torch or execute any device operation.

    The optional probe tests only Torch's HIP tensor path. It cannot establish
    native provider availability, hip_safe qualification, scientific validity,
    or permission to relabel CPU prepared cross evaluation as GPU work.
    """
    if type(probe) is not bool:
        raise ValueError("probe_must_be_boolean")
    result: dict[str, Any] = {
        "schema_version": "local_rocm_observation_v1",
        "platform": platform.system(),
        "kfd_present": os.path.exists("/dev/kfd"),
        "kfd_accessible": os.access("/dev/kfd", os.R_OK | os.W_OK),
        "hip_compiler_present": shutil.which("hipcc") is not None,
        "status": "not_probed", "torch_hip_version": None,
        "device_count": None, "devices": [], "probe_backend": None,
        "native_docking_provider": "not_probed",
        "native_backend_qualified": False, "scientifically_validated": False,
        "customer_execution": False,
    }
    if not probe:
        return result
    try:
        torch = importlib.import_module("torch")
        result["torch_hip_version"] = torch.version.hip
        if not torch.version.hip:
            result["status"] = "unavailable_not_torch_hip_build"
            return result
        if not torch.cuda.is_available():
            result["status"] = "unavailable_torch_hip_device"
            return result
        count = torch.cuda.device_count()
        result["device_count"] = count
        if count < 1:
            result["status"] = "unavailable_torch_hip_device"
            return result
        for index in range(count):
            prop = torch.cuda.get_device_properties(index)
            result["devices"].append({
                "index": index, "name": str(prop.name),
                "total_memory_bytes": int(prop.total_memory),
                "architecture": str(getattr(prop, "gcnArchName", "unknown")),
            })
        # Exactly representable arithmetic, bounded allocation, no global RNG.
        x = torch.tensor([1., 2., 4., 8.], dtype=torch.float64, device="cuda:0")
        y = x.square() + x
        torch.cuda.synchronize(0)
        if y.device.type != "cuda" or y.detach().cpu().tolist() != [2., 6., 20., 72.]:
            result["status"] = "failed_torch_hip_probe"
            return result
        result.update(status="torch_hip_probe_passed", probe_backend="torch_hip_device_0")
    except Exception as exc:
        result.update(status="probe_failed", error_type=type(exc).__name__)
    return result


# The callable above remains the in-process worker/legacy diagnostic. Workflow
# and CLI callers use this wrapper so driver hangs/aborts cannot take their
# completion journal or application process with them.
MAX_PROBE_BYTES = 64 * 1024
DEFAULT_PROBE_TIMEOUT = 30.0
_PROBE_STATUSES = {
    "unavailable_not_torch_hip_build", "unavailable_torch_hip_device",
    "failed_torch_hip_probe", "torch_hip_probe_passed", "probe_failed",
}


def _probe_command(fd: int) -> list[str]:
    from pathlib import Path
    import sys

    # Fixed owned code, not a command/library path from a molecular request.
    return [sys.executable, str(Path(__file__).resolve()), "--worker-fd", str(fd)]


def _probe_packet(raw: bytes) -> dict:
    import json

    def object_pairs(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("duplicate_probe_key")
            output[key] = value
        return output
    packet = json.loads(raw, object_pairs_hook=object_pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_probe")))
    allowed = set(diagnose_rocm()) | {"error_type"}
    if (type(packet) is not dict or set(packet) - allowed
            or packet.get("schema_version") != "local_rocm_observation_v1"
            or packet.get("status") not in _PROBE_STATUSES
            or any(packet.get(key) is not False for key in (
                "native_backend_qualified", "scientifically_validated", "customer_execution"))
            or packet.get("native_docking_provider") != "not_probed"):
        raise ValueError("invalid_probe_contract")
    count, devices = packet.get("device_count"), packet.get("devices")
    if count is not None and (type(count) is not int or not 0 <= count <= 64):
        raise ValueError("invalid_probe_device_count")
    if type(devices) is not list or len(devices) > 64:
        raise ValueError("invalid_probe_devices")
    for index, device in enumerate(devices):
        if (type(device) is not dict or set(device) != {"index", "name", "total_memory_bytes", "architecture"}
                or type(device["index"]) is not int or device["index"] != index
                or type(device["total_memory_bytes"]) is not int or device["total_memory_bytes"] <= 0
                or any(type(device[k]) is not str or len(device[k]) > 256 for k in ("name", "architecture"))):
            raise ValueError("invalid_probe_device")
    for key in ("platform", "torch_hip_version", "error_type"):
        value = packet.get(key)
        if value is not None and (type(value) is not str or len(value) > 256):
            raise ValueError("invalid_probe_metadata")
    if "error_type" in packet and not packet["error_type"].isidentifier():
        raise ValueError("invalid_probe_error_type")
    for key in ("kfd_present", "kfd_accessible", "hip_compiler_present"):
        if type(packet.get(key)) is not bool:
            raise ValueError("invalid_probe_flag")
    if packet.get("probe_backend") not in (None, "torch_hip_device_0"):
        raise ValueError("invalid_probe_backend")
    if packet["status"] == "torch_hip_probe_passed":
        if not (count and len(devices) == count and packet.get("torch_hip_version")
                and packet.get("probe_backend") == "torch_hip_device_0"):
            raise ValueError("missing_probe_success_evidence")
    elif packet.get("probe_backend") is not None:
        raise ValueError("failed_probe_claims_execution")
    return packet


def diagnose_rocm_isolated(*, probe: bool = False,
                           timeout_seconds: float = DEFAULT_PROBE_TIMEOUT) -> dict[str, Any]:
    """Linux/POSIX bounded child probe; no model/engine import in the parent.

    The timeout bounds waiting after process creation, not a kernel stuck in
    uninterruptible sleep or the OS process creation call itself. A process
    group is killed on timeout/interruption. Child stdout/stderr are discarded;
    one bounded receipt is returned via an anonymous temporary descriptor.
    This is observation, not GPU qualification or native-provider parity.
    """
    import contextlib
    import math
    import signal
    import subprocess
    import tempfile
    import time

    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120):
        raise ValueError("probe_timeout_must_be_in_0_1_to_120_seconds")
    if type(probe) is not bool:
        raise ValueError("probe_must_be_boolean")
    result = diagnose_rocm()
    result.update(probe_isolation="not_requested", probe_timeout_seconds=float(timeout_seconds))
    if not probe:
        return result
    if os.name != "posix":
        result["status"] = "probe_isolation_unsupported_platform"
        return result
    started = time.perf_counter()
    process = None
    result["probe_isolation"] = "separate_process_no_caller_state"
    try:
        with tempfile.TemporaryFile(mode="w+b") as receipt:
            process = subprocess.Popen(_probe_command(receipt.fileno()), stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       close_fds=True, pass_fds=(receipt.fileno(),), start_new_session=True)
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["status"] = "probe_timeout"
            else:
                result["probe_returncode"] = process.returncode
                if process.returncode != 0:
                    result["status"] = "probe_process_failed"
                else:
                    receipt.seek(0)
                    raw = receipt.read(MAX_PROBE_BYTES + 1)
                    if len(raw) > MAX_PROBE_BYTES:
                        raise ValueError("probe_receipt_exceeds_capacity")
                    result.update(_probe_packet(raw))
    except Exception as exc:
        result.update(status="probe_failed", error_type=type(exc).__name__)
    finally:
        if process is not None:
            # Also reap descendants if a broken worker exited without them.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                result["probe_cleanup"] = "pending_uninterruptible_child"
            else:
                result["probe_cleanup"] = "child_reaped"
        result["probe_wall_seconds"] = time.perf_counter() - started
    return result


def _worker_main() -> int:
    import json
    import resource
    import sys

    if len(sys.argv) != 3 or sys.argv[1] != "--worker-fd":
        return 2
    fd = int(sys.argv[2])
    if fd < 3:
        return 2
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    payload = json.dumps(diagnose_rocm(probe=True), sort_keys=True, allow_nan=False).encode()
    if len(payload) > MAX_PROBE_BYTES:
        return 2
    with os.fdopen(fd, "wb") as output:
        output.write(payload)
        output.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker_main())
