from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    GEOMETRIC_RIGID_REFINEMENT_BLOCKERS,
    DockingBudget,
    DockingProblemIdentity,
    ElementGeometryDiagnosticScoreConfig,
    ElementGeometryDiagnosticScorer,
    GeometricRigidBodyRefiner,
    GeometricRigidRefinementConfig,
    GeometricRigidRefinementError,
    GeometricRigidRefinementReceipt,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


def _proposal():
    coordinates = torch.tensor(
        [[4.0, 0.0, 0.0], [5.4, 0.0, 0.0], [5.4, 1.2, 0.0]],
        dtype=torch.float64,
    )
    space = TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((3,), -1, dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=torch.float64),
        rotatable_mask=torch.zeros(3, dtype=torch.bool),
        root_positions=coordinates,
    )
    return generate_bounded_docking_proposals(
        space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0),
        problem=_problem(),
    )[0]


def _scorer() -> ElementGeometryDiagnosticScorer:
    return ElementGeometryDiagnosticScorer(
        torch.tensor([[0.0, 0.0, 0.0], [0.0, 3.4, 0.0]], dtype=torch.float64),
        (6, 8),
        (6, 6, 8),
        _problem(),
        config=ElementGeometryDiagnosticScoreConfig(
            receptor_shell_radius_angstrom=10.1,
            pocket_radius_angstrom=10.0,
        ),
    )


def _distances(coordinates: torch.Tensor) -> torch.Tensor:
    return torch.cdist(coordinates, coordinates)


def test_rigid_refinement_is_deterministic_nonincreasing_and_distance_preserving() -> None:
    proposal = _proposal()
    refiner = GeometricRigidBodyRefiner(
        _scorer(),
        config=GeometricRigidRefinementConfig(maximum_steps=8),
    )

    refined, receipt = refiner.refine_with_receipt(proposal, max_steps=8)
    repeated, repeated_receipt = refiner.refine_with_receipt(proposal, max_steps=8)

    assert refined.fingerprint_sha256 == repeated.fingerprint_sha256
    assert receipt.to_dict() == repeated_receipt.to_dict()
    assert receipt.final_score <= receipt.initial_score
    assert receipt.accepted_step_count + receipt.rejected_step_count == len(receipt.steps)
    assert receipt.blockers == GEOMETRIC_RIGID_REFINEMENT_BLOCKERS
    assert refined.refined
    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256
    assert refined.refinement_receipt_sha256 == receipt.fingerprint_sha256
    torch.testing.assert_close(
        _distances(refined.coordinates),
        _distances(proposal.coordinates),
        atol=1.0e-12,
        rtol=1.0e-12,
    )
    assert receipt.to_dict()["scientifically_validated"] is False
    assert receipt.to_dict()["claim_safe"] is False


def test_refiner_protocol_method_returns_bound_lineage() -> None:
    proposal = _proposal()
    refiner = GeometricRigidBodyRefiner(_scorer())

    refined = refiner.refine(proposal, max_steps=4)

    assert refined.refiner_id == refiner.refiner_id
    assert refined.refiner_version == refiner.refiner_version
    assert len(refined.refinement_receipt_sha256) == 64


def test_refiner_rejects_budget_problem_and_receipt_tampering() -> None:
    proposal = _proposal()
    refiner = GeometricRigidBodyRefiner(
        _scorer(),
        config=GeometricRigidRefinementConfig(maximum_steps=4),
    )
    with pytest.raises(GeometricRigidRefinementError, match="configured bound"):
        refiner.refine(proposal, max_steps=5)

    other_problem = DockingProblemIdentity(
        receptor_system_sha256="d" * 64,
        ligand_system_sha256="e" * 64,
    )
    mismatched = replace(proposal, problem_fingerprint_sha256=other_problem.fingerprint_sha256)
    with pytest.raises(GeometricRigidRefinementError, match="does not match"):
        refiner.refine(mismatched, max_steps=1)

    _refined, receipt = refiner.refine_with_receipt(proposal, max_steps=4)
    with pytest.raises(GeometricRigidRefinementError, match="must not increase"):
        replace(receipt, final_score=receipt.initial_score + 1.0)
    if receipt.steps:
        with pytest.raises(GeometricRigidRefinementError, match="disagree"):
            replace(
                receipt,
                final_coordinate_sha256="f" * 64,
            )


def test_geometric_refinement_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.geometric_refinement import (
        __all__ as refinement_exports,
    )

    assert set(refinement_exports) <= set(docking.__all__)
    assert GeometricRigidRefinementReceipt
