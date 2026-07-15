from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
import math

import pytest

import betelgeuze_engine_v2.molecular.standard_l_peptide_completion_rules as rules_module
from betelgeuze_engine_v2.molecular.standard_l_peptide_completion_rules import (
    STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES,
    STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT,
    STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION,
    StandardLPeptideCompletionRuleError,
    standard_l_peptide_completion_component_rule,
    standard_l_peptide_completion_role_rule,
    standard_l_peptide_completion_rule_manifest_bytes,
    standard_l_peptide_completion_rule_manifest_document,
    validate_standard_l_peptide_completion_rule_manifest,
)


EXPECTED_COORDINATE_TOKENS = {
    "ALA": {
        "N": ("-0.966", "0.493", "1.500"),
        "CA": ("0.257", "0.418", "0.692"),
        "C": ("-0.094", "0.017", "-0.716"),
        "O": ("-1.056", "-0.682", "-0.923"),
        "CB": ("1.204", "-0.620", "1.296"),
        "OXT": ("0.661", "0.439", "-1.742"),
        "H": ("-1.383", "-0.425", "1.482"),
        "H2": ("-0.676", "0.661", "2.452"),
        "HA": ("0.746", "1.392", "0.682"),
        "HB1": ("1.459", "-0.330", "2.316"),
        "HB2": ("0.715", "-1.594", "1.307"),
        "HB3": ("2.113", "-0.676", "0.697"),
        "HXT": ("0.435", "0.182", "-2.647"),
    },
    "GLY": {
        "N": ("1.931", "0.090", "-0.034"),
        "CA": ("0.761", "-0.799", "-0.008"),
        "C": ("-0.498", "0.029", "-0.005"),
        "O": ("-0.429", "1.235", "-0.023"),
        "OXT": ("-1.697", "-0.574", "0.018"),
        "H": ("1.910", "0.738", "0.738"),
        "H2": ("2.788", "-0.442", "-0.037"),
        "HA2": ("0.772", "-1.440", "-0.889"),
        "HA3": ("0.793", "-1.415", "0.891"),
        "HXT": ("-2.477", "-0.002", "0.019"),
    },
}

EXPECTED_HYDROGEN_PARENTS = {
    "ALA": {
        "H": "N",
        "H2": "N",
        "HA": "CA",
        "HB1": "CB",
        "HB2": "CB",
        "HB3": "CB",
        "HXT": "OXT",
    },
    "GLY": {
        "H": "N",
        "H2": "N",
        "HA2": "CA",
        "HA3": "CA",
        "HXT": "OXT",
    },
}

EXPECTED_HEAVY_BONDS = {
    "ALA": (
        ("N", "CA", "SING", 1),
        ("CA", "C", "SING", 4),
        ("CA", "CB", "SING", 5),
        ("C", "O", "DOUB", 7),
        ("C", "OXT", "SING", 8),
    ),
    "GLY": (
        ("N", "CA", "SING", 1),
        ("CA", "C", "SING", 4),
        ("C", "O", "DOUB", 7),
        ("C", "OXT", "SING", 8),
    ),
}

EXPECTED_ROLE_INVENTORIES = {
    ("ALA", "singleton"): (
        ("N", "CA", "C", "O", "CB", "OXT"),
        ("H", "H2", "HA", "HB1", "HB2", "HB3", "HXT"),
    ),
    ("ALA", "n_sequence_boundary"): (
        ("N", "CA", "C", "O", "CB"),
        ("H", "H2", "HA", "HB1", "HB2", "HB3"),
    ),
    ("ALA", "internal"): (
        ("N", "CA", "C", "O", "CB"),
        ("H", "HA", "HB1", "HB2", "HB3"),
    ),
    ("ALA", "c_sequence_boundary"): (
        ("N", "CA", "C", "O", "CB", "OXT"),
        ("H", "HA", "HB1", "HB2", "HB3", "HXT"),
    ),
    ("GLY", "singleton"): (
        ("N", "CA", "C", "O", "OXT"),
        ("H", "H2", "HA2", "HA3", "HXT"),
    ),
    ("GLY", "n_sequence_boundary"): (
        ("N", "CA", "C", "O"),
        ("H", "H2", "HA2", "HA3"),
    ),
    ("GLY", "internal"): (
        ("N", "CA", "C", "O"),
        ("H", "HA2", "HA3"),
    ),
    ("GLY", "c_sequence_boundary"): (
        ("N", "CA", "C", "O", "OXT"),
        ("H", "HA2", "HA3", "HXT"),
    ),
}


