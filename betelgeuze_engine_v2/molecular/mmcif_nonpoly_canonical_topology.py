"""Fail-closed bounded canonical topology for selected nonpoly mmCIF atoms.

The profile composes accepted component declarations, atom-site observations,
coordinate/scalar values, and ``_struct_conn`` declarations. Component bond
order, aromatic flag, and double-bond stereo are interpreted only for a small
controlled vocabulary. Identity-symmetry ``covale`` connections may create a
canonical :class:`Bond`; identity-symmetry ``metalc`` connections become
separate coordination edges and never become bonds.

Hydrogen bonds, disulfides, non-identity symmetry, delocalized/pi/polymeric
orders, atom chemistry, preparation, parameterization, and scientific geometry
assessment remain unsupported.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_nonpoly_atom_site_observations import (
    MmcifNonpolyAtomSiteObservationSnapshot,
    parse_mmcif_nonpoly_atom_site_observations,
)
from .mmcif_nonpoly_atom_site_scalar_values import (
    MmcifNonpolyAtomSiteScalarValueSnapshot,
    parse_mmcif_nonpoly_atom_site_scalar_values,
)
from .mmcif_nonpoly_component_declarations import (
    MmcifNonpolyComponentBondDeclaration,
    MmcifNonpolyComponentDeclarationSnapshot,
    parse_mmcif_nonpoly_component_declarations,
)
from .mmcif_semantics import MmcifSemanticValue
from .mmcif_struct_conn_declarations import (
    MmcifStructConnDeclarationSnapshot,
    parse_mmcif_struct_conn_declarations,
)
from .models import Bond


MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_canonical_topology_projection/1.0.0"
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_canonical_topology_source_binding/1.0.0"
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_canonical_topology_document/1.0.0"
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID = (
    "bounded_mmcif_nonpoly_canonical_topology/1.0.0"
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION = "1.0.0"

MMCIF_IDENTITY_SYMMETRY = "1_555"
MMCIF_SUPPORTED_CONNECTION_TYPES = ("covale", "metalc")
MMCIF_COMPONENT_BOND_ORDERS: Mapping[str, tuple[float, bool]] = MappingProxyType(
    {
        "SING": (1.0, False),
        "DOUB": (2.0, False),
        "TRIP": (3.0, False),
        "QUAD": (4.0, False),
        "AROM": (1.5, True),
    }
)
MMCIF_STRUCT_COVALENT_BOND_ORDERS: Mapping[str, float] = MappingProxyType(
    {"SING": 1.0, "DOUB": 2.0, "TRIP": 3.0, "QUAD": 4.0}
)
MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS: Mapping[str, str] = (
    MappingProxyType(
        {
            "_chem_comp_bond.value_order": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_chem_comp_bond.value_order.html"
            ),
            "_chem_comp_bond.pdbx_aromatic_flag": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_chem_comp_bond.pdbx_aromatic_flag.html"
            ),
            "_chem_comp_bond.pdbx_stereo_config": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_chem_comp_bond.pdbx_stereo_config.html"
            ),
            "_struct_conn.conn_type_id": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_struct_conn.conn_type_id.html"
            ),
            "_struct_conn.pdbx_value_order": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_struct_conn.pdbx_value_order.html"
            ),
            "_struct_conn.ptnr1_symmetry": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
                "_struct_conn.ptnr1_symmetry.html"
            ),
        }
    )
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyCanonicalTopologyError(ValueError):
    """Stable fail-closed topology error without private source values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_canonical_topology:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifCanonicalTopologyAtomReference:
    atom_index: int
    source_atom_id: int
    site_identity_sha256: str
    instance_identity_sha256: str
    component_atom_identity_sha256: str
    coordinate_value_identity_sha256: str
    scalar_value_identity_sha256: str
    component_id: str
    atom_id: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifCanonicalTopologyAtomReference("
            f"atom_index={self.atom_index}, source_atom_id={self.source_atom_id})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_index": self.atom_index,
            "source_atom_id": self.source_atom_id,
            "site_identity_sha256": self.site_identity_sha256,
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_atom_identity_sha256": self.component_atom_identity_sha256,
            "coordinate_value_identity_sha256": self.coordinate_value_identity_sha256,
            "scalar_value_identity_sha256": self.scalar_value_identity_sha256,
            "component_id": self.component_id,
            "atom_id": self.atom_id,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifCanonicalTopologyBond:
    index: int
    atom_i: int
    atom_j: int
    order: float
    aromatic: bool
    stereo: str
    source_kind: str
    source_id: str
    source_ordinal: int
    bond_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifCanonicalTopologyBond("
            f"index={self.index}, atom_i={self.atom_i}, atom_j={self.atom_j})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "order": self.order,
            "aromatic": self.aromatic,
            "stereo": self.stereo,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_ordinal": self.source_ordinal,
            "bond_identity_sha256": self.bond_identity_sha256,
        }

    def to_bond(self) -> Bond:
        return Bond(
            index=self.index,
            atom_i=self.atom_i,
            atom_j=self.atom_j,
            order=self.order,
            aromatic=self.aromatic,
            stereo=self.stereo,
            source=self.source_kind,
            metadata={
                "source_id": self.source_id,
                "source_ordinal": self.source_ordinal,
                "bond_identity_sha256": self.bond_identity_sha256,
            },
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifCanonicalCoordinationEdge:
    connection_id: str
    atom_i: int
    atom_j: int
    partner_1_site_identity_sha256: str
    partner_2_site_identity_sha256: str
    source_ordinal: int
    coordination_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifCanonicalCoordinationEdge("
            f"atom_i={self.atom_i}, atom_j={self.atom_j}, "
            f"source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "connection_type": "metalc",
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "partner_1_site_identity_sha256": self.partner_1_site_identity_sha256,
            "partner_2_site_identity_sha256": self.partner_2_site_identity_sha256,
            "partner_1_symmetry": MMCIF_IDENTITY_SYMMETRY,
            "partner_2_symmetry": MMCIF_IDENTITY_SYMMETRY,
            "source_ordinal": self.source_ordinal,
            "coordination_identity_sha256": self.coordination_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyCanonicalTopologySnapshot:
    source_sha256: str
    observation_snapshot_sha256: str
    scalar_snapshot_sha256: str
    scalar_projection_sha256: str
    scalar_source_binding_sha256: str
    component_snapshot_sha256: str
    component_projection_sha256: str
    component_source_binding_sha256: str
    struct_conn_snapshot_sha256: str
    struct_conn_projection_sha256: str
    struct_conn_source_binding_sha256: str
    atoms: tuple[MmcifCanonicalTopologyAtomReference, ...]
    bonds: tuple[MmcifCanonicalTopologyBond, ...]
    coordination_edges: tuple[MmcifCanonicalCoordinationEdge, ...]
    component_bond_count: int
    struct_covalent_bond_count: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyCanonicalTopologySnapshot("
            f"atom_count={len(self.atoms)}, bond_count={len(self.bonds)}, "
            f"coordination_count={len(self.coordination_edges)})"
        )

    @property
    def canonical_bonds(self) -> tuple[Bond, ...]:
        return tuple(row.to_bond() for row in self.bonds)

    @property
    def topology_sha256(self) -> str:
        return _sha256(_topology_payload(self.atoms, self.bonds, self.coordination_edges))

    @property
    def topology_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_canonical_topology_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_canonical_topology_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
                "topology_projection_sha256": self.topology_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "observation_snapshot_sha256": self.observation_snapshot_sha256,
            "scalar_snapshot_sha256": self.scalar_snapshot_sha256,
            "component_snapshot_sha256": self.component_snapshot_sha256,
            "struct_conn_snapshot_sha256": self.struct_conn_snapshot_sha256,
            "atom_count": len(self.atoms),
            "bond_count": len(self.bonds),
            "component_bond_count": self.component_bond_count,
            "struct_covalent_bond_count": self.struct_covalent_bond_count,
            "coordination_edge_count": len(self.coordination_edges),
            "topology_sha256": self.topology_sha256,
            "topology_projection_sha256": self.topology_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


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
        "source_declarations_bound": True,
        "atom_site_identity_joined": True,
        "component_bond_order_interpreted": True,
        "component_bond_aromaticity_interpreted": True,
        "component_bond_stereo_interpreted": True,
        "connection_type_interpreted": True,
        "identity_symmetry_interpreted": True,
        "covalence_interpreted": True,
        "coordination_interpreted": True,
        "coordination_edges_separate_from_bonds": True,
        "topology_interpreted": True,
        "canonical_bond_records_created": True,
        "source_authenticated": False,
        "non_identity_symmetry_supported": False,
        "hydrogen_connection_supported": False,
        "disulfide_connection_supported": False,
        "delocalized_pi_polymeric_bond_orders_supported": False,
        "atom_element_interpreted": False,
        "atom_formal_charge_crosschecked": False,
        "atom_aromaticity_crosschecked": False,
        "coordinate_geometry_interpreted": False,
        "bond_distance_assessed": False,
        "chemistry_interpreted": False,
        "preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _topology_payload(
    atoms: tuple[MmcifCanonicalTopologyAtomReference, ...],
    bonds: tuple[MmcifCanonicalTopologyBond, ...],
    coordination_edges: tuple[MmcifCanonicalCoordinationEdge, ...],
) -> dict[str, Any]:
    return {
        "schema_id": "betelgeuze.engine_v2_bounded_nonpoly_topology/1.0.0",
        "atom_order": "selected_source_atom_site_order",
        "bond_order": "component_instance_then_struct_conn_source_order",
        "atoms": [row.to_dict() for row in atoms],
        "bonds": [row.to_dict() for row in bonds],
        "coordination_edges": [row.to_dict() for row in coordination_edges],
    }


def _known_code(value: MmcifSemanticValue, *, field_name: str) -> str:
    if value.state != "known":
        raise MmcifNonpolyCanonicalTopologyError(
            "required_topology_code_missing",
            f"{field_name} must be explicitly known before topology creation",
            line_number=value.line_number,
        )
    return value.value.upper()


def _component_bond_semantics(
    row: MmcifNonpolyComponentBondDeclaration,
) -> tuple[float, bool, str]:
    order_code = _known_code(row.value_order, field_name="_chem_comp_bond.value_order")
    if order_code not in MMCIF_COMPONENT_BOND_ORDERS:
        raise MmcifNonpolyCanonicalTopologyError(
            "unsupported_component_bond_order",
            "component bond order is outside the bounded canonical mapping",
            line_number=row.value_order.line_number,
        )
    order, aromatic = MMCIF_COMPONENT_BOND_ORDERS[order_code]
    aromatic_code = _known_code(
        row.aromatic_flag, field_name="_chem_comp_bond.pdbx_aromatic_flag"
    )
    if aromatic_code not in {"Y", "N"} or (aromatic_code == "Y") is not aromatic:
        raise MmcifNonpolyCanonicalTopologyError(
            "component_bond_aromaticity_mismatch",
            "component bond order and aromatic flag must agree in this profile",
            line_number=row.aromatic_flag.line_number,
        )
    stereo_code = _known_code(
        row.stereo_config, field_name="_chem_comp_bond.pdbx_stereo_config"
    )
    if stereo_code not in {"N", "E", "Z"}:
        raise MmcifNonpolyCanonicalTopologyError(
            "unsupported_component_bond_stereo",
            "component bond stereo is outside the bounded vocabulary",
            line_number=row.stereo_config.line_number,
        )
    if order_code != "DOUB" and stereo_code != "N":
        raise MmcifNonpolyCanonicalTopologyError(
            "component_bond_stereo_order_mismatch",
            "E/Z stereo is supported only for non-aromatic double bonds",
            line_number=row.stereo_config.line_number,
        )
    return order, aromatic, "none" if stereo_code == "N" else stereo_code


def _bond_row(
    *,
    index: int,
    atom_i: int,
    atom_j: int,
    order: float,
    aromatic: bool,
    stereo: str,
    source_kind: str,
    source_id: str,
    source_ordinal: int,
) -> MmcifCanonicalTopologyBond:
    first, second = sorted((atom_i, atom_j))
    if first == second:
        raise MmcifNonpolyCanonicalTopologyError(
            "self_bond_not_supported", "canonical bond endpoints must be distinct"
        )
    identity = _sha256(
        {
            "atom_i": first,
            "atom_j": second,
            "order": order,
            "aromatic": aromatic,
            "stereo": stereo,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_ordinal": source_ordinal,
        }
    )
    return MmcifCanonicalTopologyBond(
        index=index,
        atom_i=first,
        atom_j=second,
        order=order,
        aromatic=aromatic,
        stereo=stereo,
        source_kind=source_kind,
        source_id=source_id,
        source_ordinal=source_ordinal,
        bond_identity_sha256=identity,
    )


def _atom_references(
    observation: MmcifNonpolyAtomSiteObservationSnapshot,
    scalar: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> tuple[MmcifCanonicalTopologyAtomReference, ...]:
    rows: list[MmcifCanonicalTopologyAtomReference] = []
    for atom_index, (source_row, scalar_row) in enumerate(
        zip(observation.observations, scalar.scalar_observations, strict=True)
    ):
        if (
            source_row.source_atom_id != scalar_row.source_atom_id
            or source_row.site_identity_sha256 != scalar_row.site_identity_sha256
            or source_row.source_ordinal != scalar_row.source_ordinal
        ):
            raise MmcifNonpolyCanonicalTopologyError(
                "scalar_observation_row_mismatch",
                "scalar and observation identities must match before topology creation",
            )
        rows.append(
            MmcifCanonicalTopologyAtomReference(
                atom_index=atom_index,
                source_atom_id=source_row.source_atom_id,
                site_identity_sha256=source_row.site_identity_sha256,
                instance_identity_sha256=source_row.instance_identity_sha256,
                component_atom_identity_sha256=(
                    source_row.component_atom_identity_sha256
                ),
                coordinate_value_identity_sha256=(
                    scalar_row.coordinate_value_identity_sha256
                ),
                scalar_value_identity_sha256=scalar_row.scalar_value_identity_sha256,
                component_id=source_row.label_comp_id,
                atom_id=source_row.label_atom_id,
                source_ordinal=source_row.source_ordinal,
            )
        )
    return tuple(rows)


def _component_bonds(
    atoms: tuple[MmcifCanonicalTopologyAtomReference, ...],
    components: MmcifNonpolyComponentDeclarationSnapshot,
) -> tuple[MmcifCanonicalTopologyBond, ...]:
    atom_index = {
        (row.instance_identity_sha256, row.atom_id): row.atom_index for row in atoms
    }
    instances: list[tuple[str, str]] = []
    seen_instances: set[str] = set()
    for row in atoms:
        if row.instance_identity_sha256 not in seen_instances:
            seen_instances.add(row.instance_identity_sha256)
            instances.append((row.instance_identity_sha256, row.component_id))
    bonds: list[MmcifCanonicalTopologyBond] = []
    pairs: set[tuple[int, int]] = set()
    for instance_identity, component_id in instances:
        for declaration in components.bond_declarations:
            if declaration.comp_id != component_id:
                continue
            endpoints = (
                atom_index.get((instance_identity, declaration.atom_id_1)),
                atom_index.get((instance_identity, declaration.atom_id_2)),
            )
            if endpoints[0] is None or endpoints[1] is None:
                raise MmcifNonpolyCanonicalTopologyError(
                    "component_bond_observation_missing",
                    "every replicated component bond endpoint must be observed",
                )
            order, aromatic, stereo = _component_bond_semantics(declaration)
            pair = tuple(sorted((endpoints[0], endpoints[1])))
            if pair in pairs:
                raise MmcifNonpolyCanonicalTopologyError(
                    "duplicate_canonical_bond_pair",
                    "canonical bond endpoint pairs must be unique",
                )
            pairs.add(pair)
            bonds.append(
                _bond_row(
                    index=len(bonds),
                    atom_i=endpoints[0],
                    atom_j=endpoints[1],
                    order=order,
                    aromatic=aromatic,
                    stereo=stereo,
                    source_kind="mmcif_chem_comp_bond",
                    source_id=f"{component_id}:{declaration.ordinal}",
                    source_ordinal=declaration.source_ordinal,
                )
            )
    return tuple(bonds)


def _identity_symmetry(value: MmcifSemanticValue, *, partner: str) -> None:
    if value.state != "known" or value.value != MMCIF_IDENTITY_SYMMETRY:
        raise MmcifNonpolyCanonicalTopologyError(
            "non_identity_symmetry_not_supported",
            f"{partner} must use the explicit identity symmetry in this profile",
            line_number=value.line_number,
        )


def _struct_connections(
    observation: MmcifNonpolyAtomSiteObservationSnapshot,
    struct_conn: MmcifStructConnDeclarationSnapshot,
    component_bonds: tuple[MmcifCanonicalTopologyBond, ...],
) -> tuple[
    tuple[MmcifCanonicalTopologyBond, ...],
    tuple[MmcifCanonicalCoordinationEdge, ...],
]:
    by_site = {
        row.site_identity_sha256: index
        for index, row in enumerate(observation.observations)
    }
    pairs = {(row.atom_i, row.atom_j) for row in component_bonds}
    added_bonds: list[MmcifCanonicalTopologyBond] = []
    coordination: list[MmcifCanonicalCoordinationEdge] = []
    for declaration, binding in zip(
        struct_conn.declarations, observation.endpoint_bindings, strict=True
    ):
        if (
            declaration.connection_id != binding.connection_id
            or declaration.source_ordinal != binding.source_ordinal
        ):
            raise MmcifNonpolyCanonicalTopologyError(
                "struct_conn_observation_binding_mismatch",
                "connection declarations and observed endpoints must match exactly",
            )
        _identity_symmetry(declaration.partner_1.symmetry, partner="partner 1")
        _identity_symmetry(declaration.partner_2.symmetry, partner="partner 2")
        connection_type = _known_code(
            declaration.connection_type, field_name="_struct_conn.conn_type_id"
        ).lower()
        if connection_type not in MMCIF_SUPPORTED_CONNECTION_TYPES:
            raise MmcifNonpolyCanonicalTopologyError(
                "unsupported_connection_type",
                "connection type is outside the bounded covalent/coordination profile",
                line_number=declaration.connection_type.line_number,
            )
        try:
            endpoint_1 = by_site[binding.partner_1_site_identity_sha256]
            endpoint_2 = by_site[binding.partner_2_site_identity_sha256]
        except KeyError as exc:
            raise MmcifNonpolyCanonicalTopologyError(
                "connection_endpoint_observation_missing",
                "each interpreted connection endpoint must be observed",
            ) from exc
        pair = tuple(sorted((endpoint_1, endpoint_2)))
        if pair[0] == pair[1] or pair in pairs:
            raise MmcifNonpolyCanonicalTopologyError(
                "duplicate_or_self_connection_pair",
                "connection pairs must be distinct and absent from existing topology",
            )
        pairs.add(pair)
        if connection_type == "metalc":
            if declaration.value_order.state == "known":
                raise MmcifNonpolyCanonicalTopologyError(
                    "coordination_bond_order_not_supported",
                    "metal coordination must not be converted from a bond order",
                    line_number=declaration.value_order.line_number,
                )
            identity = _sha256(
                {
                    "connection_id": declaration.connection_id,
                    "atom_i": pair[0],
                    "atom_j": pair[1],
                    "connection_type": "metalc",
                    "partner_1_site_identity_sha256": (
                        binding.partner_1_site_identity_sha256
                    ),
                    "partner_2_site_identity_sha256": (
                        binding.partner_2_site_identity_sha256
                    ),
                    "partner_1_symmetry": MMCIF_IDENTITY_SYMMETRY,
                    "partner_2_symmetry": MMCIF_IDENTITY_SYMMETRY,
                    "source_ordinal": declaration.source_ordinal,
                }
            )
            coordination.append(
                MmcifCanonicalCoordinationEdge(
                    connection_id=declaration.connection_id,
                    atom_i=pair[0],
                    atom_j=pair[1],
                    partner_1_site_identity_sha256=(
                        binding.partner_1_site_identity_sha256
                    ),
                    partner_2_site_identity_sha256=(
                        binding.partner_2_site_identity_sha256
                    ),
                    source_ordinal=declaration.source_ordinal,
                    coordination_identity_sha256=identity,
                )
            )
            continue
        order_code = _known_code(
            declaration.value_order, field_name="_struct_conn.pdbx_value_order"
        )
        if order_code not in MMCIF_STRUCT_COVALENT_BOND_ORDERS:
            raise MmcifNonpolyCanonicalTopologyError(
                "unsupported_struct_covalent_bond_order",
                "covalent connection order is outside the bounded mapping",
                line_number=declaration.value_order.line_number,
            )
        added_bonds.append(
            _bond_row(
                index=len(component_bonds) + len(added_bonds),
                atom_i=pair[0],
                atom_j=pair[1],
                order=MMCIF_STRUCT_COVALENT_BOND_ORDERS[order_code],
                aromatic=False,
                stereo="none",
                source_kind="mmcif_struct_conn_covale",
                source_id=declaration.connection_id,
                source_ordinal=declaration.source_ordinal,
            )
        )
    return tuple(added_bonds), tuple(coordination)


def parse_mmcif_nonpoly_canonical_topology(
    text: str,
) -> MmcifNonpolyCanonicalTopologySnapshot:
    """Create the bounded canonical nonpoly bond/coordination topology."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly canonical topology input must be a string")
    observation = parse_mmcif_nonpoly_atom_site_observations(text)
    scalar = parse_mmcif_nonpoly_atom_site_scalar_values(text)
    components = parse_mmcif_nonpoly_component_declarations(text)
    struct_conn = parse_mmcif_struct_conn_declarations(text)
    if not (
        observation.source_sha256
        == scalar.source_sha256
        == components.source_sha256
        == struct_conn.source_sha256
    ):
        raise MmcifNonpolyCanonicalTopologyError(
            "source_carrier_mismatch",
            "all topology source carriers must bind the same source bytes",
        )
    if (
        scalar.observation_snapshot_sha256 != observation.snapshot_sha256
        or observation.component_snapshot_sha256 != components.snapshot_sha256
        or observation.struct_conn_snapshot_sha256 != struct_conn.snapshot_sha256
    ):
        raise MmcifNonpolyCanonicalTopologyError(
            "source_snapshot_mismatch",
            "topology dependencies must bind the exact accepted snapshots",
        )
    atoms = _atom_references(observation, scalar)
    component_bonds = _component_bonds(atoms, components)
    struct_bonds, coordination = _struct_connections(
        observation, struct_conn, component_bonds
    )
    return MmcifNonpolyCanonicalTopologySnapshot(
        source_sha256=observation.source_sha256,
        observation_snapshot_sha256=observation.snapshot_sha256,
        scalar_snapshot_sha256=scalar.snapshot_sha256,
        scalar_projection_sha256=scalar.scalar_projection_sha256,
        scalar_source_binding_sha256=scalar.source_binding_sha256,
        component_snapshot_sha256=components.snapshot_sha256,
        component_projection_sha256=components.declaration_projection_sha256,
        component_source_binding_sha256=components.source_binding_sha256,
        struct_conn_snapshot_sha256=struct_conn.snapshot_sha256,
        struct_conn_projection_sha256=struct_conn.declaration_projection_sha256,
        struct_conn_source_binding_sha256=struct_conn.source_binding_sha256,
        atoms=atoms,
        bonds=component_bonds + struct_bonds,
        coordination_edges=coordination,
        component_bond_count=len(component_bonds),
        struct_covalent_bond_count=len(struct_bonds),
    )


def mmcif_nonpoly_canonical_topology_projection(
    snapshot: MmcifNonpolyCanonicalTopologySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION,
        "scalar_projection_sha256": snapshot.scalar_projection_sha256,
        "component_projection_sha256": snapshot.component_projection_sha256,
        "struct_conn_projection_sha256": snapshot.struct_conn_projection_sha256,
        "topology": _topology_payload(
            snapshot.atoms, snapshot.bonds, snapshot.coordination_edges
        ),
        "topology_sha256": snapshot.topology_sha256,
        **_claim_policy(),
    }


def mmcif_nonpoly_canonical_topology_source_binding(
    snapshot: MmcifNonpolyCanonicalTopologySnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "observation_snapshot_sha256": snapshot.observation_snapshot_sha256,
        "scalar_snapshot_sha256": snapshot.scalar_snapshot_sha256,
        "scalar_source_binding_sha256": snapshot.scalar_source_binding_sha256,
        "component_snapshot_sha256": snapshot.component_snapshot_sha256,
        "component_source_binding_sha256": snapshot.component_source_binding_sha256,
        "struct_conn_snapshot_sha256": snapshot.struct_conn_snapshot_sha256,
        "struct_conn_source_binding_sha256": snapshot.struct_conn_source_binding_sha256,
        "dictionary_items": dict(
            MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS
        ),
        "supported_component_bond_orders": list(MMCIF_COMPONENT_BOND_ORDERS),
        "supported_struct_covalent_bond_orders": list(
            MMCIF_STRUCT_COVALENT_BOND_ORDERS
        ),
        "supported_connection_types": list(MMCIF_SUPPORTED_CONNECTION_TYPES),
        "supported_symmetry": MMCIF_IDENTITY_SYMMETRY,
    }


def mmcif_nonpoly_canonical_topology_document(
    snapshot: MmcifNonpolyCanonicalTopologySnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_canonical_topology_projection(snapshot)
    binding = mmcif_nonpoly_canonical_topology_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION,
        "topology_projection": projection,
        "source_binding": binding,
        "topology_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"nonpoly canonical topology {label} digest invalid")
    return candidate


def _require_topology(payload: object) -> tuple[int, int, int, int, int]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly canonical topology payload must be a mapping")
    topology = dict(payload)
    if topology.get("schema_id") != "betelgeuze.engine_v2_bounded_nonpoly_topology/1.0.0":
        raise ValueError("nonpoly canonical topology payload schema mismatch")
    atoms = topology.get("atoms")
    bonds = topology.get("bonds")
    coordination = topology.get("coordination_edges")
    if not isinstance(atoms, list) or not atoms:
        raise ValueError("nonpoly canonical topology atoms must be non-empty")
    if not isinstance(bonds, list) or not isinstance(coordination, list):
        raise ValueError("nonpoly canonical topology edges must be lists")
    if topology.get("atom_order") != "selected_source_atom_site_order":
        raise ValueError("nonpoly canonical topology atom order mismatch")
    if topology.get("bond_order") != "component_instance_then_struct_conn_source_order":
        raise ValueError("nonpoly canonical topology bond order mismatch")

    source_ids: set[int] = set()
    site_ids: set[str] = set()
    previous_source_ordinal = -1
    for index, item in enumerate(atoms):
        if not isinstance(item, Mapping):
            raise ValueError("nonpoly canonical topology atom must be a mapping")
        atom = dict(item)
        if atom.get("atom_index") != index:
            raise ValueError("nonpoly canonical topology atom indices must be contiguous")
        source_id = atom.get("source_atom_id")
        ordinal = atom.get("source_ordinal")
        if type(source_id) is not int or source_id <= 0:
            raise ValueError("nonpoly canonical topology source atom id invalid")
        if type(ordinal) is not int or ordinal < 0:
            raise ValueError("nonpoly canonical topology source ordinal invalid")
        if ordinal <= previous_source_ordinal:
            raise ValueError("nonpoly canonical topology source ordinals must increase")
        previous_source_ordinal = ordinal
        site_id = _require_digest(atom.get("site_identity_sha256"), "site identity")
        for key in (
            "instance_identity_sha256",
            "component_atom_identity_sha256",
            "coordinate_value_identity_sha256",
            "scalar_value_identity_sha256",
        ):
            _require_digest(atom.get(key), key)
        if (
            source_id in source_ids
            or site_id in site_ids
            or type(atom.get("component_id")) is not str
            or not atom.get("component_id")
            or type(atom.get("atom_id")) is not str
            or not atom.get("atom_id")
        ):
            raise ValueError("nonpoly canonical topology atom identity invalid")
        source_ids.add(source_id)
        site_ids.add(site_id)

    pairs: set[tuple[int, int]] = set()
    component_bond_count = 0
    struct_covalent_bond_count = 0
    for index, item in enumerate(bonds):
        if not isinstance(item, Mapping):
            raise ValueError("nonpoly canonical topology bond must be a mapping")
        bond = dict(item)
        if bond.get("index") != index:
            raise ValueError("nonpoly canonical topology bond indices must be contiguous")
        atom_i = bond.get("atom_i")
        atom_j = bond.get("atom_j")
        if (
            type(atom_i) is not int
            or type(atom_j) is not int
            or not 0 <= atom_i < atom_j < len(atoms)
        ):
            raise ValueError("nonpoly canonical topology bond endpoints invalid")
        pair = (atom_i, atom_j)
        if pair in pairs:
            raise ValueError("nonpoly canonical topology bond pairs must be unique")
        pairs.add(pair)
        order = bond.get("order")
        aromatic = bond.get("aromatic")
        stereo = bond.get("stereo")
        source_kind = bond.get("source_kind")
        if type(order) not in (int, float) or float(order) not in {1.0, 1.5, 2.0, 3.0, 4.0}:
            raise ValueError("nonpoly canonical topology bond order invalid")
        if type(aromatic) is not bool or aromatic is not (float(order) == 1.5):
            raise ValueError("nonpoly canonical topology bond aromaticity invalid")
        if stereo not in {"none", "E", "Z"} or (
            stereo != "none" and float(order) != 2.0
        ):
            raise ValueError("nonpoly canonical topology bond stereo invalid")
        if source_kind not in {"mmcif_chem_comp_bond", "mmcif_struct_conn_covale"}:
            raise ValueError("nonpoly canonical topology bond source kind invalid")
        if source_kind == "mmcif_struct_conn_covale" and (
            aromatic or stereo != "none" or float(order) == 1.5
        ):
            raise ValueError("nonpoly canonical struct_conn bond semantics invalid")
        if source_kind == "mmcif_chem_comp_bond":
            component_bond_count += 1
        else:
            struct_covalent_bond_count += 1
        if type(bond.get("source_id")) is not str or not bond.get("source_id"):
            raise ValueError("nonpoly canonical topology bond source id invalid")
        if type(bond.get("source_ordinal")) is not int or bond["source_ordinal"] < 0:
            raise ValueError("nonpoly canonical topology bond source ordinal invalid")
        identity = _sha256(
            {
                "atom_i": atom_i,
                "atom_j": atom_j,
                "order": float(order),
                "aromatic": aromatic,
                "stereo": stereo,
                "source_kind": source_kind,
                "source_id": bond["source_id"],
                "source_ordinal": bond["source_ordinal"],
            }
        )
        if bond.get("bond_identity_sha256") != identity:
            raise ValueError("nonpoly canonical topology bond identity mismatch")

    coordination_pairs: set[tuple[int, int]] = set()
    connection_ids: set[str] = set()
    for item in coordination:
        if not isinstance(item, Mapping):
            raise ValueError("nonpoly canonical coordination edge must be a mapping")
        edge = dict(item)
        atom_i = edge.get("atom_i")
        atom_j = edge.get("atom_j")
        if (
            type(atom_i) is not int
            or type(atom_j) is not int
            or not 0 <= atom_i < atom_j < len(atoms)
        ):
            raise ValueError("nonpoly canonical coordination endpoints invalid")
        pair = (atom_i, atom_j)
        if pair in pairs or pair in coordination_pairs:
            raise ValueError("nonpoly canonical coordination pairs must be separate")
        coordination_pairs.add(pair)
        if (
            edge.get("connection_type") != "metalc"
            or edge.get("partner_1_symmetry") != MMCIF_IDENTITY_SYMMETRY
            or edge.get("partner_2_symmetry") != MMCIF_IDENTITY_SYMMETRY
            or type(edge.get("connection_id")) is not str
            or not edge.get("connection_id")
            or type(edge.get("source_ordinal")) is not int
            or edge["source_ordinal"] < 0
        ):
            raise ValueError("nonpoly canonical coordination semantics invalid")
        connection_id = str(edge["connection_id"])
        if connection_id in connection_ids:
            raise ValueError("nonpoly canonical coordination ids must be unique")
        connection_ids.add(connection_id)
        first_site = _require_digest(
            edge.get("partner_1_site_identity_sha256"), "coordination partner 1"
        )
        second_site = _require_digest(
            edge.get("partner_2_site_identity_sha256"), "coordination partner 2"
        )
        identity = _sha256(
            {
                "connection_id": edge["connection_id"],
                "atom_i": atom_i,
                "atom_j": atom_j,
                "connection_type": "metalc",
                "partner_1_site_identity_sha256": first_site,
                "partner_2_site_identity_sha256": second_site,
                "partner_1_symmetry": MMCIF_IDENTITY_SYMMETRY,
                "partner_2_symmetry": MMCIF_IDENTITY_SYMMETRY,
                "source_ordinal": edge["source_ordinal"],
            }
        )
        if edge.get("coordination_identity_sha256") != identity:
            raise ValueError("nonpoly canonical coordination identity mismatch")
        if first_site == second_site:
            raise ValueError("nonpoly canonical coordination sites must be distinct")
        endpoint_sites = {
            str(atoms[atom_i]["site_identity_sha256"]),
            str(atoms[atom_j]["site_identity_sha256"]),
        }
        if {first_site, second_site} != endpoint_sites:
            raise ValueError("nonpoly canonical coordination site binding mismatch")
    return (
        len(atoms),
        len(bonds),
        len(coordination),
        component_bond_count,
        struct_covalent_bond_count,
    )


def require_mmcif_nonpoly_canonical_topology_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly canonical topology document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly canonical topology document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID:
        raise ValueError("nonpoly canonical topology profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION:
        raise ValueError("nonpoly canonical topology parser version mismatch")
    projection = document.get("topology_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly canonical topology sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly canonical topology projection schema mismatch")
    if binding.get("schema_id") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("nonpoly canonical topology source binding schema mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("topology_projection_sha256") != projection_digest:
        raise ValueError("nonpoly canonical topology projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly canonical topology source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
            "topology_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly canonical topology snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly canonical topology claim policy mismatch")

    topology = projection.get("topology")
    (
        atom_count,
        bond_count,
        coordination_count,
        component_bond_count,
        struct_covalent_bond_count,
    ) = _require_topology(topology)
    if document.get("atom_count") != atom_count or document.get("bond_count") != bond_count:
        raise ValueError("nonpoly canonical topology count mismatch")
    if document.get("coordination_edge_count") != coordination_count:
        raise ValueError("nonpoly canonical coordination count mismatch")
    if (
        type(document.get("component_bond_count")) is not int
        or type(document.get("struct_covalent_bond_count")) is not int
        or document["component_bond_count"] != component_bond_count
        or document["struct_covalent_bond_count"] != struct_covalent_bond_count
    ):
        raise ValueError("nonpoly canonical topology bond source counts mismatch")
    if not isinstance(topology, Mapping):
        raise ValueError("nonpoly canonical topology payload must be a mapping")
    topology_digest = _sha256(dict(topology))
    if projection.get("topology_sha256") != topology_digest:
        raise ValueError("nonpoly canonical topology payload digest mismatch")
    if document.get("topology_sha256") != topology_digest:
        raise ValueError("nonpoly canonical topology digest mismatch")

    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly canonical topology source digest mismatch")
    for key in (
        "observation_snapshot_sha256",
        "scalar_snapshot_sha256",
        "component_snapshot_sha256",
        "struct_conn_snapshot_sha256",
    ):
        digest = _require_digest(binding.get(key), key)
        if document.get(key) != digest:
            raise ValueError(f"nonpoly canonical topology {key} mismatch")
    for key in (
        "scalar_projection_sha256",
        "component_projection_sha256",
        "struct_conn_projection_sha256",
    ):
        _require_digest(projection.get(key), key)
    for key in (
        "scalar_source_binding_sha256",
        "component_source_binding_sha256",
        "struct_conn_source_binding_sha256",
    ):
        _require_digest(binding.get(key), key)
    if binding.get("dictionary_items") != MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS:
        raise ValueError("nonpoly canonical topology dictionary binding mismatch")
    if binding.get("supported_component_bond_orders") != list(MMCIF_COMPONENT_BOND_ORDERS):
        raise ValueError("nonpoly canonical topology component order policy mismatch")
    if binding.get("supported_struct_covalent_bond_orders") != list(
        MMCIF_STRUCT_COVALENT_BOND_ORDERS
    ):
        raise ValueError("nonpoly canonical topology struct order policy mismatch")
    if binding.get("supported_connection_types") != list(
        MMCIF_SUPPORTED_CONNECTION_TYPES
    ) or binding.get("supported_symmetry") != MMCIF_IDENTITY_SYMMETRY:
        raise ValueError("nonpoly canonical topology connection policy mismatch")
    return payload


def mmcif_nonpoly_canonical_topology_json_bytes(
    snapshot: MmcifNonpolyCanonicalTopologySnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_canonical_topology_document(snapshot))


def write_mmcif_nonpoly_canonical_topology_json(
    path: str | Path,
    snapshot: MmcifNonpolyCanonicalTopologySnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_canonical_topology_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
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
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "MMCIF_COMPONENT_BOND_ORDERS",
    "MMCIF_IDENTITY_SYMMETRY",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PARSER_VERSION",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_CANONICAL_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_STRUCT_COVALENT_BOND_ORDERS",
    "MMCIF_SUPPORTED_CONNECTION_TYPES",
    "MmcifCanonicalCoordinationEdge",
    "MmcifCanonicalTopologyAtomReference",
    "MmcifCanonicalTopologyBond",
    "MmcifNonpolyCanonicalTopologyError",
    "MmcifNonpolyCanonicalTopologySnapshot",
    "mmcif_nonpoly_canonical_topology_document",
    "mmcif_nonpoly_canonical_topology_json_bytes",
    "mmcif_nonpoly_canonical_topology_projection",
    "mmcif_nonpoly_canonical_topology_source_binding",
    "parse_mmcif_nonpoly_canonical_topology",
    "require_mmcif_nonpoly_canonical_topology_document",
    "write_mmcif_nonpoly_canonical_topology_json",
]
