from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (  # noqa: E402
    MAX_REFERENCE_NVE_RETAINED_FRAMES,
    REFERENCE_NVE_SCIENTIFIC_BLOCKERS,
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceForceFieldParameters,
    ReferenceNVECheckpoint,
    ReferenceNVEConfig,
    ReferenceNVEError,
    resume_reference_nve,
    run_reference_nve,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    masses: tuple[float | None, ...] | None = None,
    bonded: bool = False,
    cell: UnitCell | None = None,
) -> AllAtomSystem:
    active_masses = masses or tuple(12.0 for _ in coordinates)
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=atomic_number_for_element("C"),
            residue_index=0,
            partial_charge_e=0.0,
            mass_da=active_masses[index],
        )
        for index in range(len(coordinates))
    )
    bonds = (Bond(index=0, atom_i=0, atom_j=1),) if bonded else ()
    return AllAtomSystem(
        system_id="reference-nve-unit-system",
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name="MOL",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
        cell=cell,
    )


def _parameters(
    system: AllAtomSystem,
    *,
    equilibrium_angstrom: float = 1.0,
    force_constant: float = 100.0,
) -> ReferenceForceFieldParameters:
    bonds = tuple(
        HarmonicBondParameter(
            atom_i=bond.atom_i,
            atom_j=bond.atom_j,
            equilibrium_angstrom=equilibrium_angstrom,
            force_constant_kcal_per_mol_angstrom2=force_constant,
        )
        for bond in system.bonds
    )
    return ReferenceForceFieldParameters(
        parameter_set_id="reference-nve-unit-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=atom.index,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=0.0,
                charge_e=0.0,
            )
            for atom in system.atoms
        ),
        bonds=bonds,
        excluded_pairs=tuple((bond.atom_i, bond.atom_j) for bond in system.bonds),
        cutoff_angstrom=4.0 if system.cell is not None else 10.0,
        switch_start_angstrom=3.0 if system.cell is not None else 8.0,
    )


def test_force_free_particle_follows_ballistic_nve_trajectory() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    velocity = torch.tensor([[[1.0, -2.0, 0.5]]], dtype=torch.float64)
    result = run_reference_nve(
        system,
        _parameters(system),
        velocity,
        steps=10,
        config=ReferenceNVEConfig(timestep_ps=0.01, trajectory_stride=4),
    )

    torch.testing.assert_close(
        result.system.coordinates,
        torch.tensor([[[0.1, -0.2, 0.05]]], dtype=torch.float64),
        atol=1.0e-15,
        rtol=0.0,
    )
    assert torch.equal(result.checkpoint.velocities_angstrom_per_ps, velocity)
    assert [frame.step for frame in result.frames] == [0, 4, 8, 10]
    assert result.checkpoint.evaluated_frame_count == 11
    assert result.energy_drift_kcal_per_mol == 0.0
    assert result.max_abs_energy_drift_kcal_per_mol == 0.0
    assert result.scientific_blockers == REFERENCE_NVE_SCIENTIFIC_BLOCKERS
    assert "shake_rattle_constraints_not_implemented" in result.scientific_blockers
    assert result.claim_safe is False
    assert result.to_dict()["claim_safe"] is False


def test_full_orthorhombic_pbc_wraps_coordinates_each_step() -> None:
    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    system = _system(((9.9, 0.0, 0.0),), cell=cell)
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.tensor([[[2.0, 0.0, 0.0]]], dtype=torch.float64),
        steps=1,
        config=ReferenceNVEConfig(timestep_ps=0.1),
    )

    assert result.system.coordinates[0, 0, 0].item() == pytest.approx(
        0.1,
        abs=1.0e-14,
    )
    assert result.energy_drift_kcal_per_mol == 0.0


def test_harmonic_dimer_has_bounded_velocity_verlet_energy_drift() -> None:
    system = _system(((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)), bonded=True)
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=200,
        config=ReferenceNVEConfig(timestep_ps=0.0001, trajectory_stride=20),
    )

    assert result.initial_total_energy_kcal_per_mol == pytest.approx(0.5)
    assert result.max_abs_energy_drift_kcal_per_mol < 1.0e-4
    assert result.checkpoint.evaluated_frame_count == 201