def _subtract(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return tuple(a - b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def _cross(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def test_manifest_identity_hash_and_nonpromotion_semantics_are_frozen() -> None:
    payload = standard_l_peptide_completion_rule_manifest_bytes()

    assert STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID == (
        "betelgeuze.standard_l_peptide_heavy_to_fixed_neutral_all_atom_"
        "completion_rule_manifest/1.0.0"
    )
    assert STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION == "1.0.0"
    assert STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256 == (
        "eed2b432c6a4b916370e14d922830a5eeb9f531acc579c94b7e823b8949810c6"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
    )
    assert validate_standard_l_peptide_completion_rule_manifest() == (
        STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
    )
    assert json.loads(payload) == standard_l_peptide_completion_rule_manifest_document()

    document = standard_l_peptide_completion_rule_manifest_document()
    assert document["runtime_network_required"] is False
    assert document["source_authenticated"] is False
    assert document["output_formal_charge_policy"] == {
        "scope": "all_output_atoms",
        "formal_charge": 0,
        "semantics": "fixed_profile_microstate_not_environmental_pH_correctness",
    }
    assert document["environmental_pH_correctness_assessed"] is False
    assert document["generic_preparation_ready"] is False
    assert document["global_preparation_ready"] is False
    assert document["parameterability_assessed"] is False
    assert document["physics_supported"] is False
    assert document["runtime_execution_authorized"] is False
    assert document["claim_safe"] is False


@pytest.mark.parametrize("component_id", ["ALA", "GLY"])
def test_component_pins_exact_ccd_coordinates_parents_and_provenance(
    component_id: str,
) -> None:
    component = standard_l_peptide_completion_component_rule(component_id)
    expected_coordinates = EXPECTED_COORDINATE_TOKENS[component_id]
    expected_parents = EXPECTED_HYDROGEN_PARENTS[component_id]

    assert component.frame_anchor_atom_ids == ("N", "CA", "C")
    assert component.ccd_retrieval_date == "2026-07-15"
    assert component.ccd_download_url == (
        f"https://files.rcsb.org/ligands/download/{component_id}.cif"
    )
    assert (component.ccd_file_sha256, component.ccd_file_size_bytes) == {
        "ALA": (
            "6d32b34d4f7b3ddf0cd3dff3f98ddaf7649bc5303ff9a8bd95ba62283f47a1ca",
            6071,
        ),
        "GLY": (
            "c49458946b0ebc057db6ad0a4e1557a1caaed4c80a203accd458efddccbf92ff",
            5615,
        ),
    }[component_id]
    assert tuple(atom.atom_id for atom in component.atoms) == tuple(
        expected_coordinates
    )
    assert all(atom.formal_charge == 0 for atom in component.atoms)
    assert {
        atom.atom_id: (
            atom.ideal_x_token,
            atom.ideal_y_token,
            atom.ideal_z_token,
        )
        for atom in component.atoms
    } == expected_coordinates
    assert {
        atom.atom_id: atom.hydrogen_parent_atom_id
        for atom in component.atoms
        if atom.element == "H"
    } == expected_parents
    assert all(
        atom.hydrogen_parent_atom_id is None
        for atom in component.atoms
        if atom.element != "H"
    )
    assert (
        tuple(
            (bond.atom_id_1, bond.atom_id_2, bond.value_order, bond.ccd_ordinal)
            for bond in component.source_heavy_bonds
        )
        == EXPECTED_HEAVY_BONDS[component_id]
    )


@pytest.mark.parametrize(("component_id", "role"), sorted(EXPECTED_ROLE_INVENTORIES))
def test_role_inventories_pin_heavy_inputs_and_active_hydrogens(
    component_id: str, role: str
) -> None:
    rule = standard_l_peptide_completion_role_rule(component_id, role)
    expected_heavy, expected_hydrogen = EXPECTED_ROLE_INVENTORIES[(component_id, role)]

    assert rule.required_source_heavy_atom_ids == expected_heavy
    assert rule.active_hydrogen_atom_ids == expected_hydrogen
    assert rule.output_atom_ids == expected_heavy + expected_hydrogen
    assert ("OXT" in expected_heavy) == (role in {"singleton", "c_sequence_boundary"})
    assert ("H2" in expected_hydrogen) == (role in {"singleton", "n_sequence_boundary"})
    assert ("HXT" in expected_hydrogen) == (
        role in {"singleton", "c_sequence_boundary"}
    )


def test_geometry_contract_pins_admission_bounds_not_scientific_validation() -> None:
    geometry = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT

    assert geometry.semantics == (
        "profile_contract_admission_not_scientific_validation"
    )
    assert geometry.heavy_bond_ideal_length_reference == (
        "euclidean_distance_between_pinned_CCD_ideal_coordinate_decimal_tokens"
    )
    assert geometry.heavy_bond_absolute_tolerance_angstrom == 0.20
    assert (
        geometry.same_asym_adjacent_left_atom_id,
        geometry.same_asym_adjacent_right_atom_id,
        geometry.same_asym_adjacent_c_n_minimum_distance_angstrom,
        geometry.same_asym_adjacent_c_n_maximum_distance_angstrom,
    ) == ("C", "N", 1.15, 1.55)
    assert geometry.distance_bounds_inclusive is True
    assert geometry.frame_anchor_atom_ids == ("N", "CA", "C")
    assert geometry.normalized_frame_sine_minimum == 0.05
    assert geometry.ala_orientation_center_atom_id == "CA"
    assert geometry.ala_orientation_ordered_atom_ids == ("N", "C", "CB")
    assert geometry.ala_orientation_ideal_sign == "positive"
    assert geometry.ala_normalized_absolute_triple_product_minimum == 0.05
    assert geometry.geometry_scientifically_validated is False

    ala = standard_l_peptide_completion_component_rule("ALA")
    coordinate = {atom.atom_id: atom.ideal_coordinate for atom in ala.atoms}
    n_vector = _subtract(coordinate["N"], coordinate["CA"])
    c_vector = _subtract(coordinate["C"], coordinate["CA"])
    cb_vector = _subtract(coordinate["CB"], coordinate["CA"])
    frame_sine = _norm(_cross(n_vector, c_vector)) / (_norm(n_vector) * _norm(c_vector))
    normalized_triple = _dot(_cross(n_vector, c_vector), cb_vector) / (
        _norm(n_vector) * _norm(c_vector) * _norm(cb_vector)
    )
    assert frame_sine >= geometry.normalized_frame_sine_minimum
    assert normalized_triple > 0.0
    assert abs(normalized_triple) >= (
        geometry.ala_normalized_absolute_triple_product_minimum
    )


def test_manifest_document_is_fresh_and_detached() -> None:
    first = standard_l_peptide_completion_rule_manifest_document()
    first["components"][0]["atoms"][0]["ideal_coordinate_decimal_tokens"]["x"] = (
        "999.999"
    )
    first["sequence_roles"][0]["active_hydrogen_atom_ids"].append("FORGED")

    second = standard_l_peptide_completion_rule_manifest_document()
    assert (
        second["components"][0]["atoms"][0]["ideal_coordinate_decimal_tokens"]["x"]
        == "-0.966"
    )
    assert "FORGED" not in second["sequence_roles"][0]["active_hydrogen_atom_ids"]


def test_records_are_frozen() -> None:
    component = STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES[0]
    role = STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES[0]

    with pytest.raises(FrozenInstanceError):
        component.component_id = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        component.atoms[0].atom_id = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        component.source_heavy_bonds[0].atom_id_1 = "FORGED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        role.role = "FORGED"  # type: ignore[misc]


def test_hash_tamper_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rules_module,
        "STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256",
        "0" * 64,
    )

    with pytest.raises(
        StandardLPeptideCompletionRuleError,
        match="standard_l_peptide_completion_rule_manifest_hash_mismatch",
    ):
        validate_standard_l_peptide_completion_rule_manifest()


def test_exact_key_tamper_fails_even_with_matching_forged_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = standard_l_peptide_completion_rule_manifest_document()
    document["unexpected_authority"] = True
    forged_payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    monkeypatch.setattr(
        rules_module,
        "standard_l_peptide_completion_rule_manifest_document",
        lambda: document,
    )
    monkeypatch.setattr(
        rules_module,
        "STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256",
        hashlib.sha256(forged_payload).hexdigest(),
    )

    with pytest.raises(
        StandardLPeptideCompletionRuleError,
        match="standard_l_peptide_completion_rule_manifest_top_level_keys_mismatch",
    ):
        validate_standard_l_peptide_completion_rule_manifest()


@pytest.mark.parametrize("component_id", ["UNK", "ala", ""])
def test_unknown_component_fails_closed(component_id: str) -> None:
    with pytest.raises(
        StandardLPeptideCompletionRuleError,
        match="unsupported_standard_l_peptide_completion_component",
    ):
        standard_l_peptide_completion_component_rule(component_id)
    with pytest.raises(
        StandardLPeptideCompletionRuleError,
        match="unsupported_standard_l_peptide_completion_component",
    ):
        standard_l_peptide_completion_role_rule(component_id, "singleton")


@pytest.mark.parametrize("role", ["n_terminal", "INTERNAL", ""])
def test_unknown_role_fails_closed(role: str) -> None:
    with pytest.raises(
        StandardLPeptideCompletionRuleError,
        match="unsupported_standard_l_peptide_completion_role",
    ):
        standard_l_peptide_completion_role_rule("ALA", role)


def test_non_string_lookup_arguments_fail_closed() -> None:
    with pytest.raises(TypeError, match="component_id must be a string"):
        standard_l_peptide_completion_component_rule(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="component_id must be a string"):
        standard_l_peptide_completion_role_rule(None, "singleton")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="role must be a string"):
        standard_l_peptide_completion_role_rule("ALA", 1)  # type: ignore[arg-type]
