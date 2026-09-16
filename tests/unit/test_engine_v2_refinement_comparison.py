"""Real CPU search integration, failure denominators and conservative work budgets."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json

import pytest

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.docking import energy_refinement_v1_1 as energy_refinement
from betelgeuze_engine_v2.docking.refinement_comparison import (
    RefinementComparisonConfig, _selection, plan_refinement_comparison,
    run_cpu_refinement_comparison,
)
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _config as _legacy_config, _parameters


from betelgeuze_engine_v2.docking.energy_refinement_v1_1 import EnergyLocalRefinementConfig
from betelgeuze_engine_v2.physics.reference_minimization_v1_1 import ReferenceMinimizationConfig


def _config():
    old = _legacy_config()
    return EnergyLocalRefinementConfig(
        minimization=ReferenceMinimizationConfig(**asdict(old.minimization)),
        max_attempts=old.max_attempts,
    )


def run_comparison(*, comparison=None, parameters=None, count=4, steps=3, minimization=None):
    authority, receptor, ligand = _authority()
    if parameters is None:
        original = _parameters(ligand)
        # Explicitly altered synthetic equilibrium lengths, not fitted parameters.
        parameters = replace(original, bonds=tuple(
            replace(b, equilibrium_angstrom=b.equilibrium_angstrom * .9) for b in original.bonds))
    return run_cpu_refinement_comparison(
        authority, DockingBudget(candidate_count=count, top_k=min(2, count),
                                max_torsions=1, max_refinement_steps=steps, seed=1301),
        receptor_system=receptor, ligand_system=ligand, parameters=parameters,
        implementation_source_sha256="e" * 64,
        minimization=_config().minimization if minimization is None else minimization,
        comparison=comparison,
    )


def test_actual_coordinate_refinement_and_rescoring_are_paired():
    report = run_comparison()
    assert report["baseline"]["candidate_count"] == report["refined"]["candidate_count"] == 4
    assert len(report["paired_rows"]) == 4
    assert any(r["pre_coordinates_sha256"] != r["post_coordinates_sha256"] for r in report["paired_rows"])
    assert any(r["energy_delta_kcal_per_mol"] < 0 for r in report["paired_rows"])
    for before, after, pair in zip(report["baseline"]["rows"], report["refined"]["rows"],
                                  report["paired_rows"], strict=True):
        assert before["coordinates_sha256"] == pair["pre_coordinates_sha256"]
        assert after["coordinates_sha256"] == pair["post_coordinates_sha256"]
        assert after["terms"]["proposal_fingerprint_sha256"] == after["result_proposal_fingerprint_sha256"]
        assert after["pose_validity"] is not None
    assert report["refined"]["force_evaluations_exact"] >= 4
    assert not report["claim_safe"] and not report["customer_execution_allowed"]
    assert not report["receptor_ligand_interaction_energy_minimized"]
    digest = report.pop("report_sha256")
    assert hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest() == digest


def test_numerics_repeat_exactly_but_elapsed_time_is_not_a_digest_claim():
    first, second = run_comparison(), run_comparison()
    assert first["paired_rows"] == second["paired_rows"]
    assert first["baseline"]["rows"] == second["baseline"]["rows"]
    assert first["refined"]["rows"] == second["refined"]["rows"]
    assert first["refined"]["attempts"] == second["refined"]["attempts"]


def test_refinement_failures_keep_all_rows_and_unknown_work(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic evaluation failure; private detail")
    monkeypatch.setattr(energy_refinement, "minimize_reference_force_field", fail)
    report = run_comparison()
    assert report["baseline"]["success_count"] == 4
    assert report["refined"]["failure_count"] == 4
    assert report["refined"]["force_evaluations_exact"] is None
    assert report["refined"]["failed_attempts_with_unknown_work"] == 4
    assert report["refined"]["work_units_reserved"] > 4
    assert len(report["refined"]["rows"]) == len(report["paired_rows"]) == 4
    for row in report["paired_rows"]:
        assert row["energy_delta_kcal_per_mol"] is None
        assert row["selected_variant"] == ("baseline" if row["baseline_pose_valid"] else "none")
    assert "private detail" not in json.dumps(report)


def test_equal_work_caps_both_arms_without_claiming_equal_cpu_time():
    config = replace(_config().minimization, max_backtracks=0)
    report = run_comparison(comparison=RefinementComparisonConfig(
        mode="equal_work_budget", work_units_per_arm=8), count=16, steps=2, minimization=config)
    assert report["force_evaluation_upper_bound_per_candidate"] == 3
    assert report["baseline"]["candidate_count"] == 8
    assert report["refined"]["candidate_count"] == 2
    assert report["baseline"]["work_units_reserved"] == report["refined"]["work_units_reserved"] == 8
    assert report["paired_rows"] == [] and report["selected_candidates"] == []
    assert report["equal_elapsed_compute_time_claimed"] is False


@pytest.mark.parametrize("mode", ["same_candidates", "equal_work_budget"])
def test_insufficient_budget_rejected_before_any_search(monkeypatch, mode):
    import betelgeuze_engine_v2.docking.refinement_comparison as module
    def forbidden(*args, **kwargs):
        pytest.fail("search executed before budget admission")
    monkeypatch.setattr(module, "run_authenticated_scorer_v1_guided_search", forbidden)
    with pytest.raises(ValueError, match="work budget"):
        run_comparison(comparison=RefinementComparisonConfig(mode=mode, work_units_per_arm=1))


@pytest.mark.parametrize("kwargs", [
    {"mode": "unknown"}, {"work_units_per_arm": True}, {"work_units_per_arm": 0},
    {"score_evaluation_weight": True}, {"force_evaluation_weight": -1},
    {"require_convergence_for_selection": "false"}, {"mode": "equal_work_budget"},
])
def test_invalid_comparison_contract(kwargs):
    with pytest.raises(ValueError):
        RefinementComparisonConfig(**kwargs)


def test_weighted_reservation_and_candidate_cap():
    b = DockingBudget(candidate_count=10, top_k=2, max_refinement_steps=2)
    m = replace(_config().minimization, max_backtracks=0)
    before, after, bound = plan_refinement_comparison(
        b, m, RefinementComparisonConfig(mode="equal_work_budget", work_units_per_arm=44,
                                        score_evaluation_weight=2, force_evaluation_weight=3))
    assert bound == 3
    assert before.candidate_count == 10 and after.candidate_count == 4


def test_request_sources_remain_unchanged():
    authority, receptor, ligand = _authority()
    original = canonical_system_sha256(receptor), canonical_system_sha256(ligand)
    run_cpu_refinement_comparison(authority, DockingBudget(candidate_count=2, top_k=1, max_refinement_steps=2),
        receptor_system=receptor, ligand_system=ligand, parameters=_parameters(ligand),
        implementation_source_sha256="e" * 64, minimization=_config().minimization)
    assert (canonical_system_sha256(receptor), canonical_system_sha256(ligand)) == original


def test_selection_keeps_baseline_when_refinement_invalid_or_worse():
    from types import SimpleNamespace as Row
    before = Row(succeeded=True, selection_eligible=True, score=1.)
    after = Row(succeeded=True, selection_eligible=False, score=-100.)
    attempt = Row(status="success", converged=True, energy_delta_kcal_per_mol=-3.)
    assert _selection(before, after, attempt, True)[0] == "baseline"
    after.selection_eligible = True
    assert _selection(before, after, attempt, True)[0] == "refined"
    after.score = 2.
    assert _selection(before, after, attempt, True)[0] == "baseline"
    after.score = 0.
    attempt.converged = False
    assert _selection(before, after, attempt, True)[0] == "baseline"
    assert _selection(before, after, attempt, False)[0] == "refined"
    attempt.energy_delta_kcal_per_mol = 1.
    assert _selection(before, after, attempt, False)[0] == "baseline"


def test_refiner_rejects_legacy_config_and_receipts_identify_new_numerics():
    authority, _, ligand = _authority()
    with pytest.raises(TypeError, match="1.1"):
        energy_refinement.EnergyBasedLocalRefiner(
            authority, ligand, _parameters(ligand), implementation_source_sha256="e" * 64,
            config=_legacy_config())
    with pytest.raises(TypeError, match="1.1"):
        EnergyLocalRefinementConfig(minimization=_legacy_config().minimization)
    report = run_comparison()
    for attempt in report["refined"]["attempts"]:
        assert attempt["reference_minimization_algorithm_id"].endswith("/1.1.0")
        assert attempt["algorithm_id"].endswith("/1.1.0")
    assert report["minimization"]["algorithm_id"].endswith("/1.1.0")


def test_nearly_linear_ligand_is_actually_relaxed_in_search():
    import math
    from tests.unit.test_engine_v2_reference_angle_boundary import angle_system
    ligand, parameters = angle_system(math.pi - 1.e-7)
    authority, receptor, ligand = _authority(ligand)
    report = run_cpu_refinement_comparison(
        authority, DockingBudget(candidate_count=2, top_k=1, max_refinement_steps=2),
        receptor_system=receptor, ligand_system=ligand, parameters=parameters,
        implementation_source_sha256="e" * 64, minimization=ReferenceMinimizationConfig(max_iterations=2))
    for attempt in report["refined"]["attempts"]:
        assert attempt["status"] == "success"
        assert attempt["accepted_iterations"] > 0
    for pair in report["paired_rows"]:
        assert pair["energy_delta_kcal_per_mol"] < 0.
        assert pair["pre_coordinates_sha256"] != pair["post_coordinates_sha256"]


def test_rescoring_failure_preserves_successful_refinement_and_original(monkeypatch):
    from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
    original = ChemistryPoseScorerV1._score_terms_python
    def score(self, proposal):
        if proposal.refinement_receipt_sha256:
            raise RuntimeError("synthetic rescore failure")
        return original(self, proposal)
    monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", score)
    report = run_comparison()
    assert report["baseline"]["success_count"] == 4
    assert report["refined"]["failure_count"] == 4
    assert all(a["status"] == "success" for a in report["refined"]["attempts"])
    for pair in report["paired_rows"]:
        assert pair["selected_variant"] in {"baseline", "none"}
        assert pair["selection_reason"] == "refinement_or_rescoring_failed"
