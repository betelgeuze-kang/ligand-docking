"""Fail-closed contract tests for legacy product intake (P0-3)."""

from __future__ import annotations

import pytest

from betelgeuze_product.legacy_input_contract import (
    LEGACY_INPUT_COMPATIBILITY_ENV,
    REASON_INVALID_BOOLEAN,
    REASON_INVALID_COORDINATE,
    REASON_INVALID_NUMERIC,
    REASON_MISSING_REQUIRED_FIELD,
    LegacyInputContractError,
    LegacyInputPolicy,
    require_field,
    require_fields,
    resolve_legacy_input_policy,
    strict_bool,
    strict_coordinate,
    strict_float,
    strict_int,
)

STRICT = LegacyInputPolicy()
COMPAT = LegacyInputPolicy(compatibility_mode=True)


def test_default_policy_is_fail_closed() -> None:
    policy = resolve_legacy_input_policy(env={})

    assert policy.fail_closed is True
    assert policy.compatibility_mode is False
    assert policy.receipt()["fail_closed"] is True


def test_compatibility_mode_requires_explicit_true_token() -> None:
    assert resolve_legacy_input_policy(env={LEGACY_INPUT_COMPATIBILITY_ENV: "1"}).compatibility_mode is True
    assert resolve_legacy_input_policy(env={LEGACY_INPUT_COMPATIBILITY_ENV: "true"}).compatibility_mode is True
    # Anything unparseable must not silently unlock lenient intake.
    assert resolve_legacy_input_policy(env={LEGACY_INPUT_COMPATIBILITY_ENV: "maybe"}).compatibility_mode is False
    assert resolve_legacy_input_policy(env={LEGACY_INPUT_COMPATIBILITY_ENV: ""}).compatibility_mode is False


def test_explicit_argument_overrides_environment() -> None:
    env = {LEGACY_INPUT_COMPATIBILITY_ENV: "1"}

    assert resolve_legacy_input_policy(compatibility_mode=False, env=env).fail_closed is True


@pytest.mark.parametrize("value", ["", None, "abc", float("nan"), float("inf"), True])
def test_strict_float_fails_closed_on_invalid_numeric(value: object) -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        strict_float(value, field="binding_score", policy=STRICT)

    assert excinfo.value.reason_code == REASON_INVALID_NUMERIC
    assert "binding_score" in excinfo.value.reason_detail


def test_strict_float_accepts_valid_numeric_forms() -> None:
    assert strict_float("1.5", field="f", policy=STRICT) == 1.5
    assert strict_float(-2, field="f", policy=STRICT) == -2.0


def test_strict_float_compatibility_mode_returns_legacy_default() -> None:
    assert strict_float("abc", field="f", policy=COMPAT, default=0.0) == 0.0
    assert strict_float(None, field="f", policy=COMPAT, default=None) is None


@pytest.mark.parametrize("value", ["", None, "abc", 1.5, True])
def test_strict_int_fails_closed_on_invalid_numeric(value: object) -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        strict_int(value, field="ligand_count", policy=STRICT)

    assert excinfo.value.reason_code == REASON_INVALID_NUMERIC


def test_strict_int_accepts_integral_values() -> None:
    assert strict_int("3", field="n", policy=STRICT) == 3
    assert strict_int(4.0, field="n", policy=STRICT) == 4


@pytest.mark.parametrize("value", ["maybe", "0.5", 2, [], object()])
def test_strict_bool_fails_closed_instead_of_truthiness(value: object) -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        strict_bool(value, field="runner_synthetic_input_allowed", policy=STRICT)

    assert excinfo.value.reason_code == REASON_INVALID_BOOLEAN


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("No", False),
        (1, True),
        (0, False),
    ],
)
def test_strict_bool_accepts_canonical_tokens(value: object, expected: bool) -> None:
    assert strict_bool(value, field="flag", policy=STRICT) is expected


def test_strict_bool_compatibility_mode_restores_coercion() -> None:
    assert strict_bool("maybe", field="flag", policy=COMPAT) is True
    assert strict_bool("maybe", field="flag", policy=COMPAT, default=False) is False


@pytest.mark.parametrize(
    "values",
    [
        ["1.0", "2.0"],
        ["1.0", "2.0", "3.0", "4.0"],
        ["1.0", "bad", "3.0"],
        ["1.0", "2.0", ""],
        ["nan", "2.0", "3.0"],
        ["1e12", "2.0", "3.0"],
        [True, 2.0, 3.0],
    ],
)
def test_strict_coordinate_fails_closed_on_invalid_coordinate(values: list[object]) -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        strict_coordinate(values, field="atom_xyz", policy=STRICT)

    assert excinfo.value.reason_code == REASON_INVALID_COORDINATE


def test_strict_coordinate_accepts_valid_triple() -> None:
    assert strict_coordinate(["1.0", 2, "3.5"], field="atom_xyz", policy=STRICT) == (1.0, 2.0, 3.5)


def test_strict_coordinate_compatibility_mode_skips_instead_of_failing() -> None:
    assert strict_coordinate(["1.0", "bad", "3.0"], field="atom_xyz", policy=COMPAT) is None


def test_require_field_fails_closed_on_missing_required_field() -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        require_field({"target_id": "   "}, "target_id", policy=STRICT, context="intake")

    assert excinfo.value.reason_code == REASON_MISSING_REQUIRED_FIELD
    assert "target_id" in excinfo.value.reason_detail


def test_require_field_compatibility_mode_returns_placeholder() -> None:
    assert require_field({}, "resname", policy=COMPAT, default="UNK") == "UNK"


def test_require_fields_reports_every_missing_field() -> None:
    with pytest.raises(LegacyInputContractError) as excinfo:
        require_fields({"family": "gpcr"}, ["family", "target_id", "ligands"], policy=STRICT)

    assert excinfo.value.reason_code == REASON_MISSING_REQUIRED_FIELD
    assert "target_id" in excinfo.value.reason_detail
    assert "ligands" in excinfo.value.reason_detail
    assert "family" not in excinfo.value.reason_detail.split("fields=")[1].split()[0].split(",")


def test_require_fields_passes_when_all_present() -> None:
    require_fields({"family": "gpcr", "target_id": "ADRB2"}, ["family", "target_id"], policy=STRICT)


def test_reason_round_trips_through_structured_reason() -> None:
    error = LegacyInputContractError(f"{REASON_INVALID_NUMERIC}:field=x value='y'")

    assert error.reason_code == REASON_INVALID_NUMERIC
    assert error.reason_detail == "field=x value='y'"
    assert error.reason == f"{REASON_INVALID_NUMERIC}:field=x value='y'"
