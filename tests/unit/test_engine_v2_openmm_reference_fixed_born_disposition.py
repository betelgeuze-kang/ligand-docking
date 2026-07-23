from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest


pytest.importorskip("openmm")

from betelgeuze_engine_v2.offline.openmm_reference_fixed_born_disposition import (  # noqa: E402
    FIXED_BORN_FAILURE_CASE_IDS,
    OpenMMReferenceFixedBornDispositionError,
    build_openmm_reference_fixed_born_disposition_receipt,
    main,
    read_openmm_reference_fixed_born_disposition_receipt,
    require_openmm_reference_fixed_born_disposition_receipt,
    write_openmm_reference_fixed_born_disposition_receipt,
)
from betelgeuze_engine_v2.offline.openmm_reference_materialization import (  # noqa: E402
    build_openmm_reference_materialization,
    write_openmm_reference_materialization,
)
from betelgeuze_engine_v2.offline.openmm_reference_native_minimization import (  # noqa: E402
    build_openmm_reference_native_minimization_receipt,
    write_openmm_reference_native_minimization_receipt,
)


SOURCE_OBSERVED_AT = "2026-07-24T14:20:00Z"
NATIVE_OBSERVED_AT = "2026-07-24T14:30:00Z"
DISPOSITION_OBSERVED_AT = "2026-07-24T14:40:00Z"


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
def native_receipt(
    source_materialization: dict[str, object],
) -> dict[str, object]:
    return build_openmm_reference_native_minimization_receipt(
        source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        observed_at_utc=NATIVE_OBSERVED_AT,
    )


@pytest.fixture(scope="module")
def disposition_receipt(
    source_materialization: dict[str, object],
    native_receipt: dict[str, object],
) -> dict[str, object]:
    return build_openmm_reference_fixed_born_disposition_receipt(
        source_materialization,
        native_receipt,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
        observed_at_utc=DISPOSITION_OBSERVED_AT,
    )


def test_fixed_born_disposition_classifies_final_projection_tradeoff(
    disposition_receipt: dict[str, object],
    source_materialization: dict[str, object],
    native_receipt: dict[str, object],
) -> None:
    verified = require_openmm_reference_fixed_born_disposition_receipt(
        disposition_receipt,
        source_materialization=source_materialization,
        source_native_receipt=native_receipt,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
    )
    summary = verified["summary"]

    assert verified["status"] == "accepted_failure_disposition_evidence"
    assert summary["case_count"] == 2
    assert summary["total_probe_count"] == 16
    assert summary["no_reporter_baseline_exact_native_endpoint_reproduction_case_count"] == 2
    assert summary["instrumented_baseline_bitwise_equal_case_count"] == 0
    assert summary["all_engine_openmm_same_coordinate_mappings_passed"] is True
    assert summary["all_reporter_traces_present"] is True
    assert summary["cross_alias_physics_projection_exactly_equal"] is True
    assert summary["cross_alias_classification_exactly_equal"] is True
    assert summary["classification"] == "final_constraint_projection_tradeoff_observed"
    assert summary["failure_disposition_complete"] is True
    assert summary["frozen_native_endpoint_health_failure_resolved"] is False
    assert summary["causal_root_cause_proven"] is False
    assert tuple(row["case_id"] for row in verified["cases"]) == (
        FIXED_BORN_FAILURE_CASE_IDS
    )
    assert (
        verified["cases"][0]["case_physics_projection_sha256"]
        == verified["cases"][1]["case_physics_projection_sha256"]
    )

    for case in verified["cases"]:
        assert (
            case[
                "no_reporter_baseline_source_native_endpoint_exactly_reproduced"
            ]
            is True
        )
        assert (
            case["instrumented_baseline_source_native_endpoint_bitwise_equal"]
            is False
        )
        assert case["disposition"] == {
            "classification": "final_constraint_projection_tradeoff_observed",
            "resolving_probe_id": "baseline_protocol",
            "baseline_failure_exactly_reproduced": True,
            "causal_root_cause_proven": False,
            "frozen_endpoint_health_failure_resolved": False,
            "threshold_relaxation_used": False,
        }
        assert len(case["probes"]) == 8
        assert all(
            not probe["post_projection"]["original_endpoint_health_passed"]
            for probe in case["probes"]
        )
        baseline = case["probes"][0]
        pre = baseline["pre_projection"]
        post = baseline["post_projection"]
        assert pre["tangent_force_threshold_passed"] is True
        assert pre["constraint_residual_threshold_passed"] is False
        assert post["tangent_force_threshold_passed"] is False
        assert post["constraint_residual_threshold_passed"] is True
        assert (
            pre["constraint_diagnostics"][
                "tangent_force_max_kcal_per_mol_angstrom"
            ]
            <= 1.0e-8
        )
        assert (
            post["constraint_diagnostics"][
                "tangent_force_max_kcal_per_mol_angstrom"
            ]
            > 1.0e-8
        )
        trace = baseline["probe_endpoint"]["minimizer_reporter_trace"]["summary"]
        assert trace["callback_count"] == 66
        assert trace["callback_count_exceeds_declared_maximum_iterations"] is True
        assert trace["restraint_stage_count"] == 4
        assert trace["restraint_stage_transition_count"] == 3
        assert trace["optimizer_rejection_count_available"] is False


