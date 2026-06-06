#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_THROUGHPUT_SCORECARD_JSON = "runs/amd_hardware_throughput_scorecard_current.json"
DEFAULT_PUBLIC_REGRESSION_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_REQUIREMENTS_ROCM = "requirements-rocm.txt"
DEFAULT_REQUIREMENTS_CPU = "requirements-cpu.txt"
DEFAULT_REQUIREMENTS_DEV = "requirements-dev.txt"
DEFAULT_OUT_JSON = "runs/amd_workstation_server_packaging_profile_current.json"
DEFAULT_OUT_CSV = "runs/amd_workstation_server_packaging_profile_current.csv"
DEFAULT_OUT_MD = "runs/amd_workstation_server_packaging_profile_current.md"

CLAIM_BOUNDARY = (
    "AMD workstation/server packaging profile only; records packaging requirements, local ROCm evidence, dependency "
    "profiles, install/smoke/report guide surfaces, and delivery policy. It does not assemble a customer bundle, run "
    "docking, train models, install packages, upload, submit, email, archive, externalize, or delete files. Multi-GPU "
    "server support is documented as a topology policy unless current hardware evidence shows multiple ROCm devices."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _vram_total_gb(rocm_manifest_packet: dict[str, Any]) -> float:
    text = str(rocm_manifest_packet.get("command_probes", {}).get("rocm_smi", {}).get("stdout_excerpt", ""))
    match = re.search(r"VRAM Total Memory \(B\):\s*([0-9]+)", text)
    if not match:
        return 0.0
    return round(int(match.group(1)) / (1024**3), 3)


def _file_ready(path_like: str | Path) -> bool:
    path = _resolve(path_like)
    return path.exists() and path.is_file() and path.stat().st_size > 0


def _row(component: str, status: str, evidence: str, required: str, reason: str) -> dict[str, Any]:
    return {
        "component": component,
        "status": status,
        "evidence": evidence,
        "required": required,
        "reason": reason,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_amd_workstation_server_packaging_profile(
    *,
    rocm_manifest_packet: dict[str, Any],
    throughput_scorecard_packet: dict[str, Any],
    public_regression_packet: dict[str, Any],
    gpcr_proof_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
    requirements_rocm_path: str = DEFAULT_REQUIREMENTS_ROCM,
    requirements_cpu_path: str = DEFAULT_REQUIREMENTS_CPU,
    requirements_dev_path: str = DEFAULT_REQUIREMENTS_DEV,
) -> dict[str, Any]:
    rocm = _summary(rocm_manifest_packet)
    throughput = _summary(throughput_scorecard_packet)
    public_regression = _summary(public_regression_packet)
    gpcr_proof = _summary(gpcr_proof_packet)
    residual_shadow = _summary(residual_shadow_packet)

    device_names = list(rocm.get("device_names") or [])
    visible_device_count = int(rocm.get("visible_device_count") or 0)
    vram_gb = _vram_total_gb(rocm_manifest_packet)
    rocm_ready = _text(rocm.get("status")) == "rocm_environment_manifest_ready" and rocm.get("manifest_ready") is True
    throughput_ready = _text(throughput.get("status")) == "amd_hardware_throughput_scorecard_ready" and throughput.get("scorecard_ready") is True
    public_gate_ready = (
        _text(public_regression.get("status")) == "public_benchmark_residual_regression_gate_ready"
        and public_regression.get("regression_gate_ready") is True
    )
    gpcr_ready = _text(gpcr_proof.get("status")) == "gpcr_hard_decoy_residual_proof_ready" and gpcr_proof.get("proof_ready") is True
    residual_ready = _text(residual_shadow.get("status")) == "residual_shadow_ab_scaffold_ready" and residual_shadow.get("scaffold_ready") is True
    requirements_rocm_ready = _file_ready(requirements_rocm_path)
    requirements_cpu_ready = _file_ready(requirements_cpu_path)
    requirements_dev_ready = _file_ready(requirements_dev_path)
    workstation_profile_ready = bool(rocm_ready and throughput_ready and visible_device_count >= 1 and vram_gb >= 8.0)
    server_profile_ready = bool(rocm_ready and throughput_ready and visible_device_count >= 1)
    install_guide_ready = bool(requirements_rocm_ready and requirements_cpu_ready and requirements_dev_ready)
    smoke_guide_ready = bool(throughput_ready and public_gate_ready)
    report_guide_ready = bool(public_gate_ready and gpcr_ready and residual_ready)

    rows = [
        _row(
            "AMD Workstation Profile",
            "pass" if workstation_profile_ready else "fail",
            ", ".join(device_names) or "missing",
            ">=1 AMD ROCm GPU, >=8GB VRAM, ROCm/PyTorch ready, smoke throughput scorecard ready",
            "Single-user/local profile is ready for small/medium docking and benchmark smoke workloads.",
        ),
        _row(
            "AMD Server Profile",
            "pass" if server_profile_ready else "fail",
            f"visible_device_count={visible_device_count}",
            "ROCm-visible AMD GPU topology documented; multi-GPU claim requires multi-device evidence",
            "Server packaging policy is ready; current hardware is recorded as single-GPU unless more devices are visible.",
        ),
        _row(
            "requirements-rocm.txt",
            "pass" if requirements_rocm_ready else "fail",
            requirements_rocm_path,
            "AMD ROCm/HIP production runtime dependency profile",
            "ROCm runtime profile is separate from CPU/dev profiles.",
        ),
        _row(
            "requirements-cpu.txt",
            "pass" if requirements_cpu_ready else "fail",
            requirements_cpu_path,
            "CPU fallback runtime dependency profile",
            "CPU fallback remains available but is not the commercial compute default.",
        ),
        _row(
            "requirements-dev.txt",
            "pass" if requirements_dev_ready else "fail",
            requirements_dev_path,
            "developer/test tooling dependency profile",
            "Developer tooling is separated from production runtime.",
        ),
        _row(
            "install guide surface",
            "pass" if install_guide_ready else "fail",
            "requirements-rocm.txt; requirements-cpu.txt; requirements-dev.txt",
            "install guide references separated dependency profiles",
            "The package can tell operators which profile to install for ROCm, CPU fallback, and development.",
        ),
        _row(
            "smoke benchmark guide surface",
            "pass" if smoke_guide_ready else "fail",
            "runs/amd_hardware_throughput_scorecard_current.json; runs/public_benchmark_residual_regression_gate_current.json",
            "ROCm smoke and public regression gates ready",
            "The package has a reproducible hardware smoke evidence path.",
        ),
        _row(
            "report bundle guide surface",
            "pass" if report_guide_ready else "fail",
            "runs/residual_shadow_ab_current.json; runs/gpcr_hard_decoy_residual_proof_current.json; runs/public_benchmark_residual_regression_gate_current.json",
            "residual, GPCR proof, and public benchmark gate artifacts ready",
            "Report bundle inputs are present for the alpha handoff surface.",
        ),
    ]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    packaging_ready = not fail_rows
    summary = {
        "packet_type": "amd_workstation_server_packaging_profile",
        "status": "amd_workstation_server_packaging_profile_ready" if packaging_ready else "blocked_amd_workstation_server_packaging_profile",
        "amd_workstation_server_packaging_profile_ready": packaging_ready,
        "packaging_ready": packaging_ready,
        "workstation_profile_ready": workstation_profile_ready,
        "server_profile_ready": server_profile_ready,
        "install_guide_ready": install_guide_ready,
        "smoke_benchmark_guide_ready": smoke_guide_ready,
        "report_bundle_guide_ready": report_guide_ready,
        "commercial_compute_default": "rocm_hip",
        "cpu_fallback_available": True,
        "supported_amd_gpu_family": device_names,
        "visible_device_count": visible_device_count,
        "current_topology": "single_gpu" if visible_device_count == 1 else ("multi_gpu" if visible_device_count > 1 else "missing_gpu"),
        "server_multi_gpu_claim_ready": visible_device_count > 1,
        "recommended_workstation_vram_gb": 16,
        "observed_vram_total_gb": vram_gb,
        "recommended_ram_gb": 64,
        "recommended_storage_gb": 500,
        "rocm_version": _text(rocm.get("rocm_version")),
        "torch_version": _text(rocm.get("torch_version")),
        "torch_hip_version": _text(rocm.get("torch_hip_version")),
        "ligands_per_hour": throughput.get("ligands_per_hour"),
        "cpu_vs_rocm_speedup": throughput.get("cpu_vs_rocm_speedup"),
        "requirements_rocm": requirements_rocm_path,
        "requirements_cpu": requirements_cpu_path,
        "requirements_dev": requirements_dev_path,
        "component_count": len(rows),
        "pass_component_count": len(rows) - len(fail_rows),
        "fail_component_count": len(fail_rows),
        "approval_tokens_required": [],
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Proceed to customer-facing alpha bundle manifest."
            if packaging_ready
            else "Repair AMD packaging components before alpha bundle handoff."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# AMD Workstation/Server Packaging Profile",
        "",
        f"- status: `{s['status']}`",
        f"- packaging_ready: `{s['packaging_ready']}`",
        f"- workstation_profile_ready: `{s['workstation_profile_ready']}`",
        f"- server_profile_ready: `{s['server_profile_ready']}`",
        f"- commercial_compute_default: `{s['commercial_compute_default']}`",
        f"- supported_amd_gpu_family: `{', '.join(s['supported_amd_gpu_family'])}`",
        f"- current_topology: `{s['current_topology']}`",
        f"- server_multi_gpu_claim_ready: `{s['server_multi_gpu_claim_ready']}`",
        f"- observed_vram_total_gb: `{s['observed_vram_total_gb']}`",
        f"- rocm_version: `{s['rocm_version']}`",
        f"- torch_hip_version: `{s['torch_hip_version']}`",
        f"- pass_component_count: `{s['pass_component_count']}` / `{s['component_count']}`",
        "",
        "## Components",
        "",
        "| component | status | evidence | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['component']}` | `{row['status']}` | `{row['evidence']}` | {row['required']} | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AMD workstation/server packaging profile from productization evidence.")
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--throughput-scorecard-json", default=DEFAULT_THROUGHPUT_SCORECARD_JSON)
    parser.add_argument("--public-regression-json", default=DEFAULT_PUBLIC_REGRESSION_JSON)
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--requirements-rocm", default=DEFAULT_REQUIREMENTS_ROCM)
    parser.add_argument("--requirements-cpu", default=DEFAULT_REQUIREMENTS_CPU)
    parser.add_argument("--requirements-dev", default=DEFAULT_REQUIREMENTS_DEV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_amd_workstation_server_packaging_profile(
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        throughput_scorecard_packet=_read_json_if_present(args.throughput_scorecard_json),
        public_regression_packet=_read_json_if_present(args.public_regression_json),
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        requirements_rocm_path=args.requirements_rocm,
        requirements_cpu_path=args.requirements_cpu,
        requirements_dev_path=args.requirements_dev,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
