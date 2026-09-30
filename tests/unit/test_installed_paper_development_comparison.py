"""Synthetic representation/CPU orchestration only; no experimental values."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from betelgeuze_product import installed_paper_development_comparison as paper
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
from betelgeuze_product.cpu_refinement_v1_3 import minimization, workflow
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json, canonical_system_json_bytes
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from tests.unit.test_installed_native_v4_registered_binding import _fixture, _write


def _protocol(directory, *, missing=False, attempts=2, accepted=1, strained=False):
    directory.mkdir(parents=True, exist_ok=True)
    article = _write(directory / "article.bin", b"synthetic retained public paper bytes")
    initial = _write(directory / "initial-protocol.json", {"synthetic_initial_registered_geometry": True})
    model = _write(directory / "declared-model.json", {"synthetic_unconstrained_computational_model": True})
    candidates = []
    for index, compound in enumerate(("PR49", "PR59")):
        child = directory / compound
        child.mkdir()
        identity_row, original, charge, ligand = _fixture(child)
        if strained:
            xyz = ligand.coordinates.clone()
            xyz[0, 1, 0] += .08
            ligand = ligand.with_coordinates(xyz, operation="synthetic_test_coordinate_change")
            original["ligand"] = _write(Path(original["ligand"]["path"]), canonical_system_json_bytes(ligand))
            charge = _mutate(charge, lambda value: value.update(ligand_source_sha256=original["ligand"]["sha256"],
                                                               ligand_system_sha256=canonical_system_sha256(ligand)))
        identity = {"schema_version": paper.IDENTITY, "doi": "10.1234/synthetic", "local_compound_id": compound,
                    "occurrence_id": "table4:" + compound, "chemical_identity": identity_row["chemical_identity"],
                    "source_evidence": article}
        identity_ref = _write(child / "identity.json", identity)
        source = {k: identity[k] for k in ("doi", "local_compound_id", "occurrence_id", "chemical_identity")}
        source.update(schema_version=paper.SOURCE, target=deepcopy(paper.TARGET), boundary=deepcopy(paper.BOUNDARY),
                      evidence={"article": article, "identity_statement": identity_ref},
                      method={"local_method_id": "section_3.2.2", "endpoint_context": "reported_human_5ht6_radioligand_binding_Ki",
                              "physical_pages": [39, 40], "evidence": article})
        source_ref = _write(child / "source.json", source)
        request_ref = _write(child / "request.json", original)
        evidence = paper.derive_prepared_evidence(source_ref, request_ref, charge, initial_pose_protocol=initial,
                                                declared_model_evidence=model)
        candidates.append({"candidate_id": paper.candidate_id(source), "source": source_ref,
                           "original_request": request_ref, "prepared_evidence": _write(child / "prepared-evidence.json", evidence)})
        if missing and index == 1:
            candidates[-1].update(original_request=None, prepared_evidence=None)
    return {"schema_version": paper.PROTOCOL, "candidates": candidates,
            "cartesian_solver": SolverConfig(max_objective_attempts=attempts, max_accepted_steps=accepted,
                                              max_restart_verifications=1).to_dict()}


def _mutate(ref, change):
    path = Path(ref["path"])
    value = json.loads(path.read_bytes())
    change(value)
    return _write(path, value)


def _forbid(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("metadata admission or exact reuse performed molecular calls")
    monkeypatch.setattr(workflow, "evaluate", fail)
    monkeypatch.setattr(minimization, "minimize", fail)
    monkeypatch.setattr(ExplicitGraphScorer, "score_terms", fail)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, "evaluate", fail)


def test_preflight_preserves_null_roles_original_requests_and_missing_denominator(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path, missing=True)
    before = deepcopy(protocol)
    _forbid(monkeypatch)
    frozen = paper.freeze(protocol)
    assert protocol == before
    assert frozen["requested_candidate_count"] == 2
    assert frozen["prepared_candidate_count"] == 1
    assert frozen["boundary"] == paper.BOUNDARY
    assert frozen["evaluation_labels_read"] == 0
    original = json.loads(Path(protocol["candidates"][0]["original_request"]["path"]).read_bytes())
    assert frozen["candidates"][0]["original_request"] == original
    assert frozen["candidates"][0]["request"]["schema_id"] == workflow.REQUEST_SCHEMA
    assert "max_refinement_steps" not in frozen["candidates"][0]["request"]["budget"]
    assert frozen["candidates"][1]["blockers"] == ["paper_registered_preparation_missing"]


@pytest.mark.parametrize("change", ["role", "fit", "chembl", "outcome", "identity_candidate", "target"])
def test_source_forgery_and_outcome_fields_fail_before_execution(tmp_path, monkeypatch, change):
    protocol = _protocol(tmp_path)
    entry = protocol["candidates"][0]
    def alter(source):
        if change == "role":
            source["boundary"]["assigned_role"] = "fit"
        elif change == "fit":
            source["fit_value"] = 9.
        elif change == "chembl":
            source["assay_chembl_id"] = "CHEMBL123"
        elif change == "outcome":
            source["method"]["reported_ki_mean"] = "0.077"
        elif change == "target":
            source["target"]["physical_state_verified"] = True
        else:
            source["evidence"]["identity_statement"] = _mutate(source["evidence"]["identity_statement"],
                                                               lambda identity: identity.update(local_compound_id="PR59"))
    entry["source"] = _mutate(entry["source"], alter)
    _forbid(monkeypatch)
    with pytest.raises(ValueError):
        paper.run(protocol, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


@pytest.mark.parametrize("change", ["source_bytes", "coordinate", "candidate_swap", "cohort", "promotion"])
def test_preparation_changes_preserve_failed_candidate_denominator(tmp_path, monkeypatch, change):
    protocol = _protocol(tmp_path)
    first, second = protocol["candidates"]
    if change == "source_bytes":
        Path(first["prepared_evidence"]["path"]).write_bytes(b"{}")
    elif change == "coordinate":
        request = json.loads(Path(first["original_request"]["path"]).read_bytes())
        ligand = all_atom_system_from_canonical_json(Path(request["ligand"]["path"]).read_bytes())
        xyz = ligand.coordinates.clone()
        xyz[0, 0, 0] += .01
        request["ligand"] = _write(Path(request["ligand"]["path"]), canonical_system_json_bytes(ligand.with_coordinates(xyz, operation="synthetic_test_coordinate_change")))
        first["original_request"] = _write(Path(first["original_request"]["path"]), request)
    elif change == "candidate_swap":
        first["prepared_evidence"], second["prepared_evidence"] = second["prepared_evidence"], first["prepared_evidence"]
    elif change == "promotion":
        first["prepared_evidence"] = _mutate(first["prepared_evidence"], lambda evidence: evidence["boundary"].update(assigned_role="development_test"))
    else:
        evidence = json.loads(Path(second["prepared_evidence"]["path"]).read_bytes())
        changed = _write(tmp_path / "different-initial-protocol.json", {"different_initial_protocol": True})
        rebuilt = paper.derive_prepared_evidence(second["source"], second["original_request"], evidence["charge_origin"],
                                                initial_pose_protocol=changed, declared_model_evidence=evidence["declared_model_evidence"])
        second["prepared_evidence"] = _write(Path(second["prepared_evidence"]["path"]), rebuilt)
    _forbid(monkeypatch)
    frozen = paper.freeze(protocol)
    assert frozen["requested_candidate_count"] == 2
    assert frozen["prepared_candidate_count"] < 2
    if change == "cohort":
        assert frozen["prepared_candidate_count"] == 0
    else:
        assert frozen["candidates"][0]["blockers"]


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("paper-development-completed")
    protocol = _protocol(root / "input", missing=True)
    directory = root / "run"
    return protocol, directory, paper.run(protocol, directory)


def test_cpu_completion_retains_preparation_failure_and_separate_arm_selections(completed):
    protocol, directory, result = completed
    assert result["status"] == "complete"
    assert result["denominator"] == {"requested": 2, "completed": 1, "preparation_blocked": 1}
    assert result["independent_measurement_denominator"] is None
    assert result["boundary"] == paper.BOUNDARY
    done, missing = result["rows"]
    assert done["refinement_state"] in {"no_refinement", "converged", "rejected"}
    assert set(done["raw_per_arm_selection"]) == set(done["per_arm_selection"]) == {"baseline", "refined"}
    assert done["work"]["score_calls"] == 2
    assert missing["force_calls"] == missing["score_calls"] == 0
    assert paper.verify_run(protocol, directory)["status"] == "verified"


def test_completed_exact_reuse_never_scores_refines_or_rewrites(completed, monkeypatch):
    protocol, directory, result = completed
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    _forbid(monkeypatch)
    assert paper.run(protocol, directory, resume=True) == result
    assert paper.verify_run(protocol, directory)["execution_performed"] is False
    assert before == {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def test_partial_execution_failure_does_not_drop_or_zero_unknown_work(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path / "input")
    original = workflow.evaluate
    def fail_first(request, directory, **kwargs):
        if directory.name == paper._sha(protocol["candidates"][0]["candidate_id"]) + ".cartesian":
            raise RuntimeError("synthetic interrupted entrypoint")
        return original(request, directory, **kwargs)
    monkeypatch.setattr(workflow, "evaluate", fail_first)
    directory = tmp_path / "run"
    result = paper.run(protocol, directory)
    assert result["denominator"] == {"requested": 2, "interrupted_unknown": 1, "completed": 1}
    failed = result["rows"][0]
    assert failed["work"]["numerical_work"] is None
    assert failed["work"]["all_candidate_molecular_work_recorded"] is False
    _forbid(monkeypatch)
    resumed = paper.run(protocol, directory, resume=True)
    assert resumed["rows"][0]["work"] is None
    assert resumed["denominator"] == result["denominator"]


def test_cli_requires_explicit_protocol_pin(tmp_path, monkeypatch, capsys):
    protocol = _protocol(tmp_path / "input")
    ref = _write(tmp_path / "protocol.json", protocol)
    _forbid(monkeypatch)
    assert paper.main(["preflight", "--protocol", ref["path"], "--expected-protocol-sha256", ref["sha256"]]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requested_candidate_count"] == result["prepared_candidate_count"] == 2
    with pytest.raises(ValueError, match="hash_mismatch"):
        paper.main(["preflight", "--protocol", ref["path"], "--expected-protocol-sha256", "0" * 64])


def test_known_checkpoint_resume_reuses_baseline_and_scores_terminal_only_once(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path / "input", missing=True, strained=True, attempts=4, accepted=3)
    directory = tmp_path / "run"
    calls = {"score": 0}
    actual = ExplicitGraphScorer.score_terms
    def count(*args, **kwargs):
        calls["score"] += 1
        return actual(*args, **kwargs)
    monkeypatch.setattr(ExplicitGraphScorer, "score_terms", count)
    checkpoint = paper.run(protocol, directory, pause_after_objective_attempts=1)
    assert checkpoint["denominator"] == {"requested": 2, "checkpointed": 1, "preparation_blocked": 1}
    assert calls["score"] == 1
    result = paper.run(protocol, directory, resume=True)
    assert result["status"] == "complete"
    assert calls["score"] == 2
    done = result["rows"][0]
    assert done["refinement_state"] == "rejected"
    assert done["attempt"]["converged"] is False
    assert done["paired_decision"]["variant"] == "baseline"
    assert done["per_arm_selection"]["refined"]["selected_candidates"] == []
    assert done["registered_summary"]["workflow_invocation_work"]["score_work"]["new_score_calls"] == 1
    _forbid(monkeypatch)
    assert paper.run(protocol, directory, resume=True) == result


@pytest.mark.parametrize("damage", ["pending_score", "missing_invocation_end", "unknown_prior_force_calls"])
def test_unknown_child_work_never_reissues_force_or_score_calls(completed, tmp_path, monkeypatch, damage):
    protocol, original, _ = completed
    directory = tmp_path / "copy"
    shutil.copytree(original, directory)
    (directory / "result.json").unlink()
    child = paper._candidate_directory(directory, protocol["candidates"][0]["candidate_id"])
    end_path = child / "invocation-000000.end.json"
    if damage == "unknown_prior_force_calls":
        invocation = json.loads(end_path.read_bytes())
        invocation["new_force_calls"] = None
        end_path.write_bytes(paper._canonical(invocation) + b"\n")
    else:
        end_path.unlink()
    if damage == "pending_score":
        (child / "result.json").unlink()
        (child / "baseline-score.json").unlink()
    def fail(*args, **kwargs):
        pytest.fail("unknown child work attempted a repeated molecular call")
    monkeypatch.setattr(minimization, "minimize", fail)
    monkeypatch.setattr(ExplicitGraphScorer, "score_terms", fail)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, "evaluate", fail)
    result = paper.run(protocol, directory, resume=True)
    assert result["denominator"] == {"requested": 2, "interrupted_unknown": 1, "preparation_blocked": 1}
    assert result["rows"][0]["refinement_state"] == "unknown"
    if damage == "pending_score":
        assert result["rows"][0]["work"]["unknown_score_attempts"] == 1
