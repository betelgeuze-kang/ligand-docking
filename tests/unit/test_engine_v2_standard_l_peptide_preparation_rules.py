from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json

import pytest

from betelgeuze_engine_v2.molecular.standard_l_peptide_preparation_rules import (
    STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES,
    STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE,
    STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_VERSION,
    StandardLPeptidePreparationRuleError,
    standard_l_peptide_expected_retained_atoms,
    standard_l_peptide_expected_retained_bonds,
    standard_l_peptide_preparation_component_rule,
    standard_l_peptide_preparation_role_rule,
    standard_l_peptide_preparation_rule_manifest_bytes,
    standard_l_peptide_preparation_rule_manifest_document,
    validate_standard_l_peptide_preparation_rule_manifest,
)


EXPECTED_ATOMS = {
    "ALA": (
        ("N", "N", 0, "N", "N", "N", "Y", "Y", "N", 1),
        ("CA", "C", 0, "N", "N", "S", "Y", "N", "N", 2),
        ("C", "C", 0, "N", "N", "N", "Y", "N", "Y", 3),
        ("O", "O", 0, "N", "N", "N", "Y", "N", "Y", 4),
        ("CB", "C", 0, "N", "N", "N", "N", "N", "N", 5),
        ("OXT", "O", 0, "N", "Y", "N", "Y", "N", "Y", 6),
        ("H", "H", 0, "N", "N", "N", "Y", "Y", "N", 7),
        ("H2", "H", 0, "N", "Y", "N", "Y", "Y", "N", 8),
        ("HA", "H", 0, "N", "N", "N", "Y", "N", "N", 9),
        ("HB1", "H", 0, "N", "N", "N", "N", "N", "N", 10),
        ("HB2", "H", 0, "N", "N", "N", "N", "N", "N", 11),
        ("HB3", "H", 0, "N", "N", "N", "N", "N", "N", 12),
        ("HXT", "H", 0, "N", "Y", "N", "Y", "N", "Y", 13),
    ),
    "GLY": (
        ("N", "N", 0, "N", "N", "N", "Y", "Y", "N", 1),
        ("CA", "C", 0, "N", "N", "N", "Y", "N", "N", 2),
        ("C", "C", 0, "N", "N", "N", "Y", "N", "Y", 3),
        ("O", "O", 0, "N", "N", "N", "Y", "N", "Y", 4),
        ("OXT", "O", 0, "N", "Y", "N", "Y", "N", "Y", 5),
        ("H", "H", 0, "N", "N", "N", "Y", "Y", "N", 6),
        ("H2", "H", 0, "N", "Y", "N", "Y", "Y", "N", 7),
        ("HA2", "H", 0, "N", "N", "N", "Y", "N", "N", 8),
        ("HA3", "H", 0, "N", "N", "N", "Y", "N", "N", 9),
        ("HXT", "H", 0, "N", "Y", "N", "Y", "N", "Y", 10),
    ),
}

EXPECTED_BONDS = {
    "ALA": (
        ("N", "CA", "SING", 1.0, "N", "N", 1),
        ("N", "H", "SING", 1.0, "N", "N", 2),
        ("N", "H2", "SING", 1.0, "N", "N", 3),
        ("CA", "C", "SING", 1.0, "N", "N", 4),
        ("CA", "CB", "SING", 1.0, "N", "N", 5),
        ("CA", "HA", "SING", 1.0, "N", "N", 6),
        ("C", "O", "DOUB", 2.0, "N", "N", 7),
        ("C", "OXT", "SING", 1.0, "N", "N", 8),
        ("CB", "HB1", "SING", 1.0, "N", "N", 9),
        ("CB", "HB2", "SING", 1.0, "N", "N", 10),
        ("CB", "HB3", "SING", 1.0, "N", "N", 11),
        ("OXT", "HXT", "SING", 1.0, "N", "N", 12),
    ),
    "GLY": (
        ("N", "CA", "SING", 1.0, "N", "N", 1),
        ("N", "H", "SING", 1.0, "N", "N", 2),
        ("N", "H2", "SING", 1.0, "N", "N", 3),
        ("CA", "C", "SING", 1.0, "N", "N", 4),
        ("CA", "HA2", "SING", 1.0, "N", "N", 5),
        ("CA", "HA3", "SING", 1.0, "N", "N", 6),
        ("C", "O", "DOUB", 2.0, "N", "N", 7),
        ("C", "OXT", "SING", 1.0, "N", "N", 8),
        ("OXT", "HXT", "SING", 1.0, "N", "N", 9),
    ),
}

