"""Synthetic-only registered D3 policy boundary and retained evidence tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json, canonical_system_json_bytes,
)
from betelgeuze_product.cpu_refinement_v1_2 import registered_policy_adapter as adapter
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import request_binding
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    FIXED_REQUEST_SCHEMA, FixedReceptorEnvironment, ReferencePhysicsApplicabilityError,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest
from betelgeuze_product.cpu_refinement_v1_2.refinement import ExtendedRefiner
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import (
    EXPLICIT_MODEL, EXPLICIT_REQUEST_SCHEMA, EXPLICIT_REPORT_SCHEMA, LEGACY_MODEL,
    REGISTERED_PROPOSAL_POLICY, REGISTERED_REPORT_SCHEMA, descriptor,
)
from tests.unit.test_cpu_registered_pose_workflow import request_fixture


def _rehash(report):
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})


def _no_physics(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("input binding or saved-evidence verification executed physics/scoring")
    monkeypatch.setattr(adapter, "run_comparison", forbidden)
    monkeypatch.setattr(ExtendedEvaluator, "evaluate", forbidden)
    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", forbidden)
    monkeypatch.setattr(ExtendedRefiner, "refine", forbidden)
    for method in ("score", "score_terms", "score_batch", "score_terms_batch"):
        monkeypatch.setattr(ChemistryPoseScorerV1, method, forbidden)


@pytest.fixture(scope="module")
def actual(tmp_path_factory):
    root = tmp_path_factory.mktemp("registered-policy-adapter")
    request, ligand = request_fixture(root, strained=True)
    return request, ligand, adapter.evaluate(request)


def test_input_binding_has_no_physics_and_preserves_original_coordinates(tmp_path, monkeypatch):
    request, ligand = request_fixture(tmp_path)
    _no_physics(monkeypatch)
    binding = adapter.input_binding(request)
    assert binding["backend"] == adapter.BACKEND
    assert binding["request_sha256"] == digest(request)
    assert binding["proposal_policy"]["initial_coordinates_binary64_hex"] == coordinates_hex(ligand.coordinates[0])
    assert binding["proposal_policy"]["policy_id"] == REGISTERED_PROPOSAL_POLICY
    assert binding["scorer"]["feature_model_id"] == EXPLICIT_MODEL
    assert binding["score_descriptor"] == descriptor(EXPLICIT_MODEL).to_dict()
    assert binding["score_quantity"] == adapter.SCORE_QUANTITY
    assert binding["evaluator"]["parameter_fingerprint_sha256"] == binding["parameters_sha256"]
    assert not binding["candidate_source_admission_verified"]
    assert not binding["scientifically_validated"]


@pytest.mark.parametrize("schema", [FIXED_REQUEST_SCHEMA, EXPLICIT_REQUEST_SCHEMA,
                                    "cpu_extended_comparison_request/1.2.0"])
def test_nonregistered_request_rejected_before_execution(tmp_path, monkeypatch, schema):
    request, _ = request_fixture(tmp_path)
    request["schema_id"] = schema
    _no_physics(monkeypatch)
    for operation in (adapter.input_binding, adapter.evaluate):
        with pytest.raises(ResearchError, match="requires_registered"):
            operation(request)


@pytest.mark.parametrize("change", [
    {"candidate_count": 2}, {"top_k": 2}, {"max_torsions": 1},
    {"translation_radius_angstrom": .25},
])
def test_registered_policy_rejects_placement_or_multiple_candidates(tmp_path, monkeypatch, change):
    request, _ = request_fixture(tmp_path)
    request["budget"].update(change)
    _no_physics(monkeypatch)
    # Invalid top_k is rejected by the underlying DockingBudget before the
    # registered-specific validator; both validators expose ValueError.
    with pytest.raises(ValueError):
        adapter.input_binding(request)


def test_actual_selected_baseline_is_not_replaced_by_nonconverged_endpoint(actual):
    request, ligand, result = actual
    summary = adapter.summarize(result, request)
    report = result["comparison"]
    assert set(result) == {"schema_version", "backend", "request", "comparison"}
    assert result["schema_version"] == adapter.RESULT_SCHEMA
    assert report["schema_id"] == REGISTERED_REPORT_SCHEMA
    assert report["scorer"]["feature_model_id"] == EXPLICIT_MODEL
    attempt, = report["attempts"]
    assert attempt["status"] == "success" and not attempt["converged"]
    assert attempt["final_energy"] < attempt["initial_energy"]
    assert report["paired_decisions"][0]["reason"] == "refinement_not_converged"
    selected, = summary["selected_candidates"]
    assert selected["variant"] == "baseline"
    assert selected["coordinates_binary64_hex"] == coordinates_hex(ligand.coordinates[0])
    assert selected["coordinates_binary64_hex"] != attempt["post_coordinates_binary64_hex"]
    assert summary["score"] == selected["score"] == report["arms"]["baseline"]["rows"][0]["score"]
    assert summary["original_selected_count"] == 1
    assert summary["refined_selected_count"] == summary["refinement_converged"] == 0
    assert summary["work"]["score_evaluation_calls"] == 2
    assert summary["work"]["actual_force_evaluation_calls"] > 0
    assert summary["work"]["failed_force_evaluation_calls"] == 0
    assert summary["work"]["pose_candidates_in_both_arms"] == 2
    assert not summary["physical_affinity_computed"]
    assert not summary["candidate_source_admission_verified"]
    assert not summary["scientifically_validated"]


def test_saved_summary_never_reexecutes_physics(actual, monkeypatch):
    request, _, result = actual
    expected = adapter.summarize(result, request=request)
    _no_physics(monkeypatch)
    assert adapter.summarize(result, request=request) == expected


@pytest.mark.parametrize("change", ["schema", "model", "descriptor", "recenter"])
def test_resealed_report_profile_or_pose_substitution_is_rejected(actual, change):
    request, _, result = actual
    forged = deepcopy(result)
    report = forged["comparison"]
    if change == "schema":
        report["schema_id"] = EXPLICIT_REPORT_SCHEMA
        report.pop("proposal_policy")
    elif change == "model":
        report["scorer"]["feature_model_id"] = LEGACY_MODEL
    elif change == "descriptor":
        report["per_arm_selection"]["baseline"]["score_descriptor"] = descriptor(LEGACY_MODEL).to_dict()
    else:
        policy = report["proposal_policy"]
        xyz = policy["initial_coordinates_binary64_hex"]
        xyz[0][0] = (float.fromhex(xyz[0][0]) - 2.5).hex()
        policy["receipt_sha256"] = digest({k: v for k, v in policy.items() if k != "receipt_sha256"})
    _rehash(report)
    with pytest.raises(ResearchError):
        adapter.summarize(forged, request=request)


def test_request_substitution_is_rejected_even_when_report_binding_is_resealed(actual):
    request, _, result = actual
    forged = deepcopy(result)
    forged["request"]["pocket"]["radius_angstrom"] += .25
    forged["comparison"]["request_binding"] = request_binding(forged["request"])
    _rehash(forged["comparison"])
    with pytest.raises(ResearchError, match="request_mismatch"):
        adapter.summarize(forged, request=request)
    # With no external request, rederive the live authority instead of accepting
    # an internally consistent old report relabeled with a different pocket.
    with pytest.raises(ResearchError, match="request/report"):
        adapter.summarize(forged)


@pytest.mark.parametrize("change", ["coordinates", "parameters"])
def test_resealed_input_file_cannot_reuse_an_old_report(actual, tmp_path, change):
    _, _, result = actual
    forged = deepcopy(result)
    request = forged["request"]
    if change == "coordinates":
        system = all_atom_system_from_canonical_json(Path(request["ligand"]["path"]).read_bytes())
        system = system.with_coordinates(system.coordinates + .125, operation="synthetic_translation")
        raw = canonical_system_json_bytes(system)
        field = "ligand"
    else:
        document = json.loads(Path(request["extensions"]["path"]).read_bytes())
        document["metadata"] = {**document["metadata"], "synthetic_changed_declaration": True}
        raw = json.dumps(document).encode()
        field = "extensions"
    path = tmp_path / (field + ".json")
    path.write_bytes(raw)
    request[field] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    forged["comparison"]["request_binding"] = request_binding(request)
    _rehash(forged["comparison"])
    with pytest.raises(ResearchError):
        adapter.summarize(forged)


def test_failed_force_preserves_baseline_and_failed_call_count(tmp_path, monkeypatch):
    request, ligand = request_fixture(tmp_path)
    def fail(*args, **kwargs):
        raise ReferencePhysicsApplicabilityError("synthetic force failure")
    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", fail)
    result = adapter.evaluate(request)
    summary = adapter.summarize(result, request=request)
    assert summary["status"] == "evaluated"
    assert summary["refinement_failures"] == 1
    assert summary["original_selected_count"] == 1
    assert summary["refined_selected_count"] == 0
    assert summary["work"]["failed_force_evaluation_calls"] == 1
    assert summary["selected_candidates"][0]["coordinates_binary64_hex"] == coordinates_hex(ligand.coordinates[0])
