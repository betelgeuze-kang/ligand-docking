from __future__ import annotations

import math

import pytest
import torch

import betelgeuze_engine_v2.molecular.pdb_mmcif as pdb_mmcif
from betelgeuze_engine_v2.molecular import (
    StructureParseError,
    deserialize_all_atom_system,
    parse_mmcif,
    serialize_all_atom_system,
)


ATOM_HEADERS = (
    "_atom_site.group_PDB",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_alt_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_entity_id",
    "_atom_site.label_seq_id",
    "_atom_site.pdbx_PDB_ins_code",
    "_atom_site.Cartn_x",
    "_atom_site.Cartn_y",
    "_atom_site.Cartn_z",
    "_atom_site.occupancy",
    "_atom_site.B_iso_or_equiv",
    "_atom_site.auth_atom_id",
    "_atom_site.auth_comp_id",
    "_atom_site.auth_asym_id",
    "_atom_site.auth_seq_id",
    "_atom_site.pdbx_PDB_model_num",
    "_atom_site.pdbx_formal_charge",
)


def _atom_row(
    atom_id: int | str,
    atom_name: str,
    *,
    element: str = "C",
    group: str = "ATOM",
    comp: str = "GLY",
    asym: str = "A",
    entity: str = "1",
    label_seq: str = "1",
    insertion: str = "?",
    x: str = "0.0",
    y: str = "0.0",
    z: str = "0.0",
    occupancy: str = "1.0",
    b_factor: str = "20.0",
    auth_atom: str | None = None,
    auth_comp: str | None = None,
    auth_asym: str = "X",
    auth_seq: str = "10",
    model: int = 1,
    charge: str = "0",
) -> str:
    return " ".join(
        (
            group,
            str(atom_id),
            element,
            atom_name,
            ".",
            comp,
            asym,
            entity,
            label_seq,
            insertion,
            x,
            y,
            z,
            occupancy,
            b_factor,
            atom_name if auth_atom is None else auth_atom,
            comp if auth_comp is None else auth_comp,
            auth_asym,
            auth_seq,
            str(model),
            charge,
        )
    )


def _loop(headers: tuple[str, ...], rows: tuple[str, ...]) -> str:
    return "\n".join(("loop_", *headers, *rows, "#"))


def _entity_sections(
    entity_rows: tuple[str, ...] = ("1 polymer",),
    asym_rows: tuple[str, ...] = ("A 1",),
) -> tuple[str, str]:
    return (
        _loop(("_entity.id", "_entity.type"), entity_rows),
        _loop(("_struct_asym.id", "_struct_asym.entity_id"), asym_rows),
    )


def _document(*sections: str, name: str = "demo") -> bytes:
    return ("\n".join((f"data_{name}", "#", *sections)) + "\n").encode("ascii")


def _atom_loop(*rows: str, headers: tuple[str, ...] = ATOM_HEADERS) -> str:
    return _loop(headers, tuple(rows))


def _assert_code(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(payload)
    assert exc_info.value.source_format == "mmcif"
    assert exc_info.value.code == code


def test_label_namespace_prevents_auth_chain_and_residue_collisions() -> None:
    entity, asym = _entity_sections(asym_rows=("A 1", "B 1"))
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "N", element="N", asym="A", auth_asym="X", auth_seq="10"),
                _atom_row(2, "CA", asym="B", auth_asym="X", auth_seq="10"),
            ),
        )
    )
    assert [chain.chain_id for chain in result.system.chains] == ["A", "B"]
    assert [chain.entity_id for chain in result.system.chains] == ["1", "1"]
    assert result.system.chains[0].metadata["auth_asym_ids"] == ["X"]


def test_modified_polymer_hetatm_keeps_entity_type_separate_from_record_class() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(_atom_row(1, "SE", element="Se", group="HETATM", comp="MSE")),
        )
    )
    residue = result.system.residues[0]
    assert residue.hetero is True
    assert residue.entity_type == "polymer"
    assert residue.metadata["entity_type_basis"] == "mmcif_entity_category"


