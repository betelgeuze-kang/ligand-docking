"""Shared search execution versus journaled candidates and no-compute replay."""

from dataclasses import replace
import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.docking.guided_placement import (
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from betelgeuze_product.cpu_refinement.refinement_comparison import _pose
from betelgeuze_product.cpu_refinement_v1_2.refinement import ExtendedRefiner
from betelgeuze_product.cpu_refinement_v1_2.candidate_execution import (
    CandidateExecution,
)
from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    source_manifest,
    environment,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture


@pytest.mark.parametrize(
    "refined,failure",
    [(False, None), (True, None), (False, "score"), (True, "score"), (True, "refine")],
)
def test_shared_candidate_path_matches_full_search_and_replays(
    tmp_path, monkeypatch, refined, failure
):
    a, r, ligand, params, fixed, solver, budget = fixture()
    if not refined:
        budget = replace(budget, max_refinement_steps=0)
    source = digest(source_manifest())
    context = build_guided_placement_context(a, r, ligand)
    proposals, _ = generate_guided_docking_proposals(
        a, budget, context, receptor_system=r, ligand_system=ligand
    )

    def scorer():
        return ChemistryPoseScorerV1(a, r, ligand, implementation_source_sha256=source)

    def refiner():
        return (
            None
            if not refined
            else ExtendedRefiner(
                a,
                ligand,
                params,
                solver,
                implementation_source_sha256=source,
                fixed_environment=fixed,
            )
        )

    def fail(*args, **kwargs):
        raise ResearchError("synthetic candidate failure")

    if failure == "score":
        monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", fail)
    if failure == "refine":
        from betelgeuze_product.cpu_refinement_v1_2 import refinement

        monkeypatch.setattr(refinement, "minimize_extended", fail)
    result = run_authenticated_scorer_v1_guided_search(
        a,
        budget,
        scorer(),
        context,
        receptor_system=r,
        ligand_system=ligand,
        refiner=refiner(),
    )
    reference = (
        result.guided_search_result.authenticated_search_result.search_result.rows
    )
    keys = [digest([refined, p.fingerprint_sha256]) for p in proposals]
    indices = {k: i for i, k in enumerate(keys)}
    binding = dict(
        schema_id="cpu_comparison_candidate_journal/1.0.0",
        request_sha256=digest(budget.to_dict()),
        implementation_sha256=source,
        environment_sha256=digest(environment()),
        candidate_keys=keys,
    )
    engine = CandidateExecution(a, budget, scorer(), proposals, refiner=refiner())

    def validate(key, record):
        engine.validate(indices[key], record)

    with open_journal(tmp_path / "candidates", binding, validate_record=validate) as j:
        actual = [engine.execute(j, i) for i in range(len(proposals))]
    assert [_pose(row, row.score_evidence) for row, _ in actual] == [
        _pose(row, row.score_evidence) for row in reference
    ]
    for row, saved in actual:
        calls = saved["execution_work"]["stages"].get("score.evaluate", {})
        assert calls.get("calls", 0) == (0 if failure == "refine" else 1)
        assert calls.get("failed", 0) == (1 if failure == "score" else 0)
    engine = CandidateExecution(a, budget, scorer(), proposals, refiner=refiner())

    def forbidden(*args, **kwargs):
        raise AssertionError("committed candidate recomputed")

    monkeypatch.setattr(CandidateExecution, "compute", forbidden)
    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden)
    monkeypatch.setattr(ExtendedRefiner, "refine", forbidden)
    with open_journal(
        tmp_path / "candidates", binding, validate_record=validate, resume=True
    ) as j:
        replayed = [engine.execute(j, i) for i in range(len(proposals))]
    assert [saved for _, saved in replayed] == [saved for _, saved in actual]
    assert [_pose(row, row.score_evidence) for row, _ in replayed] == [
        _pose(row, row.score_evidence) for row in reference
    ]
