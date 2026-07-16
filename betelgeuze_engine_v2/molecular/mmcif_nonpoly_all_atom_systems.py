"""Canonical all-atom materialization for bounded mmCIF nonpoly preparation.

This adapter composes the bounded nonpoly identity, prepared chemical graph,
atom-site scalar, and hydrogen-coordinate carriers into one canonical
``AllAtomSystem`` per eligible source instance.  Materialization is allowed only
when the component graph and every atom coordinate exist and no intercomponent
connection would be silently discarded.

The resulting systems are structural bookkeeping artifacts.  Partial charges,
parameter-source binding, parameter assignment, geometry quality, protonation,
tautomer, chemistry, and scientific validity remain explicitly unestablished.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

import torch

from .mmcif_nonpoly_atom_site_scalar_values import (
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION,
    MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
    MmcifNonpolyAtomSiteScalarObservation,
    parse_mmcif_nonpoly_atom_site_scalar_values,
)
from .mmcif_nonpoly_hydrogen_coordinates import (
    MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
    MmcifHydrogenCoordinateInstanceReport,
    parse_mmcif_nonpoly_hydrogen_coordinates,
)
from .mmcif_nonpoly_canonical_topology import (
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION,
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
    parse_mmcif_nonpoly_canonical_topology,
)
from .mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
    MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
    MmcifNonpolyInstanceIdentity,
    parse_mmcif_nonpoly_identity,
)
from .mmcif_nonpoly_preparation import (
    MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
    MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
    MmcifNonpolyInstancePreparationReport,
    parse_mmcif_nonpoly_preparation,
)
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
)
from .serialization import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .validation import require_valid_all_atom_system


MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_all_atom_system_projection/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_SYSTEM_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_all_atom_system_source_binding/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_all_atom_system_document/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID = (
    "bounded_mmcif_neutral_coh_canonical_all_atom_materialization/1.0.0"
)
MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION = "1.0.0"

MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS = (
    "fixed_parent_offset_geometry_not_validated",
    "parameter_source_not_bound_to_system",
    "parameter_assignment_not_implemented",
    "partial_charge_assignment_not_implemented",
    "atom_masses_not_assigned",
    "chemistry_not_scientifically_validated",
    "source_format_round_trip_not_implemented",
    "intercomponent_coordination_not_materialized_as_bond",
)

_CREATED_STATUS = "canonical_all_atom_system_created"
_GRAPH_UNAVAILABLE_STATUS = "not_created_preparation_graph_unavailable"
_CONNECTION_BLOCKED_STATUS = "not_created_intercomponent_connection_unmaterialized"
_COORDINATE_UNAVAILABLE_STATUS = "not_created_coordinate_set_unavailable"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyAllAtomSystemError(ValueError):
    """Stable fail-closed error without source-coordinate or identity echo."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_all_atom_system:{self.code}: {self.detail}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_identity_bound": True,
        "preparation_graph_bound": True,
        "hydrogen_coordinate_set_bound": True,
        "source_atom_scalar_states_bound": True,
        "source_atom_coordinate_bits_preserved": True,
        "prepared_atom_and_bond_identities_preserved": True,
        "residue_and_chain_source_identity_bound": True,
        "canonical_all_atom_system_created": True,
        "canonical_all_atom_schema_validated": True,
        "canonical_hashes_bound": True,
        "failure_complete_instance_reports": True,
        "intercomponent_connections_materialized": False,
        "source_authenticated": False,
        "neighbor_geometry_interpreted": False,
        "stereochemistry_interpreted": False,
        "protonation_state_interpreted": False,
        "tautomer_selected": False,
        "coordinate_geometry_validated": False,
        "partial_charge_assigned": False,
        "parameter_source_bound": False,
        "parameter_assignment_implemented": False,
        "atom_masses_assigned": False,
        "parameterable": False,
        "source_format_round_trip_validated": False,
        "chemistry_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _canonical_system_document(system: AllAtomSystem) -> dict[str, Any]:
    return json.loads(canonical_system_json_bytes(system).decode("ascii"))


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAllAtomSystemInstanceReport:
    instance_identity_sha256: str
    component_id: str
    materialization_status: str
    materialization_blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    preparation_graph_sha256: str
    coordinate_set_sha256: str
    system: AllAtomSystem | None

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAllAtomSystemInstanceReport("
            f"component_id={self.component_id!r}, "
            f"materialization_status={self.materialization_status!r})"
        )

    @property
    def system_created(self) -> bool:
        return self.system is not None

    @property
    def system_sha256(self) -> str:
        return "" if self.system is None else canonical_system_sha256(self.system)

    @property
    def topology_sha256(self) -> str:
        return "" if self.system is None else canonical_topology_sha256(self.system)

    @property
    def coordinates_sha256(self) -> str:
        return "" if self.system is None else canonical_coordinates_sha256(self.system)

    def to_dict(self) -> dict[str, Any]:
        system = self.system
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "materialization_status": self.materialization_status,
            "materialization_blockers": list(self.materialization_blockers),
            "limitations": list(self.limitations),
            "preparation_graph_sha256": self.preparation_graph_sha256,
            "coordinate_set_sha256": self.coordinate_set_sha256,
            "system_created": self.system_created,
            "atom_count": 0 if system is None else system.atom_count,
            "bond_count": 0 if system is None else len(system.bonds),
            "residue_count": 0 if system is None else len(system.residues),
            "chain_count": 0 if system is None else len(system.chains),
            "model_count": 0 if system is None else system.model_count,
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "canonical_system_document": (
                None if system is None else _canonical_system_document(system)
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAllAtomSystemSnapshot:
    source_sha256: str
    identity_snapshot_sha256: str
    scalar_snapshot_sha256: str
    topology_snapshot_sha256: str
    preparation_snapshot_sha256: str
    hydrogen_coordinate_snapshot_sha256: str
    instance_reports: tuple[MmcifNonpolyAllAtomSystemInstanceReport, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAllAtomSystemSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"created_system_count={self.created_system_count})"
        )

    @property
    def created_system_count(self) -> int:
        return sum(row.system_created for row in self.instance_reports)

    @property
    def unavailable_system_count(self) -> int:
        return len(self.instance_reports) - self.created_system_count

    @property
    def system_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_all_atom_system_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_all_atom_system_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
                "system_projection_sha256": self.system_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
            "materializer_version": (
                MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
            ),
            "source_sha256": self.source_sha256,
            "identity_snapshot_sha256": self.identity_snapshot_sha256,
            "scalar_snapshot_sha256": self.scalar_snapshot_sha256,
            "topology_snapshot_sha256": self.topology_snapshot_sha256,
            "preparation_snapshot_sha256": self.preparation_snapshot_sha256,
            "hydrogen_coordinate_snapshot_sha256": (
                self.hydrogen_coordinate_snapshot_sha256
            ),
            "instance_count": len(self.instance_reports),
            "created_system_count": self.created_system_count,
            "unavailable_system_count": self.unavailable_system_count,
            "system_projection_sha256": self.system_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _known_scalar(
    observation: MmcifNonpolyAtomSiteScalarObservation,
    field: str,
) -> float | None:
    value = getattr(observation, field)
    return value.numeric_value if value.state == "known" else None


def _atom_metadata(
    atom: Any,
    coordinate: Any,
    scalar: MmcifNonpolyAtomSiteScalarObservation | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "prepared_atom_identity_sha256": atom.atom_identity_sha256,
        "origin": atom.origin,
        "parent_atom_index": atom.parent_atom_index,
        "coordinate_identity_sha256": coordinate.coordinate_identity_sha256,
        "coordinate_binary64_bits_hex": [
            coordinate.x_binary64_bits_hex,
            coordinate.y_binary64_bits_hex,
            coordinate.z_binary64_bits_hex,
        ],
        "coordinate_generation_method": coordinate.generation_method,
        "source_coordinate_value_identity_sha256": (
            coordinate.source_coordinate_value_identity_sha256
        ),
        "partial_charge_assignment_status": "not_implemented",
        "mass_assignment_status": "not_implemented",
    }
    if scalar is None:
        metadata["source_atom_scalar_status"] = "not_applicable_added_atom"
    else:
        metadata.update(
            {
                "source_atom_scalar_status": "bound",
                "source_atom_id": scalar.source_atom_id,
                "site_identity_sha256": scalar.site_identity_sha256,
                "scalar_value_identity_sha256": scalar.scalar_value_identity_sha256,
                "scalar_source_binding_sha256": scalar.scalar_source_binding_sha256,
                "occupancy_state": scalar.occupancy.state,
                "b_factor_state": scalar.b_iso_or_equiv.state,
                "formal_charge_state": scalar.formal_charge.state,
            }
        )
    return metadata


def _materialize_system(
    *,
    identity: MmcifNonpolyInstanceIdentity,
    preparation: MmcifNonpolyInstancePreparationReport,
    coordinates: MmcifHydrogenCoordinateInstanceReport,
    scalars_by_source_atom_id: Mapping[int, MmcifNonpolyAtomSiteScalarObservation],
    source_sha256: str,
    parent_snapshot_sha256: Mapping[str, str],
    coordination_edges: tuple[Mapping[str, Any], ...],
) -> AllAtomSystem:
    if len(preparation.atoms) != len(coordinates.atom_coordinates):
        raise MmcifNonpolyAllAtomSystemError(
            "atom_coordinate_count_mismatch",
            "prepared atoms and generated coordinates must have equal coverage",
        )

    atoms: list[Atom] = []
    coordinate_rows: list[tuple[float, float, float]] = []
    for prepared, coordinate in zip(
        preparation.atoms,
        coordinates.atom_coordinates,
        strict=True,
    ):
        if (
            prepared.index != coordinate.atom_index
            or prepared.atom_identity_sha256 != coordinate.atom_identity_sha256
            or prepared.origin != coordinate.origin
            or prepared.element != coordinate.element
        ):
            raise MmcifNonpolyAllAtomSystemError(
                "prepared_coordinate_crosswire",
                "prepared atom and coordinate identities must match exactly",
            )
        scalar = (
            scalars_by_source_atom_id.get(prepared.source_atom_id)
            if prepared.source_atom_id is not None
            else None
        )
        if prepared.origin == "source_atom" and scalar is None:
            raise MmcifNonpolyAllAtomSystemError(
                "source_scalar_missing",
                "every prepared source atom requires its exact scalar carrier",
            )
        atoms.append(
            Atom(
                index=prepared.index,
                name=prepared.name,
                element=prepared.element,
                atomic_number=atomic_number_for_element(prepared.element),
                residue_index=0,
                formal_charge=prepared.formal_charge,
                partial_charge_e=None,
                mass_da=None,
                serial=prepared.source_atom_id,
                altloc="",
                occupancy=None if scalar is None else _known_scalar(scalar, "occupancy"),
                b_factor=(
                    None
                    if scalar is None
                    else _known_scalar(scalar, "b_iso_or_equiv")
                ),
                aromatic=prepared.aromatic,
                stereo=prepared.stereo,
                metadata=_atom_metadata(prepared, coordinate, scalar),
            )
        )
        coordinate_rows.append(
            (
                coordinate.x_angstrom,
                coordinate.y_angstrom,
                coordinate.z_angstrom,
            )
        )

    bonds = tuple(
        Bond(
            index=row.index,
            atom_i=row.atom_i,
            atom_j=row.atom_j,
            order=row.order,
            aromatic=row.aromatic,
            stereo=row.stereo,
            source=row.origin,
            metadata={"prepared_bond_identity_sha256": row.bond_identity_sha256},
        )
        for row in preparation.bonds
    )
    insertion_code = (
        identity.pdb_ins_code.value
        if identity.pdb_ins_code.state == "known"
        else ""
    )
    identity_metadata = {
        "instance_identity_sha256": identity.instance_identity_sha256,
        "asym_id": identity.asym_id,
        "entity_id": identity.entity_id,
        "entity_type": identity.entity_type,
        "mon_id": identity.mon_id,
        "ndb_seq_num": identity.ndb_seq_num,
        "pdb_seq_num": identity.pdb_seq_num,
        "auth_seq_num": identity.auth_seq_num,
        "pdb_mon_id": identity.pdb_mon_id,
        "auth_mon_id": identity.auth_mon_id,
        "pdb_strand_id": identity.pdb_strand_id,
        "pdb_ins_code": identity.pdb_ins_code.to_dict(),
        "source_ordinal": identity.source_ordinal,
    }
    residue = Residue(
        index=0,
        name=identity.mon_id,
        chain_index=0,
        sequence_number=identity.source_ordinal + 1,
        atom_indices=tuple(range(len(atoms))),
        insertion_code=insertion_code,
        entity_type=identity.entity_type,
        hetero=True,
        metadata={
            **identity_metadata,
            "sequence_number_semantics": "bounded_source_ordinal_plus_one",
        },
    )
    chain = Chain(
        index=0,
        chain_id=identity.asym_id,
        residue_indices=(0,),
        entity_id=identity.entity_id,
        metadata={
            "source_asym_id": identity.asym_id,
            "source_pdb_strand_id": identity.pdb_strand_id,
        },
    )
    system = AllAtomSystem(
        system_id=f"mmcif-nonpoly-{identity.instance_identity_sha256[:20]}",
        atoms=tuple(atoms),
        bonds=bonds,
        residues=(residue,),
        chains=(chain,),
        coordinates=torch.tensor(
            [coordinate_rows],
            dtype=torch.float64,
            device="cpu",
        ),
        provenance=StructureProvenance(
            source_format="mmcif",
            source_id=identity.instance_identity_sha256,
            source_sha256=source_sha256,
            parser_name="bounded_mmcif_nonpoly_all_atom_system",
            parser_version=MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
            operations=(
                "bounded_neutral_coh_hydrogen_completion",
                "fixed_parent_offset_hydrogen_coordinates",
                "canonical_all_atom_system_materialization",
            ),
            source_digest_verified=False,
            transformation_chain_verified=False,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata={
                **dict(parent_snapshot_sha256),
                "coordinate_geometry_validated": False,
                "parameter_source_bound": False,
                "parameter_assignment_implemented": False,
                "partial_charge_assigned": False,
                "claim_safe": False,
            },
        ),
        coordinate_unit="angstrom",
        metadata={
            "profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
            "materializer_version": (
                MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
            ),
            **identity_metadata,
            "preparation_graph_sha256": preparation.preparation_graph_sha256,
            "coordinate_set_sha256": coordinates.coordinate_set_sha256,
            "geometry_limitations": list(coordinates.geometry_limitations),
            "preserved_intercomponent_coordination_edges": [
                dict(row) for row in coordination_edges
            ],
            "intercomponent_coordination_materialization": (
                "metadata_only_not_canonical_bond"
                if coordination_edges
                else "not_present"
            ),
            "parameterable": False,
            "source_format_round_trip_validated": False,
        },
    )
    validation = require_valid_all_atom_system(system)
    if validation.claim_stage.name.lower() != "contract_valid" or validation.claim_safe:
        raise MmcifNonpolyAllAtomSystemError(
            "unexpected_claim_promotion",
            "materialized systems must remain contract-valid and claim-blocked",
        )
    return system


def _instance_report(
    *,
    identity: MmcifNonpolyInstanceIdentity,
    preparation: MmcifNonpolyInstancePreparationReport,
    coordinates: MmcifHydrogenCoordinateInstanceReport,
    scalars_by_source_atom_id: Mapping[int, MmcifNonpolyAtomSiteScalarObservation],
    source_sha256: str,
    parent_snapshot_sha256: Mapping[str, str],
    coordination_edges: tuple[Mapping[str, Any], ...],
) -> MmcifNonpolyAllAtomSystemInstanceReport:
    if not (
        identity.instance_identity_sha256
        == preparation.instance_identity_sha256
        == coordinates.instance_identity_sha256
    ):
        raise MmcifNonpolyAllAtomSystemError(
            "instance_crosswire", "all materialization carriers must bind one instance"
        )
    if identity.mon_id != preparation.component_id:
        raise MmcifNonpolyAllAtomSystemError(
            "component_crosswire", "instance and preparation components must match"
        )

    if preparation.preparation_status != "prepared_component_graph":
        blockers = tuple(
            dict.fromkeys(
                (
                    "preparation_graph_unavailable",
                    *preparation.chemistry_blockers,
                )
            )
        )
        return MmcifNonpolyAllAtomSystemInstanceReport(
            instance_identity_sha256=identity.instance_identity_sha256,
            component_id=identity.mon_id,
            materialization_status=_GRAPH_UNAVAILABLE_STATUS,
            materialization_blockers=blockers,
            limitations=(),
            preparation_graph_sha256="",
            coordinate_set_sha256="",
            system=None,
        )

    connection_blockers = tuple(
        value
        for value in preparation.parameterability_blockers
        if value.startswith("intercomponent_")
        and value != "intercomponent_coordination_not_prepared"
    )
    if connection_blockers:
        return MmcifNonpolyAllAtomSystemInstanceReport(
            instance_identity_sha256=identity.instance_identity_sha256,
            component_id=identity.mon_id,
            materialization_status=_CONNECTION_BLOCKED_STATUS,
            materialization_blockers=connection_blockers,
            limitations=(),
            preparation_graph_sha256=preparation.preparation_graph_sha256,
            coordinate_set_sha256=coordinates.coordinate_set_sha256,
            system=None,
        )

    if coordinates.coordinate_status != "coordinate_bearing_prepared_graph":
        return MmcifNonpolyAllAtomSystemInstanceReport(
            instance_identity_sha256=identity.instance_identity_sha256,
            component_id=identity.mon_id,
            materialization_status=_COORDINATE_UNAVAILABLE_STATUS,
            materialization_blockers=coordinates.coordinate_blockers,
            limitations=(),
            preparation_graph_sha256=preparation.preparation_graph_sha256,
            coordinate_set_sha256="",
            system=None,
        )

    system = _materialize_system(
        identity=identity,
        preparation=preparation,
        coordinates=coordinates,
        scalars_by_source_atom_id=scalars_by_source_atom_id,
        source_sha256=source_sha256,
        parent_snapshot_sha256=parent_snapshot_sha256,
        coordination_edges=coordination_edges,
    )
    return MmcifNonpolyAllAtomSystemInstanceReport(
        instance_identity_sha256=identity.instance_identity_sha256,
        component_id=identity.mon_id,
        materialization_status=_CREATED_STATUS,
        materialization_blockers=(),
        limitations=MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS,
        preparation_graph_sha256=preparation.preparation_graph_sha256,
        coordinate_set_sha256=coordinates.coordinate_set_sha256,
        system=system,
    )


def parse_mmcif_nonpoly_all_atom_systems(
    text: str,
) -> MmcifNonpolyAllAtomSystemSnapshot:
    """Materialize eligible bounded nonpoly instances as canonical systems."""

    if type(text) is not str:
        raise TypeError("mmCIF all-atom-system input must be a string")
    identity = parse_mmcif_nonpoly_identity(text)
    scalar = parse_mmcif_nonpoly_atom_site_scalar_values(text)
    preparation = parse_mmcif_nonpoly_preparation(text)
    coordinates = parse_mmcif_nonpoly_hydrogen_coordinates(text)
    topology = parse_mmcif_nonpoly_canonical_topology(text)
    if not (
        identity.source_sha256
        == scalar.source_sha256
        == preparation.source_sha256
        == coordinates.source_sha256
        == topology.source_sha256
    ):
        raise MmcifNonpolyAllAtomSystemError(
            "source_crosswire", "all materialization carriers must bind one source"
        )
    if not (
        len(identity.instances)
        == len(preparation.instance_reports)
        == len(coordinates.instance_reports)
    ):
        raise MmcifNonpolyAllAtomSystemError(
            "instance_coverage_mismatch",
            "identity preparation and coordinate instance coverage must match",
        )
    scalars_by_source_atom_id = {
        row.source_atom_id: row for row in scalar.scalar_observations
    }
    if len(scalars_by_source_atom_id) != len(scalar.scalar_observations):
        raise MmcifNonpolyAllAtomSystemError(
            "scalar_identity_duplicate", "source scalar identities must be unique"
        )
    parent_snapshot_sha256 = {
        "identity_snapshot_sha256": identity.snapshot_sha256,
        "scalar_snapshot_sha256": scalar.snapshot_sha256,
        "topology_snapshot_sha256": topology.snapshot_sha256,
        "preparation_snapshot_sha256": preparation.snapshot_sha256,
        "hydrogen_coordinate_snapshot_sha256": coordinates.snapshot_sha256,
    }
    topology_atoms = {row.atom_index: row for row in topology.atoms}
    if len(topology_atoms) != len(topology.atoms):
        raise MmcifNonpolyAllAtomSystemError(
            "topology_atom_identity_duplicate", "topology atom indices must be unique"
        )
    coordination_edges_by_instance: dict[str, list[Mapping[str, Any]]] = {
        row.instance_identity_sha256: [] for row in identity.instances
    }
    for edge in topology.coordination_edges:
        try:
            endpoint_instances = {
                topology_atoms[edge.atom_i].instance_identity_sha256,
                topology_atoms[edge.atom_j].instance_identity_sha256,
            }
        except KeyError as exc:
            raise MmcifNonpolyAllAtomSystemError(
                "coordination_endpoint_missing",
                "coordination edges must reference selected topology atoms",
            ) from exc
        for instance in endpoint_instances:
            if instance not in coordination_edges_by_instance:
                raise MmcifNonpolyAllAtomSystemError(
                    "coordination_instance_missing",
                    "coordination edges must reference selected instances",
                )
            coordination_edges_by_instance[instance].append(edge.to_dict())
    reports = tuple(
        _instance_report(
            identity=identity_row,
            preparation=preparation_row,
            coordinates=coordinate_row,
            scalars_by_source_atom_id=scalars_by_source_atom_id,
            source_sha256=identity.source_sha256,
            parent_snapshot_sha256=parent_snapshot_sha256,
            coordination_edges=tuple(
                coordination_edges_by_instance[identity_row.instance_identity_sha256]
            ),
        )
        for identity_row, preparation_row, coordinate_row in zip(
            identity.instances,
            preparation.instance_reports,
            coordinates.instance_reports,
            strict=True,
        )
    )
    return MmcifNonpolyAllAtomSystemSnapshot(
        source_sha256=identity.source_sha256,
        identity_snapshot_sha256=identity.snapshot_sha256,
        scalar_snapshot_sha256=scalar.snapshot_sha256,
        topology_snapshot_sha256=topology.snapshot_sha256,
        preparation_snapshot_sha256=preparation.snapshot_sha256,
        hydrogen_coordinate_snapshot_sha256=coordinates.snapshot_sha256,
        instance_reports=reports,
    )


def mmcif_nonpoly_all_atom_system_projection(
    snapshot: MmcifNonpolyAllAtomSystemSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
        "materializer_version": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
        "preparation_snapshot_sha256": snapshot.preparation_snapshot_sha256,
        "hydrogen_coordinate_snapshot_sha256": (
            snapshot.hydrogen_coordinate_snapshot_sha256
        ),
        "instance_reports": [row.to_dict() for row in snapshot.instance_reports],
        "instance_order": "bounded_nonpoly_identity_source_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_all_atom_system_source_binding(
    snapshot: MmcifNonpolyAllAtomSystemSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "identity_snapshot_sha256": snapshot.identity_snapshot_sha256,
        "scalar_snapshot_sha256": snapshot.scalar_snapshot_sha256,
        "topology_snapshot_sha256": snapshot.topology_snapshot_sha256,
        "preparation_snapshot_sha256": snapshot.preparation_snapshot_sha256,
        "hydrogen_coordinate_snapshot_sha256": (
            snapshot.hydrogen_coordinate_snapshot_sha256
        ),
        "identity_profile_id": MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
        "identity_parser_version": MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
        "scalar_profile_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
        "scalar_parser_version": (
            MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION
        ),
        "topology_profile_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
        "topology_parser_version": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION,
        "preparation_profile_id": MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
        "preparation_parser_version": MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
        "hydrogen_coordinate_profile_id": (
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID
        ),
        "hydrogen_coordinate_generator_version": (
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION
        ),
        "coordinate_unit": "angstrom",
        "coordinate_dtype": "float64",
        "geometry_limitations": list(MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS),
        "materialization_limitations": list(
            MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS
        ),
        "intercomponent_coordination_policy": "preserve_as_metadata_not_bond",
        "intercomponent_covalent_policy": "fail_closed_without_materialization",
    }


def mmcif_nonpoly_all_atom_system_document(
    snapshot: MmcifNonpolyAllAtomSystemSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_all_atom_system_projection(snapshot)
    binding = mmcif_nonpoly_all_atom_system_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
        "materializer_version": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
        "system_projection": projection,
        "source_binding": binding,
        "system_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"all-atom materialization {label} digest invalid")
    return candidate


def require_mmcif_nonpoly_all_atom_system_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify embedded canonical systems, identities, digests, and claims."""

    if not isinstance(payload, Mapping):
        raise ValueError("all-atom materialization document must be a mapping")
    document = dict(payload)
    projection = document.get("system_projection")
    binding = document.get("source_binding")
    if (
        document.get("schema_id") != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID
        or document.get("profile_id") != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID
        or document.get("materializer_version")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        or not isinstance(projection, Mapping)
        or not isinstance(binding, Mapping)
    ):
        raise ValueError("all-atom materialization document envelope mismatch")
    projection_dict = dict(projection)
    binding_dict = dict(binding)
    projection_sha = _sha256(projection_dict)
    binding_sha = _sha256(binding_dict)
    if (
        document.get("system_projection_sha256") != projection_sha
        or document.get("source_binding_sha256") != binding_sha
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROJECTION_SCHEMA_ID
        or binding_dict.get("schema_id")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_SOURCE_BINDING_SCHEMA_ID
        or projection_dict.get("instance_order")
        != "bounded_nonpoly_identity_source_order"
        or projection_dict.get("profile_id")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID
        or projection_dict.get("materializer_version")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
    ):
        raise ValueError("all-atom materialization section digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID,
            "system_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("all-atom materialization snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection_dict.get(key) is not expected:
            raise ValueError("all-atom materialization claim boundary mismatch")

    reports = projection_dict.get("instance_reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("all-atom materialization reports must be non-empty")
    created = 0
    instances: set[str] = set()
    for item in reports:
        if not isinstance(item, Mapping):
            raise ValueError("all-atom materialization report invalid")
        report = dict(item)
        instance = _require_digest(report.get("instance_identity_sha256"), "instance")
        if instance in instances:
            raise ValueError("all-atom materialization instances must be unique")
        instances.add(instance)
        status = report.get("materialization_status")
        blockers = report.get("materialization_blockers")
        limitations = report.get("limitations")
        if not isinstance(blockers, list) or not isinstance(limitations, list):
            raise ValueError("all-atom materialization report lists invalid")
        system_document = report.get("canonical_system_document")
        if status == _CREATED_STATUS:
            created += 1
            if blockers or limitations != list(MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS):
                raise ValueError("created all-atom materialization boundary invalid")
            if not isinstance(system_document, Mapping):
                raise ValueError("created all-atom materialization system missing")
            encoded = json.dumps(
                dict(system_document),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            system = all_atom_system_from_canonical_json(encoded)
            validation = require_valid_all_atom_system(system)
            if validation.claim_stage.name.lower() != "contract_valid":
                raise ValueError("materialized all-atom system claim stage invalid")
            if (
                report.get("system_created") is not True
                or report.get("system_sha256") != canonical_system_sha256(system)
                or report.get("topology_sha256") != canonical_topology_sha256(system)
                or report.get("coordinates_sha256")
                != canonical_coordinates_sha256(system)
                or report.get("atom_count") != system.atom_count
                or report.get("bond_count") != len(system.bonds)
                or report.get("residue_count") != 1
                or report.get("chain_count") != 1
                or report.get("model_count") != 1
                or system.metadata.get("instance_identity_sha256") != instance
                or system.metadata.get("preparation_graph_sha256")
                != report.get("preparation_graph_sha256")
                or system.metadata.get("coordinate_set_sha256")
                != report.get("coordinate_set_sha256")
                or any(atom.partial_charge_e is not None for atom in system.atoms)
                or any(atom.mass_da is not None for atom in system.atoms)
                or system.provenance.source_sha256
                != binding_dict.get("source_sha256")
                or system.provenance.source_digest_verified
                or system.provenance.transformation_chain_verified
                or system.provenance.chemistry_validated
                or system.provenance.scientifically_validated
                or system.provenance.product_qualified
            ):
                raise ValueError("materialized canonical system identity mismatch")
            _require_digest(report.get("preparation_graph_sha256"), "graph")
            _require_digest(report.get("coordinate_set_sha256"), "coordinates")
        elif status in {
            _GRAPH_UNAVAILABLE_STATUS,
            _CONNECTION_BLOCKED_STATUS,
            _COORDINATE_UNAVAILABLE_STATUS,
        }:
            if (
                report.get("system_created") is not False
                or not blockers
                or limitations
                or system_document is not None
                or any(
                    report.get(key) not in {"", 0}
                    for key in (
                        "system_sha256",
                        "topology_sha256",
                        "coordinates_sha256",
                        "atom_count",
                        "bond_count",
                        "residue_count",
                        "chain_count",
                        "model_count",
                    )
                )
            ):
                raise ValueError("unavailable all-atom materialization report invalid")
            if status == _GRAPH_UNAVAILABLE_STATUS and (
                report.get("preparation_graph_sha256") != ""
                or report.get("coordinate_set_sha256") != ""
            ):
                raise ValueError("graph-unavailable materialization hashes invalid")
            if status == _CONNECTION_BLOCKED_STATUS:
                _require_digest(report.get("preparation_graph_sha256"), "graph")
                _require_digest(report.get("coordinate_set_sha256"), "coordinates")
            if status == _COORDINATE_UNAVAILABLE_STATUS:
                _require_digest(report.get("preparation_graph_sha256"), "graph")
                if report.get("coordinate_set_sha256") != "":
                    raise ValueError("coordinate-unavailable materialization hash invalid")
        else:
            raise ValueError("all-atom materialization status invalid")
    if (
        document.get("instance_count") != len(reports)
        or document.get("created_system_count") != created
        or document.get("unavailable_system_count") != len(reports) - created
    ):
        raise ValueError("all-atom materialization summary mismatch")
    source_sha = _require_digest(binding_dict.get("source_sha256"), "source")
    for key in (
        "identity_snapshot_sha256",
        "scalar_snapshot_sha256",
        "topology_snapshot_sha256",
        "preparation_snapshot_sha256",
        "hydrogen_coordinate_snapshot_sha256",
    ):
        digest = _require_digest(binding_dict.get(key), key)
        if document.get(key) != digest:
            raise ValueError("all-atom materialization source binding mismatch")
    if document.get("source_sha256") != source_sha:
        raise ValueError("all-atom materialization source digest mismatch")
    if (
        binding_dict.get("identity_profile_id") != MMCIF_NONPOLY_IDENTITY_PROFILE_ID
        or binding_dict.get("identity_parser_version")
        != MMCIF_NONPOLY_IDENTITY_PARSER_VERSION
        or binding_dict.get("scalar_profile_id")
        != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID
        or binding_dict.get("scalar_parser_version")
        != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION
        or binding_dict.get("topology_profile_id")
        != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID
        or binding_dict.get("topology_parser_version")
        != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION
        or binding_dict.get("preparation_profile_id")
        != MMCIF_NONPOLY_PREPARATION_PROFILE_ID
        or binding_dict.get("preparation_parser_version")
        != MMCIF_NONPOLY_PREPARATION_PARSER_VERSION
        or binding_dict.get("hydrogen_coordinate_profile_id")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID
        or binding_dict.get("hydrogen_coordinate_generator_version")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION
        or binding_dict.get("coordinate_unit") != "angstrom"
        or binding_dict.get("coordinate_dtype") != "float64"
        or binding_dict.get("geometry_limitations")
        != list(MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS)
        or binding_dict.get("materialization_limitations")
        != list(MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS)
        or binding_dict.get("intercomponent_coordination_policy")
        != "preserve_as_metadata_not_bond"
        or binding_dict.get("intercomponent_covalent_policy")
        != "fail_closed_without_materialization"
        or projection_dict.get("preparation_snapshot_sha256")
        != binding_dict.get("preparation_snapshot_sha256")
        or projection_dict.get("hydrogen_coordinate_snapshot_sha256")
        != binding_dict.get("hydrogen_coordinate_snapshot_sha256")
    ):
        raise ValueError("all-atom materialization source policy mismatch")
    return payload


def mmcif_nonpoly_all_atom_system_json_bytes(
    snapshot: MmcifNonpolyAllAtomSystemSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_all_atom_system_document(snapshot))


def write_mmcif_nonpoly_all_atom_system_json(
    path: str | Path,
    snapshot: MmcifNonpolyAllAtomSystemSnapshot,
) -> Path:
    """Atomically write a private canonical materialization document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_all_atom_system_json_bytes(snapshot) + b"\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return destination


__all__ = [
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_LIMITATIONS",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_ALL_ATOM_SYSTEM_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyAllAtomSystemError",
    "MmcifNonpolyAllAtomSystemInstanceReport",
    "MmcifNonpolyAllAtomSystemSnapshot",
    "mmcif_nonpoly_all_atom_system_document",
    "mmcif_nonpoly_all_atom_system_json_bytes",
    "mmcif_nonpoly_all_atom_system_projection",
    "mmcif_nonpoly_all_atom_system_source_binding",
    "parse_mmcif_nonpoly_all_atom_systems",
    "require_mmcif_nonpoly_all_atom_system_document",
    "write_mmcif_nonpoly_all_atom_system_json",
]
