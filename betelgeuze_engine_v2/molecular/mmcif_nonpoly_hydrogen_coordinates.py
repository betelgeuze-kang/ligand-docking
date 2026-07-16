"""Deterministic coordinate-bearing hydrogen scaffold for bounded preparation.

This module composes the bounded neutral C/O/H preparation graph with selected
PDBx/mmCIF ``_atom_site.Cartn_x/y/z`` values.  Source-atom Cartesian coordinates
are preserved exactly as binary64 values.  Added hydrogens receive deterministic
coordinates from a fixed parent-centered 1.0 angstrom offset table.

The offset table is a source-level scaffold, not a calibrated geometry method.
It does not orient hydrogens from neighboring atoms, interpret stereochemistry,
select protonation or tautomers, assess clashes, minimize coordinates, establish
parameterability, or validate chemistry.  Unsupported preparation graphs retain
failure-complete instance reports without generated coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_nonpoly_coordinate_values import (
    MmcifNonpolyCoordinateValueObservation,
    parse_mmcif_nonpoly_coordinate_values,
)
from .mmcif_nonpoly_preparation import (
    MmcifNonpolyInstancePreparationReport,
    parse_mmcif_nonpoly_preparation,
)


MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_hydrogen_coordinate_projection/1.0.0"
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_hydrogen_coordinate_source_binding/1.0.0"
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_hydrogen_coordinate_document/1.0.0"
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID = (
    "bounded_mmcif_neutral_coh_fixed_parent_offset_hydrogen_coordinates/1.0.0"
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION = "1.0.0"

MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM = 1.0
_TETRAHEDRAL_COMPONENT = 0.5773502691896258
MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS = (
    (
        _TETRAHEDRAL_COMPONENT,
        _TETRAHEDRAL_COMPONENT,
        _TETRAHEDRAL_COMPONENT,
    ),
    (
        -_TETRAHEDRAL_COMPONENT,
        -_TETRAHEDRAL_COMPONENT,
        _TETRAHEDRAL_COMPONENT,
    ),
    (
        -_TETRAHEDRAL_COMPONENT,
        _TETRAHEDRAL_COMPONENT,
        -_TETRAHEDRAL_COMPONENT,
    ),
    (
        _TETRAHEDRAL_COMPONENT,
        -_TETRAHEDRAL_COMPONENT,
        -_TETRAHEDRAL_COMPONENT,
    ),
)
MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS = (
    "neighbor_geometry_not_interpreted",
    "stereochemistry_not_interpreted",
    "hydrogen_bond_length_not_calibrated",
    "steric_clash_not_assessed",
    "coordinate_minimization_not_performed",
)
MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS: Mapping[str, str] = (
    MappingProxyType(
        {
            "_atom_site.Cartn_x": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_atom_site.Cartn_x.html"
            ),
            "_atom_site.Cartn_y": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_atom_site.Cartn_y.html"
            ),
            "_atom_site.Cartn_z": (
                "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
                "Items/_atom_site.Cartn_z.html"
            ),
        }
    )
)

_GENERATED_STATUS = "coordinate_bearing_prepared_graph"
_UNAVAILABLE_STATUS = "not_generated_preparation_graph_unavailable"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyHydrogenCoordinateError(ValueError):
    """Stable fail-closed error without source identity or coordinate echo."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_hydrogen_coordinate:{self.code}: {self.detail}")


