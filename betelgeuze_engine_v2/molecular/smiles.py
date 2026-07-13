"""Strict, topology-only SMILES ingestion for the canonical all-atom model.

RDKit is deliberately an optional, function-local syntax and chemistry
adapter.  Successful RDKit sanitization is followed by a small independent
canonical-graph validation pass; it is never treated as preparation for
numeric engine execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Iterable

import torch

from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
    element_for_atomic_number,
)
from .observation import attach_parser_observation_digest
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256
from .validation import MolecularValidationError, require_valid_all_atom_system


SMILES_PARSER_VERSION = "1.4.0"

# The sole production-supported version is the repository's pinned RDKit.
# Tests may monkeypatch this private set to exercise adapter semantics with a
# locally installed historical RDKit, but production code must not broaden it.
_SUPPORTED_RDKIT_VERSIONS = frozenset({"2025.9.6"})

_MAX_INPUT_BYTES = 64 * 1024
_MAX_SOURCE_ID_BYTES = 4_096
_MAX_SOURCE_ATOMS = 4096
_MAX_EXPANDED_ATOMS = 16384
_MAX_BONDS = 32768
_MAX_FRAGMENTS = 256
_MAX_ABS_CANONICAL_FORMAL_CHARGE = (1 << 15) - 1

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_BASE_BLOCKERS = (
    "coordinates_missing",
    "partial_charges_not_assigned",
    "force_field_parameters_not_assigned",
    "protonation_not_independently_assessed",
    "tautomer_not_independently_assessed",
    "hydrogen_expansion_not_independently_valence_verified",
    "rdkit_sanitization_not_independently_revalidated",
    "stereochemistry_completeness_not_assessed",
    "chemistry_applicability_not_established",
)


class SmilesParseError(ValueError):
    """Stable, raw-input-free failure raised by :func:`parse_smiles`."""

    def __init__(self, code: str, detail: str, *, position: int | None = None):
        self.code = str(code)
        self.position = None if position is None else int(position)
        self.detail = str(detail)
        location = "" if self.position is None else f" at byte {self.position}"
        super().__init__(f"smiles:{self.code}{location}: {self.detail}")


@dataclass(frozen=True)
class SmilesIngestCoverage:
    rdkit_version: str
    source_atom_count: int
    expanded_atom_count: int
    bond_count: int
    fragment_count: int
    generated_hydrogen_count: int
    explicit_hydrogen_count: int
    formal_charge_total: int
    isotope_count: int
    atom_map_count: int
    aromatic_atom_count: int
    typed_atom_stereo_count: int
    typed_bond_stereo_count: int
    ordered_topology_sha256: str
    canonical_topology_schema_id: str
    canonical_topology_sha256: str
    blockers: tuple[str, ...]
    ingest_supported: bool = True
    chemistry_supported: bool = False
    parameterability_assessed: bool = False
    all_hydrogens_explicit: bool = True
    topology_only: bool = True
    preparation_ready: bool = False
    claim_safe: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "smiles",
            "parser_version": SMILES_PARSER_VERSION,
            "rdkit_version": self.rdkit_version,
            "supported": self.ingest_supported,
            "ingest_supported": self.ingest_supported,
            "chemistry_supported": self.chemistry_supported,
            "parameterability_assessed": self.parameterability_assessed,
            "all_hydrogens_explicit": self.all_hydrogens_explicit,
            "topology_only": self.topology_only,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
            "source_atom_count": self.source_atom_count,
            "expanded_atom_count": self.expanded_atom_count,
            "bond_count": self.bond_count,
            "fragment_count": self.fragment_count,
            "generated_hydrogen_count": self.generated_hydrogen_count,
            "explicit_hydrogen_count": self.explicit_hydrogen_count,
            "formal_charge_total": self.formal_charge_total,
            "isotope_count": self.isotope_count,
            "atom_map_count": self.atom_map_count,
            "aromatic_atom_count": self.aromatic_atom_count,
            "typed_atom_stereo_count": self.typed_atom_stereo_count,
            "typed_bond_stereo_count": self.typed_bond_stereo_count,
            "ordered_topology_sha256": self.ordered_topology_sha256,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class SmilesIngestResult:
    system: AllAtomSystem
    coverage: SmilesIngestCoverage

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe summary without embedding coordinates or source text."""

        return {
            "system": {
                "schema_id": self.system.schema_id,
                "system_id": self.system.system_id,
                "atom_count": self.system.atom_count,
                "bond_count": len(self.system.bonds),
                "residue_count": len(self.system.residues),
                "chain_count": len(self.system.chains),
                "model_count": self.system.model_count,
                "source_sha256": self.system.provenance.source_sha256,
                "ordered_topology_sha256": self.coverage.ordered_topology_sha256,
                "canonical_topology_schema_id": self.coverage.canonical_topology_schema_id,
                "canonical_topology_sha256": self.coverage.canonical_topology_sha256,
            },
            "coverage": self.coverage.to_dict(),
        }


@dataclass(frozen=True)
class _SourceAtomRecord:
    index: int
    atomic_number: int
    formal_charge: int
    isotope_mass_number: int | None
    atom_map: int | None
    aromatic: bool
    stereo: str
    chiral_tag: str
    bracket_hydrogen_count: int
    implicit_hydrogen_count: int


