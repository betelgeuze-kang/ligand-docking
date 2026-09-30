"""Source-pinned, separate-process audit of authenticated saved SRO endpoints.

This runner imports no native product and never opens a pose reference. The
driver's semantic verifier selects checkpoint initial/current before independent
OpenMM arithmetic; the resulting receipt is bounded numerical evidence only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from types import ModuleType


DEPENDENCY_SITE = "/home/betelgeuze/.local/lib/python3.10/site-packages"
CASE_IDS = [f"perturbed_{i:02d}" for i in range(1, 5)]
SPEC_SCHEMA = "sro_endpoint_oracle_input_spec/1"
PROTOCOL_SHA = "5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23"
MANIFEST_SHA = "4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3"


class RunnerError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise RunnerError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def finite(value):
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_json")
    elif type(value) is dict:
        for item in value.values():
            finite(item)
    elif type(value) is list:
        for item in value:
            finite(item)
    else:
        require(value is None or type(value) in (str, int, bool), "unsupported_json_type")
    return value


def loads(raw):
    return finite(json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (
        _ for _ in ()).throw(RunnerError("nonfinite_json"))))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode()


def file_ref(path):
    path = Path(path)
    require(path.is_absolute() and str(path.resolve(strict=True)) == str(path)
            and not path.is_symlink(), "canonical_path_required")
    allowed_path(path)
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def allowed_path(path):
    require(not {"evaluation_only", "stability_control"}.intersection(path.parts)
            and "provenance" not in path.name and "chemical-graph" not in path.name
            and path.name != "ligand-canonical.json", "reference_or_provenance_body_forbidden")


def bound(ref, *, parse=True):
    require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "exact_file_pin_required")
    require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in ref["sha256"]), "invalid_source_digest")
    require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 32 * 1024 * 1024, "bounded_file_required")
    path = Path(ref["path"])
    require(path.is_absolute() and str(path.resolve(strict=True)) == ref["path"]
            and not path.is_symlink(), "canonical_path_required")
    allowed_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == ref["bytes"], "file_size_changed")
        raw = stream.read(ref["bytes"] + 1)
        after = os.fstat(stream.fileno())
        current = path.stat()
    def identity(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    require(identity(before) == identity(after) == identity(current), "file_changed_during_read")
    require(len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "file_hash_mismatch")
    return loads(raw) if parse else raw


def load_source(ref, name):
    raw = bound(ref, parse=False)
    module = ModuleType(name)
    module.__file__ = ref["path"]
    sys.modules[name] = module
    try:
        exec(compile(raw, ref["path"], "exec"), module.__dict__)
        bound(ref, parse=False)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def publish(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return file_ref(path)


def native_snapshot(plan, case, child_ref, driver, *, plan_ref=None):
    """Authenticate saved endpoint selection before any oracle artifact reads."""
    root = Path(child_ref["path"]).parent
    require(Path(child_ref["path"]).name == "child-result.json", "child_result_filename")
    child = bound(child_ref)
    require(child["schema_id"] == "sro_native_child_result/1" and child["case_id"] == case["case_id"]
            and child["status"] == "native_completed", "successful_native_child_required")
    run = root / "run"
    require(child["run_directory"] == str(run), "native_run_directory_changed")
    require(child["native_artifact_refs"] == driver.inventory(run), "native_inventory_changed")
    indexed = {ref["path"]: ref for ref in child["native_artifact_refs"]}
    require(len(indexed) == len(child["native_artifact_refs"]), "duplicate_native_artifact")
    for path in indexed:
        require(Path(path).is_relative_to(run), "native_artifact_escape")
    result = bound(indexed[str(run / "result.json")])
    require(sha(canonical({k: v for k, v in result.items() if k != "result_sha256"}))
            == result["result_sha256"], "native_result_seal")
    require(result["execution_complete"] is True and result["attempt"]["status"] == "success",
            "native_execution_incomplete")
    driver.completed_observations(result)
    expected = bound(case["expected_binding_ref"])
    require(result["binding"] == expected["input_binding"], "native_result_binding_changed")
    lifecycle_names = {"native-start.json", "preflight.json", "native-end.json", "post-exit-source-check.json"}
    lifecycle_refs = child["lifecycle_refs"]
    require(type(lifecycle_refs) is dict and set(lifecycle_refs) == lifecycle_names
            and all(ref["path"] == str(root / name) for name, ref in lifecycle_refs.items()),
            "native_lifecycle_pin_set")
    lifecycle = {ref["path"]: ref for ref in lifecycle_refs.values()}
    start = bound(lifecycle[str(root / "native-start.json")])
    require(start["case_id"] == case["case_id"], "native_start_case_changed")
    if plan_ref is not None:
        require(start["plan_ref"] == plan_ref, "native_start_plan_changed")
        driver.review_execution(plan_ref, start["execution_review_ref"])
        driver.supervisor_contract(start["supervisor_ref"], plan_ref, start["execution_review_ref"],
                                   case["case_id"], root)
    require(start["preflight_ref"] == lifecycle[str(root / "preflight.json")], "preflight_path_changed")
    preflight = bound(start["preflight_ref"])
    post = bound(lifecycle[str(root / "post-exit-source-check.json")])
    for observed in (preflight, post):
        require(observed["input_binding"] == expected["input_binding"]
                and observed["executed_wheel"] == plan["wheel_ref"]
                and observed["loaded_module_origins_verified_against_wheel"] is True,
                "native_source_or_input_binding_changed")
    end = bound(lifecycle[str(root / "native-end.json")])
    require(end["case_id"] == case["case_id"] and end["error_type"] is None
            and end["post_exit_error_type"] is None and not end["pending_dispatches"]
            and end["dispatch_starts"]["score"] == 2, "native_failure_or_pending_work")
    verification_ref = child["verification_ref"]
    require(verification_ref["path"] == str(root / "semantic-verification.json"), "verification_path_changed")
    verification = bound(verification_ref)
    require(verification["structural_verification_passed"] is True
            and verification["result_sha256"] == result["result_sha256"]
            and verification["scoring_reexecuted"] is False
            and verification["numerical_evaluation_reexecuted"] is False,
            "native_semantic_verification_required")
    endpoint_ref = child["endpoint_states_ref"]
    require(endpoint_ref["path"] == str(root / "endpoint-states.json"), "endpoint_path_changed")
    endpoints = bound(endpoint_ref)
    json_refs = [ref for ref in child["native_artifact_refs"]
                 if ref["bytes"] > 0 and Path(ref["path"]).suffix in (".json", ".jsonl")]
    require(endpoints == driver.endpoint_document(case["case_id"], result, json_refs),
            "endpoint_selection_changed")
    # Source/byte identity is necessary, but the separate semantic verifier above
    # supplies the reconstruction proof for the retained native result.
    return child, start["preflight_ref"], endpoint_ref


def validate_spec(spec, phase, runner_ref):
    require(type(spec) is dict and set(spec) == {"schema_id", "oracle_source_ref", "ligand_xml_ref",
            "receptor_xml_ref", "original_parameter_refs", "dependency_site"}, "oracle_spec_fields")
    require(spec["schema_id"] == SPEC_SCHEMA and spec["dependency_site"] == DEPENDENCY_SITE,
            "declared_oracle_environment_required")
    source_refs = phase["source_refs"]
    require(runner_ref in source_refs and spec["oracle_source_ref"] in source_refs,
            "oracle_sources_not_review_bound")
    return spec


def source_layout(plan, spec_ref):
    """Gate reviewed source roles before opening or executing supplied refs."""
    source = Path(__file__).resolve(strict=True).parent
    require(plan["schema_id"] == "sro_native_execution_plan/1"
            and plan["protocol_sha256"] == PROTOCOL_SHA and plan["manifest_sha256"] == MANIFEST_SHA,
            "frozen_plan_role_required")
    require(plan["driver_source_ref"]["path"] == str(source / "runtime_execution.py"),
            "reviewed_driver_role_path_required")
    require(spec_ref["path"] == str(source.parent / "oracle-input-spec.json"), "oracle_spec_role_path_required")
    expected = {str(source / name) for name in ("endpoint_oracle_runner.py", "campaign_supervisor.py",
                                                "sro_recovery_endpoint_numerics_v1.py")}
    expected.add(spec_ref["path"])
    refs = plan["oracle_phase"]["source_refs"]
    require(type(refs) is list and len(refs) == len(expected)
            and {ref["path"] for ref in refs} == expected, "reviewed_oracle_source_roles_required")
    return source


def run(plan_ref, case_id, child_ref, spec_ref, output):
    require(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1, "isolated_no_bytecode_required")
    require(case_id in CASE_IDS, "undeclared_case")
    require(not any(name.startswith(("betelgeuze_engine_v2", "betelgeuze_product", "openmm"))
                    for name in sys.modules), "preloaded_molecular_module")
    plan = bound(plan_ref)
    phase = plan["oracle_phase"]
    require(phase is not None and spec_ref in phase["source_refs"], "review_bound_oracle_spec_required")
    source = source_layout(plan, spec_ref)
    require(str(Path(sys.executable).absolute()) == phase["python_executable"]
            and file_ref(Path(sys.executable).resolve(strict=True)) == phase["python_binary_ref"],
            "oracle_python_changed")
    runner_ref = file_ref(Path(__file__).resolve(strict=True))
    spec = validate_spec(bound(spec_ref), phase, runner_ref)
    require(spec["oracle_source_ref"]["path"] == str(source / "sro_recovery_endpoint_numerics_v1.py"),
            "reviewed_oracle_module_role_path_required")
    for ref in phase["source_refs"]:
        bound(ref, parse=False)
    driver = load_source(plan["driver_source_ref"], "sro_oracle_validated_driver")
    driver.validate_plan(plan)
    case = next(case for case in plan["cases"] if case["case_id"] == case_id)
    child, binding_ref, endpoint_ref = native_snapshot(plan, case, child_ref, driver, plan_ref=plan_ref)
    derivation = bound(plan["derivation_ref"])
    require(spec["original_parameter_refs"] == {name: derivation["original_input_refs"][name]
            for name in ("parameters", "extensions", "cross_parameters")}, "original_parameter_source_changed")
    output = Path(output).absolute()
    output.mkdir(mode=0o700)
    started = time.monotonic_ns()
    receipt_ref = None
    failure = None
    try:
        sys.path.insert(0, spec["dependency_site"])
        oracle = load_source(spec["oracle_source_ref"], "sro_independent_endpoint_oracle")
        receipt = oracle.audit_case(case_id=case_id, request_ref=case["request_file_ref"],
            binding_ref=binding_ref, endpoint_states_ref=endpoint_ref,
            ligand_xml_ref=spec["ligand_xml_ref"], receptor_xml_ref=spec["receptor_xml_ref"],
            original_parameter_refs=spec["original_parameter_refs"], wheel_ref=plan["wheel_ref"],
            protocol_sha256=plan["protocol_sha256"], manifest_sha256=plan["manifest_sha256"])
        receipt_ref = publish(output / "numerical-receipt.json", receipt)
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    try:
        for ref in (plan_ref, child_ref, spec_ref, *phase["source_refs"]):
            bound(ref, parse=False)
        native_snapshot(plan, case, child_ref, driver, plan_ref=plan_ref)
        driver.validate_plan(plan)
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    lifecycle = {"schema_id": "sro_endpoint_oracle_lifecycle/1", "case_id": case_id,
        "completed_at": datetime.now(timezone.utc).isoformat(), "plan_ref": plan_ref,
        "native_child_ref": child_ref, "oracle_spec_ref": spec_ref, "runner_source_ref": runner_ref,
        "numerical_receipt_ref": receipt_ref, "failure": failure,
        "inclusive_wall_ns": time.monotonic_ns() - started, "durations_are_inclusive_do_not_sum": True,
        "new_native_force_calls": 0, "new_native_score_calls": 0, "scientifically_validated": False}
    publish(output / "lifecycle.json", lifecycle)
    require(failure is None, "oracle_runner_failed")
    return receipt_ref


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--case", required=True, choices=CASE_IDS)
    parser.add_argument("--native-result", required=True, type=Path)
    parser.add_argument("--native-result-sha256", required=True)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    require(args.native_result.name == "child-result.json", "child_result_filename")
    source = Path(__file__).resolve(strict=True).parent
    require(args.plan.absolute() == source.parent / "plan.json", "plan_role_path_required")
    require(args.spec.absolute() == source.parent / "oracle-input-spec.json", "oracle_spec_role_path_required")
    require(args.native_result.absolute().is_relative_to(source.parent) and args.case in args.native_result.parts,
            "native_child_role_path_required")
    plan_ref, child_ref = file_ref(args.plan.absolute()), file_ref(args.native_result.absolute())
    require(plan_ref["sha256"] == args.plan_sha256 and child_ref["sha256"] == args.native_result_sha256,
            "supervisor_file_pin_changed")
    run(plan_ref, args.case, child_ref, file_ref(args.spec.absolute()), args.output)


if __name__ == "__main__":
    main()
