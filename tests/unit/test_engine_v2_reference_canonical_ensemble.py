from __future__ import annotations

from dataclasses import replace
import json

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
from betelgeuze_engine_v2.physics.reference_canonical_ensemble import (  # noqa: E402
    BAR_ANGSTROM3_TO_KCAL_PER_MOL,
    REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS,
    ReferenceCanonicalEnsembleCheckpoint,
    ReferenceCanonicalEnsembleConfig,
    ReferenceCanonicalEnsembleError,
    ReferenceLangevinThermostatConfig,
    ReferenceMonteCarloBarostatConfig,
    _CounterRandomStream,
    resume_reference_canonical_ensemble,
    resume_reference_npt,
    resume_reference_nvt,
    run_reference_npt,
    run_reference_nvt,
)
from betelgeuze_engine_v2.physics.reference_ensemble_statistics import (  # noqa: E402
    REFERENCE_ENSEMBLE_COMMON_METRIC_IDS,
    REFERENCE_ENSEMBLE_NPT_METRIC_IDS,
    REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS,
    ReferenceEnsembleStatisticsAcceptanceConfig,
    ReferenceEnsembleStatisticsError,
    analyze_reference_ensemble_statistics,
)
from betelgeuze_engine_v2.physics import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceEwaldConfig,
    ReferenceForceFieldParameters,
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    masses: tuple[float | None, ...] | None = None,
    bonds: tuple[tuple[int, int], ...] = (),
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
    bond_rows = tuple(
        Bond(index=index, atom_i=atom_i, atom_j=atom_j)
        for index, (atom_i, atom_j) in enumerate(bonds)
    )
    return AllAtomSystem(
        system_id="canonical-ensemble-unit-system",
        atoms=atoms,
        bonds=bond_rows,
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
    charges: tuple[float, ...] | None = None,
    epsilon: float = 0.0,
    cutoff: float | None = None,
) -> ReferenceForceFieldParameters:
    active_charges = charges or tuple(0.0 for _ in system.atoms)
    return ReferenceForceFieldParameters(
        parameter_set_id="canonical-ensemble-unit-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=atom.index,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=epsilon,
                charge_e=active_charges[atom.index],
            )
            for atom in system.atoms
        ),
        bonds=tuple(
            HarmonicBondParameter(
                atom_i=bond.atom_i,
                atom_j=bond.atom_j,
                equilibrium_angstrom=1.0,
                force_constant_kcal_per_mol_angstrom2=100.0,
            )
            for bond in system.bonds
        ),
        excluded_pairs=tuple((bond.atom_i, bond.atom_j) for bond in system.bonds),
        cutoff_angstrom=(
            cutoff
            if cutoff is not None
            else (4.0 if system.cell is not None else 10.0)
        ),
        switch_start_angstrom=(
            (cutoff - 1.0)
            if cutoff is not None
            else (3.0 if system.cell is not None else 8.0)
        ),
    )


def _thermostat(*, seed: int = 17) -> ReferenceLangevinThermostatConfig:
    return ReferenceLangevinThermostatConfig(
        temperature_kelvin=300.0,
        collision_rate_per_ps=2.0,
        random_seed=seed,
    )


def test_configs_are_canonical_and_bind_ensemble_and_rng_policy() -> None:
    thermostat = _thermostat()
    barostat = ReferenceMonteCarloBarostatConfig(
        pressure_bar=1.0,
        interval_steps=2,
        max_delta_volume_angstrom3=10.0,
        pressure_observation_stride=2,
    )
    nvt = ReferenceCanonicalEnsembleConfig(thermostat=thermostat)
    npt = ReferenceCanonicalEnsembleConfig(
        thermostat=thermostat,
        barostat=barostat,
        ewald_config=ReferenceEwaldConfig(
            alpha_per_angstrom=0.4,
            reciprocal_max_indices=(2, 2, 2),
        ),
    )

    assert nvt.ensemble == "NVT"
    assert npt.ensemble == "NPT"
    assert ReferenceCanonicalEnsembleConfig.from_dict(nvt.to_dict()) == nvt
    assert ReferenceCanonicalEnsembleConfig.from_dict(npt.to_dict()) == npt
    assert nvt.fingerprint_sha256 != npt.fingerprint_sha256
    assert thermostat.to_dict()["random_algorithm_id"].startswith("sha256_counter")
    assert BAR_ANGSTROM3_TO_KCAL_PER_MOL == pytest.approx(
        1.4393261854684513e-5,
        rel=0.0,
        abs=1.0e-20,
    )


