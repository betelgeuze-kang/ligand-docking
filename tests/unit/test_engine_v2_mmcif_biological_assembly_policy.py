from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_biological_assembly_policy as module
from betelgeuze_engine_v2.molecular.mmcif_biological_assembly_policy import (
    MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID,
    MmcifBiologicalAssemblyPolicyError,
    mmcif_biological_assembly_policy_document,
    mmcif_biological_assembly_policy_json_bytes,
    parse_mmcif_biological_assembly_policy,
    require_mmcif_biological_assembly_policy_document,
    write_mmcif_biological_assembly_policy_json,
)
from betelgeuze_engine_v2.molecular.mmcif_syntax import CifSyntaxError


def _loop(headers: tuple[str, ...], rows: tuple[dict[str, str], ...]) -> str:
    return (
        "loop_\n"
        + "\n".join(headers)
        + "\n"
        + "\n".join(" ".join(row[header] for header in headers) for row in rows)
        + "\n#\n"
    )


def _definition_row() -> dict[str, str]:
    return {"_pdbx_struct_assembly.id": "PRIVATE_ASSEMBLY"}


def _generator_row(*, asym_id_list: str = "PRIVATE_CHAIN") -> dict[str, str]:
    return {
        "_pdbx_struct_assembly_gen.assembly_id": "PRIVATE_ASSEMBLY",
        "_pdbx_struct_assembly_gen.oper_expression": "PRIVATE_OPERATION",
        "_pdbx_struct_assembly_gen.asym_id_list": asym_id_list,
    }


def _operator_row() -> dict[str, str]:
    return {
        "_pdbx_struct_oper_list.id": "PRIVATE_OPERATION",
        "_pdbx_struct_oper_list.matrix[1][1]": "1",
        "_pdbx_struct_oper_list.matrix[1][2]": "0",
        "_pdbx_struct_oper_list.matrix[1][3]": "0",
        "_pdbx_struct_oper_list.matrix[2][1]": "0",
        "_pdbx_struct_oper_list.matrix[2][2]": "1",
        "_pdbx_struct_oper_list.matrix[2][3]": "0",
        "_pdbx_struct_oper_list.matrix[3][1]": "0",
        "_pdbx_struct_oper_list.matrix[3][2]": "0",
        "_pdbx_struct_oper_list.matrix[3][3]": "1",
        "_pdbx_struct_oper_list.vector[1]": "0",
        "_pdbx_struct_oper_list.vector[2]": "0",
        "_pdbx_struct_oper_list.vector[3]": "0",
    }


def _source(
    *,
    definition: bool = False,
    generator: bool = False,
    operator: bool = False,
    definition_headers: tuple[
        str, ...
    ] = MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
    generator_headers: tuple[
        str, ...
    ] = MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS,
    operator_headers: tuple[str, ...] = MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS,
    generator_row: dict[str, str] | None = None,
) -> str:
    source = "data_assembly_policy\n_entry.id ASSEMBLY\n#\n"
    if definition:
        source += _loop(definition_headers, (_definition_row(),))
    if generator:
        source += _loop(generator_headers, (generator_row or _generator_row(),))
    if operator:
        source += _loop(operator_headers, (_operator_row(),))
    return source


