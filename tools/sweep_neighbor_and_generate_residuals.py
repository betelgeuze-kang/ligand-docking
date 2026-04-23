#!/usr/bin/env python3

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import torch

from benchmark.performance_bench import benchmark_simulation
from core.config import config
from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.topology import TopologyFactory
from tools.generate_perturbed_data import DataGenerator
from tools.pdb_loader import load_native_structure


@dataclass
class SweepRecord:
    target: str
    cutoff: float
    skin: float
    throughput: float
    step_ms: float
    force_rmse: float
    score: float
    neighbor_settings: Dict[str, float]


def _parse_float_list(spec: str) -> List[float]:
    return [float(x.strip()) for x in spec.split(",") if x.strip()]


def _wrap_box(c: torch.Tensor, box: torch.Tensor) -> torch.Tensor:
    return torch.remainder(c, box.view(1, 1, 3))


def estimate_force_rmse(
    target: str,
    neighbor_settings: Dict[str, float],
    samples: int,
    noise: float,
    reference_cutoff: float,
    reference_max_neighbors: int,
    force_backend: str,
) -> float:
    t_conf = ResearchConstants.CHALLENGES[target]
    top = TopologyFactory(t_conf["n_res"], t_conf["type"], t_conf["box"], config.DEVICE, target_name=target)
    ff = ForceField(
        top,
        params={"d_e": 20.0, "eps_solv": 25.0, "sigma": 3.8, "r0": 4.2},
        neighbor_settings=neighbor_settings,
        force_backend=force_backend,
    ).to(config.DEVICE)

    native_coords, _ = load_native_structure(target)
    if native_coords is None:
        native_coords = torch.linspace(0, t_conf["n_res"] - 1, t_conf["n_res"], device=config.DEVICE).view(1, t_conf["n_res"], 1).repeat(1, 1, 3)
    elif native_coords.dim() == 2:
        native_coords = native_coords.unsqueeze(0)
    native_coords = native_coords.to(config.DEVICE)
    box = torch.as_tensor(t_conf["box"], dtype=torch.float32, device=config.DEVICE)

    rmses = []
    for _ in range(samples):
        c = native_coords + torch.randn_like(native_coords) * noise
        c = _wrap_box(c, box)
        with torch.no_grad():
            f_pred, _ = ff.compute(c, None)
            f_ref, _ = ff.compute_reference_pytorch(
                c,
                cutoff=reference_cutoff,
                max_neighbors=reference_max_neighbors,
                skin=0.0,
            )
        rmse = torch.sqrt(torch.mean((f_pred - f_ref) ** 2)).item()
        rmses.append(rmse)

    return float(sum(rmses) / max(len(rmses), 1))


def run_sweep(
    targets: List[str],
    cutoffs: List[float],
    skins: List[float],
    steps: int,
    runs: int,
    max_neighbors: int,
    max_atoms_per_cell: int,
    rebuild_stride: int,
    eval_samples: int,
    eval_noise: float,
    reference_cutoff: float,
    reference_max_neighbors: int,
    force_rust: bool,
) -> List[SweepRecord]:
    records: List[SweepRecord] = []
    if force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"

    for target in targets:
        for cutoff in cutoffs:
            for skin in skins:
                neighbor_settings = {
                    "grid_spacing": float(cutoff),
                    "cutoff": float(cutoff),
                    "skin": float(skin),
                    "max_neighbors": int(max_neighbors),
                    "max_atoms_per_cell": int(max_atoms_per_cell),
                    "rebuild_stride": int(rebuild_stride),
                }
                perf = benchmark_simulation(
                    target=target,
                    steps=steps,
                    use_ai_router=False,
                    num_runs=runs,
                    output_file="benchmark_results.csv",
                    neighbor_settings=neighbor_settings,
                )
                force_backend = "auto" if force_rust else "pytorch"
                force_rmse = estimate_force_rmse(
                    target=target,
                    neighbor_settings=neighbor_settings,
                    samples=eval_samples,
                    noise=eval_noise,
                    reference_cutoff=reference_cutoff,
                    reference_max_neighbors=reference_max_neighbors,
                    force_backend=force_backend,
                )
                throughput = float(perf["avg_throughput_steps_per_sec"])
                step_ms = float(perf["avg_time_per_step_ms"])
                score = throughput / (1.0 + force_rmse)
                records.append(
                    SweepRecord(
                        target=target,
                        cutoff=float(cutoff),
                        skin=float(skin),
                        throughput=throughput,
                        step_ms=step_ms,
                        force_rmse=force_rmse,
                        score=score,
                        neighbor_settings=neighbor_settings,
                    )
                )
    return records