def test_fixed_born_disposition_exactly_reexecutes(
    disposition_receipt: dict[str, object],
    source_materialization: dict[str, object],
    native_receipt: dict[str, object],
) -> None:
    verified = require_openmm_reference_fixed_born_disposition_receipt(
        disposition_receipt,
        source_materialization=source_materialization,
        source_native_receipt=native_receipt,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
        reexecute=True,
    )
    assert verified == disposition_receipt


@pytest.mark.parametrize(
    "mutation",
    ("summary", "probe_metric", "control_endpoint", "claim_boundary", "ancestry"),
)
def test_fixed_born_disposition_rejects_tampering(
    mutation: str,
    disposition_receipt: dict[str, object],
    source_materialization: dict[str, object],
    native_receipt: dict[str, object],
) -> None:
    value = deepcopy(disposition_receipt)
    if mutation == "summary":
        value["summary"]["failure_disposition_complete"] = False
    elif mutation == "probe_metric":
        value["cases"][0]["probes"][0]["post_projection"][
            "energy_change_from_initial_kcal_per_mol"
        ] += 1.0
    elif mutation == "control_endpoint":
        value["cases"][0]["no_reporter_baseline_control_endpoint"][
            "maximum_iterations"
        ] += 1
    elif mutation == "claim_boundary":
        value["s0_accepted"] = True
    else:
        value["source_native_receipt_sha256"] = "0" * 64
    _refresh_receipt(value)

    with pytest.raises(OpenMMReferenceFixedBornDispositionError):
        require_openmm_reference_fixed_born_disposition_receipt(
            value,
            source_materialization=source_materialization,
            source_native_receipt=native_receipt,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
            expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
        )


def test_fixed_born_disposition_file_is_mode_0600_and_cli_verifies(
    tmp_path: Path,
    disposition_receipt: dict[str, object],
    source_materialization: dict[str, object],
    native_receipt: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "source.json"
    native_path = tmp_path / "native.json"
    output = tmp_path / "fixed-born-disposition.json"
    write_openmm_reference_materialization(source_materialization, source_path)
    write_openmm_reference_native_minimization_receipt(
        native_receipt,
        native_path,
        source_materialization=source_materialization,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
    )
    write_openmm_reference_fixed_born_disposition_receipt(
        disposition_receipt,
        output,
        source_materialization=source_materialization,
        source_native_receipt=native_receipt,
        expected_source_materialization_sha256=source_materialization[
            "materialization_sha256"
        ],
        expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
    )

    assert os.stat(output).st_mode & 0o777 == 0o600
    assert (
        read_openmm_reference_fixed_born_disposition_receipt(
            output,
            source_materialization=source_materialization,
            source_native_receipt=native_receipt,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
            expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
        )
        == disposition_receipt
    )
    with pytest.raises(OpenMMReferenceFixedBornDispositionError):
        write_openmm_reference_fixed_born_disposition_receipt(
            disposition_receipt,
            output,
            source_materialization=source_materialization,
            source_native_receipt=native_receipt,
            expected_source_materialization_sha256=source_materialization[
                "materialization_sha256"
            ],
            expected_source_native_receipt_sha256=native_receipt["receipt_sha256"],
        )

    return_code = main(
        [
            "verify",
            "--source-materialization",
            str(source_path),
            "--expected-source-materialization-sha256",
            source_materialization["materialization_sha256"],
            "--source-native-receipt",
            str(native_path),
            "--expected-source-native-receipt-sha256",
            native_receipt["receipt_sha256"],
            "--input",
            str(output),
        ]
    )
    assert return_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "accepted_failure_disposition_evidence"
    assert summary["receipt_sha256"] == disposition_receipt["receipt_sha256"]
    assert summary["claim_safe"] is False
