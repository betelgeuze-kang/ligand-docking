"""Canonical digest for parser-observed chemical-state markers.

Canonical topology identity deliberately excludes source metadata.  This
second, parser-facing digest binds the small set of metadata markers used by
fail-closed preparation inventory to the raw-source digest, parser version,
and recomputed topology identity.  It is tamper evidence, not proof that the
source chemistry is complete or scientifically correct.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import hashlib
import hmac
import json
import struct
from typing import Any

from .models import AllAtomSystem
from .topology import canonical_topology_sha256


PARSER_OBSERVATION_SCHEMA_VERSION = "1.0.0"
PARSER_OBSERVATION_SCHEMA_ID = (
    f"betelgeuze.parser_chemical_state_observation/{PARSER_OBSERVATION_SCHEMA_VERSION}"
)

_ATOM_MARKER_KEYS = (
    "formal_charge_interpretation",
    "formal_charge_source",
    "hydrogen_ordinal",
    "hydrogen_origin",
    "manually_expanded",
    "parent_source_atom_index",
    "pdb_atom_name_field",
    "sdf_atom_map",
    "sdf_source_atom_index",
    "source_atom_index",
    "source_atom_order_preserved",
    "source_record",
)
_BOND_MARKER_KEYS = (
    "hydrogen_ordinal",
    "hydrogen_origin",
    "parent_source_atom_index",
    "sdf_bond_type",
    "sdf_source_atom_i",
    "sdf_source_atom_j",
    "sdf_source_bond_index",
    "source_bond_index",
)
_SYSTEM_MARKER_KEYS = (
    "fragment_count",
    "generated_hydrogen_count",
    "ordered_topology_sha256",
    "source_atom_count",
)
_COVERAGE_MARKER_KEYS = (
    "expanded_atom_count",
    "generated_hydrogen_count",
    "ordered_topology_sha256",
    "rdkit_version",
    "source_atom_count",
)
_PROVENANCE_MARKER_KEYS = (
    "normalized_isomeric_smiles_sha256",
    "ordered_topology_sha256",
    "rdkit_version",
)


def _marker_value(value: Any) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        return {"unexpected_float_ieee754_binary64_be": struct.pack(">d", value).hex()}
    if isinstance(value, Mapping):
        return {
            "unexpected_mapping": {
                key: _marker_value(item) for key, item in value.items()
            }
        }
    if isinstance(value, (list, tuple)):
        return {"unexpected_sequence": [_marker_value(item) for item in value]}
    return {"unsupported_marker_type": type(value).__name__}


def _mmcif_formal_charge_token_observation(atom_site: Any) -> dict[str, Any]:
    if not isinstance(atom_site, Mapping):
        return {"present": False, "atom_site_mapping_present": False}
    key = "_atom_site.pdbx_formal_charge"
    if key not in atom_site:
        return {"present": False, "atom_site_mapping_present": True}
    payload = atom_site.get(key)
    if not isinstance(payload, Mapping):
        return {
            "present": True,
            "atom_site_mapping_present": True,
            "payload_type": type(payload).__name__,
        }
    return {
        "present": True,
        "atom_site_mapping_present": True,
        "value": _marker_value(payload.get("value")),
        "quoted": _marker_value(payload.get("quoted")),
        "multiline": _marker_value(payload.get("multiline")),
    }


def parser_observation_document(system: AllAtomSystem) -> dict[str, Any]:
    """Return the deterministic parser-marker observation document."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    atoms = []
    for atom in system.atoms:
        mmcif = atom.metadata.get("mmcif")
        mmcif_source_atom_site_id = (
            mmcif.get("source_atom_site_id") if isinstance(mmcif, Mapping) else None
        )
        atom_site = mmcif.get("atom_site") if isinstance(mmcif, Mapping) else None
        markers = {
            key: _marker_value(atom.metadata.get(key)) for key in _ATOM_MARKER_KEYS
        }
        if "mmcif_nonpoly_component_topology" in atom.metadata:
            markers["mmcif_nonpoly_component_topology"] = _marker_value(
                atom.metadata.get("mmcif_nonpoly_component_topology")
            )
        atoms.append(
            {
                "index": atom.index,
                "serial": atom.serial,
                "element": atom.element,
                "formal_charge": atom.formal_charge,
                "formal_charge_known": atom.formal_charge_known,
                "aromatic": atom.aromatic,
                "markers": markers,
                "mmcif_source_atom_site_id": _marker_value(mmcif_source_atom_site_id),
                "mmcif_metadata_mapping_present": isinstance(
                    mmcif,
                    Mapping,
                ),
                "mmcif_atom_site_mapping_present": (isinstance(atom_site, Mapping)),
                "mmcif_formal_charge_token": (
                    _mmcif_formal_charge_token_observation(atom_site)
                ),
            }
        )
    bonds = []
    for bond in system.bonds:
        markers = {
            key: _marker_value(bond.metadata.get(key)) for key in _BOND_MARKER_KEYS
        }
        if "mmcif_nonpoly_covalent_struct_conn_topology" in bond.metadata:
            markers["mmcif_nonpoly_covalent_struct_conn_topology"] = _marker_value(
                bond.metadata.get("mmcif_nonpoly_covalent_struct_conn_topology")
            )
        bonds.append(
            {
                "index": bond.index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
                "aromatic": bond.aromatic,
                "source": bond.source,
                "markers": markers,
            }
        )
    coverage = system.provenance.metadata.get("coverage")
    return {
        "observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
        "canonical_topology_sha256": canonical_topology_sha256(system),
        "source_format": system.provenance.source_format,
        "source_id": system.provenance.source_id,
        "source_sha256": system.provenance.source_sha256,
        "parser_name": system.provenance.parser_name,
        "parser_version": system.provenance.parser_version,
        "operations": list(system.provenance.operations),
        "parent_sha256": list(system.provenance.parent_sha256),
        "provenance_markers": {
            key: _marker_value(system.provenance.metadata.get(key))
            for key in _PROVENANCE_MARKER_KEYS
        },
        "system_markers": {
            key: _marker_value(system.metadata.get(key)) for key in _SYSTEM_MARKER_KEYS
        },
        "coverage_markers": {
            key: _marker_value(coverage.get(key))
            if isinstance(coverage, Mapping)
            else None
            for key in _COVERAGE_MARKER_KEYS
        },
        "atoms": atoms,
        "bonds": bonds,
    }


