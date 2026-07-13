"""Canonical, versioned all-atom molecular data model.

Topology records use stable zero-based indices.  Coordinates are kept in one
floating ``torch.Tensor`` with shape ``[M, N, 3]`` (models, atoms, xyz) so the
same topology can carry an ensemble without duplicating atom metadata.  A
topology-only system uses the unambiguous empty shape ``[0, N, 3]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from types import MappingProxyType
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID


_ELEMENT_SYMBOLS = (
    "",
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
)
_ATOMIC_NUMBER_BY_SYMBOL = {symbol: number for number, symbol in enumerate(_ELEMENT_SYMBOLS) if symbol}
_SUPPORTED_CANONICAL_FLOAT_DTYPES = frozenset({torch.float32, torch.float64})
_MAX_CANONICAL_METADATA_DEPTH = 64
_MAX_CANONICAL_METADATA_NODES = 1_000_000
_MAX_CANONICAL_JSON_INTEGER = (1 << 53) - 1
_MAX_ABS_CANONICAL_FORMAL_CHARGE = (1 << 15) - 1


class _FrozenMetadataList(tuple):
    """Read-only JSON-array value that retains equality with ordinary lists."""

    __hash__ = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple)):
            return tuple.__eq__(self, tuple(other))
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal


def _freeze_metadata_value(
    value: Any,
    *,
    field_name: str,
    depth: int,
    active_container_ids: set[int],
    node_count: list[int],
) -> Any:
    node_count[0] += 1
    if node_count[0] > _MAX_CANONICAL_METADATA_NODES:
        raise ValueError(
            f"{field_name} exceeds the {_MAX_CANONICAL_METADATA_NODES}-node safety limit"
        )
    if depth > _MAX_CANONICAL_METADATA_DEPTH:
        raise ValueError(
            f"{field_name} exceeds the {_MAX_CANONICAL_METADATA_DEPTH}-level depth limit"
        )
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return _strict_int(value, field_name=field_name)
    if type(value) is str:
        return _strict_string(value, field_name=field_name)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} floats must be finite")
        return value
    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValueError(f"{field_name} must not contain a reference cycle")
        active_container_ids.add(container_id)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError(f"{field_name} keys must be strings")
                normalized_key = _strict_string(
                    key,
                    field_name=f"{field_name} key",
                )
                frozen[normalized_key] = _freeze_metadata_value(
                    item,
                    field_name=f"{field_name}.{normalized_key}",
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    node_count=node_count,
                )
            return MappingProxyType(frozen)
        finally:
            active_container_ids.remove(container_id)
    if type(value) is list or isinstance(value, _FrozenMetadataList):
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValueError(f"{field_name} must not contain a reference cycle")
        active_container_ids.add(container_id)
        try:
            return _FrozenMetadataList(
                _freeze_metadata_value(
                    item,
                    field_name=f"{field_name}[{index}]",
                    depth=depth + 1,
                    active_container_ids=active_container_ids,
                    node_count=node_count,
                )
                for index, item in enumerate(value)
            )
        finally:
            active_container_ids.remove(container_id)
    raise TypeError(
        f"{field_name} supports only JSON null, boolean, integer, finite float, string, list, and mapping values"
    )


def _freeze_metadata_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    frozen = _freeze_metadata_value(
        value,
        field_name=field_name,
        depth=0,
        active_container_ids=set(),
        node_count=[0],
    )
    if not isinstance(frozen, Mapping):  # pragma: no cover - root contract above
        raise TypeError(f"{field_name} must be a mapping")
    return frozen


def _strict_int(value: Any, *, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if abs(value) > _MAX_CANONICAL_JSON_INTEGER:
        raise ValueError(
            f"{field_name} must be within the interoperable JSON integer range"
        )
    return value


def _strict_float(value: Any, *, field_name: str) -> float:
    if type(value) is not float:
        raise TypeError(f"{field_name} must be a float")
    return value


def _strict_optional_float(value: Any, *, field_name: str) -> float | None:
    if value is None:
        return None
    return _strict_float(value, field_name=field_name)


def _strict_optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _strict_int(value, field_name=field_name)


def _strict_bool(value: Any, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _strict_string(value: Any, *, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{field_name} must contain only Unicode scalar values")
    return value


def _strict_int_tuple(values: Any, *, field_name: str) -> tuple[int, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{field_name} must be a tuple of integers")
    return tuple(
        _strict_int(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(values)
    )


def _strict_string_tuple(values: Any, *, field_name: str) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{field_name} must be a tuple of strings")
    return tuple(
        _strict_string(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(values)
    )


def canonical_element_symbol(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[0].upper() + text[1:].lower()


def atomic_number_for_element(element: str) -> int:
    return int(_ATOMIC_NUMBER_BY_SYMBOL.get(canonical_element_symbol(element), 0))


def element_for_atomic_number(atomic_number: int) -> str:
    number = _strict_int(atomic_number, field_name="atomic_number")
    if number < 1 or number >= len(_ELEMENT_SYMBOLS):
        raise ValueError(f"atomic_number must be in [1, 118], got {number}")
    return _ELEMENT_SYMBOLS[number]


@dataclass(frozen=True)
class Atom:
    """One explicit atom, including hydrogens when they exist in the source."""

    index: int
    name: str
    element: str
    atomic_number: int
    residue_index: int
    formal_charge: int = 0
    formal_charge_known: bool = True
    partial_charge_e: float | None = None
    mass_da: float | None = None
    isotope_mass_number: int | None = None
    serial: int | None = None
    atom_map: int | None = None
    altloc: str = ""
    occupancy: float | None = None
    b_factor: float | None = None
    aromatic: bool = False
    stereo: str = "unspecified"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _strict_int(self.index, field_name="atom.index"))
        object.__setattr__(self, "atomic_number", _strict_int(self.atomic_number, field_name="atom.atomic_number"))
        object.__setattr__(self, "residue_index", _strict_int(self.residue_index, field_name="atom.residue_index"))
        formal_charge = _strict_int(
            self.formal_charge,
            field_name="atom.formal_charge",
        )
        if abs(formal_charge) > _MAX_ABS_CANONICAL_FORMAL_CHARGE:
            raise ValueError(
                "atom.formal_charge exceeds the canonical magnitude limit"
            )
        object.__setattr__(self, "formal_charge", formal_charge)
        object.__setattr__(
            self,
            "formal_charge_known",
            _strict_bool(self.formal_charge_known, field_name="atom.formal_charge_known"),
        )
        object.__setattr__(
            self,
            "partial_charge_e",
            _strict_optional_float(self.partial_charge_e, field_name="atom.partial_charge_e"),
        )
        object.__setattr__(self, "mass_da", _strict_optional_float(self.mass_da, field_name="atom.mass_da"))
        object.__setattr__(
            self,
            "isotope_mass_number",
            _strict_optional_int(self.isotope_mass_number, field_name="atom.isotope_mass_number"),
        )
        object.__setattr__(self, "serial", _strict_optional_int(self.serial, field_name="atom.serial"))
        object.__setattr__(self, "atom_map", _strict_optional_int(self.atom_map, field_name="atom.atom_map"))
        object.__setattr__(self, "occupancy", _strict_optional_float(self.occupancy, field_name="atom.occupancy"))
        object.__setattr__(self, "b_factor", _strict_optional_float(self.b_factor, field_name="atom.b_factor"))
        object.__setattr__(self, "aromatic", _strict_bool(self.aromatic, field_name="atom.aromatic"))
        object.__setattr__(self, "name", _strict_string(self.name, field_name="atom.name").strip())
        object.__setattr__(self, "element", canonical_element_symbol(_strict_string(self.element, field_name="atom.element")))
        object.__setattr__(self, "altloc", _strict_string(self.altloc, field_name="atom.altloc").strip())
        object.__setattr__(self, "stereo", _strict_string(self.stereo, field_name="atom.stereo"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(self.metadata, field_name="atom.metadata"),
        )


@dataclass(frozen=True)
class Bond:
    """Canonical bond record; endpoints must be ordered ``atom_i < atom_j``."""

    index: int
    atom_i: int
    atom_j: int
    order: float = 1.0
    aromatic: bool = False
    stereo: str = "none"
    source: str = "input"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _strict_int(self.index, field_name="bond.index"))
        object.__setattr__(self, "atom_i", _strict_int(self.atom_i, field_name="bond.atom_i"))
        object.__setattr__(self, "atom_j", _strict_int(self.atom_j, field_name="bond.atom_j"))
        object.__setattr__(self, "order", _strict_float(self.order, field_name="bond.order"))
        object.__setattr__(self, "aromatic", _strict_bool(self.aromatic, field_name="bond.aromatic"))
        object.__setattr__(self, "stereo", _strict_string(self.stereo, field_name="bond.stereo"))
        object.__setattr__(self, "source", _strict_string(self.source, field_name="bond.source"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(self.metadata, field_name="bond.metadata"),
        )


@dataclass(frozen=True)
class Residue:
    index: int
    name: str
    chain_index: int
    sequence_number: int
    atom_indices: tuple[int, ...]
    insertion_code: str = ""
    entity_type: str = "polymer"
    hetero: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _strict_int(self.index, field_name="residue.index"))
        object.__setattr__(self, "chain_index", _strict_int(self.chain_index, field_name="residue.chain_index"))
        object.__setattr__(self, "sequence_number", _strict_int(self.sequence_number, field_name="residue.sequence_number"))
        object.__setattr__(self, "name", _strict_string(self.name, field_name="residue.name").strip().upper())
        object.__setattr__(self, "atom_indices", _strict_int_tuple(self.atom_indices, field_name="residue.atom_indices"))
        object.__setattr__(
            self,
            "insertion_code",
            _strict_string(self.insertion_code, field_name="residue.insertion_code").strip(),
        )
        object.__setattr__(self, "entity_type", _strict_string(self.entity_type, field_name="residue.entity_type"))
        object.__setattr__(self, "hetero", _strict_bool(self.hetero, field_name="residue.hetero"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(self.metadata, field_name="residue.metadata"),
        )


@dataclass(frozen=True)
class Chain:
    index: int
    chain_id: str
    residue_indices: tuple[int, ...]
    entity_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _strict_int(self.index, field_name="chain.index"))
        object.__setattr__(self, "chain_id", _strict_string(self.chain_id, field_name="chain.chain_id"))
        object.__setattr__(self, "residue_indices", _strict_int_tuple(self.residue_indices, field_name="chain.residue_indices"))
        object.__setattr__(self, "entity_id", _strict_string(self.entity_id, field_name="chain.entity_id"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(self.metadata, field_name="chain.metadata"),
        )


@dataclass(frozen=True)
class UnitCell:
    """Lattice vectors in Angstrom, stored as three row vectors."""

    vectors: torch.Tensor
    periodic: tuple[bool, bool, bool] = (True, True, True)

    def __post_init__(self) -> None:
        if type(self.vectors) is not torch.Tensor:
            raise TypeError("unit-cell vectors must be an exact torch.Tensor")
        if self.vectors.layout is not torch.strided:
            raise TypeError("unit-cell vectors must use strided tensor layout")
        if self.vectors.device.type == "meta":
            raise ValueError("unit-cell vectors must be materialized")
        if self.vectors.shape != (3, 3):
            raise ValueError("unit-cell vectors must have shape [3, 3]")
        if self.vectors.dtype not in _SUPPORTED_CANONICAL_FLOAT_DTYPES:
            raise TypeError("unit-cell vectors must use float32 or float64 dtype")
        if len(self.periodic) != 3:
            raise ValueError("unit-cell periodic flags must have length 3")
        if not all(type(value) is bool for value in self.periodic):
            raise TypeError("unit-cell periodic flags must be booleans")
        object.__setattr__(self, "periodic", tuple(self.periodic))

    @classmethod
    def orthorhombic(
        cls,
        lengths_angstrom: torch.Tensor | tuple[float, float, float] | list[float],
        *,
        dtype: torch.dtype = torch.float32,
        device: torch.device | str | None = None,
        periodic: tuple[bool, bool, bool] = (True, True, True),
    ) -> "UnitCell":
        lengths = torch.as_tensor(lengths_angstrom, dtype=dtype, device=device)
        if lengths.shape != (3,):
            raise ValueError("orthorhombic cell lengths must have shape [3]")
        return cls(vectors=torch.diag(lengths), periodic=periodic)

    @property
    def volume_angstrom3(self) -> torch.Tensor:
        return torch.linalg.det(self.vectors)

    def orthorhombic_lengths(self, *, atol: float = 1.0e-7) -> torch.Tensor:
        diagonal = torch.diag(torch.diagonal(self.vectors))
        if not bool(torch.allclose(self.vectors, diagonal, atol=atol, rtol=0.0)):
            raise ValueError("operation requires an orthorhombic unit cell")
        return torch.diagonal(self.vectors)


@dataclass(frozen=True)
class StructureProvenance:
    """Origin and transformation ledger for a canonical molecular system."""

    source_format: str
    source_id: str = ""
    source_sha256: str = ""
    parser_name: str = ""
    parser_version: str = ""
    operations: tuple[str, ...] = ()
    parent_sha256: tuple[str, ...] = ()
    preparation_ready: bool = False
    claim_safe: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_format", _strict_string(self.source_format, field_name="provenance.source_format").lower())
        object.__setattr__(self, "source_id", _strict_string(self.source_id, field_name="provenance.source_id"))
        object.__setattr__(self, "source_sha256", _strict_string(self.source_sha256, field_name="provenance.source_sha256").lower())
        object.__setattr__(self, "parser_name", _strict_string(self.parser_name, field_name="provenance.parser_name"))
        object.__setattr__(self, "parser_version", _strict_string(self.parser_version, field_name="provenance.parser_version"))
        object.__setattr__(self, "operations", _strict_string_tuple(self.operations, field_name="provenance.operations"))
        object.__setattr__(
            self,
            "parent_sha256",
            tuple(value.lower() for value in _strict_string_tuple(self.parent_sha256, field_name="provenance.parent_sha256")),
        )
        object.__setattr__(
            self,
            "preparation_ready",
            _strict_bool(self.preparation_ready, field_name="provenance.preparation_ready"),
        )
        object.__setattr__(self, "claim_safe", _strict_bool(self.claim_safe, field_name="provenance.claim_safe"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(
                self.metadata,
                field_name="provenance.metadata",
            ),
        )


@dataclass(frozen=True)
class AllAtomSystem:
    """Canonical topology plus zero or more all-atom coordinate models.

    Coordinates are absent only when represented by a floating tensor with
    shape ``[0, atom_count, 3]``.  This topology-only state is serializable and
    valid, but molecular preparation gates reject it before numeric execution.
    """

    system_id: str
    atoms: tuple[Atom, ...]
    bonds: tuple[Bond, ...]
    residues: tuple[Residue, ...]
    chains: tuple[Chain, ...]
    coordinates: torch.Tensor
    provenance: StructureProvenance
    cell: UnitCell | None = None
    coordinate_unit: str = "angstrom"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)
    schema_id: str = ALL_ATOM_SCHEMA_ID

    def __post_init__(self) -> None:
        if type(self.coordinates) is not torch.Tensor:
            raise TypeError("coordinates must be an exact torch.Tensor")
        if self.coordinates.layout is not torch.strided:
            raise TypeError("coordinates must use strided tensor layout")
        if self.coordinates.device.type == "meta":
            raise ValueError("coordinates must be materialized")
        if self.coordinates.ndim != 3 or self.coordinates.shape[-1] != 3:
            raise ValueError("coordinates must have shape [M, N, 3]")
        if self.coordinates.dtype not in _SUPPORTED_CANONICAL_FLOAT_DTYPES:
            raise TypeError("coordinates must use float32 or float64 dtype")
        record_contracts = (
            ("atoms", self.atoms, Atom),
            ("bonds", self.bonds, Bond),
            ("residues", self.residues, Residue),
            ("chains", self.chains, Chain),
        )
        for field_name, records, expected_type in record_contracts:
            if not isinstance(records, tuple) or not all(
                isinstance(record, expected_type) for record in records
            ):
                raise TypeError(
                    f"{field_name} must be a tuple of {expected_type.__name__} records"
                )
        if not isinstance(self.provenance, StructureProvenance):
            raise TypeError("provenance must be a StructureProvenance")
        if self.cell is not None and not isinstance(self.cell, UnitCell):
            raise TypeError("cell must be a UnitCell or None")
        object.__setattr__(self, "system_id", _strict_string(self.system_id, field_name="system_id"))
        object.__setattr__(self, "atoms", tuple(self.atoms))
        object.__setattr__(self, "bonds", tuple(self.bonds))
        object.__setattr__(self, "residues", tuple(self.residues))
        object.__setattr__(self, "chains", tuple(self.chains))
        object.__setattr__(self, "coordinate_unit", _strict_string(self.coordinate_unit, field_name="coordinate_unit").lower())
        object.__setattr__(self, "schema_id", _strict_string(self.schema_id, field_name="schema_id"))
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata_mapping(self.metadata, field_name="system.metadata"),
        )

    @property
    def atom_count(self) -> int:
        return len(self.atoms)

    @property
    def model_count(self) -> int:
        return int(self.coordinates.shape[0])

    @property
    def has_coordinates(self) -> bool:
        return self.model_count > 0

    def with_coordinates(self, coordinates: torch.Tensor) -> "AllAtomSystem":
        """Return the same immutable topology with a new coordinate ensemble."""

        return replace(self, coordinates=coordinates)
