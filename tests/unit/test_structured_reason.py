from __future__ import annotations

from betelgeuze_product.docking_materialization_errors import DockingMaterializationError
from betelgeuze_product.structured_reason import join_reason, reason_fields, split_reason


def test_split_reason_without_detail() -> None:
    assert split_reason("runner_input_materialization_not_ready") == (
        "runner_input_materialization_not_ready",
        "",
    )


def test_split_reason_with_detail() -> None:
    assert split_reason("runner_profile_not_customer_submission_allowed:profile-a") == (
        "runner_profile_not_customer_submission_allowed",
        "profile-a",
    )


def test_split_reason_preserves_colons_in_detail() -> None:
    code, detail = split_reason("materialized_ligand_count_mismatch:expected=2:observed=1")
    assert code == "materialized_ligand_count_mismatch"
    assert detail == "expected=2:observed=1"


def test_split_reason_handles_empty() -> None:
    assert split_reason("") == ("", "")
    assert split_reason(None) == ("", "")


def test_reason_fields_shape() -> None:
    fields = reason_fields("runner_profile_not_ready:boom")
    assert fields == {
        "reason": "runner_profile_not_ready:boom",
        "reason_code": "runner_profile_not_ready",
        "reason_detail": "boom",
    }


def test_join_reason_roundtrip() -> None:
    assert join_reason("code", "detail") == "code:detail"
    assert join_reason("code", "") == "code"
    code, detail = split_reason(join_reason("a", "b:c"))
    assert (code, detail) == ("a", "b:c")


# --- DockingMaterializationError structured behavior ---


def test_error_single_code_backward_compatible_str() -> None:
    err = DockingMaterializationError("redacted_ligand_source_cannot_be_materialized")
    assert err.reason_code == "redacted_ligand_source_cannot_be_materialized"
    assert err.reason_detail == ""
    assert str(err) == "redacted_ligand_source_cannot_be_materialized"


def test_error_combined_string_is_split() -> None:
    err = DockingMaterializationError("unsupported_ligand_source_for_htvs_materialization:sdf_path")
    assert err.reason_code == "unsupported_ligand_source_for_htvs_materialization"
    assert err.reason_detail == "sdf_path"
    # str() preserves the original combined form for legacy matchers.
    assert str(err) == "unsupported_ligand_source_for_htvs_materialization:sdf_path"


def test_error_explicit_code_and_detail() -> None:
    err = DockingMaterializationError("materialized_ligand_count_mismatch", "expected=2:observed=1")
    assert err.reason_code == "materialized_ligand_count_mismatch"
    assert err.reason_detail == "expected=2:observed=1"
    assert str(err) == "materialized_ligand_count_mismatch:expected=2:observed=1"
    assert err.reason == "materialized_ligand_count_mismatch:expected=2:observed=1"


def test_error_is_value_error() -> None:
    assert isinstance(DockingMaterializationError("x"), ValueError)
