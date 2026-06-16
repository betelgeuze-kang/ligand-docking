from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from betelgeuze_ai_md.contracts.claim_scope import CLAIM_SCOPE_RESTRICTED_LOCAL
from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.serialization import sha256_payload, to_plain
from betelgeuze_ai_md.contracts.units import CANONICAL_UNITS


def _text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContractValidationError(f"{field_name} is required")
    return text


def _xyz(value: Any, field_name: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ContractValidationError(f"{field_name} must be a 3-vector")
    return (float(value[0]), float(value[1]), float(value[2]))


@dataclass(frozen=True)
class AtomRecord:
    atom_id: str
    element: str
    xyz: tuple[float, float, float]
    residue_id: str = ""
    molecule_id: str = ""
    charge: float = 0.0
    radius: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "atom_id", _text(self.atom_id, "atom_id"))
        object.__setattr__(self, "element", _text(self.element, "element").upper())
        object.__setattr__(self, "xyz", _xyz(self.xyz, "xyz"))
        object.__setattr__(self, "charge", float(self.charge))
        object.__setattr__(self, "radius", float(self.radius))


@dataclass(frozen=True)
class BondRecord:
    atom_i: str
    atom_j: str
    order: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "atom_i", _text(self.atom_i, "atom_i"))
        object.__setattr__(self, "atom_j", _text(self.atom_j, "atom_j"))
        if self.atom_i == self.atom_j:
            raise ContractValidationError("bond endpoints must be distinct")
        object.__setattr__(self, "order", float(self.order))
        if self.order <= 0.0:
            raise ContractValidationError("bond order must be positive")


@dataclass(frozen=True)
class MolecularProject:
    project_id: str
    target_id: str
    family: str
    receptor_structure: str
    ligand_library: list[dict[str, Any]] = field(default_factory=list)
    pocket_definition: dict[str, Any] = field(default_factory=dict)
    run_profile: dict[str, Any] = field(default_factory=dict)
    claim_scope: str = CLAIM_SCOPE_RESTRICTED_LOCAL
    units: dict[str, str] = field(default_factory=lambda: dict(CANONICAL_UNITS))

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", _text(self.project_id, "project_id"))
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        object.__setattr__(self, "family", _text(self.family, "family").lower())
        object.__setattr__(self, "receptor_structure", _text(self.receptor_structure, "receptor_structure"))
        object.__setattr__(self, "claim_scope", _text(self.claim_scope, "claim_scope"))

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def contract_hash(self) -> str:
        return sha256_payload(self)

@dataclass(frozen=True)
class MolecularSystem:
    system_id: str
    atoms: list[AtomRecord]
    bonds: list[BondRecord] = field(default_factory=list)
    residues: list[dict[str, Any]] = field(default_factory=list)
    ligands: list[dict[str, Any]] = field(default_factory=list)
    beads: list[dict[str, Any]] = field(default_factory=list)
    mapping: dict[str, Any] = field(default_factory=dict)
    topology_report: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "system_id", _text(self.system_id, "system_id"))
        atom_ids = [atom.atom_id for atom in self.atoms]
        if not atom_ids:
            raise ContractValidationError("MolecularSystem requires at least one atom")
        if len(atom_ids) != len(set(atom_ids)):
            raise ContractValidationError("atom_id values must be unique")
        atom_set = set(atom_ids)
        for bond in self.bonds:
            if bond.atom_i not in atom_set or bond.atom_j not in atom_set:
                raise ContractValidationError("bond references an unknown atom_id")

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def contract_hash(self) -> str:
        return sha256_payload(self)


@dataclass(frozen=True)
class CoarseState:
    x: list[list[float]]
    v: list[list[float]]
    mass: list[float]
    charge: list[float]
    bead_type: list[int]
    molecule_id: list[int]
    residue_id: list[int]
    mask: list[bool]
    units: dict[str, str] = field(default_factory=lambda: dict(CANONICAL_UNITS))

    def __post_init__(self) -> None:
        n = len(self.x)
        if n <= 0:
            raise ContractValidationError("CoarseState requires at least one bead")
        for field_name, coords in (("x", self.x), ("v", self.v)):
            if len(coords) != n:
                raise ContractValidationError(f"{field_name} length must match x")
            for row in coords:
                _xyz(row, field_name)
        for field_name, values in (
            ("mass", self.mass),
            ("charge", self.charge),
            ("bead_type", self.bead_type),
            ("molecule_id", self.molecule_id),
            ("residue_id", self.residue_id),
            ("mask", self.mask),
        ):
            if len(values) != n:
                raise ContractValidationError(f"{field_name} length must match x")
        if any(float(mass) <= 0.0 for mass in self.mass):
            raise ContractValidationError("mass values must be positive")

    def to_dict(self) -> dict[str, Any]:
        return to_plain(self)

    def contract_hash(self) -> str:
        return sha256_payload(self)