@dataclass(frozen=True, slots=True, repr=False)
class MmcifPreparedAtomCoordinate:
    atom_index: int
    atom_identity_sha256: str
    origin: str
    element: str
    parent_atom_index: int | None
    generation_method: str
    source_coordinate_value_identity_sha256: str
    x_angstrom: float
    y_angstrom: float
    z_angstrom: float
    x_binary64_bits_hex: str
    y_binary64_bits_hex: str
    z_binary64_bits_hex: str
    coordinate_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifPreparedAtomCoordinate("
            f"atom_index={self.atom_index}, origin={self.origin!r}, "
            f"generation_method={self.generation_method!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_index": self.atom_index,
            "atom_identity_sha256": self.atom_identity_sha256,
            "origin": self.origin,
            "element": self.element,
            "parent_atom_index": self.parent_atom_index,
            "generation_method": self.generation_method,
            "source_coordinate_value_identity_sha256": (
                self.source_coordinate_value_identity_sha256
            ),
            "coordinate_angstrom": [
                self.x_angstrom,
                self.y_angstrom,
                self.z_angstrom,
            ],
            "coordinate_binary64_bits_hex": [
                self.x_binary64_bits_hex,
                self.y_binary64_bits_hex,
                self.z_binary64_bits_hex,
            ],
            "coordinate_identity_sha256": self.coordinate_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifHydrogenCoordinateInstanceReport:
    instance_identity_sha256: str
    preparation_graph_sha256: str
    coordinate_status: str
    coordinate_blockers: tuple[str, ...]
    geometry_limitations: tuple[str, ...]
    atom_coordinates: tuple[MmcifPreparedAtomCoordinate, ...]
    added_hydrogen_coordinate_count: int
    coordinate_set_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifHydrogenCoordinateInstanceReport("
            f"coordinate_status={self.coordinate_status!r}, "
            f"atom_coordinate_count={len(self.atom_coordinates)}, "
            "added_hydrogen_coordinate_count="
            f"{self.added_hydrogen_coordinate_count})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "preparation_graph_sha256": self.preparation_graph_sha256,
            "coordinate_status": self.coordinate_status,
            "coordinate_blockers": list(self.coordinate_blockers),
            "geometry_limitations": list(self.geometry_limitations),
            "atom_coordinate_count": len(self.atom_coordinates),
            "added_hydrogen_coordinate_count": (
                self.added_hydrogen_coordinate_count
            ),
            "all_prepared_atoms_coordinate_bearing": bool(self.atom_coordinates),
            "atom_coordinates": [row.to_dict() for row in self.atom_coordinates],
            "coordinate_set_sha256": self.coordinate_set_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyHydrogenCoordinateSnapshot:
    source_sha256: str
    preparation_snapshot_sha256: str
    coordinate_value_snapshot_sha256: str
    coordinate_value_projection_sha256: str
    coordinate_value_source_binding_sha256: str
    instance_reports: tuple[MmcifHydrogenCoordinateInstanceReport, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyHydrogenCoordinateSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"generated_instance_count={self.generated_instance_count}, "
            "added_hydrogen_coordinate_count="
            f"{self.added_hydrogen_coordinate_count})"
        )

    @property
    def generated_instance_count(self) -> int:
        return sum(row.coordinate_status == _GENERATED_STATUS for row in self.instance_reports)

    @property
    def unavailable_instance_count(self) -> int:
        return len(self.instance_reports) - self.generated_instance_count

    @property
    def added_hydrogen_coordinate_count(self) -> int:
        return sum(row.added_hydrogen_coordinate_count for row in self.instance_reports)

    @property
    def all_prepared_graphs_coordinate_bearing(self) -> bool:
        return all(
            row.coordinate_status != _GENERATED_STATUS or bool(row.atom_coordinates)
            for row in self.instance_reports
        )

    @property
    def coordinate_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_hydrogen_coordinate_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_hydrogen_coordinate_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
                "coordinate_projection_sha256": self.coordinate_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
            "generator_version": MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION,
            "source_sha256": self.source_sha256,
            "preparation_snapshot_sha256": self.preparation_snapshot_sha256,
            "coordinate_value_snapshot_sha256": self.coordinate_value_snapshot_sha256,
            "instance_count": len(self.instance_reports),
            "generated_instance_count": self.generated_instance_count,
            "unavailable_instance_count": self.unavailable_instance_count,
            "added_hydrogen_coordinate_count": (
                self.added_hydrogen_coordinate_count
            ),
            "all_prepared_graphs_coordinate_bearing": (
                self.all_prepared_graphs_coordinate_bearing
            ),
            "coordinate_projection_sha256": self.coordinate_projection_sha256,
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
        "prepared_graph_bound": True,
        "source_cartesian_coordinates_bound": True,
        "source_cartesian_angstrom_unit_interpreted": True,
        "source_atom_coordinates_preserved": True,
        "added_hydrogen_coordinates_generated": True,
        "fixed_parent_offset_geometry_applied": True,
        "failure_complete_instance_reports": True,
        "source_authenticated": False,
        "neighbor_geometry_interpreted": False,
        "stereochemistry_interpreted": False,
        "protonation_state_interpreted": False,
        "tautomer_selected": False,
        "hydrogen_bond_length_calibrated": False,
        "steric_clash_assessed": False,
        "coordinate_geometry_validated": False,
        "coordinate_minimized": False,
        "partial_charge_assigned": False,
        "reviewed_parameter_source_bound": False,
        "all_atom_system_created": False,
        "chemistry_validated": False,
        "parameterable": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _bits(value: float) -> str:
    if type(value) is not float or not math.isfinite(value):
        raise MmcifNonpolyHydrogenCoordinateError(
            "nonfinite_generated_coordinate",
            "hydrogen-coordinate output must contain finite binary64 values",
        )
    return struct.pack(">d", value).hex()


def _coordinate_payload(
    *,
    atom_index: int,
    atom_identity_sha256: str,
    origin: str,
    element: str,
    parent_atom_index: int | None,
    generation_method: str,
    source_coordinate_value_identity_sha256: str,
    coordinate: tuple[float, float, float],
) -> dict[str, Any]:
    bits = tuple(_bits(value) for value in coordinate)
    return {
        "atom_index": atom_index,
        "atom_identity_sha256": atom_identity_sha256,
        "origin": origin,
        "element": element,
        "parent_atom_index": parent_atom_index,
        "generation_method": generation_method,
        "source_coordinate_value_identity_sha256": (
            source_coordinate_value_identity_sha256
        ),
        "coordinate_angstrom": list(coordinate),
        "coordinate_binary64_bits_hex": list(bits),
    }


def _prepared_coordinate(
    *,
    atom_index: int,
    atom_identity_sha256: str,
    origin: str,
    element: str,
    parent_atom_index: int | None,
    generation_method: str,
    source_coordinate_value_identity_sha256: str,
    coordinate: tuple[float, float, float],
) -> MmcifPreparedAtomCoordinate:
    payload = _coordinate_payload(
        atom_index=atom_index,
        atom_identity_sha256=atom_identity_sha256,
        origin=origin,
        element=element,
        parent_atom_index=parent_atom_index,
        generation_method=generation_method,
        source_coordinate_value_identity_sha256=(
            source_coordinate_value_identity_sha256
        ),
        coordinate=coordinate,
    )
    bits = payload["coordinate_binary64_bits_hex"]
    return MmcifPreparedAtomCoordinate(
        atom_index=atom_index,
        atom_identity_sha256=atom_identity_sha256,
        origin=origin,
        element=element,
        parent_atom_index=parent_atom_index,
        generation_method=generation_method,
        source_coordinate_value_identity_sha256=(
            source_coordinate_value_identity_sha256
        ),
        x_angstrom=coordinate[0],
        y_angstrom=coordinate[1],
        z_angstrom=coordinate[2],
        x_binary64_bits_hex=bits[0],
        y_binary64_bits_hex=bits[1],
        z_binary64_bits_hex=bits[2],
        coordinate_identity_sha256=_sha256(payload),
    )


def _source_coordinate(
    row: MmcifNonpolyCoordinateValueObservation,
) -> tuple[float, float, float]:
    return (
        row.cartn_x.numeric_value,
        row.cartn_y.numeric_value,
        row.cartn_z.numeric_value,
    )


def _coordinate_set_sha256(
    *,
    instance_identity_sha256: str,
    preparation_graph_sha256: str,
    atom_coordinates: tuple[MmcifPreparedAtomCoordinate, ...],
) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_hydrogen_coordinate_set/1.0.0",
            "instance_identity_sha256": instance_identity_sha256,
            "preparation_graph_sha256": preparation_graph_sha256,
            "atom_coordinates": [row.to_dict() for row in atom_coordinates],
            "geometry_limitations": list(
                MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS
            ),
        }
    )


