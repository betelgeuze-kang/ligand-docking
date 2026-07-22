from __future__ import annotations

from dataclasses import replace
import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.geometry import (  # noqa: E402
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_ewald import (  # noqa: E402
    REFERENCE_EWALD_ALGORITHM_ID,
    REFERENCE_EWALD_SCIENTIFIC_BLOCKERS,
    ReferenceEwaldConfig,
    ReferenceEwaldError,
    evaluate_reference_force_field_with_ewald,
)
from betelgeuze_engine_v2.physics.reference_forcefield import (  # noqa: E402
    evaluate_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    AtomNonbondedParameter,
    PairScalingParameter,
    ReferenceForceFieldParameters,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    cell: UnitCell | None = None,
    dtype: torch.dtype = torch.float64,
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"X{index + 1}",
            element="C",
            atomic_number=atomic_number_for_element("C"),
            residue_index=0,
            partial_charge_e=0.0,
            mass_da=12.0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="reference-ewald-unit-system",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="EWALD",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=dtype),
        provenance=StructureProvenance(source_format="unit-test"),
        cell=(
            UnitCell.orthorhombic(
                (20.0, 22.0, 24.0),
                dtype=dtype,
            )
            if cell is None
            else cell
        ),
    )


def _parameters(
    system: AllAtomSystem,
    charges: tuple[float, ...],
    *,
    excluded_pairs: tuple[tuple[int, int], ...] = (),
    scaled_pairs: tuple[PairScalingParameter, ...] = (),
    screening_kappa_per_angstrom: float = 0.0,
) -> ReferenceForceFieldParameters:
    return ReferenceForceFieldParameters(
        parameter_set_id="reference-ewald-unit-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=index,
                sigma_angstrom=3.0,
                epsilon_kcal_per_mol=0.0,
                charge_e=charge,
            )
            for index, charge in enumerate(charges)
        ),
        excluded_pairs=excluded_pairs,
        scaled_pairs=scaled_pairs,
        cutoff_angstrom=8.0,
        switch_start_angstrom=6.0,
        screening_kappa_per_angstrom=screening_kappa_per_angstrom,
    )


def _neighbors(system: AllAtomSystem, cutoff: float = 8.0):
    return build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=cutoff,
            max_neighbors=32,
            max_atoms_per_cell=32,
        ),
        cell=system.cell,
    )


def _evaluate(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceEwaldConfig,
):
    return evaluate_reference_force_field_with_ewald(
        system,
        _neighbors(system, parameters.cutoff_angstrom),
        parameters,
        config,
    )


def _independent_two_charge_energy(
    system: AllAtomSystem,
    charges: tuple[float, float],
    config: ReferenceEwaldConfig,
    cutoff: float,
) -> float:
    lengths = tuple(
        float(value)
        for value in system.cell.orthorhombic_lengths().detach().cpu().tolist()
    )
    raw = [
        float(system.coordinates[0, 0, axis] - system.coordinates[0, 1, axis])
        for axis in range(3)
    ]
    displacement = [
        value - round(value / length) * length
        for value, length in zip(raw, lengths)
    ]
    distance = math.sqrt(sum(value * value for value in displacement))
    alpha = config.alpha_per_angstrom
    real = charges[0] * charges[1] * (
        math.erfc(alpha * distance) / distance
        - math.erfc(alpha * cutoff) / cutoff
    )
    reciprocal = 0.0
    limits = config.reciprocal_max_indices
    volume = math.prod(lengths)
    coordinates = [
        [
            float(system.coordinates[0, atom, axis]) % lengths[axis]
            for axis in range(3)
        ]
        for atom in range(2)
    ]
    for first in range(-limits[0], limits[0] + 1):
        for second in range(-limits[1], limits[1] + 1):
            for third in range(-limits[2], limits[2] + 1):
                if (first, second, third) == (0, 0, 0):
                    continue
                vector = (
                    2.0 * math.pi * first / lengths[0],
                    2.0 * math.pi * second / lengths[1],
                    2.0 * math.pi * third / lengths[2],
                )
                norm2 = sum(value * value for value in vector)
                structure_real = 0.0
                structure_imag = 0.0
                for charge, coordinate in zip(charges, coordinates):
                    phase = sum(
                        value * position
                        for value, position in zip(vector, coordinate)
                    )
                    structure_real += charge * math.cos(phase)
                    structure_imag += charge * math.sin(phase)
                reciprocal += (
                    math.exp(-norm2 / (4.0 * alpha * alpha))
                    / norm2
                    * (structure_real * structure_real + structure_imag * structure_imag)
                )
    reciprocal *= 2.0 * math.pi / volume
    self_energy = -alpha / math.sqrt(math.pi) * sum(
        charge * charge for charge in charges
    )
    return COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * (
        real + reciprocal + self_energy
    )