def test_counter_random_stream_has_pinned_binary64_reference_sequence() -> None:
    uniform_stream = _CounterRandomStream(seed=0, word_index=0)
    assert [uniform_stream.uniform_open().hex() for _ in range(4)] == [
        "0x1.9f3c3dfe85d9cp-4",
        "0x1.e76a478442406p-1",
        "0x1.b714e8e1c45a0p-7",
        "0x1.ce504a6e0bfb3p-2",
    ]

    normal_stream = _CounterRandomStream(seed=0, word_index=0)
    assert [value.hex() for value in normal_stream.standard_normals(5).tolist()] == [
        "0x1.057f586497accp+1",
        "-0x1.45837a3191e60p-1",
        "-0x1.6694a6d2ad1c7p+1",
        "0x1.c35b19aa88092p-1",
        "0x1.bd1f2b4492661p-1",
    ]
    assert normal_stream.word_index == 6


def test_nvt_checkpoint_round_trip_and_resume_are_bit_exact() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
        bonds=((0, 1),),
    )
    parameters = _parameters(system)
    velocities = torch.tensor(
        [[[0.0, 0.2, 0.0], [0.0, -0.1, 0.0]]],
        dtype=torch.float64,
    )
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=0.0005,
        trajectory_stride=1,
        thermostat=_thermostat(seed=991),
    )
    constraints = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                atom_i=0,
                atom_j=1,
                target_distance_angstrom=1.0,
                tolerance_angstrom=1.0e-10,
            ),
        ),
    )

    uninterrupted = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=12,
        config=config,
        constraint_config=constraints,
    )
    paused = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=5,
        config=config,
        constraint_config=constraints,
    )
    raw = paused.checkpoint.to_json_bytes()
    restored = ReferenceCanonicalEnsembleCheckpoint.from_json_bytes(raw)
    resumed = resume_reference_nvt(
        system,
        parameters,
        restored,
        additional_steps=7,
    )

    assert restored.to_json_bytes() == raw
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.trajectory_head_sha256 == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )
    assert torch.equal(
        resumed.checkpoint.coordinates,
        uninterrupted.checkpoint.coordinates,
    )
    assert torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
    )
    assert resumed.checkpoint.random_word_index == 12 * 6
    assert uninterrupted.frames[-1].kinetic_temperature_kelvin >= 0.0
    assert uninterrupted.scientific_blockers == (
        REFERENCE_CANONICAL_ENSEMBLE_SCIENTIFIC_BLOCKERS
    )
    assert uninterrupted.claim_safe is False
    momentum = (
        uninterrupted.checkpoint.velocities_angstrom_per_ps
        * torch.tensor((1.0, 3.0), dtype=torch.float64).view(1, -1, 1)
    ).sum(dim=1)
    torch.testing.assert_close(
        momentum,
        torch.zeros_like(momentum),
        atol=1.0e-12,
        rtol=0.0,
    )
    assert (
        uninterrupted.checkpoint.max_abs_position_constraint_residual_angstrom
        <= 1.0e-10
    )


