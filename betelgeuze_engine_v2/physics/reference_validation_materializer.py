"""Exact runtime materializer for the frozen CPU validation protocol.

The materializer projects every frozen fixture and mutation contract into
deterministic float64 Engine v2 runtime objects.  It emits only identities and
materialization metadata: no energy, force, metric, validation-result, or claim
artifact is collected here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from betelgeuze_engine_v2.geometry import (
    CompactNeighborList,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)

from .reference_parameters import (
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PairScalingParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from .reference_validation_oracle import IndependentAnalyticOracleInput
from .reference_validation_protocol import (
    CPUReferenceValidationCase,
    CPUReferenceValidationProtocol,
    CPUReferenceValidationSpec,
    frozen_cpu_reference_validation_protocol,
)


REFERENCE_VALIDATION_MATERIALIZER_SCHEMA_ID = "betelgeuze.engine_v2_reference_validation_materializer/1.0.0"
REFERENCE_VALIDATION_MATERIALIZER_ID = "cpu_reference_validation_exact_fixture_materializer/1.0.0"
REFERENCE_VALIDATION_MATERIALIZER_VERSION = "1.0.0"

MATERIALIZER_MAX_NEIGHBORS = 16
MATERIALIZER_MAX_ATOMS_PER_CELL = 16
MATERIALIZER_DOMAIN_MAX_ATOMS = 16
MATERIALIZER_DOMAIN_MAX_BONDS = 32
MATERIALIZER_DOMAIN_MAX_ANGLES = 64
MATERIALIZER_DOMAIN_MAX_TORSIONS = 128
MATERIALIZER_DOMAIN_MAX_NONBONDED_PAIRS = 120
MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM = 1.0e-6

_AXIS_NAMES = ("x", "y", "z")
_KEEP_CELL = object()


class ReferenceValidationMaterializationError(ValueError):
    """A frozen fixture or mutation could not be materialized exactly."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceValidationMaterializationError("materialization payload is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def reference_validation_materializer_source_sha256() -> str:
    """Return the byte identity of this exact source file."""

    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _neighbor_sha256(neighbors: CompactNeighborList) -> str:
    payload = {
        "diagnostics": neighbors.diagnostics.to_dict(),
        "indices": neighbors.indices.detach().cpu().tolist(),
        "mask": neighbors.mask.detach().cpu().tolist(),
        "distances_hex": [float(value).hex() for value in neighbors.distances.detach().cpu().reshape(-1).tolist()],
        "displacements_hex": [
            float(value).hex() for value in neighbors.displacements.detach().cpu().reshape(-1).tolist()
        ],
        "image_shifts": neighbors.image_shifts.detach().cpu().tolist(),
    }
    return _sha256(payload)


def _base_domain() -> ReferenceApplicabilityDomain:
    return ReferenceApplicabilityDomain(
        max_atoms=MATERIALIZER_DOMAIN_MAX_ATOMS,
        max_bonds=MATERIALIZER_DOMAIN_MAX_BONDS,
        max_angles=MATERIALIZER_DOMAIN_MAX_ANGLES,
        max_torsions=MATERIALIZER_DOMAIN_MAX_TORSIONS,
        max_nonbonded_pairs=MATERIALIZER_DOMAIN_MAX_NONBONDED_PAIRS,
        periodic_orthorhombic_supported=True,
        minimum_pair_distance_angstrom=(MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM),
    )


def _coordinates_tensor(rows: object) -> torch.Tensor:
    try:
        coordinates = torch.tensor(rows, dtype=torch.float64, device="cpu")
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ReferenceValidationMaterializationError("fixture coordinates must be finite float64 values") from exc
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ReferenceValidationMaterializationError("fixture coordinates must have [atom,3] shape")
    if not bool(torch.isfinite(coordinates).all().item()):
        raise ReferenceValidationMaterializationError("fixture coordinates must be finite")
    return coordinates.unsqueeze(0)


def _build_neighbors(
    system: AllAtomSystem,
    *,
    cutoff_angstrom: float,
    coordinate_override: torch.Tensor | None = None,
) -> CompactNeighborList:
    coordinates = system.coordinates if coordinate_override is None else coordinate_override
    return build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=float(cutoff_angstrom),
            max_neighbors=MATERIALIZER_MAX_NEIGHBORS,
            max_atoms_per_cell=MATERIALIZER_MAX_ATOMS_PER_CELL,
        ),
        cell=system.cell,
    )


