#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/casp17_backend_readiness_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_backend_readiness_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_backend_readiness_packet_current.md"

COMMANDS = (
    "python3",
    "pip",
    "pip3",
    "conda",
    "mamba",
    "micromamba",
    "uv",
    "nvidia-smi",
    "rocm-smi",
    "rocminfo",
    "hipcc",
    "colabfold_batch",
    "omegafold",
    "esm-fold",
    "esmfold",
)
PYTHON_MODULES = (
    "torch",
    "esm",
    "transformers",
    "colabfold",
    "openfold",
    "omegafold",
    "boltz",
    "chai_lab",
    "jax",
    "haiku",
)
CLI_BACKENDS = ("colabfold_batch", "omegafold", "esm-fold", "esmfold")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_text_command(command: list[str], timeout_seconds: int = 4) -> tuple[bool, str]:
    try:
        run = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - probe only.
        return False, f"{type(exc).__name__}: {exc}"
    return run.returncode == 0, (run.stdout or run.stderr or "").strip()


def _torch_probe() -> dict[str, Any]:
    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if cuda_available else 0
        return {
            "present": True,
            "version": _text(getattr(torch, "__version__", "")),
            "cuda_available": cuda_available,
            "device_count": device_count,
            "device_names": [str(torch.cuda.get_device_name(index)) for index in range(device_count)],
        }
    except Exception as exc:  # noqa: BLE001 - optional probe only.
        return {"present": False, "version": "", "cuda_available": False, "device_count": 0, "device_names": [], "error": str(exc)[:300]}


def _probe_environment() -> dict[str, Any]:
    commands = {command: shutil.which(command) or "" for command in COMMANDS}
    modules = {module: bool(importlib.util.find_spec(module)) for module in PYTHON_MODULES}
    torch = _torch_probe()
    rocm_smi_ok = False
    rocm_smi_text = ""
    if commands.get("rocm-smi"):
        rocm_smi_ok, rocm_smi_text = _run_text_command([commands["rocm-smi"], "--showproductname"], timeout_seconds=6)
    nvidia_smi_ok = False
    nvidia_smi_text = ""
    if commands.get("nvidia-smi"):
        nvidia_smi_ok, nvidia_smi_text = _run_text_command([commands["nvidia-smi"], "--query-gpu=name", "--format=csv,noheader"], timeout_seconds=6)
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "commands": commands,
        "python_modules": modules,
        "torch": torch,
        "rocm": {
            "rocm_smi_present": bool(commands.get("rocm-smi")),
            "rocminfo_present": bool(commands.get("rocminfo")),
            "rocm_smi_ok": rocm_smi_ok,
            "rocm_smi_output": rocm_smi_text[:1000],
        },
        "nvidia": {
            "nvidia_smi_present": bool(commands.get("nvidia-smi")),
            "nvidia_smi_ok": nvidia_smi_ok,
            "nvidia_smi_output": nvidia_smi_text[:1000],
        },
    }


def _probe(args: argparse.Namespace) -> dict[str, Any]:
    if _text(args.probe_json):
        payload = _read_json(args.probe_json)
        return payload.get("probe", payload) if isinstance(payload.get("probe", payload), dict) else {}
    return _probe_environment()


def _accelerator_status(probe: dict[str, Any]) -> tuple[str, str, list[str]]:
    torch = probe.get("torch", {}) if isinstance(probe.get("torch"), dict) else {}
    nvidia = probe.get("nvidia", {}) if isinstance(probe.get("nvidia"), dict) else {}
    rocm = probe.get("rocm", {}) if isinstance(probe.get("rocm"), dict) else {}
    device_names = [str(name) for name in torch.get("device_names", []) if _text(name)]
    if bool(torch.get("cuda_available")) and any("amd" in name.lower() or "radeon" in name.lower() for name in device_names):
        return "rocm_gpu_ready", "ROCm/PyTorch GPU is available.", device_names
    if bool(torch.get("cuda_available")) and (nvidia.get("nvidia_smi_present") or device_names):
        return "cuda_gpu_ready", "CUDA/PyTorch GPU is available.", device_names
    if bool(rocm.get("rocm_smi_present") or rocm.get("rocminfo_present")):
        return "rocm_tooling_present_torch_gpu_not_ready", "ROCm tooling exists but PyTorch GPU is not ready.", device_names
    return "gpu_not_detected", "No usable PyTorch GPU was detected.", device_names


