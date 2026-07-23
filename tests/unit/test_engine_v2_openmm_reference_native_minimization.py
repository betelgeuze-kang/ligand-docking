from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest


pytest.importorskip("openmm")

from betelgeuze_engine_v2.offline.openmm_reference_materialization import (  # noqa: E402
    build_openmm_reference_materialization,
    write_openmm_reference_materialization,
)
from betelgeuze_engine_v2.offline.openmm_reference_native_minimization import (  # noqa: E402
    FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256,
    OpenMMReferenceNativeMinimizationError,
    build_openmm_reference_native_minimization_receipt,
    main,
    openmm_reference_native_minimization_configuration_document,
    read_openmm_reference_native_minimization_receipt,
    require_openmm_reference_native_minimization_receipt,
    write_openmm_reference_native_minimization_receipt,
)


SOURCE_OBSERVED_AT = "2026-07-24T12:30:00Z"
ENDPOINT_OBSERVED_AT = "2026-07-24T12:40:00Z"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _refresh_receipt(value: dict[str, object]) -> None:
    projection = {key: item for key, item in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = hashlib.sha256(_canonical_bytes(projection)).hexdigest()


@pytest.fixture(scope="module")
def source_materialization() -> dict[str, object]:
    return build_openmm_reference_materialization(
        observed_at_utc=SOURCE_OBSERVED_AT
    )


@pytest.fixture(scope="module")
def endpoint_receipt(
    source_materialization: dict[str, object],
) -> dict[str, object]:
    return build_openmm_reference_native_minimization_receipt(
        source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        observed_at_utc=ENDPOINT_OBSERVED_AT,
    )


def test_configuration_is_frozen_before_endpoint_observation() -> None:
    configuration = openmm_reference_native_minimization_configuration_document()

    assert (
        configuration["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
        == "6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e"
    )
    assert configuration["coverage"] == {
        "case_count": 14,
        "executable_case_count": 8,
        "not_applicable_case_count": 6,
        "all_failure_rows_retained": True,
    }
    assert configuration["acceptance"]["post_observation_tuning_allowed"] is False
    assert (
        configuration["acceptance"][
            "native_tangent_force_and_constraint_thresholds_reused_from_frozen_cases"
        ]
        is True
    )
    assert (
        configuration["acceptance"]["final_context_constraint_projection_required"]
        is True
    )
    assert all(
        row["openmm_constraint_tolerance_relative"] == 1.0e-10
        for row in configuration["case_rows"]
        if row["disposition"] == "execute_openmm_native_endpoint"
    )


def test_native_endpoint_receipt_retains_observed_fixed_born_failures(
    endpoint_receipt: dict[str, object],
    source_materialization: dict[str, object],
) -> None:
    verified = require_openmm_reference_native_minimization_receipt(
        endpoint_receipt,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
    )
    summary = verified["summary"]

    assert verified["status"] == "rejected_offline_native_endpoint_comparison"
    assert summary["case_count"] == 14
    assert summary["evaluated_case_count"] == 8
    assert summary["not_applicable_engine_contract_case_count"] == 6
    assert summary["same_coordinate_mapping_passed_case_count"] == 8
    assert summary["energy_nonincreasing_case_count"] == 8
    assert summary["endpoint_health_passed_case_count"] == 6
    assert summary["complete_failure_inclusive_comparison"] is True
    assert summary["all_failure_rows_retained"] is True
    assert summary["cross_algorithm_endpoint_equivalence_gated"] is False
    failing = {
        row["case_id"]
        for row in verified["cases"]
        if row["native_endpoint_executed"]
        and not row["case_passed_predefined_endpoint_health"]
    }
    assert failing == {
        "v2_fixed_born_constrained_energy_decrease",
        "v2_fixed_born_checkpoint_restart_exact",
    }
    for row in verified["cases"]:
        if not row["native_endpoint_executed"]:
            assert row["disposition"] == "not_applicable_engine_contract"
            assert row["expected_error_code"]
            continue
        diagnostics = row["native_endpoint_diagnostics"]
        assert diagnostics["constraint_residual_threshold_passed"] is True
        assert (
            row["engine_openmm_same_coordinate_comparison"][
                "passed_predefined_thresholds"
            ]
            is True
        )
        assert (
            row["cross_algorithm_endpoint_delta"]["endpoint_equivalence_claimed"]
            is False
        )


def test_native_endpoint_receipt_exactly_reexecutes(
    endpoint_receipt: dict[str, object],
    source_materialization: dict[str, object],
) -> None:
    verified = require_openmm_reference_native_minimization_receipt(
        endpoint_receipt,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        reexecute=True,
    )
    assert verified == endpoint_receipt


@pytest.mark.parametrize(
    "mutation",
    (
        "endpoint_energy",
        "summary",
        "failure_omission",
        "claim_boundary",
        "source_crosswire",
    ),
)
def test_native_endpoint_receipt_rejects_tampering(
    mutation: str,
    endpoint_receipt: dict[str, object],
    source_materialization: dict[str, object],
) -> None:
    value = deepcopy(endpoint_receipt)
    if mutation == "endpoint_energy":
        case = next(row for row in value["cases"] if row["native_endpoint_executed"])
        case["native_endpoint"]["final_evaluation"]["total_energy"]["value"] += 1.0
    elif mutation == "summary":
        value["summary"]["endpoint_health_passed_case_count"] += 1
    elif mutation == "failure_omission":
        value["cases"].pop()
    elif mutation == "claim_boundary":
        value["s0_accepted"] = True
    else:
        value["source_materialization_sha256"] = "0" * 64
    _refresh_receipt(value)

    with pytest.raises(OpenMMReferenceNativeMinimizationError):
        require_openmm_reference_native_minimization_receipt(
            value,
            source_materialization=source_materialization,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
        )


def test_native_endpoint_receipt_file_is_mode_0600_and_no_overwrite(
    tmp_path: Path,
    endpoint_receipt: dict[str, object],
    source_materialization: dict[str, object],
) -> None:
    output = tmp_path / "native-endpoint.json"
    write_openmm_reference_native_minimization_receipt(
        endpoint_receipt,
        output,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
    )

    assert os.stat(output).st_mode & 0o777 == 0o600
    assert (
        read_openmm_reference_native_minimization_receipt(
            output,
            source_materialization=source_materialization,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
        )
        == endpoint_receipt
    )
    with pytest.raises(OpenMMReferenceNativeMinimizationError):
        write_openmm_reference_native_minimization_receipt(
            endpoint_receipt,
            output,
            source_materialization=source_materialization,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
        )


def test_verify_cli_returns_scientific_rejection_without_losing_receipt(
    tmp_path: Path,
    endpoint_receipt: dict[str, object],
    source_materialization: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "source.json"
    receipt_path = tmp_path / "native.json"
    write_openmm_reference_materialization(source_materialization, source_path)
    write_openmm_reference_native_minimization_receipt(
        endpoint_receipt,
        receipt_path,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
    )

    return_code = main(
        [
            "verify",
            "--source-materialization",
            str(source_path),
            "--expected-source-materialization-sha256",
            source_materialization["materialization_sha256"],
            "--input",
            str(receipt_path),
        ]
    )

    assert return_code == 3
    summary = json.loads(capsys.readouterr().out)
    assert summary["receipt_sha256"] == endpoint_receipt["receipt_sha256"]
    assert summary["status"] == "rejected_offline_native_endpoint_comparison"
    assert summary["claim_safe"] is False
