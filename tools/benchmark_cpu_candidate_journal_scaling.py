"""Measure journal storage overhead on synthetic records, without molecular work."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from betelgeuze_product.cpu_refinement_v1_2 import candidate_journal as module
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest


def benchmark(output, sizes=(8, 32, 64), repetitions=3):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    if (
        repetitions < 1
        or not sizes
        or any(type(n) is not int or not 1 <= n <= 256 for n in sizes)
    ):
        raise ValueError("bounded positive sizes and repetitions required")
    source_sha = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
    plan = dict(
        sizes=list(sizes),
        repetitions=repetitions,
        journal_source_sha256=source_sha,
        synthetic=True,
        molecular_compute=False,
        instrumentation="read calls, bytes, validation calls",
        timing="in-process wall and CPU; includes instrumentation; uncontrolled filesystem cache",
    )
    (output / "plan.json").write_text(json.dumps(plan, indent=2))
    original_read = module._read
    observations = []
    counts = {}

    def read(path):
        raw = original_read(path)
        counts["read_calls"] += 1
        counts["read_bytes"] += len(raw)
        return raw

    def validate(key, row):
        counts["validation_calls"] += 1
        if row != {"key": key, "energy": -2.5}:
            raise AssertionError("invalid synthetic record")

    module._read = read
    try:
        for n in sizes:
            binding = dict(
                schema_id="cpu_comparison_candidate_journal/1.0.0",
                request_sha256=digest("request"),
                implementation_sha256=digest("benchmark"),
                environment_sha256=digest("local"),
                candidate_keys=[digest(i) for i in range(n)],
            )
            for repetition in range(repetitions):
                path = output / f"n{n}-r{repetition}"
                for resume in (False, True):
                    counts = dict(
                        read_calls=0, read_bytes=0, validation_calls=0, compute_calls=0
                    )
                    start = time.perf_counter_ns()
                    cpu = time.process_time_ns()
                    with module.open_journal(
                        path, binding, validate_record=validate, resume=resume
                    ) as journal:
                        for index, key in enumerate(binding["candidate_keys"]):

                            def compute(key=key):
                                counts["compute_calls"] += 1
                                if resume:
                                    raise AssertionError("replay recomputed")
                                return {"key": key, "energy": -2.5}

                            assert journal.evaluate(index, compute) == {
                                "key": key,
                                "energy": -2.5,
                            }
                        assert journal.unknown_attempts == 0
                    sample = dict(
                        n=n,
                        repetition=repetition,
                        resume=resume,
                        wall_seconds=(time.perf_counter_ns() - start) / 1e9,
                        cpu_seconds=(time.process_time_ns() - cpu) / 1e9,
                        **counts,
                    )
                    assert counts["compute_calls"] == (0 if resume else n)
                    observations.append(sample)
                    (output / "observations.json").write_text(
                        json.dumps(observations, indent=2)
                    )
    finally:
        module._read = original_read
    return observations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 32, 64])
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.output, args.sizes, args.repetitions), indent=2))