def test_nvt_seed_changes_trajectory_but_repeated_seed_is_exact() -> None:
    system = _system(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    parameters = _parameters(system)
    velocities = torch.zeros((1, 2, 3), dtype=torch.float64)
    first = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=4,
        config=ReferenceCanonicalEnsembleConfig(thermostat=_thermostat(seed=1)),
    )
    repeated = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=4,
        config=ReferenceCanonicalEnsembleConfig(thermostat=_thermostat(seed=1)),
    )
    different = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=4,
        config=ReferenceCanonicalEnsembleConfig(thermostat=_thermostat(seed=2)),
    )

    assert first.checkpoint.checkpoint_sha256 == repeated.checkpoint.checkpoint_sha256
    assert torch.equal(first.system.coordinates, repeated.system.coordinates)
    assert not torch.equal(first.system.coordinates, different.system.coordinates)


def test_npt_records_pressure_volume_attempts_and_exact_restart() -> None:
    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    system = _system(
        ((3.0, 3.0, 3.0), (8.0, 8.0, 8.0)),
        cell=cell,
    )
    parameters = _parameters(system)
    velocities = torch.tensor(
        [[[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=0.0001,
        trajectory_stride=1,
        thermostat=_thermostat(seed=8128),
        barostat=ReferenceMonteCarloBarostatConfig(
            pressure_bar=1.0,
            interval_steps=2,
            max_delta_volume_angstrom3=20.0,
            pressure_observation_stride=1,
            pressure_log_length_step=1.0e-5,
        ),
    )

    uninterrupted = run_reference_npt(
        system,
        parameters,
        velocities,
        steps=8,
        config=config,
    )
    paused = run_reference_npt(
        system,
        parameters,
        velocities,
        steps=3,
        config=config,
    )
    restored = ReferenceCanonicalEnsembleCheckpoint.from_json_bytes(
        paused.checkpoint.to_json_bytes()
    )
    resumed = resume_reference_npt(
        system,
        parameters,
        restored,
        additional_steps=5,
    )

    assert len(uninterrupted.barostat_attempts) == 4
    assert uninterrupted.checkpoint.cumulative_barostat_attempt_count == 4
    assert uninterrupted.checkpoint.cumulative_barostat_accept_count + (
        uninterrupted.checkpoint.cumulative_barostat_reject_count
    ) == 4
    assert all(frame.volume_angstrom3 is not None for frame in uninterrupted.frames)
    assert all(
        frame.instantaneous_pressure_bar is not None
        for frame in uninterrupted.frames
    )
    assert uninterrupted.checkpoint.barostat_head_sha256
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.barostat_head_sha256 == (
        uninterrupted.checkpoint.barostat_head_sha256
    )
    assert resumed.checkpoint.random_word_index == 8 * 6 + 4 * 2
    assert torch.equal(
        resumed.system.cell.vectors,
        uninterrupted.system.cell.vectors,
    )


def test_npt_molecular_centre_scaling_preserves_constrained_bond() -> None:
    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    system = _system(
        ((11.7, 2.0, 2.0), (0.7, 2.0, 2.0), (6.0, 7.0, 7.0)),
        masses=(16.0, 1.0, 23.0),
        bonds=((0, 1),),
        cell=cell,
    )
    parameters = _parameters(system)
    constraints = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                atom_i=0,
                atom_j=1,
                target_distance_angstrom=1.0,
                tolerance_angstrom=1.0e-9,
            ),
        ),
    )
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=0.0001,
        thermostat=_thermostat(seed=11),
        barostat=ReferenceMonteCarloBarostatConfig(
            interval_steps=1,
            max_delta_volume_angstrom3=30.0,
            pressure_observation_stride=1,
        ),
    )
    result = run_reference_npt(
        system,
        parameters,
        torch.zeros((1, 3, 3), dtype=torch.float64),
        steps=3,
        config=config,
        constraint_config=constraints,
    )

    lengths = result.system.cell.orthorhombic_lengths()
    delta = result.system.coordinates[0, 0] - result.system.coordinates[0, 1]
    delta = delta - torch.round(delta / lengths) * lengths
    assert torch.linalg.vector_norm(delta).item() == pytest.approx(
        1.0,
        abs=1.0e-9,
    )
    assert result.checkpoint.max_abs_position_constraint_residual_angstrom <= 1.0e-9


