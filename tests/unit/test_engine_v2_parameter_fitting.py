from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2 import engine as engine_module
from betelgeuze_engine_v2.forcefield import fitting as fitting_module
from betelgeuze_engine_v2.forcefield import (
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    PARAMETER_FIT_RUN_RECEIPT_SCHEMA_ID,
    SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1,
    SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID_1_1,
    SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256,
    SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1,
    ParameterFitContractError,
    ParameterFitRunReceipt,
    SyntheticParameterFitBundle,
    analyze_exact_methane_bond_angle_parameter_assignment,
    run_synthetic_exact_methane_harmonic_fit,
    serialize_exact_methane_bond_angle_parameter_set,
    serialize_parameter_fit_run_receipt,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_2_parameter_pipeline"
METHANE = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "v2_1_ingest_corpus"
    / "methane_explicit_h.sdf"
)


class _AlwaysEqualString(str):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


class _AlwaysEqualTuple(tuple):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


class _AlwaysEqualFraction(Fraction):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


class _AlwaysEqualBytes(bytes):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


class _AlwaysEqualObject:
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


def _fixture_bytes() -> tuple[bytes, bytes, bytes]:
    return tuple(
        (FIXTURES / name).read_bytes()
        for name in (
            "synthetic_harmonic_rows.json",
            "synthetic_dataset_manifest.json",
            "synthetic_split_manifest.json",
        )
    )  # type: ignore[return-value]


def _form_bound_bundle() -> SyntheticParameterFitBundle:
    return run_synthetic_exact_methane_harmonic_fit(
        *_fixture_bytes(),
        output_parameter_artifact_schema_version=(
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
        ),
    )


