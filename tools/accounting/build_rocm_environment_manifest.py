#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_OUT_MD = "runs/rocm_environment_manifest_current.md"

ROCM_ENV_KEYS = (
    "ROCM_HOME",
    "ROCM_PATH",
    "HIP_PATH",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "AMD_VISIBLE_DEVICES",
    "HSA_OVERRIDE_GFX_VERSION",
    "PYTORCH_ROCM_ARCH",
    "TORCH_BLAS_PREFER_HIPBLASLT",
    "FORCE_RUST_HIP",
    "RUST_HIP_USE_GPU_NBLIST_BUILDER",
    "RUST_HIP_USE_FUSED_CELL",
    "RUST_HIP_NBLIST_AUTOGROW",
    "LD_LIBRARY_PATH",
)

PROBE_COMMANDS: dict[str, list[str]] = {
    "rocminfo": ["rocminfo"],
    "rocm_smi": ["rocm-smi", "--showproductname", "--showdriverversion", "--showmeminfo", "vram"],
    "hipcc": ["hipcc", "--version"],
}
TORCH_VISIBILITY_PROBE_COMMAND = (
    "python3 -c \"import torch; "
    "print('torch_version=' + str(torch.__version__)); "
    "print('torch_hip_version=' + str(getattr(torch.version, 'hip', '') or '')); "
    "print('cuda_available=' + str(torch.cuda.is_available())); "
    "print('visible_device_count=' + str(torch.cuda.device_count())); "
    "print('device_names=' + ','.join(torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())))\""
)
GPU_VISIBILITY_DIAGNOSTIC_COMMANDS = [
    "python3 tools/build_rocm_environment_manifest.py",
    "rocminfo",
    "rocm-smi --showproductname --showdriverversion --showmeminfo vram",
    "hipcc --version",
    TORCH_VISIBILITY_PROBE_COMMAND,
]
GPU_VISIBILITY_DIAGNOSTIC_REQUIRED_FIELDS = [
    "manifest_ready",
    "rocm_stack_detected",
    "torch_rocm_ready",
    "amd_gpu_detected",
    "visible_device_count",
    "device_names",
    "torch_version",
    "torch_hip_version",
]

