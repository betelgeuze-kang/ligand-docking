"""Measured projection stage only; includes cases where validation overhead wins.

No pass/fail speed threshold, no cross-call cache and no whole-docking claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

import torch

from betelgeuze_engine_v2.physics.reference_constrained_minimization import (
    _project_forces_to_constraint_tangent as historical,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import environment
from betelgeuze_product.cpu_refinement_v1_2.tangent_projection import project_tangent_forces
from tests.unit.test_cpu_refinement_v1_2_tangent_projection import fixture
from tests.unit.test_cpu_refinement_v1_2_physics import near_linear


def benchmark() -> dict:
    cases = []
    for seed in (0, 3):
        system, params, forces = fixture(seed)
        cases.append((f"star-{seed}", system, params, forces))
    for constrained in (True, False):
        system, params, _, _ = near_linear(constrained=constrained)
        forces = torch.arange(9, dtype=torch.float64).reshape(1, 3, 3)
        cases.append((f"near-linear-constrained-{constrained}", system, params, forces))
    config = SolverConfig(force_projection_max_sweeps=200)
    results = []
    for name, system, params, forces in cases:
        args = (system, system.coordinates, forces, params, config)
        old, new = historical(*args), project_tangent_forces(*args)
        if not torch.equal(old[0], new[0]) or old[1:] != new[1:]:
            raise AssertionError("benchmark comparison changed numerical result")
        methods = {"historical": historical, "call_local_geometry": project_tangent_forces}
        for _ in range(5):
            for function in methods.values():
                function(*args)
        samples = {method: {"wall_ns": [], "cpu_ns": []} for method in methods}
        for iteration in range(31):
            order = list(methods) if iteration % 2 == 0 else list(reversed(methods))
            for method in order:
                wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                methods[method](*args)
                samples[method]["cpu_ns"].append(time.process_time_ns() - cpu)
                samples[method]["wall_ns"].append(time.perf_counter_ns() - wall)
        results.append({"case": name, "atoms": system.atom_count, "constraints": len(params.constraints),
                        "sweeps": new[3], "converged": new[4], "bit_exact": True,
                        "samples": samples, "medians": {method: {
                            key: statistics.median(values) for key, values in timings.items()}
                            for method, timings in samples.items()}})
    return {"schema_id": "cpu_tangent_stage_benchmark/1.0.0", "environment": environment(),
            "config": config.to_dict(), "warmups": 5, "alternating_repetitions": 31,
            "results": results, "synthetic_only": True, "whole_docking_speedup_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(benchmark(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