def test_npt_direct_ewald_is_bound_to_config_and_runs_neutral_pair() -> None:
    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    system = _system(((3.0, 6.0, 6.0), (8.0, 6.0, 6.0)), cell=cell)
    parameters = _parameters(system, charges=(0.25, -0.25))
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=1.0e-5,
        thermostat=_thermostat(seed=5),
        barostat=ReferenceMonteCarloBarostatConfig(
            interval_steps=1,
            max_delta_volume_angstrom3=2.0,
            pressure_observation_stride=1,
        ),
        ewald_config=ReferenceEwaldConfig(
            alpha_per_angstrom=0.4,
            reciprocal_max_indices=(2, 2, 2),
        ),
    )

    result = run_reference_npt(
        system,
        parameters,
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=2,
        config=config,
    )

    assert result.checkpoint.config.electrostatics_mode == "neutral_direct_ewald_v1"
    assert result.frames[-1].instantaneous_pressure_bar is not None
    assert result.checkpoint.current_total_energy_kcal_per_mol == pytest.approx(
        result.frames[-1].total_energy_kcal_per_mol,
        rel=0.0,
        abs=0.0,
    )


def test_npt_and_checkpoint_failure_rows_fail_closed() -> None:
    nonperiodic = _system(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    npt_config = ReferenceCanonicalEnsembleConfig(
        thermostat=_thermostat(),
        barostat=ReferenceMonteCarloBarostatConfig(),
    )
    with pytest.raises(ReferenceCanonicalEnsembleError, match="periodic cell"):
        run_reference_npt(
            nonperiodic,
            _parameters(nonperiodic),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            config=npt_config,
        )

    small_cell = UnitCell.orthorhombic((8.0, 8.0, 8.0), dtype=torch.float64)
    small = _system(((1.0, 1.0, 1.0), (5.0, 5.0, 5.0)), cell=small_cell)
    with pytest.raises(ReferenceCanonicalEnsembleError, match="below half"):
        run_reference_npt(
            small,
            _parameters(small, cutoff=4.0),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            config=npt_config,
        )

    valid = _system(
        ((1.0, 1.0, 1.0), (6.0, 6.0, 6.0)),
        cell=UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64),
    )
    result = run_reference_npt(
        valid,
        _parameters(valid),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=2,
        config=replace(
            npt_config,
            barostat=ReferenceMonteCarloBarostatConfig(interval_steps=1),
        ),
    )
    raw = result.checkpoint.to_json_bytes()
    payload = json.loads(raw.decode("ascii"))
    payload["random_word_index"] += 1
    tampered = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    with pytest.raises(ReferenceCanonicalEnsembleError, match="random word index"):
        ReferenceCanonicalEnsembleCheckpoint.from_json_bytes(tampered)

    foreign_runtime = replace(
        result.checkpoint,
        torch_version="0.0.0-foreign-runtime",
    )
    parsed_foreign_runtime = ReferenceCanonicalEnsembleCheckpoint.from_json_bytes(
        foreign_runtime.to_json_bytes()
    )
    with pytest.raises(ReferenceCanonicalEnsembleError, match="provenance mismatch"):
        resume_reference_canonical_ensemble(
            valid,
            _parameters(valid),
            parsed_foreign_runtime,
            additional_steps=1,
        )

    domain_rejected = run_reference_npt(
        valid,
        _parameters(valid),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=1,
        config=ReferenceCanonicalEnsembleConfig(
            timestep_ps=1.0e-4,
            thermostat=_thermostat(seed=0),
            barostat=ReferenceMonteCarloBarostatConfig(
                interval_steps=1,
                max_delta_volume_angstrom3=1.0e6,
                pressure_observation_stride=1,
            ),
        ),
    ).barostat_attempts[0]
    assert domain_rejected.disposition == "domain_rejected"
    assert domain_rejected.accepted is False
    assert domain_rejected.proposed_volume_angstrom3 < 0.0
    assert domain_rejected.proposed_potential_energy_kcal_per_mol is None
    assert domain_rejected.log_acceptance_probability is None


