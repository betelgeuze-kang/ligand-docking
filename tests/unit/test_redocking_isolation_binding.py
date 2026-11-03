"""Synthetic binding/denominator tests; no molecular or evaluator execution."""
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools import run_redocking_isolated_development as run
from tools.redocking_isolation import IsolationError, atomic_json, digest_file, digest_json


def signed(value):
    return {**value, "receipt_sha256": digest_json(value)}


@pytest.fixture
def bundle(tmp_path):
    m = run.read_json(run.ROOT / "config/redocking_p0_p1_20261104.json")
    cid, index = m["case_ids"][0], 0
    common, destination = tmp_path / "materialization", tmp_path / "engine"
    directory = common / "inputs" / cid
    directory.mkdir(parents=True)
    inputs = {}
    for role, filename in run.ROLES.items():
        # Deliberately not chemical input; these tests validate bytes only.
        payload = ("synthetic bytes: " + role).encode()
        (directory / f"{cid}_{filename}").write_bytes(payload)
        inputs[role] = hashlib.sha256(payload).hexdigest()
    mat = signed({"case_id": cid, "frozen_case_seed": m["seed_base"],
        "source_archive_sha256": m["inputs"]["archive"]["sha256"], "hash_verified_archive": True,
        "archive_members": {f: f"posebusters_benchmark_set/{cid}/{cid}_{f}" for f in run.ROLES.values()},
        "artifact_sha256s": {f: inputs[role] for role, f in run.ROLES.items()}})
    atomic_json(common / "materialization.json", mat)
    source = {"commit": "a" * 40, "tree": "b" * 40, "manifest_sha256": "c" * 64}
    preflight = {"status": "ready", "source": source, "case_id": cid, "engine_id": "engine_v2", "profile": "legacy_v7",
        "seed": m["seed_base"], "input_sha256s": inputs,
        "materialization_receipt_sha256": mat["receipt_sha256"], "evaluation_pipeline_sha256": "d" * 64,
        "execution_environment_sha256": "e" * 64, "engine_source_sha256": "f" * 64}
    command = ["synthetic", "--seed", str(m["seed_base"]), "--cpu", "1", "--candidate-count", "64",
               "--scorer-backend", "python_reference", "--out", str(destination / "poses" / "engine_v2" / (cid + ".sdf"))]
    row = {"case_id": cid, "engine_id": "engine_v2", "status": "failure", "failure_code": "unsupported_fixture",
        "runtime_seconds": 0.25, "execution_command": command,
        "rmsd_angstroms": [], "geometric_valid": [], "chemical_valid": [], "pose_artifact_sha256s": [],
        "engine_v2_diagnostics": {"candidate_budget": 64, "preparation_status": "failure",
            "preparation_failure_code": "unsupported_fixture", "candidates": []},
        **{role + "_artifact_sha256": value for role, value in inputs.items()}}
    payload = {"schema_id": "betelgeuze.engine_v2_public_redocking_case_execution/1.1.0",
        "runner_id": "betelgeuze.engine_v2_public_redocking_300_runner/2.13.0",
        "materialization_receipt_sha256": mat["receipt_sha256"],
        "archive_sha256": m["inputs"]["archive"]["sha256"],
        "source_ids_sha256": m["inputs"]["source_identifiers"]["sha256"], "input_sha256s": inputs,
        "evaluation_pipeline_sha256": preflight["evaluation_pipeline_sha256"],
        "execution_environment_sha256": preflight["execution_environment_sha256"],
        "implementation_sha256": preflight["engine_source_sha256"], "fresh_execution": True,
        "cache_read_allowed": False, "command": command, "result": row}
    atomic_json(destination / "preflight.json", preflight)
    atomic_json(destination / "receipt.json", signed(payload))
    return SimpleNamespace(m=m, cid=cid, index=index, common=common, destination=destination,
                           source=source, preflight=preflight, payload=payload, mat=mat)


