"""Registered input coordinates survive comparison, selection and restart.

Only synthetic water graphs are used. The fixture is translated away from the
pocket center so an accidental placement/recentering cannot pass unnoticed.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json, canonical_system_json_bytes,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, coordinates_hex, decode_coordinates, digest,
)
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request, verify_output
from betelgeuze_product.cpu_refinement_v1_2.resumable_workflow import (
    run_resumable_request, verify_resumable_output,
)
from betelgeuze_product.cpu_refinement_v1_2.resume_verification import verify_resume_summary
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from tests.unit.test_cpu_explicit_chemistry_workflow import request_fixture as chemistry_request


REQUEST_SCHEMA = "cpu_registered_pose_fixed_receptor_request/1.0.0"
REPORT_SCHEMA = "cpu_registered_pose_fixed_receptor_comparison/1.0.0"
PLAN_SCHEMA = "cpu_registered_pose_candidate_comparison_plan/1.0.0"
POLICY_ID = "registered_input_single_pose/1.0.0"


def _write_ref(path, raw):
    path.write_bytes(raw)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def request_fixture(directory, *, strained=False):
    request = chemistry_request(directory)
    translation = torch.tensor([2.5, -1.75, 1.25], dtype=torch.float64)
    systems = {}
    for name in ("receptor", "ligand"):
        system = all_atom_system_from_canonical_json(Path(request[name]["path"]).read_bytes())
        xyz = system.coordinates + translation
        if name == "ligand" and strained:
            xyz[0, 1, 0] += .08
        systems[name] = system.with_coordinates(xyz, operation="synthetic_registered_translation")
        request[name] = _write_ref(directory / (name + "-registered.json"),
                                   canonical_system_json_bytes(systems[name]))
    cross = json.loads(Path(request["cross_parameters"]["path"]).read_bytes())
    cross["receptor_system_sha256"] = canonical_system_sha256(systems["receptor"])
    request["cross_parameters"] = _write_ref(directory / "cross-registered.json",
                                             json.dumps(cross).encode())
    request["schema_id"] = REQUEST_SCHEMA
    request["budget"].update(candidate_count=1, top_k=1, max_torsions=0,
                              translation_radius_angstrom=0., max_refinement_steps=1)
    request["selection"]["top_k"] = 1
    assert request["comparison"]["mode"] == "same_candidates"
    assert request["comparison"]["require_convergence_for_selection"] is True
    # Source coordinates and the fixed environment are translated together;
    # declared force parameters, convergence/strain limits and pocket remain.
    return request, systems["ligand"]


@pytest.fixture(scope="module")
def registered_run(tmp_path_factory):
    directory = tmp_path_factory.mktemp("registered-pose-workflow")
    request, ligand = request_fixture(directory)
    full = run_request(request, directory / "full")["result"]
    paused = run_resumable_request(request, directory / "split", stop_after=1)
    assert paused["execution_complete"] is False
    assert paused["committed_candidates"] == 1
    run_resumable_request(request, directory / "split", resume=True)
    summary = json.loads((directory / "split/report.json").read_bytes())["summary"]
    return directory, request, ligand, full, summary


def test_registered_input_is_never_recentered_and_restart_preserves_every_row(registered_run):
    directory, request, ligand, report, summary = registered_run
    expected_xyz = ligand.coordinates[0]
    expected_hex = coordinates_hex(expected_xyz)
    expected_digest = coordinate_fingerprint(expected_xyz)
    assert not torch.allclose(expected_xyz.mean(0), torch.tensor(
        request["pocket"]["center_angstrom"], dtype=torch.float64))
    assert report["schema_id"] == REPORT_SCHEMA
    assert summary["plan"]["schema_id"] == PLAN_SCHEMA
    policy = report["proposal_policy"]
    assert policy["policy_id"] == POLICY_ID
    assert policy["initial_coordinates_binary64_hex"] == expected_hex
    assert policy["initial_coordinate_fingerprint_sha256"] == expected_digest
    assert policy["source_ligand_system_sha256"] == canonical_system_sha256(ligand)
    assert policy == summary["plan"]["proposal_policy"]
    baseline = report["arms"]["baseline"]["rows"][0]
    assert baseline["succeeded"] and baseline["selection_eligible"]
    assert baseline["coordinates_binary64_hex"] == expected_hex
    assert baseline["coordinates_sha256"] == expected_digest
    assert baseline["proposal_fingerprint_sha256"] == policy["proposal_fingerprint_sha256"]
    assert report["attempts"][0]["pre_coordinates_binary64_hex"] == expected_hex
    assert report["attempts"][0]["pre_coordinates_sha256"] == expected_digest
    for arm in ("baseline", "refined"):
        assert report["arms"][arm]["candidate_count"] == 1
        assert summary["rows"][arm] == report["arms"][arm]["rows"]
    assert summary["attempts"] == report["attempts"]
    assert summary["plan"]["scorer"] == report["scorer"]
    assert summary["paired_decisions"] == report["paired_decisions"]
    assert summary["costs"]["baseline"]["reused_candidates"] == 1
    assert summary["costs"]["baseline"]["new_candidates"] == 0
    assert summary["costs"]["refined"]["new_candidates"] == 1
    assert verify_output(directory / "full")["structural_verification_passed"]
    assert verify_resumable_output(directory / "split")["structural_verification_passed"]


def test_valid_registered_baseline_is_preserved_when_refinement_does_not_converge(tmp_path):
    request, ligand = request_fixture(tmp_path, strained=True)
    original_solver = deepcopy(request["solver"])
    original_cross = json.loads(Path(request["cross_parameters"]["path"]).read_bytes())
    report = run_request(request, tmp_path / "run")["result"]
    assert report["solver"] == original_solver
    assert report["cross_parameters"] == original_cross
    assert report["comparison"]["require_convergence_for_selection"] is True
    attempt = report["attempts"][0]
    assert attempt["status"] == "success" and not attempt["converged"]
    assert attempt["final_energy"] < attempt["initial_energy"]
    assert report["arms"]["refined"]["rows"][0]["succeeded"]
    assert report["paired_decisions"] == [{"candidate_id": report["arms"]["baseline"]["rows"][0]["candidate_id"],
                                            "variant": "baseline", "reason": "refinement_not_converged"}]
    selected, = report["final_selection"]["selected_candidates"]
    assert selected["variant"] == "baseline"
    assert selected["coordinates_binary64_hex"] == coordinates_hex(ligand.coordinates[0])
    assert report["per_arm_selection"]["refined"]["selected_candidates"] == []


def _rehash(document, field):
    document[field] = digest({k: v for k, v in document.items() if k != field})


POLICY_MUTATIONS = ("policy", "receipt_schema", "source_ligand", "initial_coordinates",
                    "initial_coordinate_fingerprint", "receipt_digest")


def _mutate_policy(policy, mutation):
    if mutation == "policy":
        policy["policy_id"] = "pocket_centered_placement/1.0.0"
    elif mutation == "receipt_schema":
        policy["schema_id"] = "cpu_registered_input_single_pose_receipt/999.0.0"
    elif mutation == "source_ligand":
        policy["source_ligand_system_sha256"] = "0" * 64
    elif mutation == "initial_coordinates":
        rows = policy["initial_coordinates_binary64_hex"]
        rows[0][0] = (float.fromhex(rows[0][0]) + .125).hex()
        policy["initial_coordinate_fingerprint_sha256"] = coordinate_fingerprint(decode_coordinates(rows, len(rows))[0])
    elif mutation == "initial_coordinate_fingerprint":
        policy["initial_coordinate_fingerprint_sha256"] = "0" * 64
    elif mutation == "receipt_digest":
        policy["receipt_sha256"] = "0" * 64
        return
    else:
        raise AssertionError(mutation)
    _rehash(policy, "receipt_sha256")


@pytest.mark.parametrize("mutation", POLICY_MUTATIONS)
def test_rehashed_registered_report_policy_contradictions_reject(registered_run, mutation):
    forged = deepcopy(registered_run[3])
    _mutate_policy(forged["proposal_policy"], mutation)
    _rehash(forged, "report_sha256")
    with pytest.raises(ResearchError):
        verify_report(forged)


@pytest.mark.parametrize("mutation", POLICY_MUTATIONS)
def test_rehashed_registered_resume_policy_contradictions_reject(registered_run, mutation):
    forged = deepcopy(registered_run[4])
    _mutate_policy(forged["plan"]["proposal_policy"], mutation)
    forged["plan_sha256"] = digest(forged["plan"])
    _rehash(forged, "summary_sha256")
    with pytest.raises(ResearchError):
        verify_resume_summary(forged)


def _shift_attempt_pre(attempt):
    xyz = decode_coordinates(attempt["pre_coordinates_binary64_hex"], 3)[0]
    xyz = xyz + .125
    attempt["pre_coordinates_binary64_hex"] = coordinates_hex(xyz)
    attempt["pre_coordinates_sha256"] = coordinate_fingerprint(xyz)
    if attempt["status"] == "success":
        final = decode_coordinates(attempt["post_coordinates_binary64_hex"], 3)[0]
        attempt["maximum_displacement_angstrom"] = float(torch.linalg.vector_norm(final - xyz, dim=-1).max())
    _rehash(attempt, "receipt_sha256")


def test_rehashed_refiner_pre_coordinates_cannot_replace_registered_pose(registered_run):
    report = deepcopy(registered_run[3])
    _shift_attempt_pre(report["attempts"][0])
    _rehash(report, "report_sha256")
    with pytest.raises(ResearchError):
        verify_report(report)
    summary = deepcopy(registered_run[4])
    _shift_attempt_pre(summary["attempts"][0])
    summary["records"]["refined"][0]["attempt"] = deepcopy(summary["attempts"][0])
    _rehash(summary, "summary_sha256")
    with pytest.raises(ResearchError):
        verify_resume_summary(summary)


def test_registered_report_and_plan_cannot_be_relabelled_as_guided_search(registered_run):
    report = deepcopy(registered_run[3])
    report["schema_id"] = "cpu_explicit_chemistry_fixed_receptor_comparison/1.0.0"
    _rehash(report, "report_sha256")
    with pytest.raises(ResearchError):
        verify_report(report)
    summary = deepcopy(registered_run[4])
    summary["plan"]["schema_id"] = "cpu_explicit_chemistry_candidate_comparison_plan/1.0.0"
    summary["plan_sha256"] = digest(summary["plan"])
    _rehash(summary, "summary_sha256")
    with pytest.raises(ResearchError):
        verify_resume_summary(summary)


def test_guided_request_cannot_resume_registered_candidate_journal(registered_run):
    directory, request, *_ = registered_run
    request = deepcopy(request)
    request["schema_id"] = "cpu_explicit_chemistry_fixed_receptor_request/1.0.0"
    with pytest.raises(ResearchError, match="resume request"):
        run_resumable_request(request, directory / "split", resume=True)


@pytest.mark.parametrize("mutation", ["count", "top_k", "torsions", "translation", "mode"])
@pytest.mark.parametrize("resumable", [False, True])
def test_unsupported_registered_request_is_rejected_before_output(tmp_path, mutation, resumable):
    request, _ = request_fixture(tmp_path)
    if mutation == "count":
        request["budget"]["candidate_count"] = 2
    elif mutation == "top_k":
        request["budget"]["top_k"] = 2
        request["selection"]["top_k"] = 2
    elif mutation == "torsions":
        request["budget"]["max_torsions"] = 1
    elif mutation == "translation":
        request["budget"]["translation_radius_angstrom"] = .1
    else:
        request["comparison"].update(mode="equal_work_budget", work_units_per_arm=100)
    output = tmp_path / "rejected"
    run = run_resumable_request if resumable else run_request
    with pytest.raises(ValueError):
        run(request, output)
    assert not output.exists()
