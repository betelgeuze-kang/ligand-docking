"""Actual authenticated optimization records restored without a solver call."""

from copy import deepcopy
import pytest
import torch

from betelgeuze_engine_v2.docking.guided_placement import (
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from betelgeuze_product.cpu_refinement_v1_2 import refinement
from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    source_manifest,
    environment,
)
from tests.unit.test_cpu_fixed_receptor_pipeline import fixture


def setup(fixed=True):
    a, r, ligand, p, e, s, b = fixture()
    context = build_guided_placement_context(a, r, ligand)
    proposals, _ = generate_guided_docking_proposals(
        a, b, context, receptor_system=r, ligand_system=ligand
    )
    source = digest(source_manifest())

    def factory():
        return refinement.ExtendedRefiner(
            a,
            ligand,
            p,
            s,
            implementation_source_sha256=source,
            fixed_environment=e if fixed else None,
        )

    return factory, proposals[0], b.max_refinement_steps, source


def forbidden(*args, **kwargs):
    raise AssertionError("restored attempt must not invoke solver")


@pytest.mark.parametrize("fixed", [False, True])
def test_real_attempt_journal_replay_exact_proposal_and_work(
    tmp_path, monkeypatch, fixed
):
    factory, proposal, steps, source = setup(fixed)
    original = factory()
    refined = original.refine(proposal, max_steps=steps)
    attempt = original.attempt_for(proposal.fingerprint_sha256)
    saved = {"attempt": attempt.to_dict(), "work": attempt.work()}
    restored = factory()
    key = digest(["refined", proposal.fingerprint_sha256])
    binding = dict(
        schema_id="cpu_comparison_candidate_journal/1.0.0",
        request_sha256=digest([steps, fixed]),
        implementation_sha256=source,
        environment_sha256=digest(environment()),
        candidate_keys=[key],
    )

    def validate(k, row):
        assert k == key
        restored.validate_saved_attempt(
            proposal, row["attempt"], row["work"], max_steps=steps
        )

    with open_journal(tmp_path / "records", binding, validate_record=validate) as j:
        j.evaluate(0, lambda: saved)
    monkeypatch.setattr(refinement, "minimize_extended", forbidden)
    with open_journal(
        tmp_path / "records", binding, validate_record=validate, resume=True
    ) as j:
        row = j.evaluate(0, forbidden)
        replay = restored.restore_attempt(
            proposal, row["attempt"], row["work"], max_steps=steps
        )
    assert replay.fingerprint_sha256 == refined.fingerprint_sha256
    assert torch.equal(
        replay.coordinates.view(torch.int64), refined.coordinates.view(torch.int64)
    )
    assert (
        restored.attempt_for(proposal.fingerprint_sha256).to_dict() == saved["attempt"]
    )
    assert restored.attempt_for(proposal.fingerprint_sha256).work() == saved["work"]
    assert restored.replayed_attempts == {proposal.fingerprint_sha256}
    with pytest.raises(ResearchError, match="already"):
        restored.restore_attempt(proposal, row["attempt"], row["work"], max_steps=steps)


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "evaluator",
        "delta",
        "displacement",
        "components",
        "work",
        "coordinates",
        "solver",
    ],
)
def test_rehashed_saved_attempt_contradictions_reject(field, monkeypatch):
    factory, proposal, steps, _ = setup()
    original = factory()
    original.refine(proposal, max_steps=steps)
    attempt = original.attempt_for(proposal.fingerprint_sha256)
    doc, work = deepcopy(attempt.to_dict()), deepcopy(attempt.work())
    if field == "source":
        doc["implementation_source_sha256"] = "0" * 64
    elif field == "evaluator":
        doc["evaluator"]["receptor_system_sha256"] = "0" * 64
    elif field == "delta":
        doc["energy_delta"] += 1
    elif field == "displacement":
        doc["maximum_displacement_angstrom"] += 0.01
    elif field == "components":
        doc["final_components"]["cross_lennard_jones"] += 1
    elif field == "work":
        work["force_evaluation_calls"] = 0
    elif field == "coordinates":
        doc["post_coordinates_binary64_hex"][0][0] = float(999).hex()
    elif field == "solver":
        doc["solver"]["minimization"]["max_iterations"] += 1
    doc["receipt_sha256"] = digest(
        {k: v for k, v in doc.items() if k != "receipt_sha256"}
    )
    restored = factory()
    monkeypatch.setattr(refinement, "minimize_extended", forbidden)
    with pytest.raises(ResearchError):
        restored.restore_attempt(proposal, doc, work, max_steps=steps)
    assert not restored.attempts and not restored.replayed_attempts


def test_recorded_failure_restores_failure_without_recompute(monkeypatch):
    factory, proposal, steps, _ = setup()
    original = factory()

    def fail(*args, **kwargs):
        raise ResearchError("synthetic solver failure")

    monkeypatch.setattr(refinement, "minimize_extended", fail)
    with pytest.raises(ResearchError):
        original.refine(proposal, max_steps=steps)
    attempt = original.attempt_for(proposal.fingerprint_sha256)
    restored = factory()
    monkeypatch.setattr(refinement, "minimize_extended", forbidden)
    with pytest.raises(ResearchError, match="restored"):
        restored.restore_attempt(
            proposal, attempt.to_dict(), attempt.work(), max_steps=steps
        )
    assert (
        restored.attempt_for(proposal.fingerprint_sha256).to_dict() == attempt.to_dict()
    )
    assert restored.replayed_attempts == {proposal.fingerprint_sha256}
