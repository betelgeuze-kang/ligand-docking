from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_missing_atom_residue_policy as module
from betelgeuze_engine_v2.molecular.mmcif_missing_atom_residue_policy import (
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES,
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS,
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID,
    MmcifMissingAtomResiduePolicyError,
    mmcif_missing_atom_residue_policy_document,
    mmcif_missing_atom_residue_policy_json_bytes,
    parse_mmcif_missing_atom_residue_policy,
    require_mmcif_missing_atom_residue_policy_document,
    write_mmcif_missing_atom_residue_policy_json,
)
from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy import (
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
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


def _residue_row(
    *,
    source_id: str = "1",
    occupancy_flag: str = "-0",
    label_comp_id: str = "PRIVATE_RESIDUE",
) -> dict[str, str]:
    return {
        "_pdbx_unobs_or_zero_occ_residues.id": source_id,
        "_pdbx_unobs_or_zero_occ_residues.polymer_flag": "Y",
        "_pdbx_unobs_or_zero_occ_residues.occupancy_flag": occupancy_flag,
        "_pdbx_unobs_or_zero_occ_residues.pdb_model_num": "1",
        "_pdbx_unobs_or_zero_occ_residues.auth_asym_id": "PRIVATE_AUTH_ASYM",
        "_pdbx_unobs_or_zero_occ_residues.auth_comp_id": "PRIVATE_AUTH_COMP",
        "_pdbx_unobs_or_zero_occ_residues.auth_seq_id": "501",
        "_pdbx_unobs_or_zero_occ_residues.pdb_ins_code": ".",
        "_pdbx_unobs_or_zero_occ_residues.label_asym_id": "P",
        "_pdbx_unobs_or_zero_occ_residues.label_comp_id": label_comp_id,
        "_pdbx_unobs_or_zero_occ_residues.label_seq_id": "1",
    }


def _atom_row(
    *,
    source_id: str = "1",
    occupancy_flag: str = "+1",
    label_atom_id: str = "PRIVATE_ATOM",
) -> dict[str, str]:
    return {
        "_pdbx_unobs_or_zero_occ_atoms.id": source_id,
        "_pdbx_unobs_or_zero_occ_atoms.polymer_flag": "Y",
        "_pdbx_unobs_or_zero_occ_atoms.occupancy_flag": occupancy_flag,
        "_pdbx_unobs_or_zero_occ_atoms.pdb_model_num": "1",
        "_pdbx_unobs_or_zero_occ_atoms.auth_asym_id": "PRIVATE_AUTH_ASYM",
        "_pdbx_unobs_or_zero_occ_atoms.auth_comp_id": "PRIVATE_AUTH_COMP",
        "_pdbx_unobs_or_zero_occ_atoms.auth_seq_id": "501",
        "_pdbx_unobs_or_zero_occ_atoms.pdb_ins_code": ".",
        "_pdbx_unobs_or_zero_occ_atoms.auth_atom_id": "PRIVATE_AUTH_ATOM",
        "_pdbx_unobs_or_zero_occ_atoms.label_alt_id": ".",
        "_pdbx_unobs_or_zero_occ_atoms.label_asym_id": "P",
        "_pdbx_unobs_or_zero_occ_atoms.label_comp_id": "PRIVATE_RESIDUE",
        "_pdbx_unobs_or_zero_occ_atoms.label_seq_id": "1",
        "_pdbx_unobs_or_zero_occ_atoms.label_atom_id": label_atom_id,
    }


def _source(
    *,
    residue_rows: tuple[dict[str, str], ...] = (),
    atom_rows: tuple[dict[str, str], ...] = (),
    residue_headers: tuple[str, ...] = MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
    atom_headers: tuple[str, ...] = MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
) -> str:
    source = "data_gaps\n_entry.id GAP\n#\n"
    if residue_rows:
        source += _loop(residue_headers, residue_rows)
    if atom_rows:
        source += _loop(atom_headers, atom_rows)
    return source


def _error(source: str, code: str) -> MmcifMissingAtomResiduePolicyError:
    with pytest.raises(MmcifMissingAtomResiduePolicyError) as exc_info:
        parse_mmcif_missing_atom_residue_policy(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_absent_optional_declarations_allow_only_this_admission_gate() -> None:
    snapshot = parse_mmcif_missing_atom_residue_policy(_source())

    assert snapshot.observations == ()
    assert snapshot.category_bindings == ()
    assert snapshot.execution_policy_status == (
        "allowed_no_source_observation_gap_declarations"
    )
    assert snapshot.execution_allowed is True
    assert snapshot.execution_blockers == ()
    payload = snapshot.to_dict()
    assert payload["source_declared_observation_gap_input"] is False
    assert payload["absence_proves_structure_complete"] is False
    assert payload["missingness_inferred"] is False
    assert payload["missing_atom_or_residue_repaired"] is False


def test_zero_occupancy_residue_and_unobserved_atom_are_both_blocked() -> None:
    snapshot = parse_mmcif_missing_atom_residue_policy(
        _source(residue_rows=(_residue_row(),), atom_rows=(_atom_row(),))
    )

    assert snapshot.residue_declaration_count == 1
    assert snapshot.atom_declaration_count == 1
    assert snapshot.zero_occupancy_declaration_count == 1
    assert snapshot.unobserved_declaration_count == 1
    assert snapshot.execution_policy_status == (
        "explicitly_unsupported_source_declared_observation_gaps"
    )
    assert snapshot.execution_allowed is False
    assert snapshot.execution_blockers == (
        "source_declared_zero_occupancy_residue_preparation_not_supported",
        "source_declared_unobserved_atom_preparation_not_supported",
    )
    residue, atom = snapshot.observations
    assert (residue.occupancy_flag_token, residue.occupancy_flag) == ("-0", 0)
    assert residue.declaration_status == "zero_occupancy"
    assert (atom.occupancy_flag_token, atom.occupancy_flag) == ("+1", 1)
    assert atom.declaration_status == "unobserved"
    assert len(residue.row_sha256) == 64
    assert len(atom.observation_identity_sha256) == 64

    payload = snapshot.to_dict()
    assert payload["declaration_status_counts"] == [
        {
            "declaration_kind": "residue",
            "declaration_status": "zero_occupancy",
            "row_count": 1,
        },
        {
            "declaration_kind": "atom",
            "declaration_status": "zero_occupancy",
            "row_count": 0,
        },
        {
            "declaration_kind": "residue",
            "declaration_status": "unobserved",
            "row_count": 0,
        },
        {
            "declaration_kind": "atom",
            "declaration_status": "unobserved",
            "row_count": 1,
        },
    ]
    for flag in (
        "source_declaration_presence_classified",
        "complete_selected_declaration_rows_bound",
        "occupancy_flag_values_interpreted",
        "unobserved_and_zero_occupancy_status_classified",
        "preparation_admission_policy_interpreted",
    ):
        assert payload[flag] is True
    for flag in (
        "declaration_identity_interpreted",
        "atom_site_coordinates_interpreted",
        "atom_site_occupancy_crosschecked",
        "missingness_inferred",
        "coordinates_generated",
        "chemistry_interpreted",
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_all_category_status_blockers_are_deterministic() -> None:
    snapshot = parse_mmcif_missing_atom_residue_policy(
        _source(
            residue_rows=(
                _residue_row(source_id="1", occupancy_flag="0"),
                _residue_row(source_id="2", occupancy_flag="1"),
            ),
            atom_rows=(
                _atom_row(source_id="1", occupancy_flag="0"),
                _atom_row(source_id="2", occupancy_flag="1"),
            ),
        )
    )

    assert snapshot.execution_blockers == (
        "source_declared_zero_occupancy_residue_preparation_not_supported",
        "source_declared_zero_occupancy_atom_preparation_not_supported",
        "source_declared_unobserved_residue_preparation_not_supported",
        "source_declared_unobserved_atom_preparation_not_supported",
    )


@pytest.mark.parametrize(
    ("occupancy_flag", "code"),
    (
        ("'0'", "invalid_occupancy_flag"),
        ("1.0", "invalid_occupancy_flag"),
        ("?", "invalid_occupancy_flag"),
        ("-1", "occupancy_flag_outside_controlled_vocabulary"),
        ("2", "occupancy_flag_outside_controlled_vocabulary"),
    ),
)
def test_invalid_or_out_of_vocabulary_flags_fail_closed(
    occupancy_flag: str,
    code: str,
) -> None:
    error = _error(
        _source(residue_rows=(_residue_row(occupancy_flag=occupancy_flag),)),
        code,
    )
    assert "PRIVATE" not in error.detail
    assert "PRIVATE" not in str(error)


def test_category_shape_and_token_bounds_are_fail_closed() -> None:
    scalar = (
        "data_x\n"
        "_pdbx_unobs_or_zero_occ_residues.occupancy_flag 0\n"
    )
    _error(scalar, "declaration_category_must_be_loop")

    missing_header = tuple(
        header
        for header in MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS
        if header != "_pdbx_unobs_or_zero_occ_residues.auth_seq_id"
    )
    _error(
        _source(
            residue_rows=(_residue_row(),),
            residue_headers=missing_header,
        ),
        "unsupported_declaration_headers",
    )

    mixed_headers = MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS + ("_custom.value",)
    mixed_row = {**_residue_row(), "_custom.value": "X"}
    _error(
        _source(residue_rows=(mixed_row,), residue_headers=mixed_headers),
        "mixed_declaration_loop",
    )

    duplicate = _source(residue_rows=(_residue_row(),)) + _loop(
        MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
        (_residue_row(source_id="2"),),
    )
    with pytest.raises(CifSyntaxError, match="duplicate_data_name"):
        parse_mmcif_missing_atom_residue_policy(duplicate)

    too_long = _residue_row(label_comp_id="X" * 257)
    _error(
        _source(residue_rows=(too_long,)),
        "declaration_token_out_of_bounds",
    )


def test_header_reordering_changes_binding_but_not_policy_result() -> None:
    source = _source(residue_rows=(_residue_row(),))
    reordered = _source(
        residue_rows=(_residue_row(),),
        residue_headers=tuple(reversed(MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS)),
    )
    first = parse_mmcif_missing_atom_residue_policy(source)
    second = parse_mmcif_missing_atom_residue_policy(reordered)

    assert first.execution_policy_status == second.execution_policy_status
    assert first.execution_blockers == second.execution_blockers
    assert first.category_bindings[0].headers != second.category_bindings[0].headers
    assert first.source_binding_sha256 != second.source_binding_sha256


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_missing_atom_residue_policy(
        _source(residue_rows=(_residue_row(),), atom_rows=(_atom_row(),))
    )
    document = mmcif_missing_atom_residue_policy_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID
    assert document["source_binding"]["dictionary_categories"] == (
        MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_CATEGORIES
    )
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_MISSING_ATOM_RESIDUE_POLICY_DICTIONARY_ITEMS
    )
    assert require_mmcif_missing_atom_residue_policy_document(document) == document
    encoded = mmcif_missing_atom_residue_policy_json_bytes(snapshot)
    assert json.loads(encoded) == document
    assert b"PRIVATE_RESIDUE" not in encoded
    assert b"PRIVATE_ATOM" not in encoded
    assert b"PRIVATE_AUTH" not in encoded

    destination = write_mmcif_missing_atom_residue_policy_json(
        tmp_path / "missing-policy.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".missing-policy.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["policy_projection"]["execution_policy_status"] = (
        "allowed_no_source_observation_gap_declarations"
    )
    tampered["policy_projection"]["execution_allowed"] = True
    tampered["policy_projection"]["execution_blockers"] = []
    tampered["execution_policy_status"] = (
        "allowed_no_source_observation_gap_declarations"
    )
    tampered["execution_allowed"] = True
    tampered["execution_blockers"] = []
    projection_digest = module._sha256(tampered["policy_projection"])
    tampered["policy_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_MISSING_ATOM_RESIDUE_POLICY_DOCUMENT_SCHEMA_ID,
            "policy_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="classification mismatch"):
        require_mmcif_missing_atom_residue_policy_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_missing_atom_residue_policy(b"data_x")  # type: ignore[arg-type]


def test_dedicated_policy_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-missing-atom-residue-policy.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_missing_atom_residue_policy.py" in source
    assert "test_engine_v2_mmcif_missing_atom_residue_policy.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