def test_models_allow_distinct_atom_site_ids_and_are_aligned_by_label_identity() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "N", element="N", x="0.0", model=1),
                _atom_row(2, "CA", x="1.0", model=1),
                _atom_row(4, "CA", x="1.5", model=2),
                _atom_row(3, "N", element="N", x="0.1", model=2),
            ),
        )
    )
    system = result.system
    assert [atom.name for atom in system.atoms] == ["N", "CA"]
    assert torch.allclose(
        system.coordinates[:, :, 0],
        torch.tensor([[0.0, 1.0], [0.1, 1.5]], dtype=torch.float64),
    )
    assert system.atoms[0].metadata["mmcif"]["atom_site_id_by_model"] == [
        {"model_id": 1, "atom_site_id": "1"},
        {"model_id": 2, "atom_site_id": "3"},
    ]


def test_atom_site_id_is_an_arbitrary_globally_unique_code_and_serial_is_synthetic() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(entity, asym, _atom_loop(_atom_row("Ca3g28", "CA")))
    )
    atom = result.system.atoms[0]
    assert atom.serial == 1
    assert atom.metadata["mmcif"]["source_atom_site_id"] == "Ca3g28"

    _assert_code(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row("same", "CA", model=1),
                _atom_row("same", "CA", model=2),
            ),
        ),
        "duplicate_atom_site_id",
    )


def test_nonpolymer_arbitrary_auth_seq_id_gets_stable_synthetic_sequence_number() -> None:
    entity, asym = _entity_sections(entity_rows=("1 non-polymer",))
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row("a1", "C1", comp="LIG", label_seq=".", auth_seq="A-10"),
                _atom_row("a2", "O1", element="O", comp="LIG", label_seq=".", auth_seq="A-10"),
            ),
        )
    )
    residue = result.system.residues[0]
    assert residue.sequence_number == -1
    assert residue.metadata["mmcif_auth_seq_id"] == "A-10"
    assert residue.metadata["canonical_sequence_source"] == "synthetic_negative_from_nonpolymer_auth_identity"


def test_label_identity_whitespace_that_canonical_model_would_strip_is_rejected() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, '" CA "', auth_atom='" CA "'))),
        "label_identity_whitespace_not_supported",
    )


def test_missing_and_explicit_zero_formal_charges_remain_distinguishable() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "N", element="N", charge="?"),
                _atom_row(2, "CA", charge="0"),
            ),
        )
    )
    assert [atom.formal_charge for atom in result.system.atoms] == [0, 0]
    assert result.system.atoms[0].formal_charge_known is False
    assert result.system.atoms[1].formal_charge_known is True
    assert result.system.atoms[0].metadata["formal_charge_known"] is False
    assert result.system.atoms[1].metadata["formal_charge_known"] is True
    assert result.coverage.unknown_formal_charge_count == 1
    assert "formal_charge_unknown_for_some_atoms" in result.coverage.blockers


def test_quoted_question_mark_charge_is_literal_and_invalid_not_missing() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", charge='"?"'))),
        "invalid_formal_charge",
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"x": '"1.0"'}, "invalid_atom_coordinate"),
        ({"occupancy": '"1.0"'}, "invalid_occupancy"),
        ({"charge": '"0"'}, "invalid_formal_charge"),
    ],
)
def test_quoted_numeric_lexemes_are_not_retyped_as_numbers(
    overrides: dict[str, str],
    code: str,
) -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", **overrides))),
        code,
    )


def test_triclinic_scalar_cell_and_cif_numbers_are_preserved() -> None:
    entity, asym = _entity_sections()
    cell = "\n".join(
        (
            "_cell.length_a 2.0(1)e1",
            "_cell.length_b 21.0(2)",
            "_cell.length_c 22",
            "_cell.angle_alpha 80.0",
            "_cell.angle_beta 90.0",
            "_cell.angle_gamma 100.0",
            "_space_group.name_H-M_alt 'P 1'",
            "#",
        )
    )
    result = parse_mmcif(
        _document(entity, cell, asym, _atom_loop(_atom_row(1, "CA", x="1e0")))
    )
    assert result.system.cell is not None
    assert result.system.cell.periodic == (False, False, False)
    assert math.isclose(float(result.system.cell.volume_angstrom3), 8955.0, rel_tol=0.03)
    assert result.system.metadata["mmcif"]["cell"]["standard_uncertainty_present"] is True
    assert "numeric_standard_uncertainty_not_propagated" in result.coverage.blockers
    assert "crystallographic_cell_not_simulation_box" in result.coverage.blockers


