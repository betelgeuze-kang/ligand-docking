from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_atom_site_model_policy as module
from betelgeuze_engine_v2.molecular.mmcif_atom_site_model_policy import (
    MAX_MMCIF_ATOM_SITE_MODEL_NUMBER,
    MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM,
    MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS,
    MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
    MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
    MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER,
    MmcifAtomSiteModelPolicyError,
    mmcif_atom_site_model_policy_document,
    mmcif_atom_site_model_policy_json_bytes,
    parse_mmcif_atom_site_model_policy,
    require_mmcif_atom_site_model_policy_document,
    write_mmcif_atom_site_model_policy_json,
)


def _source(rows: tuple[tuple[str, str, str], ...]) -> str:
    rendered = "\n".join(" ".join(row) for row in rows)
    return (
        "data_models\n"
        "_entry.id MODELS\n"
        "#\n"
        "loop_\n"
        "_atom_site.id\n"
        "_atom_site.pdbx_PDB_model_num\n"
        "_atom_site.label_atom_id\n"
        f"{rendered}\n"
        "#\n"
    )


def _error(source: str, code: str) -> MmcifAtomSiteModelPolicyError:
    with pytest.raises(MmcifAtomSiteModelPolicyError) as exc_info:
        parse_mmcif_atom_site_model_policy(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_model_1_only_source_is_the_only_execution_allowed_profile() -> None:
    snapshot = parse_mmcif_atom_site_model_policy(
        _source((("1", "1", "C1"), ("2", "+1", "PRIVATE_ATOM")))
    )

    assert snapshot.model_numbers == (1,)
    assert snapshot.model_row_counts == ((1, 2),)
    assert snapshot.execution_policy_status == "supported_single_model_1"
    assert snapshot.execution_allowed is True
    assert snapshot.execution_blockers == ()
    first, second = snapshot.observations
    assert first.model_number_token == "1"
    assert second.model_number_token == "+1"
    assert second.model_number == 1
    assert first.model_number_quoted is False
    assert first.source_ordinal == 0
    assert len(first.row_sha256) == 64

    payload = snapshot.to_dict()
    assert payload["single_model_input"] is True
    assert payload["multi_model_input"] is False
    assert payload["supported_model_number"] == 1
    assert payload["model_row_counts"] == [{"model_number": 1, "row_count": 2}]
    for flag in (
        "atom_site_model_number_values_interpreted",
        "exact_model_number_tokens_preserved",
        "complete_atom_site_model_set_classified",
        "single_model_1_execution_policy_interpreted",
    ):
        assert payload[flag] is True
    for flag in (
        "dictionary_conformance_assessed",
        "coordinate_values_interpreted",
        "atom_identity_interpreted",
        "cross_category_model_references_reconciled",
        "model_selection_implemented",
        "model_ensemble_semantics_interpreted",
        "trajectory_semantics_interpreted",
        "model_averaging_supported",
        "multimodel_execution_enabled",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_multiple_source_models_are_preserved_and_explicitly_unsupported() -> None:
    snapshot = parse_mmcif_atom_site_model_policy(
        _source(
            (
                ("1", "2", "A"),
                ("2", "1", "B"),
                ("3", "2", "C"),
            )
        )
    )

    assert snapshot.model_numbers == (1, 2)
    assert snapshot.model_row_counts == ((1, 1), (2, 2))
    assert [row.model_number for row in snapshot.observations] == [2, 1, 2]
    assert snapshot.execution_policy_status == "explicitly_unsupported_multimodel"
    assert snapshot.execution_allowed is False
    assert snapshot.execution_blockers == ("multimodel_execution_not_supported",)
    payload = snapshot.to_dict()
    assert payload["single_model_input"] is False
    assert payload["multi_model_input"] is True


@pytest.mark.parametrize("model_number", ("0", "2", "+7"))
def test_single_non_1_model_is_distinct_from_multimodel_but_still_blocked(
    model_number: str,
) -> None:
    snapshot = parse_mmcif_atom_site_model_policy(_source((("1", model_number, "A"),)))

    assert snapshot.model_numbers == (int(model_number),)
    assert snapshot.execution_policy_status == (
        "explicitly_unsupported_single_model_non_1"
    )
    assert snapshot.execution_allowed is False
    assert snapshot.execution_blockers == (
        "model_number_outside_supported_execution_profile",
    )


def test_quoted_integer_spelling_is_preserved_without_claiming_conformance() -> None:
    snapshot = parse_mmcif_atom_site_model_policy(_source((("1", "'1'", "A"),)))
    observation = snapshot.observations[0]

    assert observation.model_number == 1
    assert observation.model_number_token == "1"
    assert observation.model_number_quoted is True
    assert snapshot.to_dict()["dictionary_conformance_assessed"] is False


@pytest.mark.parametrize(
    ("model_number", "code"),
    (
        ("?", "model_number_unavailable"),
        (".", "model_number_unavailable"),
        ("1.0", "invalid_model_number"),
        ("-1", "model_number_out_of_bounds"),
        (str(MAX_MMCIF_ATOM_SITE_MODEL_NUMBER + 1), "model_number_out_of_bounds"),
        ("9" * 300, "model_number_token_too_long"),
    ),
)
def test_invalid_model_number_values_fail_without_private_row_echo(
    model_number: str, code: str
) -> None:
    error = _error(_source((("1", model_number, "PRIVATE_ATOM"),)), code)

    assert "PRIVATE_ATOM" not in error.detail
    assert "PRIVATE_ATOM" not in str(error)


def test_quoted_marker_is_not_treated_as_missing_or_defaulted() -> None:
    _error(_source((("1", "'?'", "A"),)), "invalid_model_number")


def test_atom_site_category_shape_is_bounded() -> None:
    scalar = "data_x\n_atom_site.pdbx_PDB_model_num 1\n"
    _error(scalar, "atom_site_must_be_loop")

    missing_header = "data_x\nloop_\n_atom_site.id\n_atom_site.label_atom_id\n1 A\n#\n"
    _error(missing_header, "model_number_header_missing")

    multiple = (
        _source((("1", "1", "A"),))
        + "loop_\n_atom_site.occupancy\n_atom_site.b_iso_or_equiv\n1.0 10.0\n#\n"
    )
    _error(multiple, "atom_site_loop_count_mismatch")

    mixed = (
        "data_x\nloop_\n_atom_site.id\n_atom_site.pdbx_PDB_model_num\n"
        "_other.value\n1 1 X\n#\n"
    )
    _error(mixed, "mixed_atom_site_loop")


def test_header_reordering_changes_binding_not_interpretation() -> None:
    source = _source((("1", "1", "PRIVATE_ATOM"),))
    reordered = source.replace(
        "_atom_site.id\n_atom_site.pdbx_PDB_model_num\n"
        "_atom_site.label_atom_id\n1 1 PRIVATE_ATOM",
        "_atom_site.label_atom_id\n_atom_site.pdbx_PDB_model_num\n"
        "_atom_site.id\nPRIVATE_ATOM 1 1",
        1,
    )
    assert reordered != source
    first = parse_mmcif_atom_site_model_policy(source)
    second = parse_mmcif_atom_site_model_policy(reordered)

    assert first.model_numbers == second.model_numbers == (1,)
    assert first.execution_policy_status == second.execution_policy_status
    assert first.category_binding.headers != second.category_binding.headers
    assert first.source_binding_sha256 != second.source_binding_sha256


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_atom_site_model_policy(
        _source((("1", "1", "PRIVATE_ATOM"), ("2", "2", "ANOTHER_PRIVATE")))
    )
    document = mmcif_atom_site_model_policy_document(snapshot)

    assert document["schema_id"] == MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_ATOM_SITE_MODEL_POLICY_DICTIONARY_ITEMS
    )
    assert document["source_binding"]["dictionary_minimum_model_number"] == (
        MMCIF_ATOM_SITE_MODEL_NUMBER_MINIMUM
    )
    assert document["supported_model_number"] == (
        MMCIF_ATOM_SITE_MODEL_POLICY_SUPPORTED_MODEL_NUMBER
    )
    assert require_mmcif_atom_site_model_policy_document(document) == document
    encoded = mmcif_atom_site_model_policy_json_bytes(snapshot)
    assert json.loads(encoded) == document
    assert b"PRIVATE_ATOM" not in encoded
    assert b"ANOTHER_PRIVATE" not in encoded

    destination = write_mmcif_atom_site_model_policy_json(
        tmp_path / "model-policy.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".model-policy.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["model_policy_projection"]["execution_policy_status"] = (
        "supported_single_model_1"
    )
    tampered["model_policy_projection"]["execution_allowed"] = True
    tampered["model_policy_projection"]["execution_blockers"] = []
    tampered["execution_policy_status"] = "supported_single_model_1"
    tampered["execution_allowed"] = True
    tampered["execution_blockers"] = []
    projection_digest = module._sha256(tampered["model_policy_projection"])
    tampered["model_policy_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_ATOM_SITE_MODEL_POLICY_DOCUMENT_SCHEMA_ID,
            "model_policy_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="deterministic classification mismatch"):
        require_mmcif_atom_site_model_policy_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_atom_site_model_policy(b"data_x")  # type: ignore[arg-type]


def test_dedicated_model_policy_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-atom-site-model-policy.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_atom_site_model_policy.py" in source
    assert "test_engine_v2_mmcif_atom_site_model_policy.py" in source
    assert "test_engine_v2_mmcif_nonpoly_atom_site_observations.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
