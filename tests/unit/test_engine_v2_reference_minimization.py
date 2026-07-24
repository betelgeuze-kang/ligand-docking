from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import struct

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.geometry import (  # noqa: E402
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_minimization import (  # noqa: E402
    REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID,
    REFERENCE_MINIMIZATION_SCIENTIFIC_BLOCKERS,
    ReferenceMinimizationConfig,
    ReferenceMinimizationError,
    minimize_reference_force_field,
    require_reference_minimization_checkpoint_document,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _system(*, distance: float = 1.5, dtype: torch.dtype = torch.float64) -> AllAtomSystem:
    return AllAtomSystem(
        system_id="reference-minimization-two-atom",
        atoms=(
            Atom(index=0, name="C1", element="C", atomic_number=6, residue_index=0),
            Atom(index=1, name="C2", element="C", atomic_number=6, residue_index=0),
        ),
        bonds=(Bond(index=0, atom_i=0, atom_j=1, order=1.0, source="unit"),),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [distance, 0.0, 0.0]]], dtype=dtype
        ),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="reference-minimization-two-atom",
            source_sha256="a" * 64,
            parser_name="unit",
            parser_version="1",
            operations=("unit_fixture",),
            source_digest_verified=True,
            transformation_chain_verified=True,
        ),
    )


def _parameters(system: AllAtomSystem | None = None) -> ReferenceForceFieldParameters:
    bound = _system() if system is None else system
    return ReferenceForceFieldParameters(
        parameter_set_id="two-atom-harmonic",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(bound),
        atom_parameters=(
            AtomNonbondedParameter(0, 1.0, 0.0, 0.0),
            AtomNonbondedParameter(1, 1.0, 0.0, 0.0),
        ),
        bonds=(HarmonicBondParameter(0, 1, 1.0, 100.0),),
        excluded_pairs=((0, 1),),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=4),
    )


def _config(**overrides: object) -> ReferenceMinimizationConfig:
    values: dict[str, object] = {
        "max_iterations": 100,
        "max_backtracks": 12,
        "initial_step_size_angstrom2_mol_per_kcal": 1.0e-3,
        "backtrack_factor": 0.5,
        "armijo_constant": 1.0e-4,
        "maximum_atom_displacement_angstrom": 0.05,
        "force_tolerance_kcal_per_mol_angstrom": 1.0e-3,
        "max_neighbors": 4,
        "max_atoms_per_cell": 4,
    }
    values.update(overrides)
    return ReferenceMinimizationConfig(**values)


def _rehash(document: dict[str, object]) -> None:
    projection = {key: value for key, value in document.items() if key != "checkpoint_sha256"}
    document["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _coordinate_hex_digest(rows: list[list[str]]) -> str:
    return hashlib.sha256(
        b"".join(
            struct.pack("<d", float.fromhex(item))
            for row in rows
            for item in row
        )
    ).hexdigest()


def test_minimization_is_deterministic_decreases_energy_and_preserves_claim_blockers() -> None:
    system = _system()
    parameters = _parameters(system)
    config = _config()

    first = minimize_reference_force_field(system, parameters, config)
    second = minimize_reference_force_field(system, parameters, config)

    assert first.status == "converged"
    assert first.converged
    assert first.energy_decreased
    assert first.final_energy_kcal_per_mol < first.initial_energy_kcal_per_mol
    assert first.final_max_force_kcal_per_mol_angstrom <= (
        config.force_tolerance_kcal_per_mol_angstrom
    )
    assert first.accepted_iterations > 0
    assert first.rejected_evaluations == 0
    assert first.evaluation_count == len(first.observations)
    assert first.to_dict() == second.to_dict()
    assert torch.equal(first.system.coordinates, second.system.coordinates)
    assert first.checkpoint.to_dict() == second.checkpoint.to_dict()
    assert first.scientific_blockers == REFERENCE_MINIMIZATION_SCIENTIFIC_BLOCKERS
    assert not first.scientifically_validated
    assert not first.system.provenance.transformation_chain_verified
    assert (
        first.system.provenance.metadata["last_operation_evidence_sha256"]
        == first.checkpoint.checkpoint_sha256
    )
    assert canonical_system_sha256(system) == first.checkpoint.source_system_sha256


def test_default_capacity_is_executable_and_matches_radius_graph_hard_caps() -> None:
    config = ReferenceMinimizationConfig()

    assert config.max_neighbors == MAX_COMPACT_NEIGHBORS
    assert config.max_atoms_per_cell == MAX_COMPACT_ATOMS_PER_CELL

    system = _system()
    result = minimize_reference_force_field(system, _parameters(system))

    assert result.status == "converged"
    assert result.checkpoint.config["max_neighbors"] == MAX_COMPACT_NEIGHBORS
    assert (
        result.checkpoint.config["max_atoms_per_cell"]
        == MAX_COMPACT_ATOMS_PER_CELL
    )


def test_checkpoint_restart_is_bit_exact_with_uninterrupted_execution() -> None:
    system = _system()
    parameters = _parameters(system)
    config = _config()

    uninterrupted = minimize_reference_force_field(system, parameters, config)
    paused = minimize_reference_force_field(
        system,
        parameters,
        config,
        pause_after_accepted_iterations=3,
    )
    assert paused.status == "checkpointed"
    assert paused.failure_code is None
    assert paused.accepted_iterations == 3

    serialized = json.loads(
        json.dumps(paused.checkpoint.to_dict(), allow_nan=False, sort_keys=True)
    )
    restored = require_reference_minimization_checkpoint_document(serialized)
    resumed = minimize_reference_force_field(
        system,
        parameters,
        config,
        checkpoint=restored,
    )

    assert resumed.to_dict() == uninterrupted.to_dict()
    assert resumed.checkpoint.to_dict() == uninterrupted.checkpoint.to_dict()
    assert torch.equal(resumed.system.coordinates, uninterrupted.system.coordinates)
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )


