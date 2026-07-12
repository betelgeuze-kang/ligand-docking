"""Canonical, versioned all-atom molecular data model.

Topology records use stable zero-based indices. Coordinates are kept in one
floating ``torch.Tensor`` with shape ``[M, N, 3]`` (models, atoms, xyz) so the
same topology can carry an ensemble without duplicating atom metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID, ClaimStage


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
_ATOMIC_NUMBER_BY_SYMBOL = {
    symbol: number for number, symbol in enumerate(_ELEMENT_SYMBOLS) if symbol
}


def canonical_element_symbol(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[0].upper() + text[1:].lower()


def atomic_number_for_element(element: str) -> int:
    return int(_ATOMIC_NUMBER_BY_SYMBOL.get(canonical_element_symbol(element), 0))


def element_for_atomic_number(atomic_number: int) -> str:
    number = int(atomic_number)
    if number < 1 or number >= len(_ELEMENT_SYMBOLS):
        raise ValueError(f"atomic_number must be in [1, 118], got {number}")
    return _ELEMENT_SYMBOLS[number]


def _digest_or_empty(value: str, *, field_name: str) -> str:
    digest = str(value or "").strip().lower()
    if digest and _SHA256_RE.fullmatch(digest) is None:
        raise ValueError(f"{field_name} must be 64 lowercase hexadecimal characters")
    return digest


@dataclass(frozen=True)
class Atom:
    """One explicit atom, including hydrogens when present in the source."""

    index: int
    name: str
    element: str
    atomic_number: int
    residue_index: int
    formal_charge: int = 0
    partial_charge_e: float | None = None
    mass_da: float | None = None
    isotope_mass_number: int | None = None
    serial: int | None = None
    altloc: str = ""
    occupancy: float | None = None
    b_factor: float | None = None
    aromatic: bool = False
    stereo: str = "unspecified"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", int(self.index))
        object.__setattr__(self, "atomic_number", int(self.atomic_number))
        object.__setattr__(self, "residue_index", int(self.residue_index))
        object.__setattr__(self, "formal_charge", int(self.formal_charge))
        object.__setattr__(
            self,
            "partial_charge_e",
            None if self.partial_charge_e is None else float(self.partial_charge_e),
        )
        object.__setattr__(self, "mass_da", None if self.mass_da is None else float(self.mass_da))
        object.__setattr__(
            self,
            "isotope_mass_number",
            None if self.isotope_mass_number is None else int(self.isotope_mass_number),
        )
        object.__setattr__(self, "serial", None if self.serial is None else int(self.serial))
        object.__setattr__(self, "occupancy", None if self.occupancy is None else float(self.occupancy))
        object.__setattr__(self, "b_factor", None if self.b_factor is None else float(self.b_factor))
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "element", canonical_element_symbol(self.element))
        object.__setattr__(self, "altloc", str(self.altloc or "").strip())
        object.__setattr__(self, "stereo", str(self.stereo or "unspecified"))
        object.__setattr__(self, "metadata", dict(self.metadata))


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
        object.__setattr__(self, "index", int(self.index))
        object.__setattr__(self, "atom_i", int(self.atom_i))
        object.__setattr__(self, "atom_j", int(self.atom_j))
        object.__setattr__(self, "order", float(self.order))
        object.__setattr__(self, "stereo", str(self.stereo or "none"))
        object.__setattr__(self, "source", str(self.source or "unknown"))
        object.__setattr__(self, "metadata", dict(self.metadata))


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
        object.__setattr__(self, "index", int(self.index))
        object.__setattr__(self, "chain_index", int(self.chain_index))
        object.__setattr__(self, "sequence_number", int(self.sequence_number))
        object.__setattr__(self, "name", str(self.name).strip().upper())
        object.__setattr__(self, "atom_indices", tuple(int(value) for value in self.atom_indices))
        object.__setattr__(self, "insertion_code", str(self.insertion_code or "").strip())
        object.__setattr__(self, "entity_type", str(self.entity_type or "unknown"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class Chain:
    index: int
    chain_id: str
    residue_indices: tuple[int, ...]
    entity_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", int(self.index))
        object.__setattr__(self, "chain_id", str(self.chain_id))
        object.__setattr__(self, "residue_indices", tuple(int(value) for value in self.residue_indices))
        object.__setattr__(self, "entity_id", str(self.entity_id or ""))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class UnitCell:
    """Lattice vectors in Angstrom, stored as three row vectors."""

    vectors: torch.Tensor
    periodic: tuple[bool, bool, bool] = (True, True, True)

    def __post_init__(self) -> None:
        if not isinstance(self.vectors, torch.Tensor):
            raise TypeError("unit-cell vectors must be a torch.Tensor")
        if self.vectors.shape != (3, 3):
            raise ValueError("unit-cell vectors must have shape [3, 3]")
        if not self.vectors.is_floating_point():
            raise TypeError("unit-cell vectors must use a floating dtype")
        if len(self.periodic) != 3:
            raise ValueError("unit-cell periodic flags must have length 3")
        object.__setattr__(self, "periodic", tuple(bool(value) for value in self.periodic))

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
    """Origin and transformation evidence for a canonical molecular system."""

    source_format: str
    source_id: str = ""
    source_sha256: str = ""
    parser_name: str = ""
    parser_version: str = ""
    operations: tuple[str, ...] = ()
    parent_sha256: tuple[str, ...] = ()
    source_digest_verified: bool = False
    transformation_chain_verified: bool = False
    chemistry_validated: bool = False
    scientifically_validated: bool = False
    product_qualified: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_format", str(self.source_format or "unknown").lower())
        object.__setattr__(self, "source_id", str(self.source_id or ""))
        object.__setattr__(
            self,
            "source_sha256",
            _digest_or_empty(self.source_sha256, field_name="source_sha256"),
        )
        object.__setattr__(self, "parser_name", str(self.parser_name or ""))
        object.__setattr__(self, "parser_version", str(self.parser_version or ""))
        object.__setattr__(self, "operations", tuple(str(value) for value in self.operations))
        object.__setattr__(
            self,
            "parent_sha256",
            tuple(_digest_or_empty(value, field_name="parent_sha256") for value in self.parent_sha256),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.source_digest_verified and not self.source_sha256:
            raise ValueError("source_digest_verified requires source_sha256")
        if self.chemistry_validated and not self.provenance_verified:
            raise ValueError("chemistry_validated requires verified provenance")
        if self.scientifically_validated and not self.chemistry_validated:
            raise ValueError("scientifically_validated requires chemistry_validated")
        if self.product_qualified and not self.scientifically_validated:
            raise ValueError("product_qualified requires scientifically_validated")

    @property
    def provenance_verified(self) -> bool:
        return bool(self.source_digest_verified and self.transformation_chain_verified)

    @property
    def claim_stage(self) -> ClaimStage:
        if self.product_qualified:
            return ClaimStage.PRODUCT_QUALIFIED
        if self.scientifically_validated:
            return ClaimStage.SCIENTIFICALLY_VALIDATED
        if self.chemistry_validated:
            return ClaimStage.CHEMISTRY_VALIDATED
        if self.provenance_verified:
            return ClaimStage.PROVENANCE_VERIFIED
        return ClaimStage.CONTRACT_VALID

    @property
    def claim_safe(self) -> bool:
        """Compatibility alias; scientific validation is required."""

        return self.claim_stage.claim_safe


@dataclass(frozen=True)
class AllAtomSystem:
    """Canonical topology plus one or more all-atom coordinate models."""

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
        if not isinstance(self.coordinates, torch.Tensor):
            raise TypeError("coordinates must be a torch.Tensor")
        if self.coordinates.ndim != 3 or self.coordinates.shape[-1] != 3:
            raise ValueError("coordinates must have shape [M, N, 3]")
        if not self.coordinates.is_floating_point():
            raise TypeError("coordinates must use a floating dtype")
        object.__setattr__(self, "system_id", str(self.system_id))
        object.__setattr__(self, "atoms", tuple(self.atoms))
        object.__setattr__(self, "bonds", tuple(self.bonds))
        object.__setattr__(self, "residues", tuple(self.residues))
        object.__setattr__(self, "chains", tuple(self.chains))
        object.__setattr__(self, "coordinate_unit", str(self.coordinate_unit).lower())
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def atom_count(self) -> int:
        return len(self.atoms)

    @property
    def model_count(self) -> int:
        return int(self.coordinates.shape[0])

    def with_coordinates(
        self,
        coordinates: torch.Tensor,
        *,
        operation: str,
        operation_evidence_sha256: str = "",
    ) -> "AllAtomSystem":
        """Return transformed coordinates and invalidate transformation claims.

        The immutable source digest remains attached, but transformed state is
        not provenance-verified until a separate verifier attests the operation.
        """

        operation_name = str(operation or "").strip()
        if not operation_name:
            raise ValueError("coordinate transformations must declare an operation")
        evidence_digest = _digest_or_empty(
            operation_evidence_sha256,
            field_name="operation_evidence_sha256",
        )
        from .serialization import canonical_system_sha256

        parent_digest = canonical_system_sha256(self)
        metadata = dict(self.provenance.metadata)
        metadata["last_operation"] = operation_name
        metadata["last_operation_evidence_sha256"] = evidence_digest
        derived_provenance = replace(
            self.provenance,
            operations=(*self.provenance.operations, operation_name),
            parent_sha256=(*self.provenance.parent_sha256, parent_digest),
            transformation_chain_verified=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata=metadata,
        )
        return replace(self, coordinates=coordinates, provenance=derived_provenance)
