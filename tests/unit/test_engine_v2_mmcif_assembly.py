from __future__ import annotations

import pytest
import torch

import betelgeuze_engine_v2.molecular.pdb_mmcif as pdb_mmcif
from betelgeuze_engine_v2.molecular import (
    StructureParseError,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    parse_mmcif,
    serialize_all_atom_system,
)


ATOM_HEADERS = (
    "_atom_site.group_PDB",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_seq_id",
    "_atom_site.Cartn_x",
    "_atom_site.Cartn_y",
    "_atom_site.Cartn_z",
    "_atom_site.pdbx_PDB_model_num",
)

OPER_TAGS = (
    "_pdbx_struct_oper_list.id",
    "_pdbx_struct_oper_list.matrix[1][1]",
    "_pdbx_struct_oper_list.matrix[1][2]",
    "_pdbx_struct_oper_list.matrix[1][3]",
    "_pdbx_struct_oper_list.matrix[2][1]",
    "_pdbx_struct_oper_list.matrix[2][2]",
    "_pdbx_struct_oper_list.matrix[2][3]",
    "_pdbx_struct_oper_list.matrix[3][1]",
    "_pdbx_struct_oper_list.matrix[3][2]",
    "_pdbx_struct_oper_list.matrix[3][3]",
    "_pdbx_struct_oper_list.vector[1]",
    "_pdbx_struct_oper_list.vector[2]",
    "_pdbx_struct_oper_list.vector[3]",
)


def _loop(headers: tuple[str, ...], rows: tuple[str, ...]) -> str:
    return "\n".join(("loop_", *headers, *rows, "#"))


def _atom_row(
    atom_id: int,
    atom_name: str,
    *,
    asym: str = "A",
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    model: int = 1,
    altloc: str | None = None,
) -> str:
    values = [
        "ATOM",
        str(atom_id),
        "C",
        atom_name,
        "GLY",
        asym,
        "1",
        str(x),
        str(y),
        str(z),
        str(model),
    ]
    if altloc is not None:
        values.append(altloc)
    return " ".join(values)


def _operation_row(
    operation_id: str,
    *,
    rotation: tuple[tuple[str | float, str | float, str | float], ...] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ),
    translation: tuple[str | float, str | float, str | float] = (0.0, 0.0, 0.0),
) -> str:
    values = [
        operation_id,
        *(str(value) for row in rotation for value in row),
        *(str(value) for value in translation),
    ]
    return " ".join(values)


def _assembly_sections(
    *,
    assembly_rows: tuple[str, ...] = ("1",),
    generator_rows: tuple[str, ...] = ("1 1 A",),
    operation_rows: tuple[str, ...] = (_operation_row("1"),),
    operation_headers: tuple[str, ...] = OPER_TAGS,
) -> tuple[str, str, str]:
    return (
        _loop(("_pdbx_struct_assembly.id",), assembly_rows),
        _loop(
            (
                "_pdbx_struct_assembly_gen.assembly_id",
                "_pdbx_struct_assembly_gen.oper_expression",
                "_pdbx_struct_assembly_gen.asym_id_list",
            ),
            generator_rows,
        ),
        _loop(operation_headers, operation_rows),
    )


def _document(
    atom_rows: tuple[str, ...],
    *sections: str,
    atom_headers: tuple[str, ...] = ATOM_HEADERS,
    name: str = "assembly",
) -> bytes:
    return (
        "\n".join(
            (
                f"data_{name}",
                "#",
                *sections,
                _loop(atom_headers, atom_rows),
            )
        )
        + "\n"
    ).encode("ascii")


def _scalar_items(tags: tuple[str, ...], values: tuple[str, ...]) -> str:
    return "\n".join(f"{tag} {value}" for tag, value in zip(tags, values)) + "\n#"


def _assert_code(payload: bytes, code: str, *, assembly_id: str = "1") -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(payload, assembly_id=assembly_id)
    assert exc_info.value.code == code


