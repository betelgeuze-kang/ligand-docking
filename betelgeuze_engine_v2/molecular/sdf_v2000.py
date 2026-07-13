"""Strict, dependency-free ingestion for one supported SDF V2000 record.

The parser deliberately implements a narrow, lossless subset.  Any source
feature that cannot be represented in the canonical v2 molecular contract is
rejected instead of being discarded or guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import re
from typing import Any

import torch

from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
    canonical_element_symbol,
)
from .observation import attach_parser_observation_digest
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256
from .validation import MolecularValidationError, require_valid_all_atom_system


SDF_V2000_PARSER_VERSION = "1.5.0"
_MAX_SDF_INPUT_BYTES = 2 * 1024 * 1024
_MAX_SDF_LINE_COUNT = 4_096
_MAX_SDF_LINE_CHARS = 256

_CHARGE_CODE_TO_FORMAL_CHARGE = {
    0: 0,
    1: 3,
    2: 2,
    3: 1,
    5: -1,
    6: -2,
    7: -3,
}
_BOND_TYPE_TO_ORDER = {1: 1.0, 2: 2.0, 3: 3.0, 4: 1.5}
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_COVERAGE_BLOCKERS = (
    "hydrogen_completion_not_assessed",
    "protonation_not_assessed",
    "tautomer_not_assessed",
    "stereochemistry_perception_not_implemented",
    "parameter_coverage_not_assessed",
)


class SdfV2000ParseError(ValueError):
    """A stable fail-closed SDF parse error."""

    def __init__(self, code: str, message: str, *, line_number: int | None = None):
        self.code = str(code)
        self.line_number = None if line_number is None else int(line_number)
        self.detail = str(message)
        location = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"{self.code}{location}: {self.detail}")


@dataclass(frozen=True)
class SdfV2000Coverage:
    atom_count: int
    bond_count: int
    explicit_hydrogen_count: int
    formal_charge_count: int
    isotope_count: int
    aromatic_bond_count: int
    atom_map_count: int
    canonical_topology_schema_id: str = CANONICAL_TOPOLOGY_SCHEMA_ID
    canonical_topology_sha256: str = ""
    blockers: tuple[str, ...] = _COVERAGE_BLOCKERS
    supported: bool = True
    preparation_ready: bool = False
    claim_safe: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "sdf_v2000",
            "parser_version": SDF_V2000_PARSER_VERSION,
            "supported": self.supported,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "explicit_hydrogen_count": self.explicit_hydrogen_count,
            "formal_charge_count": self.formal_charge_count,
            "isotope_count": self.isotope_count,
            "aromatic_bond_count": self.aromatic_bond_count,
            "atom_map_count": self.atom_map_count,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class SdfV2000IngestResult:
    system: AllAtomSystem
    coverage: SdfV2000Coverage


@dataclass(frozen=True)
class _ParsedAtom:
    element: str
    coordinates: tuple[float, float, float]
    formal_charge: int
    atom_map: int


@dataclass(frozen=True)
class _ParsedBond:
    source_atom_i: int
    source_atom_j: int
    bond_type: int


def _parse_fixed_int(
    line: str,
    start: int,
    end: int,
    *,
    code: str,
    line_number: int,
    field: str,
) -> int:
    text = line[start:end].strip()
    if _INTEGER_RE.fullmatch(text) is None:
        raise SdfV2000ParseError(code, f"{field} is not a decimal integer: {text!r}", line_number=line_number)
    try:
        return int(text, 10)
    except ValueError as exc:
        raise SdfV2000ParseError(code, f"{field} is not an integer: {text!r}", line_number=line_number) from exc


def _parse_fixed_float(
    line: str,
    start: int,
    end: int,
    *,
    line_number: int,
    field: str,
) -> float:
    text = line[start:end].strip()
    if _DECIMAL_RE.fullmatch(text) is None:
        raise SdfV2000ParseError(
            "invalid_atom_coordinate",
            f"{field} is not a fixed-point decimal: {text!r}",
            line_number=line_number,
        )
    try:
        value = float(text)
    except ValueError as exc:
        raise SdfV2000ParseError(
            "invalid_atom_coordinate",
            f"{field} is not a floating-point number: {text!r}",
            line_number=line_number,
        ) from exc
    if not math.isfinite(value):
        raise SdfV2000ParseError(
            "nonfinite_atom_coordinate",
            f"{field} must be finite",
            line_number=line_number,
        )
    return value


def _parse_counts_line(line: str, *, line_number: int) -> tuple[int, int]:
    if len(line) < 39 or line[33:39] != " V2000" or line[39:].strip():
        marker = line.rstrip()[-5:] if line.strip() else ""
        if marker == "V3000":
            raise SdfV2000ParseError("unsupported_v3000", "only V2000 is supported", line_number=line_number)
        raise SdfV2000ParseError("invalid_counts_line", "expected a fixed-width V2000 counts line", line_number=line_number)
    atom_count = _parse_fixed_int(
        line, 0, 3, code="invalid_counts_line", line_number=line_number, field="atom_count"
    )
    bond_count = _parse_fixed_int(
        line, 3, 6, code="invalid_counts_line", line_number=line_number, field="bond_count"
    )
    if atom_count < 1 or atom_count > 999:
        raise SdfV2000ParseError("unsupported_atom_count", "atom_count must be in [1, 999]", line_number=line_number)
    if bond_count < 0 or bond_count > 999:
        raise SdfV2000ParseError("unsupported_bond_count", "bond_count must be in [0, 999]", line_number=line_number)
    for start in range(6, 30, 3):
        value = _parse_fixed_int(
            line,
            start,
            start + 3,
            code="invalid_counts_line",
            line_number=line_number,
            field=f"counts_field_{start // 3}",
        )
        if value != 0:
            raise SdfV2000ParseError(
                "unsupported_counts_feature",
                f"counts field at columns {start + 1}-{start + 3} must be zero",
                line_number=line_number,
            )
    if _parse_fixed_int(
        line, 30, 33, code="invalid_counts_line", line_number=line_number, field="property_version"
    ) != 999:
        raise SdfV2000ParseError(
            "unsupported_counts_feature",
            "V2000 property version field must be 999",
            line_number=line_number,
        )
    return atom_count, bond_count


def _parse_atom_line(line: str, *, line_number: int) -> _ParsedAtom:
    if len(line) < 69 or line[69:].strip():
        raise SdfV2000ParseError(
            "invalid_atom_line",
            "atom line must contain exactly the supported 69-column V2000 fields",
            line_number=line_number,
        )
    x = _parse_fixed_float(line, 0, 10, line_number=line_number, field="x")
    y = _parse_fixed_float(line, 10, 20, line_number=line_number, field="y")
    z = _parse_fixed_float(line, 20, 30, line_number=line_number, field="z")
    if line[30:31] != " ":
        raise SdfV2000ParseError("invalid_atom_line", "missing atom-symbol separator", line_number=line_number)
    element = canonical_element_symbol(line[31:34])
    if not element or atomic_number_for_element(element) == 0:
        raise SdfV2000ParseError("unknown_element", f"unknown element {element!r}", line_number=line_number)

    mass_difference = _parse_fixed_int(
        line, 34, 36, code="invalid_atom_line", line_number=line_number, field="mass_difference"
    )
    if mass_difference != 0:
        raise SdfV2000ParseError(
            "unsupported_mass_difference",
            "atom-block mass differences are not supported; use M  ISO",
            line_number=line_number,
        )
    charge_code = _parse_fixed_int(
        line, 36, 39, code="invalid_atom_line", line_number=line_number, field="charge_code"
    )
    if charge_code == 4:
        raise SdfV2000ParseError("unsupported_radical", "radical atom charge code is unsupported", line_number=line_number)
    if charge_code not in _CHARGE_CODE_TO_FORMAL_CHARGE:
        raise SdfV2000ParseError(
            "unsupported_charge_code",
            f"unsupported atom charge code {charge_code}",
            line_number=line_number,
        )
    parity = _parse_fixed_int(
        line, 39, 42, code="invalid_atom_line", line_number=line_number, field="atom_stereo_parity"
    )
    if parity != 0:
        raise SdfV2000ParseError(
            "unsupported_atom_stereo",
            "nonzero V2000 atom stereo parity is not yet supported",
            line_number=line_number,
        )
    for start, field in (
        (42, "hydrogen_count"),
        (45, "stereo_care"),
        (48, "valence"),
        (51, "h0_designator"),
        (54, "unused_1"),
        (57, "unused_2"),
        (63, "inversion_retention"),
        (66, "exact_change"),
    ):
        value = _parse_fixed_int(
            line, start, start + 3, code="invalid_atom_line", line_number=line_number, field=field
        )
        if value != 0:
            raise SdfV2000ParseError(
                "unsupported_atom_feature",
                f"unsupported nonzero {field} field",
                line_number=line_number,
            )
    atom_map = _parse_fixed_int(
        line, 60, 63, code="invalid_atom_line", line_number=line_number, field="atom_map"
    )
    if atom_map < 0 or atom_map > 999:
        raise SdfV2000ParseError("invalid_atom_map", "atom map must be in [0, 999]", line_number=line_number)
    return _ParsedAtom(
        element=element,
        coordinates=(x, y, z),
        formal_charge=_CHARGE_CODE_TO_FORMAL_CHARGE[charge_code],
        atom_map=atom_map,
    )


def _parse_bond_line(line: str, *, line_number: int) -> _ParsedBond:
    content = line.rstrip()
    if len(content) not in {12, 15, 18, 21} or line[21:].strip():
        raise SdfV2000ParseError(
            "invalid_bond_line",
            "bond line must contain only the standard 12-21 fixed-width columns",
            line_number=line_number,
        )
    atom_i = _parse_fixed_int(line, 0, 3, code="invalid_bond_line", line_number=line_number, field="atom_i")
    atom_j = _parse_fixed_int(line, 3, 6, code="invalid_bond_line", line_number=line_number, field="atom_j")
    bond_type = _parse_fixed_int(line, 6, 9, code="invalid_bond_line", line_number=line_number, field="bond_type")
    if bond_type not in _BOND_TYPE_TO_ORDER:
        raise SdfV2000ParseError(
            "unsupported_bond_type",
            f"bond type {bond_type} is query, unspecified, or unsupported",
            line_number=line_number,
        )
    stereo = _parse_fixed_int(line, 9, 12, code="invalid_bond_line", line_number=line_number, field="bond_stereo")
    if stereo != 0:
        raise SdfV2000ParseError(
            "unsupported_bond_stereo",
            "nonzero V2000 bond stereo is not yet supported",
            line_number=line_number,
        )
    tail = content[12:]
    if tail:
        for offset in range(0, len(tail), 3):
            text = tail[offset : offset + 3].strip()
            if _INTEGER_RE.fullmatch(text) is None:
                raise SdfV2000ParseError(
                    "invalid_bond_line", "bond tail contains a non-integer field", line_number=line_number
                )
            value = int(text, 10)
            if value != 0:
                raise SdfV2000ParseError(
                    "unsupported_bond_feature",
                    "bond topology/reaction fields must be zero",
                    line_number=line_number,
                )
    return _ParsedBond(source_atom_i=atom_i, source_atom_j=atom_j, bond_type=bond_type)


def _parse_property_pairs(
    line: str,
    *,
    line_number: int,
    property_name: str,
) -> tuple[tuple[int, int], ...]:
    tokens = line.split()
    if len(tokens) < 3 or tokens[0] != "M" or tokens[1] != property_name:
        raise SdfV2000ParseError("invalid_property_line", "invalid property record", line_number=line_number)
    if _INTEGER_RE.fullmatch(tokens[2]) is None:
        raise SdfV2000ParseError("invalid_property_line", "property pair count is invalid", line_number=line_number)
    count_digits = tokens[2].lstrip("+-").lstrip("0") or "0"
    if len(count_digits) > 1:
        raise SdfV2000ParseError(
            "invalid_property_line",
            "property pair count is outside the supported range",
            line_number=line_number,
        )
    count_magnitude = int(count_digits, 10)
    count = -count_magnitude if tokens[2].startswith("-") else count_magnitude
    if count < 1 or count > 8 or len(tokens) != 3 + 2 * count:
        raise SdfV2000ParseError(
            "invalid_property_line",
            "property record must contain 1-8 complete atom/value pairs",
            line_number=line_number,
        )
    pairs: list[tuple[int, int]] = []
    for offset in range(count):
        atom_token = tokens[3 + 2 * offset]
        value_token = tokens[4 + 2 * offset]
        if _INTEGER_RE.fullmatch(atom_token) is None or _INTEGER_RE.fullmatch(value_token) is None:
            raise SdfV2000ParseError(
                "invalid_property_line", "property atom/value pair is invalid", line_number=line_number
            )
        atom_digits = atom_token.lstrip("+-").lstrip("0") or "0"
        value_digits = value_token.lstrip("+-").lstrip("0") or "0"
        if len(atom_digits) > 3 or len(value_digits) > 4:
            raise SdfV2000ParseError(
                "invalid_property_line",
                "property atom/value pair is outside the supported range",
                line_number=line_number,
            )
        atom_magnitude = int(atom_digits, 10)
        value_magnitude = int(value_digits, 10)
        atom_index = (
            -atom_magnitude if atom_token.startswith("-") else atom_magnitude
        )
        value = -value_magnitude if value_token.startswith("-") else value_magnitude
        pairs.append((atom_index, value))
    return tuple(pairs)


def parse_sdf_v2000(data: bytes, *, source_id: str = "") -> SdfV2000IngestResult:
    """Parse one strict SDF V2000 record into a canonical all-atom system."""

    if type(data) is not bytes:
        raise TypeError("SDF V2000 input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if not data:
        raise SdfV2000ParseError("empty_input", "SDF input is empty")
    if len(data) > _MAX_SDF_INPUT_BYTES:
        raise SdfV2000ParseError(
            "input_too_large",
            f"SDF input exceeds the {_MAX_SDF_INPUT_BYTES}-byte safety limit",
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SdfV2000ParseError("invalid_ascii", "fixed-width SDF V2000 input must be ASCII") from exc
    if "\x00" in text:
        raise SdfV2000ParseError("invalid_text", "NUL bytes are not allowed")
    lines = text.splitlines()
    if len(lines) > _MAX_SDF_LINE_COUNT:
        raise SdfV2000ParseError(
            "too_many_lines",
            f"SDF input exceeds the {_MAX_SDF_LINE_COUNT}-line safety limit",
        )
    oversized_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if len(line) > _MAX_SDF_LINE_CHARS
        ),
        None,
    )
    if oversized_line is not None:
        raise SdfV2000ParseError(
            "line_too_long",
            f"SDF lines may contain at most {_MAX_SDF_LINE_CHARS} characters",
            line_number=oversized_line,
        )
    if len(lines) < 5:
        raise SdfV2000ParseError("truncated_record", "SDF record is missing required lines")

    title, program, comment = lines[0], lines[1], lines[2]
    atom_count, bond_count = _parse_counts_line(lines[3], line_number=4)
    required_end = 4 + atom_count + bond_count
    if len(lines) < required_end:
        raise SdfV2000ParseError("truncated_record", "atom or bond block is truncated")
    if len(lines) == required_end:
        raise SdfV2000ParseError("missing_m_end", "M  END record is required")

    parsed_atoms = [
        _parse_atom_line(lines[4 + index], line_number=5 + index)
        for index in range(atom_count)
    ]
    atom_maps: set[int] = set()
    for index, parsed_atom in enumerate(parsed_atoms):
        if parsed_atom.atom_map == 0:
            continue
        if parsed_atom.atom_map in atom_maps:
            raise SdfV2000ParseError(
                "duplicate_atom_map",
                f"nonzero atom map {parsed_atom.atom_map} is assigned more than once",
                line_number=5 + index,
            )
        atom_maps.add(parsed_atom.atom_map)
    parsed_bonds = [
        _parse_bond_line(lines[4 + atom_count + index], line_number=5 + atom_count + index)
        for index in range(bond_count)
    ]

    charges = [atom.formal_charge for atom in parsed_atoms]
    isotopes: list[int | None] = [None] * atom_count
    charge_property_atoms: set[int] = set()
    isotope_property_atoms: set[int] = set()
    m_chg_seen = False
    cursor = required_end
    while cursor < len(lines):
        line = lines[cursor]
        line_number = cursor + 1
        if line.strip() == "M  END":
            cursor += 1
            break
        if line.startswith("M  CHG"):
            pairs = _parse_property_pairs(line, line_number=line_number, property_name="CHG")
            if not m_chg_seen:
                if any(charge != 0 for charge in charges):
                    raise SdfV2000ParseError(
                        "conflicting_charge_sources",
                        "M  CHG cannot be mixed with atom-block charge codes",
                        line_number=line_number,
                    )
                m_chg_seen = True
            for source_atom_index, charge in pairs:
                atom_index = source_atom_index - 1
                if atom_index < 0 or atom_index >= atom_count:
                    raise SdfV2000ParseError(
                        "property_atom_out_of_range", "M  CHG atom index is out of range", line_number=line_number
                    )
                if atom_index in charge_property_atoms or charges[atom_index] != 0:
                    raise SdfV2000ParseError(
                        "conflicting_charge_sources",
                        "formal charge is duplicated or conflicts with the atom block",
                        line_number=line_number,
                    )
                if charge == 0 or charge < -15 or charge > 15:
                    raise SdfV2000ParseError(
                        "unsupported_formal_charge", "M  CHG value must be a nonzero integer in [-15, 15]", line_number=line_number
                    )
                charge_property_atoms.add(atom_index)
                charges[atom_index] = charge
        elif line.startswith("M  ISO"):
            pairs = _parse_property_pairs(line, line_number=line_number, property_name="ISO")
            for source_atom_index, mass_number in pairs:
                atom_index = source_atom_index - 1
                if atom_index < 0 or atom_index >= atom_count:
                    raise SdfV2000ParseError(
                        "property_atom_out_of_range", "M  ISO atom index is out of range", line_number=line_number
                    )
                if atom_index in isotope_property_atoms:
                    raise SdfV2000ParseError(
                        "duplicate_isotope_property", "isotope is assigned more than once", line_number=line_number
                    )
                atomic_number = atomic_number_for_element(parsed_atoms[atom_index].element)
                if mass_number < atomic_number or mass_number > 350:
                    raise SdfV2000ParseError(
                        "invalid_isotope_mass_number", "M  ISO mass number is outside the supported range", line_number=line_number
                    )
                isotope_property_atoms.add(atom_index)
                isotopes[atom_index] = mass_number
        elif line.startswith("M  "):
            record_name = line[3:6].strip() or "unknown"
            raise SdfV2000ParseError(
                "unsupported_property_record",
                f"M  {record_name} is not supported",
                line_number=line_number,
            )
        else:
            raise SdfV2000ParseError(
                "unexpected_record_line",
                "only M  CHG, M  ISO, and M  END may follow the bond block",
                line_number=line_number,
            )
        cursor += 1
    else:
        raise SdfV2000ParseError("missing_m_end", "M  END record is required")

    delimiter_seen = False
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        line_number = cursor + 1
        if not stripped:
            cursor += 1
            continue
        if stripped == "$$$$" and not delimiter_seen:
            delimiter_seen = True
            cursor += 1
            continue
        if delimiter_seen:
            raise SdfV2000ParseError(
                "multiple_records", "content after the first SDF delimiter is not allowed", line_number=line_number
            )
        raise SdfV2000ParseError(
            "unsupported_data_fields",
            "SDF property data fields are not supported by this parser version",
            line_number=line_number,
        )

    bond_pairs: set[tuple[int, int]] = set()
    aromatic_atoms: set[int] = set()
    bonds: list[Bond] = []
    normalized_endpoints = False
    for index, parsed in enumerate(parsed_bonds):
        source_i = parsed.source_atom_i - 1
        source_j = parsed.source_atom_j - 1
        if source_i < 0 or source_i >= atom_count or source_j < 0 or source_j >= atom_count:
            raise SdfV2000ParseError("bond_atom_out_of_range", "bond atom index is out of range")
        if source_i == source_j:
            raise SdfV2000ParseError("self_bond", "self-bonds are not supported")
        atom_i, atom_j = sorted((source_i, source_j))
        normalized_endpoints = normalized_endpoints or (atom_i != source_i)
        pair = (atom_i, atom_j)
        if pair in bond_pairs:
            raise SdfV2000ParseError("duplicate_bond", f"duplicate bond {pair}")
        bond_pairs.add(pair)
        aromatic = parsed.bond_type == 4
        if aromatic:
            aromatic_atoms.update(pair)
        bonds.append(
            Bond(
                index=index,
                atom_i=atom_i,
                atom_j=atom_j,
                order=_BOND_TYPE_TO_ORDER[parsed.bond_type],
                aromatic=aromatic,
                source="sdf_v2000",
                metadata={
                    "sdf_source_bond_index": index + 1,
                    "sdf_source_atom_i": parsed.source_atom_i,
                    "sdf_source_atom_j": parsed.source_atom_j,
                    "sdf_bond_type": parsed.bond_type,
                },
            )
        )

    atoms = tuple(
        Atom(
            index=index,
            name=f"{parsed.element}{index + 1}",
            element=parsed.element,
            atomic_number=atomic_number_for_element(parsed.element),
            residue_index=0,
            formal_charge=charges[index],
            isotope_mass_number=isotopes[index],
            serial=index + 1,
            atom_map=None if parsed.atom_map == 0 else parsed.atom_map,
            aromatic=index in aromatic_atoms,
            metadata={
                "sdf_source_atom_index": index + 1,
                "sdf_atom_map": parsed.atom_map,
                "hydrogen_origin": (
                    "source" if parsed.element == "H" else "not_hydrogen"
                ),
                "formal_charge_source": (
                    "sdf_v2000_m_chg"
                    if index in charge_property_atoms
                    else "sdf_v2000_atom_block"
                ),
            },
        )
        for index, parsed in enumerate(parsed_atoms)
    )
    coordinates = torch.tensor(
        [[parsed.coordinates for parsed in parsed_atoms]],
        dtype=torch.float64,
    )
    coverage = SdfV2000Coverage(
        atom_count=atom_count,
        bond_count=bond_count,
        explicit_hydrogen_count=sum(atom.element == "H" for atom in atoms),
        formal_charge_count=sum(atom.formal_charge != 0 for atom in atoms),
        isotope_count=sum(atom.isotope_mass_number is not None for atom in atoms),
        aromatic_bond_count=sum(bond.aromatic for bond in bonds),
        atom_map_count=sum(parsed.atom_map != 0 for parsed in parsed_atoms),
    )
    source_sha256 = hashlib.sha256(data).hexdigest()
    operations = [
        "parse_strict_sdf_v2000_single_record",
        "preserve_source_atom_order",
        "synthesize_atom_names",
        "synthesize_single_ligand_residue_and_chain",
    ]
    if normalized_endpoints:
        operations.append("canonicalize_bond_endpoint_order")
    system_id = source_id.strip() or title.strip() or f"sdf-{source_sha256[:16]}"
    system = AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(atom_count)),
                entity_type="non_polymer",
                hetero=True,
                metadata={"source": "sdf_v2000_single_record"},
            ),
        ),
        chains=(
            Chain(
                index=0,
                chain_id="L",
                residue_indices=(0,),
                entity_id="ligand",
                metadata={"source": "sdf_v2000_single_record"},
            ),
        ),
        coordinates=coordinates,
        provenance=StructureProvenance(
            source_format="sdf_v2000",
            source_id=source_id,
            source_sha256=source_sha256,
            parser_name="betelgeuze_engine_v2.molecular.sdf_v2000",
            parser_version=SDF_V2000_PARSER_VERSION,
            operations=tuple(operations),
            preparation_ready=False,
            claim_safe=False,
            metadata={"coverage": coverage.to_dict()},
        ),
        metadata={
            "sdf_v2000_header": {
                "title": title,
                "program": program,
                "comment": comment,
            }
        },
    )
    try:
        require_valid_all_atom_system(system)
    except MolecularValidationError as exc:
        raise SdfV2000ParseError("canonical_validation_failed", str(exc)) from exc
    topology_sha256 = canonical_topology_sha256(system)
    coverage = replace(coverage, canonical_topology_sha256=topology_sha256)
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["coverage"] = coverage.to_dict()
    provenance_metadata["canonical_topology_schema_id"] = (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    provenance_metadata["canonical_topology_sha256"] = topology_sha256
    system = replace(
        system,
        provenance=replace(system.provenance, metadata=provenance_metadata),
    )
    system = attach_parser_observation_digest(system)
    return SdfV2000IngestResult(system=system, coverage=coverage)
