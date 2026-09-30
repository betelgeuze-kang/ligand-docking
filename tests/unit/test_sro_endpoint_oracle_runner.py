"""Portable boundary tests; these fixtures perform no molecular calculations."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_sro_pose_recovery/endpoint_oracle_runner.py"
spec = importlib.util.spec_from_file_location("sro_endpoint_runner_test", SOURCE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return runner.file_ref(path)


def inventory(root):
    return [runner.file_ref(path) for path in sorted(root.rglob("*")) if path.is_file()]


def endpoints(case_id, result, refs):
    state = result["numerical_result"]["checkpoint"]["state"]
    return {"schema_id": "sro_saved_numerical_endpoints/1", "case_id": case_id,
            "request_sha256": result["binding"]["request_sha256"],
            "binding_receipt_sha256": result["binding"]["receipt_sha256"], "native_artifact_refs": refs,
            "states": [{"label": label, **deepcopy(state[key])}
                       for label, key in (("initial", "initial"), ("last_accepted", "current"))]}


@pytest.fixture
def native(tmp_path):
    root = tmp_path / "native"
    run = root / "run"
    case_id = "perturbed_01"
    binding = {"request_sha256": "a" * 64, "receipt_sha256": "b" * 64}
    wheel = {"path": "/declared/wheel.whl", "sha256": "c" * 64, "bytes": 1}
    outer = {"input_binding": binding, "executed_wheel": wheel,
             "loaded_module_origins_verified_against_wheel": True}
    expected_ref = save(tmp_path / "expected.json", outer)
    observed = {"coordinates": [[float(i).hex(), "0x0.0p+0", "0x0.0p+0"] for i in range(26)],
                "forces": [["0x0.0p+0"] * 3 for _ in range(26)], "energy": "0x0.0p+0",
                "components": {key: "0x0.0p+0" for key in ("ligand_internal", "cross_lennard_jones",
                                                            "cross_screened_coulomb", "total")}}
    result = {"execution_complete": True, "attempt": {"status": "success"}, "binding": binding,
              "numerical_result": {"checkpoint": {"state": {"initial": observed, "current": observed}}}}
    result["result_sha256"] = hashlib.sha256(runner.canonical(result)).hexdigest()
    save(run / "result.json", result)
    refs = inventory(run)
    preflight = save(root / "preflight.json", outer)
    save(root / "post-exit-source-check.json", outer)
    save(root / "native-start.json", {"case_id": case_id, "preflight_ref": preflight})
    save(root / "native-end.json", {"case_id": case_id, "error_type": None, "post_exit_error_type": None,
                                   "pending_dispatches": [], "dispatch_starts": {"score": 2}})
    verification = save(root / "semantic-verification.json", {"structural_verification_passed": True,
        "result_sha256": result["result_sha256"], "scoring_reexecuted": False,
        "numerical_evaluation_reexecuted": False})
    endpoint = save(root / "endpoint-states.json", endpoints(case_id, result, refs))
    child = {"schema_id": "sro_native_child_result/1", "case_id": case_id, "status": "native_completed",
             "run_directory": str(run), "native_artifact_refs": refs, "verification_ref": verification,
             "endpoint_states_ref": endpoint, "lifecycle_refs": {name: runner.file_ref(root / name) for name in (
                "native-start.json", "preflight.json", "native-end.json", "post-exit-source-check.json")}}
    child_ref = save(root / "child-result.json", child)
    return {"root": root, "result": result, "child": child, "child_ref": child_ref,
            "plan": {"wheel_ref": wheel}, "case": {"case_id": case_id, "expected_binding_ref": expected_ref},
            "driver": SimpleNamespace(inventory=inventory, endpoint_document=endpoints,
                                      completed_observations=lambda result: result)}


def check(native):
    return runner.native_snapshot(native["plan"], native["case"], native["child_ref"], native["driver"])


def rewrite_child(native):
    native["child_ref"] = save(native["root"] / "child-result.json", native["child"])


def reseal_lifecycle(native):
    native["child"]["lifecycle_refs"] = {name: runner.file_ref(Path(ref["path"]))
        for name, ref in native["child"]["lifecycle_refs"].items()}
    rewrite_child(native)


def test_authenticates_saved_endpoint_selection_without_calculation(native):
    child, binding, endpoint = check(native)
    assert child["status"] == "native_completed"
    assert binding["path"].endswith("/preflight.json")
    assert endpoint["path"].endswith("/endpoint-states.json")


def test_resealed_arbitrary_last_state_is_rejected(native):
    path = Path(native["child"]["endpoint_states_ref"]["path"])
    document = json.loads(path.read_bytes())
    document["states"][1]["coordinates"][0][0] = float(999).hex()
    native["child"]["endpoint_states_ref"] = save(path, document)
    rewrite_child(native)
    with pytest.raises(runner.RunnerError, match="endpoint_selection_changed"):
        check(native)


def test_extra_native_artifact_cannot_be_silently_ignored(native):
    save(native["root"] / "run/unexpected.json", {"extra": True})
    with pytest.raises(runner.RunnerError, match="native_inventory_changed"):
        check(native)


@pytest.mark.parametrize("field,value,reason", [
    ("error_type", "RuntimeError", "native_failure_or_pending_work"),
    ("post_exit_error_type", "RuntimeError", "native_failure_or_pending_work"),
    ("pending_dispatches", [["force", 1]], "native_failure_or_pending_work"),
    ("dispatch_starts", {"score": 1}, "native_failure_or_pending_work"),
])
def test_native_incomplete_work_blocks_oracle(native, field, value, reason):
    path = native["root"] / "native-end.json"
    value_doc = json.loads(path.read_bytes())
    value_doc[field] = value
    save(path, value_doc)
    with pytest.raises(runner.RunnerError, match="file_hash_mismatch|file_size_changed"):
        check(native)
    native["child"]["lifecycle_refs"] = {name: runner.file_ref(Path(ref["path"]))
        for name, ref in native["child"]["lifecycle_refs"].items()}
    rewrite_child(native)
    with pytest.raises(runner.RunnerError, match=reason):
        check(native)


@pytest.mark.parametrize("field", ["scoring_reexecuted", "numerical_evaluation_reexecuted"])
def test_reexecution_receipt_is_rejected(native, field):
    path = Path(native["child"]["verification_ref"]["path"])
    document = json.loads(path.read_bytes())
    document[field] = True
    native["child"]["verification_ref"] = save(path, document)
    rewrite_child(native)
    with pytest.raises(runner.RunnerError, match="native_semantic_verification_required"):
        check(native)


def test_post_exit_binding_mutation_is_rejected(native):
    path = native["root"] / "post-exit-source-check.json"
    document = json.loads(path.read_bytes())
    document["input_binding"]["receipt_sha256"] = "d" * 64
    save(path, document)
    native["child"]["lifecycle_refs"] = {name: runner.file_ref(Path(ref["path"]))
        for name, ref in native["child"]["lifecycle_refs"].items()}
    rewrite_child(native)
    with pytest.raises(runner.RunnerError, match="native_source_or_input_binding_changed"):
        check(native)


def test_source_executes_captured_bytes_and_ignores_cached_code(tmp_path):
    path = tmp_path / "module.py"
    path.write_text("VALUE = 19\n")
    module = runner.load_source(runner.file_ref(path), "sro_captured_source_test")
    assert module.VALUE == 19
    assert not (tmp_path / "__pycache__").exists()


def test_file_pin_detects_replacement(tmp_path):
    path = tmp_path / "sealed.json"
    ref = save(path, {"value": 1})
    save(path, {"value": 2})
    with pytest.raises(runner.RunnerError, match="file_hash_mismatch"):
        runner.bound(ref)


@pytest.mark.parametrize("name", ["evaluation_only/reference.json", "stability_control/control.json",
                                   "atom-provenance.csv", "chemical-graph.json", "ligand-canonical.json"])
def test_forbidden_body_is_rejected_before_open(tmp_path, monkeypatch, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b'{"value": 1}'
    path.write_bytes(raw)
    ref = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    monkeypatch.setattr(runner.os, "open", lambda *_args, **_kwargs: pytest.fail("forbidden body opened"))
    with pytest.raises(runner.RunnerError, match="reference_or_provenance_body_forbidden"):
        runner.bound(ref)


def test_wrong_kind_child_rejected_without_body_read(native, monkeypatch):
    wrong = {"path": str(native["root"] / "wrong.json"), "sha256": "a" * 64, "bytes": 1}
    monkeypatch.setattr(runner, "bound", lambda *_args, **_kwargs: pytest.fail("wrong role body read"))
    with pytest.raises(runner.RunnerError, match="child_result_filename"):
        runner.native_snapshot(native["plan"], native["case"], wrong, native["driver"])


def test_wrong_preflight_path_rejected_before_read(native, monkeypatch):
    path = native["root"] / "native-start.json"
    document = json.loads(path.read_bytes())
    document["preflight_ref"]["path"] = str(native["root"] / "not-preflight.json")
    save(path, document)
    native["child"]["lifecycle_refs"] = {name: runner.file_ref(Path(ref["path"]))
        for name, ref in native["child"]["lifecycle_refs"].items()}
    rewrite_child(native)
    original = runner.bound
    def checked(ref, **kwargs):
        if ref["path"].endswith("not-preflight.json"):
            pytest.fail("wrong preflight body read")
        return original(ref, **kwargs)
    monkeypatch.setattr(runner, "bound", checked)
    with pytest.raises(runner.RunnerError, match="preflight_path_changed"):
        check(native)


def test_production_snapshot_requires_same_plan_review_and_supervisor(native):
    plan_ref = {"path": "/reviewed/plan.json", "sha256": "e" * 64, "bytes": 1}
    path = native["root"] / "native-start.json"
    document = json.loads(path.read_bytes())
    document.update(plan_ref=plan_ref, execution_review_ref={"reviewed": True}, supervisor_ref={"supervised": True})
    save(path, document)
    reseal_lifecycle(native)
    calls = []
    native["driver"].review_execution = lambda *args: calls.append(("review", args))
    native["driver"].supervisor_contract = lambda *args: calls.append(("supervisor", args))
    runner.native_snapshot(native["plan"], native["case"], native["child_ref"], native["driver"], plan_ref=plan_ref)
    assert calls == [("review", (plan_ref, {"reviewed": True})),
        ("supervisor", ({"supervised": True}, plan_ref, {"reviewed": True}, "perturbed_01", native["root"]))]


def test_wrong_plan_stops_before_review_or_oracle(native):
    path = native["root"] / "native-start.json"
    document = json.loads(path.read_bytes())
    document["plan_ref"] = {"changed": True}
    save(path, document)
    reseal_lifecycle(native)
    with pytest.raises(runner.RunnerError, match="native_start_plan_changed"):
        runner.native_snapshot(native["plan"], native["case"], native["child_ref"], native["driver"],
                               plan_ref={"expected": True})


@pytest.fixture
def layout(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    entry = source / "endpoint_oracle_runner.py"
    entry.write_text("# captured runner fixture\n")
    monkeypatch.setattr(runner, "__file__", str(entry))
    spec_ref = {"path": str(tmp_path / "oracle-input-spec.json"), "sha256": "a" * 64, "bytes": 1}
    plan = {"schema_id": "sro_native_execution_plan/1", "protocol_sha256": runner.PROTOCOL_SHA,
            "manifest_sha256": runner.MANIFEST_SHA,
            "driver_source_ref": {"path": str(source / "runtime_execution.py")},
            "oracle_phase": {"source_refs": [{"path": str(source / name)} for name in (
                "endpoint_oracle_runner.py", "campaign_supervisor.py", "sro_recovery_endpoint_numerics_v1.py")]
                + [spec_ref]}}
    return plan, spec_ref, source


def test_review_bound_source_roles_accept_metadata_without_source_execution(layout, monkeypatch):
    plan, spec_ref, source = layout
    monkeypatch.setattr(runner, "bound", lambda *_args, **_kwargs: pytest.fail("role gate read a body"))
    monkeypatch.setattr(runner, "load_source", lambda *_args, **_kwargs: pytest.fail("role gate executed source"))
    assert runner.source_layout(plan, spec_ref) == source


def test_arbitrary_driver_rejected_before_loading(layout, monkeypatch):
    plan, spec_ref, _source = layout
    plan["driver_source_ref"]["path"] = "/arbitrary/unreviewed.py"
    monkeypatch.setattr(runner, "load_source", lambda *_args, **_kwargs: pytest.fail("arbitrary source executed"))
    with pytest.raises(runner.RunnerError, match="reviewed_driver_role_path_required"):
        runner.source_layout(plan, spec_ref)


def test_injected_phase_source_rejected_before_read(layout, monkeypatch):
    plan, spec_ref, _source = layout
    plan["oracle_phase"]["source_refs"].append({"path": "/forbidden/ligand-canonical.json"})
    monkeypatch.setattr(runner, "bound", lambda *_args, **_kwargs: pytest.fail("injected body read"))
    with pytest.raises(runner.RunnerError, match="reviewed_oracle_source_roles_required"):
        runner.source_layout(plan, spec_ref)


def test_wrong_spec_role_rejected_before_read(layout):
    plan, spec_ref, _source = layout
    spec_ref["path"] = "/different/source.json"
    with pytest.raises(runner.RunnerError, match="oracle_spec_role_path_required"):
        runner.source_layout(plan, spec_ref)


def test_changed_protocol_rejected_before_source_execution(layout):
    plan, spec_ref, _source = layout
    plan["protocol_sha256"] = "f" * 64
    with pytest.raises(runner.RunnerError, match="frozen_plan_role_required"):
        runner.source_layout(plan, spec_ref)


def test_duplicate_and_nonfinite_json_rejected():
    with pytest.raises(runner.RunnerError, match="duplicate_json_key"):
        runner.loads(b'{"a":1,"a":2}')
    with pytest.raises(runner.RunnerError, match="nonfinite_json"):
        runner.loads(b'{"a":NaN}')


def test_schema_two_source_roles_preserve_metadata_only_gate(layout, monkeypatch):
    plan, spec_ref, source = layout
    plan["schema_id"] = "sro_native_execution_plan/2"
    monkeypatch.setattr(runner, "bound", lambda *_args, **_kwargs: pytest.fail("role gate read a body"))
    monkeypatch.setattr(runner, "load_source", lambda *_args, **_kwargs: pytest.fail("role gate executed source"))
    assert runner.source_layout(plan, spec_ref) == source


@pytest.mark.parametrize("field,value,reason", [
    ("schema_id", "sro_native_execution_plan/3", "frozen_plan_role_required"),
    ("protocol_sha256", "f" * 64, "frozen_plan_role_required"),
    ("manifest_sha256", "f" * 64, "frozen_plan_role_required"),
])
def test_schema_two_still_rejects_changed_frozen_contract(layout, field, value, reason):
    plan, spec_ref, _source = layout
    plan["schema_id"] = "sro_native_execution_plan/2"
    plan[field] = value
    with pytest.raises(runner.RunnerError, match=reason):
        runner.source_layout(plan, spec_ref)


def test_schema_two_lifecycle_carries_validated_revision_without_molecular_calls(layout, monkeypatch):
    plan, spec_ref, source = layout
    revision = {"explicit_fake_boundary": "validated operational lineage"}
    plan.update(schema_id="sro_native_execution_plan/2", operational_revision=revision,
                cases=[{"case_id": "perturbed_01", "request_file_ref": {"test_request": True}}],
                derivation_ref={"test_derivation": True}, wheel_ref={"test_wheel": True})
    plan_ref, child_ref = {"test_plan": True}, {"test_child": True}
    parameter_refs = {name: {"test_parameter": name} for name in ("parameters", "extensions", "cross_parameters")}
    oracle_ref = {"path": str(source / "sro_recovery_endpoint_numerics_v1.py")}
    phase = plan["oracle_phase"]
    phase.update(python_executable=str(Path(runner.sys.executable).absolute()),
                 python_binary_ref=runner.file_ref(Path(runner.sys.executable).resolve(strict=True)))
    oracle_spec = {"oracle_source_ref": oracle_ref, "dependency_site": str(source),
                   "original_parameter_refs": parameter_refs, "ligand_xml_ref": {"test_xml": "ligand"},
                   "receptor_xml_ref": {"test_xml": "receptor"}}
    # This synthetic interpreter belongs only to the fake lifecycle fixture.
    # Other suites may have product modules loaded in the real shared sys.
    monkeypatch.setattr(runner, "sys", SimpleNamespace(
        flags=SimpleNamespace(isolated=1, dont_write_bytecode=1), modules={},
        executable=runner.sys.executable, path=list(runner.sys.path)))
    validations, revisions, observations = [], [], []
    driver = SimpleNamespace(validate_plan=lambda value: validations.append(value),
        operational_revision_contract=lambda value: revisions.append(value) or revision)
    oracle = SimpleNamespace(audit_case=lambda **kwargs: observations.append(kwargs) or {"explicit_fake_boundary": True})
    def bound(ref, **kwargs):
        if ref == plan_ref:
            return plan
        if ref == spec_ref:
            return oracle_spec
        if ref == plan["derivation_ref"]:
            return {"original_input_refs": parameter_refs}
        return b"synthetic pinned source"
    monkeypatch.setattr(runner, "bound", bound)
    monkeypatch.setattr(runner, "validate_spec", lambda value, *_args: value)
    monkeypatch.setattr(runner, "load_source", lambda ref, name: driver if name == "sro_oracle_validated_driver" else oracle)
    monkeypatch.setattr(runner, "native_snapshot", lambda *_args, **_kwargs: ({}, {"test_binding": True}, {"test_endpoint": True}))
    output = source.parent / "oracle-output"
    receipt_ref = runner.run(plan_ref, "perturbed_01", child_ref, spec_ref, output)
    lifecycle = json.loads((output / "lifecycle.json").read_bytes())
    assert lifecycle["schema_id"] == "sro_endpoint_oracle_lifecycle/2"
    assert lifecycle["operational_revision"] == revision
    assert lifecycle["numerical_receipt_ref"] == receipt_ref
    assert lifecycle["new_native_force_calls"] == lifecycle["new_native_score_calls"] == 0
    assert validations == [plan, plan]
    assert revisions == [plan]
    assert len(observations) == 1  # Explicit fake callable; no numerical observation.


def test_schema_two_arbitrary_driver_rejected_before_body_read(layout, monkeypatch):
    plan, spec_ref, _source = layout
    plan["schema_id"] = "sro_native_execution_plan/2"
    plan["driver_source_ref"]["path"] = "/arbitrary/unreviewed.py"
    monkeypatch.setattr(runner, "bound", lambda *_args, **_kwargs: pytest.fail("arbitrary source body read"))
    monkeypatch.setattr(runner, "load_source", lambda *_args, **_kwargs: pytest.fail("arbitrary source executed"))
    with pytest.raises(runner.RunnerError, match="reviewed_driver_role_path_required"):
        runner.source_layout(plan, spec_ref)
