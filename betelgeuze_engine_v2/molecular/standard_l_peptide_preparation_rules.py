"""Pinned offline neutral-linkage preparation rules for ALA and GLY.

The immutable records in this module reproduce the selected atom, bond, and
terminal-linkage annotations in the official wwPDB Chemical Component
Dictionary ALA and GLY entries.  They describe one source-explicit CCD-neutral
linkage microstate only.  They do not authenticate the CCD downloads, infer pH
or protonation correctness, establish generic molecular preparation, or grant
physics, runtime, execution, or claim authority.  Runtime use performs no
network access.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any


STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.standard_l_peptide_neutral_linkage_preparation_rule_manifest/1.0.0"
)
STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_VERSION = "1.0.0"
STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256 = (
    "daa2beb6648d2749204093bfd0db5dd316cb38557b29890054ddc54c73193d7f"
)


class StandardLPeptidePreparationRuleError(ValueError):
    """Raised when a bounded preparation rule request cannot be satisfied."""


@dataclass(frozen=True, slots=True)
class StandardLPeptidePreparationAtomRule:
    """One exact selected ``_chem_comp_atom`` rule row."""

    atom_id: str
    element: str
    formal_charge: int
    aromatic_flag: str
    leaving_atom_flag: str
    stereo_config: str
    backbone_atom_flag: str
    n_terminal_atom_flag: str
    c_terminal_atom_flag: str
    ccd_ordinal: int


@dataclass(frozen=True, slots=True)
class StandardLPeptidePreparationBondRule:
    """One exact selected ``_chem_comp_bond`` rule row."""

    atom_id_1: str
    atom_id_2: str
    value_order: str
    bond_order: float
    aromatic_flag: str
    stereo_config: str
    ccd_ordinal: int


@dataclass(frozen=True, slots=True)
class StandardLPeptidePreparationComponentRule:
    """The frozen source-explicit atom and bond inventory for one component."""

    component_id: str
    rule_id: str
    ccd_component_type: str
    ccd_release_status: str
    ccd_initial_date: str
    ccd_modified_date: str
    ccd_download_url: str
    ccd_file_sha256: str
    ccd_file_size_bytes: int
    atoms: tuple[StandardLPeptidePreparationAtomRule, ...]
    bonds: tuple[StandardLPeptidePreparationBondRule, ...]


@dataclass(frozen=True, slots=True)
class StandardLPeptidePreparationRoleRule:
    """Exact atom deletions for one sequence-boundary role."""

    role: str
    deleted_atom_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StandardLPeptidePreparationInterResidueRule:
    """The only sequence-adjacent inter-residue linkage in this manifest."""

    rule_id: str
    left_atom_id: str
    right_atom_id: str
    value_order: str
    bond_order: float
    aromatic_flag: str
    stereo_config: str
    scope: str


def _atom(
    atom_id: str,
    element: str,
    ordinal: int,
    *,
    leaving: str = "N",
    stereo: str = "N",
    backbone: str = "N",
    n_terminal: str = "N",
    c_terminal: str = "N",
) -> StandardLPeptidePreparationAtomRule:
    return StandardLPeptidePreparationAtomRule(
        atom_id=atom_id,
        element=element,
        formal_charge=0,
        aromatic_flag="N",
        leaving_atom_flag=leaving,
        stereo_config=stereo,
        backbone_atom_flag=backbone,
        n_terminal_atom_flag=n_terminal,
        c_terminal_atom_flag=c_terminal,
        ccd_ordinal=ordinal,
    )


def _bond(
    atom_id_1: str,
    atom_id_2: str,
    value_order: str,
    ordinal: int,
) -> StandardLPeptidePreparationBondRule:
    return StandardLPeptidePreparationBondRule(
        atom_id_1=atom_id_1,
        atom_id_2=atom_id_2,
        value_order=value_order,
        bond_order={"SING": 1.0, "DOUB": 2.0}[value_order],
        aromatic_flag="N",
        stereo_config="N",
        ccd_ordinal=ordinal,
    )


STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES = (
    StandardLPeptidePreparationComponentRule(
        component_id="ALA",
        rule_id="betelgeuze.standard_l_peptide_neutral_linkage.ALA/1.0.0",
        ccd_component_type="L-PEPTIDE LINKING",
        ccd_release_status="REL",
        ccd_initial_date="1999-07-08",
        ccd_modified_date="2024-09-27",
        ccd_download_url="https://files.rcsb.org/ligands/download/ALA.cif",
        ccd_file_sha256=(
            "6d32b34d4f7b3ddf0cd3dff3f98ddaf7649bc5303ff9a8bd95ba62283f47a1ca"
        ),
        ccd_file_size_bytes=6071,
        atoms=(
            _atom("N", "N", 1, backbone="Y", n_terminal="Y"),
            _atom("CA", "C", 2, stereo="S", backbone="Y"),
            _atom("C", "C", 3, backbone="Y", c_terminal="Y"),
            _atom("O", "O", 4, backbone="Y", c_terminal="Y"),
            _atom("CB", "C", 5),
            _atom("OXT", "O", 6, leaving="Y", backbone="Y", c_terminal="Y"),
            _atom("H", "H", 7, backbone="Y", n_terminal="Y"),
            _atom(
                "H2",
                "H",
                8,
                leaving="Y",
                backbone="Y",
                n_terminal="Y",
            ),
            _atom("HA", "H", 9, backbone="Y"),
            _atom("HB1", "H", 10),
            _atom("HB2", "H", 11),
            _atom("HB3", "H", 12),
            _atom("HXT", "H", 13, leaving="Y", backbone="Y", c_terminal="Y"),
        ),
        bonds=(
            _bond("N", "CA", "SING", 1),
            _bond("N", "H", "SING", 2),
            _bond("N", "H2", "SING", 3),
            _bond("CA", "C", "SING", 4),
            _bond("CA", "CB", "SING", 5),
            _bond("CA", "HA", "SING", 6),
            _bond("C", "O", "DOUB", 7),
            _bond("C", "OXT", "SING", 8),
            _bond("CB", "HB1", "SING", 9),
            _bond("CB", "HB2", "SING", 10),
            _bond("CB", "HB3", "SING", 11),
            _bond("OXT", "HXT", "SING", 12),
        ),
    ),
    StandardLPeptidePreparationComponentRule(
        component_id="GLY",
        rule_id="betelgeuze.standard_l_peptide_neutral_linkage.GLY/1.0.0",
        ccd_component_type="PEPTIDE LINKING",
        ccd_release_status="REL",
        ccd_initial_date="1999-07-08",
        ccd_modified_date="2024-09-27",
        ccd_download_url="https://files.rcsb.org/ligands/download/GLY.cif",
        ccd_file_sha256=(
            "c49458946b0ebc057db6ad0a4e1557a1caaed4c80a203accd458efddccbf92ff"
        ),
        ccd_file_size_bytes=5615,
        atoms=(
            _atom("N", "N", 1, backbone="Y", n_terminal="Y"),
            _atom("CA", "C", 2, backbone="Y"),
            _atom("C", "C", 3, backbone="Y", c_terminal="Y"),
            _atom("O", "O", 4, backbone="Y", c_terminal="Y"),
            _atom("OXT", "O", 5, leaving="Y", backbone="Y", c_terminal="Y"),
            _atom("H", "H", 6, backbone="Y", n_terminal="Y"),
            _atom(
                "H2",
                "H",
                7,
                leaving="Y",
                backbone="Y",
                n_terminal="Y",
            ),
            _atom("HA2", "H", 8, backbone="Y"),
            _atom("HA3", "H", 9, backbone="Y"),
            _atom("HXT", "H", 10, leaving="Y", backbone="Y", c_terminal="Y"),
        ),
        bonds=(
            _bond("N", "CA", "SING", 1),
            _bond("N", "H", "SING", 2),
            _bond("N", "H2", "SING", 3),
            _bond("CA", "C", "SING", 4),
            _bond("CA", "HA2", "SING", 5),
            _bond("CA", "HA3", "SING", 6),
            _bond("C", "O", "DOUB", 7),
            _bond("C", "OXT", "SING", 8),
            _bond("OXT", "HXT", "SING", 9),
        ),
    ),
)

STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES = (
    StandardLPeptidePreparationRoleRule("singleton", ()),
    StandardLPeptidePreparationRoleRule("n_sequence_boundary", ("OXT", "HXT")),
    StandardLPeptidePreparationRoleRule("internal", ("H2", "OXT", "HXT")),
    StandardLPeptidePreparationRoleRule("c_sequence_boundary", ("H2",)),
)

STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE = (
    StandardLPeptidePreparationInterResidueRule(
        rule_id="betelgeuze.standard_l_peptide_neutral_sequence_adjacent_C_N/1.0.0",
        left_atom_id="C",
        right_atom_id="N",
        value_order="SING",
        bond_order=1.0,
        aromatic_flag="N",
        stereo_config="N",
        scope="same_asym_consecutive_entity_poly_seq_positions_only",
    )
)


def _atom_document(atom: StandardLPeptidePreparationAtomRule) -> dict[str, Any]:
    return {
        "atom_id": atom.atom_id,
        "element": atom.element,
        "formal_charge": atom.formal_charge,
        "aromatic_flag": atom.aromatic_flag,
        "leaving_atom_flag": atom.leaving_atom_flag,
        "stereo_config": atom.stereo_config,
        "backbone_atom_flag": atom.backbone_atom_flag,
        "n_terminal_atom_flag": atom.n_terminal_atom_flag,
        "c_terminal_atom_flag": atom.c_terminal_atom_flag,
        "ccd_ordinal": atom.ccd_ordinal,
    }


def _bond_document(bond: StandardLPeptidePreparationBondRule) -> dict[str, Any]:
    return {
        "atom_id_1": bond.atom_id_1,
        "atom_id_2": bond.atom_id_2,
        "value_order": bond.value_order,
        "bond_order": bond.bond_order,
        "aromatic_flag": bond.aromatic_flag,
        "stereo_config": bond.stereo_config,
        "ccd_ordinal": bond.ccd_ordinal,
    }


def standard_l_peptide_preparation_rule_manifest_document() -> dict[str, Any]:
    """Return a fresh deterministic JSON-safe view of the immutable rules."""

    inter_residue = STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE
    return {
        "schema_id": STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID,
        "version": STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_VERSION,
        "scope": "bounded_ALA_GLY_source_explicit_CCD_neutral_linkage_microstate",
        "runtime_network_required": False,
        "source_authenticated": False,
        "source_hash_semantics": "downloaded_file_tamper_evidence_not_authentication",
        "source_retrieval_date": "2026-07-15",
        "microstate_semantics": (
            "source_explicit_CCD_neutral_linkage_not_environmental_pH_or_"
            "protonation_correctness"
        ),
        "ph_assessed": False,
        "protonation_correctness_assessed": False,
        "generic_chemistry_supported": False,
        "generic_preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_execution_authorized": False,
        "claim_safe": False,
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
                "atoms": [_atom_document(atom) for atom in rule.atoms],
                "bonds": [_bond_document(bond) for bond in rule.bonds],
            }
            for rule in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES
        ],
        "sequence_roles": [
            {
                "role": role.role,
                "deleted_atom_ids": list(role.deleted_atom_ids),
                "retention_semantics": "retain_all_other_component_atoms_and_bonds",
            }
            for role in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES
        ],
        "inter_residue_rule": {
            "rule_id": inter_residue.rule_id,
            "left_atom_id": inter_residue.left_atom_id,
            "right_atom_id": inter_residue.right_atom_id,
            "value_order": inter_residue.value_order,
            "bond_order": inter_residue.bond_order,
            "aromatic_flag": inter_residue.aromatic_flag,
            "stereo_config": inter_residue.stereo_config,
            "scope": inter_residue.scope,
        },
    }


def standard_l_peptide_preparation_rule_manifest_bytes() -> bytes:
    """Serialize the rule document as canonical ASCII JSON bytes."""

    return json.dumps(
        standard_l_peptide_preparation_rule_manifest_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _computed_standard_l_peptide_preparation_rule_manifest_sha256() -> str:
    return hashlib.sha256(
        standard_l_peptide_preparation_rule_manifest_bytes()
    ).hexdigest()


def validate_standard_l_peptide_preparation_rule_manifest() -> str:
    """Fail closed unless the runtime rule document exactly matches its pin."""

    computed = _computed_standard_l_peptide_preparation_rule_manifest_sha256()
    if not hmac.compare_digest(
        computed, STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    ):
        raise StandardLPeptidePreparationRuleError(
            "standard_l_peptide_preparation_rule_manifest_hash_mismatch"
        )

    if tuple(
        rule.component_id for rule in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES
    ) != (
        "ALA",
        "GLY",
    ):
        raise StandardLPeptidePreparationRuleError(
            "standard_l_peptide_preparation_rule_manifest_component_set_mismatch"
        )
    if tuple(role.role for role in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES) != (
        "singleton",
        "n_sequence_boundary",
        "internal",
        "c_sequence_boundary",
    ):
        raise StandardLPeptidePreparationRuleError(
            "standard_l_peptide_preparation_rule_manifest_role_set_mismatch"
        )

    for component in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES:
        atom_ids = tuple(atom.atom_id for atom in component.atoms)
        if len(atom_ids) != len(set(atom_ids)):
            raise StandardLPeptidePreparationRuleError(
                "standard_l_peptide_preparation_rule_duplicate_atom"
            )
        if tuple(atom.ccd_ordinal for atom in component.atoms) != tuple(
            range(1, len(component.atoms) + 1)
        ):
            raise StandardLPeptidePreparationRuleError(
                "standard_l_peptide_preparation_rule_atom_ordinal_mismatch"
            )
        if tuple(bond.ccd_ordinal for bond in component.bonds) != tuple(
            range(1, len(component.bonds) + 1)
        ):
            raise StandardLPeptidePreparationRuleError(
                "standard_l_peptide_preparation_rule_bond_ordinal_mismatch"
            )
        atom_id_set = set(atom_ids)
        seen_pairs: set[tuple[str, str]] = set()
        for bond in component.bonds:
            if bond.atom_id_1 not in atom_id_set or bond.atom_id_2 not in atom_id_set:
                raise StandardLPeptidePreparationRuleError(
                    "standard_l_peptide_preparation_rule_unknown_bond_endpoint"
                )
            pair = tuple(sorted((bond.atom_id_1, bond.atom_id_2)))
            if pair in seen_pairs:
                raise StandardLPeptidePreparationRuleError(
                    "standard_l_peptide_preparation_rule_duplicate_bond"
                )
            seen_pairs.add(pair)
        for role in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES:
            if not set(role.deleted_atom_ids).issubset(atom_id_set):
                raise StandardLPeptidePreparationRuleError(
                    "standard_l_peptide_preparation_rule_unknown_role_deletion"
                )
    return computed


def standard_l_peptide_preparation_component_rule(
    component_id: str,
) -> StandardLPeptidePreparationComponentRule:
    """Return the exact immutable rule for one admitted component."""

    validate_standard_l_peptide_preparation_rule_manifest()
    if type(component_id) is not str:
        raise TypeError("component_id must be a string")
    for rule in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES:
        if rule.component_id == component_id:
            return rule
    raise StandardLPeptidePreparationRuleError(
        "unsupported_standard_l_peptide_preparation_component"
    )


def standard_l_peptide_preparation_role_rule(
    role: str,
) -> StandardLPeptidePreparationRoleRule:
    """Return the exact immutable deletion rule for one admitted role."""

    validate_standard_l_peptide_preparation_rule_manifest()
    if type(role) is not str:
        raise TypeError("role must be a string")
    for rule in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES:
        if rule.role == role:
            return rule
    raise StandardLPeptidePreparationRuleError(
        "unsupported_standard_l_peptide_preparation_role"
    )


def standard_l_peptide_expected_retained_atoms(
    component_id: str, role: str
) -> tuple[StandardLPeptidePreparationAtomRule, ...]:
    """Return retained atoms in their exact CCD ordinal order."""

    component = standard_l_peptide_preparation_component_rule(component_id)
    role_rule = standard_l_peptide_preparation_role_rule(role)
    deleted = frozenset(role_rule.deleted_atom_ids)
    return tuple(atom for atom in component.atoms if atom.atom_id not in deleted)


def standard_l_peptide_expected_retained_bonds(
    component_id: str, role: str
) -> tuple[StandardLPeptidePreparationBondRule, ...]:
    """Return retained intra-residue bonds in exact CCD ordinal order."""

    component = standard_l_peptide_preparation_component_rule(component_id)
    retained_atom_ids = {
        atom.atom_id
        for atom in standard_l_peptide_expected_retained_atoms(component_id, role)
    }
    return tuple(
        bond
        for bond in component.bonds
        if bond.atom_id_1 in retained_atom_ids and bond.atom_id_2 in retained_atom_ids
    )


__all__ = [
    "STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES",
    "STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE",
    "STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES",
    "STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID",
    "STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256",
    "STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_VERSION",
    "StandardLPeptidePreparationAtomRule",
    "StandardLPeptidePreparationBondRule",
    "StandardLPeptidePreparationComponentRule",
    "StandardLPeptidePreparationInterResidueRule",
    "StandardLPeptidePreparationRoleRule",
    "StandardLPeptidePreparationRuleError",
    "standard_l_peptide_expected_retained_atoms",
    "standard_l_peptide_expected_retained_bonds",
    "standard_l_peptide_preparation_component_rule",
    "standard_l_peptide_preparation_role_rule",
    "standard_l_peptide_preparation_rule_manifest_bytes",
    "standard_l_peptide_preparation_rule_manifest_document",
    "validate_standard_l_peptide_preparation_rule_manifest",
]