def test_restart_rejects_different_source_parameter_or_runtime_contract() -> None:
    system = _system(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    parameters = _parameters(system)
    result = run_reference_nvt(
        system,
        parameters,
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=2,
    )
    different_source = replace(
        system,
        coordinates=system.coordinates + 0.1,
    )
    with pytest.raises(ReferenceCanonicalEnsembleError, match="provenance mismatch"):
        resume_reference_canonical_ensemble(
            different_source,
            parameters,
            result.checkpoint,
            additional_steps=1,
        )
    with pytest.raises(ReferenceCanonicalEnsembleError, match="provenance mismatch"):
        resume_reference_canonical_ensemble(
            system,
            replace(parameters, parameter_set_version="1.0.1"),
            result.checkpoint,
            additional_steps=1,
        )


def test_canonical_ensemble_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_canonical_ensemble import (
        __all__ as ensemble_exports,
    )

    assert set(ensemble_exports) <= set(physics.__all__)


def _acceptance(
    *,
    burn_in_steps: int = 2,
    max_temperature_bias: float = 1.0e6,
    max_pressure_bias: float = 1.0e12,
) -> ReferenceEnsembleStatisticsAcceptanceConfig:
    return ReferenceEnsembleStatisticsAcceptanceConfig(
        burn_in_steps=burn_in_steps,
        max_abs_temperature_bias_kelvin=max_temperature_bias,
        min_temperature_effective_sample_size=1.0,
        max_abs_pressure_bias_bar=max_pressure_bias,
        min_pressure_effective_sample_size=1.0,
        min_barostat_acceptance_fraction=0.0,
        max_barostat_acceptance_fraction=1.0,
        min_barostat_attempt_count=1,
        max_position_constraint_residual_angstrom=1.0e-8,
        max_velocity_constraint_residual_angstrom_per_ps=1.0e-8,
        confidence_level=0.95,
        require_temperature_target_inside_confidence_interval=False,
        require_pressure_target_inside_confidence_interval=False,
    )


def test_nvt_all_step_statistics_bind_ci_ess_restart_and_failure_rows() -> None:
    system = _system(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    parameters = _parameters(system)
    velocities = torch.zeros((1, 2, 3), dtype=torch.float64)
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=0.001,
        trajectory_stride=1,
        thermostat=_thermostat(seed=42),
    )
    uninterrupted = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=80,
        config=config,
    )
    paused = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=31,
        config=config,
    )
    resumed = resume_reference_nvt(
        system,
        parameters,
        paused.checkpoint,
        additional_steps=49,
    )
    acceptance = _acceptance(burn_in_steps=10)
    assert ReferenceEnsembleStatisticsAcceptanceConfig.from_dict(
        acceptance.to_dict()
    ) == acceptance

    result = analyze_reference_ensemble_statistics(
        uninterrupted,
        resumed,
        acceptance,
    )

    assert result.ensemble == "NVT"
    assert result.restart_equality.exact is True
    assert {row.metric_id for row in result.metrics} == set(
        REFERENCE_ENSEMBLE_COMMON_METRIC_IDS
    )
    assert {row.series_id for row in result.series} == {
        "potential_energy_kcal_per_mol",
        "kinetic_energy_kcal_per_mol",
        "total_energy_kcal_per_mol",
        "kinetic_temperature_kelvin",
    }
    temperature = next(
        row for row in result.series if row.series_id == "kinetic_temperature_kelvin"
    )
    assert 0.0 < temperature.effective_sample_size <= temperature.sample_count
    assert temperature.confidence_interval_low <= temperature.mean <= (
        temperature.confidence_interval_high
    )
    assert result.failure_rows == ()
    assert result.passed is True
    assert result.scientific_blockers == (
        REFERENCE_ENSEMBLE_STATISTICS_SCIENTIFIC_BLOCKERS
    )
    assert result.to_dict()["claim_safe"] is False

    strict = analyze_reference_ensemble_statistics(
        uninterrupted,
        resumed,
        _acceptance(burn_in_steps=10, max_temperature_bias=0.0),
    )
    assert "temperature_absolute_bias_kelvin" in strict.failure_rows
    assert strict.passed is False