def test_iteration_exhaustion_is_failure_inclusive_and_keeps_decreased_state() -> None:
    system = _system()
    result = minimize_reference_force_field(
        system,
        _parameters(system),
        _config(max_iterations=1),
    )

    assert result.status == "max_iterations_reached"
    assert result.failure_code == "maximum_iteration_budget_exhausted"
    assert not result.converged
    assert result.energy_decreased
    assert result.accepted_iterations == 1
    assert [row.outcome for row in result.observations] == ["initial", "accepted"]
    assert result.checkpoint.accepted_iterations == 1


def test_convergence_on_final_budgeted_iteration_is_not_reported_as_exhaustion() -> None:
    system = _system()
    result = minimize_reference_force_field(
        system,
        _parameters(system),
        _config(
            max_iterations=1,
            force_tolerance_kcal_per_mol_angstrom=40.0001,
        ),
    )

    assert result.status == "converged"
    assert result.failure_code is None
    assert result.accepted_iterations == 1
    assert result.final_max_force_kcal_per_mol_angstrom <= 40.0001


def test_bounded_line_search_retains_rejected_failure_row_and_original_state() -> None:
    system = _system()
    result = minimize_reference_force_field(
        system,
        _parameters(system),
        _config(
            max_iterations=2,
            max_backtracks=0,
            initial_step_size_angstrom2_mol_per_kcal=100.0,
            maximum_atom_displacement_angstrom=1_000.0,
        ),
    )

    assert result.status == "line_search_failed"
    assert result.failure_code == "bounded_backtracking_exhausted"
    assert result.accepted_iterations == 0
    assert result.rejected_evaluations == 1
    assert result.evaluation_count == 2
    assert result.observations[-1].outcome == "rejected_armijo"
    assert result.observations[-1].failure_code == "armijo_decrease_not_satisfied"
    assert result.final_energy_kcal_per_mol == result.initial_energy_kcal_per_mol
    assert torch.equal(result.system.coordinates, system.coordinates)


def test_rehashed_checkpoint_line_search_order_tampering_fails_closed() -> None:
    system = _system()
    result = minimize_reference_force_field(
        system,
        _parameters(system),
        _config(
            max_iterations=2,
            max_backtracks=12,
            initial_step_size_angstrom2_mol_per_kcal=0.01,
            maximum_atom_displacement_angstrom=1_000.0,
        ),
    )
    assert result.observations[1].outcome == "rejected_armijo"
    assert result.observations[1].trial == 0
    tampered = result.checkpoint.to_dict()
    tampered["observations"][1]["trial"] = 1
    _rehash(tampered)

    with pytest.raises(ReferenceMinimizationError, match="line-search sequence"):
        require_reference_minimization_checkpoint_document(tampered)

    repeated_initial = result.checkpoint.to_dict()
    repeated_initial["observations"][1]["outcome"] = "initial"
    repeated_initial["observations"][1]["failure_code"] = None
    _rehash(repeated_initial)
    with pytest.raises(ReferenceMinimizationError, match="repeats the initial state"):
        require_reference_minimization_checkpoint_document(repeated_initial)


