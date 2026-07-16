from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_roles as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_roles import (
    MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS,
    MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS,
    MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS,
    MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
    MmcifNonpolyComponentRoleError,
    mmcif_nonpoly_component_role_document,
    mmcif_nonpoly_component_role_json_bytes,
    parse_mmcif_nonpoly_component_roles,
    require_mmcif_nonpoly_component_role_document,
    write_mmcif_nonpoly_component_role_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    MmcifPreparationCorpusAtom,
    _corpus_source,
    mmcif_nonpoly_preparation_corpus_cases,
)


def _single_atom_source(
    element: str,
    charge: str,
    *,
    site_charge: str | None = None,
) -> str:
    return _corpus_source(
        (
            MmcifPreparationCorpusAtom(
                "X1",
                element,
                charge,
                site_formal_charge=site_charge,
            ),
        ),
        (),
    )


def _role_error(source: str, code: str) -> MmcifNonpolyComponentRoleError:
    with pytest.raises(MmcifNonpolyComponentRoleError) as exc_info:
        parse_mmcif_nonpoly_component_roles(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_source_water_is_interpreted_but_general_nonpoly_role_remains_unresolved() -> (
    None
):
    source = mmcif_nonpoly_preparation_corpus_cases()[0].source_text
    snapshot = parse_mmcif_nonpoly_component_roles(source)

    ligand, water = snapshot.roles
    assert ligand.component_id == "LIG"
    assert ligand.entity_type == "non-polymer"
    assert ligand.chem_comp_type == "non-polymer"
    assert ligand.composition_role == "unresolved_nonpoly_component"
    assert ligand.role_status == "unresolved"
    assert ligand.preparation_disposition == "eligible_for_chemistry_gate_only"
    assert dict(ligand.element_counts) == {"C": 1, "O": 1}
    assert ligand.total_formal_charge == 0
    assert ligand.role_blockers == (
        "ligand_cofactor_and_other_nonpoly_roles_not_interpreted",
    )

    assert water.component_id == "HOH"
    assert water.entity_type == "water"
    assert water.chem_comp_type == "non-polymer"
    assert water.composition_role == "water"
    assert water.role_status == "interpreted"
    assert water.preparation_disposition == "eligible_for_bounded_preparation"
    assert dict(water.element_counts) == {"O": 1}
    assert water.total_formal_charge == 0
    assert water.role_blockers == ()

    payload = snapshot.to_dict()
    for flag in (
        "source_entity_type_interpreted",
        "chem_comp_type_interpreted",
        "component_element_composition_interpreted",
        "component_formal_charge_composition_interpreted",
        "source_water_role_interpreted",
        "monoatomic_metal_composition_interpreted",
        "monoatomic_nonmetal_ion_composition_interpreted",
        "bounded_composition_role_interpreted",
    ):
        assert payload[flag] is True
    for flag in (
        "formal_charge_default_inferred",
        "general_ligand_role_interpreted",
        "cofactor_role_interpreted",
        "modified_residue_role_interpreted",
        "biological_function_inferred",
        "metal_coordination_chemistry_interpreted",
        "ion_parameterization_supported",
        "metal_parameterization_supported",
        "preparation_ready",
        "parameterable",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


@pytest.mark.parametrize(
    ("element", "charge"), (("Na", "+1"), ("Zn", "+2"), ("Fe", "+3"))
)
def test_monoatomic_metal_composition_is_explicitly_unsupported(
    element: str, charge: str
) -> None:
    snapshot = parse_mmcif_nonpoly_component_roles(_single_atom_source(element, charge))
    role = snapshot.roles[0]

    assert role.composition_role == "monoatomic_metal_component"
    assert role.role_status == "interpreted"
    assert role.preparation_disposition == "explicitly_unsupported"
    assert dict(role.element_counts) == {element: 1}
    assert role.total_formal_charge == int(charge)
    assert "monoatomic_metal_preparation_not_supported" in role.role_blockers


@pytest.mark.parametrize(
    ("element", "charge"), (("Cl", "-1"), ("F", "-1"), ("N", "-3"))
)
def test_charged_monoatomic_nonmetal_is_an_explicit_ion_boundary(
    element: str, charge: str
) -> None:
    snapshot = parse_mmcif_nonpoly_component_roles(_single_atom_source(element, charge))
    role = snapshot.roles[0]

    assert role.composition_role == "monoatomic_nonmetal_ion"
    assert role.role_status == "interpreted"
    assert role.preparation_disposition == "explicitly_unsupported"
    assert dict(role.element_counts) == {element: 1}
    assert role.total_formal_charge == int(charge)
    assert "monoatomic_nonmetal_ion_preparation_not_supported" in (role.role_blockers)


def test_neutral_multiatom_or_unreviewed_nonpoly_role_remains_unresolved() -> None:
    neutral = parse_mmcif_nonpoly_component_roles(_single_atom_source("C", "0"))
    charged_multi = parse_mmcif_nonpoly_component_roles(
        _corpus_source(
            (
                MmcifPreparationCorpusAtom("C1", "C", "+1"),
                MmcifPreparationCorpusAtom("O1", "O", "0"),
            ),
            (),
        )
    )

    for role in (neutral.roles[0], charged_multi.roles[0]):
        assert role.composition_role == "unresolved_nonpoly_component"
        assert role.role_status == "unresolved"
        assert "ligand_cofactor_and_other_nonpoly_roles_not_interpreted" in (
            role.role_blockers
        )

    disputed_element = parse_mmcif_nonpoly_component_roles(
        _single_atom_source("B", "+3")
    ).roles[0]
    assert disputed_element.composition_role == "unresolved_nonpoly_component"


def test_unknown_charge_is_not_defaulted_into_an_ion_role() -> None:
    snapshot = parse_mmcif_nonpoly_component_roles(
        _single_atom_source("Cl", "?", site_charge="?")
    )
    role = snapshot.roles[0]

    assert role.composition_role == "unresolved_nonpoly_component"
    assert role.formal_charge_state == "unavailable"
    assert role.total_formal_charge is None
    assert "formal_charge_composition_unavailable" in role.role_blockers


def test_water_composition_or_charge_mismatch_is_failure_complete() -> None:
    source = mmcif_nonpoly_preparation_corpus_cases()[0].source_text
    element_mismatch = source.replace("HOH O O 0 N N 1", "HOH O N 0 N N 1", 1)
    charge_mismatch = source.replace("HOH O O 0 N N 1", "HOH O O +1 N N 1", 1)
    assert element_mismatch != source
    assert charge_mismatch != source

    element_role = parse_mmcif_nonpoly_component_roles(element_mismatch).roles[1]
    charge_role = parse_mmcif_nonpoly_component_roles(charge_mismatch).roles[1]
    assert element_role.composition_role == "water_composition_mismatch"
    assert "water_element_composition_mismatch" in element_role.role_blockers
    assert charge_role.composition_role == "water_composition_mismatch"
    assert "water_formal_charge_mismatch" in charge_role.role_blockers
    assert element_role.preparation_disposition == "explicitly_unsupported"
    assert charge_role.preparation_disposition == "explicitly_unsupported"


def test_selected_chem_comp_type_must_use_official_nonpolymer_vocabulary() -> None:
    source = mmcif_nonpoly_preparation_corpus_cases()[0].source_text
    invalid = source.replace("HOH non-polymer 0", "HOH water 0", 1)
    assert invalid != source

    _role_error(invalid, "selected_component_type_not_nonpolymer")


def test_component_identifiers_remain_case_sensitive_and_header_order_is_bound() -> (
    None
):
    source = mmcif_nonpoly_preparation_corpus_cases()[0].source_text
    lower_case_ids = source.replace("LIG", "lig")
    lower_case_snapshot = parse_mmcif_nonpoly_component_roles(lower_case_ids)
    assert lower_case_snapshot.roles[0].component_id == "lig"

    original = (
        "loop_\n"
        "_chem_comp.id\n"
        "_chem_comp.type\n"
        "_chem_comp.pdbx_formal_charge\n"
        "LIG non-polymer 0\n"
        "HOH non-polymer 0\n"
        "#\n"
    )
    reordered = (
        "loop_\n"
        "_chem_comp.type\n"
        "_chem_comp.id\n"
        "_chem_comp.pdbx_formal_charge\n"
        "non-polymer LIG 0\n"
        "non-polymer HOH 0\n"
        "#\n"
    )
    reordered_source = source.replace(original, reordered, 1)
    assert reordered_source != source
    reordered_snapshot = parse_mmcif_nonpoly_component_roles(reordered_source)
    document = mmcif_nonpoly_component_role_document(reordered_snapshot)
    assert require_mmcif_nonpoly_component_role_document(document) == document


@pytest.mark.parametrize(
    ("element", "charge", "code"),
    (
        ("Xx", "0", "invalid_component_element_symbol"),
        ("C", "1.0", "invalid_component_formal_charge"),
        ("C", "9", "component_formal_charge_out_of_bounds"),
    ),
)
def test_invalid_composition_values_fail_without_private_echo(
    element: str, charge: str, code: str
) -> None:
    error = _role_error(
        _single_atom_source(element, charge, site_charge="0"),
        code,
    )

    private_value = element if code == "invalid_component_element_symbol" else charge
    assert private_value not in error.detail
    assert private_value not in str(error)


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_nonpoly_component_roles(
        mmcif_nonpoly_preparation_corpus_cases()[0].source_text
    )
    document = mmcif_nonpoly_component_role_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS
    )
    assert document["source_binding"]["metal_element_policy"] == list(
        MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS
    )
    assert document["source_binding"]["nonmetal_ion_element_policy"] == list(
        MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS
    )
    assert require_mmcif_nonpoly_component_role_document(document) == document
    encoded = mmcif_nonpoly_component_role_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_component_role_json(
        tmp_path / "component-roles.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".component-roles.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["role_projection"]["roles"][0]["composition_role"] = "water"
    projection_digest = module._sha256(tampered["role_projection"])
    tampered["role_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
            "role_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="source-water role mismatch"):
        require_mmcif_nonpoly_component_role_document(tampered)


def test_document_rejects_a_rehashed_role_that_bypasses_classifier_precedence() -> None:
    snapshot = parse_mmcif_nonpoly_component_roles(_single_atom_source("Zn", "+2"))
    document = mmcif_nonpoly_component_role_document(snapshot)
    tampered = deepcopy(document)
    role = tampered["role_projection"]["roles"][0]
    role["composition_role"] = "unresolved_nonpoly_component"
    role["role_status"] = "unresolved"
    role["preparation_disposition"] = "eligible_for_chemistry_gate_only"
    role["role_blockers"] = ["ligand_cofactor_and_other_nonpoly_roles_not_interpreted"]
    role["role_identity_sha256"] = module._sha256(
        {key: value for key, value in role.items() if key != "role_identity_sha256"}
    )
    tampered["composition_role_counts"] = {
        "unresolved_nonpoly_component": 1,
        "water": 1,
    }
    tampered["role_status_counts"] = {"interpreted": 1, "unresolved": 1}
    projection_digest = module._sha256(tampered["role_projection"])
    tampered["role_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
            "role_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )

    with pytest.raises(ValueError, match="deterministic classification mismatch"):
        require_mmcif_nonpoly_component_role_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_component_roles(b"data_x")  # type: ignore[arg-type]


def test_dedicated_component_role_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-component-roles.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_nonpoly_component_roles.py" in source
    assert "test_engine_v2_mmcif_nonpoly_component_roles.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
