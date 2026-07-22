"""Bounded single-molecule SDF V2000 parser for Engine v2.

The parser accepts explicit atom and bond tables plus ``M  CHG`` and ``M  ISO``.
It does not perform aromaticity perception, tautomerization, protonation, bond
inference, sanitization, or multi-record ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
    require_valid_all_atom_system,
)


SDF_PARSER_NAME = "betelgeuze_engine_v2.strict_sdf_v2000"
SDF_PARSER_VERSION = "1.0.0"


class SDFParseError(ValueError):
    """Input is outside the supported strict single-molecule SDF subset."""


@dataclass(frozen=True)
class SDFParserLimits:
    max_bytes: int = 4 * 1024 * 1024
    max_lines: int = 100_000
    max_atoms: int = 20_000
    max_bonds: int = 80_000

    def __post_init__(self) -> None:
        if min(self.max_bytes, self.max_lines, self.max_atoms, self.max_bonds) < 1:
            raise ValueError("all SDF parser limits must be positive")


_CHARGE_CODE = {0: 0, 1: 3, 2: 2, 3: 1, 5: -1, 6: -2, 7: -3}
_BOND_STEREO = {0: "none", 1: "up", 4: "either", 6: "down"}


def _source_bytes(source: str | bytes, limits: SDFParserLimits) -> tuple[bytes, list[str]]:
    if isinstance(source, str):
        raw = source.encode("utf-8")
    elif isinstance(source, bytes):
        raw = source
    else:
        raise TypeError("SDF source must be str or bytes")
    if len(raw) > limits.max_bytes:
        raise SDFParseError("SDF input exceeds max_bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SDFParseError("SDF input must be UTF-8 text") from exc
    lines = text.splitlines()
    if len(lines) > limits.max_lines:
        raise SDFParseError("SDF input exceeds max_lines")
    delimiters = [index for index, line in enumerate(lines) if line.strip() == "$$$$"]
    if len(delimiters) > 1:
        raise SDFParseError("multiple SDF molecule records are not supported")
    if delimiters:
        first = delimiters[0]
        if any(line.strip() for line in lines[first + 1 :]):
            raise SDFParseError("content after the first SDF record is not supported")
        lines = lines[:first]
    return raw, lines


def _parse_int(text: str, *, name: str) -> int:
    try:
        return int(text.strip())
    except ValueError as exc:
        raise SDFParseError(f"invalid {name}: {text!r}") from exc


def _parse_float(text: str, *, name: str) -> float:
    try:
        value = float(text.strip())
    except ValueError as exc:
        raise SDFParseError(f"invalid {name}: {text!r}") from exc
    if not math.isfinite(value):
        raise SDFParseError(f"non-finite {name}")
    return value


def _apply_m_pairs(
    line: str,
    *,
    label: str,
    atom_count: int,
    target: dict[int, int],
) -> None:
    fields = line.split()
    if len(fields) < 3 or fields[0] != "M" or fields[1] != label:
        raise SDFParseError(f"invalid M  {label} record")
    count = _parse_int(fields[2], name=f"M {label} count")
    expected = 3 + 2 * count
    if count < 0 or len(fields) != expected:
        raise SDFParseError(f"M  {label} pair count does not match the record")
    for offset in range(count):
        atom_number = _parse_int(fields[3 + 2 * offset], name=f"M {label} atom")
        value = _parse_int(fields[4 + 2 * offset], name=f"M {label} value")
        atom_index = atom_number - 1
        if atom_index < 0 or atom_index >= atom_count:
            raise SDFParseError(f"M  {label} references an unknown atom")
        if atom_index in target:
            raise SDFParseError(f"duplicate M  {label} assignment for atom {atom_number}")
        target[atom_index] = value


def parse_sdf_v2000(
    source: str | bytes,
    *,
    source_id: str = "",
    limits: SDFParserLimits | None = None,
    dtype: torch.dtype = torch.float64,
    device: torch.device | str = "cpu",
) -> AllAtomSystem:
    parser_limits = limits or SDFParserLimits()
    raw, lines = _source_bytes(source, parser_limits)
    if dtype not in (torch.float32, torch.float64):
        raise TypeError("strict SDF parser supports float32 or float64 coordinates")
    if len(lines) < 5:
        raise SDFParseError("SDF V2000 record is incomplete")

    title = lines[0].strip()
    counts = lines[3].ljust(39)
    if "V3000" in counts:
        raise SDFParseError("SDF V3000 is not supported by this bounded parser")
    if "V2000" not in counts:
        raise SDFParseError("SDF counts line must declare V2000")
    atom_count = _parse_int(counts[0:3], name="atom count")
    bond_count = _parse_int(counts[3:6], name="bond count")
    if atom_count < 1 or atom_count > parser_limits.max_atoms:
        raise SDFParseError("SDF atom count is outside the configured bound")
    if bond_count < 0 or bond_count > parser_limits.max_bonds:
        raise SDFParseError("SDF bond count is outside the configured bound")
    block_end = 4 + atom_count + bond_count
    if len(lines) <= block_end:
        raise SDFParseError("SDF record is truncated before M  END")

    atoms: list[Atom] = []
    coordinates: list[tuple[float, float, float]] = []
    for atom_index in range(atom_count):
        line_number = 5 + atom_index
        line = lines[4 + atom_index].ljust(69)
        x = _parse_float(line[0:10], name="x coordinate")
        y = _parse_float(line[10:20], name="y coordinate")
        z = _parse_float(line[20:30], name="z coordinate")
        element = line[31:34].strip()
        atomic_number = atomic_number_for_element(element)
        if atomic_number == 0:
            raise SDFParseError(f"unsupported or missing element {element!r}")
        mass_difference = _parse_int(line[34:36] or "0", name="mass difference")
        if mass_difference != 0:
            raise SDFParseError("atom-line mass differences are unsupported; use M  ISO")
        charge_code = _parse_int(line[36:39] or "0", name="charge code")
        if charge_code not in _CHARGE_CODE:
            raise SDFParseError(f"unsupported atom charge code {charge_code}")
        atoms.append(
            Atom(
                index=atom_index,
                name=f"{element}{atom_index + 1}",
                element=element,
                atomic_number=atomic_number,
                residue_index=0,
                formal_charge=_CHARGE_CODE[charge_code],
                metadata={"source_line": line_number},
            )
        )
        coordinates.append((x, y, z))

    bonds: list[Bond] = []
    seen_pairs: set[tuple[int, int]] = set()
    for bond_offset in range(bond_count):
        line = lines[4 + atom_count + bond_offset].ljust(12)
        first = _parse_int(line[0:3], name="bond atom 1") - 1
        second = _parse_int(line[3:6], name="bond atom 2") - 1
        bond_type = _parse_int(line[6:9], name="bond type")
        stereo_code = _parse_int(line[9:12] or "0", name="bond stereo")
        if first < 0 or second < 0 or first >= atom_count or second >= atom_count:
            raise SDFParseError("bond references an unknown atom")
        if first == second:
            raise SDFParseError("self bonds are not supported")
        atom_i, atom_j = sorted((first, second))
        pair = (atom_i, atom_j)
        if pair in seen_pairs:
            raise SDFParseError("duplicate bond endpoints are not supported")
        seen_pairs.add(pair)
        if bond_type not in {1, 2, 3, 4}:
            raise SDFParseError(f"unsupported V2000 bond type {bond_type}")
        if stereo_code not in _BOND_STEREO:
            raise SDFParseError(f"unsupported V2000 bond stereo code {stereo_code}")
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=atom_i,
                atom_j=atom_j,
                order=1.5 if bond_type == 4 else float(bond_type),
                aromatic=bond_type == 4,
                stereo=_BOND_STEREO[stereo_code],
                source="sdf_v2000_bond_table",
                metadata={
                    "v2000_source_atom_i": first,
                    "v2000_source_atom_j": second,
                    "v2000_bond_type": bond_type,
                    "v2000_stereo_code": stereo_code,
                },
            )
        )

    charge_overrides: dict[int, int] = {}
    isotope_overrides: dict[int, int] = {}
    end_seen = False
    for line in lines[block_end:]:
        stripped = line.rstrip()
        if stripped == "M  END":
            if end_seen:
                raise SDFParseError("duplicate M  END record")
            end_seen = True
            continue
        if not end_seen:
            if stripped.startswith("M  CHG"):
                _apply_m_pairs(
                    stripped,
                    label="CHG",
                    atom_count=atom_count,
                    target=charge_overrides,
                )
                continue
            if stripped.startswith("M  ISO"):
                _apply_m_pairs(
                    stripped,
                    label="ISO",
                    atom_count=atom_count,
                    target=isotope_overrides,
                )
                continue
            if not stripped:
                continue
            raise SDFParseError(f"unsupported SDF property record before M  END: {stripped!r}")
        if stripped:
            raise SDFParseError("SDF data fields after M  END are outside this bounded parser")
    if not end_seen:
        raise SDFParseError("SDF record must contain M  END")

    for atom_index, formal_charge in charge_overrides.items():
        atoms[atom_index] = replace(atoms[atom_index], formal_charge=formal_charge)
    for atom_index, isotope in isotope_overrides.items():
        if isotope < atoms[atom_index].atomic_number or isotope > 350:
            raise SDFParseError("M  ISO mass number is outside the supported range")
        atoms[atom_index] = replace(atoms[atom_index], isotope_mass_number=isotope)

    source_sha256 = hashlib.sha256(raw).hexdigest()
    system = AllAtomSystem(
        system_id=str(source_id or title or f"sdf-{source_sha256[:12]}"),
        atoms=tuple(atoms),
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
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=dtype, device=device),
        provenance=StructureProvenance(
            source_format="sdf_v2000",
            source_id=str(source_id or title),
            source_sha256=source_sha256,
            parser_name=SDF_PARSER_NAME,
            parser_version=SDF_PARSER_VERSION,
            operations=("strict_sdf_v2000_parse",),
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            metadata={
                "atom_count": atom_count,
                "bond_count": bond_count,
                "formal_charge_override_count": len(charge_overrides),
                "isotope_override_count": len(isotope_overrides),
                "limitations": [
                    "single_molecule_only",
                    "v2000_only",
                    "no_aromaticity_perception",
                    "no_sanitization_or_protonation",
                    "no_data_fields_after_m_end",
                ],
            },
        ),
        metadata={"parser_claim_grade": "bounded_strict_ingest_only"},
    )
    require_valid_all_atom_system(system)
    return system


__all__ = [
    "SDF_PARSER_NAME",
    "SDF_PARSER_VERSION",
    "SDFParseError",
    "SDFParserLimits",
    "parse_sdf_v2000",
]