def test_cif_standard_uncertainty_precedes_exponent_and_post_exponent_form_fails() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(_atom_row(1, "CA", x="1.25(3)e1")),
        )
    )
    assert math.isclose(float(result.system.coordinates[0, 0, 0]), 12.5)
    assert "numeric_standard_uncertainty_not_propagated" in result.coverage.blockers

    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", x="1.25e1(3)"))),
        "invalid_atom_coordinate",
    )


def test_explicit_cell_esd_is_validated_preserved_and_blocks_lossy_use() -> None:
    entity, asym = _entity_sections()
    cell = "\n".join(
        (
            "_cell.length_a 20.0",
            "_cell.length_b 21.0",
            "_cell.length_c 22.0",
            "_cell.angle_alpha 90.0",
            "_cell.angle_beta 90.0",
            "_cell.angle_gamma 90.0",
            "_cell.length_a_esd 0.05",
            "_space_group.name_H-M_alt 'P 1'",
            "#",
        )
    )
    result = parse_mmcif(
        _document(entity, cell, asym, _atom_loop(_atom_row(1, "CA")))
    )
    assert result.system.metadata["mmcif"]["cell"]["standard_uncertainty_present"] is True
    assert "numeric_standard_uncertainty_not_propagated" in result.coverage.blockers
    cell_payload = next(
        entry
        for entry in result.system.metadata["mmcif"]["preserved_category_payloads"]
        if entry["category"] == "_cell"
    )
    values = {item["tag"]: item["value"]["value"] for item in cell_payload["scalar_items"]}
    assert values["_cell.length_a_esd"] == "0.05"


@pytest.mark.parametrize("esd", ["-0.05", '"0.05"'])
def test_invalid_cell_esd_fails_closed(esd: str) -> None:
    entity, asym = _entity_sections()
    cell = "\n".join(
        (
            "_cell.length_a 20.0",
            "_cell.length_b 21.0",
            "_cell.length_c 22.0",
            "_cell.angle_alpha 90.0",
            "_cell.angle_beta 90.0",
            "_cell.angle_gamma 90.0",
            f"_cell.length_a_esd {esd}",
            "#",
        )
    )
    _assert_code(
        _document(entity, cell, asym, _atom_loop(_atom_row(1, "CA"))),
        "invalid_numeric_standard_uncertainty",
    )


def test_uninterpreted_reciprocal_cell_esd_still_triggers_uncertainty_blocker() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            "_cell.reciprocal_length_a_esd 0.0005\n#",
            asym,
            _atom_loop(_atom_row(1, "CA")),
        )
    )
    assert result.system.cell is None
    assert "numeric_standard_uncertainty_not_propagated" in result.coverage.blockers


def test_explicit_atom_site_esd_is_validated_preserved_and_blocks_lossy_use() -> None:
    entity, asym = _entity_sections()
    headers = ATOM_HEADERS + ("_atom_site.Cartn_x_esd",)
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(_atom_row(1, "CA") + " 0.025", headers=headers),
        )
    )
    assert "numeric_standard_uncertainty_not_propagated" in result.coverage.blockers
    atom_site = result.system.atoms[0].metadata["mmcif"]["atom_site"]
    assert atom_site["_atom_site.cartn_x_esd"]["value"] == "0.025"


@pytest.mark.parametrize("esd", ["-0.1", '"0.1"'])
def test_invalid_atom_site_esd_fails_closed(esd: str) -> None:
    entity, asym = _entity_sections()
    headers = ATOM_HEADERS + ("_atom_site.Cartn_x_esd",)
    _assert_code(
        _document(
            entity,
            asym,
            _atom_loop(_atom_row(1, "CA") + f" {esd}", headers=headers),
        ),
        "invalid_numeric_standard_uncertainty",
    )


