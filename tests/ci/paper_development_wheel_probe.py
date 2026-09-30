"""Portable synthetic installed probe; preparation alone imports checkout fixtures."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def prepare(root):
    from tests.unit.test_installed_paper_development_comparison import _protocol
    root.mkdir(parents=True, exist_ok=False)
    for name, options in (("complete", {}), ("partial-preparation", {"missing": True}),
                          ("checkpoint", {"strained": True, "attempts": 4, "accepted": 3})):
        protocol = _protocol(root / (name + "-inputs"), **options)
        _write(root / (name + "-protocol.json"), protocol)


def execute(root, installed_root, require_fresh_environment):
    assert importlib.util.find_spec("tools") is None, "checkout must be absent"
    try:
        fixture_spec = importlib.util.find_spec("tests.unit")
    except ModuleNotFoundError:
        fixture_spec = None
    assert fixture_spec is None, "checkout fixtures must be absent"
    import betelgeuze_product
    from betelgeuze_product import installed_paper_development_comparison as paper
    from betelgeuze_product.cpu_refinement_v1_3 import workflow, minimization
    from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
    package = Path(betelgeuze_product.__file__).resolve()
    assert package.is_relative_to(installed_root.resolve())
    entry = importlib.metadata.distribution("betelgeuze-md-product").entry_points
    assert any(e.name == "betelgeuze-paper-development" and e.value ==
               "betelgeuze_product.installed_paper_development_comparison:main" for e in entry)
    config = Path(sys.prefix) / "pyvenv.cfg"
    fresh = (sys.prefix != sys.base_prefix and config.is_file()
             and "include-system-site-packages = false" in config.read_text().lower())
    if require_fresh_environment:
        assert fresh, "fresh isolated dependencies required"
    stages = []
    observed = {"force": 0, "score": 0}
    def counted(original, name):
        def call(*args, **kwargs):
            observed[name] += 1
            return original(*args, **kwargs)
        return call
    def invoke(name, action, protocol_name, *, run_name=None, extra=(), expected=0):
        protocol = root / (protocol_name + "-protocol.json")
        digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
        args = [action, "--protocol", str(protocol), "--expected-protocol-sha256", digest]
        if run_name is not None:
            args += ["--run-dir", str(root / run_name)]
        output = io.StringIO()
        with redirect_stdout(output):
            code = paper.main(args + list(extra))
        value = json.loads(output.getvalue())
        assert code == expected, value
        _write(root / (name + ".json"), value)
        stages.append({"name": name, "exit_code": code, "status": value["status"]})
        return value
    with ExitStack() as counted_stack:
        counted_stack.enter_context(patch.object(workflow.FixedReceptorEvaluator, "evaluate",
                                                counted(workflow.FixedReceptorEvaluator.evaluate, "force")))
        counted_stack.enter_context(patch.object(ExplicitGraphScorer, "score_terms",
                                                counted(ExplicitGraphScorer.score_terms, "score")))
        ready = invoke("preflight", "preflight", "complete")
        assert ready["requested_candidate_count"] == ready["prepared_candidate_count"] == 2
        assert observed == {"force": 0, "score": 0}
        completed = invoke("complete-run", "run", "complete", run_name="complete-run-dir")
        assert completed["denominator"] == {"requested": 2, "completed": 2}
        assert all(r["refinement_state"] == "no_refinement" for r in completed["rows"])
        partial = invoke("partial-preparation", "run", "partial-preparation", run_name="partial-preparation-run")
        assert partial["denominator"] == {"requested": 2, "completed": 1, "preparation_blocked": 1}
        paused = invoke("checkpoint", "run", "checkpoint", run_name="checkpoint-run",
                        extra=("--pause-after-objective-attempts", "1"), expected=2)
        assert paused["denominator"] == {"requested": 2, "checkpointed": 2}
        resumed = invoke("checkpoint-resume", "resume", "checkpoint", run_name="checkpoint-run")
        assert resumed["denominator"] == {"requested": 2, "completed": 2}
        assert all(r["refinement_state"] == "rejected" and r["paired_decision"]["variant"] == "baseline"
                   for r in resumed["rows"])
        assert all(r["registered_summary"]["workflow_invocation_work"]["score_work"]["new_score_calls"] == 1
                   for r in resumed["rows"])
        before = deepcopy(observed)
        def forbidden(*args, **kwargs):
            raise AssertionError("exact reuse or unknown interruption reissued molecular work")
        with ExitStack() as stack:
            for target, name in ((workflow, "evaluate"), (minimization, "minimize"),
                                 (workflow.FixedReceptorEvaluator, "evaluate"), (ExplicitGraphScorer, "score_terms")):
                stack.enter_context(patch.object(target, name, forbidden))
            snapshot = {p.relative_to(root / "complete-run-dir"): p.read_bytes()
                        for p in (root / "complete-run-dir").rglob("*") if p.is_file()}
            invoke("verify", "verify", "complete", run_name="complete-run-dir")
            assert invoke("reuse", "resume", "complete", run_name="complete-run-dir") == completed
            assert snapshot == {p.relative_to(root / "complete-run-dir"): p.read_bytes()
                                for p in (root / "complete-run-dir").rglob("*") if p.is_file()}
            unknown = root / "unknown-run"
            shutil.copytree(root / "complete-run-dir", unknown)
            (unknown / "result.json").unlink()
            child = paper._candidate_directory(unknown, completed["rows"][0]["candidate_id"])
            (child / "invocation-000000.end.json").unlink()
            unknown_result = invoke("unknown-resume", "resume", "complete", run_name="unknown-run", expected=2)
            assert unknown_result["denominator"] == {"requested": 2, "interrupted_unknown": 1, "completed": 1}
            assert unknown_result["rows"][0]["work"]["all_candidate_molecular_work_recorded"] is False
        assert observed == before
    assert not any(n == "tools" or n.startswith("tools.") or n.startswith("tests.unit") for n in sys.modules)
    receipt = {"schema_version": "installed_paper_development_wheel_probe_v1", "status": "passed",
               "package_path": str(package), "fresh_dependency_environment": fresh,
               "synthetic_inputs_only": True, "stages": stages, "observed_molecular_calls": observed,
               "exact_reuse_new_force_or_score_calls": 0, "unknown_resume_new_force_or_score_calls": 0,
               "independent_measurement_denominator": None, "boundary": deepcopy(paper.BOUNDARY)}
    _write(root / "installed-probe.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


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
            parser.error("--installed-root required")
        execute(args.root.resolve(), args.installed_root, args.require_fresh_environment)


if __name__ == "__main__":
    main()
