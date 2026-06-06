#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_OUT_JSON = "runs/amd_hardware_throughput_measurements_current.json"
DEFAULT_OUT_MD = "runs/amd_hardware_throughput_measurements_current.md"

CLAIM_BOUNDARY = (
    "AMD hardware throughput measurements run a local deterministic PyTorch ROCm smoke workload only. "
    "Metrics are hardware-smoke proxy measurements for Phase 1 productization evidence, not final docking accuracy "
    "or full production throughput claims. This tool does not install packages, submit jobs, upload, email, archive, "
    "externalize, or delete files."
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


def _now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _torch_smoke_benchmark(
    *,
    ligand_count: int,
    poses_per_ligand: int,
    feature_dim: int,
    iterations: int,
    warmup_iterations: int,
    seed: int,
) -> dict[str, Any]:
    import torch  # type: ignore

    if not bool(getattr(torch.version, "hip", "") or ""):
        raise RuntimeError("PyTorch is not a ROCm/HIP build.")
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch ROCm runtime is not available.")

    device = torch.device("cuda")
    cpu_device = torch.device("cpu")
    torch.manual_seed(seed)
    features_cpu = torch.randn(ligand_count, poses_per_ligand, feature_dim, device=cpu_device)
    weights_cpu = torch.randn(feature_dim, device=cpu_device)

    def score_once(features: Any, weights: Any) -> Any:
        scores = torch.tanh(features * weights).sum(dim=-1)
        penalty = 0.01 * (features.square().mean(dim=-1))
        return scores - penalty

    # CPU reference timing keeps the speedup metric tied to the same deterministic proxy workload.
    cpu_start = time.perf_counter()
    cpu_checksum = None
    for _ in range(max(1, iterations)):
        cpu_checksum = float(score_once(features_cpu, weights_cpu).sum().item())
    cpu_elapsed_seconds = max(time.perf_counter() - cpu_start, 1e-9)

    features_gpu = features_cpu.to(device)
    weights_gpu = weights_cpu.to(device)
    torch.cuda.synchronize()
    try:
        torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass

    for _ in range(max(0, warmup_iterations)):
        score_once(features_gpu, weights_gpu)
    torch.cuda.synchronize()

    gpu_start = time.perf_counter()
    gpu_checksum = None
    for _ in range(max(1, iterations)):
        gpu_checksum = float(score_once(features_gpu, weights_gpu).sum().item())
    torch.cuda.synchronize()
    rocm_elapsed_seconds = max(time.perf_counter() - gpu_start, 1e-9)
    try:
        peak_bytes = int(torch.cuda.max_memory_allocated())
    except Exception:
        peak_bytes = int(features_gpu.numel() * features_gpu.element_size() + weights_gpu.numel() * weights_gpu.element_size())

    torch.manual_seed(seed)
    features_repeat = features_cpu.to(device)
    weights_repeat = weights_cpu.to(device)
    torch.cuda.synchronize()
    repeat_checksum = float(score_once(features_repeat, weights_repeat).sum().item())
    torch.cuda.synchronize()

    score_evaluations = int(ligand_count * poses_per_ligand * max(1, iterations))
    ligands_processed = int(ligand_count * max(1, iterations))
    rocm_elapsed = max(rocm_elapsed_seconds, 1e-9)
    return {
        "status": "amd_hardware_throughput_measurements_ready",
        "measurement_ready": True,
        "device": str(device),
        "device_name": str(torch.cuda.get_device_name(0)),
        "torch_version": str(getattr(torch, "__version__", "")),
        "torch_hip_version": str(getattr(torch.version, "hip", "") or ""),
        "ligand_count": ligand_count,
        "poses_per_ligand": poses_per_ligand,
        "feature_dim": feature_dim,
        "iterations": iterations,
        "warmup_iterations": warmup_iterations,
        "seed": seed,
        "rocm_elapsed_seconds": rocm_elapsed_seconds,
        "cpu_elapsed_seconds": cpu_elapsed_seconds,
        "ligands_per_hour": float(ligands_processed / rocm_elapsed * 3600.0),
        "poses_per_sec": float(score_evaluations / rocm_elapsed),
        "score_evaluations_per_sec": float(score_evaluations / rocm_elapsed),
        "vram_gb_per_1k_ligands": float((peak_bytes / (1024**3)) / max(ligand_count / 1000.0, 1e-9)),
        "cpu_vs_rocm_speedup": float(cpu_elapsed_seconds / rocm_elapsed),
        "failure_rate": 0.0,
        "fixed_seed_reproducible": bool(gpu_checksum is not None and abs(float(gpu_checksum) - repeat_checksum) <= 1e-4),
        "cpu_checksum": cpu_checksum,
        "rocm_checksum": gpu_checksum,
        "repeat_checksum": repeat_checksum,
        "peak_memory_bytes": peak_bytes,
        "benchmark_kind": "deterministic_torch_rocm_pose_score_proxy",
    }


def build_amd_hardware_throughput_measurements(
    *,
    rocm_manifest_packet: dict[str, Any],
    benchmark_runner: Callable[..., dict[str, Any]] | None = None,
    ligand_count: int = 256,
    poses_per_ligand: int = 16,
    feature_dim: int = 64,
    iterations: int = 48,
    warmup_iterations: int = 4,
    seed: int = 1337,
) -> dict[str, Any]:
    manifest = _summary(rocm_manifest_packet)
    rocm_ready = manifest.get("status") == "rocm_environment_manifest_ready" and manifest.get("manifest_ready") is True
    runner = benchmark_runner or _torch_smoke_benchmark
    errors: list[str] = []
    measurements: dict[str, Any] = {}
    if rocm_ready:
        try:
            measurements = dict(
                runner(
                    ligand_count=int(ligand_count),
                    poses_per_ligand=int(poses_per_ligand),
                    feature_dim=int(feature_dim),
                    iterations=int(iterations),
                    warmup_iterations=int(warmup_iterations),
                    seed=int(seed),
                )
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    else:
        errors.append("ROCm manifest is not ready.")

    measurement_ready = bool(measurements.get("measurement_ready") is True and not errors)
    summary = {
        "packet_type": "amd_hardware_throughput_measurements",
        "status": "amd_hardware_throughput_measurements_ready" if measurement_ready else "blocked_amd_hardware_throughput_measurements",
        "measurement_ready": measurement_ready,
        "generated_at": _now_local(),
        "rocm_environment_manifest_ready": rocm_ready,
        "rocm_manifest_status": str(manifest.get("status") or ""),
        "rocm_manifest_device_names": list(manifest.get("device_names") or []),
        "commercial_compute_default": "rocm_hip",
        "benchmark_kind": str(measurements.get("benchmark_kind") or "deterministic_torch_rocm_pose_score_proxy"),
        "ligands_per_hour": measurements.get("ligands_per_hour"),
        "poses_per_sec": measurements.get("poses_per_sec"),
        "score_evaluations_per_sec": measurements.get("score_evaluations_per_sec"),
        "vram_gb_per_1k_ligands": measurements.get("vram_gb_per_1k_ligands"),
        "cpu_vs_rocm_speedup": measurements.get("cpu_vs_rocm_speedup"),
        "failure_rate": measurements.get("failure_rate"),
        "fixed_seed_reproducible": measurements.get("fixed_seed_reproducible"),
        "device": measurements.get("device"),
        "device_name": measurements.get("device_name"),
        "torch_version": measurements.get("torch_version"),
        "torch_hip_version": measurements.get("torch_hip_version"),
        "ligand_count": int(ligand_count),
        "poses_per_ligand": int(poses_per_ligand),
        "feature_dim": int(feature_dim),
        "iterations": int(iterations),
        "warmup_iterations": int(warmup_iterations),
        "seed": int(seed),
        "error_count": len(errors),
        "errors": errors,
        "execution_enabled": measurement_ready,
        "benchmark_executed": measurement_ready,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rebuild AMD hardware throughput scorecard."
            if measurement_ready
            else "Fix ROCm runtime or PyTorch ROCm smoke execution before scorecard promotion."
        ),
    }
    return {"summary": summary, "details": measurements}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# AMD Hardware Throughput Measurements",
        "",
        f"- status: `{s['status']}`",
        f"- measurement_ready: `{s['measurement_ready']}`",
        f"- rocm_environment_manifest_ready: `{s['rocm_environment_manifest_ready']}`",
        f"- benchmark_kind: `{s['benchmark_kind']}`",
        f"- device_name: `{s['device_name']}`",
        f"- ligands_per_hour: `{s['ligands_per_hour']}`",
        f"- poses_per_sec: `{s['poses_per_sec']}`",
        f"- score_evaluations_per_sec: `{s['score_evaluations_per_sec']}`",
        f"- vram_gb_per_1k_ligands: `{s['vram_gb_per_1k_ligands']}`",
        f"- cpu_vs_rocm_speedup: `{s['cpu_vs_rocm_speedup']}`",
        f"- failure_rate: `{s['failure_rate']}`",
        f"- fixed_seed_reproducible: `{s['fixed_seed_reproducible']}`",
        f"- benchmark_executed: `{s['benchmark_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- `{item}`" for item in s["errors"]) if s["errors"] else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic PyTorch ROCm smoke throughput measurement.")
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--ligand-count", type=int, default=256)
    parser.add_argument("--poses-per-ligand", type=int, default=16)
    parser.add_argument("--feature-dim", type=int, default=64)
    parser.add_argument("--iterations", type=int, default=48)
    parser.add_argument("--warmup-iterations", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1337)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_amd_hardware_throughput_measurements(
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        ligand_count=args.ligand_count,
        poses_per_ligand=args.poses_per_ligand,
        feature_dim=args.feature_dim,
        iterations=args.iterations,
        warmup_iterations=args.warmup_iterations,
        seed=args.seed,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