def _core_sha(document: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _canonical_bundle_bytes(bundle: SyntheticParameterFitBundle) -> bytes:
    return json.dumps(
        bundle.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _rebundle(
    rows_document: dict[str, object],
    *,
    fit_row_ids: list[str] | None = None,
    holdout_row_ids: list[str] | None = None,
) -> tuple[bytes, bytes, bytes]:
    rows_data = json.dumps(
        rows_document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    rows_sha = hashlib.sha256(rows_data).hexdigest()
    rows = rows_document["rows"]
    assert isinstance(rows, list)
    dataset_core: dict[str, object] = {
        "schema_id": "betelgeuze.parameter_fit_dataset_manifest/1.0.0",
        "dataset_id": "nonphysical_exact_methane_harmonic_contract_fixture",
        "dataset_version": "1.0.0",
        "artifact_purpose": "contract_fixture_only",
        "scientific_status": "nonphysical_test_fixture",
        "rows_artifact_name": "synthetic_harmonic_rows.json",
        "rows_sha256": rows_sha,
        "row_count": len(rows),
        "bond_row_count": sum(row["term_kind"] == "bond" for row in rows),
        "angle_row_count": sum(row["term_kind"] == "angle" for row in rows),
        "license_review_status": "not_applicable_nonphysical_fixture",
        "source_authentication_status": "not_authenticated",
        "runtime_eligible": False,
    }
    dataset_sha = _core_sha(dataset_core)
    dataset_data = json.dumps(
        {**dataset_core, "manifest_sha256": dataset_sha},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    split_core: dict[str, object] = {
        "schema_id": "betelgeuze.parameter_fit_split_manifest/1.0.0",
        "split_id": "nonphysical_exact_methane_harmonic_fit_holdout_v1",
        "split_version": "1.0.0",
        "dataset_id": dataset_core["dataset_id"],
        "dataset_version": dataset_core["dataset_version"],
        "dataset_manifest_sha256": dataset_sha,
        "rows_sha256": rows_sha,
        "split_policy_id": "fixed_explicit_row_id_fit_holdout/1.0.0",
        "fit_row_ids": fit_row_ids
        or [
            "angle_001",
            "angle_002",
            "angle_003",
            "bond_001",
            "bond_002",
            "bond_003",
        ],
        "holdout_row_ids": holdout_row_ids or ["angle_004", "bond_004"],
        "artifact_purpose": "contract_fixture_only",
        "runtime_eligible": False,
    }
    split_data = json.dumps(
        {**split_core, "manifest_sha256": _core_sha(split_core)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return rows_data, dataset_data, split_data


def test_synthetic_fit_recomputes_exact_parameters_and_hash_dag() -> None:
    bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    parameter_set = bundle.parameter_set
    receipt = bundle.receipt
    payload = receipt.to_dict()

    assert payload["schema_id"] == PARAMETER_FIT_RUN_RECEIPT_SCHEMA_ID
    assert receipt.dataset_manifest.rows_sha256 == (
        "9f517d649ac2b9765f4cb255c0f72793069dc046af9fe1e2a40418d503d5f58a"
    )
    assert receipt.dataset_manifest.manifest_sha256 == (
        "e8133626102289485d1452d7d1a9ebc8eca722d7d03bcbd68d373d5f87adcd3b"
    )
    assert receipt.split_manifest.manifest_sha256 == (
        "45b85e852c080cbd6c45db26435a921c98d0c02bfc3b7bf40b7c12ca5edc232a"
    )
    assert SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256 == (
        "fbba0362c86e749bbd3dac98412cf648d3c7f7ac98346e90f68f6e65d122ea44"
    )
    assert receipt.bond_coefficients == (
        Fraction(1),
        Fraction(-2),
        Fraction(1),
    )
    assert receipt.angle_coefficients == (
        Fraction(2),
        Fraction(-4),
        Fraction(2),
    )
    assert receipt.bond_equilibrium == receipt.angle_equilibrium == Fraction(1)
    assert receipt.bond_force_constant == Fraction(2)
    assert receipt.angle_force_constant == Fraction(4)
    assert receipt.max_holdout_absolute_residual == 0
    assert payload["bond_equilibrium_ieee754_binary64_be"] == "3ff0000000000000"
    assert payload["bond_force_constant_ieee754_binary64_be"] == (
        "4000000000000000"
    )
    assert payload["angle_force_constant_ieee754_binary64_be"] == (
        "4010000000000000"
    )
    assert parameter_set.parameter_payload_sha256 == (
        "6ac3561a7ce577e5adad9c045d19518a320ca23b3b2724307473f902f6bc4166"
    )
    assert receipt.receipt_sha256 == (
        "01923526e06d0ed516c1dacebaa7ddfae792e71a2157da9bf62acc1745ec0141"
    )
    assert parameter_set.parameter_set_sha256 == (
        "497d452d7bf7a510ba5a5b1e5c023988cd09921fc8e2b3bcd727b36a1613040d"
    )
    assert bundle.bundle_sha256 == (
        "ef4b6e8635d3b8a509c18cd37f5a7bb7a54081a656332223087d6a2619025e5c"
    )
    assert hashlib.sha256(
        serialize_parameter_fit_run_receipt(receipt)
    ).hexdigest() == (
        "8c66c0c89b65597200e129e45773561afd12547d0406390e3f86bef646a373b6"
    )
    assert hashlib.sha256(
        serialize_exact_methane_bond_angle_parameter_set(parameter_set)
    ).hexdigest() == (
        "24e7031d3911aec10f9d73f7e5f0cc0cf3dc1a6d74c8ac1e199aa33f8e5d53e0"
    )
    assert hashlib.sha256(_canonical_bundle_bytes(bundle)).hexdigest() == (
        "da86537ed8a2b09bb097a7e99d2426906c27b24d36045115ce5fa418cc1a3112"
    )
    assert "parameter_set_sha256" not in receipt._core_dict()
    assert parameter_set.fit_receipt_sha256 == receipt.receipt_sha256
    assert parameter_set.fit_protocol_id == payload["fit_protocol"]["protocol_id"]
    assert payload["fit_protocol_sha256"] == _core_sha(payload["fit_protocol"])


def test_form_bound_1_1_fit_has_separate_frozen_protocol_and_hash_dag() -> None:
    bundle = _form_bound_bundle()
    parameter_set = bundle.parameter_set
    receipt = bundle.receipt
    payload = receipt.to_dict()
    protocol = payload["fit_protocol"]

    assert receipt.output_parameter_artifact_schema_version == "1.1.0"
    assert parameter_set.artifact_schema_version == "1.1.0"
    assert parameter_set.schema_id == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
    )
    assert parameter_set.functional_form_id == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert protocol["schema_id"] == (
        SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID_1_1
    )
    assert protocol["protocol_id"] == SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1
    assert protocol["output_parameter_set_schema_id"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
    )
    assert protocol["functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert payload["output_parameter_set_schema_id"] == (
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
    )
    assert payload["fit_protocol_sha256"] == (
        SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1
    ) == "99628ebbb81e66e1901bf2bc33ac5904fe223fcd6af9237acc6867aeb90075e5"
    assert parameter_set.parameter_payload_sha256 == (
        "a9bed93a9e5f42c94d869aca048bc0af332187ed73380351e762782896f23984"
    )
    assert receipt.receipt_sha256 == (
        "23710162841aacdcad5338f84cc1cac67720976c8ad9e25235b44f88e4bd53d7"
    )
    assert parameter_set.parameter_set_sha256 == (
        "80cbd5971f11d0dc35b7c315ad4cd68e6b56d1abbaae8efd4f63838464dca0ad"
    )
    assert bundle.bundle_sha256 == (
        "ebab515183c7b0ebacd621baa333a3d817710e367817fcc7c63c58ae4f5d6112"
    )
    assert hashlib.sha256(
        serialize_parameter_fit_run_receipt(receipt)
    ).hexdigest() == (
        "b96ad858f92d403b7205191b9b110a8b16d76ad9ef528612724b392cc5b46a3f"
    )
    assert hashlib.sha256(
        serialize_exact_methane_bond_angle_parameter_set(parameter_set)
    ).hexdigest() == (
        "a10b1a0b108a260da59a97875fce65c682c2f71cb114b2963e88b0c140248839"
    )
    assert hashlib.sha256(_canonical_bundle_bytes(bundle)).hexdigest() == (
        "1bf4284c28c5f438381f4d22a6c69b45ca84d1177ba3b49e79aa5dc1a445c4ea"
    )
    assert _form_bound_bundle().to_dict() == bundle.to_dict()
    assert parameter_set.parameterability_assessed is False
    assert parameter_set.parameterizable is False
    assert parameter_set.runtime_eligible is False
    assert parameter_set.execution_authorized is False
    assert parameter_set.claim_safe is False
    bundle_payload = bundle.to_dict()
    assert bundle_payload["energy_evaluation_authorized"] is False
    assert bundle_payload["force_evaluation_authorized"] is False
    assert bundle_payload["minimization_authorized"] is False
    assert bundle_payload["simulation_ready"] is False
    assert bundle_payload["claim_safe"] is False


def test_dataset_row_ids_are_split_neutral_and_holdout_is_not_fit_input() -> None:
    rows_data, _, _ = _fixture_bytes()
    rows = json.loads(rows_data)["rows"]
    assert all("fit" not in row["row_id"] for row in rows)
    assert all("holdout" not in row["row_id"] for row in rows)

    rows_document = json.loads(rows_data)
    for row in rows_document["rows"]:
        if row["row_id"] == "bond_004":
            row["energy_decimal"] = "2"
    with pytest.raises(ParameterFitContractError, match="holdout residual"):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))


def test_fit_values_are_recomputed_instead_of_copied_from_fixture() -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    for row in rows_document["rows"]:
        if row["row_id"] in {"bond_001", "bond_003"}:
            row["energy_decimal"] = "0.5"
        elif row["row_id"] == "bond_004":
            row["energy_decimal"] = "2"
    changed = run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))
    baseline = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())

    assert changed.parameter_set.bond_parameter.force_constant_kj_mol_angstrom2 == 4.0
    assert changed.parameter_set.angle_parameter == baseline.parameter_set.angle_parameter
    assert changed.parameter_set.parameter_payload_sha256 != (
        baseline.parameter_set.parameter_payload_sha256
    )
    assert changed.receipt.receipt_sha256 != baseline.receipt.receipt_sha256


