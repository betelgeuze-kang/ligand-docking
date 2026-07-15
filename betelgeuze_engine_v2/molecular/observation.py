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
MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID = (
    "betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/1.0.0"
)
MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID = (
    "betelgeuze.mmcif_archive_standard_l_peptide_topology_"
    "preparation_inventory_commitment/1.0.0"
)
MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS = (
    "_atom_site.group_pdb",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
    "_atom_site.pdbx_pdb_ins_code",
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
    "_atom_site.occupancy",
    "_atom_site.b_iso_or_equiv",
    "_atom_site.pdbx_formal_charge",
    "_atom_site.auth_seq_id",
    "_atom_site.auth_comp_id",
    "_atom_site.auth_asym_id",
    "_atom_site.auth_atom_id",
    "_atom_site.pdbx_pdb_model_num",
)

_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology."
    "parse_mmcif_polymer_component_topology"
)
_MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION = "1.0.0"
_MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY = "mmcif_polymer_component_topology"
_MMCIF_POLYMER_COMPONENT_TOPOLOGY_COMMITMENT_FIELDS = frozenset(
    {
        "preparation_inventory_commitment_schema_id",
        "preparation_inventory_commitment_sha256",
    }
)
_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology."
    "parse_mmcif_archive_standard_l_peptide_topology"
)
_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION = "1.0.0"
_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY = (
    "mmcif_archive_standard_l_peptide_topology"
)
_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_COMMITMENT_FIELDS = frozenset(
    {
        "preparation_inventory_commitment_schema_id",
        "preparation_inventory_commitment_sha256",
    }
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
_ATOM_TOPOLOGY_MARKER_KEYS = (
    "mmcif_archive_standard_l_peptide_topology",
    "mmcif_nonpoly_component_topology",
    "mmcif_polymer_component_topology",
)
_BOND_TOPOLOGY_MARKER_KEYS = (
    "mmcif_archive_standard_l_peptide_topology",
    "mmcif_nonpoly_covalent_struct_conn_topology",
    "mmcif_polymer_component_topology",
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


def _is_mmcif_polymer_component_topology_parser(system: AllAtomSystem) -> bool:
    return bool(
        system.provenance.source_format == "mmcif"
        and system.provenance.parser_name
        == _MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME
        and system.provenance.parser_version
        == _MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_VERSION
    )


def _is_mmcif_archive_standard_l_peptide_topology_parser(
    system: AllAtomSystem,
) -> bool:
    return bool(
        system.provenance.source_format == "mmcif"
        and system.provenance.parser_name
        == _MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_NAME
        and system.provenance.parser_version
        == _MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PARSER_VERSION
    )


def _normalized_inventory_value(value: Any) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        return {"float_ieee754_binary64_be": struct.pack(">d", value).hex()}
    if isinstance(value, Mapping):
        return {key: _normalized_inventory_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalized_inventory_value(item) for item in value]
    raise TypeError(
        "preparation inventory contains an unsupported value type: "
        f"{type(value).__name__}"
    )


def _preparation_inventory_document(
    system: AllAtomSystem,
    *,
    schema_id: str,
    marker_key: str,
    commitment_fields: frozenset[str],
) -> dict[str, Any]:
    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")

    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata.pop("parser_observation_schema_id", None)
    provenance_metadata.pop("parser_observation_sha256", None)
    provenance_marker = provenance_metadata.get(marker_key)
    if isinstance(provenance_marker, Mapping):
        provenance_metadata[marker_key] = {
            key: item
            for key, item in provenance_marker.items()
            if key not in commitment_fields
        }

    atoms = [
        {
            "index": atom.index,
            "name": atom.name,
            "element": atom.element,
            "atomic_number": atom.atomic_number,
            "residue_index": atom.residue_index,
            "formal_charge": atom.formal_charge,
            "formal_charge_known": atom.formal_charge_known,
            "partial_charge_e": _normalized_inventory_value(atom.partial_charge_e),
            "mass_da": _normalized_inventory_value(atom.mass_da),
            "isotope_mass_number": atom.isotope_mass_number,
            "serial": atom.serial,
            "atom_map": atom.atom_map,
            "altloc": atom.altloc,
            "occupancy": _normalized_inventory_value(atom.occupancy),
            "b_factor": _normalized_inventory_value(atom.b_factor),
            "aromatic": atom.aromatic,
            "stereo": atom.stereo,
            "metadata": _normalized_inventory_value(atom.metadata),
        }
        for atom in system.atoms
    ]
    bonds = [
        {
            "index": bond.index,
            "atom_i": bond.atom_i,
            "atom_j": bond.atom_j,
            "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
            "aromatic": bond.aromatic,
            "stereo": bond.stereo,
            "source": bond.source,
            "metadata": _normalized_inventory_value(bond.metadata),
        }
        for bond in system.bonds
    ]
    residues = [
        {
            "index": residue.index,
            "name": residue.name,
            "chain_index": residue.chain_index,
            "sequence_number": residue.sequence_number,
            "atom_indices": list(residue.atom_indices),
            "insertion_code": residue.insertion_code,
            "entity_type": residue.entity_type,
            "hetero": residue.hetero,
            "metadata": _normalized_inventory_value(residue.metadata),
        }
        for residue in system.residues
    ]
    chains = [
        {
            "index": chain.index,
            "chain_id": chain.chain_id,
            "residue_indices": list(chain.residue_indices),
            "entity_id": chain.entity_id,
            "metadata": _normalized_inventory_value(chain.metadata),
        }
        for chain in system.chains
    ]
    return {
        "schema_id": schema_id,
        "commitment_semantics": (
            "source_bound_digest_tamper_evidence_not_source_authentication"
        ),
        "canonical_topology_sha256": canonical_topology_sha256(system),
        "system": {
            "schema_id": system.schema_id,
            "system_id": system.system_id,
            "coordinate_unit": system.coordinate_unit,
            "model_count": system.model_count,
            "atom_count": len(system.atoms),
            "bond_count": len(system.bonds),
            "residue_count": len(system.residues),
            "chain_count": len(system.chains),
            "atoms": atoms,
            "bonds": bonds,
            "residues": residues,
            "chains": chains,
            "metadata": _normalized_inventory_value(system.metadata),
        },
        "provenance": {
            "source_format": system.provenance.source_format,
            "source_id": system.provenance.source_id,
            "source_sha256": system.provenance.source_sha256,
            "parser_name": system.provenance.parser_name,
            "parser_version": system.provenance.parser_version,
            "operations": list(system.provenance.operations),
            "parent_sha256": list(system.provenance.parent_sha256),
            "preparation_ready": system.provenance.preparation_ready,
            "claim_safe": system.provenance.claim_safe,
            "metadata_excluding_commitment_and_observation_attachment": (
                _normalized_inventory_value(provenance_metadata)
            ),
        },
    }


def mmcif_polymer_component_topology_preparation_inventory_document(
    system: AllAtomSystem,
) -> dict[str, Any]:
    """Build the source-bound normalized polymer-component inventory commitment.

    This is digest-bound tamper evidence, not source authentication.  An attacker
    able to rewrite this commitment and every enclosing digest is outside this
    unkeyed integrity check's threat model.
    """

    return _preparation_inventory_document(
        system,
        schema_id=(
            MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
        ),
        marker_key=_MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY,
        commitment_fields=_MMCIF_POLYMER_COMPONENT_TOPOLOGY_COMMITMENT_FIELDS,
    )


def mmcif_polymer_component_topology_preparation_inventory_sha256(
    system: AllAtomSystem,
) -> str:
    """Hash the normalized source-bound preparation inventory."""

    payload = json.dumps(
        mmcif_polymer_component_topology_preparation_inventory_document(system),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def mmcif_archive_standard_l_peptide_topology_preparation_inventory_document(
    system: AllAtomSystem,
) -> dict[str, Any]:
    """Build the normalized archive-standard peptide inventory commitment."""

    return _preparation_inventory_document(
        system,
        schema_id=(
            MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID
        ),
        marker_key=_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY,
        commitment_fields=(
            _MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_COMMITMENT_FIELDS
        ),
    )


def mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256(
    system: AllAtomSystem,
) -> str:
    """Hash the normalized archive-standard peptide preparation inventory."""

    payload = json.dumps(
        mmcif_archive_standard_l_peptide_topology_preparation_inventory_document(
            system
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


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
        for key in _ATOM_TOPOLOGY_MARKER_KEYS:
            if key in atom.metadata:
                markers[key] = _marker_value(atom.metadata.get(key))
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
        for key in _BOND_TOPOLOGY_MARKER_KEYS:
            if key in bond.metadata:
                markers[key] = _marker_value(bond.metadata.get(key))
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
    provenance_markers = {
        key: _marker_value(system.provenance.metadata.get(key))
        for key in _PROVENANCE_MARKER_KEYS
    }
    system_markers = {
        key: _marker_value(system.metadata.get(key)) for key in _SYSTEM_MARKER_KEYS
    }
    if _is_mmcif_polymer_component_topology_parser(system):
        provenance_markers[_MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY] = (
            _marker_value(
                system.provenance.metadata.get(
                    _MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY
                )
            )
        )
        system_markers[_MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY] = _marker_value(
            system.metadata.get(_MMCIF_POLYMER_COMPONENT_TOPOLOGY_MARKER_KEY)
        )
    if _is_mmcif_archive_standard_l_peptide_topology_parser(system):
        provenance_markers[_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY] = (
            _marker_value(
                system.provenance.metadata.get(
                    _MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY
                )
            )
        )
        system_markers[_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY] = (
            _marker_value(
                system.metadata.get(
                    _MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_MARKER_KEY
                )
            )
        )
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
        "provenance_markers": provenance_markers,
        "system_markers": system_markers,
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
    "MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_ATOM_SITE_HEADERS",
    "MMCIF_POLYMER_COMPONENT_TOPOLOGY_PREPARATION_INVENTORY_COMMITMENT_SCHEMA_ID",
    "PARSER_OBSERVATION_SCHEMA_ID",
    "PARSER_OBSERVATION_SCHEMA_VERSION",
    "attach_parser_observation_digest",
    "attached_parser_observation_sha256_matches",
    "mmcif_archive_standard_l_peptide_topology_preparation_inventory_document",
    "mmcif_archive_standard_l_peptide_topology_preparation_inventory_sha256",
    "mmcif_polymer_component_topology_preparation_inventory_document",
    "mmcif_polymer_component_topology_preparation_inventory_sha256",
    "parser_observation_document",
    "parser_observation_sha256",
]