@dataclass(frozen=True)
class _SourceBondRecord:
    index: int
    atom_i: int
    atom_j: int
    order: float
    aromatic: bool
    stereo: str
    stereo_atom_indices: tuple[int, ...]


@dataclass(frozen=True)
class _PreSanitizeStereoState:
    atom_chiral_tags: tuple[str, ...]
    bond_endpoints: tuple[tuple[int, int], ...]
    bond_types: tuple[str, ...]
    directional_double_bonds: tuple[tuple[int, str, tuple[int, ...]], ...]


@dataclass(frozen=True)
class _GraphValidation:
    components: tuple[tuple[int, ...], ...]
    formal_charge_total: int


def _import_rdkit() -> tuple[Any, Any]:
    from rdkit import Chem, rdBase

    return Chem, rdBase


def _version_key(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _rdkit_version_is_supported(version: str) -> bool:
    candidate = _version_key(version)
    if candidate is None:
        return False
    return any(
        _version_key(allowed) == candidate for allowed in _SUPPORTED_RDKIT_VERSIONS
    )


def _validate_input(data: bytes, source_id: str) -> tuple[str, str]:
    if type(data) is not bytes:
        raise TypeError("data must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded_source_id = source_id.encode("utf-8")
    except UnicodeEncodeError:
        raise SmilesParseError(
            "invalid_source_id",
            "source_id must contain only Unicode scalar values",
        ) from None
    if len(encoded_source_id) > _MAX_SOURCE_ID_BYTES:
        raise SmilesParseError(
            "source_id_too_large",
            "source_id exceeds the fixed 4096-byte UTF-8 limit",
        )
    if len(data) > _MAX_INPUT_BYTES:
        raise SmilesParseError(
            "input_too_large",
            "SMILES input exceeds the fixed 64 KiB limit",
            position=_MAX_INPUT_BYTES,
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SmilesParseError(
            "non_ascii_input",
            "SMILES input must contain ASCII bytes only",
            position=exc.start,
        ) from None
    if not text:
        raise SmilesParseError(
            "empty_input",
            "SMILES input must contain exactly one non-empty line",
            position=0,
        )
    newline_positions = [
        position for position in (text.find("\n"), text.find("\r")) if position >= 0
    ]
    if newline_positions:
        raise SmilesParseError(
            "multiline_input",
            "SMILES input must contain exactly one non-empty line",
            position=min(newline_positions),
        )
    cx_position = text.find("|")
    if cx_position >= 0:
        raise SmilesParseError(
            "cxsmiles_forbidden",
            "CXSMILES extensions are not accepted",
            position=cx_position,
        )
    whitespace_position = next(
        (index for index, char in enumerate(text) if char.isspace()), None
    )
    if whitespace_position is not None:
        raise SmilesParseError(
            "whitespace_forbidden",
            "whitespace and trailing molecule names are not accepted",
            position=whitespace_position,
        )
    control_position = next(
        (
            index
            for index, char in enumerate(text)
            if ord(char) < 0x21 or ord(char) > 0x7E
        ),
        None,
    )
    if control_position is not None:
        raise SmilesParseError(
            "invalid_character",
            "SMILES input contains a non-printable ASCII character",
            position=control_position,
        )
    return text, hashlib.sha256(data).hexdigest()


def _load_adapter() -> tuple[Any, Any, str]:
    try:
        Chem, rdBase = _import_rdkit()
    except Exception:
        raise SmilesParseError(
            "rdkit_unavailable",
            "the optional RDKit dependency is unavailable",
        ) from None
    version = getattr(rdBase, "rdkitVersion", None)
    if type(version) is not str or not _rdkit_version_is_supported(version):
        raise SmilesParseError(
            "unsupported_rdkit_version",
            "the installed RDKit version is not allowlisted",
        )
    if not hasattr(rdBase, "BlockLogs"):
        raise SmilesParseError(
            "rdkit_adapter_incompatible",
            "the RDKit adapter cannot suppress raw parser diagnostics",
        )
    return Chem, rdBase, version


def _configured_parser_params(Chem: Any) -> Any:
    try:
        params = Chem.SmilesParserParams()
        required = {
            "sanitize": False,
            "removeHs": False,
            "parseName": False,
            "allowCXSMILES": False,
            "strictCXSMILES": True,
        }
        for name, value in required.items():
            if not hasattr(params, name):
                raise AttributeError(name)
            setattr(params, name, value)
            if getattr(params, name) is not value:
                raise AttributeError(name)
        return params
    except (AttributeError, TypeError, RuntimeError):
        raise SmilesParseError(
            "rdkit_adapter_incompatible",
            "required strict SMILES parser parameters are unavailable",
        ) from None


def _source_identity(mol: Any) -> tuple[tuple[int, int, int, int, int], ...]:
    identity: list[tuple[int, int, int, int, int]] = []
    for expected_index, atom in enumerate(mol.GetAtoms()):
        atom.SetIntProp("_betelgeuze_source_index", expected_index)
        identity.append(
            (
                expected_index,
                int(atom.GetAtomicNum()),
                int(atom.GetIsotope()),
                int(atom.GetAtomMapNum()),
                int(atom.GetFormalCharge()),
            )
        )
    return tuple(identity)


def _assert_source_identity_unchanged(
    mol: Any, expected: tuple[tuple[int, int, int, int, int], ...]
) -> None:
    observed: list[tuple[int, int, int, int, int]] = []
    for expected_index, atom in enumerate(mol.GetAtoms()):
        if not atom.HasProp("_betelgeuze_source_index"):
            raise SmilesParseError(
                "source_atom_identity_changed",
                "RDKit did not preserve source atom identity during sanitization",
            )
        try:
            source_index = int(atom.GetIntProp("_betelgeuze_source_index"))
        except (KeyError, TypeError, ValueError, RuntimeError):
            raise SmilesParseError(
                "source_atom_identity_changed",
                "RDKit did not preserve source atom identity during sanitization",
            ) from None
        if source_index != expected_index:
            raise SmilesParseError(
                "source_atom_order_changed",
                "RDKit changed source atom order during sanitization",
            )
        observed.append(
            (
                source_index,
                int(atom.GetAtomicNum()),
                int(atom.GetIsotope()),
                int(atom.GetAtomMapNum()),
                int(atom.GetFormalCharge()),
            )
        )
    if tuple(observed) != expected:
        raise SmilesParseError(
            "source_atom_identity_changed",
            "RDKit changed element, isotope, atom map, or charge during sanitization",
        )


def _capture_pre_sanitize_stereo_state(mol: Any) -> _PreSanitizeStereoState:
    atom_chiral_tags = tuple(str(atom.GetChiralTag()) for atom in mol.GetAtoms())
    allowed_atom_tags = {
        "CHI_UNSPECIFIED",
        "CHI_TETRAHEDRAL_CW",
        "CHI_TETRAHEDRAL_CCW",
    }
    if any(tag not in allowed_atom_tags for tag in atom_chiral_tags):
        raise SmilesParseError(
            "unsupported_atom_stereo",
            "only tetrahedral atom stereochemistry is accepted",
        )

    raw_bonds = tuple(mol.GetBonds())
    bond_endpoints = tuple(
        tuple(sorted((int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx()))))
        for bond in raw_bonds
    )
    bond_types = tuple(str(bond.GetBondType()).upper() for bond in raw_bonds)
    directional: list[tuple[int, str, tuple[int, ...]]] = []
    for bond_index, bond in enumerate(raw_bonds):
        direction = str(bond.GetBondDir()).upper()
        if direction == "NONE":
            continue
        if direction not in {"ENDUPRIGHT", "ENDDOWNRIGHT"}:
            raise SmilesParseError(
                "unsupported_bond_stereo",
                "only SMILES double-bond direction markers are accepted",
            )
        endpoints = set(bond_endpoints[bond_index])
        adjacent_double_bonds = tuple(
            candidate_index
            for candidate_index, (candidate_endpoints, candidate_type) in enumerate(
                zip(bond_endpoints, bond_types)
            )
            if candidate_index != bond_index
            and candidate_type == "DOUBLE"
            and len(endpoints.intersection(candidate_endpoints)) == 1
        )
        if not adjacent_double_bonds:
            raise SmilesParseError(
                "stereo_marker_not_retained",
                "a directional bond marker is not attached to a double bond",
            )
        directional.append((bond_index, direction, adjacent_double_bonds))
    return _PreSanitizeStereoState(
        atom_chiral_tags=atom_chiral_tags,
        bond_endpoints=bond_endpoints,
        bond_types=bond_types,
        directional_double_bonds=tuple(directional),
    )


def _assert_stereo_markers_retained(
    mol: Any, expected: _PreSanitizeStereoState
) -> None:
    if int(mol.GetNumAtoms()) != len(expected.atom_chiral_tags):
        raise SmilesParseError(
            "source_atom_identity_changed",
            "RDKit changed the source atom count during sanitization",
        )
    post_bonds = tuple(mol.GetBonds())
    if len(post_bonds) != len(expected.bond_endpoints):
        raise SmilesParseError(
            "source_bond_identity_changed",
            "RDKit changed the source bond count during sanitization",
        )
    for bond_index, bond in enumerate(post_bonds):
        endpoints = tuple(
            sorted((int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx())))
        )
        if endpoints != expected.bond_endpoints[bond_index]:
            raise SmilesParseError(
                "source_bond_identity_changed",
                "RDKit changed source bond endpoints during sanitization",
            )
        before_type = expected.bond_types[bond_index]
        after_type = str(bond.GetBondType()).upper()
        aromaticity_transition = (
            before_type in {"SINGLE", "DOUBLE", "AROMATIC"}
            and after_type == "AROMATIC"
            and bool(bond.GetIsAromatic())
        )
        if after_type != before_type and not aromaticity_transition:
            raise SmilesParseError(
                "source_bond_identity_changed",
                "RDKit changed a source bond type during sanitization",
            )

    for atom_index, before_tag in enumerate(expected.atom_chiral_tags):
        if before_tag == "CHI_UNSPECIFIED":
            continue
        stereo, _ = _atom_stereo(mol.GetAtomWithIdx(atom_index))
        if stereo not in {"R", "S"}:
            raise SmilesParseError(
                "stereo_marker_not_retained",
                "an explicit tetrahedral stereo marker was not retained",
            )

    for _, _, candidate_double_bonds in expected.directional_double_bonds:
        if not any(
            str(post_bonds[bond_index].GetStereo()).upper() in {"STEREOE", "STEREOZ"}
            for bond_index in candidate_double_bonds
        ):
            raise SmilesParseError(
                "stereo_marker_not_retained",
                "an explicit double-bond direction marker was not retained",
            )


def _atom_stereo(atom: Any) -> tuple[str, str]:
    chiral_tag = str(atom.GetChiralTag())
    if chiral_tag not in {
        "CHI_UNSPECIFIED",
        "CHI_TETRAHEDRAL_CW",
        "CHI_TETRAHEDRAL_CCW",
    }:
        raise SmilesParseError(
            "unsupported_atom_stereo",
            "only tetrahedral atom stereochemistry is accepted",
        )
    if atom.HasProp("_CIPCode"):
        try:
            value = str(atom.GetProp("_CIPCode"))
        except (KeyError, RuntimeError):
            value = ""
        if value in {"R", "S"}:
            return value, chiral_tag
        if value in {"r", "s"}:
            raise SmilesParseError(
                "unsupported_atom_stereo",
                "pseudoasymmetric atom stereochemistry is not accepted",
            )
    if chiral_tag != "CHI_UNSPECIFIED":
        return "UNKNOWN", chiral_tag
    return "UNSPECIFIED", chiral_tag


def _bond_stereo(bond: Any) -> str:
    value = str(bond.GetStereo()).upper()
    mapping = {
        "STEREONONE": "none",
        "STEREOANY": "unknown",
        "STEREOE": "E",
        "STEREOZ": "Z",
    }
    if value not in mapping:
        raise SmilesParseError(
            "unsupported_bond_stereo",
            "RDKit returned an unsupported bond stereochemistry label",
        )
    return mapping[value]


def _extract_source_records(
    mol: Any,
) -> tuple[tuple[_SourceAtomRecord, ...], tuple[_SourceBondRecord, ...]]:
    source_bonds: list[_SourceBondRecord] = []
    allowed_bond_types = {
        "SINGLE": (1.0, False),
        "DOUBLE": (2.0, False),
        "TRIPLE": (3.0, False),
        "AROMATIC": (1.5, True),
    }
    for index, bond in enumerate(mol.GetBonds()):
        if bool(bond.HasQuery()):
            raise SmilesParseError(
                "query_bond_forbidden",
                "query, zero, and unspecified bonds are not accepted",
            )
        bond_type = str(bond.GetBondType()).upper()
        if bond_type not in allowed_bond_types:
            raise SmilesParseError(
                "unsupported_bond",
                "only single, double, triple, and aromatic bonds are accepted",
            )
        order, aromatic = allowed_bond_types[bond_type]
        if bool(bond.GetIsAromatic()) is not aromatic:
            raise SmilesParseError(
                "inconsistent_aromatic_bond",
                "RDKit returned inconsistent aromatic bond flags",
            )
        atom_i, atom_j = sorted(
            (int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx()))
        )
        source_bonds.append(
            _SourceBondRecord(
                index=index,
                atom_i=atom_i,
                atom_j=atom_j,
                order=order,
                aromatic=aromatic,
                stereo=_bond_stereo(bond),
                stereo_atom_indices=tuple(
                    int(value) for value in bond.GetStereoAtoms()
                ),
            )
        )

    source_atoms: list[_SourceAtomRecord] = []
    atom_maps: set[int] = set()
    for index, atom in enumerate(mol.GetAtoms()):
        if bool(atom.HasQuery()):
            raise SmilesParseError(
                "query_atom_forbidden", "query atoms are not accepted"
            )
        atomic_number = int(atom.GetAtomicNum())
        if atomic_number == 0:
            raise SmilesParseError(
                "wildcard_atom_forbidden", "wildcard atoms are not accepted"
            )
        try:
            element_for_atomic_number(atomic_number)
        except ValueError:
            raise SmilesParseError(
                "unsupported_element",
                "atom atomic number is outside the canonical periodic table",
            ) from None
        if int(atom.GetNumRadicalElectrons()) != 0:
            raise SmilesParseError(
                "radical_atom_forbidden", "radical atoms are not accepted"
            )
        atom_map_value = int(atom.GetAtomMapNum())
        atom_map = None if atom_map_value == 0 else atom_map_value
        if atom_map is not None:
            if atom_map < 1:
                raise SmilesParseError(
                    "invalid_atom_map", "atom maps must be positive integers"
                )
            if atom_map in atom_maps:
                raise SmilesParseError(
                    "duplicate_atom_map",
                    "positive atom maps must be unique across the source graph",
                )
            atom_maps.add(atom_map)
        isotope_value = int(atom.GetIsotope())
        if isotope_value and not atomic_number <= isotope_value <= 350:
            raise SmilesParseError(
                "unsupported_isotope",
                "isotope mass number is outside the canonical contract",
            )
        stereo, chiral_tag = _atom_stereo(atom)
        formal_charge = int(atom.GetFormalCharge())
        if abs(formal_charge) > _MAX_ABS_CANONICAL_FORMAL_CHARGE:
            raise SmilesParseError(
                "unsupported_formal_charge",
                "formal charge exceeds the canonical magnitude limit",
            )
        source_atoms.append(
            _SourceAtomRecord(
                index=index,
                atomic_number=atomic_number,
                formal_charge=formal_charge,
                isotope_mass_number=None if isotope_value == 0 else isotope_value,
                atom_map=atom_map,
                aromatic=bool(atom.GetIsAromatic()),
                stereo=stereo,
                chiral_tag=chiral_tag,
                bracket_hydrogen_count=int(atom.GetNumExplicitHs()),
                implicit_hydrogen_count=int(atom.GetNumImplicitHs()),
            )
        )
    return tuple(source_atoms), tuple(source_bonds)