def _system_from_spec(spec: CPUReferenceValidationSpec) -> AllAtomSystem:
    if spec.kind != "fixture_profile":
        raise ReferenceValidationMaterializationError("only frozen fixture profiles can be materialized")
    payload = json.loads(spec.canonical_payload_json)
    atom_rows = payload.get("atoms")
    bond_rows = payload.get("bonds")
    if not isinstance(atom_rows, list) or not atom_rows:
        raise ReferenceValidationMaterializationError("fixture atom rows must be non-empty")
    if not isinstance(bond_rows, list):
        raise ReferenceValidationMaterializationError("fixture bonds must be a list")
    atoms: list[Atom] = []
    for expected_index, row in enumerate(atom_rows):
        if not isinstance(row, dict) or row.get("index") != expected_index:
            raise ReferenceValidationMaterializationError("fixture atom indices must be contiguous and ordered")
        element = str(row.get("element", ""))
        atomic_number = row.get("atomic_number")
        if isinstance(atomic_number, bool) or not isinstance(atomic_number, int):
            raise ReferenceValidationMaterializationError("fixture atomic numbers must be integers")
        atoms.append(
            Atom(
                index=expected_index,
                name=f"{element}{expected_index + 1}",
                element=element,
                atomic_number=atomic_number,
                residue_index=0,
                formal_charge=0,
                partial_charge_e=None,
                mass_da=None,
                metadata={
                    "synthetic_validation_fixture": True,
                    "scientifically_validated": False,
                },
            )
        )
    bonds: list[Bond] = []
    seen_pairs: set[tuple[int, int]] = set()
    for index, row in enumerate(bond_rows):
        if not isinstance(row, list) or len(row) != 2:
            raise ReferenceValidationMaterializationError("fixture topology bond rows must be atom-index pairs")
        atom_i, atom_j = sorted((int(row[0]), int(row[1])))
        if atom_i < 0 or atom_j >= len(atoms) or atom_i == atom_j:
            raise ReferenceValidationMaterializationError("fixture topology bond index is invalid")
        if (atom_i, atom_j) in seen_pairs:
            raise ReferenceValidationMaterializationError("fixture topology bonds must be unique")
        seen_pairs.add((atom_i, atom_j))
        bonds.append(
            Bond(
                index=index,
                atom_i=atom_i,
                atom_j=atom_j,
                order=1.0,
                source="frozen_validation_protocol",
            )
        )
    coordinates = _coordinates_tensor(payload.get("coordinates_angstrom"))
    if coordinates.shape[1] != len(atoms):
        raise ReferenceValidationMaterializationError("fixture coordinate count must match atom count")
    cell = None
    cell_rows = payload.get("orthorhombic_cell_angstrom")
    periodic_rows = payload.get("periodic_axes")
    if cell_rows is not None:
        if not isinstance(periodic_rows, list) or len(periodic_rows) != 3:
            raise ReferenceValidationMaterializationError("periodic fixture requires three periodic-axis flags")
        cell = UnitCell.orthorhombic(
            cell_rows,
            dtype=torch.float64,
            device="cpu",
            periodic=tuple(bool(value) for value in periodic_rows),
        )
    elif periodic_rows is not None:
        raise ReferenceValidationMaterializationError("periodic-axis flags require a cell")
    return AllAtomSystem(
        system_id=f"cpu-reference-validation:{spec.spec_id}",
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="SYN",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non_polymer",
                hetero=True,
                metadata={"synthetic_validation_fixture": True},
            ),
        ),
        chains=(
            Chain(
                index=0,
                chain_id="V",
                residue_indices=(0,),
                entity_id="synthetic-validation-fixture",
            ),
        ),
        coordinates=coordinates,
        cell=cell,
        coordinate_unit="angstrom",
        provenance=StructureProvenance(
            source_format="engine_v2_validation_fixture_spec",
            source_id=spec.spec_id,
            source_sha256=spec.spec_sha256,
            parser_name=REFERENCE_VALIDATION_MATERIALIZER_ID,
            parser_version=REFERENCE_VALIDATION_MATERIALIZER_VERSION,
            operations=("exact_frozen_fixture_materialization",),
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
        ),
        metadata={
            "fixture_profile_id": spec.spec_id,
            "fixture_profile_sha256": spec.spec_sha256,
            "parameter_origin": "synthetic_protocol_values_not_fit_data",
            "validation_result": False,
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )


