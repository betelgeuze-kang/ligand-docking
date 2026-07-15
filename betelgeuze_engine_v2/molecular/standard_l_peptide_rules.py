"""Pinned offline heavy-atom rules for a bounded ALA/GLY peptide profile.

The rules in this module are engine-owned topology rules.  The recorded wwPDB
Chemical Component Dictionary downloads are provenance and tamper evidence;
their hashes do not authenticate the downloads and the files are never fetched
at runtime.  Atom names are exact rule keys, not a geometry- or alias-based
chemistry inference mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any


STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.standard_l_peptide_heavy_topology_rule_manifest/1.0.0"
)
STANDARD_L_PEPTIDE_RULE_MANIFEST_VERSION = "1.0.0"
STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256 = (
    "4d941815d26431a5de9bd74b4860f84ce39232e7123ee87b3b61a104457eb244"
)


class StandardLPeptideRuleError(ValueError):
    """Raised when the immutable runtime rule manifest is inconsistent."""


@dataclass(frozen=True, slots=True)
class StandardLPeptideRuleBond:
    atom_id_1: str
    atom_id_2: str
    order: float
    ccd_ordinal: int
    condition: str = "always"


@dataclass(frozen=True, slots=True)
class StandardLPeptideComponentRule:
    component_id: str
    rule_id: str
    ccd_component_type: str
    ccd_release_status: str
    ccd_initial_date: str
    ccd_modified_date: str
    ccd_download_url: str
    ccd_file_sha256: str
    ccd_file_size_bytes: int
    core_atom_elements: tuple[tuple[str, str], ...]
    c_boundary_additional_atom_elements: tuple[tuple[str, str], ...]
    bonds: tuple[StandardLPeptideRuleBond, ...]

    def atom_elements(
        self, *, c_sequence_boundary: bool
    ) -> tuple[tuple[str, str], ...]:
        if c_sequence_boundary:
            return (*self.core_atom_elements, *self.c_boundary_additional_atom_elements)
        return self.core_atom_elements

    def active_bonds(
        self, *, c_sequence_boundary: bool
    ) -> tuple[StandardLPeptideRuleBond, ...]:
        return tuple(
            bond
            for bond in self.bonds
            if bond.condition == "always"
            or (
                c_sequence_boundary
                and bond.condition == "c_sequence_boundary_or_singleton"
            )
        )


STANDARD_L_PEPTIDE_COMPONENT_RULES = (
    StandardLPeptideComponentRule(
        component_id="ALA",
        rule_id="betelgeuze.standard_l_peptide_heavy_graph.ALA/1.0.0",
        ccd_component_type="L-PEPTIDE LINKING",
        ccd_release_status="REL",
        ccd_initial_date="1999-07-08",
        ccd_modified_date="2024-09-27",
        ccd_download_url="https://files.rcsb.org/ligands/download/ALA.cif",
        ccd_file_sha256=(
            "6d32b34d4f7b3ddf0cd3dff3f98ddaf7649bc5303ff9a8bd95ba62283f47a1ca"
        ),
        ccd_file_size_bytes=6071,
        core_atom_elements=(
            ("N", "N"),
            ("CA", "C"),
            ("C", "C"),
            ("O", "O"),
            ("CB", "C"),
        ),
        c_boundary_additional_atom_elements=(("OXT", "O"),),
        bonds=(
            StandardLPeptideRuleBond("N", "CA", 1.0, 1),
            StandardLPeptideRuleBond("CA", "C", 1.0, 4),
            StandardLPeptideRuleBond("C", "O", 2.0, 7),
            StandardLPeptideRuleBond("CA", "CB", 1.0, 5),
            StandardLPeptideRuleBond(
                "C", "OXT", 1.0, 8, "c_sequence_boundary_or_singleton"
            ),
        ),
    ),
    StandardLPeptideComponentRule(
        component_id="GLY",
        rule_id="betelgeuze.standard_l_peptide_heavy_graph.GLY/1.0.0",
        ccd_component_type="PEPTIDE LINKING",
        ccd_release_status="REL",
        ccd_initial_date="1999-07-08",
        ccd_modified_date="2024-09-27",
        ccd_download_url="https://files.rcsb.org/ligands/download/GLY.cif",
        ccd_file_sha256=(
            "c49458946b0ebc057db6ad0a4e1557a1caaed4c80a203accd458efddccbf92ff"
        ),
        ccd_file_size_bytes=5615,
        core_atom_elements=(("N", "N"), ("CA", "C"), ("C", "C"), ("O", "O")),
        c_boundary_additional_atom_elements=(("OXT", "O"),),
        bonds=(
            StandardLPeptideRuleBond("N", "CA", 1.0, 1),
            StandardLPeptideRuleBond("CA", "C", 1.0, 4),
            StandardLPeptideRuleBond("C", "O", 2.0, 7),
            StandardLPeptideRuleBond(
                "C", "OXT", 1.0, 8, "c_sequence_boundary_or_singleton"
            ),
        ),
    ),
)

STANDARD_L_PEPTIDE_INTER_RESIDUE_RULE_ID = (
    "betelgeuze.standard_l_peptide_sequence_adjacent_C_N/1.0.0"
)
STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS = ("C", "N")
STANDARD_L_PEPTIDE_INTER_RESIDUE_BOND_ORDER = 1.0


def _bond_document(bond: StandardLPeptideRuleBond) -> dict[str, Any]:
    return {
        "atom_id_1": bond.atom_id_1,
        "atom_id_2": bond.atom_id_2,
        "bond_order": bond.order,
        "ccd_bond_ordinal": bond.ccd_ordinal,
        "condition": bond.condition,
    }


def standard_l_peptide_rule_manifest_document() -> dict[str, Any]:
    """Return a fresh JSON-safe view derived only from immutable rule records."""

    return {
        "schema_id": STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID,
        "version": STANDARD_L_PEPTIDE_RULE_MANIFEST_VERSION,
        "scope": "bounded_standard_l_peptide_ALA_GLY_heavy_atom_topology",
        "runtime_network_required": False,
        "source_authenticated": False,
        "source_hash_semantics": "downloaded_file_tamper_evidence_not_authentication",
        "source_retrieval_date": "2026-07-14",
        "atom_identity_semantics": (
            "exact_engine_rule_atom_id_join_not_geometry_or_auth_alias_inference"
        ),
        "formal_charge_semantics": "preserve_source_unknownness_without_assignment",
        "components": [
            {
                "component_id": rule.component_id,
                "rule_id": rule.rule_id,
                "ccd_provenance": {
                    "component_type": rule.ccd_component_type,
                    "release_status": rule.ccd_release_status,
                    "initial_date": rule.ccd_initial_date,
                    "modified_date": rule.ccd_modified_date,
                    "download_url": rule.ccd_download_url,
                    "downloaded_file_sha256": rule.ccd_file_sha256,
                    "downloaded_file_size_bytes": rule.ccd_file_size_bytes,
                },
                "core_atom_elements": [
                    {"atom_id": atom_id, "element": element}
                    for atom_id, element in rule.core_atom_elements
                ],
                "c_sequence_boundary_additional_atom_elements": [
                    {"atom_id": atom_id, "element": element}
                    for atom_id, element in rule.c_boundary_additional_atom_elements
                ],
                "intra_residue_bonds": [_bond_document(bond) for bond in rule.bonds],
            }
            for rule in STANDARD_L_PEPTIDE_COMPONENT_RULES
        ],
        "inter_residue_rule": {
            "rule_id": STANDARD_L_PEPTIDE_INTER_RESIDUE_RULE_ID,
            "left_atom_id": STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS[0],
            "right_atom_id": STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS[1],
            "bond_order": STANDARD_L_PEPTIDE_INTER_RESIDUE_BOND_ORDER,
            "scope": "same_asym_consecutive_entity_poly_seq_positions_only",
        },
    }


def standard_l_peptide_rule_manifest_bytes() -> bytes:
    return json.dumps(
        standard_l_peptide_rule_manifest_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _computed_standard_l_peptide_rule_manifest_sha256() -> str:
    return hashlib.sha256(standard_l_peptide_rule_manifest_bytes()).hexdigest()


def validate_standard_l_peptide_rule_manifest() -> str:
    """Fail closed unless the runtime immutable rule document matches its pin."""

    computed = _computed_standard_l_peptide_rule_manifest_sha256()
    if not hmac.compare_digest(computed, STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256):
        raise StandardLPeptideRuleError(
            "standard_l_peptide_rule_manifest_hash_mismatch"
        )
    if {rule.component_id for rule in STANDARD_L_PEPTIDE_COMPONENT_RULES} != {
        "ALA",
        "GLY",
    }:
        raise StandardLPeptideRuleError(
            "standard_l_peptide_rule_manifest_component_set_mismatch"
        )
    return computed


def standard_l_peptide_component_rule(
    component_id: str,
) -> StandardLPeptideComponentRule:
    """Return the exact immutable rule for one admitted component."""

    validate_standard_l_peptide_rule_manifest()
    if type(component_id) is not str:
        raise TypeError("component_id must be a string")
    for rule in STANDARD_L_PEPTIDE_COMPONENT_RULES:
        if rule.component_id == component_id:
            return rule
    raise StandardLPeptideRuleError("unsupported_standard_l_peptide_component")


__all__ = [
    "STANDARD_L_PEPTIDE_COMPONENT_RULES",
    "STANDARD_L_PEPTIDE_INTER_RESIDUE_ATOM_IDS",
    "STANDARD_L_PEPTIDE_INTER_RESIDUE_BOND_ORDER",
    "STANDARD_L_PEPTIDE_INTER_RESIDUE_RULE_ID",
    "STANDARD_L_PEPTIDE_RULE_MANIFEST_SCHEMA_ID",
    "STANDARD_L_PEPTIDE_RULE_MANIFEST_SHA256",
    "STANDARD_L_PEPTIDE_RULE_MANIFEST_VERSION",
    "StandardLPeptideComponentRule",
    "StandardLPeptideRuleBond",
    "StandardLPeptideRuleError",
    "standard_l_peptide_component_rule",
    "standard_l_peptide_rule_manifest_bytes",
    "standard_l_peptide_rule_manifest_document",
    "validate_standard_l_peptide_rule_manifest",
]
