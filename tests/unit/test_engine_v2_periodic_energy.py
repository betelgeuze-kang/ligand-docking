from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.ai import (  # noqa: E402
    LocalEnergyConfig,
    ParityAwareLocalEnergyModel,
    SparseNeighborGraph,
)
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph  # noqa: E402
from betelgeuze_engine_v2.molecular import UnitCell  # noqa: E402


def _model() -> ParityAwareLocalEnergyModel:
    torch.manual_seed(507)
    return ParityAwareLocalEnergyModel(
        LocalEnergyConfig(
            input_features=4,
            hidden_features=12,
            radial_features=6,
            layers=2,
            cutoff=2.0,
            max_neighbors=4,
        )
    ).double().eval()


def _periodic_graph(coordinates: torch.Tensor, cell: UnitCell) -> SparseNeighborGraph:
    compact = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=2, max_atoms_per_cell=4),
        cell=cell,
    )
    return SparseNeighborGraph.from_compact_neighbor_list(
        compact,
        max_neighbors=4,
        cell=cell,
    )


def test_periodic_compact_input_without_cell_fails_closed() -> None:
    coordinates = torch.tensor(
        [[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    cell = UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64)
    compact = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=2, max_atoms_per_cell=4),
        cell=cell,
    )
    features = torch.randn((1, 2, 4), dtype=torch.float64)

    with pytest.raises(ValueError, match="periodic sparse energy is blocked"):
        _model().energy_and_forces(coordinates, features, compact)


def test_periodic_energy_and_force_use_exact_image_shift_gradient() -> None:
    coordinates = torch.tensor(
        [[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    cell = UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64)
    graph = _periodic_graph(coordinates, cell)
    features = torch.tensor(
        [[[1.0, 0.2, -0.1, 0.5], [0.3, -0.4, 0.8, 0.1]]],
        dtype=torch.float64,
    )
    model = _model()
    prediction = model.energy_and_forces(coordinates, features, graph)

    assert prediction.energy.shape == (1,)
    assert prediction.forces.shape == coordinates.shape
    assert torch.isfinite(prediction.energy).all()
    assert torch.isfinite(prediction.forces).all()
    assert prediction.diagnostics["periodic_image_gradient_path"] is True
    assert prediction.diagnostics["periodic_geometry_ready"] is True
    assert prediction.energy_descriptor.unit is None
    assert prediction.energy_descriptor.physical_quantity is False
    assert prediction.force_descriptor.unit is None
    assert prediction.force_descriptor.physical_quantity is False
    assert torch.allclose(
        prediction.forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=2.0e-10,
        rtol=0.0,
    )

    epsilon = 1.0e-5
    plus = coordinates.clone()
    minus = coordinates.clone()
    plus[0, 0, 0] += epsilon
    minus[0, 0, 0] -= epsilon
    finite_difference = (
        model(plus, features, graph) - model(minus, features, graph)
    ) / (2.0 * epsilon)
    assert torch.allclose(
        -prediction.forces[0, 0, 0],
        finite_difference[0],
        atol=4.0e-5,
        rtol=4.0e-5,
    )


def test_equivalent_wrapped_coordinates_produce_same_periodic_result() -> None:
    first = torch.tensor(
        [[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    second = torch.tensor(
        [[[0.2, 0.0, 0.0], [-0.2, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    cell = UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64)
    features = torch.tensor(
        [[[0.1, 0.5, -0.2, 1.0], [0.7, -0.3, 0.4, 0.2]]],
        dtype=torch.float64,
    )
    model = _model()
    first_result = model.energy_and_forces(first, features, _periodic_graph(first, cell))
    second_result = model.energy_and_forces(second, features, _periodic_graph(second, cell))

    assert torch.allclose(first_result.energy, second_result.energy, atol=2.0e-10, rtol=2.0e-10)
    assert torch.allclose(first_result.forces, second_result.forces, atol=2.0e-8, rtol=2.0e-8)
