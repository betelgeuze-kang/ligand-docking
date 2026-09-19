"""Measure installed CLI process costs on synthetic prepared fixtures (Linux)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import time

from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture
from betelgeuze_product.cpu_refinement_v1_2.provenance import source_manifest


def benchmark(python, output, repetitions=3):
    if repetitions < 3:
        raise ValueError("at least three repetitions required")
    output = Path(output).absolute()
    source = Path(__file__).resolve().parents[1]
    if output.is_relative_to(source):
        raise ValueError("output must be outside checkout")
    output.mkdir(parents=True, exist_ok=False)
    python = str(Path(python).absolute())
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        HIP_VISIBLE_DEVICES="",
        ROCR_VISIBLE_DEVICES="",
    )
    commands = []
    expected = source_manifest()
    (output / "source-manifest.json").write_text(json.dumps(expected))
    plan = dict(
        repetitions=repetitions,
        stop_after=2,
        modes=["same-candidates", "equal-budget"],
        order="cold first on even repetitions, pause/resume first on odd repetitions",
        timing="subprocess launch through exit; wall and child user+system CPU seconds",
        excluded="fixture preparation, dependency installation, parent validation; synthetic inputs only",
        threads=1,
        cache_policy="no cache flushing; process starts are fresh, OS caches uncontrolled",
    )
    (output / "plan.json").write_text(json.dumps(plan, indent=2))

    def run(args):
        command = [python, "-I", *args]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter_ns()
        result = subprocess.run(
            command, cwd=output, env=env, capture_output=True, text=True, timeout=180
        )
        wall = (time.perf_counter_ns() - start) / 1e9
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        sample = dict(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            wall_seconds=wall,
            cpu_seconds=after.ru_utime
            + after.ru_stime
            - before.ru_utime
            - before.ru_stime,
        )
        commands.append(sample)
        (output / "commands.json").write_text(json.dumps(commands, indent=2))
        if result.returncode:
            raise RuntimeError("CLI failed; see commands.json")
        return json.loads(result.stdout), sample

    probe, _ = run(
        [
            "-c",
            "import sys,json,hashlib; from pathlib import Path; "
            "import betelgeuze_product,betelgeuze_engine_v2; "
            "root=Path(betelgeuze_product.__file__).resolve().parent.parent; "
            "assert root.is_relative_to(Path(sys.prefix)); "
            "assert Path(betelgeuze_engine_v2.__file__).resolve().is_relative_to(root); "
            "expected=json.loads(Path('source-manifest.json').read_text()); "
            "assert {k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in expected}==expected; "
            "print(json.dumps({'python':sys.version,'root':str(root),'source_hashes':len(expected)}))",
        ]
    )
    observations = []
    numerical_keys = (
        "rows",
        "attempts",
        "paired_decisions",
        "final_selection",
        "raw_per_arm_selection",
        "per_arm_selection",
    )
    for mode in plan["modes"]:
        for rep in range(repetitions):
            case = output / f"{mode}-{rep}"
            case.mkdir()
            inputs = case / "inputs"
            inputs.mkdir()
            request = request_fixture(inputs)
            if mode == "equal-budget":
                request["solver"]["minimization"]["max_backtracks"] = 0
                request["budget"].update(candidate_count=12, max_refinement_steps=2)
                request["comparison"].update(
                    mode="equal_work_budget", work_units_per_arm=8
                )
            request_file = case / "request.json"
            request_file.write_text(json.dumps(request))
            times = {}
            for route in ["cold", "resumed"] if rep % 2 == 0 else ["resumed", "cold"]:
                prefix = [
                    "-m",
                    "betelgeuze_product.cpu_refinement_v1_2",
                    "run-resumable",
                    str(request_file),
                    "--output",
                    str(case / route),
                ]
                stages = []
                if route == "resumed":
                    paused, sample = run([*prefix, "--stop-after", "2"])
                    assert paused["execution_complete"] is False
                    assert paused["committed_candidates"] == 2
                    stages.append(sample)
                completed, sample = run(
                    prefix + (["--resume"] if route == "resumed" else [])
                )
                assert completed["execution_complete"] is True
                stages.append(sample)
                times[route] = {
                    k: sum(s[k] for s in stages)
                    for k in ("wall_seconds", "cpu_seconds")
                }
            reports = {
                r: json.loads((case / r / "report.json").read_text()) for r in times
            }
            for report in reports.values():
                assert report["implementation_sources"] == expected
            cold, resumed = (reports[r]["summary"] for r in ("cold", "resumed"))
            for key in numerical_keys:
                assert cold[key] == resumed[key], (mode, rep, key)
            for arm in ("baseline", "refined"):
                for kind in ("force", "score"):
                    key = f"new_{kind}_calls"
                    assert cold["costs"][arm][key] == (
                        resumed["costs"][arm][key]
                        + resumed["costs"][arm][f"historical_{kind}_calls"]
                    )
            assert resumed["costs"]["baseline"]["reused_candidates"] == 2
            inputs.rename(case / "inputs-moved")
            for route in times:
                report_file = case / route / "report.json"
                saved = report_file.read_bytes()
                verified, _ = run(
                    [
                        "-m",
                        "betelgeuze_product.cpu_refinement_v1_2",
                        "verify-resumable",
                        str(case / route),
                    ]
                )
                assert verified["structural_verification_passed"] is True
                assert saved == report_file.read_bytes()
            observations.append(
                dict(
                    mode=mode,
                    repetition=rep,
                    times=times,
                    numerical_identity=True,
                    candidate_call_totals_equal=True,
                    costs={r: reports[r]["summary"]["costs"] for r in reports},
                    reports_sha256={
                        r: hashlib.sha256(
                            (case / r / "report.json").read_bytes()
                        ).hexdigest()
                        for r in reports
                    },
                )
            )
    medians = {}
    for mode in plan["modes"]:
        rows = [o for o in observations if o["mode"] == mode]
        medians[mode] = {
            r: {
                k: statistics.median(o["times"][r][k] for o in rows)
                for k in ("wall_seconds", "cpu_seconds")
            }
            for r in ("cold", "resumed")
        }
        medians[mode]["paired_wall_ratio_median"] = statistics.median(
            o["times"]["resumed"]["wall_seconds"] / o["times"]["cold"]["wall_seconds"]
            for o in rows
        )
    result = dict(
        plan=plan,
        probe=probe,
        observations=observations,
        medians=medians,
        scientifically_validated=False,
        whole_docking_speedup_claim=False,
    )
    (output / "benchmark.json").write_text(json.dumps(result, indent=2))
    return medians


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.python, args.output, args.repetitions), indent=2))