def _error(source: str, code: str) -> MmcifBiologicalAssemblyPolicyError:
    with pytest.raises(MmcifBiologicalAssemblyPolicyError) as exc_info:
        parse_mmcif_biological_assembly_policy(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_absent_optional_declarations_allow_only_this_admission_gate() -> None:
    snapshot = parse_mmcif_biological_assembly_policy(_source())

    assert snapshot.category_bindings == ()
    assert snapshot.declaration_row_count == 0
    assert snapshot.execution_policy_status == (
        "allowed_no_source_biological_assembly_declarations"
    )
    assert snapshot.execution_allowed is True
    assert snapshot.execution_blockers == ()
    payload = snapshot.to_dict()
    assert payload["source_declared_biological_assembly_input"] is False
    assert payload["absence_proves_asymmetric_unit_is_biological_assembly"] is False
    assert payload["coordinates_expanded"] is False


def test_complete_selected_assembly_surface_is_bound_and_blocked() -> None:
    snapshot = parse_mmcif_biological_assembly_policy(
        _source(definition=True, generator=True, operator=True)
    )

    assert snapshot.declaration_row_count == 3
    assert snapshot.present_categories == (
        "_pdbx_struct_assembly",
        "_pdbx_struct_assembly_gen",
        "_pdbx_struct_oper_list",
    )
    assert snapshot.execution_policy_status == (
        "explicitly_unsupported_source_declared_biological_assembly"
    )
    assert snapshot.execution_allowed is False
    assert snapshot.execution_blockers == (
        "source_declared_assembly_metadata_preparation_not_supported",
        "source_declared_assembly_generation_preparation_not_supported",
        "source_declared_coordinate_operations_preparation_not_supported",
    )
    assert [row.row_count for row in snapshot.category_bindings] == [1, 1, 1]
    assert all(len(row.row_sha256[0]) == 64 for row in snapshot.category_bindings)
    payload = snapshot.to_dict()
    for flag in (
        "source_assembly_declaration_presence_classified",
        "complete_selected_assembly_rows_bound",
        "preparation_admission_policy_interpreted",
    ):
        assert payload[flag] is True
    for flag in (
        "assembly_id_interpreted",
        "assembly_generation_expression_interpreted",
        "assembly_asym_id_list_interpreted",
        "operation_matrix_and_vector_values_interpreted",
        "operation_composition_order_interpreted",
        "biological_assembly_correctness_assessed",
        "coordinates_expanded",
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


@pytest.mark.parametrize(
    ("source", "blocker"),
    (
        (
            _source(definition=True),
            "source_declared_assembly_metadata_preparation_not_supported",
        ),
        (
            _source(generator=True),
            "source_declared_assembly_generation_preparation_not_supported",
        ),
        (
            _source(operator=True),
            "source_declared_coordinate_operations_preparation_not_supported",
        ),
    ),
)
def test_each_selected_category_independently_blocks(
    source: str,
    blocker: str,
) -> None:
    snapshot = parse_mmcif_biological_assembly_policy(source)

    assert snapshot.execution_allowed is False
    assert snapshot.execution_blockers == (blocker,)


def test_category_shape_and_token_bounds_are_fail_closed() -> None:
    _error(
        "data_x\n_pdbx_struct_assembly.id PRIVATE\n",
        "assembly_category_must_be_loop",
    )

    missing_header = tuple(
        header
        for header in MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS
        if header != "_pdbx_struct_assembly_gen.asym_id_list"
    )
    _error(
        _source(generator=True, generator_headers=missing_header),
        "unsupported_assembly_headers",
    )

    mixed_headers = MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS + (
        "_custom.value",
    )
    mixed_row = {**_definition_row(), "_custom.value": "X"}
    mixed = (
        "data_x\n_entry.id X\n#\n"
        + _loop(mixed_headers, (mixed_row,))
    )
    _error(mixed, "mixed_assembly_loop")

    duplicate = _source(definition=True) + _loop(
        MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
        (_definition_row(),),
    )
    with pytest.raises(CifSyntaxError, match="duplicate_data_name"):
        parse_mmcif_biological_assembly_policy(duplicate)

    long_row = _generator_row(asym_id_list="X" * 1_025)
    _error(
        _source(generator=True, generator_row=long_row),
        "assembly_token_out_of_bounds",
    )


def test_header_reordering_changes_binding_but_not_policy_result() -> None:
    source = _source(generator=True)
    reordered = _source(
        generator=True,
        generator_headers=tuple(
            reversed(MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS)
        ),
    )
    first = parse_mmcif_biological_assembly_policy(source)
    second = parse_mmcif_biological_assembly_policy(reordered)

    assert first.execution_policy_status == second.execution_policy_status
    assert first.execution_blockers == second.execution_blockers
    assert first.category_bindings[0].headers != second.category_bindings[0].headers
    assert first.source_binding_sha256 != second.source_binding_sha256


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_biological_assembly_policy(
        _source(definition=True, generator=True, operator=True)
    )
    document = mmcif_biological_assembly_policy_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID
    assert document["source_binding"]["dictionary_categories"] == (
        MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DICTIONARY_CATEGORIES
    )
    assert require_mmcif_biological_assembly_policy_document(document) == document
    encoded = mmcif_biological_assembly_policy_json_bytes(snapshot)
    assert json.loads(encoded) == document
    assert b"PRIVATE_ASSEMBLY" not in encoded
    assert b"PRIVATE_CHAIN" not in encoded
    assert b"PRIVATE_OPERATION" not in encoded

    destination = write_mmcif_biological_assembly_policy_json(
        tmp_path / "assembly-policy.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".assembly-policy.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["policy_projection"]["execution_policy_status"] = (
        "allowed_no_source_biological_assembly_declarations"
    )
    tampered["policy_projection"]["execution_allowed"] = True
    tampered["policy_projection"]["execution_blockers"] = []
    tampered["execution_policy_status"] = (
        "allowed_no_source_biological_assembly_declarations"
    )
    tampered["execution_allowed"] = True
    tampered["execution_blockers"] = []
    projection_digest = module._sha256(tampered["policy_projection"])
    tampered["policy_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_DOCUMENT_SCHEMA_ID,
            "policy_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="classification mismatch"):
        require_mmcif_biological_assembly_policy_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_biological_assembly_policy(b"data_x")  # type: ignore[arg-type]


def test_dedicated_policy_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-biological-assembly-policy.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_biological_assembly_policy.py" in source
    assert "test_engine_v2_mmcif_biological_assembly_policy.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
