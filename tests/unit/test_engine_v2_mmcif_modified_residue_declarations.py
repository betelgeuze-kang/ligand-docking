from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_modified_residue_declarations as module
from betelgeuze_engine_v2.molecular.mmcif_modified_residue_declarations import (
    MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS,
    MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
    MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS,
    MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID,
    MmcifModifiedResidueDeclarationError,
    mmcif_modified_residue_declaration_document,
    mmcif_modified_residue_declaration_json_bytes,
    parse_mmcif_modified_residue_declarations,
    require_mmcif_modified_residue_declaration_document,
    write_mmcif_modified_residue_declaration_json,
)


def _source(
    rows: tuple[str, ...] = (
        "1 P 1 MSE MET 1 .",
        "2 P 2 SEP SER 2 A",
    ),
    *,
    extra_header: str = "",
    extra_values: tuple[str, ...] = (),
) -> str:
    headers = list(MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS)
    if extra_header:
        headers.append(extra_header)
    rendered_rows = []
    for index, row in enumerate(rows):
        suffix = f" {extra_values[index]}" if extra_values else ""
        rendered_rows.append(f"{row}{suffix}")
    return (
        "data_mod\n"
        "_entry.id MOD\n"
        "#\n"
        "loop_\n"
        "_entity.id\n"
        "_entity.type\n"
        "1 polymer\n"
        "#\n"
        "loop_\n"
        "_struct_asym.id\n"
        "_struct_asym.entity_id\n"
        "P 1\n"
        "#\n"
        "loop_\n"
        "_entity_poly.entity_id\n"
        "_entity_poly.type\n"
        "1 'polypeptide(L)'\n"
        "#\n"
        "loop_\n"
        "_entity_poly_seq.entity_id\n"
        "_entity_poly_seq.num\n"
        "_entity_poly_seq.mon_id\n"
        "_entity_poly_seq.hetero\n"
        "1 1 MSE n\n"
        "1 2 SEP n\n"
        "#\n"
        "loop_\n" + "\n".join(headers) + "\n" + "\n".join(rendered_rows) + "\n#\n"
    )


