"""Portable native dispatch boundaries; fixtures perform no molecular work."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import time

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_sro_pose_recovery/runtime_execution.py"
spec = importlib.util.spec_from_file_location("sro_native_execution_test", SOURCE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def saved(tmp_path, name, value):
    path = tmp_path / name
    path.write_bytes(runtime.encode(value))
    return runtime.pin(path)


@pytest.fixture
def observed():
    xyz = [[float(i).hex(), "0x0.0p+0", "0x0.0p+0"] for i in range(26)]
    pose = {"valid": False, "checks": {k: False for k in runtime.GEOMETRY_CHECKS},
            "evaluated_checks": {k: True for k in runtime.GEOMETRY_CHECKS}, "complete": True,
            "valid_within_evaluated_scope": False, "measurements": {}, "blockers": [],
            "not_evaluated_reasons": [], "claim_safe": False}
    return {"execution_complete": True, "score_calls": 2,
            "attempt": {"status": "success", "post_coordinates_binary64_hex": xyz},
            "rows": {arm: {"succeeded": True, "status": "success", "score": 1.0, "terms": {},
                           "pose_validity": deepcopy(pose), "validity_complete": True,
                           "coordinates_binary64_hex": deepcopy(xyz)} for arm in ("baseline", "refined")},
            "numerical_result": {"checkpoint": {"state": {"current": {"coordinates": xyz}}}}}


def test_complete_invalid_geometry_is_completed_without_admission(observed):
    assert runtime.completed_observations(observed) is observed
    assert not any(observed["rows"]["refined"]["pose_validity"]["checks"].values())


@pytest.mark.parametrize("arm", ["baseline", "refined"])
@pytest.mark.parametrize("field,value", [("succeeded", False), ("status", "failure"),
                                        ("score", float("nan")), ("terms", None)])
def test_score_failure_blocks_native_completion(observed, arm, field, value):
    observed["rows"][arm][field] = value
    with pytest.raises(runtime.ExecutionError, match="successful_finite_score_required"):
        runtime.completed_observations(observed)


def test_incomplete_geometry_blocks_native_completion(observed):
    observed["rows"]["refined"]["pose_validity"]["complete"] = False
    with pytest.raises(runtime.ExecutionError, match="complete_authenticated_geometry_required"):
        runtime.completed_observations(observed)


def test_final_row_cannot_substitute_another_trajectory_state(observed):
    observed["rows"]["refined"]["coordinates_binary64_hex"][0][0] = float(999).hex()
    with pytest.raises(runtime.ExecutionError, match="last_accepted_geometry_binding"):
        runtime.completed_observations(observed)


def test_captured_adapter_source_executes_without_bytecode_cache(tmp_path):
    path = tmp_path / "adapter.py"
    path.write_text("VALUE = 47\n")
    module = runtime.load_adapter(runtime.pin(path))
    assert module.VALUE == 47
    assert not (tmp_path / "__pycache__").exists()


def test_bound_rejects_mutated_or_duplicate_json(tmp_path):
    ref = saved(tmp_path, "sealed.json", {"value": 1})
    Path(ref["path"]).write_bytes(b'{"value": 2}')
    with pytest.raises(runtime.ExecutionError, match="immutable_input_changed"):
        runtime.bound(ref)
    path = tmp_path / "duplicate.json"
    path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(runtime.ExecutionError, match="duplicate_json_key"):
        runtime.bound(runtime.pin(path))


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    # Shell-less test runners may be reparented to PID 1; use a controlled parent.
    monkeypatch.setattr(runtime.os, "getppid", lambda: 12345)
    plan = {"path": "/reviewed/plan.json", "sha256": "a" * 64, "bytes": 1}
    review = {"path": "/reviewed/review.json", "sha256": "b" * 64, "bytes": 1}
    start = time.monotonic_ns() - 1_000_000
    value = {"schema_id": "sro_native_case_supervisor/1", "case_id": "perturbed_01",
             "plan_ref": plan, "execution_review_ref": review, "controller_pid": os.getppid(),
             "started_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
             "started_monotonic_ns": start, "deadline_monotonic_ns": start + 7200 * 1_000_000_000,
             "native_output": str(tmp_path / "native")}
    return value, plan, review


def verify_supervisor(tmp_path, supervisor):
    value, plan, review = supervisor
    return runtime.supervisor_contract(saved(tmp_path, "supervisor.json", value), plan, review,
                                       "perturbed_01", tmp_path / "native")


def test_same_parent_and_exact_shared_deadline_required(tmp_path, supervisor):
    assert verify_supervisor(tmp_path, supervisor)["controller_pid"] == os.getppid()
    supervisor[0]["controller_pid"] += 10000
    with pytest.raises(runtime.ExecutionError, match="supervisor_parent_required"):
        verify_supervisor(tmp_path, supervisor)


def test_supervisor_cannot_extend_the_frozen_ceiling(tmp_path, supervisor):
    supervisor[0]["deadline_monotonic_ns"] += 1
    with pytest.raises(runtime.ExecutionError, match="case_deadline_required"):
        verify_supervisor(tmp_path, supervisor)


def test_supervisor_case_mismatch_rejected(tmp_path, supervisor):
    supervisor[0]["case_id"] = "perturbed_02"
    with pytest.raises(runtime.ExecutionError, match="supervisor_association"):
        verify_supervisor(tmp_path, supervisor)


def test_deadline_rejects_dispatch_before_count_or_call(tmp_path):
    ledger = runtime.DispatchLedger(tmp_path / "dispatch.jsonl", deadline_monotonic_ns=time.monotonic_ns() - 1)
    calls = []
    with pytest.raises(runtime.ExecutionError, match="case_deadline_exhausted"):
        ledger.wrap(lambda: calls.append(True), "force")()
    assert calls == [] and ledger.counts["force"] == 0 and not ledger.path.exists()


def test_failed_dispatch_keeps_attempt_and_error_receipts(tmp_path):
    ledger = runtime.DispatchLedger(tmp_path / "dispatch.jsonl", deadline_monotonic_ns=time.monotonic_ns() + 10**9)
    def failed():
        raise RuntimeError("fixture failure")
    with pytest.raises(RuntimeError):
        ledger.wrap(failed, "force")()
    events = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["begin", "end"]
    assert events[-1]["error_type"] == "RuntimeError" and ledger.counts["force"] == 1
    assert ledger.active == []


def test_arbitrary_oracle_source_role_rejected_before_body_read(monkeypatch):
    phase = {"python_executable": "/usr/bin/python3", "python_binary_ref": {}, "argv_template": [],
             "source_refs": [{"path": "/forbidden/ligand-canonical.json"}], "receipt_name": "numerical-receipt.json"}
    monkeypatch.setattr(runtime, "bound", lambda *_args, **_kwargs: pytest.fail("unreviewed body read"))
    with pytest.raises(runtime.ExecutionError, match="oracle_source_roles_required"):
        runtime.oracle_phase_contract(phase)


@pytest.fixture
def saved_verifier():
    from contextlib import contextmanager
    from types import SimpleNamespace

    state = {"guarded": False, "calls": 0, "geometry_allowed": False}
    result = {"structural_verification_passed": True, "scoring_reexecuted": False,
              "numerical_evaluation_reexecuted": False}

    @contextmanager
    def guard(*, allow_saved_geometry=False):
        assert allow_saved_geometry is True
        state["guarded"] = True
        state["geometry_allowed"] = allow_saved_geometry
        try:
            yield
        finally:
            state["guarded"] = False

    def verify(request, output):
        assert state["guarded"] and state["geometry_allowed"]
        assert request == {"saved": True} and output == Path("saved-run")
        state["calls"] += 1
        return result

    return SimpleNamespace(forbid_physics=guard), SimpleNamespace(verify_output=verify), state, result


def test_saved_verification_uses_only_geometry_guard(saved_verifier):
    adapter, workflow, state, result = saved_verifier
    assert runtime.verify_saved_output(adapter, workflow, {"saved": True}, Path("saved-run")) is result
    assert state["calls"] == 1 and state["guarded"] is False


@pytest.mark.parametrize("field,value", [("structural_verification_passed", False),
                                         ("scoring_reexecuted", True),
                                         ("numerical_evaluation_reexecuted", True)])
def test_saved_verification_requires_semantics_and_no_new_calculation(saved_verifier, field, value):
    adapter, workflow, state, result = saved_verifier
    result[field] = value
    with pytest.raises(runtime.ExecutionError, match="read_only_semantic_verification_required"):
        runtime.verify_saved_output(adapter, workflow, {"saved": True}, Path("saved-run"))
    assert state["calls"] == 1 and state["guarded"] is False


def test_older_guard_rejected_before_native_work():
    from types import SimpleNamespace

    calls = []
    def old_guard():
        calls.append("guard invoked")
    with pytest.raises(runtime.ExecutionError, match="saved_geometry_guard_capability_required"):
        runtime.require_saved_geometry_guard(SimpleNamespace(forbid_physics=old_guard))
    assert calls == []


def test_saved_geometry_guard_default_must_stay_strict():
    from types import SimpleNamespace

    def permissive_guard(*, allow_saved_geometry=True):
        pytest.fail("capability review must not invoke guard")
    with pytest.raises(runtime.ExecutionError, match="saved_geometry_guard_capability_required"):
        runtime.require_saved_geometry_guard(SimpleNamespace(forbid_physics=permissive_guard))


def test_saved_geometry_guard_support_is_inspected_without_invocation(saved_verifier):
    adapter, _workflow, state, _result = saved_verifier
    runtime.require_saved_geometry_guard(adapter)
    assert state["calls"] == 0 and state["guarded"] is False


@pytest.fixture
def revision_packet(tmp_path, monkeypatch):
    """Synthetic metadata only; protected original refs deliberately do not exist."""
    old = tmp_path / "old-audit"
    repaired = tmp_path / "repaired-audit"
    predecessor = tmp_path / "stopped-campaign"
    for root in (old, repaired, predecessor):
        root.mkdir()
    for root in (old, repaired):
        (root / "derived-inputs").mkdir()
    wheel_path = tmp_path / "frozen.whl"
    wheel_path.write_bytes(b"synthetic frozen wheel; never imported")
    wheel_ref = runtime.pin(wheel_path)
    monkeypatch.setattr(runtime, "WHEEL_SHA", wheel_ref["sha256"])
    monkeypatch.setattr(runtime, "AUDIT_ROOT", str(old))
    monkeypatch.setattr(runtime, "REPAIRED_AUDIT_ROOT", str(repaired))
    monkeypatch.setattr(runtime, "OLD_SITE", str(tmp_path / "unimported-site"))
    adapter_refs = {}
    for root, marker in ((old, "old"), (repaired, "repaired")):
        path = root / "runtime_adapter_snapshot.py"
        path.write_text("# synthetic " + marker + " adapter; never executed\n")
        adapter_refs[root] = runtime.pin(path)
    monkeypatch.setattr(
        runtime, "REPAIRED_ADAPTER_SHA", adapter_refs[repaired]["sha256"]
    )
    cases = []
    bindings = {}
    for case_id in runtime.CASE_IDS:
        refs = {
            name: saved(old, case_id + "-" + name + ".json", {"synthetic": name})
            for name in runtime.FILE_FIELDS
        }
        request = {
            "schema_id": "cpu_cartesian_registered_pose_request/1.3.0",
            "backend": "python_cpu_reference",
            "solvation": None,
            "solver": {
                "algorithm": "lbfgs",
                "max_objective_attempts": 417,
                "max_accepted_steps": 416,
                "max_restart_verifications": 2,
                "force_tolerance": 0.001,
                "maximum_atom_displacement": 0.05,
            },
            "budget": {
                "candidate_count": 1,
                "top_k": 1,
                "max_torsions": 0,
                "translation_radius_angstrom": 0,
            },
            "pocket": {"coordinate_frame_id": runtime.FRAME},
            **{
                name: {key: ref[key] for key in ("path", "sha256")}
                for name, ref in refs.items()
            },
        }
        request_ref = saved(old, case_id + "-request.json", request)
        proof_ref = saved(
            old,
            case_id + "-proof.json",
            {
                "all_nonidentity_fields_exact": True,
                "rebound_identity_fields": list(runtime.FILE_FIELDS),
            },
        )
        cases.append(
            {
                "case_id": case_id,
                "derived_input_refs": refs,
                "request_file_ref": request_ref,
                "numeric_term_preservation_proof_ref": proof_ref,
                "source_candidate_coordinates_sha256": "c" * 64,
            }
        )
        binding = {
            "executed_wheel": wheel_ref,
            "installed_site": runtime.OLD_SITE,
            "python_executable": "/usr/bin/python3",
            "input_binding": {
                "request_sha256": runtime.native_digest(request),
                "source_identity": "frozen synthetic source",
            },
        }
        bindings[case_id] = binding
    derivation = {
        "schema_id": "synthetic_derivation/1",
        "adapter_source_sha256": adapter_refs[old]["sha256"],
        "prospective_protocol_sha256": runtime.PROTOCOL_SHA,
        "prospective_manifest_sha256": runtime.MANIFEST_SHA,
        "expected_executed_wheel_sha256": runtime.WHEEL_SHA,
        "original_input_refs": {
            "ligand": {
                "path": "/forbidden/unread/original-ligand.json",
                "sha256": "d" * 64,
                "bytes": 999,
            }
        },
        "cases": cases,
    }
    packets = {}
    for root in (old, repaired):
        current = deepcopy(derivation)
        current["adapter_source_sha256"] = adapter_refs[root]["sha256"]
        derivation_ref = saved(root / "derived-inputs", "derivation.json", current)
        audit = {
            "status": "passed",
            "requested_derivatives": 4,
            "prepared_derivatives": 4,
            "reference_body_reads": 0,
            "original_ligand_body_reads": 0,
            "protocol_sha256": runtime.PROTOCOL_SHA,
            "manifest_sha256": runtime.MANIFEST_SHA,
            "source_adapter_sha256": adapter_refs[root]["sha256"],
            "actual_execution_authorized": False,
            "scientifically_validated": False,
            **{
                field: 0
                for field in (
                    "actual_new_OpenMM_observations",
                    "actual_new_force_calls",
                    "actual_new_native_graph_calls",
                    "actual_new_optimizer_calls",
                    "actual_new_score_calls",
                )
            },
        }
        audit_ref = saved(root, "root-audit.json", audit)
        payload_refs = [adapter_refs[root], derivation_ref, audit_ref]
        payload_refs.extend(
            saved(root, case_id + "-installed-binding.json", binding)
            for case_id, binding in bindings.items()
        )
        manifest_ref = saved(
            root,
            "manifest.json",
            {
                "payload_files": {
                    str(Path(ref["path"]).relative_to(root)): {
                        key: ref[key] for key in ("sha256", "bytes")
                    }
                    for ref in payload_refs
                }
            },
        )
        packets[root] = {
            "root_audit_ref": audit_ref,
            "derivation_ref": derivation_ref,
            "audit_manifest_ref": manifest_ref,
        }
    for name, ref in packets[old].items():
        monkeypatch.setattr(
            runtime,
            {
                "root_audit_ref": "ROOT_AUDIT_SHA",
                "derivation_ref": "DERIVATION_SHA",
                "audit_manifest_ref": "AUDIT_MANIFEST_SHA",
            }[name],
            ref["sha256"],
        )
    for name, ref in packets[repaired].items():
        monkeypatch.setattr(
            runtime,
            {
                "root_audit_ref": "REPAIRED_ROOT_AUDIT_SHA",
                "derivation_ref": "REPAIRED_DERIVATION_SHA",
                "audit_manifest_ref": "REPAIRED_AUDIT_MANIFEST_SHA",
            }[name],
            ref["sha256"],
        )
    dispatch_path = predecessor / "dispatch.jsonl"
    dispatch_path.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {"event": "begin", "kind": "force", "index": 0},
                {
                    "event": "end",
                    "kind": "force",
                    "index": 0,
                    "error_type": "AdapterError",
                },
            )
        )
        + "\n"
    )
    dispatch_ref = runtime.pin(dispatch_path)
    campaign = {
        "schema_id": "sro_four_case_campaign/1",
        "status": "stopped",
        "denominator": 4,
        "execution_order": runtime.CASE_IDS,
        "completed_count": 0,
        "unstarted_count": 3,
        "scientifically_validated": False,
        "product_qualified": False,
        "HIP_qualified": False,
        "case_results": [
            {
                "case_id": case_id,
                "status": "failed" if index == 0 else "unstarted",
                "actual_receipt_refs": [dispatch_ref] if index == 0 else [],
            }
            for index, case_id in enumerate(runtime.CASE_IDS)
        ],
    }
    revision = deepcopy(runtime.OPERATIONAL_REVISION)
    revision.update(
        {
            "predecessor_campaign_ref": saved(
                predecessor, "campaign-result.json", campaign
            ),
            "predecessor_dispatch_ref": dispatch_ref,
            **{"predecessor_" + field: ref for field, ref in packets[old].items()},
        }
    )
    monkeypatch.setattr(runtime, "OPERATIONAL_REVISION", revision)
    plans = {
        root: runtime.build_plan(
            root, "/usr/bin/python3", tmp_path / (root.name + "-plan.json")
        )
        for root in (old, repaired)
    }
    return {"old": old, "repaired": repaired, "plans": plans, "revision": revision}


def repaired_plan(revision_packet):
    return revision_packet["plans"][revision_packet["repaired"]]


def replace_pinned_json(plan, field, anchor, change, monkeypatch):
    ref = plan[field]
    value = runtime.bound(ref)
    change(value)
    Path(ref["path"]).write_bytes(runtime.encode(value))
    plan[field] = runtime.pin(ref["path"])
    monkeypatch.setattr(runtime, anchor, plan[field]["sha256"])


def test_legacy_and_one_repaired_revision_keep_frozen_science(revision_packet):
    old = revision_packet["plans"][revision_packet["old"]]
    new = repaired_plan(revision_packet)
    assert runtime.validate_plan(old) is old and runtime.validate_plan(new) is new
    assert (
        old["schema_id"] == "sro_native_execution_plan/1"
        and "operational_revision" not in old
    )
    assert new["schema_id"] == "sro_native_execution_plan/2"
    assert runtime.operational_revision_contract(new) == revision_packet["revision"]
    assert old["budget"] == new["budget"] == runtime.BUDGET
    assert old["protocol_sha256"] == new["protocol_sha256"] == runtime.PROTOCOL_SHA
    assert old["manifest_sha256"] == new["manifest_sha256"] == runtime.MANIFEST_SHA
    assert new["operational_revision"]["predecessor_force_dispatch"] == {
        "attempts": 1,
        "returned": 0,
        "errors": 1,
    }


def test_arbitrary_audit_override_rejected_before_body_read(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime, "pin", lambda *_: pytest.fail("unreviewed audit body read")
    )
    with pytest.raises(runtime.ExecutionError, match="declared_audit_root_required"):
        runtime.build_plan(tmp_path, "/usr/bin/python3", tmp_path / "plan.json")


@pytest.mark.parametrize(
    "field,value",
    [
        ("resume", True),
        ("budget_reset", True),
        ("independent_dataset", True),
        ("scientific_protocol_changed", True),
        ("source_roles_changed", True),
        ("predecessor_denominator", 3),
        ("predecessor_failed_count", 0),
        ("predecessor_unstarted_count", 0),
        ("purpose", "scientific_replication"),
    ],
)
def test_revision_semantics_rejected_before_predecessor_read(
    revision_packet, monkeypatch, field, value
):
    plan = repaired_plan(revision_packet)
    plan["operational_revision"][field] = value
    monkeypatch.setattr(
        runtime,
        "bound",
        lambda *_a, **_kw: pytest.fail("unreviewed predecessor body read"),
    )
    with pytest.raises(runtime.ExecutionError, match="operational_revision_changed"):
        runtime.operational_revision_contract(plan)


@pytest.mark.parametrize("field", ["path", "sha256", "bytes"])
def test_predecessor_typed_pin_cannot_be_substituted(
    revision_packet, monkeypatch, field
):
    plan = repaired_plan(revision_packet)
    plan["operational_revision"]["predecessor_campaign_ref"][field] = {
        "path": "/forbidden/predecessor.json",
        "sha256": "e" * 64,
        "bytes": 1,
    }[field]
    monkeypatch.setattr(
        runtime,
        "bound",
        lambda *_a, **_kw: pytest.fail("unreviewed predecessor body read"),
    )
    with pytest.raises(runtime.ExecutionError, match="operational_revision_changed"):
        runtime.operational_revision_contract(plan)


def test_adapter_revision_pin_rejected_before_predecessor_read(
    revision_packet, monkeypatch
):
    plan = repaired_plan(revision_packet)
    plan["adapter_ref"]["sha256"] = "f" * 64
    monkeypatch.setattr(
        runtime,
        "bound",
        lambda *_a, **_kw: pytest.fail("unreviewed predecessor body read"),
    )
    with pytest.raises(
        runtime.ExecutionError, match="operational_revision_audit_binding"
    ):
        runtime.operational_revision_contract(plan)


@pytest.mark.parametrize(
    "field", ["cases", "original_input_refs", "prospective_protocol_sha256"]
)
def test_repair_cannot_change_any_frozen_derivation_field(
    revision_packet, monkeypatch, field
):
    plan = repaired_plan(revision_packet)

    def change(value):
        if field == "cases":
            value[field][0]["source_candidate_coordinates_sha256"] = "a" * 64
        elif field == "original_input_refs":
            value[field]["ligand"]["path"] = "/forbidden/promoted-reference.json"
        else:
            value[field] = "b" * 64

    replace_pinned_json(
        plan, "derivation_ref", "REPAIRED_DERIVATION_SHA", change, monkeypatch
    )
    with pytest.raises(runtime.ExecutionError, match="scientific_derivation_changed"):
        runtime.operational_revision_contract(plan)


@pytest.mark.parametrize(
    "field",
    [
        "actual_new_force_calls",
        "actual_new_score_calls",
        "reference_body_reads",
        "original_ligand_body_reads",
    ],
)
def test_fresh_audit_has_zero_dispatch_and_no_protected_body_reads(
    revision_packet, monkeypatch, field
):
    plan = repaired_plan(revision_packet)
    replace_pinned_json(
        plan,
        "root_audit_ref",
        "REPAIRED_ROOT_AUDIT_SHA",
        lambda value: value.update({field: 1}),
        monkeypatch,
    )
    with pytest.raises(
        runtime.ExecutionError, match="zero_dispatch_repaired_audit_required"
    ):
        runtime.operational_revision_contract(plan)


def test_fresh_installed_binding_cannot_change_frozen_environment(revision_packet):
    plan = repaired_plan(revision_packet)
    ref = plan["cases"][0]["expected_binding_ref"]
    value = runtime.bound(ref)
    value["input_binding"]["source_identity"] = "changed synthetic source"
    Path(ref["path"]).write_bytes(runtime.encode(value))
    plan["cases"][0]["expected_binding_ref"] = runtime.pin(ref["path"])
    with pytest.raises(
        runtime.ExecutionError, match="operational_input_binding_changed"
    ):
        runtime.operational_revision_contract(plan)


def test_legacy_plan_rejects_revision_injection_before_read(
    revision_packet, monkeypatch
):
    plan = revision_packet["plans"][revision_packet["old"]]
    plan["operational_revision"] = deepcopy(revision_packet["revision"])
    monkeypatch.setattr(
        runtime,
        "bound",
        lambda *_a, **_kw: pytest.fail("unreviewed predecessor body read"),
    )
    with pytest.raises(runtime.ExecutionError, match="legacy_revision_injection"):
        runtime.operational_revision_contract(plan)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "completed"),
        ("denominator", 3),
        ("completed_count", 1),
        ("unstarted_count", 0),
    ],
)
def test_predecessor_metadata_cannot_erase_failed_roster(
    revision_packet, monkeypatch, field, value
):
    plan = repaired_plan(revision_packet)
    revision = plan["operational_revision"]
    ref = revision["predecessor_campaign_ref"]
    campaign = runtime.bound(ref)
    campaign[field] = value
    Path(ref["path"]).write_bytes(runtime.encode(campaign))
    revision["predecessor_campaign_ref"] = runtime.pin(ref["path"])
    monkeypatch.setattr(runtime, "OPERATIONAL_REVISION", deepcopy(revision))
    with pytest.raises(runtime.ExecutionError, match="stopped_predecessor_required"):
        runtime.operational_revision_contract(plan)


def test_predecessor_force_error_cannot_be_promoted_to_return(
    revision_packet, monkeypatch
):
    plan = repaired_plan(revision_packet)
    revision = plan["operational_revision"]
    ref = revision["predecessor_dispatch_ref"]
    path = Path(ref["path"])
    events = [runtime.loads(line) for line in path.read_bytes().splitlines()]
    events[-1]["error_type"] = None
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    revision["predecessor_dispatch_ref"] = runtime.pin(path)
    campaign_path = Path(revision["predecessor_campaign_ref"]["path"])
    campaign = runtime.loads(campaign_path.read_bytes())
    campaign["case_results"][0]["actual_receipt_refs"] = [
        revision["predecessor_dispatch_ref"]
    ]
    campaign_path.write_bytes(runtime.encode(campaign))
    revision["predecessor_campaign_ref"] = runtime.pin(campaign_path)
    monkeypatch.setattr(runtime, "OPERATIONAL_REVISION", deepcopy(revision))
    with pytest.raises(
        runtime.ExecutionError, match="predecessor_force_attempt_required"
    ):
        runtime.operational_revision_contract(plan)


def test_incomplete_fresh_audit_anchors_never_open_inputs(revision_packet, monkeypatch):
    monkeypatch.setattr(runtime, "REPAIRED_ROOT_AUDIT_SHA", None)
    monkeypatch.setattr(
        runtime, "pin", lambda *_a: pytest.fail("unanchored audit body read")
    )
    with pytest.raises(runtime.ExecutionError, match="repaired_audit_anchors_required"):
        runtime.build_plan(
            revision_packet["repaired"], "/usr/bin/python3", Path("unused")
        )


@pytest.mark.parametrize("field", ["actual_execution_authorized", "scientifically_validated"])
def test_revision_plan_cannot_promote_authority_or_scientific_claim(revision_packet, monkeypatch, field):
    plan = repaired_plan(revision_packet)
    plan[field] = True
    monkeypatch.setattr(runtime, "bound", lambda *_a, **_kw: pytest.fail("unreviewed predecessor body read"))
    with pytest.raises(runtime.ExecutionError, match="operational_revision_claim_boundary"):
        runtime.operational_revision_contract(plan)
