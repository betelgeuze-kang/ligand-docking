"""Both comparison modes retain numerical rows/selection across an actual pause."""

from dataclasses import replace
import pytest
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig,
)
from betelgeuze_product.cpu_refinement_v1_2.comparison import run_comparison
from betelgeuze_product.cpu_refinement_v1_2.comparison_resume import (
    run_candidate_comparison,
)
from betelgeuze_product.cpu_refinement_v1_2.candidate_execution import (
    CandidateExecution,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture


def inputs(equal):
    a, r, ligand, p, e, s, b = fixture()
    comparison = RefinementComparisonConfig()
    if equal:
        s = replace(s, minimization=replace(s.minimization, max_backtracks=0))
        b = replace(b, candidate_count=12, max_refinement_steps=2)
        comparison = RefinementComparisonConfig(
            mode="equal_work_budget", work_units_per_arm=8
        )
    return (
        a,
        b,
        dict(
            receptor_system=r,
            ligand_system=ligand,
            parameters=p,
            solver=s,
            fixed_environment=e,
            comparison=comparison,
        ),
    )


@pytest.mark.parametrize("equal", [False, True])
def test_pause_resume_matches_existing_comparison_and_completed_replay(
    tmp_path, monkeypatch, equal
):
    a, b, kw = inputs(equal)
    reference = run_comparison(a, b, **kw)
    output = tmp_path / "comparison"
    paused = run_candidate_comparison(a, b, **kw, output=output, stop_after=2)
    assert paused["execution_complete"] is False and paused["committed_candidates"] == 2
    actual = run_candidate_comparison(a, b, **kw, output=output, resume=True)
    assert actual["execution_complete"]
    assert actual["rows"] == {
        name: arm["rows"] for name, arm in reference["arms"].items()
    }
    for name in [
        "attempts",
        "paired_decisions",
        "final_selection",
        "raw_per_arm_selection",
        "per_arm_selection",
    ]:
        assert actual[name] == reference[name]
    assert actual["costs"]["baseline"]["reused_candidates"] == 2
    assert sum(
        c["historical_score_calls"] + c["new_score_calls"]
        for c in actual["costs"].values()
    ) == sum(arm["score_evaluation_calls"] for arm in reference["arms"].values())
    assert (
        sum(
            c["historical_force_calls"] + c["new_force_calls"]
            for c in actual["costs"].values()
        )
        == reference["arms"]["refined"]["actual_force_evaluation_calls"]
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("completed comparison recomputed")

    monkeypatch.setattr(CandidateExecution, "compute", forbidden)
    replay = run_candidate_comparison(a, b, **kw, output=output, resume=True)
    assert (
        replay["rows"] == actual["rows"]
        and replay["final_selection"] == actual["final_selection"]
    )
    assert all(
        c["new_candidates"] == c["new_score_calls"] == c["new_force_calls"] == 0
        for c in replay["costs"].values()
    )
    assert len(replay["rows"]["baseline"]) == (8 if equal else 4)
    assert len(replay["rows"]["refined"]) == (2 if equal else 4)


def test_changed_budget_and_backward_pause_reject(tmp_path):
    a, b, kw = inputs(False)
    out = tmp_path / "comparison"
    run_candidate_comparison(a, b, **kw, output=out, stop_after=2)
    with pytest.raises(ResearchError, match="plan changed"):
        run_candidate_comparison(
            a, replace(b, seed=b.seed + 1), **kw, output=out, resume=True
        )
    with pytest.raises(ResearchError, match="precedes"):
        run_candidate_comparison(a, b, **kw, output=out, resume=True, stop_after=1)


@pytest.mark.parametrize("equal", [False, True])
def test_interrupted_refined_arm_retains_commits_and_unknown_cost(
    tmp_path, monkeypatch, equal
):
    a, b, kw = inputs(equal)
    out = tmp_path / "interrupted"
    reference = run_comparison(a, b, **kw)
    original = CandidateExecution.compute

    def interrupt(self, index):
        if self.refiner is not None and index == 1:
            raise KeyboardInterrupt("controlled pre-commit interruption")
        return original(self, index)

    monkeypatch.setattr(CandidateExecution, "compute", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_candidate_comparison(a, b, **kw, output=out)
    monkeypatch.setattr(CandidateExecution, "compute", original)
    resumed = run_candidate_comparison(a, b, **kw, output=out, resume=True)
    assert resumed["rows"] == {
        name: arm["rows"] for name, arm in reference["arms"].items()
    }
    assert resumed["final_selection"] == reference["final_selection"]
    assert resumed["costs"]["refined"]["reused_candidates"] == 1
    assert resumed["costs"]["refined"]["interrupted_attempts_unknown_cost"] == 1
    assert resumed["costs"]["baseline"]["new_candidates"] == 0
