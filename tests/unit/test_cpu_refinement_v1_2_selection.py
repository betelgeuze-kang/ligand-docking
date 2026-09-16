"""Final Top-K invariants and real extended-refinement/rescoring integration."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
import torch

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_product.cpu_refinement_v1_2.comparison import run_comparison
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest
from betelgeuze_product.cpu_refinement_v1_2.selection import SelectionConfig, select_final_candidates
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters
from tests.unit.test_cpu_refinement_v1_2_physics import near_linear


def descriptor(direction=ScoreDirection.MINIMIZE):
    return DockingScoreDescriptor("test", direction, None, "synthetic", False)


def candidate(index, score, offset=0., variant="baseline"):
    xyz = torch.tensor([[offset, 0., 0.], [offset + 1., 0., 0.]], dtype=torch.float64)
    return {"candidate_id": f"pose-{index}", "proposal_index": index, "score": score,
            "coordinates_sha256": coordinate_fingerprint(xyz), "coordinates_binary64_hex": coordinates_hex(xyz),
            "proposal_fingerprint_sha256": f"{index+1:064x}", "result_proposal_fingerprint_sha256": f"{index+2:064x}",
            "selection_eligible": True, "pose_valid": True, "validity_complete": True, "variant": variant}


@pytest.mark.parametrize("direction,expected", [(ScoreDirection.MINIMIZE, [3, 1]), (ScoreDirection.MAXIMIZE, [2, 1])])
def test_ordering_direction_and_topk(direction, expected):
    rows = [candidate(1, 4., 1.), candidate(2, 9., 2., "refined"), candidate(3, 1., 3.)]
    selected = select_final_candidates(rows, descriptor(direction), SelectionConfig(2), 2)
    assert [row["proposal_index"] for row in selected["selected_candidates"]] == expected


def test_stable_tie_order_and_receptor_frame_diversity():
    rows = [candidate(2, 1., 5.), candidate(1, 1., 0.), candidate(3, 2., .1)]
    result = select_final_candidates(rows, descriptor(), SelectionConfig(3, .5), 2)
    assert [row["proposal_index"] for row in result["selected_candidates"]] == [1, 2]
    # Ligand-only alignment would collapse the translated pose; direct RMSD must not.
    assert result["decisions"][-1]["reason"] == "within_diversity_distance"


def test_exact_duplicates_removed_even_at_zero_threshold():
    result = select_final_candidates([candidate(1, 1.), candidate(2, 2.)], descriptor(), SelectionConfig(2, 0.), 2)
    assert len(result["selected_candidates"]) == 1
    assert result["decisions"][1]["reason"] == "duplicate_coordinates"


def test_empty_selection_has_no_fabricated_candidate():
    result = select_final_candidates([], descriptor(), SelectionConfig(3), 2)
    assert result["selected_candidates"] == []


@pytest.mark.parametrize("change", ["nan", "boolean", "coordinate", "invalid", "incomplete", "duplicate_id", "variant"])
def test_bad_candidates_rejected(change):
    row = candidate(1, 1.)
    rows = [row]
    if change == "nan":
        row["score"] = float("nan")
    elif change == "boolean":
        row["score"] = True
    elif change == "coordinate":
        row["coordinates_binary64_hex"][0][0] = (99.).hex()
    elif change == "invalid":
        row["pose_valid"] = False
    elif change == "incomplete":
        row["validity_complete"] = False
    elif change == "variant":
        row["variant"] = "unknown"
    else:
        rows.append(deepcopy(row))
    with pytest.raises(ResearchError):
        select_final_candidates(rows, descriptor(), SelectionConfig(2), 2)


def real_run(*, equal_budget=False, extended=False, solvated=False):
    if extended:
        ligand, parameters, solvent, solver = near_linear(charged=solvated)
        authority, receptor, ligand = _authority(ligand)
    else:
        authority, receptor, ligand = _authority()
        base = _parameters(ligand)
        base = replace(base, bonds=tuple(replace(row, equilibrium_angstrom=.9 * row.equilibrium_angstrom) for row in base.bonds))
        parameters = ReferenceForceFieldV2Parameters(base)
        solver = SolverConfig(ReferenceMinimizationConfig(max_iterations=3))
        solvent = None
    comp = RefinementComparisonConfig()
    count, steps = 4, 3
    if equal_budget:
        comp = RefinementComparisonConfig(mode="equal_work_budget", work_units_per_arm=8)
        count, steps = 16, 2
        solver = replace(solver, minimization=replace(solver.minimization, max_backtracks=0))
    return run_comparison(authority, DockingBudget(candidate_count=count, top_k=2, max_torsions=1,
        max_refinement_steps=steps, seed=1301), receptor_system=receptor, ligand_system=ligand,
        parameters=parameters, solver=solver, solvation=solvent if solvated else None, comparison=comp)


@pytest.mark.parametrize("extended,solvated", [(False, False), (True, False), (True, True)])
def test_real_pipeline_uses_corrected_extension_and_final_topk(extended, solvated):
    report = real_run(extended=extended, solvated=solvated)
    assert report["arms"]["refined"]["success_count"] == 4
    assert len(report["final_selection"]["selected_candidates"]) <= 2
    scores = [row["score"] for row in report["final_selection"]["selected_candidates"]]
    assert scores == sorted(scores)
    for before, after, attempt in zip(report["arms"]["baseline"]["rows"], report["arms"]["refined"]["rows"], report["attempts"], strict=True):
        assert before["coordinates_sha256"] == attempt["pre_coordinates_sha256"]
        assert after["coordinates_sha256"] == attempt["post_coordinates_sha256"]
        assert attempt["pre_coordinates_sha256"] != attempt["post_coordinates_sha256"]
        assert attempt["energy_delta"] < 0
    assert verify_report(report)["structural_verification_passed"]


def test_equal_budget_retains_independent_arms_and_final_lists():
    report = real_run(equal_budget=True)
    assert report["arms"]["baseline"]["candidate_count"] == 8
    assert report["arms"]["refined"]["candidate_count"] == 2
    assert report["arms"]["baseline"]["work_units_reserved"] == report["arms"]["refined"]["work_units_reserved"] == 8
    assert report["final_selection"] is None and report["paired_decisions"] == []
    assert verify_report(report)["structural_verification_passed"]


def test_failed_refinement_retains_originals_and_all_denominators(monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2 import refinement
    def fail(*args, **kwargs):
        raise RuntimeError("private synthetic failure")
    monkeypatch.setattr(refinement, "minimize_extended", fail)
    report = real_run()
    assert report["arms"]["baseline"]["success_count"] == 4
    assert report["arms"]["refined"]["failure_count"] == 4
    assert len(report["attempts"]) == 4
    assert all(row["variant"] == "baseline" for row in report["final_selection"]["selected_candidates"])
    assert verify_report(report)["structural_verification_passed"]
    assert "private synthetic failure" not in str(report)


def test_rescoring_failure_keeps_successful_refinement_evidence(monkeypatch):
    from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
    original = ChemistryPoseScorerV1._score_terms_python
    def score(self, proposal):
        if proposal.refinement_receipt_sha256:
            raise RuntimeError("synthetic score failure")
        return original(self, proposal)
    monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", score)
    report = real_run()
    assert report["arms"]["refined"]["failure_count"] == 4
    assert all(attempt["status"] == "success" for attempt in report["attempts"])
    assert verify_report(report)["structural_verification_passed"]


def test_numerical_receipts_do_not_depend_on_wall_time():
    first, second = real_run(), real_run()
    assert first["attempts"] == second["attempts"]
    assert first["final_selection"] == second["final_selection"]


@pytest.mark.parametrize("change", ["score", "order", "coordinates", "decision", "denominator", "attempt"])
def test_readonly_verifier_rejects_rehashed_crosswiring(change):
    report = real_run()
    if change == "score":
        report["final_selection"]["selected_candidates"][0]["score"] += 1
    elif change == "order":
        report["final_selection"]["selected_candidates"].reverse()
    elif change == "coordinates":
        report["arms"]["baseline"]["rows"][0]["coordinates_binary64_hex"][0][0] = (99.).hex()
    elif change == "decision":
        report["paired_decisions"][0]["variant"] = "refined"
    elif change == "denominator":
        report["arms"]["refined"]["failure_count"] += 1
    else:
        report["attempts"][0]["energy_delta"] -= 1
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    with pytest.raises(ResearchError):
        verify_report(report)


@pytest.mark.parametrize("change", ["score_terms", "claim", "attempt_identity"])
def test_rehashed_evidence_inconsistency_rejected(change):
    report = real_run()
    if change == "score_terms":
        report["arms"]["baseline"]["rows"][0]["terms"]["total_score_binary64_hex"] = (99.).hex()
    elif change == "claim":
        report["scientifically_validated"] = True
    else:
        attempt = report["attempts"][0]
        attempt["candidate_id"] = "wrong-candidate"
        attempt["receipt_sha256"] = digest({k: v for k, v in attempt.items() if k != "receipt_sha256"})
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    with pytest.raises(ResearchError):
        verify_report(report)
