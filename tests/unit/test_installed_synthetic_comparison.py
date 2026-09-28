"""Installed synthetic comparison execution, recovery, and integrity contracts."""

import copy
import json
import math
from pathlib import Path
import shutil
import time

import pytest

from betelgeuze_engine.product.prepared_pose_journal import _input_binding
from betelgeuze_product import installed_synthetic_comparison as installed
from tools.product import compare_prepared_candidate_policies as research
from tests.unit.test_prepared_candidate_comparison import _protocol


def _installed_protocol(tmp_path):
    old = _protocol(tmp_path, seconds=20.0, calls=10)
    protocol = {key: value for key, value in old.items() if key != "top_k"}
    protocol.update(schema_version=installed.PROTOCOL,
                    arm_order=["ai_engine", "similarity", "engine", "similarity_engine"],
                    selection_seed=17, tie_policy="seeded_pool_order")
    return protocol


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("installed-four-arm-run")
    protocol = _installed_protocol(root / "inputs")
    result = installed.run(protocol, root / "run")
    return root, protocol, result


def test_real_four_arm_run_read_only_verify_and_idempotent_resume(completed):
    root, protocol, result = completed
    run_dir = root / "run"
    assert result["arm_order"] == protocol["arm_order"]
    assert result["pool"] == list("abcd")
    assert set(result["arms"]) == set(installed.ARMS)
    assert result["evaluation_labels_read"] == 0
    assert result["source_authenticated"] is False
    assert result["scientifically_validated"] is False
    for arm in installed.ARMS:
        data = result["arms"][arm]
        assert data["denominator"]["requested"] == 4
        assert data["completion"]["status"] == "complete"
        assert data["completion"]["budget_seconds"] == 20.0
        if arm == "engine":
            assert data["priority"]["order"] == list("abcd")
        else:
            assert set(data["priority"]["order"]) == set("abc")
    assert result["arms"]["similarity"]["denominator"] == {
        "requested": 4, "evaluated": 3, "unsupported": 1}
    assert result["arms"]["engine"]["denominator"] == {
        "requested": 4, "evaluated": 2, "failed": 1, "unsupported": 1}
    before = {str(path.relative_to(run_dir)): path.read_bytes()
              for path in run_dir.rglob("*") if path.is_file()}
    assert installed.verify_run(protocol, run_dir)["status"] == "verified"
    assert installed.run(protocol, run_dir, resume=True) == result
    after = {str(path.relative_to(run_dir)): path.read_bytes()
             for path in run_dir.rglob("*") if path.is_file()}
    assert before == after


def test_same_synthetic_v2_policy_matches_checkout_comparator(completed):
    root, protocol, result = completed
    legacy = copy.deepcopy(protocol)
    legacy.update(schema_version=research.ORDERED_SCHEMA, top_k=2)
    previous = research.run(legacy, root / "checkout-parity")
    for arm in installed.ARMS:
        actual, expected = result["arms"][arm], previous["arms"][arm]
        old_priority = expected["worker_observations"]["priority.json"]
        assert actual["priority"]["order"] == old_priority["order"]
        assert actual["priority"]["predictions"] == old_priority["predictions"]
        assert actual["denominator"] == expected["denominator"]
        assert [(row["record_id"], row["status"], row["score"]) for row in actual["rows"]] == [
            (row["record_id"], row["status"], row["score"]) for row in expected["rows"]]


def test_resealed_priority_and_result_still_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "resealed"
    shutil.copytree(root / "run", copied)
    priority_path = copied / "ai_engine" / "priority.json"
    priority = json.loads(priority_path.read_text())
    priority["order"][:2] = reversed(priority["order"][:2])
    priority_path.write_bytes(installed._canonical(priority) + b"\n")
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    result["arms"]["ai_engine"]["priority"] = priority
    result_path.write_bytes(installed._canonical(result) + b"\n")
    verdict = installed.verify_run(protocol, copied)
    assert verdict["reason"] == "installed_priority_recalculation_mismatch"
    with pytest.raises(ValueError, match="installed_priority_recalculation_mismatch"):
        installed.run(protocol, copied, resume=True)