def test_npt_all_step_statistics_include_pressure_volume_and_acceptance() -> None:
    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    system = _system(
        ((3.0, 3.0, 3.0), (8.0, 8.0, 8.0)),
        cell=cell,
    )
    parameters = _parameters(system)
    velocities = torch.zeros((1, 2, 3), dtype=torch.float64)
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=0.0001,
        trajectory_stride=1,
        thermostat=_thermostat(seed=73),
        barostat=ReferenceMonteCarloBarostatConfig(
            pressure_bar=1.0,
            interval_steps=2,
            max_delta_volume_angstrom3=5.0,
            pressure_observation_stride=1,
        ),
    )
    uninterrupted = run_reference_npt(
        system,
        parameters,
        velocities,
        steps=8,
        config=config,
    )
    paused = run_reference_npt(
        system,
        parameters,
        velocities,
        steps=3,
        config=config,
    )
    resumed = resume_reference_npt(
        system,
        parameters,
        paused.checkpoint,
        additional_steps=5,
    )

    result = analyze_reference_ensemble_statistics(
        uninterrupted,
        resumed,
        _acceptance(),
    )

    assert result.ensemble == "NPT"
    assert result.restart_equality.exact is True
    assert {row.metric_id for row in result.metrics} == set(
        REFERENCE_ENSEMBLE_COMMON_METRIC_IDS
    ) | set(REFERENCE_ENSEMBLE_NPT_METRIC_IDS)
    assert {row.series_id for row in result.series} >= {
        "volume_angstrom3",
        "instantaneous_pressure_bar",
    }
    assert result.passed is True
    assert result.failure_rows == ()


def test_ensemble_statistics_reject_subsampled_or_incomplete_pressure_trace() -> None:
    system = _system(((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    parameters = _parameters(system)
    velocities = torch.zeros((1, 2, 3), dtype=torch.float64)
    config = ReferenceCanonicalEnsembleConfig(
        trajectory_stride=2,
        thermostat=_thermostat(),
    )
    uninterrupted = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=6,
        config=config,
    )
    paused = run_reference_nvt(
        system,
        parameters,
        velocities,
        steps=2,
        config=config,
    )
    resumed = resume_reference_nvt(
        system,
        parameters,
        paused.checkpoint,
        additional_steps=4,
    )
    with pytest.raises(ReferenceEnsembleStatisticsError, match="trajectory_stride=1"):
        analyze_reference_ensemble_statistics(
            uninterrupted,
            resumed,
            _acceptance(),
        )

    cell = UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    periodic = _system(((3.0, 3.0, 3.0), (8.0, 8.0, 8.0)), cell=cell)
    npt_config = ReferenceCanonicalEnsembleConfig(
        trajectory_stride=1,
        thermostat=_thermostat(),
        barostat=ReferenceMonteCarloBarostatConfig(
            interval_steps=2,
            pressure_observation_stride=2,
        ),
    )
    npt_full = run_reference_npt(
        periodic,
        _parameters(periodic),
        velocities,
        steps=4,
        config=npt_config,
    )
    npt_paused = run_reference_npt(
        periodic,
        _parameters(periodic),
        velocities,
        steps=2,
        config=npt_config,
    )
    npt_resumed = resume_reference_npt(
        periodic,
        _parameters(periodic),
        npt_paused.checkpoint,
        additional_steps=2,
    )
    with pytest.raises(
        ReferenceEnsembleStatisticsError,
        match="pressure_observation_stride=1",
    ):
        analyze_reference_ensemble_statistics(
            npt_full,
            npt_resumed,
            _acceptance(),
        )


def test_ensemble_statistics_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_ensemble_statistics import (
        __all__ as statistics_exports,
    )

    assert set(statistics_exports) <= set(physics.__all__)