def test_assembly_is_never_auto_selected_even_when_only_one_is_present() -> None:
    sections = _assembly_sections(
        operation_rows=(_operation_row("1", translation=(10.0, 0.0, 0.0)),),
    )
    payload = _document((_atom_row(1, "CA", x=1.0),), *sections)
    result = parse_mmcif(payload)

    assert result.system.atom_count == 1
    assert result.system.chains[0].chain_id == "A"
    assert result.coverage.coordinate_scope == "deposited_asymmetric_unit"
    assert result.coverage.assembly_status == "present_not_requested"
    assert result.coverage.assembly_output_atom_count == 0
    assert "biological_assembly_not_applied" in result.coverage.blockers
    inventory = {
        item["category"]: item["policy"]
        for item in result.system.metadata["mmcif"]["category_inventory"]
    }
    assert inventory["_pdbx_struct_assembly"] == "deferred_biological_assembly"


def test_explicit_assembly_expands_list_deterministically_without_promotion() -> None:
    sections = _assembly_sections(
        generator_rows=("1 (1,2) A",),
        operation_rows=(
            _operation_row("1"),
            _operation_row("2", translation=(10.0, 0.0, 0.0)),
        ),
    )
    payload = _document((_atom_row(1, "CA", x=1.0),), *sections)
    first = parse_mmcif(payload, assembly_id="1")
    second = parse_mmcif(payload, assembly_id="1")
    system = first.system

    assert system.atom_count == 2
    assert [chain.chain_id for chain in system.chains] == ["ASM000001", "ASM000002"]
    assert torch.allclose(
        system.coordinates[0, :, 0],
        torch.tensor([1.0, 11.0], dtype=torch.float64),
    )
    assert first.coverage.coordinate_scope == "explicit_biological_assembly"
    assert first.coverage.assembly_status == "explicit_id_applied"
    assert first.coverage.requested_assembly_id == "1"
    assert first.coverage.assembly_operation_sequence_count == 2
    assert first.coverage.assembly_operation_application_count == 2
    assert first.coverage.assembly_chain_instance_count == 2
    assert first.coverage.assembly_output_atom_count == 2
    assert "biological_assembly_not_applied" not in first.coverage.blockers
    assert "bond_topology_incomplete_or_unverified" in first.coverage.blockers
    assert system.provenance.preparation_ready is False
    assert system.provenance.claim_safe is False
    assert len(system.bonds) == 0
    assert all(atom.atom_map is None for atom in system.atoms)
    assert first.coverage.canonical_topology_sha256 == (
        second.coverage.canonical_topology_sha256
    )
    assert attached_canonical_topology_sha256_matches(system)

    ledger = system.metadata["mmcif"]["assembly"]
    assert ledger["expression_semantics"] == "pdbx_right_to_left/v1"
    assert ledger["operation_application_count"] == 2
    assert ledger["resource_usage"] == {
        "definition_rows": 1,
        "generator_rows": 1,
        "selected_generator_rows": 1,
        "operator_rows": 2,
        "selected_oper_expression_characters": 5,
        "selected_oper_expression_max_characters": 5,
        "selected_asym_id_list_characters": 1,
        "selected_asym_id_list_max_characters": 1,
        "selected_asym_ids": 1,
        "operation_sequences": 2,
        "operation_applications": 2,
        "chain_instances": 2,
        "topology_atoms": 2,
        "model_atom_rows": 2,
    }
    assert ledger["resource_limits"]["definition_rows"] == 1_024
    assert ledger["resource_limits"]["generator_rows"] == 1_024
    assert ledger["resource_limits"]["operator_rows"] == 4_096
    assert ledger["resource_limits"]["topology_atoms"] == 20_000
    assert ledger["resource_limits"]["model_atom_rows"] == 40_000
    baseline_snapshot = serialize_all_atom_system(system)
    with pytest.raises(TypeError):
        ledger["assembly_id"] = "forged"  # type: ignore[index]
    with pytest.raises(TypeError):
        system.provenance.metadata["coverage"]["assembly_status"] = "forged"  # type: ignore[index]
    assert serialize_all_atom_system(system) == baseline_snapshot
    assert [item["output_chain_id"] for item in ledger["instances"]] == [
        "ASM000001",
        "ASM000002",
    ]
    assert system.chains[0].metadata["assembly_instance"][
        "source_label_asym_id"
    ] == "A"
    inventory = {
        item["category"]: item["policy"]
        for item in system.metadata["mmcif"]["category_inventory"]
    }
    assert inventory["_pdbx_struct_oper_list"] == (
        "partially_interpreted_explicit_biological_assembly_applied"
    )

    restored = deserialize_all_atom_system(serialize_all_atom_system(system))
    assert canonical_topology_sha256(restored) == first.coverage.canonical_topology_sha256
    assert attached_canonical_topology_sha256_matches(restored)


