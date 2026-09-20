"""Real failed scorer rows survive replay without rehashing private diagnostics."""

from copy import deepcopy
import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.docking.guided_placement import (
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from betelgeuze_product.cpu_refinement_v1_2.refinement import ExtendedRefiner
from betelgeuze_product.cpu_refinement_v1_2.failure_replay import restore_failure_row
from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    source_manifest,
    environment,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture


def failed_search(monkeypatch, refined=False):
    a, r, ligand, params, fixed, solver, budget = fixture()
    context = build_guided_placement_context(a, r, ligand)
    proposals, _ = generate_guided_docking_proposals(
        a, budget, context, receptor_system=r, ligand_system=ligand
    )
    source = digest(source_manifest())
    scorer = ChemistryPoseScorerV1(a, r, ligand, implementation_source_sha256=source)
    refiner = (
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
        raise ValueError("private synthetic diagnostic must not appear in saved rows")

    monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", fail)
    result = run_authenticated_scorer_v1_guided_search(
        a,
        budget,
        scorer,
        context,
        receptor_system=r,
        ligand_system=ligand,
        refiner=refiner,
    )
    rows = result.guided_search_result.authenticated_search_result.search_result.rows
    assert len(rows) == budget.candidate_count and all(
        not row.succeeded for row in rows
    )
    assert all(row.refined == refined for row in rows)
    return a, proposals, rows, source


def forbidden(*args, **kwargs):
    raise AssertionError("failure replay must not compute")


@pytest.mark.parametrize("refined", [False, True])
def test_actual_failed_rows_journal_replay_preserves_denominator(
    tmp_path, monkeypatch, refined
):
    a, proposals, rows, source = failed_search(monkeypatch, refined)
    keys = [digest([refined, p.fingerprint_sha256]) for p in proposals]
    mapping = dict(zip(keys, proposals))
    binding = dict(
        schema_id="cpu_comparison_candidate_journal/1.0.0",
        request_sha256=digest(refined),
        implementation_sha256=source,
        environment_sha256=digest(environment()),
        candidate_keys=keys,
    )

    def validate(key, doc):
        restore_failure_row(a, mapping[key], doc, refined=refined)

    with open_journal(tmp_path / "rows", binding, validate_record=validate) as j:
        for i, row in enumerate(rows):
            j.evaluate(i, row.to_dict)
    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden)
    monkeypatch.setattr(ExtendedRefiner, "refine", forbidden)
    with open_journal(
        tmp_path / "rows", binding, validate_record=validate, resume=True
    ) as j:
        restored = [
            restore_failure_row(a, p, j.evaluate(i, forbidden), refined=refined)
            for i, p in enumerate(proposals)
        ]
    assert [row.to_dict() for row in restored] == [row.to_dict() for row in rows]
    assert len(restored) == len(proposals) == 4
    assert all(
        row.proposal is None and row.score is None and not row.selection_eligible
        for row in restored
    )
    assert "private synthetic diagnostic" not in str(
        [row.to_dict() for row in restored]
    )


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "score",
        "selection_eligible",
        "candidate_id",
        "refined",
        "private_error_sha256",
        "private_error_byte_length",
        "error_message",
        "pose_validity",
        "proposal_index",
    ],
)
def test_failed_row_contradictions_reject(monkeypatch, field):
    a, proposals, rows, _ = failed_search(monkeypatch)
    doc = deepcopy(rows[0].to_dict())
    changes = dict(
        status="success",
        score=0.0,
        selection_eligible=True,
        candidate_id="other",
        refined=True,
        private_error_sha256="bad",
        private_error_byte_length=False,
        error_message="private content",
        pose_validity={},
        proposal_index=False,
    )
    doc[field] = changes[field]
    with pytest.raises(ResearchError):
        restore_failure_row(a, proposals[0], doc, refined=False)