EXPECTED_RETAINED_ATOMS = {
    ("ALA", "singleton"): (
        "N",
        "CA",
        "C",
        "O",
        "CB",
        "OXT",
        "H",
        "H2",
        "HA",
        "HB1",
        "HB2",
        "HB3",
        "HXT",
    ),
    ("ALA", "n_sequence_boundary"): (
        "N",
        "CA",
        "C",
        "O",
        "CB",
        "H",
        "H2",
        "HA",
        "HB1",
        "HB2",
        "HB3",
    ),
    ("ALA", "internal"): (
        "N",
        "CA",
        "C",
        "O",
        "CB",
        "H",
        "HA",
        "HB1",
        "HB2",
        "HB3",
    ),
    ("ALA", "c_sequence_boundary"): (
        "N",
        "CA",
        "C",
        "O",
        "CB",
        "OXT",
        "H",
        "HA",
        "HB1",
        "HB2",
        "HB3",
        "HXT",
    ),
    ("GLY", "singleton"): (
        "N",
        "CA",
        "C",
        "O",
        "OXT",
        "H",
        "H2",
        "HA2",
        "HA3",
        "HXT",
    ),
    ("GLY", "n_sequence_boundary"): (
        "N",
        "CA",
        "C",
        "O",
        "H",
        "H2",
        "HA2",
        "HA3",
    ),
    ("GLY", "internal"): ("N", "CA", "C", "O", "H", "HA2", "HA3"),
    ("GLY", "c_sequence_boundary"): (
        "N",
        "CA",
        "C",
        "O",
        "OXT",
        "H",
        "HA2",
        "HA3",
        "HXT",
    ),
}

EXPECTED_RETAINED_BOND_ORDINALS = {
    ("ALA", "singleton"): tuple(range(1, 13)),
    ("ALA", "n_sequence_boundary"): (1, 2, 3, 4, 5, 6, 7, 9, 10, 11),
    ("ALA", "internal"): (1, 2, 4, 5, 6, 7, 9, 10, 11),
    ("ALA", "c_sequence_boundary"): (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    ("GLY", "singleton"): tuple(range(1, 10)),
    ("GLY", "n_sequence_boundary"): (1, 2, 3, 4, 5, 6, 7),
    ("GLY", "internal"): (1, 2, 4, 5, 6, 7),
    ("GLY", "c_sequence_boundary"): (1, 2, 4, 5, 6, 7, 8, 9),
}


def _atom_projection(component_id: str) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            atom.atom_id,
            atom.element,
            atom.formal_charge,
            atom.aromatic_flag,
            atom.leaving_atom_flag,
            atom.stereo_config,
            atom.backbone_atom_flag,
            atom.n_terminal_atom_flag,
            atom.c_terminal_atom_flag,
            atom.ccd_ordinal,
        )
        for atom in standard_l_peptide_preparation_component_rule(component_id).atoms
    )


def _bond_projection(component_id: str) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            bond.atom_id_1,
            bond.atom_id_2,
            bond.value_order,
            bond.bond_order,
            bond.aromatic_flag,
            bond.stereo_config,
            bond.ccd_ordinal,
        )
        for bond in standard_l_peptide_preparation_component_rule(component_id).bonds
    )