def _error(source: str, code: str) -> MmcifModifiedResidueDeclarationError:
    with pytest.raises(MmcifModifiedResidueDeclarationError) as exc_info:
        parse_mmcif_modified_residue_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_source_declarations_join_polymer_label_identity_without_promotion() -> None:
    snapshot = parse_mmcif_modified_residue_declarations(_source())
    first, second = snapshot.declarations

    assert first.declaration_id == 1
    assert first.label_asym_id == "P"
    assert first.label_entity_id == "1"
    assert first.label_seq_id == 1
    assert first.label_comp_id == "MSE"
    assert first.parent_comp_id == "MET"
    assert first.model_number == 1
    assert first.pdb_ins_code.state == "not_applicable"
    assert second.label_comp_id == "SEP"
    assert second.parent_comp_id == "SER"
    assert second.model_number == 2
    assert second.pdb_ins_code.state == "known"
    assert second.pdb_ins_code.value == "A"
    assert first.to_dict()["modified_residue_role"] == (
        "source_declared_modified_polymer_component"
    )
    assert first.to_dict()["preparation_disposition"] == "explicitly_unsupported"
    assert (
        "modified_residue_preparation_not_supported"
        in (first.to_dict()["role_blockers"])
    )

    payload = snapshot.to_dict()
    assert payload["declaration_count"] == 2
    assert payload["model_numbers"] == [1, 2]
    for flag in (
        "source_modified_residue_declaration_interpreted",
        "polymer_label_identity_joined",
        "modified_residue_role_source_declared",
        "parent_component_id_preserved",
        "model_number_value_interpreted",
        "insertion_code_marker_interpreted",
    ):
        assert payload[flag] is True
    for flag in (
        "dictionary_conformance_assessed",
        "atom_site_observation_joined",
        "parent_component_chemistry_interpreted",
        "modification_nature_interpreted",
        "auth_label_equivalence_inferred",
        "model_and_insertion_semantics_interpreted",
        "modified_residue_preparation_supported",
        "parameterable",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_multiple_parent_declarations_for_one_modified_component_are_preserved() -> (
    None
):
    snapshot = parse_mmcif_modified_residue_declarations(
        _source(("1 P 1 MSE MET 1 .", "2 P 1 MSE CYS 1 ."))
    )

    assert [row.label_comp_id for row in snapshot.declarations] == ["MSE", "MSE"]
    assert [row.parent_comp_id for row in snapshot.declarations] == ["MET", "CYS"]
    assert len({row.declaration_identity_sha256 for row in snapshot.declarations}) == 2


def test_extra_source_columns_are_bound_but_not_interpreted() -> None:
    source = _source(
        extra_header="_pdbx_struct_mod_residue.details",
        extra_values=("'selenium substitution'", "'phosphorylation'"),
    )
    snapshot = parse_mmcif_modified_residue_declarations(source)
    binding = snapshot.category_binding

    assert binding.interpreted_headers == MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS
    assert binding.uninterpreted_headers == ("_pdbx_struct_mod_residue.details",)
    assert len(binding.row_sha256) == 2
    document_text = json.dumps(
        mmcif_modified_residue_declaration_document(snapshot), sort_keys=True
    )
    assert "selenium substitution" not in document_text
    assert "phosphorylation" not in document_text


def test_reviewed_header_order_can_change_without_crosswiring_values() -> None:
    source = _source(("1 P 1 MSE MET 1 .",))
    original = (
        "\n".join(MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS) + "\n1 P 1 MSE MET 1 ."
    )
    reordered_headers = (
        "_pdbx_struct_mod_residue.label_comp_id",
        "_pdbx_struct_mod_residue.id",
        "_pdbx_struct_mod_residue.parent_comp_id",
        "_pdbx_struct_mod_residue.label_seq_id",
        "_pdbx_struct_mod_residue.pdb_ins_code",
        "_pdbx_struct_mod_residue.label_asym_id",
        "_pdbx_struct_mod_residue.pdb_model_num",
    )
    reordered = "\n".join(reordered_headers) + "\nMSE 1 MET 1 . P 1"
    reordered_source = source.replace(original, reordered, 1)
    assert reordered_source != source

    snapshot = parse_mmcif_modified_residue_declarations(reordered_source)
    declaration = snapshot.declarations[0]
    assert declaration.label_asym_id == "P"
    assert declaration.label_seq_id == 1
    assert declaration.label_comp_id == "MSE"
    document = mmcif_modified_residue_declaration_document(snapshot)
    assert require_mmcif_modified_residue_declaration_document(document) == document


@pytest.mark.parametrize(
    ("old", "new", "code"),
    (
        ("1 P 1 MSE MET 1 .", "1 X 1 MSE MET 1 .", "label_asym_reference_missing"),
        (
            "1 P 1 MSE MET 1 .",
            "1 P 3 MSE MET 1 .",
            "label_sequence_reference_missing",
        ),
        (
            "1 P 1 MSE MET 1 .",
            "1 P 1 MET MET 1 .",
            "label_component_reference_mismatch",
        ),
        (
            "1 P 1 MSE MET 1 .",
            "1 P 1 MSE ? 1 .",
            "required_identity_value_invalid",
        ),
        (
            "1 P 1 MSE MET 1 .",
            "1.0 P 1 MSE MET 1 .",
            "invalid_declaration_id",
        ),
        (
            "1 P 1 MSE MET 1 .",
            "1 P 1 MSE MET 0 .",
            "invalid_model_number_out_of_bounds",
        ),
    ),
)
def test_invalid_or_crosswired_declarations_fail_without_private_echo(
    old: str, new: str, code: str
) -> None:
    source = _source().replace(old, new, 1)
    assert source != _source()
    error = _error(source, code)

    assert new not in error.detail
    assert new not in str(error)


def test_duplicate_ids_and_missing_headers_fail_closed() -> None:
    _error(
        _source(("1 P 1 MSE MET 1 .", "1 P 2 SEP SER 1 .")),
        "duplicate_declaration_id",
    )
    missing_header = _source().replace(
        "_pdbx_struct_mod_residue.parent_comp_id\n",
        "_pdbx_struct_mod_residue.auth_comp_id\n",
        1,
    )
    _error(missing_header, "required_declaration_header_missing")


def test_marker_spelling_is_not_defaulted() -> None:
    quoted = parse_mmcif_modified_residue_declarations(
        _source(("1 P 1 MSE MET 1 '.'",))
    ).declarations[0]
    unknown = parse_mmcif_modified_residue_declarations(
        _source(("1 P 1 MSE MET 1 ?",))
    ).declarations[0]

    assert quoted.pdb_ins_code.state == "known"
    assert quoted.pdb_ins_code.value == "."
    assert quoted.pdb_ins_code.quoted is True
    assert unknown.pdb_ins_code.state == "unknown"


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_modified_residue_declarations(_source())
    document = mmcif_modified_residue_declaration_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_MODIFIED_RESIDUE_DECLARATION_DICTIONARY_ITEMS
    )
    assert require_mmcif_modified_residue_declaration_document(document) == document
    encoded = mmcif_modified_residue_declaration_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_modified_residue_declaration_json(
        tmp_path / "modified-residue-declarations.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".modified-residue-declarations.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["declarations"][0]["preparation_disposition"] = (
        "eligible_for_preparation"
    )
    projection_digest = module._sha256(tampered["declaration_projection"])
    tampered["declaration_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_MODIFIED_RESIDUE_DECLARATION_DOCUMENT_SCHEMA_ID,
            "declaration_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="role boundary mismatch"):
        require_mmcif_modified_residue_declaration_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_modified_residue_declarations(b"data_x")  # type: ignore[arg-type]


def test_dedicated_declaration_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-modified-residue-declarations.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_modified_residue_declarations.py" in source
    assert "test_engine_v2_mmcif_modified_residue_declarations.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