def test_resealed_row_and_result_cannot_detach_score_from_pose(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "resealed-score"
    shutil.copytree(root / "run", copied)
    rid = "a"
    path = copied / "engine" / f"{installed._sha(rid)}.row.json"
    wrapped = json.loads(path.read_text())
    wrapped["payload"]["score"] += 1.0
    wrapped["sha256"] = installed._sha(wrapped["payload"])
    path.write_bytes(installed._canonical(wrapped) + b"\n")
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    row = next(item for item in result["arms"]["engine"]["rows"]
               if item["record_id"] == rid)
    row["score"] = wrapped["payload"]["score"]
    result_path.write_bytes(installed._canonical(result) + b"\n")
    assert installed.verify_run(protocol, copied)["reason"] == "installed_pose_report_score_mismatch"


def test_resealed_pose_report_cannot_be_assigned_to_another_candidate(completed, tmp_path):
    root, protocol, result = completed
    copied = tmp_path / "cross-candidate-pose"
    shutil.copytree(root / "run", copied)
    first, second = "a", "b"
    first_row = next(row for row in result["arms"]["engine"]["rows"]
                     if row["record_id"] == first)
    second_report = copied / "engine" / f"{installed._sha(second)}.poses.json"
    second_report.write_bytes(
        (copied / "engine" / f"{installed._sha(first)}.poses.json").read_bytes()
    )
    second_row_path = copied / "engine" / f"{installed._sha(second)}.row.json"
    wrapped = json.loads(second_row_path.read_text())
    wrapped["payload"].update(
        score=first_row["score"],
        pose_report=installed._entry(
            f"engine/{installed._sha(second)}.poses.json", second_report.read_bytes()),
        pose_denominator=first_row["pose_denominator"],
        numeric_denominator=first_row["numeric_denominator"],
    )
    wrapped["sha256"] = installed._sha(wrapped["payload"])
    second_row_path.write_bytes(installed._canonical(wrapped) + b"\n")
    result_path = copied / "comparison.json"
    resealed = json.loads(result_path.read_text())
    arm = resealed["arms"]["engine"]
    arm["rows"] = [wrapped["payload"] if row["record_id"] == second else row
                   for row in arm["rows"]]
    arm["ranked_record_ids"] = [row["record_id"] for row in sorted(
        (row for row in arm["rows"] if row["status"] == "evaluated"),
        key=lambda row: (row["score"], row["record_id"]),
    )]
    result_path.write_bytes(installed._canonical(resealed) + b"\n")
    assert installed.verify_run(protocol, copied)["reason"] == (
        "installed_pose_report_request_mismatch"
    )
    with pytest.raises(ValueError, match="installed_pose_report_request_mismatch"):
        installed.run(protocol, copied, resume=True)


def _reseal_pose_report(run_dir, arm, rid, report):
    path, relative = installed._report_ref(run_dir, arm, rid)
    path.write_bytes(installed._canonical(report) + b"\n")
    row_path = run_dir / arm / f"{installed._sha(rid)}.row.json"
    wrapped = installed._json(row_path.read_bytes())
    wrapped["payload"]["pose_report"] = installed._entry(relative, path.read_bytes())
    wrapped["sha256"] = installed._sha(wrapped["payload"])
    row_path.write_bytes(installed._canonical(wrapped) + b"\n")
    result_path = run_dir / "comparison.json"
    result = installed._json(result_path.read_bytes())
    result["arms"][arm]["rows"] = [
        wrapped["payload"] if row["record_id"] == rid else row
        for row in result["arms"][arm]["rows"]
    ]
    result_path.write_bytes(installed._canonical(result) + b"\n")


@pytest.mark.parametrize("location,field,value", [
    ("source_geometry", "physical_validity_assessed", True),
    ("pose_geometry", "physical_validity_assessed", True),
    ("source_geometry", "affects_score_or_admission", True),
    ("pose_geometry", "scientifically_validated", True),
    ("result", "scientifically_validated", True),
    ("result", "customer_execution", True),
    ("result", "external_solver_called", True),
    ("result", "uncertainty_calibrated", True),
    ("result", "uncertainty", 0.01),
    ("quantities", "affinity", -7.0),
    ("quantities", "strain", 0.0),
])
def test_resealed_pose_report_cannot_grant_physical_authority(
    completed, tmp_path, location, field, value,
):
    root, protocol, _ = completed
    copied = tmp_path / "pose-authority"
    shutil.copytree(root / "run", copied)
    path, _ = installed._report_ref(copied, "engine", "a")
    report = installed._json(path.read_bytes())
    target = {
        "source_geometry": report["preparation"]["source_geometry_observation"],
        "pose_geometry": report["rows"][0]["pose_geometry_observation"],
        "result": report["rows"][0]["result"],
        "quantities": report["rows"][0]["result"]["quantities"],
    }[location]
    target[field] = value
    assert installed.check_report(report)["status"] == "passed"
    _reseal_pose_report(copied, "engine", "a", report)
    before = {path: path.read_bytes() for path in copied.rglob("*") if path.is_file()}
    reason = "installed_pose_report_authority_claim"
    assert installed.verify_run(protocol, copied)["reason"] == reason
    with pytest.raises(ValueError, match=reason):
        installed.run(protocol, copied, resume=True)
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_resealed_pocket_declaration_cannot_admit_an_outside_pose(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "pocket-admission"
    shutil.copytree(root / "run", copied)
    changed = copy.deepcopy(protocol)
    request = installed._bound_json(changed["requests"]["a"])
    request["evaluation"]["pocket_radius_angstrom"] = 0.1
    request_path = tmp_path / "outside-pocket.request.json"
    request_path.write_bytes(installed._canonical(request) + b"\n")
    changed["requests"]["a"] = {
        "path": str(request_path), "sha256": installed._digest(request_path.read_bytes()),
    }
    frozen = installed.freeze(changed)
    binding = installed._sha(frozen)

    def rebind(value):
        if isinstance(value, dict):
            return {key: binding if key == "binding" else rebind(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [rebind(item) for item in value]
        return value

    for path in copied.rglob("*.json"):
        if path.name == "frozen.json":
            value = {"payload": frozen, "sha256": binding}
        else:
            value = rebind(installed._json(path.read_bytes()))
            if set(value) == {"payload", "sha256"}:
                value["sha256"] = installed._sha(value["payload"])
        path.write_bytes(installed._canonical(value) + b"\n")
    for arm in installed.ARMS:
        if arm == "similarity":
            continue
        path, _ = installed._report_ref(copied, arm, "a")
        report = installed._json(path.read_bytes())
        for row in report["rows"]:
            row["result"]["pocket"]["radius_angstrom"] = 0.1
        assert installed.check_report(report)["status"] == "passed"
        _reseal_pose_report(copied, arm, "a", report)
    before = {path: path.read_bytes() for path in copied.rglob("*") if path.is_file()}
    reason = "installed_pose_outside_declared_pocket"
    assert installed.verify_run(changed, copied)["reason"] == reason
    with pytest.raises(ValueError, match=reason):
        installed.run(changed, copied, resume=True)
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_pocket_boundary_matches_producer_float64_distance() -> None:
    import torch

    point = [2.7782693785236816, -2.552049145485375, 0.9548893141911563]
    center = [0.0, 0.0, 0.0]
    radius = 3.8914713390916105
    coordinates = torch.tensor([[point]], dtype=torch.float64)
    assert torch.linalg.vector_norm(coordinates[0], dim=-1).item() == radius
    assert math.dist(point, center) > radius
    assert installed._inside_declared_pocket(coordinates, center, radius)
    assert not installed._inside_declared_pocket(coordinates, center, radius - 1e-15)


def test_pose_report_binding_survives_canonical_request_key_order(tmp_path):
    protocol = _installed_protocol(tmp_path / "inputs")
    ref = protocol["requests"]["a"]
    request_path = Path(ref["path"])
    request = json.loads(request_path.read_text())
    request["prepared_input"] = dict(reversed(list(request["prepared_input"].items())))
    request_path.write_text(json.dumps(request))
    ref["sha256"] = installed._digest(request_path.read_bytes())
    root = tmp_path / "run"
    result = installed.run(protocol, root)
    saved, binding = installed._envelope(root)
    assert _input_binding(saved["requests"]["a"]) != saved["source_inputs"]["a"]
    assert installed._summary(root, "engine", saved, binding) == result["arms"]["engine"]
    assert installed.verify_run(protocol, root)["status"] == "verified"
    assert installed.run(protocol, root, resume=True) == result
    report_path, _ = installed._report_ref(root, "engine", "a")
    report = installed._json(report_path.read_bytes())
    with pytest.raises(ValueError, match="installed_pose_report_request_mismatch"):
        installed._check_pose_report_request(
            report, saved["requests"]["a"],
            saved["source_inputs"]["a"] + [saved["source_inputs"]["a"][0]],
        )


def test_bound_input_change_blocks_read_only_verification_and_resume(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "input-drift"
    shutil.copytree(root / "run", copied)
    altered = copy.deepcopy(protocol)
    altered["source"]["rows"][0]["fit_value"] += 1.0
    before = (copied / "comparison.json").read_bytes()
    assert installed.verify_run(altered, copied)["reason"] == "installed_verify_input_or_runtime_changed"
    with pytest.raises(ValueError, match="installed_resume_input_or_runtime_changed"):
        installed.run(altered, copied, resume=True)
    assert (copied / "comparison.json").read_bytes() == before


def test_runtime_dependency_change_blocks_verification_and_resume(completed, tmp_path, monkeypatch):
    root, protocol, _ = completed
    copied = tmp_path / "runtime-drift"
    shutil.copytree(root / "run", copied)
    original = installed.importlib.metadata.version

    def changed(name):
        value = original(name)
        return value + ".drift" if name == "scikit-learn" else value

    monkeypatch.setattr(installed.importlib.metadata, "version", changed)
    assert installed.verify_run(protocol, copied)["reason"] == "installed_verify_input_or_runtime_changed"
    with pytest.raises(ValueError, match="installed_resume_input_or_runtime_changed"):
        installed.run(protocol, copied, resume=True)


def test_noncanonical_result_bytes_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "raw-tamper"
    shutil.copytree(root / "run", copied)
    with (copied / "comparison.json").open("ab") as stream:
        stream.write(b" ")
    assert installed.verify_run(protocol, copied)["reason"] == "noncanonical_installed_receipt"


def test_resealed_authority_claim_rejected(completed, tmp_path):
    root, protocol, _ = completed
    copied = tmp_path / "authority"
    shutil.copytree(root / "run", copied)
    result_path = copied / "comparison.json"
    result = json.loads(result_path.read_text())
    result["scientifically_validated"] = True
    result_path.write_bytes(installed._canonical(result) + b"\n")
    assert installed.verify_run(protocol, copied)["reason"] == "invalid_installed_result_header"
    with pytest.raises(ValueError, match="invalid_installed_result_header"):
        installed.run(protocol, copied, resume=True)


def test_orphaned_attempt_forfeits_original_budget_without_replaying(tmp_path):
    protocol = _installed_protocol(tmp_path / "inputs")
    protocol["arm_order"] = list(installed.ARMS)
    frozen = installed.freeze(protocol)
    binding = installed._sha(frozen)
    root = tmp_path / "orphan"
    root.mkdir(mode=0o700)
    lock = installed._lock(root / "run.lock", create=True)
    installed.os.close(lock)
    installed._publish(root / "frozen.json", {"payload": frozen, "sha256": binding})
    arm = root / "similarity"
    arm.mkdir(mode=0o700)
    started = time.monotonic()
    installed._publish(arm / "attempt.json", {
        "binding": binding, "started_monotonic": started,
        "deadline": started + 20.0})
    lease = installed._lock(arm / "worker.lock", create=True)
    installed.os.close(lease)
    result = installed.run(protocol, root, resume=True)
    lost = result["arms"]["similarity"]
    assert lost["completion"]["status"] == "interrupted_budget_forfeited"
    assert lost["denominator"] == {"requested": 4, "not_processed": 4}
    assert lost["priority"] is None
    assert installed.verify_run(protocol, root)["status"] == "verified"
    assert installed.run(protocol, root, resume=True) == result


def test_actual_timeout_retains_denominator_and_cannot_retry(tmp_path):
    protocol = _installed_protocol(tmp_path / "inputs")
    protocol["budget_seconds_per_arm"] = 0.001
    root = tmp_path / "timed-out"
    result = installed.run(protocol, root)
    assert all(result["arms"][arm]["completion"]["status"] == "budget_exhausted"
               for arm in installed.ARMS)
    assert all(result["arms"][arm]["denominator"] == {
        "requested": 4, "not_processed": 4} for arm in installed.ARMS)
    assert installed.verify_run(protocol, root)["status"] == "verified"
    assert installed.run(protocol, root, resume=True) == result


def test_legacy_schema_does_not_create_installed_run(tmp_path):
    old = _protocol(tmp_path / "inputs")
    destination = tmp_path / "not-created"
    with pytest.raises(ValueError, match="unsupported_installed_comparison_protocol"):
        installed.run(old, destination)
    assert not destination.exists()