def _instance_report(
    preparation: MmcifNonpolyInstancePreparationReport,
    coordinates_by_source_atom_id: Mapping[int, MmcifNonpolyCoordinateValueObservation],
) -> MmcifHydrogenCoordinateInstanceReport:
    if preparation.preparation_status != "prepared_component_graph":
        blockers = preparation.chemistry_blockers or ("preparation_graph_unavailable",)
        return MmcifHydrogenCoordinateInstanceReport(
            instance_identity_sha256=preparation.instance_identity_sha256,
            preparation_graph_sha256="",
            coordinate_status=_UNAVAILABLE_STATUS,
            coordinate_blockers=tuple(blockers),
            geometry_limitations=(),
            atom_coordinates=(),
            added_hydrogen_coordinate_count=0,
            coordinate_set_sha256="",
        )

    atom_coordinates: list[MmcifPreparedAtomCoordinate] = []
    hydrogen_ordinal_by_parent: dict[int, int] = {}
    for atom in preparation.atoms:
        if atom.index != len(atom_coordinates):
            raise MmcifNonpolyHydrogenCoordinateError(
                "prepared_atom_order_mismatch",
                "prepared graph atom indices must be contiguous source order",
            )
        if atom.origin == "source_atom":
            if atom.source_atom_id is None:
                raise MmcifNonpolyHydrogenCoordinateError(
                    "source_coordinate_identity_missing",
                    "source graph atoms must retain a source coordinate identity",
                )
            source = coordinates_by_source_atom_id.get(atom.source_atom_id)
            if source is None:
                raise MmcifNonpolyHydrogenCoordinateError(
                    "source_coordinate_missing",
                    "every source graph atom must retain one selected coordinate",
                )
            prepared = _prepared_coordinate(
                atom_index=atom.index,
                atom_identity_sha256=atom.atom_identity_sha256,
                origin=atom.origin,
                element=atom.element,
                parent_atom_index=None,
                generation_method="source_atom_site_coordinate",
                source_coordinate_value_identity_sha256=(
                    source.coordinate_value_identity_sha256
                ),
                coordinate=_source_coordinate(source),
            )
        elif atom.origin == "added_hydrogen":
            parent = atom.parent_atom_index
            if parent is None or parent < 0 or parent >= len(atom_coordinates):
                raise MmcifNonpolyHydrogenCoordinateError(
                    "hydrogen_parent_coordinate_missing",
                    "added hydrogens require an earlier parent coordinate",
                )
            ordinal = hydrogen_ordinal_by_parent.get(parent, 0)
            if ordinal >= len(MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS):
                raise MmcifNonpolyHydrogenCoordinateError(
                    "hydrogen_offset_capacity_exceeded",
                    "added hydrogens exceed the fixed parent offset table",
                )
            hydrogen_ordinal_by_parent[parent] = ordinal + 1
            parent_coordinate = atom_coordinates[parent]
            direction = MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS[ordinal]
            coordinate = (
                parent_coordinate.x_angstrom
                + MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM * direction[0],
                parent_coordinate.y_angstrom
                + MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM * direction[1],
                parent_coordinate.z_angstrom
                + MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM * direction[2],
            )
            prepared = _prepared_coordinate(
                atom_index=atom.index,
                atom_identity_sha256=atom.atom_identity_sha256,
                origin=atom.origin,
                element=atom.element,
                parent_atom_index=parent,
                generation_method="fixed_parent_offset_table_v1",
                source_coordinate_value_identity_sha256="",
                coordinate=coordinate,
            )
        else:
            raise MmcifNonpolyHydrogenCoordinateError(
                "unsupported_prepared_atom_origin",
                "prepared atom origin is outside the coordinate scaffold",
            )
        atom_coordinates.append(prepared)
    frozen = tuple(atom_coordinates)
    added_count = sum(row.origin == "added_hydrogen" for row in frozen)
    return MmcifHydrogenCoordinateInstanceReport(
        instance_identity_sha256=preparation.instance_identity_sha256,
        preparation_graph_sha256=preparation.preparation_graph_sha256,
        coordinate_status=_GENERATED_STATUS,
        coordinate_blockers=(),
        geometry_limitations=MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS,
        atom_coordinates=frozen,
        added_hydrogen_coordinate_count=added_count,
        coordinate_set_sha256=_coordinate_set_sha256(
            instance_identity_sha256=preparation.instance_identity_sha256,
            preparation_graph_sha256=preparation.preparation_graph_sha256,
            atom_coordinates=frozen,
        ),
    )