def test_non_p1_cell_blocks_unexpanded_crystallographic_symmetry_without_symop_loop() -> None:
    entity, asym = _entity_sections()
    cell = "\n".join(
        (
            "_cell.length_a 20.0",
            "_cell.length_b 21.0",
            "_cell.length_c 22.0",
            "_cell.angle_alpha 90.0",
            "_cell.angle_beta 90.0",
            "_cell.angle_gamma 90.0",
            "_space_group.name_H-M_alt 'P 21 21 21'",
            "#",
        )
    )
    result = parse_mmcif(_document(entity, cell, asym, _atom_loop(_atom_row(1, "CA"))))
    assert "crystallographic_symmetry_not_expanded" in result.coverage.blockers


def test_non_p1_space_group_without_cell_still_declares_unexpanded_symmetry() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            "_space_group.name_H-M_alt 'P 21 21 21'\n#",
            asym,
            _atom_loop(_atom_row(1, "CA")),
        )
    )
    assert result.system.cell is None
    assert "crystallographic_symmetry_not_expanded" in result.coverage.blockers


def test_conflicting_space_group_aliases_fail_closed_but_equivalent_spellings_pass() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(
            entity,
            "_space_group.name_H-M_alt 'P 1'\n_symmetry.space_group_name_H-M 'P 21 21 21'\n#",
            asym,
            _atom_loop(_atom_row(1, "CA")),
        ),
        "conflicting_space_group",
    )
    result = parse_mmcif(
        _document(
            entity,
            "_space_group.name_H-M_alt 'P 1'\n_symmetry.space_group_name_H-M P1\n#",
            asym,
            _atom_loop(_atom_row(1, "CA")),
        )
    )
    assert "crystallographic_symmetry_not_expanded" not in result.coverage.blockers


def test_partial_cell_fails_closed() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(entity, "_cell.length_a 20.0\n#", asym, _atom_loop(_atom_row(1, "CA"))),
        "incomplete_cell",
    )


def test_unrelated_categories_and_assembly_metadata_are_inventoried() -> None:
    entity, asym = _entity_sections()
    audit = _loop(("_audit_author.name", "_audit_author.pdbx_ordinal"), ('"A. Author" 1',))
    assembly = "_pdbx_struct_assembly.id 1\n_pdbx_struct_assembly.details 'author assembly'\n#"
    result = parse_mmcif(
        _document(
            "_entry.id demo\n#",
            audit,
            entity,
            assembly,
            asym,
            _atom_loop(_atom_row(1, "CA")),
        )
    )
    inventory = result.system.metadata["mmcif"]["category_inventory"]
    assert [entry["category"] for entry in inventory] == [
        "_entry",
        "_audit_author",
        "_entity",
        "_pdbx_struct_assembly",
        "_struct_asym",
        "_atom_site",
    ]
    policies = {entry["category"]: entry["policy"] for entry in inventory}
    assert policies["_audit_author"] == "uninterpreted_metadata"
    assert policies["_entity"] == "partially_interpreted"
    assert policies["_atom_site"] == "interpreted_with_source_values_preserved"
    assert policies["_pdbx_struct_assembly"] == "deferred_biological_assembly"
    payloads = {
        entry["category"]: entry
        for entry in result.system.metadata["mmcif"]["preserved_category_payloads"]
    }
    assembly_payload = payloads["_pdbx_struct_assembly"]
    assert assembly_payload["scalar_items"] == [
        {"tag": "_pdbx_struct_assembly.id", "value": {"value": "1", "quoted": False, "multiline": False}},
        {
            "tag": "_pdbx_struct_assembly.details",
            "value": {"value": "author assembly", "quoted": True, "multiline": False},
        },
    ]
    assert result.coverage.uninterpreted_category_count == 2
    assert "uninterpreted_mmcif_categories_present" in result.coverage.blockers
    assert "biological_assembly_not_applied" in result.coverage.blockers


