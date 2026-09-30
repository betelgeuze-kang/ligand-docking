"""Exercise the registered Cartesian v4 contract from a wheel outside its checkout.

Only preparation imports synthetic checkout fixtures. The installed probe uses
the version-gated public CLI, retained inputs and standard-library checks.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def prepare(root):
    from tests.unit.test_installed_native_v4_cartesian_comparison import _protocol

    root.mkdir(parents=True, exist_ok=False)
    protocol = _protocol(root / "synthetic-input")
    _write(root / "draft.json", protocol)
    blocked = deepcopy(protocol)
    blocked["max_engine_calls_per_arm"] = 1
    _write(root / "blocked-cap.json", blocked)
    swapped = deepcopy(protocol)
    first, second = swapped["requests"]
    swapped["requests"][first], swapped["requests"][second] = (
        swapped["requests"][second], swapped["requests"][first])
    _write(root / "swapped-candidates.json", swapped)


def execute(root, installed_root, require_fresh_environment):
    assert importlib.util.find_spec("tools") is None, "checkout tools must not be importable"
    import betelgeuze_product
    from betelgeuze_product import installed_native_v4_replay_cli as cli
    from betelgeuze_product import installed_synthetic_comparison as comparison
    from betelgeuze_product import registered_cartesian_policy_adapter as adapter
    from betelgeuze_product.cpu_refinement_v1_3 import minimization, workflow
    from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
    from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEnvironment

    package = Path(betelgeuze_product.__file__).resolve()
    assert package.is_relative_to(installed_root.resolve())
    fresh = False
    config = Path(sys.prefix) / "pyvenv.cfg"
    if sys.prefix != sys.base_prefix and config.is_file():
        fresh = "include-system-site-packages = false" in config.read_text().lower()
    if require_fresh_environment:
        assert fresh, "CI requires a fresh venv without system site packages"
    cli.require_replay_runtime()
    results = {"schema_version": "native_v4_registered_cartesian_wheel_probe_v4",
               "package_path": str(package), "python": sys.version,
               "fresh_dependency_environment": fresh,
               "synthetic_inputs_only": True, "evaluation_labels_read": 0,
               "scientifically_validated": False, "stages": []}
    started = time.perf_counter()

    def invoke(name, args, expected=0):
        output = io.StringIO()
        tick = time.perf_counter()
        with redirect_stdout(output):
            code = cli.comparison_main(args)
        result = json.loads(output.getvalue())
        _write(root / (name + ".json"), result)
        assert code == expected, result
        results["stages"].append({"name": name, "exit_code": code,
                                  "wall_seconds": time.perf_counter() - tick})
        return result

    ready = invoke("preflight", ["preflight-v4", "--protocol", str(root / "draft.json"),
                                  "--output-protocol", str(root / "protocol.json")])
    assert ready["status"] == "ready" and ready["candidate_count"] == 2
    protocol = root / "protocol.json"
    run_dir = root / "run"
    run = invoke("run-receipt", ["run", "--protocol", str(protocol), "--run-dir", str(run_dir)])
    result_bytes = (run_dir / "comparison.json").read_bytes()
    result = json.loads(result_bytes)
    assert result["schema_version"] == comparison.NATIVE_RESULT_V4
    assert result["evaluation_labels_read"] == 0 and not result["scientifically_validated"]
    assert len(result["pool"]) == 2
    force_calls = score_calls = 0
    for name, arm in result["arms"].items():
        assert arm["completion"]["status"] == "complete"
        assert arm["denominator"] == {"requested": 2, "evaluated": 2}
        assert arm["registered_work"]["all_candidate_molecular_work_recorded"]
        assert arm["registered_work"]["candidate_calls_without_returned_report"] == 0
        counters = arm["registered_work"]["recorded_call_counters"]
        force_calls += counters["actual_force_calls"]
        score_calls += counters["score_evaluation_calls"]
        assert counters["failed_optimizer_force_calls"] == counters["failed_restart_force_calls"] == 0
        assert counters["unknown_pending_attempts"] == 0
        assert arm["cartesian_partial_work"] == {}
        if name != "similarity":
            assert arm["score_quantity"] == adapter.SCORE_QUANTITY
            assert arm["worker_complete"]["engine_calls"] == 2
            for row in arm["rows"]:
                summary = row["registered_summary"]
                assert summary["refinement_failures"] == 0
                assert summary["refinement_converged"] == 1
                assert summary["original_selected_count"] == 1
                assert summary["refined_selected_count"] == 0
    assert force_calls == 6 and score_calls == 12

    def forbidden(*args, **kwargs):
        raise AssertionError("verified reuse started a worker, score or force evaluation")

    with ExitStack() as stack:
        for target, attribute in ((comparison.subprocess, "Popen"), (adapter, "evaluate"),
                                  (workflow, "evaluate"), (minimization, "minimize"),
                                  (workflow.FixedReceptorEvaluator, "evaluate"),
                                  (ExtendedEvaluator, "evaluate"),
                                  (FixedReceptorEnvironment, "evaluate_cross"),
                                  (ExplicitGraphScorer, "score_terms")):
            stack.enter_context(patch.object(target, attribute, forbidden))
        verified = invoke("verification", ["verify-run", "--protocol", str(protocol),
                                           "--run-dir", str(run_dir)])
        resumed = invoke("resume", ["resume", "--protocol", str(protocol),
                                    "--run-dir", str(run_dir)])
        assert verified["status"] == "verified" and resumed == run
        assert (run_dir / "comparison.json").read_bytes() == result_bytes
        assert verified["new_force_calls"] == verified["new_score_calls"] == 0
        for filename in ("blocked-cap", "swapped-candidates"):
            blocked = invoke(filename + "-preflight", [
                "preflight-v4", "--protocol", str(root / (filename + ".json"))], expected=2)
            assert blocked["status"] == "blocked" and blocked["candidate_count"] == 2
            rejected = root / (filename + "-must-not-run")
            try:
                cli.comparison_main(["run", "--protocol", str(root / (filename + ".json")),
                                     "--run-dir", str(rejected)])
            except ValueError as exc:
                _write(root / (filename + "-direct-rejection.json"), {"reason": str(exc)})
            else:
                raise AssertionError("direct execution bypassed admission")
            assert not rejected.exists()
    assert not any(name == "tools" or name.startswith("tools.") for name in sys.modules)
    results.update(status="passed", force_evaluation_calls=force_calls,
                   score_evaluation_calls=score_calls, failed_force_evaluation_calls=0,
                   synthetic_initial_equilibrium=True, refinement_steps_observed=0,
                   completed_resume_new_worker_calls=0,
                   completed_resume_new_score_or_force_calls=0,
                   scorer_setup_reference_arithmetic_executed=True,
                   result_sha256=hashlib.sha256(result_bytes).hexdigest(),
                   enclosing_wall_seconds=time.perf_counter() - started)
    _write(root / "installed-probe.json", results)
    print(json.dumps(results, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--require-fresh-environment", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.root.resolve())
    else:
        if args.installed_root is None:
            parser.error("execute requires --installed-root")
        execute(args.root.resolve(), args.installed_root, args.require_fresh_environment)


if __name__ == "__main__":
    main()
