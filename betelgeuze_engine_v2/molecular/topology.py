"""Versioned canonical bytes and digest for typed molecular topology identity.

The topology contract contains ordered atoms, bonds, residues, and chains.  It
deliberately excludes coordinates, cells, provenance, source metadata,
experimental observations, and parameter-like fields so those can change
without changing topology identity.  It does not claim that independently
parsed representations of the same chemistry have already been normalized to
one cross-format identity.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import hmac
import json
import struct
from typing import Any

from .models import AllAtomSystem, StructureProvenance
from .validation import (
    MolecularValidationError,
    require_valid_all_atom_system,
    validate_all_atom_system,
)


CANONICAL_TOPOLOGY_VERSION = "1.0.0"
CANONICAL_TOPOLOGY_SCHEMA_ID = (
    f"betelgeuze.canonical_ordered_topology/{CANONICAL_TOPOLOGY_VERSION}"
)
_SUPPORTED_SYSTEM_SCHEMA_IDS = frozenset({"betelgeuze.all_atom_system/2.1.0"})
NON_TOPOLOGY_STATE_VALIDATION_ERROR_CODES = frozenset(
    {
        "unsupported_coordinate_unit",
        "coordinate_atom_count_mismatch",
        "nonfinite_coordinates",
        "nonfinite_partial_charge",
        "invalid_atom_mass",
        "invalid_occupancy",
        "nonfinite_b_factor",
        "nonfinite_unit_cell",
        "invalid_unit_cell_volume",
        "invalid_provenance_claim_safe_flag",
        "invalid_source_sha256",
        "invalid_parent_sha256",
    }
)


class CanonicalTopologyError(ValueError):
    """Raised when topology bytes cannot be assigned unambiguous v1 semantics."""


def canonical_topology_document(system: AllAtomSystem) -> dict[str, Any]:
    """Return the complete ordered topology identity as JSON-safe primitives."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if system.schema_id not in _SUPPORTED_SYSTEM_SCHEMA_IDS:
        raise CanonicalTopologyError(
            f"topology v{CANONICAL_TOPOLOGY_VERSION} does not support system schema "
            f"{system.schema_id!r}; review and version the topology contract explicitly"
        )
    require_valid_all_atom_system(system)
    ordered_bonds = sorted(system.bonds, key=lambda bond: (bond.atom_i, bond.atom_j))
    return {
        "topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "system_schema_id": system.schema_id,
        "atoms": [
            {
                "index": atom.index,
                "name": atom.name,
                "element": atom.element,
                "atomic_number": atom.atomic_number,
                "residue_index": atom.residue_index,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "isotope_mass_number": atom.isotope_mass_number,
                "atom_map": atom.atom_map,
                "altloc": atom.altloc,
                "aromatic": atom.aromatic,
                "stereo": atom.stereo.strip().upper(),
            }
            for atom in system.atoms
        ],
        "bonds": [
            {
                "index": canonical_index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
                "stereo": bond.stereo.strip().upper(),
            }
            for canonical_index, bond in enumerate(ordered_bonds)
        ],
        "residues": [
            {
                "index": residue.index,
                "name": residue.name,
                "chain_index": residue.chain_index,
                "sequence_number": residue.sequence_number,
                "atom_indices": list(residue.atom_indices),
                "insertion_code": residue.insertion_code,
                "entity_type": residue.entity_type,
                "hetero": residue.hetero,
            }
            for residue in system.residues
        ],
        "chains": [
            {
                "index": chain.index,
                "chain_id": chain.chain_id,
                "residue_indices": list(chain.residue_indices),
                "entity_id": chain.entity_id,
            }
            for chain in system.chains
        ],
    }


def serialize_canonical_topology(system: AllAtomSystem) -> bytes:
    """Serialize ordered topology identity to deterministic canonical JSON bytes."""

    document = canonical_topology_document(system)
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_topology_sha256(system: AllAtomSystem) -> str:
    """Return SHA-256 over :func:`serialize_canonical_topology`."""

    return hashlib.sha256(serialize_canonical_topology(system)).hexdigest()


def topology_validation_error_codes(system: AllAtomSystem) -> tuple[str, ...]:
    """Return sorted validation errors that affect canonical topology identity."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return tuple(
        sorted(
            {
                issue.code
                for issue in validate_all_atom_system(system).errors
                if issue.code not in NON_TOPOLOGY_STATE_VALIDATION_ERROR_CODES
            }
        )
    )


def canonical_topology_sha256_for_valid_topology(system: AllAtomSystem) -> str:
    """Digest valid topology even when excluded coordinate/provenance state is invalid.

    This function preserves exactly the v1 topology bytes.  It only neutralizes
    fields that the topology schema explicitly excludes, after first rejecting
    every validation error that affects included topology state.
    """

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    error_codes = topology_validation_error_codes(system)
    if error_codes:
        preview = ", ".join(error_codes[:6])
        suffix = "" if len(error_codes) <= 6 else f", +{len(error_codes) - 6} more"
        raise CanonicalTopologyError(
            f"canonical topology validation failed: {preview}{suffix}"
        )
    neutral_atoms = tuple(
        replace(
            atom,
            partial_charge_e=None,
            mass_da=None,
            serial=None,
            occupancy=None,
            b_factor=None,
            metadata={},
        )
        for atom in system.atoms
    )
    neutral = replace(
        system,
        system_id="canonical-topology-digest",
        atoms=neutral_atoms,
        bonds=tuple(replace(bond, source="topology", metadata={}) for bond in system.bonds),
        residues=tuple(replace(residue, metadata={}) for residue in system.residues),
        chains=tuple(replace(chain, metadata={}) for chain in system.chains),
        coordinates=system.coordinates.new_empty((0, system.atom_count, 3)),
        provenance=StructureProvenance(source_format="topology_digest"),
        cell=None,
        coordinate_unit="angstrom",
        metadata={},
    )
    try:
        return canonical_topology_sha256(neutral)
    except MolecularValidationError as exc:  # classification drift must fail closed
        raise CanonicalTopologyError(
            "excluded-state neutralization did not produce a valid topology carrier"
        ) from exc


def canonical_topologies_equal(left: AllAtomSystem, right: AllAtomSystem) -> bool:
    """Compare complete ordered topology while ignoring excluded state."""

    return serialize_canonical_topology(left) == serialize_canonical_topology(right)


def attached_canonical_topology_sha256_matches(system: AllAtomSystem) -> bool:
    """Verify, but never trust, a provenance-attached digest cache."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    attached_schema_id = system.provenance.metadata.get(
        "canonical_topology_schema_id"
    )
    if attached_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID:
        return False
    attached = system.provenance.metadata.get("canonical_topology_sha256")
    if (
        type(attached) is not str
        or len(attached) != 64
        or any(character not in "0123456789abcdef" for character in attached)
    ):
        return False
    return hmac.compare_digest(attached, canonical_topology_sha256(system))


__all__ = [
    "CANONICAL_TOPOLOGY_SCHEMA_ID",
    "CANONICAL_TOPOLOGY_VERSION",
    "CanonicalTopologyError",
    "NON_TOPOLOGY_STATE_VALIDATION_ERROR_CODES",
    "attached_canonical_topology_sha256_matches",
    "canonical_topologies_equal",
    "canonical_topology_document",
    "canonical_topology_sha256",
    "canonical_topology_sha256_for_valid_topology",
    "serialize_canonical_topology",
    "topology_validation_error_codes",
]
