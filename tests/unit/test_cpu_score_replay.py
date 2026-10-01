"""Actual baseline/refined score terms replay, including rehashed contradictions."""

from copy import deepcopy
import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1, _sha256
from betelgeuze_engine_v2.docking.guided_placement import (
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from betelgeuze_product.cpu_refinement_v1_2.refinement import ExtendedRefiner
from betelgeuze_product.cpu_refinement_v1_2.score_replay import restore_score_terms
from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    source_manifest,
    environment,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture


def setup(refined=False):
    a, r, ligand, params, fixed, solver, budget = fixture()
    source = digest(source_manifest())
    context = build_guided_placement_context(a, r, ligand)
    proposals, _ = generate_guided_docking_proposals(
        a, budget, context, receptor_system=r, ligand_system=ligand
    )
    proposal = proposals[0]
    if refined:
        refiner = ExtendedRefiner(
            a,
            ligand,
            params,
            solver,
            implementation_source_sha256=source,
            fixed_environment=fixed,
        )
        proposal = refiner.refine(proposal, max_steps=budget.max_refinement_steps)
    scorer = ChemistryPoseScorerV1(a, r, ligand, implementation_source_sha256=source)
    return scorer, proposal


def forbidden(*args, **kwargs):
    raise AssertionError("score replay must not recompute")


@pytest.mark.parametrize("refined", [False, True])
def test_actual_score_through_journal_without_scoring(tmp_path, monkeypatch, refined):
    scorer, proposal = setup(refined)
    original = scorer.score_terms(proposal)
    key = digest(["refined" if refined else "baseline", proposal.fingerprint_sha256])
    binding = dict(
        schema_id="cpu_comparison_candidate_journal/1.0.0",
        request_sha256=digest(refined),
        implementation_sha256=scorer.implementation_source_sha256,
        environment_sha256=digest(environment()),
        candidate_keys=[key],
    )

    def validate(k, value):
        assert k == key
        restore_score_terms(scorer, proposal, value)

    with open_journal(tmp_path / "scores", binding, validate_record=validate) as j:
        j.evaluate(0, original.to_dict)
    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden)
    monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", forbidden)
    with open_journal(
        tmp_path / "scores", binding, validate_record=validate, resume=True
    ) as j:
        restored = restore_score_terms(scorer, proposal, j.evaluate(0, forbidden))
    assert restored.to_dict() == original.to_dict()
    assert restored.total_score.hex() == original.total_score.hex()
    assert restored.receipt_sha256 == original.receipt_sha256


@pytest.mark.parametrize(
    "mutation",
    [
        "proposal",
        "authority",
        "context",
        "config",
        "backend",
        "component",
        "total",
        "nan",
        "hex",
        "bool_count",
        "claim",
        "schema",
        "missing",
        "extra",
        "receipt",
    ],
)
def test_saved_score_rehashed_contradictions_reject(mutation, monkeypatch):
    scorer, proposal = setup()
    doc = deepcopy(scorer.score_terms(proposal).to_dict())
    identities = {
        "proposal": "proposal_fingerprint_sha256",
        "authority": "authority_input_receipt_sha256",
        "context": "context_fingerprint_sha256",
        "config": "config_fingerprint_sha256",
        "backend": "backend_receipt_sha256",
    }
    if mutation in identities:
        doc[identities[mutation]] = "0" * 64
    elif mutation in {"component", "total"}:
        key = (
            "typed_vdw_binary64_hex"
            if mutation == "component"
            else "total_score_binary64_hex"
        )
        doc[key] = (float.fromhex(doc[key]) + 1).hex()
    elif mutation == "nan":
        doc["total_score_binary64_hex"] = "nan"
    elif mutation == "hex":
        doc["total_score_binary64_hex"] = " " + doc["total_score_binary64_hex"]
    elif mutation == "bool_count":
        doc["hbond_count"] = False
    elif mutation == "claim":
        doc["scientifically_validated"] = True
    elif mutation == "schema":
        doc["score_id"] = "binding_free_energy"
    elif mutation == "missing":
        del doc["ligand_strain_binary64_hex"]
    elif mutation == "extra":
        doc["unrecognized"] = 1
    if mutation == "receipt":
        doc["receipt_sha256"] = "0" * 64
    else:
        doc["receipt_sha256"] = _sha256(
            {k: v for k, v in doc.items() if k != "receipt_sha256"}
        )
    monkeypatch.setattr(ChemistryPoseScorerV1, "score_batch", forbidden)
    with pytest.raises(ResearchError):
        restore_score_terms(scorer, proposal, doc)
