"""Local benchmark harnesses for product evidence gates."""

from betelgeuze_engine.benchmark.runtime_scaling import (
    RuntimeScalingResult,
    build_capped_neighbor_pairs,
    run_runtime_scaling_benchmark,
    write_runtime_scaling_svg,
)

__all__ = [
    "RuntimeScalingResult",
    "build_capped_neighbor_pairs",
    "run_runtime_scaling_benchmark",
    "write_runtime_scaling_svg",
]
