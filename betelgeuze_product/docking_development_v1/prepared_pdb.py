"""Opt-in fixed-width PDB connectivity, delegating coordinates to the sealed engine.

The engine reader remains byte-for-byte unchanged. This product-owned parser
binds original input bytes and owns only the corrected CONECT interpretation.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib

import torch

from betelgeuze_engine_v2.io import (
    PDBParseError,
    PDBParserLimits,
    parse_pdb as _legacy_parse_pdb,
)
from betelgeuze_engine_v2.io.pdb import _source_bytes
from betelgeuze_engine_v2.molecular import Bond, require_valid_all_atom_system

PDB_PARSER_NAME = "betelgeuze_product_fixedwidth_pdb"
PDB_PARSER_VERSION = "1.0.0"


def parse_pdb(
    source: str | bytes,
    *,
    source_id: str = "",
    limits: PDBParserLimits | None = None,
    dtype=torch.float64,
    device="cpu",
    connectivity_policy="reject_unrepresented",
    unit_cell_policy="preserve_orthorhombic",
):
    limits = limits or PDBParserLimits()
    raw, text = _source_bytes(source, limits)
    lines = text.splitlines()
    if len(lines) > limits.max_lines:
        raise PDBParseError("PDB input exceeds max_lines")
    pairs = set()
    conect_count = 0
    coordinate_lines = []
    for raw_line in lines:
        line = raw_line.ljust(80)
        if line[:6].strip().upper() != "CONECT":
            coordinate_lines.append(raw_line)
            continue
        conect_count += 1
        coordinate_lines.append("")  # Preserve atom source-line numbers.
        if raw_line[31:].strip():
            raise PDBParseError("CONECT fields beyond column 31 are unsupported")
        fields = [line[start : start + 5].strip() for start in range(6, 31, 5)]
        if not fields[0]:
            raise PDBParseError("empty CONECT record")
        try:
            center = int(fields[0])
            targets = [int(value) for value in fields[1:] if value]
        except ValueError as exc:
            raise PDBParseError("CONECT records must contain integer serials") from exc
        if center < 1 or any(target < 1 for target in targets):
            raise PDBParseError("CONECT serials must be positive")
        if not targets:
            raise PDBParseError("CONECT record must contain a bonded atom")
        for target in targets:
            if target == center:
                raise PDBParseError("self CONECT records are not supported")
            pairs.add(tuple(sorted((center, target))))
            if len(pairs) > limits.max_bonds:
                raise PDBParseError("PDB bond count exceeds max_bonds")
    coordinate_source = "\n".join(coordinate_lines) + "\n" if conect_count else source
    system = _legacy_parse_pdb(
        coordinate_source,
        source_id=source_id,
        limits=limits,
        dtype=dtype,
        device=device,
        connectivity_policy=connectivity_policy,
        unit_cell_policy=unit_cell_policy,
    )
    serials = {atom.serial: atom.index for atom in system.atoms}
    if any(first not in serials or second not in serials for first, second in pairs):
        raise PDBParseError("CONECT references an atom serial outside the parsed model")
    mapped_pairs = sorted(tuple(sorted((serials[i], serials[j]))) for i, j in pairs)
    bonds = tuple(
        Bond(
            index=index,
            atom_i=first,
            atom_j=second,
            order=1.0,
            source="product_fixedwidth_pdb_conect_v1",
        )
        for index, (first, second) in enumerate(mapped_pairs)
    )
    provenance_metadata = dict(system.provenance.metadata)
    ignored = dict(provenance_metadata["ignored_record_counts"])
    if conect_count:
        ignored["BLANK"] = ignored.get("BLANK", 0) - conect_count
        if ignored["BLANK"] == 0:
            del ignored["BLANK"]
    provenance_metadata.update(
        bond_count=len(bonds),
        ignored_record_counts=ignored,
        conect_record_count=conect_count,
        delegated_parser_name=system.provenance.parser_name,
        delegated_parser_version=system.provenance.parser_version,
        delegated_coordinate_payload_sha256=system.provenance.source_sha256,
    )
    source_sha256 = hashlib.sha256(raw).hexdigest()
    system = replace(
        system,
        system_id=str(source_id or f"pdb-{source_sha256[:12]}"),
        bonds=bonds,
        provenance=replace(
            system.provenance,
            source_sha256=source_sha256,
            parser_name=PDB_PARSER_NAME,
            parser_version=PDB_PARSER_VERSION,
            operations=("product_fixedwidth_pdb_parse_v1",),
            transformation_chain_verified=False,
            metadata=provenance_metadata,
        ),
    )
    require_valid_all_atom_system(system)
    return system