def test_config_is_canonical_and_bounded() -> None:
    config = ReferenceEwaldConfig(
        alpha_per_angstrom=0.3,
        reciprocal_max_indices=(3, 4, 5),
        neutrality_tolerance_e=1.0e-13,
    )
    payload = config.to_dict()

    assert payload["algorithm_id"] == REFERENCE_EWALD_ALGORITHM_ID
    assert payload["reciprocal_vector_count"] == 692
    assert ReferenceEwaldConfig.from_dict(payload) == config
    assert ReferenceEwaldConfig.from_dict(payload).fingerprint_sha256 == (
        config.fingerprint_sha256
    )

    with pytest.raises(ReferenceEwaldError, match="vector-count limit"):
        ReferenceEwaldConfig(reciprocal_max_indices=(16, 16, 16))
    with pytest.raises(ReferenceEwaldError, match="must be an integer"):
        ReferenceEwaldConfig(reciprocal_max_indices=(True, 2, 2))
    with pytest.raises(ReferenceEwaldError, match="net_charge_policy"):
        ReferenceEwaldConfig(net_charge_policy="uniform_background")


def test_direct_ewald_components_match_independent_scalar_oracle() -> None:
    system = _system(((1.2, 2.3, 3.4), (4.1, 2.0, 3.8)))
    charges = (1.0, -1.0)
    parameters = _parameters(system, charges)
    config = ReferenceEwaldConfig(
        alpha_per_angstrom=0.32,
        reciprocal_max_indices=(5, 6, 7),
    )

    result = _evaluate(system, parameters, config)
    observed = float(result.electrostatics_term.energy.item())
    expected = _independent_two_charge_energy(
        system,
        charges,
        config,
        parameters.cutoff_angstrom,
    )

    assert observed == pytest.approx(expected, abs=2.0e-11, rel=0.0)
    assert result.real_pair_count == 1
    assert result.reciprocal_vector_count == config.reciprocal_vector_count
    assert set(result.component_energies) == {
        "harmonic_bond",
        "harmonic_angle",
        "periodic_torsion",
        "lennard_jones",
        "ewald_real",
        "ewald_reciprocal",
        "ewald_self",
        "ewald_pair_scaling_correction",
    }
    assert result.scientific_blockers == REFERENCE_EWALD_SCIENTIFIC_BLOCKERS
    assert result.scientifically_validated is False
    assert result.claim_safe is False


def test_direct_ewald_force_matches_central_energy_difference() -> None:
    system = _system(((1.7, 3.1, 4.0), (5.2, 2.4, 3.5)))
    parameters = _parameters(system, (0.75, -0.75))
    config = ReferenceEwaldConfig(
        alpha_per_angstrom=0.34,
        reciprocal_max_indices=(5, 5, 6),
    )
    result = _evaluate(system, parameters, config)
    step = 1.0e-5
    shifted = []
    for sign in (1.0, -1.0):
        coordinates = system.coordinates.detach().clone()
        coordinates[0, 0, 0] += sign * step
        moved = replace(system, coordinates=coordinates)
        shifted.append(float(_evaluate(moved, parameters, config).term.energy.item()))
    finite_difference_force = -(shifted[0] - shifted[1]) / (2.0 * step)

    assert float(result.term.forces[0, 0, 0].item()) == pytest.approx(
        finite_difference_force,
        abs=2.0e-7,
        rel=0.0,
    )
    torch.testing.assert_close(
        result.electrostatics_term.forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=3.0e-13,
        rtol=0.0,
    )


def test_reciprocal_truncation_converges_toward_larger_bound() -> None:
    system = _system(((1.3, 2.1, 3.7), (6.2, 4.8, 2.9), (9.4, 8.2, 7.1)))
    parameters = _parameters(system, (0.7, -0.2, -0.5))
    evaluations = {
        bound: _evaluate(
            system,
            parameters,
            ReferenceEwaldConfig(
                alpha_per_angstrom=0.35,
                reciprocal_max_indices=(bound, bound, bound),
            ),
        )
        for bound in (1, 3, 5, 8)
    }
    reference = evaluations[8]
    energy_errors = {
        bound: abs(
            float(
                evaluations[bound].electrostatics_term.energy
                - reference.electrostatics_term.energy
            )
        )
        for bound in (1, 3, 5)
    }
    force_errors = {
        bound: float(
            (
                evaluations[bound].electrostatics_term.forces
                - reference.electrostatics_term.forces
            )
            .abs()
            .max()
            .item()
        )
        for bound in (1, 3, 5)
    }

    assert energy_errors[5] < energy_errors[3] < energy_errors[1]
    assert force_errors[5] < force_errors[3] < force_errors[1]
    assert energy_errors[5] > 0.0
    assert force_errors[5] > 0.0


