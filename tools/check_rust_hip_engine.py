#!/usr/bin/env python3

import argparse
import json

from core.config import config
from core.rust_hip_backend import probe_rust_hip_backend


def _smoke_hip_add(module_name):
    import importlib

    module = importlib.import_module(module_name)
    if not hasattr(module, "hip_add"):
        return {"available": False, "ok": False, "error": "hip_add symbol missing"}

    try:
        out = module.hip_add([1.0, 2.0], [3.0, 4.0])
        return {"available": True, "ok": True, "output": out}
    except BaseException as exc:
        return {"available": True, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main():
    parser = argparse.ArgumentParser(description="Check Rust HIP engine readiness.")
    parser.add_argument("--module", type=str, default="ldi_arc_rust", help="Python module name for Rust HIP binding")
    parser.add_argument("--smoke", action="store_true", help="Run hip_add smoke call if available")
    args = parser.parse_args()

    status = probe_rust_hip_backend(module_name=args.module, device=config.DEVICE)
    payload = {
        "enabled": status.enabled,
        "reason": status.reason,
        "module_name": status.module_name,
        "module_loaded": status.module_loaded,
        "module_path": status.module_path,
        "kernel_name": status.kernel_name,
        "device_type": status.device_type,
        "torch_cuda_available": status.torch_cuda_available,
        "kfd_accessible": status.kfd_accessible,
        "kfd_error": status.kfd_error,
        "exported_symbols": list(status.exported_symbols),
    }
    hints = []
    if not status.module_loaded:
        hints.append("Build local extension: python3 tools/build_rust_hip_engine.py")
    if status.kernel_name is None:
        hints.append("Rust module must export compute_nonbonded_gpu or hip_nonbonded_kernel*")
    if status.device_type != "cuda":
        hints.append("Set config/settings.yaml device.type to cuda (if ROCm GPU is intended)")
    if not status.torch_cuda_available:
        hints.append("Current PyTorch runtime does not expose CUDA/HIP device")
    if status.kfd_accessible is False:
        hints.append(f"ROCm device access blocked: {status.kfd_error}")
    payload["hints"] = hints
    if args.smoke:
        payload["hip_add_smoke"] = _smoke_hip_add(args.module)

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if status.enabled:
        raise SystemExit(0)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