def test_assembly_provenance_records_instance_grouping_not_global_source_order() -> None:
    payload = _document(
        (
            _atom_row(1, "CA", asym="A"),
            _atom_row(2, "N", asym="B", x=1.0),
            _atom_row(3, "CB", asym="A", x=2.0),
        ),
        *_assembly_sections(generator_rows=("1 1 A,B",)),
    )
    system = parse_mmcif(payload, assembly_id="1").system

    assert [
        atom.metadata["mmcif"]["source_atom_site_id"] for atom in system.atoms
    ] == ["1", "3", "2"]
    assert "preserve_source_atom_order_from_first_model" not in (
        system.provenance.operations
    )
    assert "synthesize_canonical_atom_serials_from_first_model_order" not in (
        system.provenance.operations
    )
    assert "reorder_atoms_by_assembly_instance_then_source_order/v1" in (
        system.provenance.operations
    )
    assert "preserve_source_atom_order_within_each_assembly_instance/v1" in (
        system.provenance.operations
    )
    assert system.provenance.operations == (
        "parse_cif_1_1_block_structure",
        "parse_pdbx_atom_site_label_identity",
        "align_models_by_canonical_label_identity",
        "parse_explicit_pdbx_biological_assembly/v1",
        "compose_pdbx_oper_expression_right_to_left/v1",
        "expand_explicit_biological_assembly/v1",
        "reorder_atoms_by_assembly_instance_then_source_order/v1",
        "preserve_source_atom_order_within_each_assembly_instance/v1",
        "synthesize_assembly_chain_ids/v1",
        "synthesize_canonical_atom_serials_from_assembly_instance_order/v1",
    )