def test_periodic_images_and_global_translation_are_invariant() -> None:
    system = _system(((0.7, 1.1, 2.2), (6.3, 5.0, 3.4), (10.2, 7.1, 9.0)))
    parameters = _parameters(system, (0.8, -0.3, -0.5))
    config = ReferenceEwaldConfig(reciprocal_max_indices=(6, 6, 6))
    reference = _evaluate(system, parameters, config)

    translated_coordinates = system.coordinates + torch.tensor(
        [[[20.0, -44.0, 48.0]]],
        dtype=torch.float64,
    )
    translated = _evaluate(
        replace(system, coordinates=translated_coordinates),
        parameters,
        config,
    )
    image_coordinates = system.coordinates.detach().clone()
    image_coordinates[0, 1, 0] += 20.0
    imaged = _evaluate(
        replace(system, coordinates=image_coordinates),
        parameters,
        config,
    )

    torch.testing.assert_close(
        translated.term.energy,
        reference.term.energy,
        atol=2.0e-12,
        rtol=0.0,
    )
    torch.testing.assert_close(
        translated.term.forces,
        reference.term.forces,
        atol=2.0e-12,
        rtol=0.0,
    )
    torch.testing.assert_close(
        imaged.term.energy,
        reference.term.energy,
        atol=2.0e-12,
        rtol=0.0,
    )
    torch.testing.assert_close(
        imaged.term.forces,
        reference.term.forces,
        atol=2.0e-12,
        rtol=0.0,
    )


def test_excluded_and_scaled_pairs_apply_reciprocal_correction() -> None:
    system = _system(((1.0, 1.0, 1.0), (4.0, 1.0, 1.0)))
    config = ReferenceEwaldConfig(
        alpha_per_angstrom=0.31,
        reciprocal_max_indices=(6, 6, 6),
    )
    full = _evaluate(system, _parameters(system, (1.0, -1.0)), config)
    excluded = _evaluate(
        system,
        _parameters(system, (1.0, -1.0), excluded_pairs=((0, 1),)),
        config,
    )
    scaled = _evaluate(
        system,
        _parameters(
            system,
            (1.0, -1.0),
            scaled_pairs=(
                PairScalingParameter(
                    atom_i=0,
                    atom_j=1,
                    lj_scale=1.0,
                    electrostatic_scale=0.5,
                ),
            ),
        ),
        config,
    )
    distance = 3.0
    shifted_coulomb = (
        1.0 / distance
        - math.erfc(
            config.alpha_per_angstrom * 8.0
        )
        / 8.0
    )
    charge_product = -1.0
    excluded_delta = (
        -1.0
        * COULOMB_KCAL_ANGSTROM_PER_MOL_E2
        * charge_product
        * shifted_coulomb
    )
    scaled_delta = 0.5 * excluded_delta

    assert float(excluded.term.energy - full.term.energy) == pytest.approx(
        excluded_delta,
        abs=2.0e-11,
        rel=0.0,
    )
    assert float(scaled.term.energy - full.term.energy) == pytest.approx(
        scaled_delta,
        abs=2.0e-11,
        rel=0.0,
    )
    assert float(excluded.component_energies["ewald_real"].item()) == 0.0
    assert float(excluded.component_energies["ewald_pair_scaling_correction"].item()) != 0.0


def test_zero_charge_replacement_is_exactly_equal_to_frozen_v1() -> None:
    system = _system(((1.0, 2.0, 3.0), (4.0, 2.0, 3.0)))
    parameters = _parameters(system, (0.0, 0.0))
    neighbors = _neighbors(system)
    base = evaluate_reference_force_field(system, neighbors, parameters)
    result = evaluate_reference_force_field_with_ewald(
        system,
        neighbors,
        parameters,
        ReferenceEwaldConfig(),
    )

    assert torch.equal(result.term.energy, base.term.energy)
    assert torch.equal(result.term.forces, base.term.forces)
    assert float(result.electrostatics_term.energy.item()) == 0.0


def test_applicability_fails_closed_for_ambiguous_electrostatics() -> None:
    system = _system(((1.0, 2.0, 3.0), (4.0, 2.0, 3.0)))
    config = ReferenceEwaldConfig()

    with pytest.raises(ReferenceEwaldError, match="net charge"):
        _evaluate(system, _parameters(system, (1.0, -0.9)), config)
    with pytest.raises(ReferenceEwaldError, match="zero screened-Coulomb kappa"):
        _evaluate(
            system,
            _parameters(
                system,
                (1.0, -1.0),
                screening_kappa_per_angstrom=0.1,
            ),
            config,
        )

    partial_cell = UnitCell.orthorhombic(
        (20.0, 22.0, 24.0),
        dtype=torch.float64,
        periodic=(True, True, False),
    )
    partial = _system(
        ((1.0, 2.0, 3.0), (4.0, 2.0, 3.0)),
        cell=partial_cell,
    )
    with pytest.raises(ReferenceEwaldError, match="fully periodic"):
        _evaluate(partial, _parameters(partial, (1.0, -1.0)), config)

    float32_system = _system(
        ((1.0, 2.0, 3.0), (4.0, 2.0, 3.0)),
        dtype=torch.float32,
    )
    with pytest.raises(ReferenceEwaldError, match="CPU float64 coordinates"):
        _evaluate(
            float32_system,
            _parameters(float32_system, (1.0, -1.0)),
            config,
        )


def test_direct_ewald_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_ewald import (
        __all__ as ewald_exports,
    )

    assert set(ewald_exports) <= set(physics.__all__)