def test_split_change_preserves_fit_when_exact_rows_are_still_sufficient() -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    changed = run_synthetic_exact_methane_harmonic_fit(
        *_rebundle(
            rows_document,
            fit_row_ids=[
                "angle_001",
                "angle_002",
                "angle_004",
                "bond_001",
                "bond_002",
                "bond_004",
            ],
            holdout_row_ids=["angle_003", "bond_003"],
        )
    )
    baseline = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())

    assert changed.parameter_set.parameter_payload_sha256 == (
        baseline.parameter_set.parameter_payload_sha256
    )
    assert changed.receipt.split_manifest.manifest_sha256 != (
        baseline.receipt.split_manifest.manifest_sha256
    )
    assert changed.receipt.receipt_sha256 != baseline.receipt.receipt_sha256
    assert changed.parameter_set.parameter_set_sha256 != (
        baseline.parameter_set.parameter_set_sha256
    )


@pytest.mark.parametrize(
    ("row_id", "energy", "message"),
    [
        ("angle_001", "1.5", "zero additive offset"),
        ("bond_001", "0", "zero additive offset"),
        ("bond_002", "0.5", "curvature"),
    ],
)
def test_invalid_quadratic_fits_fail_closed(
    row_id: str,
    energy: str,
    message: str,
) -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    for row in rows_document["rows"]:
        if row["row_id"] == row_id:
            row["energy_decimal"] = energy
    with pytest.raises(ParameterFitContractError, match=message):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))