def _graph_components(
    atom_count: int, bonds: Iterable[Bond | _SourceBondRecord]
) -> tuple[tuple[int, ...], ...]:
    adjacency: list[list[int]] = [[] for _ in range(atom_count)]
    for bond in bonds:
        adjacency[bond.atom_i].append(bond.atom_j)
        adjacency[bond.atom_j].append(bond.atom_i)
    visited = [False] * atom_count
    components: list[tuple[int, ...]] = []
    for start in range(atom_count):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        members: list[int] = []
        while stack:
            current = stack.pop()
            members.append(current)
            for neighbor in sorted(adjacency[current], reverse=True):
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)
        components.append(tuple(sorted(members)))
    return tuple(components)


def _revalidate_canonical_graph(
    atoms: tuple[Atom, ...],
    bonds: tuple[Bond, ...],
    *,
    expected_formal_charge_total: int,
) -> _GraphValidation:
    """Dependency-free graph checks, intentionally narrower than chemistry perception."""

    if tuple(atom.index for atom in atoms) != tuple(range(len(atoms))):
        raise SmilesParseError(
            "canonical_graph_invalid", "atom indices are not canonical"
        )
    atom_maps: set[int] = set()
    for atom in atoms:
        if atomic_number_for_element(atom.element) != atom.atomic_number:
            raise SmilesParseError(
                "canonical_graph_invalid",
                "element and atomic number disagree after adapter conversion",
            )
        if atom.atom_map is not None:
            if atom.atom_map < 1 or atom.atom_map in atom_maps:
                raise SmilesParseError(
                    "canonical_graph_invalid", "atom maps are not positive and unique"
                )
            atom_maps.add(atom.atom_map)
    formal_charge_total = sum(atom.formal_charge for atom in atoms)
    if formal_charge_total != expected_formal_charge_total:
        raise SmilesParseError(
            "canonical_graph_invalid", "formal charge total changed during conversion"
        )

    if tuple(bond.index for bond in bonds) != tuple(range(len(bonds))):
        raise SmilesParseError(
            "canonical_graph_invalid", "bond indices are not canonical"
        )
    pairs: set[tuple[int, int]] = set()
    degree = [0] * len(atoms)
    attached_bond_by_atom: list[Bond | None] = [None] * len(atoms)
    for bond in bonds:
        if not (0 <= bond.atom_i < bond.atom_j < len(atoms)):
            raise SmilesParseError(
                "canonical_graph_invalid",
                "bond endpoints are out of range or unordered",
            )
        pair = (bond.atom_i, bond.atom_j)
        if pair in pairs:
            raise SmilesParseError(
                "canonical_graph_invalid", "duplicate bonds were produced"
            )
        pairs.add(pair)
        degree[bond.atom_i] += 1
        degree[bond.atom_j] += 1
        if attached_bond_by_atom[bond.atom_i] is None:
            attached_bond_by_atom[bond.atom_i] = bond
        if attached_bond_by_atom[bond.atom_j] is None:
            attached_bond_by_atom[bond.atom_j] = bond
        if bond.order not in {1.0, 1.5, 2.0, 3.0}:
            raise SmilesParseError(
                "canonical_graph_invalid", "unsupported bond order was produced"
            )
        if bond.aromatic:
            if (
                bond.order != 1.5
                or not atoms[bond.atom_i].aromatic
                or not atoms[bond.atom_j].aromatic
            ):
                raise SmilesParseError(
                    "canonical_graph_invalid",
                    "aromatic bond does not join two aromatic endpoints",
                )
        elif bond.order == 1.5:
            raise SmilesParseError(
                "canonical_graph_invalid", "non-aromatic bond has aromatic order"
            )
        if bond.stereo.upper() in {"E", "Z"} and (bond.aromatic or bond.order != 2.0):
            raise SmilesParseError(
                "canonical_graph_invalid", "E/Z stereo is not attached to a double bond"
            )

    adjacency = [set() for _ in atoms]
    for bond in bonds:
        adjacency[bond.atom_i].add(bond.atom_j)
        adjacency[bond.atom_j].add(bond.atom_i)

    aromatic_adjacency: list[list[int]] = [[] for _ in atoms]
    for bond in bonds:
        if bond.aromatic:
            aromatic_adjacency[bond.atom_i].append(bond.atom_j)
            aromatic_adjacency[bond.atom_j].append(bond.atom_i)

    discovery = [-1] * len(atoms)
    low_link = [0] * len(atoms)
    aromatic_parent = [-1] * len(atoms)
    discovery_counter = 0
    cyclic_aromatic_atoms: set[int] = set()
    for start, neighbors in enumerate(aromatic_adjacency):
        if not neighbors or discovery[start] >= 0:
            continue
        component_atoms = [start]
        discovery[start] = discovery_counter
        low_link[start] = discovery_counter
        discovery_counter += 1
        stack: list[tuple[int, int]] = [(start, 0)]
        while stack:
            current, neighbor_offset = stack[-1]
            current_neighbors = aromatic_adjacency[current]
            if neighbor_offset < len(current_neighbors):
                neighbor = current_neighbors[neighbor_offset]
                stack[-1] = (current, neighbor_offset + 1)
                if discovery[neighbor] < 0:
                    aromatic_parent[neighbor] = current
                    discovery[neighbor] = discovery_counter
                    low_link[neighbor] = discovery_counter
                    discovery_counter += 1
                    component_atoms.append(neighbor)
                    stack.append((neighbor, 0))
                elif neighbor != aromatic_parent[current]:
                    low_link[current] = min(
                        low_link[current],
                        discovery[neighbor],
                    )
                continue

            stack.pop()
            parent = aromatic_parent[current]
            if parent >= 0:
                if low_link[current] > discovery[parent]:
                    raise SmilesParseError(
                        "canonical_graph_invalid",
                        "aromatic bond is not part of an independently verified cycle",
                    )
                low_link[parent] = min(low_link[parent], low_link[current])
        cyclic_aromatic_atoms.update(component_atoms)
    if any(atom.aromatic and atom.index not in cyclic_aromatic_atoms for atom in atoms):
        raise SmilesParseError(
            "canonical_graph_invalid",
            "aromatic atom is not part of an independently verified cycle",
        )
    for bond in bonds:
        if bond.stereo.upper() in {"E", "Z"}:
            stereo_atoms = bond.metadata.get("stereo_atom_indices")
            if (
                not isinstance(stereo_atoms, (list, tuple))
                or len(stereo_atoms) != 2
                or any(
                    type(value) is not int or value < 0 or value >= len(atoms)
                    for value in stereo_atoms
                )
                or stereo_atoms[0] == stereo_atoms[1]
                or degree[bond.atom_i] < 2
                or degree[bond.atom_j] < 2
                or not (
                    (
                        stereo_atoms[0] in adjacency[bond.atom_i]
                        and stereo_atoms[1] in adjacency[bond.atom_j]
                    )
                    or (
                        stereo_atoms[1] in adjacency[bond.atom_i]
                        and stereo_atoms[0] in adjacency[bond.atom_j]
                    )
                )
            ):
                raise SmilesParseError(
                    "canonical_graph_invalid",
                    "E/Z stereo references inconsistent neighboring atoms",
                )

    for atom in atoms:
        if atom.stereo.upper() in {"R", "S"} and degree[atom.index] < 3:
            raise SmilesParseError(
                "canonical_graph_invalid", "R/S stereo has insufficient graph neighbors"
            )
        origin = atom.metadata.get("hydrogen_origin")
        if origin in {"bracket_explicit", "implicit"}:
            if atom.atomic_number != 1 or degree[atom.index] != 1:
                raise SmilesParseError(
                    "canonical_graph_invalid",
                    "manually expanded hydrogen is not a terminal hydrogen",
                )
            attached = attached_bond_by_atom[atom.index]
            if attached is None:  # degree-one invariant above must supply one bond
                raise SmilesParseError(
                    "canonical_graph_invalid",
                    "manually expanded hydrogen is not a terminal hydrogen",
                )
            if attached.order != 1.0 or attached.aromatic:
                raise SmilesParseError(
                    "canonical_graph_invalid",
                    "manually expanded hydrogen does not use a single bond",
                )

    components = _graph_components(len(atoms), bonds)
    return _GraphValidation(
        components=components, formal_charge_total=formal_charge_total
    )