def _parameters_from_spec(
    spec: CPUReferenceValidationSpec,
    system: AllAtomSystem,
) -> ReferenceForceFieldParameters:
    payload = json.loads(spec.canonical_payload_json)
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict):
        raise ReferenceValidationMaterializationError("fixture parameters must be an object")
    try:
        atom_parameters = tuple(
            AtomNonbondedParameter(
                atom_index=row[0],
                sigma_angstrom=row[1],
                epsilon_kcal_per_mol=row[2],
                charge_e=row[3],
            )
            for row in parameters.get("atom_nonbonded", ())
        )
        bonds = tuple(
            HarmonicBondParameter(
                atom_i=row[0],
                atom_j=row[1],
                equilibrium_angstrom=row[2],
                force_constant_kcal_per_mol_angstrom2=row[3],
            )
            for row in parameters.get("bonds", ())
        )
        angles = tuple(
            HarmonicAngleParameter(
                atom_i=row[0],
                atom_j=row[1],
                atom_k=row[2],
                equilibrium_radians=row[3],
                force_constant_kcal_per_mol_radian2=row[4],
            )
            for row in parameters.get("angles", ())
        )
        torsions = tuple(
            PeriodicTorsionParameter(
                atom_i=row[0],
                atom_j=row[1],
                atom_k=row[2],
                atom_l=row[3],
                periodicity=row[4],
                phase_radians=row[5],
                amplitude_kcal_per_mol=row[6],
            )
            for row in parameters.get("torsions", ())
        )
        scaled_pairs = tuple(
            PairScalingParameter(
                atom_i=row[0],
                atom_j=row[1],
                lj_scale=row[2],
                electrostatic_scale=row[3],
            )
            for row in parameters.get("scaled_pairs", ())
        )
        return ReferenceForceFieldParameters(
            parameter_set_id="cpu-reference-validation-synthetic",
            parameter_set_version=f"1.0.0+{spec.spec_id}",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=atom_parameters,
            bonds=bonds,
            angles=angles,
            torsions=torsions,
            excluded_pairs=tuple(tuple(row) for row in parameters.get("excluded_pairs", ())),
            scaled_pairs=scaled_pairs,
            cutoff_angstrom=parameters["cutoff_angstrom"],
            switch_start_angstrom=parameters["switch_start_angstrom"],
            dielectric=parameters.get("dielectric", 1.0),
            screening_kappa_per_angstrom=parameters.get("screening_kappa_per_angstrom", 0.0),
            applicability_domain=_base_domain(),
            scientifically_validated=False,
            validation_evidence_sha256="",
            metadata={
                "fixture_profile_id": spec.spec_id,
                "fixture_profile_sha256": spec.spec_sha256,
                "parameter_origin": "synthetic_protocol_values_not_fit_data",
                "parameter_fitting_data": False,
                "scientifically_validated": False,
            },
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceValidationMaterializationError("fixture parameter rows cannot be materialized exactly") from exc


def _oracle_input(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
) -> IndependentAnalyticOracleInput:
    cell = None
    periodic = (False, False, False)
    if system.cell is not None:
        cell = tuple(float(value) for value in system.cell.orthorhombic_lengths().detach().cpu().tolist())
        periodic = system.cell.periodic
    return IndependentAnalyticOracleInput(
        coordinates_angstrom=tuple(
            tuple(float(value) for value in row) for row in system.coordinates[0].detach().cpu().tolist()
        ),
        topology_bonds=tuple((row.atom_i, row.atom_j) for row in system.bonds),
        atom_nonbonded=tuple(
            (
                row.atom_index,
                row.sigma_angstrom,
                row.epsilon_kcal_per_mol,
                row.charge_e,
            )
            for row in parameters.atom_parameters
        ),
        bonds=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.equilibrium_angstrom,
                row.force_constant_kcal_per_mol_angstrom2,
            )
            for row in parameters.bonds
        ),
        angles=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.equilibrium_radians,
                row.force_constant_kcal_per_mol_radian2,
            )
            for row in parameters.angles
        ),
        torsions=tuple(
            (
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.atom_l,
                row.periodicity,
                row.phase_radians,
                row.amplitude_kcal_per_mol,
            )
            for row in parameters.torsions
        ),
        excluded_pairs=parameters.excluded_pairs,
        scaled_pairs=tuple(
            (row.atom_i, row.atom_j, row.lj_scale, row.electrostatic_scale) for row in parameters.scaled_pairs
        ),
        cutoff_angstrom=parameters.cutoff_angstrom,
        switch_start_angstrom=parameters.switch_start_angstrom,
        dielectric=parameters.dielectric,
        screening_kappa_per_angstrom=parameters.screening_kappa_per_angstrom,
        orthorhombic_cell_angstrom=cell,
        periodic_axes=periodic,
        minimum_pair_distance_angstrom=(parameters.applicability_domain.minimum_pair_distance_angstrom),
    )