def test_angle_rows_and_fitted_equilibrium_are_strictly_below_pi() -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    for row in rows_document["rows"]:
        if row["row_id"] == "angle_004":
            row["coordinate_decimal"] = "4"
            row["energy_decimal"] = "18"
    with pytest.raises(ParameterFitContractError, match="angle.*pi"):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))

    rows_document = json.loads(_fixture_bytes()[0])
    angle_values = {
        "angle_001": ("2.8", "0.16"),
        "angle_002": ("3", "0.04"),
        "angle_003": ("3.1", "0.01"),
        "angle_004": ("2.9", "0.09"),
    }
    for row in rows_document["rows"]:
        if row["row_id"] in angle_values:
            coordinate, energy = angle_values[row["row_id"]]
            row["coordinate_decimal"] = coordinate
            row["energy_decimal"] = energy
    with pytest.raises(ParameterFitContractError, match="angle equilibrium.*pi"):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))


@pytest.mark.parametrize(
    "invalid_decimal",
    ["+1", "1.0", "01", "1e0", " 1", "-0", "0.50"],
)
def test_noncanonical_decimal_rows_fail_closed(invalid_decimal: str) -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    rows_document["rows"][0]["coordinate_decimal"] = invalid_decimal
    with pytest.raises(ParameterFitContractError, match="canonical"):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))


def test_malformed_json_value_types_use_the_fitting_contract_error() -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    rows_document["rows"][0]["term_kind"] = []
    with pytest.raises(ParameterFitContractError, match="term_kind"):
        run_synthetic_exact_methane_harmonic_fit(*_rebundle(rows_document))

    rows_document = json.loads(_fixture_bytes()[0])
    invalid_fit_ids = [
        1,
        "angle_002",
        "angle_003",
        "bond_001",
        "bond_002",
        "bond_003",
    ]
    with pytest.raises(ParameterFitContractError, match="fit_row_ids"):
        run_synthetic_exact_methane_harmonic_fit(
            *_rebundle(
                rows_document,
                fit_row_ids=invalid_fit_ids,  # type: ignore[arg-type]
            )
        )


def test_manifest_split_and_rows_tampering_fail_closed() -> None:
    rows_data, dataset_data, split_data = _fixture_bytes()
    tampered_rows = rows_data.replace(b'"energy_decimal": "0.25"', b'"energy_decimal": "0.5"', 1)
    with pytest.raises(ParameterFitContractError, match="rows digest"):
        run_synthetic_exact_methane_harmonic_fit(
            tampered_rows,
            dataset_data,
            split_data,
        )

    dataset = json.loads(dataset_data)
    dataset["row_count"] = 9
    with pytest.raises(ParameterFitContractError):
        run_synthetic_exact_methane_harmonic_fit(
            rows_data,
            json.dumps(dataset).encode("utf-8"),
            split_data,
        )

    split = json.loads(split_data)
    split["holdout_row_ids"] = sorted(
        [*split["holdout_row_ids"], "bond_001"]
    )
    with pytest.raises(ParameterFitContractError, match="disjoint"):
        run_synthetic_exact_methane_harmonic_fit(
            rows_data,
            dataset_data,
            json.dumps(split).encode("utf-8"),
        )


