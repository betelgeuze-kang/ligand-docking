from __future__ import annotations

import inspect

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    ATOM_FEATURE_NAMES,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    NeighborOverflowError,
    RadiusGraphConfig,
    Residue,
    StructureProvenance,
    UnitCell,
    build_compact_radius_graph,
    build_deterministic_atom_features,
)
from betelgeuze_engine_v2.geometry import neighbors as neighbor_module  # noqa: E402


def _system(coordinates: torch.Tensor | None = None) -> AllAtomSystem:
    if coordinates is None:
        coordinates = torch.tensor(
            [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [0.0, 1.4, 0.0], [0.0, 0.0, 1.6]]],
            dtype=torch.float64,
        )
    return AllAtomSystem(
        system_id="feature-fixture",
        atoms=(
            Atom(index=0, name="C1", element="C", atomic_number=6, residue_index=0, isotope_mass_number=13, stereo="R"),
            Atom(index=1, name="N1", element="N", atomic_number=7, residue_index=0),
            Atom(index=2, name="O1", element="O", atomic_number=8, residue_index=0),
            Atom(index=3, name="H1", element="H", atomic_number=1, residue_index=0),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=2.0, stereo="E"),
            Bond(index=1, atom_i=0, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coordinates,
        provenance=StructureProvenance(
            source_format="unit_test",
            source_sha256="a" * 64,
        ),
    )


def _directed_pair_set(graph) -> set[tuple[int, int]]:
    triplets = graph.edge_triplets().detach().cpu().T.tolist()
    return {(int(source), int(target)) for _, source, target in triplets}


def test_features_are_coordinate_independent_and_encode_declared_identity() -> None:
    first = build_deterministic_atom_features(_system())
    moved = build_deterministic_atom_features(_system(_system().coordinates + 50.0))
    assert torch.equal(first.values, moved.values)
    assert first.values.shape == (1, 4, len(ATOM_FEATURE_NAMES))
    isotope_value = ATOM_FEATURE_NAMES.index("isotope_mass_number_scaled")
    isotope_present = ATOM_FEATURE_NAMES.index("isotope_mass_number_present")
    stereo_r = ATOM_FEATURE_NAMES.index("stereo_r")
    stereo_e = ATOM_FEATURE_NAMES.index("stereo_e_bond_count_squashed")
    assert first.values[0, 0, isotope_value].item() == pytest.approx(13.0 / 350.0)
    assert first.values[0, 0, isotope_present].item() == 1.0
    assert first.values[0, 0, stereo_r].item() == 1.0
    assert first.values[0, 0, stereo_e].item() > 0.0
    assert first.diagnostics["parameterization_inferred"] is False
    assert first.diagnostics["constructs_pair_matrix"] is False
    assert first.diagnostics["scientific_claim_safe"] is False


def test_sparse_graph_is_permutation_equivalent_without_dense_pair_allocation() -> None:
    coordinates = _system().coordinates
    config = RadiusGraphConfig(cutoff_angstrom=2.1, max_neighbors=3, max_atoms_per_cell=4)
    original = build_compact_radius_graph(coordinates, config)

    permutation = torch.tensor([2, 0, 3, 1], dtype=torch.long)
    inverse = torch.empty_like(permutation)
    inverse[permutation] = torch.arange(4)
    permuted = build_compact_radius_graph(coordinates[:, permutation], config)
    remapped_pairs = {
        (int(permutation[source]), int(permutation[target]))
        for source, target in _directed_pair_set(permuted)
    }
    assert remapped_pairs == _directed_pair_set(original)
    assert original.diagnostics.nxn_allocation_observed is False
    assert original.diagnostics.capacity_contract_satisfied is True
    assert original.diagnostics.expected_complexity.startswith("O(B*N)")


def test_real_neighbor_builder_has_deterministic_cutoff_membership() -> None:
    cutoff = 2.0
    config = RadiusGraphConfig(cutoff_angstrom=cutoff, max_neighbors=2, max_atoms_per_cell=2)

    def pair_count(distance: float) -> int:
        coordinates = torch.tensor([[[0.0, 0.0, 0.0], [distance, 0.0, 0.0]]], dtype=torch.float64)
        return build_compact_radius_graph(coordinates, config).pair_count

    assert pair_count(cutoff - 1.0e-8) == 2
    assert pair_count(cutoff) == 2
    assert pair_count(cutoff + 1.0e-8) == 0


def test_periodic_graph_records_image_shifts_and_preserves_coordinate_gradients() -> None:
    coordinates = torch.tensor(
        [[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]],
        dtype=torch.float64,
        requires_grad=True,
    )
    cell = UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64)
    graph = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=1, max_atoms_per_cell=2),
        cell=cell,
    )
    assert graph.pair_count == 2
    assert graph.distances[graph.mask].tolist() == pytest.approx([0.4, 0.4])
    shifts = graph.image_shifts[graph.mask].detach().cpu().tolist()
    assert shifts == [[-1, 0, 0], [1, 0, 0]]

    graph.distances[graph.mask].sum().backward()
    assert coordinates.grad is not None
    assert torch.isfinite(coordinates.grad).all()
    assert torch.allclose(
        coordinates.grad.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=1.0e-12,
        rtol=0.0,
    )


def test_neighbor_and_cell_capacity_overflow_fail_closed() -> None:
    dense = torch.zeros((1, 4, 3), dtype=torch.float64)
    with pytest.raises(NeighborOverflowError) as cell_overflow:
        build_compact_radius_graph(
            dense,
            RadiusGraphConfig(cutoff_angstrom=2.0, max_neighbors=3, max_atoms_per_cell=2),
        )
    assert cell_overflow.value.diagnostics.overflow_kind == "cell_capacity"

    spread = torch.tensor(
        [[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.5, 0.0]]],
        dtype=torch.float64,
    )
    with pytest.raises(NeighborOverflowError) as neighbor_overflow:
        build_compact_radius_graph(
            spread,
            RadiusGraphConfig(cutoff_angstrom=2.0, max_neighbors=1, max_atoms_per_cell=3),
        )
    assert neighbor_overflow.value.diagnostics.overflow_kind == "neighbor_capacity"


def test_sparse_source_contains_no_dense_distance_constructor() -> None:
    source = inspect.getsource(neighbor_module)
    prohibited = ("torch." + "cdist", "torch." + "pdist", "[N, N]")
    assert all(token not in source for token in prohibited)