@dataclass(frozen=True, slots=True)
class MaterializedReferenceValidationVariant:
    """One exact runtime variant without any evaluated result."""

    variant_id: str
    system: AllAtomSystem
    parameters: ReferenceForceFieldParameters
    neighbors: CompactNeighborList
    oracle_input: IndependentAnalyticOracleInput | None
    purpose: str

    def __post_init__(self) -> None:
        if not self.variant_id or not self.purpose:
            raise ReferenceValidationMaterializationError("materialized variant identity and purpose must be non-empty")
        if self.system.coordinates.dtype != torch.float64:
            raise ReferenceValidationMaterializationError("materialized coordinates must use float64")
        if self.system.coordinates.device.type != "cpu":
            raise ReferenceValidationMaterializationError("materialized coordinates must be CPU-resident")

    @property
    def runtime_input_sha256(self) -> str:
        return _sha256(self.projection())

    def projection(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "purpose": self.purpose,
            "system_sha256": canonical_system_sha256(self.system),
            "topology_sha256": canonical_topology_sha256(self.system),
            "coordinate_sha256": canonical_coordinates_sha256(self.system),
            "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
            "parameter_topology_sha256": self.parameters.topology_sha256,
            "neighbor_graph_sha256": _neighbor_sha256(self.neighbors),
            "neighbor_cutoff_angstrom": (self.neighbors.diagnostics.cutoff_angstrom),
            "oracle_input_sha256": (None if self.oracle_input is None else self.oracle_input.input_sha256),
            "coordinate_dtype": "float64",
            "device": "cpu",
            "energy_or_force_evaluated": False,
            "validation_result_collected": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["runtime_input_sha256"] = self.runtime_input_sha256
        return payload


@dataclass(frozen=True, slots=True)
class MaterializedReferenceValidationCase:
    """All runtime variants required by one frozen protocol case."""

    case_id: str
    case_input_sha256: str
    fixture_profile_id: str
    fixture_profile_sha256: str
    mutation_contract_id: str
    mutation_contract_sha256: str
    expected_outcome: str
    expected_error_code: str | None
    variants: tuple[MaterializedReferenceValidationVariant, ...]

    def __post_init__(self) -> None:
        if not self.variants or len({row.variant_id for row in self.variants}) != len(self.variants):
            raise ReferenceValidationMaterializationError("a materialized case requires unique non-empty variants")
        if self.expected_outcome == "pass":
            if self.expected_error_code is not None or any(row.oracle_input is None for row in self.variants):
                raise ReferenceValidationMaterializationError("passing cases require oracle inputs and no error code")
        elif self.expected_outcome == "fail_closed":
            if not self.expected_error_code or any(row.oracle_input is not None for row in self.variants):
                raise ReferenceValidationMaterializationError(
                    "fail-closed cases require one error code and no oracle input"
                )
        else:
            raise ReferenceValidationMaterializationError("unsupported materialized case outcome")

    def projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "fixture_profile_id": self.fixture_profile_id,
            "fixture_profile_sha256": self.fixture_profile_sha256,
            "mutation_contract_id": self.mutation_contract_id,
            "mutation_contract_sha256": self.mutation_contract_sha256,
            "expected_outcome": self.expected_outcome,
            "expected_error_code": self.expected_error_code,
            "variant_count": len(self.variants),
            "variants": [row.to_dict() for row in self.variants],
            "result_fields_present": False,
        }

    @property
    def materialization_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["materialization_sha256"] = self.materialization_sha256
        return payload


def _variant(
    variant_id: str,
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    neighbors: CompactNeighborList,
    *,
    purpose: str,
    oracle_allowed: bool,
) -> MaterializedReferenceValidationVariant:
    oracle = _oracle_input(system, parameters) if oracle_allowed else None
    return MaterializedReferenceValidationVariant(
        variant_id=variant_id,
        system=system,
        parameters=parameters,
        neighbors=neighbors,
        oracle_input=oracle,
        purpose=purpose,
    )