def test_deferred_symmetry_operation_loop_survives_canonical_round_trip() -> None:
    entity, asym = _entity_sections()
    symmetry = _loop(
        ("_space_group_symop.id", "_space_group_symop.operation_xyz"),
        ("1 'x,y,z'", "2 '-x,-y,-z'"),
    )
    result = parse_mmcif(
        _document(entity, symmetry, asym, _atom_loop(_atom_row(1, "CA")))
    )
    payloads = {
        entry["category"]: entry
        for entry in result.system.metadata["mmcif"]["preserved_category_payloads"]
    }
    symop = payloads["_space_group_symop"]
    assert symop["policy"] == "deferred_symmetry_expansion"
    assert symop["loops"][0]["tags"] == [
        "_space_group_symop.id",
        "_space_group_symop.operation_xyz",
    ]
    assert symop["loops"][0]["rows"][1][1]["value"] == "-x,-y,-z"
    assert "crystallographic_symmetry_not_expanded" in result.coverage.blockers
    restored = deserialize_all_atom_system(serialize_all_atom_system(result.system))
    assert restored.metadata["mmcif"]["preserved_category_payloads"] == result.system.metadata[
        "mmcif"
    ]["preserved_category_payloads"]


def test_mmcif_resource_limits_fail_before_semantic_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity, asym = _entity_sections()
    payload = _document(entity, asym, _atom_loop(_atom_row(1, "CA")))

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_INPUT_BYTES", len(payload) - 1)
    _assert_code(payload, "input_too_large")

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_INPUT_BYTES", len(payload))
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ATOM_ROWS", 0)
    _assert_code(payload, "too_many_atom_rows")


def test_mmcif_resource_usage_and_fixed_limits_are_recorded() -> None:
    entity, asym = _entity_sections()
    payload = _document(entity, asym, _atom_loop(_atom_row(1, "CA")))
    result = parse_mmcif(payload)
    metadata = result.system.metadata["mmcif"]
    assert metadata["resource_usage"]["input_bytes"] == len(payload)
    assert metadata["resource_usage"]["token_count"] > 1
    assert metadata["resource_usage"]["atom_site_rows"] == 1
    assert metadata["resource_limits"]["input_bytes"] == 64 * 1024 * 1024
    assert metadata["resource_limits"]["token_count"] == 2_000_000
    assert metadata["resource_limits"]["atom_site_rows"] == 80_000


@pytest.mark.parametrize("category", ["_struct_conn", "_chem_comp_bond"])
def test_explicit_topology_categories_fail_instead_of_being_dropped(category: str) -> None:
    entity, asym = _entity_sections()
    topology = _loop((f"{category}.id",), ("1",))
    _assert_code(
        _document(entity, topology, asym, _atom_loop(_atom_row(1, "CA"))),
        "unsupported_topology_category",
    )


@pytest.mark.parametrize(
    "category",
    [
        "_chem_comp",
        "_chem_link",
        "_entity_link",
        "_entity_poly",
        "_entity_poly_seq",
        "_pdbx_chem_comp_descriptor",
        "_pdbx_entity_branch",
        "_pdbx_entity_func_bind_mode",
        "_pdbx_entity_nonpoly",
        "_pdbx_connect_type",
        "_pdbx_ion_info",
        "_pdbx_linked_entity_link_list",
        "_pdbx_modification_feature",
        "_pdbx_nonpoly_scheme",
        "_pdbx_poly_seq_scheme",
        "_pdbx_solvent_info",
        "_pdbx_struct_mod_residue",
    ],
)
def test_chemical_context_categories_fail_instead_of_being_dropped(
    category: str,
) -> None:
    entity, asym = _entity_sections()
    context = _loop((f"{category}.id",), ("1",))
    _assert_code(
        _document(entity, context, asym, _atom_loop(_atom_row(1, "CA"))),
        "unsupported_context_category",
    )


@pytest.mark.parametrize(
    "category",
    [
        "_future_chemistry_context",
        "_pdbx_entity_instance_feature",
        "_pdbx_molecule",
        "_struct_site",
        "_struct_site_gen",
    ],
)
def test_unreviewed_uninterpreted_categories_fail_closed(category: str) -> None:
    entity, asym = _entity_sections()
    unreviewed = _loop((f"{category}.id",), ("1",))
    _assert_code(
        _document(entity, unreviewed, asym, _atom_loop(_atom_row(1, "CA"))),
        "unsupported_uninterpreted_category",
    )