def observe(b):
    return run.observe_science(b.destination, b.common, b.cid, b.index, "engine_v2", b.m, b.source,
                               profile="legacy_v7")


def test_typed_failure_is_observed_but_missing_receipt_is_not(bundle):
    assert observe(bundle)["row"]["failure_code"] == "unsupported_fixture"
    (bundle.destination / "receipt.json").unlink()
    result = observe(bundle)
    assert result["observation_status"] == "unobserved" and result["row"] is None
    assert result["receipt_sha256"] is None


@pytest.mark.parametrize("field,value", [("profile", "development_observation_v1"), ("seed", 999),
    ("materialization_receipt_sha256", "1" * 64)])
def test_worker_preflight_cannot_be_rebound(bundle, field, value):
    bundle.preflight[field] = value
    atomic_json(bundle.destination / "preflight.json", bundle.preflight)
    with pytest.raises(IsolationError, match="preflight mismatch"):
        observe(bundle)


@pytest.mark.parametrize("field", ["evaluation_pipeline_sha256", "execution_environment_sha256"])
def test_valid_self_hash_does_not_allow_other_worker_evaluator(bundle, field):
    bundle.payload[field] = "0" * 64
    atomic_json(bundle.destination / "receipt.json", signed(bundle.payload))
    with pytest.raises(IsolationError, match="evaluator/environment mismatch"):
        observe(bundle)


def test_materialized_role_bytes_cannot_be_swapped(bundle):
    path = bundle.common / "inputs" / bundle.cid / f"{bundle.cid}_ligand.sdf"
    path.write_bytes(b"another input, while immutable materialization receipt is unchanged")
    with pytest.raises(IsolationError, match="materialized input changed"):
        observe(bundle)


def test_request_digest_rejects_partial_record_before_runner_import(tmp_path):
    path = tmp_path / "request.json"
    path.write_bytes(b'{"incomplete":')
    with pytest.raises(IsolationError, match="request bytes changed"):
        run.worker(path, "0" * 64)


def test_controller_preserves_timeout_and_continues_external_engines(bundle, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run, "source_identity", lambda _: bundle.source)
    monkeypatch.setattr(run, "common_inputs", lambda *args: (bundle.mat, {}))
    def task(request, manifest):
        name = request["task"]
        calls.append(name)
        return {"operation_status": "timeout" if name == "engine_v2" else "completed",
            "fatal_cleanup_failure": False, "errors": [], "execution": {"cleanup_complete": True},
            "last_checkpoint": {"last_event": {"stage": "search", "phase": "start"}},
            "worker_status": {"materialization_receipt_sha256": bundle.mat["receipt_sha256"]}}
    monkeypatch.setattr(run, "run_task", task)
    def science(destination, common, cid, index, engine, manifest, source, *, profile):
        if engine == "engine_v2":
            return {"observation_status": "unobserved", "row": None, "receipt_sha256": None}
        row = deepcopy(bundle.payload["result"])
        row["engine_id"], row["engine_v2_diagnostics"] = engine, None
        if engine == "gnina":
            row.update(status="success", failure_code="", rmsd_angstroms=[1., 5., 5., 5., 5.],
                geometric_valid=[False, True, True, True, True], chemical_valid=[True]*5)
        return {"observation_status": "observed", "row": row, "receipt_sha256": "f"*64}
    monkeypatch.setattr(run, "observe_science", science)
    args = SimpleNamespace(manifest=run.ROOT / "config/redocking_p0_p1_20261104.json",
        input_root=tmp_path / "unused-input", output_root=tmp_path / "controller",
        profile="legacy_v7", stage="smoke", start=0, count=1, preflight=None)
    assert run.run(args) == 2
    assert calls == ["materialize", "engine_v2", "vina", "gnina"]
    summary = run.read_json(args.output_root / "summary.json")
    engines = summary["cases"][0]["engines"]
    assert engines["engine_v2"]["operation_status"] == "timeout"
    assert engines["engine_v2"]["row"] is None
    assert engines["engine_v2"]["last_checkpoint"]["last_event"]["stage"] == "search"
    assert summary["metrics"]["engine_v2"]["unobserved_rows"] == 1
    assert summary["metrics"]["vina"]["failure_rows"] == 1
    assert summary["metrics"]["gnina"]["top1"] == 1
    assert summary["metrics"]["gnina"]["valid_top5"] == 0  # same-pose conjunction
    assert not summary["scientific_accuracy_complete"] and not summary["execution_complete"]
    assert not run.read_json(args.output_root / "stage-status.json")["next_stage_ready"]


