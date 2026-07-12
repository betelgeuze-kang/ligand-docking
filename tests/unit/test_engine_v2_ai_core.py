from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.ai import (  # noqa: E402
    LocalEnergyConfig,
    ParityAwareLocalEnergyModel,
    PhysicsGateThresholds,
    PhysicsLossWeights,
    SparseNeighborGraph,
    TemporalStateGNN,
    TorsionTopologyGNN,
    axis_angle_matrix,
    evaluate_physics_gates,
    physics_informed_objective,
    torsion_tree_forward_kinematics,
)
from betelgeuze_engine_v2.ai import torsion as torsion_module  # noqa: E402
from betelgeuze_engine_v2.geometry import (  # noqa: E402
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import UnitCell  # noqa: E402
from betelgeuze_engine_v2.physics import (  # noqa: E402
    MAX_FIXED_PROJECTION_RANK,
    ProjectionRankError,
    fixed_rank_orthogonal_complement,
    fixed_rank_projection_adjoint,
    project_rigid_body_forces,
)


def _complete_graph(atom_count: int) -> SparseNeighborGraph:
    src: list[int] = []
    dst: list[int] = []
    for center in range(atom_count):
        for neighbor in range(atom_count):
            if center != neighbor:
                src.append(neighbor)
                dst.append(center)
    return SparseNeighborGraph.from_edges(
        torch.tensor(src),
        torch.tensor(dst),
        atom_count=atom_count,
        max_neighbors=atom_count,
    )


def _model() -> ParityAwareLocalEnergyModel:
    torch.manual_seed(1907)
    return ParityAwareLocalEnergyModel(
        LocalEnergyConfig(
            input_features=5,
            hidden_features=16,
            radial_features=8,
            layers=2,
            cutoff=5.0,
            max_neighbors=8,
        )
    ).double()


def _proper_rotation() -> torch.Tensor:
    raw = torch.tensor(
        [[0.2, -0.7, 0.4], [0.5, 0.1, -0.8], [0.9, 0.3, 0.2]], dtype=torch.float64
    )
    rotation, _ = torch.linalg.qr(raw)
    if torch.linalg.det(rotation) < 0:
        rotation[:, 0] *= -1
    return rotation


def test_local_energy_configuration_hard_caps_fail_closed() -> None:
    with pytest.raises(ValueError, match="hidden_features"):
        LocalEnergyConfig(input_features=5, hidden_features=513)
    with pytest.raises(ValueError, match="radial_features"):
        LocalEnergyConfig(input_features=5, radial_features=257)
    with pytest.raises(ValueError, match="layers"):
        LocalEnergyConfig(input_features=5, layers=17)
    with pytest.raises(ValueError, match="max_neighbors"):
        LocalEnergyConfig(input_features=5, max_neighbors=257)


def test_local_energy_is_translation_rotation_and_permutation_invariant() -> None:
    model = _model().eval()
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.1, 0.2, 0.0], [0.1, 1.3, 0.3], [-0.2, 0.4, 1.2]]],
        dtype=torch.float64,
    )
    features = torch.tensor(
        [[[1.0, 0.0, 0.2, -0.1, 0.3], [0.0, 1.0, -0.2, 0.4, 0.1],
          [0.3, -0.1, 1.0, 0.2, 0.0], [0.1, 0.5, 0.0, 1.0, -0.4]]],
        dtype=torch.float64,
    )
    graph = _complete_graph(4)
    base = model(coordinates, features, graph)
    rotation = _proper_rotation()
    moved = coordinates @ rotation.T + torch.tensor([[[7.0, -3.0, 1.5]]], dtype=torch.float64)
    transformed = model(moved, features, graph)
    assert torch.allclose(base, transformed, atol=2.0e-10, rtol=2.0e-10)

    permutation = torch.tensor([2, 0, 3, 1])
    permuted = model(coordinates[:, permutation], features[:, permutation], graph)
    assert torch.allclose(base, permuted, atol=2.0e-10, rtol=2.0e-10)