def test_checkpoint_tampering_identity_drift_and_recomputed_value_drift_fail_closed() -> None:
    system = _system()
    parameters = _parameters(system)
    config = _config()
    paused = minimize_reference_force_field(
        system,
        parameters,
        config,
        pause_after_accepted_iterations=2,
    )
    document = paused.checkpoint.to_dict()
    assert document["schema_id"] == REFERENCE_MINIMIZATION_CHECKPOINT_SCHEMA_ID

    tampered = deepcopy(document)
    tampered["accepted_iterations"] = 3
    with pytest.raises(ReferenceMinimizationError, match="checkpoint SHA-256 mismatch"):
        require_reference_minimization_checkpoint_document(tampered)

    shortened_trace = deepcopy(document)
    first_observation = shortened_trace["observations"][0]
    first_observation["coordinates_angstrom_hex"] = first_observation[
        "coordinates_angstrom_hex"
    ][:-1]
    first_observation["coordinates_sha256"] = _coordinate_hex_digest(
        first_observation["coordinates_angstrom_hex"]
    )
    _rehash(shortened_trace)
    with pytest.raises(ReferenceMinimizationError, match="atom count"):
        require_reference_minimization_checkpoint_document(shortened_trace)

    source_drifted_trace = deepcopy(document)
    initial_coordinates = source_drifted_trace["observations"][0][
        "coordinates_angstrom_hex"
    ]
    initial_coordinates[0][0] = float(123.0).hex()
    source_drifted_trace["observations"][0]["coordinates_sha256"] = (
        _coordinate_hex_digest(initial_coordinates)
    )
    _rehash(source_drifted_trace)
    require_reference_minimization_checkpoint_document(source_drifted_trace)
    with pytest.raises(
        ReferenceMinimizationError,
        match="history does not replay exactly from the source system",
    ):
        minimize_reference_force_field(
            system,
            parameters,
            config,
            checkpoint=source_drifted_trace,
        )

    drifted = deepcopy(document)
    drifted["current_energy_kcal_per_mol"] = float(
        drifted["current_energy_kcal_per_mol"]
    ) + 1.0
    drifted["observations"][-1]["energy_kcal_per_mol"] = float(
        drifted["observations"][-1]["energy_kcal_per_mol"]
    ) + 1.0
    _rehash(drifted)
    with pytest.raises(ReferenceMinimizationError, match="history does not replay"):
        minimize_reference_force_field(system, parameters, config, checkpoint=drifted)

    with pytest.raises(ReferenceMinimizationError, match="config fingerprint mismatch"):
        minimize_reference_force_field(
            system,
            parameters,
            _config(max_iterations=99),
            checkpoint=document,
        )

    with pytest.raises(TypeError):
        paused.checkpoint.config["max_iterations"] = 1

    changed_source = _system(distance=1.6)
    with pytest.raises(ReferenceMinimizationError, match="source system identity mismatch"):
        minimize_reference_force_field(
            changed_source,
            _parameters(changed_source),
            config,
            checkpoint=document,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"max_iterations": 0}, "max_iterations"),
        ({"max_backtracks": 65}, "max_backtracks"),
        ({"backtrack_factor": 1.0}, "backtrack_factor"),
        ({"armijo_constant": 1.0}, "armijo_constant"),
        ({"maximum_atom_displacement_angstrom": 0.0}, "maximum_atom_displacement"),
        ({"max_neighbors": 0}, "max_neighbors"),
        ({"max_neighbors": MAX_COMPACT_NEIGHBORS + 1}, "max_neighbors"),
        (
            {"max_atoms_per_cell": MAX_COMPACT_ATOMS_PER_CELL + 1},
            "max_atoms_per_cell",
        ),
    ),
)
def test_config_rejects_unbounded_or_degenerate_values(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ReferenceMinimizationError, match=message):
        _config(**kwargs)


def test_minimization_rejects_non_float64_and_multimodel_sources() -> None:
    float32_system = _system(dtype=torch.float32)
    with pytest.raises(ReferenceMinimizationError, match="float64"):
        minimize_reference_force_field(
            float32_system,
            _parameters(float32_system),
            _config(),
        )

    base = _system()
    multimodel = AllAtomSystem(
        **{
            **base.__dict__,
            "coordinates": torch.cat((base.coordinates, base.coordinates), dim=0),
        }
    )
    with pytest.raises(ReferenceMinimizationError, match="exactly one model"):
        minimize_reference_force_field(
            multimodel,
            _parameters(multimodel),
            _config(),
        )