def parser_observation_sha256(system: AllAtomSystem) -> str:
    """Hash the canonical parser-marker observation document."""

    payload = json.dumps(
        parser_observation_document(system),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def attach_parser_observation_digest(system: AllAtomSystem) -> AllAtomSystem:
    """Return ``system`` with a freshly computed observation digest attached."""

    digest = parser_observation_sha256(system)
    metadata = dict(system.provenance.metadata)
    metadata["parser_observation_schema_id"] = PARSER_OBSERVATION_SCHEMA_ID
    metadata["parser_observation_sha256"] = digest
    return replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )


def attached_parser_observation_sha256_matches(system: AllAtomSystem) -> bool:
    """Verify, but never trust, an attached parser-observation digest."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if (
        system.provenance.metadata.get("parser_observation_schema_id")
        != PARSER_OBSERVATION_SCHEMA_ID
    ):
        return False
    attached = system.provenance.metadata.get("parser_observation_sha256")
    if (
        type(attached) is not str
        or len(attached) != 64
        or any(character not in "0123456789abcdef" for character in attached)
    ):
        return False
    try:
        recomputed = parser_observation_sha256(system)
    except (TypeError, ValueError, OverflowError):
        return False
    return hmac.compare_digest(attached, recomputed)


__all__ = [
    "PARSER_OBSERVATION_SCHEMA_ID",
    "PARSER_OBSERVATION_SCHEMA_VERSION",
    "attach_parser_observation_digest",
    "attached_parser_observation_sha256_matches",
    "parser_observation_document",
    "parser_observation_sha256",
]
