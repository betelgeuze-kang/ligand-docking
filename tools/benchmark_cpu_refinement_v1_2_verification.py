"""Reproduce byte verification costs; not an overall docking speedup benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time

from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.provenance import environment
from betelgeuze_product.cpu_refinement_v1_2.work import verify_admitted_bytes


def benchmark(repetitions=31) -> dict:
    results = []
    with tempfile.TemporaryDirectory() as directory:
        for count in (128, 32768):
            raw = json.dumps({"synthetic_values": [i * .01 for i in range(count)]}, separators=(",", ":")).encode()
            path = Path(directory) / f"synthetic-{count}.json"
            path.write_bytes(raw)
            reference = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
            _bound(reference)  # Admission and complete parsing must happen first.
            methods = {"parse_again": lambda: _bound(reference),
                       "verify_admitted_bytes": lambda: verify_admitted_bytes(reference)}
            for _ in range(5):
                for operation in methods.values():
                    operation()
            samples = {name: {"wall_ns": [], "cpu_ns": []} for name in methods}
            for index in range(repetitions):
                order = list(methods) if index % 2 == 0 else list(reversed(methods))
                for name in order:
                    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                    methods[name]()
                    samples[name]["cpu_ns"].append(time.process_time_ns() - cpu)
                    samples[name]["wall_ns"].append(time.perf_counter_ns() - wall)
            summaries = {name: {metric + "_median": statistics.median(values)
                                for metric, values in row.items()} for name, row in samples.items()}
            results.append({"byte_length": len(raw), "source_sha256": reference["sha256"],
                            "samples": samples, "summary": summaries})
    return {"schema_id": "admitted_input_verification_benchmark/1.2.0", "environment": environment(),
            "repetitions": repetitions, "warmups_per_method": 5, "alternating_order": True,
            "scope": "post_admission_full_byte_read_hash_vs_read_hash_json_reparse_only",
            "synthetic_inputs": True, "results": results, "overall_docking_speedup_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(benchmark(), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