def test_checkpoint_round_trip_and_resume_are_bit_exact() -> None:
    system = _system(((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)), bonded=True)
    parameters = _parameters(system)
    velocities = torch.tensor(
        [[[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    config = ReferenceNVEConfig(timestep_ps=0.0001, trajectory_stride=3)

    uninterrupted = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=12,
        config=config,
    )
    paused = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=5,
        config=config,
    )
    raw = paused.checkpoint.to_json_bytes()
    restored = ReferenceNVECheckpoint.from_json_bytes(raw)
    assert restored.to_json_bytes() == raw
    assert restored.checkpoint_sha256 == paused.checkpoint.checkpoint_sha256

    resumed = resume_reference_nve(
        system,
        parameters,
        restored,
        additional_steps=7,
    )
    assert torch.equal(
        resumed.checkpoint.coordinates,
        uninterrupted.checkpoint.coordinates,
    )
    assert torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
    )
    assert resumed.checkpoint.current_total_energy_kcal_per_mol.hex() == (
        uninterrupted.checkpoint.current_total_energy_kcal_per_mol.hex()
    )
    assert resumed.checkpoint.trajectory_head_sha256 == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.evaluated_frame_count == 13


def test_checkpoint_transport_and_restart_identity_fail_closed() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    parameters = _parameters(system)
    result = run_reference_nve(
        system,
        parameters,
        torch.zeros((1, 1, 3), dtype=torch.float64),
        steps=2,
    )
    raw = result.checkpoint.to_json_bytes()
    tampered = raw.replace(
        result.checkpoint.checkpoint_sha256.encode("ascii"),
        b"0" * 64,
    )

    with pytest.raises(ReferenceNVEError, match="self-digest mismatch"):
        ReferenceNVECheckpoint.from_json_bytes(tampered)
    with pytest.raises(ReferenceNVEError, match="transport is not canonical"):
        ReferenceNVECheckpoint.from_json_bytes(raw.rstrip(b"\n"))

    different_source = replace(
        system,
        coordinates=system.coordinates + torch.tensor([[[0.1, 0.0, 0.0]]]),
    )
    with pytest.raises(ReferenceNVEError, match="provenance mismatch"):
        resume_reference_nve(
            different_source,
            parameters,
            result.checkpoint,
            additional_steps=1,
        )
    different_parameters = replace(parameters, parameter_set_version="1.0.1")
    with pytest.raises(ReferenceNVEError, match="provenance mismatch"):
        resume_reference_nve(
            system,
            different_parameters,
            result.checkpoint,
            additional_steps=1,
        )


def test_nve_admission_and_retained_frame_capacity_fail_closed() -> None:
    missing_mass = _system(((0.0, 0.0, 0.0),), masses=(None,))
    with pytest.raises(ReferenceNVEError, match="missing mass_da"):
        run_reference_nve(
            missing_mass,
            _parameters(missing_mass),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )

    system = _system(((0.0, 0.0, 0.0),))
    with pytest.raises(ReferenceNVEError, match="CPU float64"):
        run_reference_nve(
            system,
            _parameters(system),
            torch.zeros((1, 1, 3), dtype=torch.float32),
            steps=1,
        )
    with pytest.raises(ReferenceNVEError, match="retained trajectory-frame capacity"):
        run_reference_nve(
            system,
            _parameters(system),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=MAX_REFERENCE_NVE_RETAINED_FRAMES,
            config=ReferenceNVEConfig(trajectory_stride=1),
        )

    partial_cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
        periodic=(True, True, False),
    )
    partial_periodic = _system(((0.0, 0.0, 0.0),), cell=partial_cell)
    with pytest.raises(ReferenceNVEError, match="all three dimensions"):
        run_reference_nve(
            partial_periodic,
            _parameters(partial_periodic),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )

    triclinic_cell = UnitCell(
        vectors=torch.tensor(
            [[10.0, 1.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
            dtype=torch.float64,
        )
    )
    triclinic = _system(((0.0, 0.0, 0.0),), cell=triclinic_cell)
    with pytest.raises(ReferenceNVEError, match="orthorhombic"):
        run_reference_nve(
            triclinic,
            _parameters(triclinic),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )


def test_reference_nve_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_nve import __all__ as nve_exports

    assert set(nve_exports) <= set(physics.__all__)