def test_receipt_and_bundle_are_factory_bound_and_nonpromoting() -> None:
    bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    payload = bundle.to_dict()

    with pytest.raises(TypeError):
        ParameterFitRunReceipt()  # type: ignore[call-arg]
    with pytest.raises(ParameterFitContractError, match="binding"):
        SyntheticParameterFitBundle(
            replace(bundle.parameter_set, fit_receipt_sha256="0" * 64),
            bundle.receipt,
        )
    assert payload["verification_status"] == (
        "recomputed_nonphysical_fixture_match"
    )
    assert payload["parameterability_assessed"] is False
    assert payload["parameterizable"] is False
    assert payload["runtime_eligible"] is False
    assert payload["execution_authorized"] is False
    assert payload["energy_evaluation_authorized"] is False
    assert payload["force_evaluation_authorized"] is False
    assert payload["minimization_authorized"] is False
    assert payload["simulation_ready"] is False
    assert payload["claim_safe"] is False
    assert serialize_parameter_fit_run_receipt(bundle.receipt) == (
        serialize_parameter_fit_run_receipt(
            run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes()).receipt
        )
    )

    system = parse_sdf_v2000(METHANE.read_bytes(), source_id="fit-assignment").system
    assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        bundle.parameter_set,
    )
    assert assignment.assignment_status == (
        "declared_fit_candidate_mapped_unverified"
    )
    assert assignment.bond_angle_assignment_complete is True
    assert assignment.parameterizable is False
    assert assignment.execution_authorized is False


@pytest.mark.parametrize(
    "schema_version",
    [True, None, "", "1.0", "1.2.0"],
)
def test_output_parameter_schema_version_is_keyword_only_and_exact(
    schema_version: object,
) -> None:
    with pytest.raises(ParameterFitContractError):
        run_synthetic_exact_methane_harmonic_fit(
            *_fixture_bytes(),
            output_parameter_artifact_schema_version=schema_version,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError):
        run_synthetic_exact_methane_harmonic_fit(  # type: ignore[call-arg]
            *_fixture_bytes(),
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
        )


def test_receipt_and_parameter_set_schema_versions_cannot_be_mixed() -> None:
    legacy = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    form_bound = _form_bound_bundle()

    with pytest.raises(ParameterFitContractError, match="binding"):
        SyntheticParameterFitBundle(legacy.parameter_set, form_bound.receipt)
    with pytest.raises(ParameterFitContractError, match="binding"):
        SyntheticParameterFitBundle(form_bound.parameter_set, legacy.receipt)

    object.__setattr__(
        form_bound.receipt,
        "_output_parameter_artifact_schema_version",
        EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
    )
    with pytest.raises(ParameterFitContractError):
        serialize_parameter_fit_run_receipt(form_bound.receipt)