def parse_mmcif_nonpoly_hydrogen_coordinates(
    text: str,
) -> MmcifNonpolyHydrogenCoordinateSnapshot:
    """Create deterministic coordinates for every bounded prepared-graph atom."""

    if type(text) is not str:
        raise TypeError("mmCIF hydrogen-coordinate input must be a string")
    preparation = parse_mmcif_nonpoly_preparation(text)
    coordinate_values = parse_mmcif_nonpoly_coordinate_values(text)
    if preparation.source_sha256 != coordinate_values.source_sha256:
        raise MmcifNonpolyHydrogenCoordinateError(
            "source_carrier_crosswire",
            "preparation and coordinate carriers must bind the same source",
        )
    coordinates_by_source_atom_id = {
        row.source_atom_id: row for row in coordinate_values.coordinates
    }
    if len(coordinates_by_source_atom_id) != len(coordinate_values.coordinates):
        raise MmcifNonpolyHydrogenCoordinateError(
            "source_coordinate_identity_duplicate",
            "selected source coordinate identities must be unique",
        )
    reports = tuple(
        _instance_report(row, coordinates_by_source_atom_id)
        for row in preparation.instance_reports
    )
    return MmcifNonpolyHydrogenCoordinateSnapshot(
        source_sha256=preparation.source_sha256,
        preparation_snapshot_sha256=preparation.snapshot_sha256,
        coordinate_value_snapshot_sha256=coordinate_values.snapshot_sha256,
        coordinate_value_projection_sha256=(
            coordinate_values.coordinate_projection_sha256
        ),
        coordinate_value_source_binding_sha256=(
            coordinate_values.source_binding_sha256
        ),
        instance_reports=reports,
    )