def test_quoted_atom_identity_preserves_apostrophe_hash_backslash_and_control_word() -> None:
    entity, asym = _entity_sections()
    rows = (
        _atom_row(1, '"O5\'"', element="O", auth_atom='"O5\'"'),
        _atom_row(2, "'C#1'", auth_atom="'C#1'"),
        _atom_row(3, r"'C:\atom'", auth_atom=r"'C:\atom'"),
        _atom_row(4, "'loop_'", auth_atom="'loop_'"),
    )
    result = parse_mmcif(_document(entity, asym, _atom_loop(*rows)))
    assert [atom.name for atom in result.system.atoms] == ["O5'", "C#1", r"C:\atom", "loop_"]


def test_entity_identity_conflict_between_atom_site_and_struct_asym_fails() -> None:
    entity, asym = _entity_sections(entity_rows=("1 polymer", "2 polymer"))
    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", entity="2"))),
        "conflicting_entity_identity",
    )


def test_atom_site_entity_and_asym_references_must_resolve_when_categories_exist() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", asym="B"))),
        "unknown_label_asym_id",
    )
    _assert_code(
        _document(
            entity,
            _atom_loop(_atom_row(1, "CA", entity="2")),
        ),
        "unknown_atom_site_entity",
    )


def test_missing_entity_mapping_is_explicitly_unknown_and_blocked() -> None:
    result = parse_mmcif(_document(_atom_loop(_atom_row(1, "CA", entity="?"))))
    assert result.system.residues[0].entity_type == "unknown"
    assert result.coverage.unknown_entity_type_count == 1
    assert "entity_type_unknown_for_some_residues" in result.coverage.blockers


def test_model_topology_and_invariant_metadata_mismatches_fail_closed() -> None:
    entity, asym = _entity_sections()
    _assert_code(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "N", element="N", model=1),
                _atom_row(2, "CA", model=1),
                _atom_row(3, "N", element="N", model=2),
            ),
        ),
        "model_topology_mismatch",
    )
    _assert_code(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "CA", model=1, charge="0"),
                _atom_row(2, "CA", model=2, charge="1"),
            ),
        ),
        "model_atom_identity_mismatch",
    )


def test_model_variant_measurements_are_preserved_without_becoming_identity() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(
            entity,
            asym,
            _atom_loop(
                _atom_row(1, "CA", model=1, occupancy="1.0", b_factor="20.0"),
                _atom_row(2, "CA", model=2, occupancy="0.5", b_factor="35.0"),
            ),
        )
    )
    assert result.system.model_count == 2
    assert result.system.atoms[0].occupancy == 1.0
    assert result.system.atoms[0].b_factor == 20.0
    values_by_model = result.system.atoms[0].metadata["mmcif"]["atom_site_by_model"]
    assert values_by_model[0]["values"]["_atom_site.occupancy"]["value"] == "1.0"
    assert values_by_model[1]["values"]["_atom_site.occupancy"]["value"] == "0.5"
    assert values_by_model[1]["values"]["_atom_site.b_iso_or_equiv"]["value"] == "35.0"
    assert "model_variant_atom_properties_preserved_as_metadata" in result.coverage.blockers


def test_model_zero_is_supported_and_negative_model_id_fails() -> None:
    entity, asym = _entity_sections()
    result = parse_mmcif(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", model=0)))
    )
    assert result.system.provenance.metadata["model_ids"] == [0]
    assert result.system.model_count == 1

    _assert_code(
        _document(entity, asym, _atom_loop(_atom_row(1, "CA", model=-1))),
        "invalid_model_id",
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            _document(
                _loop(
                    ("_atom_site.group_PDB", "_other.id"),
                    (("ATOM 1"),),
                )
            ),
            "mixed_atom_site_loop",
        ),
        (
            _document(
                _loop(("_atom_site.id",), ("1",)),
                _loop(("_atom_site.type_symbol",), ("C",)),
            ),
            "multiple_atom_site_loops",
        ),
        (
            _document("_atom_site.id 1\n#"),
            "scalar_atom_site_not_supported",
        ),
    ],
)
def test_atom_site_representation_failure_corpus(payload: bytes, code: str) -> None:
    _assert_code(payload, code)