def test_cleanup_failure_preserves_full_denominator_and_blocks_next_engine(bundle, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run, "source_identity", lambda _: bundle.source)
    monkeypatch.setattr(run, "common_inputs", lambda *args: (bundle.mat, {}))
    def task(request, manifest):
        name = request["task"]
        calls.append(name)
        return {"operation_status": "cleanup_failed" if name == "engine_v2" else "completed",
            "fatal_cleanup_failure": name == "engine_v2", "errors": [],
            "execution": {"cleanup_complete": name != "engine_v2"},
            "worker_status": {"materialization_receipt_sha256": bundle.mat["receipt_sha256"]}}
    monkeypatch.setattr(run, "run_task", task)
    args = SimpleNamespace(manifest=run.ROOT / "config/redocking_p0_p1_20261104.json",
        input_root=tmp_path / "unused-input", output_root=tmp_path / "controller",
        profile="legacy_v7", stage="smoke", start=0, count=2, preflight=None)
    assert run.run(args) == 1
    assert calls == ["materialize", "engine_v2"]
    summary = run.read_json(args.output_root / "summary.json")
    assert summary["expected_indices"] == [0, 1] and summary["attempted_cases"] == 1
    assert all(m["case_count"] == m["unobserved_rows"] == 2 for m in summary["metrics"].values())
    assert summary["cases"][0]["engines"]["vina"]["operation_status"] == "not_started"
    assert summary["fatal_error"] and not summary["scientific_accuracy_complete"]


@pytest.mark.parametrize("field", [None, "status", "commit", "manifest_sha256", "evaluation_pipeline_sha256",
    "engine_source_sha256", "evaluator_versions", "evaluator_payload_sha256s", "file_bytes"])
def test_job_preflight_binds_ready_source_and_actual_worker_environment(bundle, tmp_path, field):
    worker = {**bundle.preflight, "evaluator_versions": {"synthetic-evaluator": "1"},
              "evaluator_payload_sha256s": {"synthetic-evaluator": "7"*64}}
    keys = ("evaluation_pipeline_sha256", "engine_source_sha256", "evaluator_versions", "evaluator_payload_sha256s")
    job = {"status": "ready", "commit": bundle.source["commit"],
        "manifest_sha256": bundle.source["manifest_sha256"], **{k: worker[k] for k in keys}}
    if field is not None and field != "file_bytes":
        job[field] = "unexpected"
    path = tmp_path / "job-preflight.json"
    atomic_json(path, job)
    request = {"source": bundle.source, "job_preflight": {"path": str(path), "sha256": digest_file(path)}}
    if field == "file_bytes":
        path.write_bytes(path.read_bytes() + b" ")
    if field is None:
        result = run.validate_job_preflight(request, worker)
        assert result["status"] == "verified" and result["worker_environment_compared"] is True
    else:
        with pytest.raises(IsolationError, match="preflight"):
            run.validate_job_preflight(request, worker)


def test_optional_job_preflight_does_not_invent_environment_binding(bundle):
    assert run.validate_job_preflight({"source": bundle.source}, bundle.preflight) is None


def test_receipt_output_cannot_be_rebound_with_recomputed_canonical_hash(bundle):
    bundle.payload["command"][-1] = "/different/worker.sdf"
    atomic_json(bundle.destination / "receipt.json", signed(bundle.payload))
    with pytest.raises(IsolationError, match="output path changed"):
        observe(bundle)