def _replace_coordinates(
    system: AllAtomSystem,
    coordinates: object,
    *,
    cell: UnitCell | None | object = _KEEP_CELL,
) -> AllAtomSystem:
    selected_cell = system.cell if cell is _KEEP_CELL else cell
    return replace(
        system,
        coordinates=_coordinates_tensor(coordinates),
        cell=selected_cell,
    )


def _rebind(
    parameters: ReferenceForceFieldParameters,
    system: AllAtomSystem,
    **changes: Any,
) -> ReferenceForceFieldParameters:
    return replace(
        parameters,
        topology_sha256=canonical_topology_sha256(system),
        **changes,
    )


def _permuted_runtime(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    new_to_old: tuple[int, ...],
) -> tuple[AllAtomSystem, ReferenceForceFieldParameters]:
    if sorted(new_to_old) != list(range(system.atom_count)):
        raise ReferenceValidationMaterializationError("atom permutation must be a complete bijection")
    old_to_new = {old: new for new, old in enumerate(new_to_old)}
    atoms = tuple(replace(system.atoms[old], index=new, residue_index=0) for new, old in enumerate(new_to_old))
    bond_pairs = sorted(tuple(sorted((old_to_new[row.atom_i], old_to_new[row.atom_j]))) for row in system.bonds)
    bonds = tuple(
        Bond(
            index=index,
            atom_i=pair[0],
            atom_j=pair[1],
            order=1.0,
            source="frozen_validation_protocol",
        )
        for index, pair in enumerate(bond_pairs)
    )
    permuted = replace(
        system,
        atoms=atoms,
        bonds=bonds,
        residues=(replace(system.residues[0], atom_indices=tuple(range(system.atom_count))),),
        coordinates=system.coordinates[:, list(new_to_old), :].detach().clone(),
    )
    remapped_atoms = tuple(
        AtomNonbondedParameter(
            atom_index=old_to_new[row.atom_index],
            sigma_angstrom=row.sigma_angstrom,
            epsilon_kcal_per_mol=row.epsilon_kcal_per_mol,
            charge_e=row.charge_e,
        )
        for row in parameters.atom_parameters
    )
    remapped_bonds = tuple(
        HarmonicBondParameter(
            old_to_new[row.atom_i],
            old_to_new[row.atom_j],
            row.equilibrium_angstrom,
            row.force_constant_kcal_per_mol_angstrom2,
        )
        for row in parameters.bonds
    )
    remapped_angles = tuple(
        HarmonicAngleParameter(
            old_to_new[row.atom_i],
            old_to_new[row.atom_j],
            old_to_new[row.atom_k],
            row.equilibrium_radians,
            row.force_constant_kcal_per_mol_radian2,
        )
        for row in parameters.angles
    )
    remapped_torsions = tuple(
        PeriodicTorsionParameter(
            old_to_new[row.atom_i],
            old_to_new[row.atom_j],
            old_to_new[row.atom_k],
            old_to_new[row.atom_l],
            row.periodicity,
            row.phase_radians,
            row.amplitude_kcal_per_mol,
        )
        for row in parameters.torsions
    )
    remapped_scaled = tuple(
        PairScalingParameter(
            old_to_new[row.atom_i],
            old_to_new[row.atom_j],
            row.lj_scale,
            row.electrostatic_scale,
        )
        for row in parameters.scaled_pairs
    )
    remapped = _rebind(
        parameters,
        permuted,
        atom_parameters=remapped_atoms,
        bonds=remapped_bonds,
        angles=remapped_angles,
        torsions=remapped_torsions,
        excluded_pairs=tuple((old_to_new[first], old_to_new[second]) for first, second in parameters.excluded_pairs),
        scaled_pairs=remapped_scaled,
    )
    return permuted, remapped


