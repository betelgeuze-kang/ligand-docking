from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DOCKING_SAMPLING_POLICY_ID,
    DockingBudget,
    DockingNumericPolicy,
    DockingProblemIdentity,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
)


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.zeros((1, 3), dtype=torch.float64),
        parent=torch.tensor([-1], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]], dtype=torch.float64),
        rotatable_mask=torch.tensor([False]),
        root_positions=torch.tensor([[1.0, 0.0, 0.0]], dtype=torch.float64),
    )


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


def test_haar_rotation_stream_is_deterministic_proper_and_prefix_stable() -> None:
    space = _space()
    short_budget = DockingBudget(
        candidate_count=16,
        top_k=1,
        max_torsions=0,
        translation_radius_angstrom=0.0,
        seed=1701,
    )
    long_budget = DockingBudget(
        candidate_count=32,
        top_k=1,
        max_torsions=0,
        translation_radius_angstrom=0.0,
        seed=1701,
    )

    first = generate_bounded_docking_proposals(
        space,
        short_budget,
        problem=_problem(),
    )
    repeated = generate_bounded_docking_proposals(
        space,
        short_budget,
        problem=_problem(),
    )
    extended = generate_bounded_docking_proposals(
        space,
        long_budget,
        problem=_problem(),
    )

    assert [row.fingerprint_sha256 for row in first] == [
        row.fingerprint_sha256 for row in repeated
    ]
    assert [row.fingerprint_sha256 for row in first] == [
        row.fingerprint_sha256 for row in extended[: len(first)]
    ]
    torch.testing.assert_close(
        first[0].rotation,
        torch.eye(3, dtype=torch.float64),
        atol=0.0,
        rtol=0.0,
    )
    assert first[0].rng_state_before_sha256 == first[0].rng_state_after_sha256
    assert first[1].rng_state_before_sha256 == first[0].rng_state_after_sha256
    for proposal in first[1:]:
        torch.testing.assert_close(
            proposal.rotation.T @ proposal.rotation,
            torch.eye(3, dtype=torch.float64),
            atol=1.0e-12,
            rtol=1.0e-12,
        )
        assert torch.linalg.det(proposal.rotation).item() == pytest.approx(
            1.0,
            abs=1.0e-12,
        )


def test_haar_rotation_empirical_first_and_second_moments_match_uniform_sphere() -> None:
    proposals = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(
            candidate_count=2_048,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
            seed=99173,
        ),
        problem=_problem(),
    )
    axis = torch.tensor([0.0, 0.0, 1.0], dtype=torch.float64)
    rotated = torch.stack(
        [proposal.rotation @ axis for proposal in proposals[1:]],
        dim=0,
    )

    assert float(rotated.mean(dim=0).abs().max().item()) < 0.05
    torch.testing.assert_close(
        rotated.square().mean(dim=0),
        torch.full((3,), 1.0 / 3.0, dtype=torch.float64),
        atol=0.04,
        rtol=0.0,
    )


def test_numeric_policy_declares_exact_haar_and_draw_order() -> None:
    policy = DockingNumericPolicy(coordinate_dtype="float64")
    payload = policy.to_dict()

    assert policy.sampling_policy_id == DOCKING_SAMPLING_POLICY_ID
    assert payload["rotation_sampling"] == (
        "shoemake_three_independent_uniforms_unit_quaternion_haar_so3"
    )
    assert payload["quaternion_component_order"] == "x_y_z_w"
    assert payload["per_candidate_draw_order"] == (
        "torsions_then_haar_u1_u2_u3_then_translation_direction_then_radius"
    )


def test_haar_proposal_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.proposals import __all__ as proposal_exports

    assert set(proposal_exports) <= set(docking.__all__)
