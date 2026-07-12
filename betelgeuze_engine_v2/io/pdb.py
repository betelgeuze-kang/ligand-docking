"""Bounded single-model PDB parser for the Engine v2 canonical state.

This parser deliberately supports a narrow, auditable subset. It does not infer
missing elements, bonds, hydrogens, protonation, alternate conformers, or
chemistry validation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from typing import Any

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    require_valid_all_atom_system,
)


PDB_PARSER_NAME = "betelgeuze_engine_v2.strict_pdb"
PDB_PARSER_VERSION = "1.0.0"


class PDBParseError(ValueError):
    """Input is outside the supported strict PDB subset."""


@dataclass(frozen=True)
class PDBParserLimits:
    max_bytes: int = 8 * 1024 * 1024
    max_lines: int = 200_000
    max_atoms: int = 100_000
    max_bonds: int = 400_000

    def __post_init__(self) -> None:
        if min(self.max_bytes, self.max_lines, self.max_atoms, self.max_bonds) < 1:
            raise ValueError("all PDB parser limits must be positive")


_ALLOWED_IGNORED_RECORDS = {
    "",
    "HEADER",
    "TITLE",
    "COMPND",
    "SOURCE",
    "KEYWDS",
    "EXPDTA",
    "AUTHOR",
    "REVDAT",
    "JRNL",
    "REMARK",
    "SEQRES",
    "DBREF",
    "DBREF1",
    "DBREF2",
    "HELIX",
    "SHEET",
    "SSBOND",
    "LINK",
    "CISPEP",
    "SITE",
    "HET",
    "HETNAM",
    "HETSYN",
    "FORMUL",
    "MODRES",
    "TER",
    "MASTER",
    "END",
}


def _source_bytes(source: str | bytes, limits: PDBParserLimits) -> tuple[bytes, str]:
    if isinstance(source, str):
        raw = source.encode("utf-8")
    elif isinstance(source, bytes):
        raw = source
    else:
        raise TypeError("PDB source must be str or bytes")
    if len(raw) > limits.max_bytes:
        raise PDBParseError("PDB input exceeds max_bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PDBParseError("PDB input must be UTF-8 text") from exc
    return raw, text


def _float_field(line: str, start: int, end: int, *, name: str, optional: bool = False) -> float | None:
    text = line[start:end].strip()
    if not text and optional:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise PDBParseError(f"invalid {name}: {text!r}") from exc
    if not math.isfinite(value):
        raise PDBParseError(f"non-finite {name}")
    return value


def _int_field(line: str, start: int, end: int, *, name: str) -> int:
    text = line[start:end].strip()
    try:
        return int(text)
    except ValueError as exc:
        raise PDBParseError(f"invalid {name}: {text!r}") from exc


def _formal_charge(text: str) -> int:
    value = text.strip()
    if not value:
        return 0
    if len(value) != 2 or value[0] not in "123456789" or value[1] not in "+-":
        raise PDBParseError(f"unsupported PDB formal charge {value!r}")
    magnitude = int(value[0])
    return magnitude if value[1] == "+" else -magnitude


def parse_pdb(
    source: str | bytes,
    *,
    source_id: str = "",
    limits: PDBParserLimits | None = None,
    dtype: torch.dtype = torch.float64,
    device: torch.device | str = "cpu",
) -> AllAtomSystem:
    """Parse one explicit PDB coordinate model without chemistry inference."""

    parser_limits = limits or PDBParserLimits()
    raw, text = _source_bytes(source, parser_limits)
    lines = text.splitlines()
    if len(lines) > parser_limits.max_lines:
        raise PDBParseError("PDB input exceeds max_lines")
    if dtype not in (torch.float32, torch.float64):
        raise TypeError("strict PDB parser supports float32 or float64 coordinates")

    atoms: list[Atom] = []
    coordinates: list[tuple[float, float, float]] = []
    serial_to_index: dict[int, int] = {}
    chain_order: list[str] = []
    chain_residue_indices: dict[str, list[int]] = {}
    residue_keys: dict[tuple[str, int, str, str, str], int] = {}
    residue_rows: list[dict[str, Any]] = []
    conect_serial_pairs: set[tuple[int, int]] = set()
    ignored = Counter()
    model_count = 0
    atom_records_started = False
    atom_records_ended = False
    cell: UnitCell | None = None

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n").ljust(80)
        record = line[0:6].strip().upper()

        if record == "MODEL":
            model_count += 1
            if model_count > 1:
                raise PDBParseError("multiple PDB MODEL blocks are not supported")
            if atom_records_started:
                raise PDBParseError("MODEL record must precede coordinates")
            continue
        if record == "ENDMDL":
            atom_records_ended = True
            continue
        if record in {"ATOM", "HETATM"}:
            if atom_records_ended:
                raise PDBParseError("coordinates after ENDMDL are not supported")
            atom_records_started = True
            if len(atoms) >= parser_limits.max_atoms:
                raise PDBParseError("PDB atom count exceeds max_atoms")
            serial = _int_field(line, 6, 11, name="atom serial")
            if serial < 1 or serial in serial_to_index:
                raise PDBParseError("PDB atom serials must be unique positive integers")
            atom_name = line[12:16].strip()
            altloc = line[16:17].strip()
            if altloc:
                raise PDBParseError("alternate locations are not supported; resolve altloc before parsing")
            residue_name = line[17:20].strip().upper()
            chain_id = line[21:22].strip()
            sequence_number = _int_field(line, 22, 26, name="residue sequence number")
            insertion_code = line[26:27].strip()
            element = line[76:78].strip()
            atomic_number = atomic_number_for_element(element)
            if not atom_name or not residue_name:
                raise PDBParseError("atom and residue names are required")
            if atomic_number == 0:
                raise PDBParseError(
                    "PDB element columns 77-78 must contain a supported explicit element"
                )
            x = _float_field(line, 30, 38, name="x coordinate")
            y = _float_field(line, 38, 46, name="y coordinate")
            z = _float_field(line, 46, 54, name="z coordinate")
            occupancy = _float_field(line, 54, 60, name="occupancy", optional=True)
            b_factor = _float_field(line, 60, 66, name="B-factor", optional=True)
            assert x is not None and y is not None and z is not None
            entity_type = "polymer" if record == "ATOM" else "non_polymer"
            residue_key = (chain_id, sequence_number, insertion_code, residue_name, entity_type)
            if residue_key not in residue_keys:
                residue_index = len(residue_rows)
                residue_keys[residue_key] = residue_index
                residue_rows.append(
                    {
                        "name": residue_name,
                        "chain_id": chain_id,
                        "sequence_number": sequence_number,
                        "insertion_code": insertion_code,
                        "entity_type": entity_type,
                        "hetero": record == "HETATM",
                        "atom_indices": [],
                    }
                )
                if chain_id not in chain_residue_indices:
                    chain_order.append(chain_id)
                    chain_residue_indices[chain_id] = []
                chain_residue_indices[chain_id].append(residue_index)
            residue_index = residue_keys[residue_key]
            atom_index = len(atoms)
            residue_rows[residue_index]["atom_indices"].append(atom_index)
            serial_to_index[serial] = atom_index
            atoms.append(
                Atom(
                    index=atom_index,
                    name=atom_name,
                    element=element,
                    atomic_number=atomic_number,
                    residue_index=residue_index,
                    formal_charge=_formal_charge(line[78:80]),
                    serial=serial,
                    altloc="",
                    occupancy=occupancy,
                    b_factor=b_factor,
                    metadata={"pdb_record": record, "source_line": line_number},
                )
            )
            coordinates.append((x, y, z))
            continue

        if record == "CONECT":
            fields = raw_line[6:].split()
            if not fields:
                raise PDBParseError("empty CONECT record")
            try:
                center = int(fields[0])
                targets = [int(value) for value in fields[1:]]
            except ValueError as exc:
                raise PDBParseError("CONECT records must contain integer serials") from exc
            for target in targets:
                if center == target:
                    raise PDBParseError("self CONECT records are not supported")
                conect_serial_pairs.add(tuple(sorted((center, target))))
                if len(conect_serial_pairs) > parser_limits.max_bonds:
                    raise PDBParseError("PDB bond count exceeds max_bonds")
            continue

        if record == "CRYST1":
            if cell is not None:
                raise PDBParseError("multiple CRYST1 records are not supported")
            a = _float_field(line, 6, 15, name="cell a")
            b = _float_field(line, 15, 24, name="cell b")
            c = _float_field(line, 24, 33, name="cell c")
            alpha = _float_field(line, 33, 40, name="cell alpha")
            beta = _float_field(line, 40, 47, name="cell beta")
            gamma = _float_field(line, 47, 54, name="cell gamma")
            assert None not in (a, b, c, alpha, beta, gamma)
            if not all(abs(float(angle) - 90.0) <= 1e-3 for angle in (alpha, beta, gamma)):
                raise PDBParseError("strict PDB parser supports orthorhombic CRYST1 cells only")
            cell = UnitCell.orthorhombic(
                (float(a), float(b), float(c)),
                dtype=dtype,
                device=device,
            )
            continue

        if record in _ALLOWED_IGNORED_RECORDS:
            ignored[record or "BLANK"] += 1
            continue
        raise PDBParseError(f"unsupported PDB record {record!r} at line {line_number}")

    if not atoms:
        raise PDBParseError("PDB input contains no ATOM/HETATM records")

    bonds: list[Bond] = []
    for serial_i, serial_j in sorted(conect_serial_pairs):
        if serial_i not in serial_to_index or serial_j not in serial_to_index:
            raise PDBParseError("CONECT references an atom serial outside the parsed model")
        atom_i, atom_j = sorted((serial_to_index[serial_i], serial_to_index[serial_j]))
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=atom_i,
                atom_j=atom_j,
                order=1.0,
                source="pdb_conect",
            )
        )

    chain_index_by_id = {chain_id: index for index, chain_id in enumerate(chain_order)}
    residues = tuple(
        Residue(
            index=index,
            name=row["name"],
            chain_index=chain_index_by_id[row["chain_id"]],
            sequence_number=row["sequence_number"],
            atom_indices=tuple(row["atom_indices"]),
            insertion_code=row["insertion_code"],
            entity_type=row["entity_type"],
            hetero=row["hetero"],
        )
        for index, row in enumerate(residue_rows)
    )
    chains = tuple(
        Chain(
            index=chain_index_by_id[chain_id],
            chain_id=chain_id,
            residue_indices=tuple(chain_residue_indices[chain_id]),
        )
        for chain_id in chain_order
    )
    source_sha256 = hashlib.sha256(raw).hexdigest()
    system = AllAtomSystem(
        system_id=str(source_id or f"pdb-{source_sha256[:12]}"),
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        residues=residues,
        chains=chains,
        coordinates=torch.tensor([coordinates], dtype=dtype, device=device),
        provenance=StructureProvenance(
            source_format="pdb",
            source_id=str(source_id),
            source_sha256=source_sha256,
            parser_name=PDB_PARSER_NAME,
            parser_version=PDB_PARSER_VERSION,
            operations=("strict_pdb_parse",),
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            metadata={
                "atom_count": len(atoms),
                "bond_count": len(bonds),
                "ignored_record_counts": dict(sorted(ignored.items())),
                "limitations": [
                    "single_model_only",
                    "alternate_locations_rejected",
                    "elements_must_be_explicit",
                    "no_bond_inference",
                    "no_hydrogen_or_protonation_inference",
                ],
            },
        ),
        cell=cell,
        metadata={"parser_claim_grade": "bounded_strict_ingest_only"},
    )
    require_valid_all_atom_system(system)
    return system


__all__ = [
    "PDB_PARSER_NAME",
    "PDB_PARSER_VERSION",
    "PDBParseError",
    "PDBParserLimits",
    "parse_pdb",
]