def _ordered_topology_digest(
    atoms: tuple[Atom, ...],
    bonds: tuple[Bond, ...],
    components: tuple[tuple[int, ...], ...],
) -> str:
    document = {
        "atoms": [
            {
                "index": atom.index,
                "atomic_number": atom.atomic_number,
                "formal_charge": atom.formal_charge,
                "isotope_mass_number": atom.isotope_mass_number,
                "atom_map": atom.atom_map,
                "aromatic": atom.aromatic,
                "stereo": atom.stereo,
                "residue_index": atom.residue_index,
                "source_atom_index": atom.metadata.get("source_atom_index"),
                "parent_source_atom_index": atom.metadata.get(
                    "parent_source_atom_index"
                ),
                "hydrogen_origin": atom.metadata.get("hydrogen_origin"),
                "hydrogen_ordinal": atom.metadata.get("hydrogen_ordinal"),
            }
            for atom in atoms
        ],
        "bonds": [
            {
                "index": bond.index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order": bond.order,
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
            }
            for bond in bonds
        ],
        "components": [list(component) for component in components],
    }
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _make_canonical_topology(
    source_atoms: tuple[_SourceAtomRecord, ...],
    source_bonds: tuple[_SourceBondRecord, ...],
) -> tuple[tuple[Atom, ...], tuple[Bond, ...], _GraphValidation]:
    source_components = _graph_components(len(source_atoms), source_bonds)
    if len(source_components) > _MAX_FRAGMENTS:
        raise SmilesParseError(
            "too_many_fragments", "source graph exceeds the fixed fragment limit"
        )
    source_component_by_atom: dict[int, int] = {}
    for component_index, component in enumerate(source_components):
        for atom_index in component:
            source_component_by_atom[atom_index] = component_index

    generated_specs: list[tuple[int, str, int]] = []
    for source_atom in source_atoms:
        for origin, count in (
            ("bracket_explicit", source_atom.bracket_hydrogen_count),
            ("implicit", source_atom.implicit_hydrogen_count),
        ):
            if count < 0:
                raise SmilesParseError(
                    "canonical_graph_invalid", "negative hydrogen count was returned"
                )
            generated_specs.extend(
                (source_atom.index, origin, ordinal) for ordinal in range(1, count + 1)
            )
    expanded_atom_count = len(source_atoms) + len(generated_specs)
    if expanded_atom_count > _MAX_EXPANDED_ATOMS:
        raise SmilesParseError(
            "too_many_expanded_atoms", "expanded graph exceeds the fixed atom limit"
        )
    if len(source_bonds) + len(generated_specs) > _MAX_BONDS:
        raise SmilesParseError(
            "too_many_bonds", "expanded graph exceeds the fixed bond limit"
        )

    atoms: list[Atom] = []
    for source_atom in source_atoms:
        element = element_for_atomic_number(source_atom.atomic_number)
        atoms.append(
            Atom(
                index=source_atom.index,
                name=f"{element}{source_atom.index + 1}",
                element=element,
                atomic_number=source_atom.atomic_number,
                residue_index=source_component_by_atom[source_atom.index],
                formal_charge=source_atom.formal_charge,
                formal_charge_known=True,
                isotope_mass_number=source_atom.isotope_mass_number,
                serial=source_atom.index + 1,
                atom_map=source_atom.atom_map,
                aromatic=source_atom.aromatic,
                stereo=source_atom.stereo,
                metadata={
                    "source_atom_index": source_atom.index,
                    "source_atom_order_preserved": True,
                    "hydrogen_origin": "source"
                    if source_atom.atomic_number == 1
                    else "not_hydrogen",
                    "formal_charge_source": "smiles_source_via_pinned_rdkit",
                    "rdkit_chiral_tag": source_atom.chiral_tag,
                },
            )
        )
    for parent_index, origin, ordinal in generated_specs:
        atom_index = len(atoms)
        atoms.append(
            Atom(
                index=atom_index,
                name=f"H{atom_index + 1}",
                element="H",
                atomic_number=1,
                residue_index=source_component_by_atom[parent_index],
                formal_charge=0,
                formal_charge_known=True,
                serial=atom_index + 1,
                aromatic=False,
                stereo="unspecified",
                metadata={
                    "parent_source_atom_index": parent_index,
                    "hydrogen_origin": origin,
                    "hydrogen_ordinal": ordinal,
                    "manually_expanded": True,
                    "formal_charge_source": "manual_hydrogen_expansion_neutral",
                },
            )
        )

    bonds: list[Bond] = []
    for source_bond in source_bonds:
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=source_bond.atom_i,
                atom_j=source_bond.atom_j,
                order=source_bond.order,
                aromatic=source_bond.aromatic,
                stereo=source_bond.stereo,
                source="smiles_source",
                metadata={
                    "source_bond_index": source_bond.index,
                    "stereo_atom_indices": list(source_bond.stereo_atom_indices),
                },
            )
        )
    for generated_offset, (parent_index, origin, ordinal) in enumerate(generated_specs):
        hydrogen_index = len(source_atoms) + generated_offset
        atom_i, atom_j = sorted((parent_index, hydrogen_index))
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=atom_i,
                atom_j=atom_j,
                order=1.0,
                aromatic=False,
                stereo="none",
                source="manual_hydrogen_expansion",
                metadata={
                    "parent_source_atom_index": parent_index,
                    "hydrogen_origin": origin,
                    "hydrogen_ordinal": ordinal,
                },
            )
        )

    atom_tuple = tuple(atoms)
    bond_tuple = tuple(bonds)
    graph_validation = _revalidate_canonical_graph(
        atom_tuple,
        bond_tuple,
        expected_formal_charge_total=sum(atom.formal_charge for atom in source_atoms),
    )
    if len(graph_validation.components) != len(source_components):
        raise SmilesParseError(
            "canonical_graph_invalid",
            "fragment count changed during hydrogen expansion",
        )
    return atom_tuple, bond_tuple, graph_validation