def test_receipt_and_bundle_recompute_instead_of_trusting_private_token() -> None:
    rows_document = json.loads(_fixture_bytes()[0])
    for row in rows_document["rows"]:
        if row["row_id"] == "bond_004":
            row["energy_decimal"] = "2"
    invalid_artifacts = _rebundle(rows_document)
    with pytest.raises(ParameterFitContractError, match="holdout residual"):
        ParameterFitRunReceipt(
            factory_token=fitting_module._RECEIPT_FACTORY_TOKEN,
            rows_data=invalid_artifacts[0],
            dataset_manifest_data=invalid_artifacts[1],
            split_manifest_data=invalid_artifacts[2],
        )

    bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    assert not hasattr(bundle.receipt, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(
            bundle.receipt,
            "_require_self_consistent",
            lambda: None,
        )
    object.__setattr__(
        bundle.receipt,
        "max_holdout_absolute_residual",
        Fraction(999),
    )
    with pytest.raises(ParameterFitContractError, match="recomputation"):
        serialize_parameter_fit_run_receipt(bundle.receipt)
    with pytest.raises(ParameterFitContractError, match="recomputation"):
        SyntheticParameterFitBundle(bundle.parameter_set, bundle.receipt)

    bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    assert not hasattr(bundle, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(bundle, "_require_self_consistent", lambda: None)
    object.__setattr__(
        bundle,
        "parameter_set",
        replace(bundle.parameter_set, fit_receipt_sha256="0" * 64),
    )
    with pytest.raises(ParameterFitContractError, match="binding"):
        bundle.to_dict()
    with pytest.raises(ParameterFitContractError, match="binding"):
        _ = bundle.bundle_sha256


def test_receipt_rejects_always_equal_scalar_and_collection_subclasses() -> None:
    mutations = (
        (
            "fit_rows_sha256",
            _AlwaysEqualString("f" * 64),
        ),
        (
            "fit_row_ids",
            _AlwaysEqualTuple(("forged_fit_row",)),
        ),
        (
            "bond_coefficients",
            (
                _AlwaysEqualFraction(999),
                Fraction(0),
                Fraction(0),
            ),
        ),
        (
            "max_holdout_absolute_residual",
            _AlwaysEqualFraction(999),
        ),
        (
            "_fit_protocol_json",
            _AlwaysEqualBytes(b"{}"),
        ),
        (
            "parameter_payload_sha256",
            _AlwaysEqualObject(),
        ),
    )
    for field_name, forged_value in mutations:
        bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
        object.__setattr__(bundle.receipt, field_name, forged_value)
        with pytest.raises(ParameterFitContractError):
            serialize_parameter_fit_run_receipt(bundle.receipt)
        with pytest.raises(ParameterFitContractError):
            bundle.to_dict()


def test_receipt_rejects_nested_manifest_comparator_tampering() -> None:
    for manifest_name, field_name in (
        ("dataset_manifest", "rows_sha256"),
        ("split_manifest", "dataset_manifest_sha256"),
    ):
        bundle = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
        manifest = getattr(bundle.receipt, manifest_name)
        object.__setattr__(
            manifest,
            field_name,
            _AlwaysEqualString("f" * 64),
        )
        with pytest.raises(ParameterFitContractError):
            serialize_parameter_fit_run_receipt(bundle.receipt)
        with pytest.raises(ParameterFitContractError):
            SyntheticParameterFitBundle(bundle.parameter_set, bundle.receipt)


def test_protocol_bytes_are_frozen_and_share_parameter_set_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    form_bound_baseline = _form_bound_bundle()
    baseline_protocol = baseline.receipt.to_dict()["fit_protocol"]
    form_bound_protocol = form_bound_baseline.receipt.to_dict()["fit_protocol"]
    baseline_protocol_id = baseline_protocol["protocol_id"]
    baseline_objective_id = baseline_protocol["objective_id"]

    monkeypatch.setattr(
        fitting_module,
        "SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID",
        "mutated_protocol_id",
    )
    monkeypatch.setattr(
        fitting_module,
        "SYNTHETIC_HARMONIC_OBJECTIVE_ID",
        "mutated_objective_id",
    )
    monkeypatch.setattr(
        fitting_module,
        "SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1",
        "mutated_form_bound_protocol_id",
    )
    monkeypatch.setattr(
        fitting_module,
        "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
        "mutated_functional_form_id",
    )
    recomputed = run_synthetic_exact_methane_harmonic_fit(*_fixture_bytes())
    form_bound_recomputed = _form_bound_bundle()
    payload = recomputed.receipt.to_dict()
    form_bound_payload = form_bound_recomputed.receipt.to_dict()

    assert payload["fit_protocol"] == baseline_protocol
    assert payload["fit_protocol"]["protocol_id"] == baseline_protocol_id
    assert payload["fit_protocol"]["objective_id"] == baseline_objective_id
    assert payload["fit_protocol_sha256"] == SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256
    assert recomputed.parameter_set.fit_protocol_id == baseline_protocol_id
    assert form_bound_payload["fit_protocol"] == form_bound_protocol
    assert form_bound_payload["fit_protocol_sha256"] == (
        SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1
    )
    assert form_bound_recomputed.parameter_set.functional_form_id == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )


def test_pipeline_is_hashseed_deterministic_and_absent_from_engine_runtime() -> None:
    script = f"""
from pathlib import Path
from betelgeuze_engine_v2.forcefield import run_synthetic_exact_methane_harmonic_fit
root = Path({str(FIXTURES)!r})
bundle = run_synthetic_exact_methane_harmonic_fit(
    (root / 'synthetic_harmonic_rows.json').read_bytes(),
    (root / 'synthetic_dataset_manifest.json').read_bytes(),
    (root / 'synthetic_split_manifest.json').read_bytes(),
)
form_bound = run_synthetic_exact_methane_harmonic_fit(
    (root / 'synthetic_harmonic_rows.json').read_bytes(),
    (root / 'synthetic_dataset_manifest.json').read_bytes(),
    (root / 'synthetic_split_manifest.json').read_bytes(),
    output_parameter_artifact_schema_version='1.1.0',
)
print(
    bundle.receipt.receipt_sha256,
    bundle.parameter_set.parameter_set_sha256,
    bundle.bundle_sha256,
    form_bound.receipt.receipt_sha256,
    form_bound.parameter_set.parameter_set_sha256,
    form_bound.bundle_sha256,
)
"""
    outputs = []
    for seed in ("1", "7", "31"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout.strip())
    assert len(set(outputs)) == 1
    assert "forcefield" not in inspect.getsource(engine_module)