def select_best(records: List[SweepRecord]) -> Dict[str, SweepRecord]:
    best: Dict[str, SweepRecord] = {}
    for rec in records:
        old = best.get(rec.target)
        if old is None or rec.score > old.score:
            best[rec.target] = rec
    return best


def generate_residual_data(
    selected: Dict[str, SweepRecord],
    samples_per_target: int,
    output_dir: str,
    explicit_2bead: bool,
    reference_cutoff: float,
    reference_max_neighbors: int,
):
    for target, rec in selected.items():
        gen = DataGenerator(
            target=target,
            total_samples=samples_per_target,
            noise=0.15,
            output_dir=output_dir,
            train_ratio=0.8,
            val_ratio=0.1,
            fast_mode=False,
            explicit_2bead=explicit_2bead,
            neighbor_settings=rec.neighbor_settings,
            residual_mode=True,
            reference_cutoff=reference_cutoff,
            reference_max_neighbors=reference_max_neighbors,
        )
        ok = gen.generate()
        if not ok:
            raise RuntimeError(f"Residual data generation failed for {target}")


def main():
    parser = argparse.ArgumentParser(description="Sweep neighbor parameters and generate residual-learning datasets.")
    parser.add_argument("--targets", type=str, default="Chignolin,Ubiquitin_Mini")
    parser.add_argument("--cutoffs", type=str, default="10,12,14")
    parser.add_argument("--skins", type=str, default="1,2,3")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--eval-samples", type=int, default=4)
    parser.add_argument("--eval-noise", type=float, default=0.12)
    parser.add_argument("--reference-cutoff", type=float, default=14.0)
    parser.add_argument("--reference-max-neighbors", type=int, default=160)
    parser.add_argument("--force-rust", action="store_true")
    parser.add_argument("--residual-samples-per-target", type=int, default=2000)
    parser.add_argument("--residual-output-dir", type=str, default="data/residual_sweep")
    parser.add_argument("--explicit-2bead", action="store_true")
    parser.add_argument("--report-json", type=str, default="runs/neighbor_sweep_report.json")
    parser.add_argument("--report-csv", type=str, default="runs/neighbor_sweep_report.csv")
    args = parser.parse_args()

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    cutoffs = _parse_float_list(args.cutoffs)
    skins = _parse_float_list(args.skins)

    records = run_sweep(
        targets=targets,
        cutoffs=cutoffs,
        skins=skins,
        steps=args.steps,
        runs=args.runs,
        max_neighbors=args.max_neighbors,
        max_atoms_per_cell=args.max_atoms_per_cell,
        rebuild_stride=args.rebuild_stride,
        eval_samples=args.eval_samples,
        eval_noise=args.eval_noise,
        reference_cutoff=args.reference_cutoff,
        reference_max_neighbors=args.reference_max_neighbors,
        force_rust=args.force_rust,
    )

    os.makedirs(os.path.dirname(args.report_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.report_json) or ".", exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "target": r.target,
                "cutoff": r.cutoff,
                "skin": r.skin,
                "throughput": r.throughput,
                "step_ms": r.step_ms,
                "force_rmse": r.force_rmse,
                "score": r.score,
                "neighbor_settings": json.dumps(r.neighbor_settings),
            }
            for r in records
        ]
    )
    df.to_csv(args.report_csv, index=False)

    best = select_best(records)
    summary = {
        "best_by_target": {
            target: {
                "cutoff": rec.cutoff,
                "skin": rec.skin,
                "throughput": rec.throughput,
                "step_ms": rec.step_ms,
                "force_rmse": rec.force_rmse,
                "score": rec.score,
                "neighbor_settings": rec.neighbor_settings,
            }
            for target, rec in best.items()
        }
    }
    with open(args.report_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    generate_residual_data(
        selected=best,
        samples_per_target=args.residual_samples_per_target,
        output_dir=args.residual_output_dir,
        explicit_2bead=args.explicit_2bead,
        reference_cutoff=args.reference_cutoff,
        reference_max_neighbors=args.reference_max_neighbors,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