def parse_smiles(data: bytes, *, source_id: str = "") -> SmilesIngestResult:
    """Parse one strict ASCII SMILES line into a topology-only canonical graph.

    The source text is used only for parsing and its SHA-256 digest.  Neither
    the original text nor a normalized/isomeric rendering is retained.
    """

    text, source_sha256 = _validate_input(data, source_id)
    Chem, rdBase, rdkit_version = _load_adapter()
    params = _configured_parser_params(Chem)
    try:
        with rdBase.BlockLogs():
            mol = Chem.MolFromSmiles(text, params)
            if mol is None:
                raise SmilesParseError("invalid_smiles", "RDKit rejected the input")
            source_atom_count = int(mol.GetNumAtoms())
            if source_atom_count < 1:
                raise SmilesParseError(
                    "empty_graph", "SMILES did not produce any atoms"
                )
            if source_atom_count > _MAX_SOURCE_ATOMS:
                raise SmilesParseError(
                    "too_many_source_atoms", "source graph exceeds the fixed atom limit"
                )
            source_identity = _source_identity(mol)
            pre_sanitize_stereo = _capture_pre_sanitize_stereo_state(mol)
            try:
                Chem.SanitizeMol(mol)
                Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
            except SmilesParseError:
                raise
            except Exception:
                raise SmilesParseError(
                    "sanitization_failed", "RDKit sanitization rejected the graph"
                ) from None
            _assert_source_identity_unchanged(mol, source_identity)
            _assert_stereo_markers_retained(mol, pre_sanitize_stereo)
            source_atoms, source_bonds = _extract_source_records(mol)
            try:
                normalized_isomeric = Chem.MolToSmiles(
                    mol,
                    canonical=True,
                    isomericSmiles=True,
                )
            except Exception:
                raise SmilesParseError(
                    "rdkit_adapter_failure",
                    "RDKit could not produce a deterministic normalized identity hash",
                ) from None
            if type(normalized_isomeric) is not str or not normalized_isomeric:
                raise SmilesParseError(
                    "rdkit_adapter_failure",
                    "RDKit returned an invalid normalized identity",
                )
            normalized_isomeric_sha256 = hashlib.sha256(
                normalized_isomeric.encode("utf-8")
            ).hexdigest()
    except SmilesParseError:
        raise
    except Exception:
        raise SmilesParseError(
            "rdkit_adapter_failure", "RDKit failed without a stable parse result"
        ) from None

    atoms, bonds, graph_validation = _make_canonical_topology(
        source_atoms, source_bonds
    )
    if len(graph_validation.components) > _MAX_FRAGMENTS:
        raise SmilesParseError(
            "too_many_fragments", "expanded graph exceeds the fixed fragment limit"
        )

    components = graph_validation.components
    residues = tuple(
        Residue(
            index=index,
            name=f"L{index + 1}",
            chain_index=index,
            sequence_number=1,
            atom_indices=component,
            entity_type="non_polymer",
            hetero=True,
            metadata={"graph_component_index": index},
        )
        for index, component in enumerate(components)
    )
    chains = tuple(
        Chain(
            index=index,
            chain_id=f"L{index + 1}",
            residue_indices=(index,),
            entity_id=f"L{index + 1}",
            metadata={"graph_component_index": index},
        )
        for index in range(len(components))
    )
    topology_sha256 = _ordered_topology_digest(atoms, bonds, components)
    typed_atom_stereo_count = sum(
        atom.stereo.upper() in {"R", "S", "UNKNOWN"} for atom in atoms
    )
    typed_bond_stereo_count = sum(
        bond.stereo.upper() not in {"NONE", "UNSPECIFIED"} for bond in bonds
    )
    blockers = list(_BASE_BLOCKERS)
    if any(atom.aromatic for atom in atoms) or any(bond.aromatic for bond in bonds):
        blockers.append("aromaticity_not_independently_verified")
    if typed_atom_stereo_count or typed_bond_stereo_count:
        blockers.append("cip_assignment_not_independently_verified")
        blockers.append("stereo_geometry_unavailable")
    if len(components) > 1:
        blockers.append("disconnected_fragment_roles_not_assessed")

    coverage = SmilesIngestCoverage(
        rdkit_version=rdkit_version,
        source_atom_count=len(source_atoms),
        expanded_atom_count=len(atoms),
        bond_count=len(bonds),
        fragment_count=len(components),
        generated_hydrogen_count=len(atoms) - len(source_atoms),
        explicit_hydrogen_count=sum(atom.atomic_number == 1 for atom in atoms),
        formal_charge_total=graph_validation.formal_charge_total,
        isotope_count=sum(atom.isotope_mass_number is not None for atom in atoms),
        atom_map_count=sum(atom.atom_map is not None for atom in atoms),
        aromatic_atom_count=sum(atom.aromatic for atom in atoms),
        typed_atom_stereo_count=typed_atom_stereo_count,
        typed_bond_stereo_count=typed_bond_stereo_count,
        ordered_topology_sha256=topology_sha256,
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256="",
        blockers=tuple(blockers),
    )
    system = AllAtomSystem(
        system_id=source_id or f"smiles-{source_sha256[:16]}",
        atoms=atoms,
        bonds=bonds,
        residues=residues,
        chains=chains,
        coordinates=torch.empty((0, len(atoms), 3), dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="smiles",
            source_id=source_id,
            source_sha256=source_sha256,
            parser_name="betelgeuze_strict_smiles",
            parser_version=SMILES_PARSER_VERSION,
            operations=(
                "rdkit_parse_without_sanitization",
                "rdkit_sanitize",
                "manual_bracket_and_implicit_hydrogen_expansion",
                "dependency_free_canonical_graph_revalidation",
            ),
            preparation_ready=False,
            claim_safe=False,
            metadata={
                "rdkit_version": rdkit_version,
                "normalized_isomeric_smiles_sha256": normalized_isomeric_sha256,
                "ordered_topology_sha256": topology_sha256,
                "coverage": coverage.to_dict(),
            },
        ),
        metadata={
            "ordered_topology_sha256": topology_sha256,
            "source_atom_count": len(source_atoms),
            "generated_hydrogen_count": len(atoms) - len(source_atoms),
            "fragment_count": len(components),
        },
    )
    try:
        require_valid_all_atom_system(system)
    except MolecularValidationError:
        raise SmilesParseError(
            "canonical_validation_failed",
            "canonical graph validation failed after adapter conversion",
        ) from None
    common_topology_sha256 = canonical_topology_sha256(system)
    coverage = replace(
        coverage,
        canonical_topology_sha256=common_topology_sha256,
    )
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["coverage"] = coverage.to_dict()
    provenance_metadata["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    provenance_metadata["canonical_topology_sha256"] = common_topology_sha256
    system = replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    system = attach_parser_observation_digest(system)
    return SmilesIngestResult(system=system, coverage=coverage)


__all__ = [
    "SMILES_PARSER_VERSION",
    "SmilesIngestCoverage",
    "SmilesIngestResult",
    "SmilesParseError",
    "parse_smiles",
]