def _materialize_variants(
    case: CPUReferenceValidationCase,
    fixture: CPUReferenceValidationSpec,
    mutation: CPUReferenceValidationSpec,
) -> tuple[MaterializedReferenceValidationVariant, ...]:
    system = _system_from_spec(fixture)
    parameters = _parameters_from_spec(fixture, system)
    payload = json.loads(mutation.canonical_payload_json)
    mutation_id = mutation.spec_id
    oracle_allowed = case.expected_outcome == "pass"

    def make(
        variant_id: str,
        selected_system: AllAtomSystem,
        selected_parameters: ReferenceForceFieldParameters,
        *,
        purpose: str,
        neighbor_cutoff: float | None = None,
        neighbor_coordinates: torch.Tensor | None = None,
    ) -> MaterializedReferenceValidationVariant:
        cutoff = selected_parameters.cutoff_angstrom if neighbor_cutoff is None else neighbor_cutoff
        return _variant(
            variant_id,
            selected_system,
            selected_parameters,
            _build_neighbors(
                selected_system,
                cutoff_angstrom=cutoff,
                coordinate_override=neighbor_coordinates,
            ),
            purpose=purpose,
            oracle_allowed=oracle_allowed,
        )

    if mutation_id == "identity_v1":
        return (make("identity", system, parameters, purpose="frozen_identity"),)

    if mutation_id == "switch_boundary_triplet_v1":
        variants = []
        for distance in payload["distances_angstrom"]:
            changed = _replace_coordinates(
                system,
                [[0.0, 0.0, 0.0], [float(distance), 0.0, 0.0]],
            )
            variants.append(
                make(
                    f"distance-{float(distance).hex()}",
                    changed,
                    _rebind(parameters, changed),
                    purpose="switch_boundary_distance",
                )
            )
        return tuple(variants)

    if mutation_id == "minimum_image_direct_equivalent_v1":
        periodic_system = _replace_coordinates(system, payload["periodic_coordinates_angstrom"])
        direct_system = _replace_coordinates(
            system,
            payload["direct_coordinates_angstrom"],
            cell=None,
        )
        return (
            make(
                "periodic-minimum-image",
                periodic_system,
                _rebind(parameters, periodic_system),
                purpose="periodic_minimum_image",
            ),
            make(
                "direct-equivalent",
                direct_system,
                _rebind(parameters, direct_system),
                purpose="direct_coordinate_equivalent",
            ),
        )

    if mutation_id == "central_difference_all_coordinates_v1":
        step = float(payload["coordinate_step_angstrom"])
        variants = [make("baseline", system, parameters, purpose="central_difference_baseline")]
        base = system.coordinates[0].detach().cpu().tolist()
        for atom_index in range(system.atom_count):
            for axis in range(3):
                for direction, sign in (("minus", -1.0), ("plus", 1.0)):
                    changed_rows = [list(row) for row in base]
                    changed_rows[atom_index][axis] += sign * step
                    changed = _replace_coordinates(system, changed_rows)
                    variants.append(
                        make(
                            f"atom-{atom_index}-{_AXIS_NAMES[axis]}-{direction}",
                            changed,
                            parameters,
                            purpose="central_difference_perturbation",
                        )
                    )
        return tuple(variants)

    if mutation_id == "rigid_translation_v1":
        translation = payload["translation_angstrom"]
        changed = _replace_coordinates(
            system,
            [
                [row[axis] + translation[axis] for axis in range(3)]
                for row in system.coordinates[0].detach().cpu().tolist()
            ],
        )
        return (
            make("baseline", system, parameters, purpose="translation_baseline"),
            make("translated", changed, parameters, purpose="rigid_translation"),
        )

    if mutation_id == "rigid_rotation_v1":
        rotation = payload["rotation_matrix"]
        changed_rows = []
        for row in system.coordinates[0].detach().cpu().tolist():
            changed_rows.append([sum(rotation[axis][column] * row[column] for column in range(3)) for axis in range(3)])
        changed = _replace_coordinates(system, changed_rows)
        return (
            make("baseline", system, parameters, purpose="rotation_baseline"),
            make("rotated", changed, parameters, purpose="rigid_rotation"),
        )

    if mutation_id == "atom_permutation_v1":
        permuted, remapped = _permuted_runtime(
            system,
            parameters,
            tuple(payload["new_to_old_atom_indices"]),
        )
        return (
            make("baseline", system, parameters, purpose="permutation_baseline"),
            make("permuted", permuted, remapped, purpose="atom_permutation"),
        )

    if mutation_id == "same_environment_repeat_v1":
        return tuple(
            make(
                f"repeat-{index + 1}",
                _system_from_spec(fixture),
                _parameters_from_spec(fixture, _system_from_spec(fixture)),
                purpose="same_environment_repeat",
            )
            for index in range(int(payload["repeat_count"]))
        )

    if mutation_id == "topology_element_crosswire_v1":
        atom_index = int(payload["atom_index"])
        changed_atoms = list(system.atoms)
        changed_atoms[atom_index] = replace(
            changed_atoms[atom_index],
            element=payload["replace_element"],
            atomic_number=payload["replace_atomic_number"],
        )
        changed = replace(system, atoms=tuple(changed_atoms))
        return (
            make(
                "topology-crosswire",
                changed,
                parameters,
                purpose="expected_parameter_topology_identity_mismatch",
            ),
        )

    if mutation_id == "drop_last_nonbonded_parameter_v1":
        changed = replace(parameters, atom_parameters=parameters.atom_parameters[:-1])
        return (
            make(
                "missing-nonbonded",
                system,
                changed,
                purpose="expected_missing_nonbonded_parameter",
            ),
        )

    if mutation_id == "drop_last_bond_parameter_v1":
        changed = replace(parameters, bonds=parameters.bonds[:-1])
        return (
            make(
                "missing-bond",
                system,
                changed,
                purpose="expected_missing_bond_parameter",
            ),
        )

    if mutation_id == "drop_last_angle_parameter_v1":
        changed = replace(parameters, angles=parameters.angles[:-1])
        return (
            make(
                "missing-angle",
                system,
                changed,
                purpose="expected_missing_angle_parameter",
            ),
        )

    if mutation_id == "drop_last_torsion_parameter_v1":
        changed = replace(parameters, torsions=parameters.torsions[:-1])
        return (
            make(
                "missing-torsion",
                system,
                changed,
                purpose="expected_missing_torsion_parameter",
            ),
        )

    if mutation_id == "stale_neighbor_graph_v1":
        stale_coordinates = _coordinates_tensor(payload["build_neighbor_coordinates_angstrom"])
        return (
            make(
                "stale-neighbor-graph",
                system,
                parameters,
                purpose="expected_stale_neighbor_graph",
                neighbor_coordinates=stale_coordinates,
            ),
        )

    if mutation_id == "short_neighbor_cutoff_v1":
        return (
            make(
                "short-neighbor-cutoff",
                system,
                parameters,
                purpose="expected_neighbor_cutoff_too_short",
                neighbor_cutoff=float(payload["neighbor_cutoff_angstrom"]),
            ),
        )

    if mutation_id == "atom_capacity_overflow_v1":
        domain = replace(
            parameters.applicability_domain,
            max_atoms=int(payload["applicability_max_atoms"]),
        )
        changed = replace(parameters, applicability_domain=domain)
        return (
            make(
                "atom-capacity-overflow",
                system,
                changed,
                purpose="expected_atom_capacity_overflow",
            ),
        )

    if mutation_id == "minimum_pair_distance_violation_v1":
        pair = payload["pair"]
        rows = system.coordinates[0].detach().cpu().tolist()
        rows[pair[1]] = list(rows[pair[0]])
        rows[pair[1]][0] += float(payload["distance_angstrom"])
        changed = _replace_coordinates(system, rows)
        return (
            make(
                "minimum-pair-distance",
                changed,
                parameters,
                purpose="expected_minimum_pair_distance_violation",
            ),
        )

    if mutation_id == "periodic_half_box_cutoff_v1":
        cutoff = float(payload["parameter_cutoff_angstrom"])
        changed = replace(parameters, cutoff_angstrom=cutoff)
        return (
            make(
                "periodic-half-box-cutoff",
                system,
                changed,
                purpose="expected_periodic_half_box_cutoff_violation",
                neighbor_cutoff=cutoff,
            ),
        )

    if mutation_id == "zero_length_angle_vector_v1":
        first, second = payload["coincident_atom_indices"]
        rows = system.coordinates[0].detach().cpu().tolist()
        rows[first] = list(rows[second])
        changed = _replace_coordinates(system, rows)
        return (
            make(
                "zero-length-angle-vector",
                changed,
                parameters,
                purpose="expected_zero_length_angle_vector",
            ),
        )

    if mutation_id == "collinear_torsion_v1":
        changed = _replace_coordinates(system, payload["coordinates_angstrom"])
        return (
            make(
                "collinear-torsion",
                changed,
                parameters,
                purpose="expected_collinear_torsion",
            ),
        )

    raise ReferenceValidationMaterializationError(f"unsupported frozen mutation contract {mutation_id!r}")