def test_parity_odd_descriptor_changes_sign_under_reflection() -> None:
    model = _model().eval()
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.1, 0.1, 0.2], [0.2, 1.3, -0.1], [-0.1, 0.3, 1.4]]],
        dtype=torch.float64,
    )
    features = torch.randn((1, 4, 5), dtype=torch.float64)
    graph = _complete_graph(4)
    original = model.energy_terms(coordinates, features, graph).parity_odd
    reflected_coordinates = coordinates.clone()
    reflected_coordinates[..., 0] *= -1.0
    reflected = model.energy_terms(reflected_coordinates, features, graph).parity_odd
    assert float(original.abs().amax()) > 1.0e-12
    assert torch.allclose(reflected, -original, atol=2.0e-10, rtol=2.0e-10)


def test_chirality_zero_crossing_has_no_absolute_value_force_cusp() -> None:
    model = _model().eval()
    features = torch.randn((1, 4, 5), dtype=torch.float64)
    graph = _complete_graph(4)

    def force_at(height: float) -> torch.Tensor:
        coordinates = torch.tensor(
            [[[0.0, 0.0, 0.0], [1.1, 0.0, 0.0], [0.0, 1.2, 0.0], [0.3, 0.4, height]]],
            dtype=torch.float64,
        )
        return model.energy_and_forces(coordinates, features, graph).forces

    epsilon = 1.0e-6
    negative = force_at(-epsilon)
    planar = force_at(0.0)
    positive = force_at(epsilon)
    assert torch.allclose(0.5 * (negative + positive), planar, atol=2.0e-6, rtol=2.0e-6)
    assert ".abs()" not in inspect.getsource(model.energy_terms)


def test_exact_energy_force_gradient_matches_finite_difference_and_rotates() -> None:
    model = _model().eval()
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.1, 0.0], [0.2, 1.1, 0.4], [0.0, 0.3, 1.5]]],
        dtype=torch.float64,
    )
    features = torch.randn((1, 4, 5), dtype=torch.float64)
    graph = _complete_graph(4)
    prediction = model.energy_and_forces(coordinates, features, graph)
    epsilon = 1.0e-5
    plus = coordinates.clone()
    minus = coordinates.clone()
    plus[0, 2, 1] += epsilon
    minus[0, 2, 1] -= epsilon
    finite_difference = (model(plus, features, graph) - model(minus, features, graph)) / (2.0 * epsilon)
    assert torch.allclose(-prediction.forces[0, 2, 1], finite_difference[0], atol=3.0e-5, rtol=3.0e-5)

    rotation = _proper_rotation()
    rotated_coordinates = coordinates @ rotation.T
    rotated = model.energy_and_forces(rotated_coordinates, features, graph)
    assert torch.allclose(rotated.energy, prediction.energy, atol=2.0e-10, rtol=2.0e-10)
    assert torch.allclose(rotated.forces, prediction.forces @ rotation.T, atol=2.0e-8, rtol=2.0e-8)
    assert prediction.diagnostics["full_hessian_materialized"] is False


def test_v2_compact_radius_graph_connects_directly_to_energy_model() -> None:
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.1, 0.0], [0.0, 0.0, 1.2]]],
        dtype=torch.float64,
    )
    neighbors = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=2.5, max_neighbors=4, max_atoms_per_cell=8),
    )
    model = _model().eval()
    features = torch.randn((1, 4, 5), dtype=torch.float64)
    prediction = model.energy_and_forces(coordinates, features, neighbors)
    assert prediction.energy.shape == (1,)
    assert prediction.forces.shape == coordinates.shape
    assert torch.isfinite(prediction.energy).all()
    assert prediction.diagnostics["constructs_nxn"] is False


def test_frozen_empty_edge_energy_returns_exact_zero_force() -> None:
    model = _model().eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    coordinates = torch.tensor([[[0.0, 0.0, 0.0]]], dtype=torch.float64)
    features = torch.randn((1, 1, 5), dtype=torch.float64)
    graph = SparseNeighborGraph.from_edges(
        torch.empty((0,), dtype=torch.long),
        torch.empty((0,), dtype=torch.long),
        atom_count=1,
        max_neighbors=1,
    )
    prediction = model.energy_and_forces(coordinates, features, graph)
    assert prediction.energy.shape == (1,)
    assert torch.equal(prediction.forces, torch.zeros_like(coordinates))


def test_frozen_empty_edge_coordinate_dependency_is_overflow_safe() -> None:
    model = _model().float().eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    coordinates = torch.tensor([[[2.0e38, 2.0e38, 2.0e38]]], dtype=torch.float32)
    features = torch.zeros((1, 1, 5), dtype=torch.float32)
    graph = SparseNeighborGraph.from_edges(
        torch.empty((0,), dtype=torch.long),
        torch.empty((0,), dtype=torch.long),
        atom_count=1,
        max_neighbors=1,
    )
    prediction = model.energy_and_forces(coordinates, features, graph)
    assert torch.isfinite(prediction.energy).all()
    assert torch.equal(prediction.forces, torch.zeros_like(coordinates))