def mmcif_nonpoly_hydrogen_coordinate_projection(
    snapshot: MmcifNonpolyHydrogenCoordinateSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
        "generator_version": MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION,
        "preparation_snapshot_sha256": snapshot.preparation_snapshot_sha256,
        "coordinate_value_projection_sha256": (
            snapshot.coordinate_value_projection_sha256
        ),
        "instance_reports": [row.to_dict() for row in snapshot.instance_reports],
        "instance_order": "preparation_instance_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_hydrogen_coordinate_source_binding(
    snapshot: MmcifNonpolyHydrogenCoordinateSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "preparation_snapshot_sha256": snapshot.preparation_snapshot_sha256,
        "coordinate_value_snapshot_sha256": (
            snapshot.coordinate_value_snapshot_sha256
        ),
        "coordinate_value_source_binding_sha256": (
            snapshot.coordinate_value_source_binding_sha256
        ),
        "dictionary_items": dict(
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS
        ),
        "coordinate_unit": "angstrom",
        "bond_length_angstrom": MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM,
        "offset_directions": [
            list(row) for row in MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS
        ],
        "geometry_limitations": list(
            MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS
        ),
    }


def mmcif_nonpoly_hydrogen_coordinate_document(
    snapshot: MmcifNonpolyHydrogenCoordinateSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_hydrogen_coordinate_projection(snapshot)
    binding = mmcif_nonpoly_hydrogen_coordinate_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
        "generator_version": MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION,
        "coordinate_projection": projection,
        "source_binding": binding,
        "coordinate_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"hydrogen-coordinate {label} digest invalid")
    return candidate


def _require_coordinate(row: Mapping[str, Any], expected_index: int) -> dict[str, Any]:
    candidate = dict(row)
    coordinate = candidate.get("coordinate_angstrom")
    bits = candidate.get("coordinate_binary64_bits_hex")
    origin = candidate.get("origin")
    element = candidate.get("element")
    parent = candidate.get("parent_atom_index")
    source_identity = candidate.get("source_coordinate_value_identity_sha256")
    if (
        candidate.get("atom_index") != expected_index
        or not isinstance(coordinate, list)
        or len(coordinate) != 3
        or not all(type(value) is float and math.isfinite(value) for value in coordinate)
        or not isinstance(bits, list)
        or bits != [_bits(value) for value in coordinate]
        or origin not in {"source_atom", "added_hydrogen"}
        or element not in {"C", "O", "H"}
    ):
        raise ValueError("hydrogen-coordinate atom coordinate invalid")
    _require_digest(candidate.get("atom_identity_sha256"), "atom identity")
    if origin == "source_atom":
        if (
            parent is not None
            or candidate.get("generation_method") != "source_atom_site_coordinate"
        ):
            raise ValueError("hydrogen-coordinate source atom metadata invalid")
        _require_digest(source_identity, "source coordinate identity")
    else:
        if (
            element != "H"
            or
            type(parent) is not int
            or parent < 0
            or parent >= expected_index
            or candidate.get("generation_method")
            != "fixed_parent_offset_table_v1"
            or source_identity != ""
        ):
            raise ValueError("hydrogen-coordinate added atom metadata invalid")
    identity_payload = {
        key: candidate[key]
        for key in (
            "atom_index",
            "atom_identity_sha256",
            "origin",
            "element",
            "parent_atom_index",
            "generation_method",
            "source_coordinate_value_identity_sha256",
            "coordinate_angstrom",
            "coordinate_binary64_bits_hex",
        )
    }
    if candidate.get("coordinate_identity_sha256") != _sha256(identity_payload):
        raise ValueError("hydrogen-coordinate atom identity mismatch")
    return candidate


def require_mmcif_nonpoly_hydrogen_coordinate_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("hydrogen-coordinate document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID:
        raise ValueError("hydrogen-coordinate document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID:
        raise ValueError("hydrogen-coordinate profile mismatch")
    if (
        document.get("generator_version")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION
    ):
        raise ValueError("hydrogen-coordinate generator version mismatch")
    projection = document.get("coordinate_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("hydrogen-coordinate sections must be mappings")
    if (
        projection.get("schema_id")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROJECTION_SCHEMA_ID
        or projection.get("profile_id")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID
        or projection.get("generator_version")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION
        or projection.get("instance_order") != "preparation_instance_order"
    ):
        raise ValueError("hydrogen-coordinate projection mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("hydrogen-coordinate source binding mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("coordinate_projection_sha256") != projection_digest:
        raise ValueError("hydrogen-coordinate projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("hydrogen-coordinate source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
            "coordinate_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("hydrogen-coordinate snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("hydrogen-coordinate claim boundary mismatch")

    reports = projection.get("instance_reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("hydrogen-coordinate reports must be a non-empty list")
    generated_count = 0
    unavailable_count = 0
    added_total = 0
    instances: set[str] = set()
    for item in reports:
        if not isinstance(item, Mapping):
            raise ValueError("hydrogen-coordinate instance report invalid")
        report = dict(item)
        instance = _require_digest(
            report.get("instance_identity_sha256"), "instance identity"
        )
        if instance in instances:
            raise ValueError("hydrogen-coordinate instance reports must be unique")
        instances.add(instance)
        status = report.get("coordinate_status")
        coordinates = report.get("atom_coordinates")
        blockers = report.get("coordinate_blockers")
        limitations = report.get("geometry_limitations")
        if (
            status not in {_GENERATED_STATUS, _UNAVAILABLE_STATUS}
            or not isinstance(coordinates, list)
            or not isinstance(blockers, list)
            or not isinstance(limitations, list)
        ):
            raise ValueError("hydrogen-coordinate instance summary invalid")
        parsed = [
            _require_coordinate(row, index)
            for index, row in enumerate(coordinates)
            if isinstance(row, Mapping)
        ]
        if len(parsed) != len(coordinates):
            raise ValueError("hydrogen-coordinate atom rows invalid")
        added_count = sum(row["origin"] == "added_hydrogen" for row in parsed)
        if (
            report.get("atom_coordinate_count") != len(parsed)
            or report.get("added_hydrogen_coordinate_count") != added_count
        ):
            raise ValueError("hydrogen-coordinate instance counts mismatch")
        if status == _GENERATED_STATUS:
            generated_count += 1
            if (
                not parsed
                or blockers
                or limitations
                != list(MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS)
                or report.get("all_prepared_atoms_coordinate_bearing") is not True
            ):
                raise ValueError("hydrogen-coordinate generated report invalid")
            graph_sha = _require_digest(
                report.get("preparation_graph_sha256"), "preparation graph"
            )
            parent_ordinals: dict[int, int] = {}
            for row in parsed:
                if row["origin"] != "added_hydrogen":
                    continue
                parent = row["parent_atom_index"]
                ordinal = parent_ordinals.get(parent, 0)
                if ordinal >= len(MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS):
                    raise ValueError("hydrogen-coordinate offset capacity mismatch")
                parent_ordinals[parent] = ordinal + 1
                parent_coordinate = parsed[parent]["coordinate_angstrom"]
                direction = MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS[ordinal]
                expected_coordinate = [
                    parent_coordinate[index]
                    + MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM
                    * direction[index]
                    for index in range(3)
                ]
                if row["coordinate_angstrom"] != expected_coordinate:
                    raise ValueError("hydrogen-coordinate fixed offset mismatch")
            expected_set_sha = _sha256(
                {
                    "schema_id": (
                        "betelgeuze.engine_v2_hydrogen_coordinate_set/1.0.0"
                    ),
                    "instance_identity_sha256": instance,
                    "preparation_graph_sha256": graph_sha,
                    "atom_coordinates": coordinates,
                    "geometry_limitations": limitations,
                }
            )
            if report.get("coordinate_set_sha256") != expected_set_sha:
                raise ValueError("hydrogen-coordinate set digest mismatch")
        else:
            unavailable_count += 1
            if (
                parsed
                or not blockers
                or limitations
                or report.get("preparation_graph_sha256") != ""
                or report.get("coordinate_set_sha256") != ""
                or report.get("all_prepared_atoms_coordinate_bearing") is not False
            ):
                raise ValueError("hydrogen-coordinate unavailable report invalid")
        added_total += added_count

    if (
        document.get("instance_count") != len(reports)
        or document.get("generated_instance_count") != generated_count
        or document.get("unavailable_instance_count") != unavailable_count
        or document.get("added_hydrogen_coordinate_count") != added_total
        or document.get("all_prepared_graphs_coordinate_bearing") is not True
    ):
        raise ValueError("hydrogen-coordinate document summary mismatch")
    source_sha = _require_digest(binding.get("source_sha256"), "source")
    preparation_sha = _require_digest(
        binding.get("preparation_snapshot_sha256"), "preparation snapshot"
    )
    coordinate_value_sha = _require_digest(
        binding.get("coordinate_value_snapshot_sha256"), "coordinate value snapshot"
    )
    _require_digest(
        binding.get("coordinate_value_source_binding_sha256"),
        "coordinate value source binding",
    )
    _require_digest(
        projection.get("coordinate_value_projection_sha256"),
        "coordinate value projection",
    )
    if (
        document.get("source_sha256") != source_sha
        or document.get("preparation_snapshot_sha256") != preparation_sha
        or projection.get("preparation_snapshot_sha256") != preparation_sha
        or document.get("coordinate_value_snapshot_sha256")
        != coordinate_value_sha
        or binding.get("dictionary_items")
        != MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS
        or binding.get("coordinate_unit") != "angstrom"
        or binding.get("bond_length_angstrom")
        != MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM
        or binding.get("offset_directions")
        != [list(row) for row in MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS]
        or binding.get("geometry_limitations")
        != list(MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS)
    ):
        raise ValueError("hydrogen-coordinate source binding mismatch")
    return payload


def mmcif_nonpoly_hydrogen_coordinate_json_bytes(
    snapshot: MmcifNonpolyHydrogenCoordinateSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_hydrogen_coordinate_document(snapshot))


def write_mmcif_nonpoly_hydrogen_coordinate_json(
    path: str | Path,
    snapshot: MmcifNonpolyHydrogenCoordinateSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_hydrogen_coordinate_json_bytes(snapshot) + b"\n"
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
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
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
    "MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM",
    "MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS",
    "MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_HYDROGEN_COORDINATE_SOURCE_BINDING_SCHEMA_ID",
    "MmcifHydrogenCoordinateInstanceReport",
    "MmcifNonpolyHydrogenCoordinateError",
    "MmcifNonpolyHydrogenCoordinateSnapshot",
    "MmcifPreparedAtomCoordinate",
    "mmcif_nonpoly_hydrogen_coordinate_document",
    "mmcif_nonpoly_hydrogen_coordinate_json_bytes",
    "mmcif_nonpoly_hydrogen_coordinate_projection",
    "mmcif_nonpoly_hydrogen_coordinate_source_binding",
    "parse_mmcif_nonpoly_hydrogen_coordinates",
    "require_mmcif_nonpoly_hydrogen_coordinate_document",
    "write_mmcif_nonpoly_hydrogen_coordinate_json",
]
