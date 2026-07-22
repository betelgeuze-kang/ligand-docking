from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("openmm")

from betelgeuze_engine_v2.offline.openmm_reference_materialization import (  # noqa: E402
    OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS,
    OpenMMReferenceMaterializationError,
    build_openmm_reference_materialization,
    main,
    read_openmm_reference_materialization,
    require_openmm_reference_materialization,
    write_openmm_reference_materialization,
)


@pytest.fixture(scope="module")
def materialization() -> dict[str, object]:
    return build_openmm_reference_materialization(
        observed_at_utc="2026-07-23T00:00:00Z"
    )


def test_materialization_executes_complete_failure_inclusive_matrices(
    materialization: dict[str, object],
) -> None:
    observed = require_openmm_reference_materialization(materialization)

    assert observed["status"] == "accepted_offline_reference_materialization"
    assert observed["summary"]["all_predefined_metrics_passed"] is True
    assert observed["summary"]["all_case_and_variant_rows_retained"] is True
    energy = observed["energy_force_receipt"]
    minimum = observed["minimization_trace_receipt"]
    assert energy["summary"]["case_count"] == 27
    assert energy["summary"]["variant_count"] == 59
    assert energy["summary"]["evaluated_variant_count"] == 47
    assert energy["summary"]["not_applicable_engine_contract_variant_count"] == 12
    assert energy["summary"]["skipped_variant_count"] == 0
    assert minimum["summary"]["case_count"] == 14
    assert minimum["summary"]["evaluated_case_count"] == 8
    assert minimum["summary"]["not_applicable_engine_contract_case_count"] == 6
    assert minimum["summary"]["evaluated_trace_step_count"] == 572
    assert minimum["summary"]["fixed_born_trace_step_count"] == 246
    assert len(minimum["source_operational_traces"]) == 14
    engine_minimum = observed["summary"]["engine_minimization"]
    assert engine_minimum["case_count"] == 14
    assert engine_minimum["expected_pass_case_count"] == 8
    assert engine_minimum["expected_fail_closed_case_count"] == 6
    assert engine_minimum["passed_case_count"] == 14
    assert engine_minimum["all_cases_passed"] is True
    assert engine_minimum["all_required_metrics_present"] is True
    assert engine_minimum["checkpoint_metric_case_count"] == 3
    assert engine_minimum["checkpoint_restart_all_bitwise_equal"] is True
    assert len(observed["engine_minimization_case_observations"]) == 14
    assert all(
        "accepted_iteration_count" in row
        and "rejected_step_count" in row
        and "energy_force_evaluation_count" in row
        and "metric_values" in row
        and "trajectory_comparison" in row
        for row in observed["engine_minimization_case_observations"]
    )
    assert materialization["scientific_blockers"] == list(
        OPENMM_REFERENCE_MATERIALIZATION_BLOCKERS
    )
    for name in (
        "production_protocol_execution",
        "signed_result_receipt",
        "independent_review_complete",
        "two_host_reproduction_complete",
        "scientific_or_product_promotion_authorized",
        "scientifically_validated",
        "claim_safe",
    ):
        assert materialization[name] is False


def test_materialization_exact_reexecution_matches(
    materialization: dict[str, object],
) -> None:
    assert (
        require_openmm_reference_materialization(materialization, reexecute=True)
        == materialization
    )


def test_materialization_round_trip_is_canonical_mode_0600_and_no_replace(
    materialization: dict[str, object],
    tmp_path: Path,
) -> None:
    output = write_openmm_reference_materialization(
        materialization,
        tmp_path / "receipt.json",
    )

    assert os.stat(output).st_mode & 0o777 == 0o600
    restored = read_openmm_reference_materialization(output)
    assert restored == materialization
    assert output.read_bytes() == json.dumps(
        materialization,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    with pytest.raises(
        OpenMMReferenceMaterializationError,
        match="already exists",
    ):
        write_openmm_reference_materialization(materialization, output)


def test_materialization_rejects_tampering_and_symlink_transport(
    materialization: dict[str, object],
    tmp_path: Path,
) -> None:
    promoted = deepcopy(materialization)
    promoted["claim_safe"] = True
    with pytest.raises(
        OpenMMReferenceMaterializationError,
        match="claim or summary",
    ):
        require_openmm_reference_materialization(promoted)

    changed = deepcopy(materialization)
    changed["summary"]["energy_force"]["evaluated_variant_count"] = 46
    with pytest.raises(
        OpenMMReferenceMaterializationError,
        match="claim or summary",
    ):
        require_openmm_reference_materialization(changed)

    source = write_openmm_reference_materialization(
        materialization,
        tmp_path / "source.json",
    )
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(source)
    with pytest.raises(
        OpenMMReferenceMaterializationError,
        match="regular non-symlink",
    ):
        read_openmm_reference_materialization(symlink)


def test_cli_verifies_without_promoting_claims(
    materialization: dict[str, object],
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source = write_openmm_reference_materialization(
        materialization,
        tmp_path / "cli.json",
    )

    assert main(["verify", "--input", str(source)]) == 0
    summary = json.loads(capfd.readouterr().out)
    assert summary["materialization_sha256"] == materialization[
        "materialization_sha256"
    ]
    assert summary["status"] == "accepted_offline_reference_materialization"
    assert summary["claim_safe"] is False