def _backend_status(probe: dict[str, Any], accelerator_status: str) -> tuple[str, str, str, list[str]]:
    commands = probe.get("commands", {}) if isinstance(probe.get("commands"), dict) else {}
    modules = probe.get("python_modules", {}) if isinstance(probe.get("python_modules"), dict) else {}
    available_cli = [backend for backend in CLI_BACKENDS if _text(commands.get(backend))]
    if available_cli:
        selected = "colabfold_batch" if "colabfold_batch" in available_cli else available_cli[0]
        return "backend_cli_ready", selected, "Detected an executable structure prediction backend.", []
    if bool(modules.get("colabfold")) and bool(modules.get("jax")):
        return "python_backend_present_cli_missing", "colabfold_python", "ColabFold/JAX modules exist, but no launch CLI was detected.", ["missing_backend_cli_wrapper"]
    if bool(modules.get("esm")) or bool(modules.get("transformers")):
        return "python_backend_present_cli_missing", "esmfold_python", "ESM/Transformers modules exist, but no launch CLI was detected.", ["missing_backend_cli_wrapper"]
    if accelerator_status == "rocm_gpu_ready":
        return "rocm_gpu_without_structure_backend", "", "ROCm GPU is available, but no structure prediction backend is installed or wrapped.", ["missing_structure_prediction_backend"]
    if accelerator_status == "cuda_gpu_ready":
        return "cuda_gpu_without_structure_backend", "", "CUDA GPU is available, but no structure prediction backend is installed or wrapped.", ["missing_structure_prediction_backend"]
    return "backend_missing", "", "No supported structure prediction backend was detected.", ["missing_structure_prediction_backend"]


