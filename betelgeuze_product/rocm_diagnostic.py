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