def materialize_frozen_reference_validation_case(
    case_id: str,
    protocol: CPUReferenceValidationProtocol | None = None,
) -> MaterializedReferenceValidationCase:
    """Materialize every runtime input variant for one exact frozen case."""

    selected = protocol or frozen_cpu_reference_validation_protocol()
    case_map = {row.case_id: row for row in selected.cases}
    fixture_map = {row.spec_id: row for row in selected.fixtures}
    mutation_map = {row.spec_id: row for row in selected.mutations}
    try:
        case = case_map[case_id]
        fixture = fixture_map[case.fixture_profile_id]
        mutation = mutation_map[case.mutation_contract_id]
    except KeyError as exc:
        raise ReferenceValidationMaterializationError("case references a missing frozen fixture or mutation") from exc
    if fixture.spec_sha256 != case.fixture_profile_sha256:
        raise ReferenceValidationMaterializationError("case fixture SHA-256 does not match the frozen protocol")
    if mutation.spec_sha256 != case.mutation_contract_sha256:
        raise ReferenceValidationMaterializationError("case mutation SHA-256 does not match the frozen protocol")
    return MaterializedReferenceValidationCase(
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        fixture_profile_id=fixture.spec_id,
        fixture_profile_sha256=fixture.spec_sha256,
        mutation_contract_id=mutation.spec_id,
        mutation_contract_sha256=mutation.spec_sha256,
        expected_outcome=case.expected_outcome,
        expected_error_code=case.expected_error_code,
        variants=_materialize_variants(case, fixture, mutation),
    )