def test_coincident_sparse_edge_fails_before_force_loss_double_backward() -> None:
    model = _model().eval()
    coordinates = torch.zeros((1, 2, 3), dtype=torch.float64, requires_grad=True)
    features = torch.randn((1, 2, 5), dtype=torch.float64)
    graph = _complete_graph(2)
    with pytest.raises(ValueError, match="coincident or numerically singular edge"):
        model.energy_and_forces(coordinates, features, graph, create_graph=True)


def test_sparse_neighbor_adapter_rejects_overflow_and_active_invalid_indices() -> None:
    invalid = SimpleNamespace(
        idx=torch.tensor([[[0, -1]]], dtype=torch.long),
        mask=torch.tensor([[[True, False]]]),
        diagnostics={"overflow": False},
        source="invalid-fixture",
    )
    with pytest.raises(ValueError, match="invalid or self"):
        SparseNeighborGraph.from_neighbor_pairs(invalid, max_neighbors=2)

    overflowed = SimpleNamespace(
        idx=torch.tensor([[[0]]], dtype=torch.long),
        mask=torch.tensor([[[False]]]),
        diagnostics={"overflow": True, "status": "blocked_capacity_overflow"},
        source="overflow-fixture",
    )
    with pytest.raises(ValueError, match="overflowed or blocked"):
        SparseNeighborGraph.from_neighbor_pairs(overflowed, max_neighbors=1)
    with pytest.raises(ValueError, match="self edges"):
        SparseNeighborGraph.from_edges(
            torch.tensor([0], dtype=torch.long),
            torch.tensor([0], dtype=torch.long),
            atom_count=1,
            max_neighbors=1,
        )