def _recommendation_rows(accelerator_status: str, backend_status: str, selected_backend: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "rank": 1,
            "lane": "attach_existing_structure_with_provenance",
            "status": "available_manual_path",
            "rationale": "A target-specific raw PDB or TS prediction can be attached through the provenance-gated existing-structure lane without installing a backend.",
            "command": (
                "python3 tools/build_casp17_existing_structure_intake_builder.py "
                "--structure-dir runs/casp17_existing_structures_current "
                "--provenance-csv runs/casp17_existing_structure_provenance_current.csv "
                "--author-code <CASP_AUTHOR_CODE>"
            ),
        }
    )
    if backend_status == "backend_cli_ready":
        rows.append(
            {
                "rank": 2,
                "lane": f"use_detected_{selected_backend}",
                "status": "ready_to_plan_launch",
                "rationale": "A supported CLI backend is detected; build the launch packet and review target-specific commands.",
                "command": "python3 tools/casp17/build_casp17_prediction_launch_packet.py",
            }
        )
    else:
        rows.append(
            {
                "rank": 2,
                "lane": "custom_backend_command",
                "status": "blocked_until_backend_command_supplied",
                "rationale": "Use the existing GPU with any local predictor that writes a raw PDB, then convert it to CASP17 TS format.",
                "command": "python3 tools/casp17/build_casp17_backend_profile_packet.py --supports-multimer",
            }
        )
    if accelerator_status == "rocm_gpu_ready":
        rows.append(
            {
                "rank": 3,
                "lane": "rocm_esmfold_environment_candidate",
                "status": "dependency_install_required_not_executed",
                "rationale": "This host exposes a ROCm PyTorch GPU; ESMFold-style PyTorch backends are a more natural first candidate than CUDA/JAX-only paths.",
                "command": "Create an isolated env, install a ROCm-compatible ESMFold/Transformers backend, then expose it through --custom-backend-command.",
            }
        )
        rows.append(
            {
                "rank": 4,
                "lane": "colabfold_cuda_lane",
                "status": "not_first_choice_on_rocm_host",
                "rationale": "ColabFold commonly depends on JAX/CUDA packaging; use only if a compatible local build is intentionally provisioned.",
                "command": "Do not install globally; build an isolated env and verify GPU execution before wiring it to launch packet.",
            }
        )
    elif accelerator_status == "cuda_gpu_ready":
        rows.append(
            {
                "rank": 3,
                "lane": "colabfold_cuda_environment_candidate",
                "status": "dependency_install_required_not_executed",
                "rationale": "CUDA GPU is available; ColabFold batch is the preferred launch shape when installed in an isolated env.",
                "command": "Install a local isolated ColabFold env, verify colabfold_batch, then run tools/casp17/build_casp17_prediction_launch_packet.py.",
            }
        )
    else:
        rows.append(
            {
                "rank": 3,
                "lane": "gpu_enablement_first",
                "status": "blocked_until_gpu_or_remote_backend_ready",
                "rationale": "No usable PyTorch GPU was detected; avoid CPU fallback for CASP17 target generation.",
                "command": "Fix GPU runtime or attach externally generated target-specific predictions.",
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    probe = _probe(args)
    accelerator_status, accelerator_reason, device_names = _accelerator_status(probe)
    backend_status, selected_backend, backend_reason, blockers = _backend_status(probe, accelerator_status)
    rows = _recommendation_rows(accelerator_status, backend_status, selected_backend)
    summary = {
        "packet_type": "casp17_backend_readiness_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "accelerator_status": accelerator_status,
        "accelerator_reason": accelerator_reason,
        "device_names": device_names,
        "backend_status": backend_status,
        "selected_backend": selected_backend,
        "backend_reason": backend_reason,
        "ready_for_launch_packet": backend_status == "backend_cli_ready",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": "Backend readiness/provisioning guidance only; no dependency installation, prediction execution, validation, or CASP17 submission is performed.",
    }
    return {"summary": summary, "probe": probe, "recommendations": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["rank", "lane", "status", "rationale", "command"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    probe = payload.get("probe", {})
    commands = probe.get("commands", {}) if isinstance(probe.get("commands"), dict) else {}
    modules = probe.get("python_modules", {}) if isinstance(probe.get("python_modules"), dict) else {}
    available_commands = sorted(name for name in CLI_BACKENDS if _text(commands.get(name)))
    available_modules = sorted(name for name, present in modules.items() if present and name != "torch")
    lines = [
        "# CASP17 Backend Readiness Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- accelerator status: `{summary['accelerator_status']}`",
        f"- devices: `{','.join(summary['device_names']) if summary['device_names'] else '-'}`",
        f"- backend status: `{summary['backend_status']}`",
        f"- selected backend: `{summary['selected_backend'] or '-'}`",
        f"- ready for launch packet: `{summary['ready_for_launch_packet']}`",
        f"- blockers: `{';'.join(summary['blockers']) if summary['blockers'] else '-'}`",
        f"- detected backend commands: `{','.join(available_commands) if available_commands else 'none'}`",
        f"- detected backend modules: `{','.join(available_modules) if available_modules else 'none'}`",
        "",
        "## Recommendations",
        "",
        "| rank | lane | status | command |",
        "| ---: | --- | --- | --- |",
    ]
    for row in payload["recommendations"]:
        lines.append(f"| {row['rank']} | `{row['lane']}` | `{row['status']}` | `{row['command']}` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 structure-prediction backend readiness/provisioning packet.")
    parser.add_argument("--probe-json", default="", help="Optional deterministic probe JSON for tests/offline review.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["recommendations"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