def reference_validation_materialization_manifest_document(
    protocol: CPUReferenceValidationProtocol | None = None,
) -> dict[str, Any]:
    """Return exact materialization identities without evaluating physics."""

    selected = protocol or frozen_cpu_reference_validation_protocol()
    cases = tuple(materialize_frozen_reference_validation_case(row.case_id, selected) for row in selected.cases)
    variant_count = sum(len(row.variants) for row in cases)
    projection = {
        "schema_id": REFERENCE_VALIDATION_MATERIALIZER_SCHEMA_ID,
        "materializer_id": REFERENCE_VALIDATION_MATERIALIZER_ID,
        "materializer_version": REFERENCE_VALIDATION_MATERIALIZER_VERSION,
        "materializer_source_sha256": (reference_validation_materializer_source_sha256()),
        "protocol_sha256": selected.protocol_sha256,
        "fixture_manifest_sha256": selected.fixture_manifest_sha256,
        "materialization_policy": {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "coordinate_unit": "angstrom",
            "max_neighbors": MATERIALIZER_MAX_NEIGHBORS,
            "max_atoms_per_cell": MATERIALIZER_MAX_ATOMS_PER_CELL,
            "applicability_domain": _base_domain().to_dict(),
            "case_order_matches_protocol": True,
            "all_failure_rows_retained": True,
            "skipped_cases_allowed": False,
        },
        "coverage": {
            "fixture_count": len(selected.fixtures),
            "mutation_count": len(selected.mutations),
            "case_count": len(cases),
            "variant_count": variant_count,
            "expected_pass_case_count": sum(row.expected_outcome == "pass" for row in cases),
            "expected_fail_closed_case_count": sum(row.expected_outcome == "fail_closed" for row in cases),
        },
        "cases": [row.to_dict() for row in cases],
        "result_collection_performed": False,
        "energy_or_force_values_present": False,
        "metric_values_present": False,
        "validation_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    document = dict(projection)
    document["materialization_manifest_sha256"] = _sha256(projection)
    return document


__all__ = [
    "MATERIALIZER_DOMAIN_MAX_ANGLES",
    "MATERIALIZER_DOMAIN_MAX_ATOMS",
    "MATERIALIZER_DOMAIN_MAX_BONDS",
    "MATERIALIZER_DOMAIN_MAX_NONBONDED_PAIRS",
    "MATERIALIZER_DOMAIN_MAX_TORSIONS",
    "MATERIALIZER_MAX_ATOMS_PER_CELL",
    "MATERIALIZER_MAX_NEIGHBORS",
    "MATERIALIZER_MINIMUM_PAIR_DISTANCE_ANGSTROM",
    "MaterializedReferenceValidationCase",
    "MaterializedReferenceValidationVariant",
    "REFERENCE_VALIDATION_MATERIALIZER_ID",
    "REFERENCE_VALIDATION_MATERIALIZER_SCHEMA_ID",
    "REFERENCE_VALIDATION_MATERIALIZER_VERSION",
    "ReferenceValidationMaterializationError",
    "materialize_frozen_reference_validation_case",
    "reference_validation_materialization_manifest_document",
    "reference_validation_materializer_source_sha256",
]