def test_manifest_literal_sha_and_nonpromotion_semantics_are_frozen() -> None:
    payload = standard_l_peptide_preparation_rule_manifest_bytes()

    assert STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SCHEMA_ID == (
        "betelgeuze.standard_l_peptide_neutral_linkage_preparation_rule_manifest/1.0.0"
    )
    assert STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_VERSION == "1.0.0"
    assert STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256 == (
        "daa2beb6648d2749204093bfd0db5dd316cb38557b29890054ddc54c73193d7f"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    )
    assert validate_standard_l_peptide_preparation_rule_manifest() == (
        STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    )
    assert (
        json.loads(payload) == standard_l_peptide_preparation_rule_manifest_document()
    )

    document = standard_l_peptide_preparation_rule_manifest_document()
    assert document["runtime_network_required"] is False
    assert document["source_authenticated"] is False
    assert document["ph_assessed"] is False
    assert document["protonation_correctness_assessed"] is False
    assert document["generic_chemistry_supported"] is False
    assert document["generic_preparation_ready"] is False
    assert document["parameterability_assessed"] is False
    assert document["physics_supported"] is False
    assert document["runtime_execution_authorized"] is False
    assert document["claim_safe"] is False
    document["components"][0]["atoms"][0]["atom_id"] = "FORGED"
    assert (
        standard_l_peptide_preparation_rule_manifest_document()["components"][0][
            "atoms"
        ][0]["atom_id"]
        == "N"
    )


@pytest.mark.parametrize("component_id", ["ALA", "GLY"])
def test_component_atoms_and_bonds_match_exact_official_ccd_rows(
    component_id: str,
) -> None:
    assert _atom_projection(component_id) == EXPECTED_ATOMS[component_id]
    assert _bond_projection(component_id) == EXPECTED_BONDS[component_id]


def test_component_and_role_records_are_immutable() -> None:
    component = STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES[0]
    role = STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES[0]

    with pytest.raises(FrozenInstanceError):
        component.component_id = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        component.atoms[0].atom_id = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        component.bonds[0].atom_id_1 = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        role.role = "FORGED"  # type: ignore[misc]


def test_role_deletions_and_inter_residue_rule_are_exact() -> None:
    assert tuple(
        (rule.role, rule.deleted_atom_ids)
        for rule in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES
    ) == (
        ("singleton", ()),
        ("n_sequence_boundary", ("OXT", "HXT")),
        ("internal", ("H2", "OXT", "HXT")),
        ("c_sequence_boundary", ("H2",)),
    )
    assert (
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.left_atom_id,
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.right_atom_id,
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.value_order,
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.bond_order,
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.aromatic_flag,
        STANDARD_L_PEPTIDE_PREPARATION_INTER_RESIDUE_RULE.stereo_config,
    ) == ("C", "N", "SING", 1.0, "N", "N")


@pytest.mark.parametrize(
    ("component_id", "role"),
    sorted(EXPECTED_RETAINED_ATOMS),
)
def test_expected_retained_atoms_and_bonds_follow_role_deletions(
    component_id: str, role: str
) -> None:
    atoms = standard_l_peptide_expected_retained_atoms(component_id, role)
    bonds = standard_l_peptide_expected_retained_bonds(component_id, role)
    retained_ids = tuple(atom.atom_id for atom in atoms)

    assert retained_ids == EXPECTED_RETAINED_ATOMS[(component_id, role)]
    assert (
        tuple(bond.ccd_ordinal for bond in bonds)
        == (EXPECTED_RETAINED_BOND_ORDINALS[(component_id, role)])
    )
    assert all(
        bond.atom_id_1 in retained_ids and bond.atom_id_2 in retained_ids
        for bond in bonds
    )


@pytest.mark.parametrize("component_id", ["UNK", "ala", ""])
def test_unknown_component_fails_closed(component_id: str) -> None:
    with pytest.raises(
        StandardLPeptidePreparationRuleError,
        match="unsupported_standard_l_peptide_preparation_component",
    ):
        standard_l_peptide_preparation_component_rule(component_id)


@pytest.mark.parametrize("role", ["n_terminal", "INTERNAL", ""])
def test_unknown_role_fails_closed(role: str) -> None:
    with pytest.raises(
        StandardLPeptidePreparationRuleError,
        match="unsupported_standard_l_peptide_preparation_role",
    ):
        standard_l_peptide_preparation_role_rule(role)


def test_non_string_component_and_role_fail_closed() -> None:
    with pytest.raises(TypeError, match="component_id must be a string"):
        standard_l_peptide_preparation_component_rule(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="role must be a string"):
        standard_l_peptide_preparation_role_rule(None)  # type: ignore[arg-type]