CLAIM_BOUNDARY = (
    "ROCm environment manifest only; records local AMD/ROCm/HIP/PyTorch readiness evidence. "
    "It does not install packages, run docking, run benchmarks, mutate external state, submit predictions, "
    "register servers, send email, upload, archive, externalize, or delete files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_command(cmd: Sequence[str], timeout_seconds: int = 8) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=int(timeout_seconds),
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return {
            "cmd": list(cmd),
            "available": bool(shutil.which(cmd[0])) if cmd else False,
            "returncode": None,
            "ok": False,
            "stdout_excerpt": "",
            "stderr_excerpt": str(exc),
        }
    return {
        "cmd": list(cmd),
        "available": bool(shutil.which(cmd[0])) if cmd else False,
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_excerpt": "\n".join((proc.stdout or "").splitlines()[:40]),
        "stderr_excerpt": "\n".join((proc.stderr or "").splitlines()[:20]),
    }


def _collect_torch_probe() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {
            "present": False,
            "import_error": f"{type(exc).__name__}: {exc}",
            "version": "",
            "hip_version": "",
            "cuda_available": False,
            "device_count": 0,
            "device_names": [],
        }

    cuda_module = getattr(torch, "cuda", None)
    cuda_available = bool(cuda_module is not None and cuda_module.is_available())
    device_count = 0
    device_names: list[str] = []
    if cuda_module is not None:
        try:
            device_count = int(cuda_module.device_count())
            for idx in range(device_count):
                try:
                    device_names.append(str(cuda_module.get_device_name(idx)))
                except Exception:
                    device_names.append(f"device_{idx}")
        except Exception:
            device_count = 0
            device_names = []
    return {
        "present": True,
        "import_error": "",
        "version": str(getattr(torch, "__version__", "")),
        "hip_version": str(getattr(getattr(torch, "version", None), "hip", "") or ""),
        "cuda_available": cuda_available,
        "device_count": device_count,
        "device_names": device_names,
    }


def _extract_rocm_version(env: Mapping[str, str], command_probes: Mapping[str, dict[str, Any]]) -> str:
    if env.get("ROCM_VERSION"):
        return str(env["ROCM_VERSION"])
    for key in ("ROCM_PATH", "ROCM_HOME", "HIP_PATH"):
        value = str(env.get(key, "")).strip()
        for part in value.replace("_", "-").split("-"):
            if part and part[0].isdigit():
                return part
    combined = "\n".join(str(probe.get("stdout_excerpt", "")) for probe in command_probes.values())
    for token in combined.replace(",", " ").split():
        cleaned = token.strip("()[],:;")
        if cleaned and cleaned[0].isdigit() and "." in cleaned:
            return cleaned
    return ""


def build_rocm_environment_manifest(
    *,
    env: Mapping[str, str] | None = None,
    command_runner: Callable[[Sequence[str], int], dict[str, Any]] | None = None,
    torch_probe: dict[str, Any] | None = None,
    probe_commands: bool = True,
) -> dict[str, Any]:
    effective_env = dict(os.environ if env is None else env)
    runner = command_runner or _run_command
    command_probes: dict[str, dict[str, Any]] = {}
    for label, cmd in PROBE_COMMANDS.items():
        if probe_commands:
            probe = dict(runner(cmd, 8))
        else:
            probe = {
                "cmd": list(cmd),
                "available": bool(shutil.which(cmd[0])),
                "returncode": None,
                "ok": False,
                "stdout_excerpt": "",
                "stderr_excerpt": "command probes skipped",
            }
        probe.setdefault("cmd", list(cmd))
        probe.setdefault("available", bool(shutil.which(cmd[0])))
        probe.setdefault("ok", False)
        probe.setdefault("stdout_excerpt", "")
        probe.setdefault("stderr_excerpt", "")
        command_probes[label] = probe

    torch_info = torch_probe if torch_probe is not None else _collect_torch_probe()
    runtime_env_vars = {key: effective_env[key] for key in ROCM_ENV_KEYS if effective_env.get(key)}
    torch_hip_version = str(torch_info.get("hip_version") or "")
    rocm_tooling_present = any(bool(probe.get("available")) for probe in command_probes.values())
    rocm_tooling_ok = any(bool(probe.get("ok")) for probe in command_probes.values())
    torch_rocm_ready = bool(torch_info.get("present")) and bool(torch_hip_version) and bool(torch_info.get("cuda_available"))
    amd_gpu_detected = bool(torch_info.get("device_count")) or bool(command_probes.get("rocm_smi", {}).get("ok"))
    rocm_stack_detected = bool(runtime_env_vars or rocm_tooling_present or torch_hip_version)
    manifest_ready = bool(rocm_stack_detected and (torch_rocm_ready or (rocm_tooling_ok and amd_gpu_detected)))
    production_execution_ready = bool(torch_rocm_ready and int(torch_info.get("device_count") or 0) > 0)
    rocm_version = _extract_rocm_version(effective_env, command_probes)

    uname = platform.uname()
    required_fields = {
        "os_name": bool(uname.system),
        "os_version": bool(platform.platform()),
        "kernel_version": bool(uname.release),
        "amd_gpu_model": bool(torch_info.get("device_names") or command_probes.get("rocm_smi", {}).get("stdout_excerpt")),
        "gpu_architecture": bool(effective_env.get("PYTORCH_ROCM_ARCH") or effective_env.get("HSA_OVERRIDE_GFX_VERSION")),
        "vram_total_free": bool(command_probes.get("rocm_smi", {}).get("ok")),
        "rocm_version": bool(rocm_version),
        "hip_version": bool(torch_hip_version or command_probes.get("hipcc", {}).get("ok")),
        "hipcc_version": bool(command_probes.get("hipcc", {}).get("stdout_excerpt")),
        "rocminfo_availability": bool(command_probes.get("rocminfo", {}).get("available")),
        "rocm_smi_availability": bool(command_probes.get("rocm_smi", {}).get("available")),
        "pytorch_version": bool(torch_info.get("version")),
        "pytorch_hip_version": bool(torch_hip_version),
        "torch_cuda_available": "cuda_available" in torch_info,
        "visible_device_count": "device_count" in torch_info,
        "runtime_env_vars": bool(runtime_env_vars),
        "manifest_generation_command": True,
    }
    missing_manifest_fields = [key for key, present in required_fields.items() if not present]

    summary = {
        "packet_type": "rocm_environment_manifest",
        "status": "rocm_environment_manifest_ready" if manifest_ready else "blocked_rocm_environment_manifest",
        "manifest_ready": manifest_ready,
        "generated_at": _now_local(),
        "commercial_compute_default": "rocm_hip",
        "cpu_fallback_available": True,
        "rocm_stack_detected": rocm_stack_detected,
        "rocm_tooling_present": rocm_tooling_present,
        "rocm_tooling_ok": rocm_tooling_ok,
        "amd_gpu_detected": amd_gpu_detected,
        "torch_present": bool(torch_info.get("present")),
        "torch_version": str(torch_info.get("version") or ""),
        "torch_hip_version": torch_hip_version,
        "torch_rocm_ready": torch_rocm_ready,
        "torch_cuda_available": bool(torch_info.get("cuda_available")),
        "visible_device_count": int(torch_info.get("device_count") or 0),
        "device_names": list(torch_info.get("device_names") or []),
        "rocm_version": rocm_version,
        "hipcc_present": bool(command_probes.get("hipcc", {}).get("available")),
        "hipcc_ok": bool(command_probes.get("hipcc", {}).get("ok")),
        "rocminfo_present": bool(command_probes.get("rocminfo", {}).get("available")),
        "rocminfo_ok": bool(command_probes.get("rocminfo", {}).get("ok")),
        "rocm_smi_present": bool(command_probes.get("rocm_smi", {}).get("available")),
        "rocm_smi_ok": bool(command_probes.get("rocm_smi", {}).get("ok")),
        "relevant_env_var_count": len(runtime_env_vars),
        "runtime_env_vars": runtime_env_vars,
        "required_manifest_field_count": len(required_fields),
        "present_manifest_field_count": len(required_fields) - len(missing_manifest_fields),
        "missing_manifest_field_count": len(missing_manifest_fields),
        "missing_manifest_fields": missing_manifest_fields,
        "manifest_generation_command": "python3 tools/build_rocm_environment_manifest.py",
        "gpu_visibility_diagnostic_packet_ready": True,
        "gpu_visibility_diagnostic_command_count": len(GPU_VISIBILITY_DIAGNOSTIC_COMMANDS),
        "gpu_visibility_diagnostic_commands": list(GPU_VISIBILITY_DIAGNOSTIC_COMMANDS),
        "gpu_visibility_diagnostic_required_fields": list(GPU_VISIBILITY_DIAGNOSTIC_REQUIRED_FIELDS),
        "gpu_visibility_diagnostic_required_field_count": len(GPU_VISIBILITY_DIAGNOSTIC_REQUIRED_FIELDS),
        "gpu_visibility_diagnostic_completion_rule": (
            "manifest_ready=true; rocm_stack_detected=true; torch_rocm_ready=true; "
            "amd_gpu_detected=true; visible_device_count>0; device_names nonempty"
        ),
        "gpu_visibility_diagnostic_return_artifacts": [
            "runs/rocm_environment_manifest_current.json",
            "runs/rocm_environment_manifest_current.md",
        ],
        "gpu_visibility_torch_probe_command": TORCH_VISIBILITY_PROBE_COMMAND,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Build AMD hardware throughput scorecard next."
            if production_execution_ready
            else (
                "Expose a visible ROCm/HIP AMD GPU device to PyTorch before production regeneration."
                if manifest_ready
                else "Expose a supported AMD ROCm/HIP runtime or document CPU fallback before AMD product packaging claims."
            )
        ),
    }
    return {
        "summary": summary,
        "platform": {
            "system": uname.system,
            "node": uname.node,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
            "platform": platform.platform(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
        },
        "torch": torch_info,
        "command_probes": command_probes,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# ROCm Environment Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- manifest_ready: `{s['manifest_ready']}`",
        f"- commercial_compute_default: `{s['commercial_compute_default']}`",
        f"- cpu_fallback_available: `{s['cpu_fallback_available']}`",
        f"- rocm_stack_detected: `{s['rocm_stack_detected']}`",
        f"- rocm_tooling_ok: `{s['rocm_tooling_ok']}`",
        f"- amd_gpu_detected: `{s['amd_gpu_detected']}`",
        f"- torch_rocm_ready: `{s['torch_rocm_ready']}`",
        f"- torch_version: `{s['torch_version']}`",
        f"- torch_hip_version: `{s['torch_hip_version']}`",
        f"- visible_device_count: `{s['visible_device_count']}`",
        f"- rocm_version: `{s['rocm_version']}`",
        f"- gpu_visibility_diagnostic_packet_ready: `{s['gpu_visibility_diagnostic_packet_ready']}`",
        f"- gpu_visibility_diagnostic_command_count: `{s['gpu_visibility_diagnostic_command_count']}`",
        f"- gpu_visibility_diagnostic_completion_rule: `{s['gpu_visibility_diagnostic_completion_rule']}`",
        f"- missing_manifest_field_count: `{s['missing_manifest_field_count']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- benchmark_executed: `{s['benchmark_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Missing Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in s["missing_manifest_fields"]) if s["missing_manifest_fields"] else lines.append("- none")
    lines.extend(["", "## GPU Visibility Diagnostics", ""])
    lines.extend(f"- `{command}`" for command in s["gpu_visibility_diagnostic_commands"])
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ROCm/HIP environment manifest for AMD productization.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--skip-command-probes", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_rocm_environment_manifest(probe_commands=not bool(args.skip_command_probes))
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