def test_periodic_energy_path_is_fail_closed_until_exact_minimum_image_gradient_exists() -> None:
    coordinates = torch.tensor(
        [[[0.2, 0.0, 0.0], [9.8, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    neighbors = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=2, max_atoms_per_cell=4),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    model = _model().eval()
    features = torch.randn((1, 2, 5), dtype=torch.float64)
    with pytest.raises(ValueError, match="periodic sparse energy is blocked"):
        model.energy_and_forces(coordinates, features, neighbors)

    adapted = SparseNeighborGraph.from_compact_neighbor_list(neighbors, max_neighbors=8)
    assert adapted.pbc_enabled is True
    assert adapted.periodic == (True, True, True)
    with pytest.raises(ValueError, match="periodic sparse energy is blocked"):
        model.energy_and_forces(coordinates, features, adapted)


def test_learned_messages_decay_continuously_to_zero_at_cutoff() -> None:
    model = _model().eval()
    features = torch.randn((1, 2, 5), dtype=torch.float64)
    epsilon = 1.0e-5

    just_inside = torch.tensor(
        [[[0.0, 0.0, 0.0], [5.0 - epsilon, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    just_outside = torch.tensor(
        [[[0.0, 0.0, 0.0], [5.0 + epsilon, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    inside_graph = _complete_graph(2)
    outside_graph = _complete_graph(2)
    inside_energy = model(just_inside, features, inside_graph)
    outside_energy = model(just_outside, features, outside_graph)

    assert torch.allclose(inside_energy, outside_energy, atol=1.0e-8, rtol=1.0e-8)


def test_cutoff_crossing_does_not_renormalize_fixed_neighbor_messages() -> None:
    model = _model().eval()
    features = torch.randn((1, 3, 5), dtype=torch.float64)
    graph = _complete_graph(3)
    epsilon = 1.0e-7
    inside = torch.tensor(
        [[[0.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [5.0 - epsilon, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    outside = torch.tensor(
        [[[0.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [5.0 + epsilon, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    inside_prediction = model.energy_and_forces(inside, features, graph)
    outside_prediction = model.energy_and_forces(outside, features, graph)
    assert torch.allclose(
        inside_prediction.energy,
        outside_prediction.energy,
        atol=2.0e-9,
        rtol=2.0e-9,
    )
    assert torch.allclose(
        inside_prediction.forces,
        outside_prediction.forces,
        atol=2.0e-7,
        rtol=2.0e-7,
    )


def test_fixed_rank_projection_is_matrix_free_orthogonal_and_has_correct_adjoint() -> None:
    torch.manual_seed(44)
    values = torch.randn((2, 7, 3), dtype=torch.float64, requires_grad=True)
    basis = torch.randn((2, 7, 3, 3), dtype=torch.float64)
    projected, diagnostics = fixed_rank_orthogonal_complement(
        values, basis, return_diagnostics=True
    )
    overlap = (basis * projected.unsqueeze(-1)).sum(dim=(1, 2))
    assert torch.allclose(overlap, torch.zeros_like(overlap), atol=2.0e-9, rtol=2.0e-9)
    assert diagnostics.constructs_nxn is False

    cotangent = torch.randn_like(projected)
    (projected * cotangent).sum().backward()
    expected = fixed_rank_projection_adjoint(cotangent, basis)
    assert values.grad is not None
    assert torch.allclose(values.grad, expected, atol=2.0e-9, rtol=2.0e-9)


def test_coordinate_dependent_projection_basis_keeps_exact_basis_gradient() -> None:
    torch.manual_seed(73)
    coordinates = torch.randn((1, 5, 3), dtype=torch.float64, requires_grad=True)
    values = torch.randn((1, 5, 3), dtype=torch.float64)

    def projected_loss(current: torch.Tensor) -> torch.Tensor:
        basis = torch.stack((current, torch.roll(current, shifts=1, dims=1)), dim=-1)
        projected = fixed_rank_orthogonal_complement(values, basis)
        return projected.square().sum()

    loss = projected_loss(coordinates)
    analytical = torch.autograd.grad(loss, coordinates)[0]
    epsilon = 1.0e-6
    plus = coordinates.detach().clone()
    minus = coordinates.detach().clone()
    plus[0, 3, 1] += epsilon
    minus[0, 3, 1] -= epsilon
    finite_difference = (projected_loss(plus) - projected_loss(minus)) / (2.0 * epsilon)
    assert torch.allclose(analytical[0, 3, 1], finite_difference, atol=2.0e-5, rtol=2.0e-5)


def test_projection_gradient_is_finite_for_repeated_gram_eigenvalues_and_rank_fails_closed() -> None:
    torch.manual_seed(91)
    raw = torch.randn((6, 3), dtype=torch.float64)
    orthonormal, _ = torch.linalg.qr(raw, mode="reduced")
    basis = orthonormal.reshape(2, 3, 3).detach().requires_grad_(True)
    values = torch.randn((2, 3), dtype=torch.float64)

    loss = fixed_rank_orthogonal_complement(values, basis).square().sum()
    gradient = torch.autograd.grad(loss, basis)[0]
    assert torch.isfinite(gradient).all()

    epsilon = 1.0e-6
    plus = basis.detach().clone()
    minus = basis.detach().clone()
    plus[1, 2, 0] += epsilon
    minus[1, 2, 0] -= epsilon
    finite_difference = (
        fixed_rank_orthogonal_complement(values, plus).square().sum()
        - fixed_rank_orthogonal_complement(values, minus).square().sum()
    ) / (2.0 * epsilon)
    assert torch.allclose(gradient[1, 2, 0], finite_difference, atol=2.0e-5, rtol=2.0e-5)

    duplicate = torch.stack((basis.detach()[..., 0], basis.detach()[..., 0]), dim=-1)
    with pytest.raises(ProjectionRankError, match="full-rank"):
        fixed_rank_orthogonal_complement(values, duplicate)

    with pytest.raises(ValueError, match="unbatched projection"):
        fixed_rank_orthogonal_complement(
            torch.tensor([[1.0, 2.0], [10.0, 20.0]], dtype=torch.float64),
            torch.ones((2, 2, 1), dtype=torch.float64),
        )
    with pytest.raises(ValueError, match="hard cap"):
        fixed_rank_orthogonal_complement(
            values,
            basis.detach(),
            max_rank=MAX_FIXED_PROJECTION_RANK + 1,
        )


def test_rigid_body_projection_removes_net_force_and_torque_without_nxn() -> None:
    torch.manual_seed(12)
    coordinates = torch.randn((2, 9, 3), dtype=torch.float64)
    forces = torch.randn_like(coordinates)
    projected, diagnostics = project_rigid_body_forces(
        coordinates, forces, return_diagnostics=True
    )
    centered = coordinates - coordinates.mean(dim=1, keepdim=True)
    torque = torch.cross(centered, projected, dim=-1).sum(dim=1)
    assert torch.allclose(projected.sum(dim=1), torch.zeros((2, 3), dtype=torch.float64), atol=2.0e-9)
    assert torch.allclose(torque, torch.zeros((2, 3), dtype=torch.float64), atol=2.0e-9)
    assert diagnostics.constructs_nxn is False
    assert diagnostics.rank == 6


def test_rigid_projection_coordinate_gradient_is_finite_for_isotropic_inertia() -> None:
    coordinates = torch.tensor(
        [[
            [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0], [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0], [0.0, 0.0, -1.0],
        ]],
        dtype=torch.float64,
        requires_grad=True,
    )
    torch.manual_seed(113)
    forces = torch.randn_like(coordinates)

    loss = project_rigid_body_forces(coordinates, forces).square().sum()
    analytical = torch.autograd.grad(loss, coordinates)[0]
    assert torch.isfinite(analytical).all()

    epsilon = 1.0e-6
    plus = coordinates.detach().clone()
    minus = coordinates.detach().clone()
    plus[0, 0, 1] += epsilon
    minus[0, 0, 1] -= epsilon
    finite_difference = (
        project_rigid_body_forces(plus, forces).square().sum()
        - project_rigid_body_forces(minus, forces).square().sum()
    ) / (2.0 * epsilon)
    assert torch.allclose(analytical[0, 0, 1], finite_difference, atol=3.0e-5, rtol=3.0e-5)

    collinear = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    with pytest.raises(ProjectionRankError, match="full-rank"):
        project_rigid_body_forces(collinear, torch.randn_like(collinear))
    with pytest.raises(TypeError, match="atom_mask must be boolean"):
        project_rigid_body_forces(
            coordinates.detach(),
            forces,
            atom_mask=torch.ones((1, 6), dtype=torch.float64),
        )


def test_torsion_tree_uses_linear_edge_work_and_differentiable_kinematics() -> None:
    atom_count = 41
    parent = torch.tensor([-1] + list(range(atom_count - 1)), dtype=torch.long)
    model = TorsionTopologyGNN(5, hidden_features=12, output_features=7).double()
    features = torch.randn((1, atom_count, 5), dtype=torch.float64, requires_grad=True)
    processed_edges = {"up": 0, "down": 0}

    def record_up(_module, inputs, _output):
        processed_edges["up"] += int(inputs[0].shape[-2])

    def record_down(_module, inputs, _output):
        processed_edges["down"] += int(inputs[0].shape[-2])

    handles = [model.up_message.register_forward_hook(record_up), model.down_message.register_forward_hook(record_down)]
    output = model(features, parent)
    for handle in handles:
        handle.remove()
    assert output.shape == (1, atom_count, 7)
    assert processed_edges == {"up": atom_count - 1, "down": atom_count - 1}
    output.square().mean().backward()
    assert features.grad is not None and torch.isfinite(features.grad).all()
    source = inspect.getsource(torsion_module.TorsionTopologyGNN.forward)
    assert "for node in order if" not in source

    local_offsets = torch.zeros((atom_count, 3), dtype=torch.float64)
    local_offsets[:, 0] = 1.0
    angles = torch.linspace(0.0, 0.5, atom_count, dtype=torch.float64, requires_grad=True)
    kinematics = torsion_tree_forward_kinematics(local_offsets, parent, angles)
    assert kinematics.coordinates.shape == (atom_count, 3)
    assert kinematics.diagnostics["constructs_full_jacobian"] is False
    kinematics.coordinates.square().sum().backward()
    assert angles.grad is not None and torch.isfinite(angles.grad).all()


def test_axis_angle_rotation_is_orthogonal_and_zero_axis_fails_closed() -> None:
    axis = torch.tensor([[1.0, 2.0, 3.0]], dtype=torch.float64)
    angle = torch.tensor([0.7], dtype=torch.float64)
    rotation = axis_angle_matrix(axis, angle)
    identity = torch.eye(3, dtype=torch.float64).unsqueeze(0)
    assert torch.allclose(rotation.transpose(-1, -2) @ rotation, identity, atol=2.0e-12)
    assert torch.allclose(torch.linalg.det(rotation), torch.ones(1, dtype=torch.float64), atol=2.0e-12)

    with pytest.raises(ValueError, match="nonzero rotation angle"):
        axis_angle_matrix(torch.zeros_like(axis), torch.ones_like(angle))
    with pytest.raises(ValueError, match="epsilon must be finite and positive"):
        axis_angle_matrix(axis, angle, epsilon=float("nan"))
    zero_rotation = axis_angle_matrix(torch.zeros_like(axis), torch.zeros_like(angle))
    assert torch.equal(zero_rotation, identity)


def test_temporal_gnn_is_sparse_recurrent_and_models_contain_no_attention_modules() -> None:
    graph = _complete_graph(4)
    temporal = TemporalStateGNN(5, hidden_features=11, max_neighbors=8).double()
    sequence = torch.randn((3, 1, 4, 5), dtype=torch.float64, requires_grad=True)
    rollout = temporal.rollout(sequence, graph, detach_interval=2)
    assert rollout.states.shape == (3, 1, 4, 11)
    assert rollout.diagnostics["full_sequence_pair_matrix"] is False
    rollout.final_state.square().mean().backward()
    assert sequence.grad is not None

    streamed_sequence = torch.randn((5, 1, 4, 5), dtype=torch.float64, requires_grad=True)
    streamed = temporal.rollout(
        streamed_sequence,
        graph,
        detach_interval=2,
        return_history=False,
    )
    assert streamed.states is None
    assert streamed.diagnostics["history_returned"] is False
    assert streamed.diagnostics["retained_state_memory"].startswith("O(W*N*C)")
    streamed.final_state.square().mean().backward()
    assert streamed_sequence.grad is not None

    prohibited = (
        torch.nn.MultiheadAttention,
        torch.nn.Transformer,
        torch.nn.TransformerEncoder,
        torch.nn.TransformerEncoderLayer,
        torch.nn.TransformerDecoder,
        torch.nn.TransformerDecoderLayer,
    )
    for candidate in (_model(), temporal, TorsionTopologyGNN(5, 8, 8)):
        assert candidate.uses_pairwise_attention is False
        assert not any(isinstance(module, prohibited) for module in candidate.modules())


def test_physics_objective_supports_vjp_training_and_gate_fails_closed() -> None:
    model = _model().train()
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.1, 0.1, 0.0], [0.2, 1.2, 0.3], [0.0, 0.2, 1.4]]],
        dtype=torch.float64,
        requires_grad=True,
    )
    features = torch.randn((1, 4, 5), dtype=torch.float64)
    prediction = model.energy_and_forces(coordinates, features, _complete_graph(4), create_graph=True)
    objective = physics_informed_objective(
        prediction.energy,
        prediction.forces,
        coordinates=coordinates,
        reference_energy=torch.zeros_like(prediction.energy),
        reference_forces=torch.zeros_like(prediction.forces),
        weights=PhysicsLossWeights(net_force=0.01, net_torque=0.01),
    )
    objective.total.backward()
    assert objective.diagnostics["full_hessian_materialized"] is False
    assert any(parameter.grad is not None for parameter in model.parameters())

    blocked = evaluate_physics_gates(prediction.energy, prediction.forces, coordinates)
    assert blocked.passed is False
    assert "finite_difference_evidence_missing" in blocked.blockers
    assert "equivariance_evidence_missing" in blocked.blockers
    assert "applicability_domain_unproven" in blocked.blockers

    nonfinite_evidence = evaluate_physics_gates(
        prediction.energy,
        prediction.forces,
        coordinates,
        finite_difference_error=float("nan"),
        equivariance_error=float("nan"),
        applicability_in_domain=True,
    )
    assert nonfinite_evidence.passed is False
    assert "finite_difference_evidence_nonfinite" in nonfinite_evidence.blockers
    assert "equivariance_evidence_nonfinite" in nonfinite_evidence.blockers

    with pytest.raises(ValueError, match="finite and non-negative"):
        PhysicsGateThresholds(max_net_force=float("nan"))
    with pytest.raises(ValueError, match="nonempty batch and atom set"):
        evaluate_physics_gates(
            torch.zeros((1,), dtype=torch.float64),
            torch.zeros((1, 0, 3), dtype=torch.float64),
            torch.zeros((1, 0, 3), dtype=torch.float64),
            finite_difference_error=0.0,
            equivariance_error=0.0,
            applicability_in_domain=True,
        )
