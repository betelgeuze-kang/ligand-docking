"""Synthetic stage benchmark: exact full-pool summaries, not docking speedup."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

from betelgeuze_engine.product.censored_rank_metrics import compare_rankings
from betelgeuze_engine.product.paired_rank_metrics import compare_cohort


def benchmark():
    rows = []
    for n in (32, 128, 256):
        endpoints = {str(i): {"relation": ">" if i % 7 == 0 else "=", "value": i + 1} for i in range(n)}
        arms = {a: {str(i): None if i % 11 == 0 else -(i % 29) for i in range(n)} for a in ("a", "b", "c")}
        methods = {"legacy_details": lambda: compare_rankings(endpoints, arms),
                   "streaming_summary": lambda: compare_cohort(endpoints, arms, [])}
        old, new = methods["legacy_details"](), methods["streaming_summary"]()
        for arm in arms:
            assert old[arm]["concordance"] == new["full_coverage"][arm]["concordance"]
            for name, value in old[arm]["counts"].items():
                assert new["full_coverage"][arm]["counts"][name] == value
        for _ in range(2):
            for function in methods.values():
                function()
        samples = {name: [] for name in methods}
        for i in range(7):
            order = list(methods) if i % 2 == 0 else list(reversed(methods))
            for name in order:
                tick = time.perf_counter_ns()
                methods[name]()
                samples[name].append(time.perf_counter_ns() - tick)
        peak = {}
        for name in methods:
            tracemalloc.start()
            result = methods[name]()
            peak[name] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            del result
        rows.append({"candidates": n, "arms": len(arms), "pairs_per_arm": n*(n-1)//2,
                     "wall_ns_samples": samples, "wall_ns_median": {k: statistics.median(v) for k,v in samples.items()},
                     "tracemalloc_peak_bytes": peak, "summary_counts_match": True})
    return {"python": platform.python_version(), "platform": platform.platform(), "results": rows,
            "warmups": 2, "alternating_repetitions": 7, "memory_is_python_allocations_not_rss": True,
            "scope": "legacy_pair_details_vs_exact_summary_without_details", "whole_docking_speedup_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(benchmark(), indent=2) + "\n")
