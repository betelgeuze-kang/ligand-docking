from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_declarations import (
    MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation import (
    MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS,
    MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
    MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS,
    MmcifNonpolyPreparationError,
    mmcif_nonpoly_preparation_document,
    mmcif_nonpoly_preparation_json_bytes,
    parse_mmcif_nonpoly_preparation,
    require_mmcif_nonpoly_preparation_document,
    write_mmcif_nonpoly_preparation_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)
from tests.unit.test_engine_v2_mmcif_nonpoly_atom_site_observations import (
    ATOM_DECLARATIONS,
    ATOM_SITE_ROWS,
    _updated,
)
from tests.unit.test_engine_v2_mmcif_nonpoly_canonical_topology import (
    _replace_row,
    _topology_source,
)


def _preparation_source(
    *,
    atom_declaration_index: int = 0,
    atom_declaration_updates: dict[str, str] | None = None,
    atom_site_rows: tuple[dict[str, str], ...] = ATOM_SITE_ROWS,
    bond_updates: dict[str, str] | None = None,
) -> str:
    source = _topology_source(
        atom_site_rows=atom_site_rows,
        bond_updates=bond_updates,
    )
    if atom_declaration_updates:
        original = dict(ATOM_DECLARATIONS[atom_declaration_index])
        updated = {**original, **atom_declaration_updates}
        source = _replace_row(
            source,
            MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
            original,
            updated,
        )
    return source


def _preparation_error(source: str, code: str) -> MmcifNonpolyPreparationError:
    with pytest.raises(MmcifNonpolyPreparationError) as exc_info:
        parse_mmcif_nonpoly_preparation(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_bounded_neutral_coh_graphs_are_hydrogen_completed_but_not_parameterable() -> (
    None
):
    snapshot = parse_mmcif_nonpoly_preparation(_preparation_source())

    assert snapshot.prepared_graph_count == 2
    assert len(snapshot.biological_assembly_policy_snapshot_sha256) == 64
    assert len(snapshot.biological_assembly_policy_projection_sha256) == 64
    assert len(snapshot.biological_assembly_policy_source_binding_sha256) == 64
    assert len(snapshot.missing_atom_residue_policy_snapshot_sha256) == 64
    assert len(snapshot.missing_atom_residue_policy_projection_sha256) == 64
    assert len(snapshot.missing_atom_residue_policy_source_binding_sha256) == 64
    assert [row.component_id for row in snapshot.instance_reports] == ["LIG", "HOH"]
    ligand, water = snapshot.instance_reports
    assert ligand.preparation_status == "prepared_component_graph"
    assert dict(ligand.formula) == {"C": 1, "H": 2, "O": 1}
    assert ligand.added_hydrogen_count == 2
    assert len(ligand.atoms) == 4
    assert len(ligand.bonds) == 3
    assert [(row.element, row.origin) for row in ligand.atoms] == [
        ("C", "source_atom"),
        ("O", "source_atom"),
        ("H", "added_hydrogen"),
        ("H", "added_hydrogen"),
    ]
    assert ligand.bonds[0].order == 2.0
    assert dict(water.formula) == {"H": 2, "O": 1}
    assert water.added_hydrogen_count == 2
    assert len(water.atoms) == 3
    assert len(water.bonds) == 2

    for report in snapshot.instance_reports:
        assert report.total_formal_charge == 0
        assert report.parameterability_status == (
            "graph_ready_external_connection_blocked"
        )
        assert "intercomponent_coordination_not_prepared" in (
            report.parameterability_blockers
        )
        for blocker in MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS:
            assert blocker in report.parameterability_blockers

    payload = snapshot.to_dict()
    assert payload["parameterable_instance_count"] == 0
    for flag in (
        "supported_chemistry_scope_defined",
        "source_element_interpreted",
        "component_formal_charge_interpreted",
        "atom_site_formal_charge_crosschecked",
        "nonaromatic_state_interpreted",
        "fixed_neutral_valence_hydrogen_completion_applied",
        "hydrogen_completion_graph_created",
        "parameterability_assessed",
        "failure_complete_instance_reports",
    ):
        assert payload[flag] is True
    for flag in (
        "source_authenticated",
        "charged_chemistry_supported",
        "aromatic_chemistry_supported",
        "nitrogen_sulfur_halogen_metal_chemistry_supported",
        "cyclic_chemistry_supported",
        "stereochemistry_prepared",
        "ph_dependent_protonation_interpreted",
        "tautomer_selection_interpreted",
        "intercomponent_connection_prepared",
        "hydrogen_coordinates_generated",
        "reviewed_parameter_source_bound",
        "prepared_all_atom_system_created",
        "parameterable",
        "chemistry_validated",
        "preparation_ready",
        "physics_supported",
        "runtime_eligible",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_source_declared_observation_gap_blocks_preparation_before_chemistry() -> None:
    case = next(
        row
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == "unsupported_unobserved_atom_input"
    )
    error = _preparation_error(
        case.source_text,
        "source_declared_observation_gap_not_supported",
    )

    assert "PRIVATE" not in error.detail
    assert "PRIVATE" not in str(error)


def test_source_declared_biological_assembly_blocks_preparation_before_chemistry() -> (
    None
):
    case = next(
        row
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == "unsupported_biological_assembly_input"
    )
    error = _preparation_error(
        case.source_text,
        "source_declared_biological_assembly_not_supported",
    )

    assert "assembly_id" not in error.detail
    assert "oper_expression" not in str(error)


@pytest.mark.parametrize(
    ("atom_updates", "site_field", "site_value", "expected_blocker"),
    (
        (
            {},
            "_atom_site.pdbx_formal_charge",
            "+1",
            "atom_site_component_formal_charge_mismatch",
        ),
        (
            {"_chem_comp_atom.charge": "+1"},
            "_atom_site.pdbx_formal_charge",
            "+1",
            "charged_chemistry_not_supported",
        ),
        ({}, "_atom_site.type_symbol", "O", "atom_site_component_element_mismatch"),
        (
            {"_chem_comp_atom.type_symbol": "N"},
            "_atom_site.type_symbol",
            "N",
            "element_outside_neutral_coh_scope",
        ),
        (
            {"_chem_comp_atom.pdbx_aromatic_flag": "Y"},
            "_atom_site.type_symbol",
            "C",
            "aromatic_chemistry_not_supported",
        ),
        (
            {"_chem_comp_atom.pdbx_stereo_config": "R"},
            "_atom_site.type_symbol",
            "C",
            "atom_stereochemistry_not_prepared",
        ),
    ),
)
def test_unsupported_or_inconsistent_atom_semantics_are_failure_complete(
    atom_updates: dict[str, str],
    site_field: str,
    site_value: str,
    expected_blocker: str,
) -> None:
    snapshot = parse_mmcif_nonpoly_preparation(
        _preparation_source(
            atom_declaration_updates=atom_updates,
            atom_site_rows=_updated(ATOM_SITE_ROWS, 1, site_field, site_value),
        )
    )

    ligand, water = snapshot.instance_reports
    assert ligand.preparation_status == "unsupported_chemistry"
    assert ligand.parameterability_status == "unsupported_chemistry"
    assert expected_blocker in ligand.chemistry_blockers
    assert expected_blocker in ligand.parameterability_blockers
    assert ligand.atoms == ()
    assert ligand.bonds == ()
    assert ligand.formula == ()
    assert ligand.total_formal_charge is None
    assert water.preparation_status == "prepared_component_graph"


@pytest.mark.parametrize(
    ("token", "expected_code"),
    (
        ("1.0", "invalid_component_formal_charge"),
        ("9", "component_formal_charge_out_of_bounds"),
    ),
)
def test_component_charge_grammar_and_range_fail_without_private_echo(
    token: str, expected_code: str
) -> None:
    error = _preparation_error(
        _preparation_source(atom_declaration_updates={"_chem_comp_atom.charge": token}),
        expected_code,
    )

    assert token not in str(error)
    assert token not in error.detail


def test_triple_bond_is_topology_but_not_supported_preparation_chemistry() -> None:
    snapshot = parse_mmcif_nonpoly_preparation(
        _preparation_source(bond_updates={"_chem_comp_bond.value_order": "TRIP"})
    )

    ligand, water = snapshot.instance_reports
    assert ligand.preparation_status == "unsupported_chemistry"
    assert ligand.chemistry_blockers == ("bond_order_outside_neutral_coh_scope",)
    assert water.preparation_status == "prepared_component_graph"


def test_double_bond_stereochemistry_is_not_prepared() -> None:
    snapshot = parse_mmcif_nonpoly_preparation(
        _preparation_source(bond_updates={"_chem_comp_bond.pdbx_stereo_config": "E"})
    )

    ligand, water = snapshot.instance_reports
    assert ligand.preparation_status == "unsupported_chemistry"
    assert ligand.chemistry_blockers == ("bond_stereochemistry_not_prepared",)
    assert water.preparation_status == "prepared_component_graph"


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_nonpoly_preparation(_preparation_source())
    document = mmcif_nonpoly_preparation_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_PREPARATION_PROFILE_ID
    assert document["missing_atom_residue_admission_checked"] is True
    assert document["biological_assembly_admission_checked"] is True
    assert document["source_binding"][
        "biological_assembly_policy_snapshot_sha256"
    ] == snapshot.biological_assembly_policy_snapshot_sha256
    assert document["source_binding"][
        "missing_atom_residue_policy_snapshot_sha256"
    ] == snapshot.missing_atom_residue_policy_snapshot_sha256
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS
    )
    assert require_mmcif_nonpoly_preparation_document(document) == document
    encoded = mmcif_nonpoly_preparation_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_preparation_json(
        tmp_path / "preparation.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".preparation.json.*.tmp"))

    tampered = deepcopy(document)
    report = tampered["preparation_projection"]["instance_reports"][0]
    added_hydrogen = report["atoms"][2]
    added_hydrogen["parent_atom_index"] = 1
    added_hydrogen["atom_identity_sha256"] = module._sha256(
        {
            "instance_identity_sha256": report["instance_identity_sha256"],
            "index": added_hydrogen["index"],
            "name": added_hydrogen["name"],
            "element": added_hydrogen["element"],
            "formal_charge": added_hydrogen["formal_charge"],
            "aromatic": False,
            "stereo": "none",
            "origin": added_hydrogen["origin"],
            "source_atom_index": None,
            "source_atom_id": None,
            "parent_atom_index": 1,
        }
    )
    projection_digest = module._sha256(tampered["preparation_projection"])
    tampered["preparation_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
            "preparation_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="hydrogen completion bond mismatch"):
        require_mmcif_nonpoly_preparation_document(tampered)


def test_preparation_is_deterministic_and_instance_bound() -> None:
    first = parse_mmcif_nonpoly_preparation(_preparation_source())
    second = parse_mmcif_nonpoly_preparation(_preparation_source())

    assert first == second
    assert first.snapshot_sha256 == second.snapshot_sha256
    ligand, water = first.instance_reports
    assert ligand.atoms[2].atom_identity_sha256 != water.atoms[1].atom_identity_sha256
    assert ligand.bonds[1].bond_identity_sha256 != water.bonds[0].bond_identity_sha256


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_preparation(b"data_x")  # type: ignore[arg-type]
