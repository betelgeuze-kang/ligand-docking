from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import TorsionSearchSpace  # noqa: E402
from betelgeuze_engine_v2.docking.proposals import (  # noqa: E402
    DockingProposalError,
)


def _forest(root_positions: torch.Tensor | None) -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, -1, 2], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 4, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, True, False, True]),
        root_positions=root_positions,
    )


def test_multi_root_positions_use_number_of_roots_not_atom_count() -> None:
    positions = torch.tensor(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        dtype=torch.float64,
    )
    space = _forest(positions)

    assert space.root_positions is not None
    assert space.root_positions.shape == (2, 3)
    assert torch.equal(space.root_positions, positions)
    space.assert_integrity()


def test_single_root_vector_is_canonicalized_to_one_by_three() -> None:
    space = TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 2, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, True]),
        root_positions=torch.tensor([1.0, 2.0, 3.0], dtype=torch.float64),
    )

    assert space.root_positions is not None
    assert space.root_positions.shape == (1, 3)
    assert torch.equal(
        space.root_positions,
        torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float64),
    )


def test_root_position_count_mismatch_fails_closed() -> None:
    with pytest.raises(
        DockingProposalError,
        match="number_of_roots",
    ):
        _forest(torch.zeros((4, 3), dtype=torch.float64))