def test_cartesian_operation_composition_is_right_to_left_and_noncommutative() -> None:
    rotation_z_90 = (
        (0.0, -1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    sections = _assembly_sections(
        generator_rows=("1 (A)(B) A",),
        operation_rows=(
            _operation_row("A", translation=(10.0, 0.0, 0.0)),
            _operation_row("B", rotation=rotation_z_90),
        ),
    )
    payload = _document((_atom_row(1, "CA", x=1.0),), *sections)
    result = parse_mmcif(payload, assembly_id="1")
    assert torch.allclose(
        result.system.coordinates[0, 0],
        torch.tensor([10.0, 1.0, 0.0], dtype=torch.float64),
        atol=1.0e-12,
        rtol=0.0,
    )
    assert result.system.metadata["mmcif"]["assembly"]["instances"][0][
        "operation_sequence"
    ] == ["A", "B"]


@pytest.mark.parametrize("operation_id", ["X-1", "P*", "A/B:2"])
def test_pdbx_character_code_operation_ids_are_supported(operation_id: str) -> None:
    sections = _assembly_sections(
        generator_rows=(f"1 ({operation_id}) A",),
        operation_rows=(_operation_row(operation_id),),
    )
    result = parse_mmcif(
        _document((_atom_row(1, "CA"),), *sections),
        assembly_id="1",
    )
    assert result.system.metadata["mmcif"]["assembly"]["instances"][0][
        "operation_sequence"
    ] == [operation_id]


def test_operation_identifier_whitespace_cannot_merge_around_hyphen() -> None:
    sections = _assembly_sections(
        generator_rows=("1 '(X - 1)' A",),
        operation_rows=(_operation_row("X-1"),),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        "invalid_oper_expression",
    )


@pytest.mark.parametrize("expression", ["(01-03)", "01-03"])
def test_ambiguous_noncanonical_numeric_ranges_fail_closed(expression: str) -> None:
    sections = _assembly_sections(
        generator_rows=(f"1 {expression} A",),
        operation_rows=(_operation_row("01-03"),),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        "invalid_oper_expression",
    )


@pytest.mark.parametrize("operation_id", ["P?", "P=", "P^"])
def test_operation_ids_outside_pdbx_id_grammar_fail_closed(
    operation_id: str,
) -> None:
    sections = _assembly_sections(
        generator_rows=(f"1 '({operation_id})' A",),
        operation_rows=(_operation_row(operation_id),),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        "invalid_oper_expression",
    )


def test_invalid_unused_operation_id_is_rejected_from_operator_list() -> None:
    sections = _assembly_sections(
        generator_rows=("1 1 A",),
        operation_rows=(_operation_row("1"), _operation_row("P?")),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        "invalid_assembly_operator",
    )


def test_assembly_asym_ids_use_label_not_author_namespace() -> None:
    headers = ATOM_HEADERS + ("_atom_site.auth_asym_id",)
    atom_row = _atom_row(1, "CA", asym="A") + " X"
    sections = _assembly_sections(generator_rows=("1 1 A",))
    result = parse_mmcif(
        _document((atom_row,), *sections, atom_headers=headers),
        assembly_id="1",
    )
    assert result.system.chains[0].metadata["assembly_instance"][
        "source_label_asym_id"
    ] == "A"
    assert result.system.chains[0].metadata["auth_asym_ids"] == ["X"]

    wrong_namespace = _assembly_sections(generator_rows=("1 1 X",))
    _assert_code(
        _document((atom_row,), *wrong_namespace, atom_headers=headers),
        "unknown_assembly_asym_id",
    )


def test_scalar_single_assembly_generator_and_operator_are_supported() -> None:
    operation_values = tuple(_operation_row("1").split())
    sections = (
        "_pdbx_struct_assembly.id 1\n#",
        _scalar_items(
            (
                "_pdbx_struct_assembly_gen.assembly_id",
                "_pdbx_struct_assembly_gen.oper_expression",
                "_pdbx_struct_assembly_gen.asym_id_list",
            ),
            ("1", "1", "A"),
        ),
        _scalar_items(OPER_TAGS, operation_values),
    )
    result = parse_mmcif(
        _document((_atom_row(1, "CA", x=2.0),), *sections),
        assembly_id="1",
    )
    assert result.system.atom_count == 1
    assert result.system.chains[0].chain_id == "ASM000001"
    assert result.system.coordinates[0, 0, 0] == 2.0


def test_ranges_asym_lists_and_multiple_models_use_stable_instance_order() -> None:
    sections = _assembly_sections(
        generator_rows=("1 (1-2) A,B",),
        operation_rows=(
            _operation_row("1"),
            _operation_row("2", translation=(5.0, 0.0, 0.0)),
        ),
    )
    atoms = (
        _atom_row(1, "CA", asym="A", x=0.0, model=1),
        _atom_row(2, "CB", asym="B", x=1.0, model=1),
        _atom_row(3, "CA", asym="A", x=0.5, model=2),
        _atom_row(4, "CB", asym="B", x=1.5, model=2),
    )
    result = parse_mmcif(_document(atoms, *sections), assembly_id="1")
    assert result.system.coordinates.shape == (2, 4, 3)
    assert [chain.chain_id for chain in result.system.chains] == [
        "ASM000001",
        "ASM000002",
        "ASM000003",
        "ASM000004",
    ]
    assert torch.allclose(
        result.system.coordinates[:, :, 0],
        torch.tensor(
            [[0.0, 1.0, 5.0, 6.0], [0.5, 1.5, 5.5, 6.5]],
            dtype=torch.float64,
        ),
    )
    assert result.coverage.assembly_operation_sequence_count == 2
    assert result.coverage.assembly_chain_instance_count == 4


def test_altloc_selection_precedes_assembly_expansion() -> None:
    sections = _assembly_sections()
    headers = ATOM_HEADERS + ("_atom_site.label_alt_id",)
    atoms = (
        _atom_row(1, "CA", x=1.0, altloc="A"),
        _atom_row(2, "CA", x=2.0, altloc="B"),
    )
    result = parse_mmcif(
        _document(atoms, *sections, atom_headers=headers),
        altloc_id="B",
        assembly_id="1",
    )
    assert result.system.atom_count == 1
    assert result.system.atoms[0].altloc == "B"
    assert result.system.coordinates[0, 0, 0] == 2.0
    assert result.coverage.altloc_status == "explicit_id_selected"
    assert result.coverage.assembly_status == "explicit_id_applied"


@pytest.mark.parametrize(
    ("sections", "assembly_id", "code"),
    [
        (_assembly_sections(), "missing", "assembly_id_not_found"),
        (
            _assembly_sections(generator_rows=("1 (9) A",)),
            "1",
            "unknown_assembly_operator_id",
        ),
        (
            _assembly_sections(generator_rows=("1 1 Z",)),
            "1",
            "unknown_assembly_asym_id",
        ),
        (
            _assembly_sections(generator_rows=("1 (3-1) A",)),
            "1",
            "descending_oper_range",
        ),
        (
            _assembly_sections(generator_rows=("1 (1,,2) A",)),
            "1",
            "invalid_oper_expression",
        ),
        (
            _assembly_sections(
                operation_rows=(
                    _operation_row(
                        "1",
                        rotation=((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                    ),
                ),
            ),
            "1",
            "non_rigid_assembly_operator",
        ),
        (
            _assembly_sections(generator_rows=("1 1 A", "1 1 A")),
            "1",
            "duplicate_assembly_instance",
        ),
    ],
)
def test_assembly_failure_corpus(
    sections: tuple[str, str, str],
    assembly_id: str,
    code: str,
) -> None:
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        code,
        assembly_id=assembly_id,
    )


def test_incomplete_operator_and_full_matrix_representation_fail_closed() -> None:
    incomplete_headers = OPER_TAGS[:-1]
    incomplete_row = " ".join(_operation_row("1").split()[:-1])
    incomplete = _assembly_sections(
        operation_headers=incomplete_headers,
        operation_rows=(incomplete_row,),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *incomplete),
        "incomplete_assembly_operator",
    )

    full_matrix_headers = OPER_TAGS + ("_pdbx_struct_oper_list.full_matrix",)
    full_matrix = _assembly_sections(
        operation_headers=full_matrix_headers,
        operation_rows=(_operation_row("1") + " 1.0",),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *full_matrix),
        "unsupported_assembly_full_matrix",
    )


@pytest.mark.parametrize("missing_value", ["?", "."])
def test_missing_optional_full_matrix_values_are_ignored(missing_value: str) -> None:
    full_matrix_headers = OPER_TAGS + ("_pdbx_struct_oper_list.full_matrix",)
    sections = _assembly_sections(
        operation_headers=full_matrix_headers,
        operation_rows=(_operation_row("1") + f" {missing_value}",),
    )
    result = parse_mmcif(
        _document((_atom_row(1, "CA"),), *sections),
        assembly_id="1",
    )
    assert result.coverage.assembly_status == "explicit_id_applied"


def test_operation_expression_whitespace_cannot_merge_operator_identifiers() -> None:
    sections = _assembly_sections(
        generator_rows=("1 '1 2' A",),
        operation_rows=(
            _operation_row("1"),
            _operation_row("2"),
            _operation_row("12"),
        ),
    )
    _assert_code(
        _document((_atom_row(1, "CA"),), *sections),
        "invalid_oper_expression",
    )


def test_missing_assembly_categories_fail_closed_in_dependency_order() -> None:
    atoms = (_atom_row(1, "CA"),)
    _assert_code(_document(atoms), "assembly_definition_missing")

    definition = _loop(("_pdbx_struct_assembly.id",), ("1",))
    _assert_code(_document(atoms, definition), "assembly_generator_missing")

    generator = _loop(
        (
            "_pdbx_struct_assembly_gen.assembly_id",
            "_pdbx_struct_assembly_gen.oper_expression",
            "_pdbx_struct_assembly_gen.asym_id_list",
        ),
        ("1 1 A",),
    )
    _assert_code(
        _document(atoms, definition, generator),
        "assembly_operator_list_missing",
    )


def test_operator_numeric_uncertainty_is_applied_but_remains_blocked() -> None:
    uncertain_rotation = (
        ("1.0(1)", 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    sections = _assembly_sections(
        operation_rows=(_operation_row("1", rotation=uncertain_rotation),),
    )
    result = parse_mmcif(
        _document((_atom_row(1, "CA"),), *sections),
        assembly_id="1",
    )
    assert "assembly_operation_numeric_standard_uncertainty_not_propagated" in (
        result.coverage.blockers
    )


def test_assembly_resource_caps_fail_before_output_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(
        (_atom_row(1, "CA"),),
        *_assembly_sections(
            generator_rows=("1 (1,2) A",),
            operation_rows=(_operation_row("1"), _operation_row("2")),
        ),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES", 1)
    _assert_code(payload, "assembly_expression_limit_exceeded")

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES", 10)
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES", 1)
    _assert_code(payload, "assembly_chain_instance_limit_exceeded")

    atom_payload = _document(
        (_atom_row(1, "CA"), _atom_row(2, "CB", x=1.0)),
        *_assembly_sections(),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES", 10)
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS", 1)
    _assert_code(atom_payload, "assembly_atom_limit_exceeded")

    model_payload = _document(
        (
            _atom_row(1, "CA", model=1),
            _atom_row(2, "CA", x=0.5, model=2),
        ),
        *_assembly_sections(),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS", 10)
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_MMCIF_ASSEMBLY_OUTPUT_MODEL_ATOM_ROWS",
        1,
    )
    _assert_code(model_payload, "assembly_model_atom_limit_exceeded")


def test_operation_application_cap_precedes_cartesian_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS",
        1,
    )

    def forbidden_product(*args: object, **kwargs: object) -> object:
        pytest.fail("Cartesian product must not be materialized after the cap fails")

    monkeypatch.setattr(pdb_mmcif.itertools, "product", forbidden_product)
    with pytest.raises(StructureParseError) as exc_info:
        pdb_mmcif._parse_mmcif_oper_expression(  # noqa: SLF001
            pdb_mmcif.CifToken("(1)(1)", 1, 1)
        )
    assert exc_info.value.code == "assembly_operation_application_limit_exceeded"


def test_assembly_plan_caps_lists_and_aggregate_work_before_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    two_chain_payload = _document(
        (_atom_row(1, "CA", asym="A"), _atom_row(2, "N", asym="B")),
        *_assembly_sections(generator_rows=("1 1 A,B",)),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS", 2)
    _assert_code(two_chain_payload, "assembly_asym_id_list_limit_exceeded")

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS", 4_096)
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR", 1)
    _assert_code(two_chain_payload, "assembly_asym_id_list_limit_exceeded")

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR", 4_096)

    def forbidden_expansion(*args: object, **kwargs: object) -> object:
        pytest.fail("assembly expansion must not run after plan resource caps fail")

    monkeypatch.setattr(pdb_mmcif, "_expand_mmcif_assembly_models", forbidden_expansion)
    aggregate_payload = _document(
        (_atom_row(1, "CA", asym="A"), _atom_row(2, "N", asym="B")),
        *_assembly_sections(generator_rows=("1 1 A", "1 1 B")),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES", 1)
    _assert_code(aggregate_payload, "assembly_chain_instance_limit_exceeded")

    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES", 4_096)
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS",
        1,
    )
    _assert_code(aggregate_payload, "assembly_operation_application_limit_exceeded")


def test_assembly_category_row_caps_precede_preservation_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(
        (_atom_row(1, "CA", asym="A"),),
        *_assembly_sections(generator_rows=("1 1 A", "1 1 A")),
    )
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS", 1)

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("assembly metadata must be capped before nested preservation")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(payload)
    assert exc_info.value.code == "assembly_generator_limit_exceeded"


def test_assembly_public_argument_is_strict() -> None:
    payload = _document((_atom_row(1, "CA"),), *_assembly_sections())
    with pytest.raises(TypeError, match="assembly_id must be a string or None"):
        parse_mmcif(payload, assembly_id=1)  # type: ignore[arg-type]
    for value in ("", "bad id", "x" * 257):
        with pytest.raises(StructureParseError) as exc_info:
            parse_mmcif(payload, assembly_id=value)
        assert exc_info.value.code == "invalid_assembly_id"
