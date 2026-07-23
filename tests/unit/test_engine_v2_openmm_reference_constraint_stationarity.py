from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.openmm_reference_constraint_stationarity import (
    FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256,
    OpenMMReferenceConstraintStationarityError,
    build_openmm_reference_constraint_stationarity_receipt,
    openmm_reference_constraint_stationarity_configuration_document,
    read_openmm_reference_constraint_stationarity_receipt,
    require_openmm_reference_constraint_stationarity_receipt,
    write_openmm_reference_constraint_stationarity_receipt,
)


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture(scope="module")
def candidate_receipt():
    return build_openmm_reference_constraint_stationarity_receipt()


def test_openmm_candidate_configuration_is_frozen_and_result_free() -> None:
    document = openmm_reference_constraint_stationarity_configuration_document()

    assert (
        document["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_CONSTRAINT_STATIONARITY_CONFIG_SHA256
        == "722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1"
    )
    assert document["candidate_case_denominator"] == 4
    assert document["excluded_frozen_case_count"] == 10
    assert len(document["case_dispositions"]) == 14
    assert document["comparison_method"]["native_openmm_minimizer_invoked"] is False
    assert (
        document["comparison_method"]["native_openmm_lbfgs_status"]
        == "unchanged_rejected_6_of_8"
    )
    assert document["frozen_14_case_production_receipt_superseded"] is False
    assert document["frozen_native_openmm_receipt_superseded"] is False
    assert document["validation_receipt"] is False
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False
    serialized = json.dumps(document, sort_keys=True)
    assert "result_sha256" not in serialized
    assert "observed" not in serialized


def test_configuration_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "import betelgeuze_engine_v2.offline."
        "openmm_reference_constraint_stationarity as module;"
        "module.openmm_reference_constraint_stationarity_configuration_document();"
        "print(int('openmm' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "0"


def test_same_coordinate_receipt_passes_only_the_four_candidate_rows(
    candidate_receipt,
) -> None:
    receipt = require_openmm_reference_constraint_stationarity_receipt(
        candidate_receipt
    )
    summary = receipt["summary"]

    assert summary["candidate_case_denominator"] == 4
    assert summary["candidate_case_passed_count"] == 4
    assert summary["candidate_case_failed_count"] == 0
    assert summary["physical_input_denominator"] == 2
    assert summary["checkpoint_restart_exact_count"] == 2
    assert summary["excluded_frozen_case_count"] == 10
    assert summary["frozen_14_case_production_denominator_claimed"] is False
    assert summary["fixed_born_self_pair_components_recorded_separately"] is True
    assert summary["native_openmm_lbfgs_invoked"] is False
    assert summary["native_openmm_lbfgs_status"] == "unchanged_rejected_6_of_8"
    assert summary["s0_complete"] is False
    assert receipt["validation_receipt"] is False
    assert receipt["candidate_observation_receipt"] is True
    assert receipt["scientifically_validated"] is False
    assert receipt["claim_safe"] is False
    assert len(receipt["case_rows"]) == 4
    assert len(receipt["excluded_case_rows"]) == 10
    assert all(row["passed"] for row in receipt["case_rows"])


def test_physical_rows_record_energy_force_constraint_tangent_and_components(
    candidate_receipt,
) -> None:
    rows = {
        row["energy_case_id"]: row
        for row in candidate_receipt["physical_comparisons"]
    }
    noncharged = rows["v2_constrained_angle_energy_decrease"]
    fixed_born = rows["v2_fixed_born_constrained_energy_decrease"]

    for row in rows.values():
        assert row["passed"] is True
        assert row["term_energy"]["absolute_error_kcal_per_mol"] <= 1.0e-10
        assert row["force_error"]["max_abs_kcal_per_mol_angstrom"] <= 1.0e-8
        assert row["force_error"]["rms_kcal_per_mol_angstrom"] <= 1.0e-8
        assert row["constraint_max_abs_residual_angstrom"] <= 1.0e-10
        assert row["tangent_force"]["engine_max_kcal_per_mol_angstrom"] <= 1.0e-8
        assert row["tangent_force"]["openmm_max_kcal_per_mol_angstrom"] <= 1.0e-8
        assert row["checkpoint_restart_document_equality"] is True
        assert row["rejected_trials"] == len(row["all_failure_rows"]) == 0
        assert len(row["energy_trace_sha256"]) == 64
        assert len(row["coordinate_trace_sha256"]) == 64
    assert noncharged["accepted_stationarity_polish_iterations"] == 0
    assert fixed_born["accepted_stationarity_polish_iterations"] == 8
    components = {
        row["name"]: row for row in fixed_born["component_energies"]
    }
    assert {
        "fixed_born_self_polar",
        "fixed_born_pair_polar",
    } <= components.keys()
    assert all(row["passed"] for row in components.values())
    assert fixed_born[
        "fixed_born_self_pair_components_recorded_separately"
    ] is True


def test_candidate_receipt_reexecutes_exactly(candidate_receipt) -> None:
    rerun = build_openmm_reference_constraint_stationarity_receipt()
    assert rerun == candidate_receipt


def test_candidate_receipt_rejects_digest_and_semantic_tampering(
    candidate_receipt,
) -> None:
    digest_tamper = deepcopy(candidate_receipt)
    digest_tamper["summary"]["candidate_case_passed_count"] = 3
    with pytest.raises(
        OpenMMReferenceConstraintStationarityError,
        match="digest mismatch",
    ):
        require_openmm_reference_constraint_stationarity_receipt(digest_tamper)

    semantic_tamper = deepcopy(candidate_receipt)
    semantic_tamper["summary"]["s0_complete"] = True
    projection = {
        key: value
        for key, value in semantic_tamper.items()
        if key != "receipt_sha256"
    }
    semantic_tamper["receipt_sha256"] = _sha256(projection)
    with pytest.raises(
        OpenMMReferenceConstraintStationarityError,
        match="claim-closed",
    ):
        require_openmm_reference_constraint_stationarity_receipt(
            semantic_tamper
        )


def test_candidate_receipt_file_is_private_and_verifiable(
    candidate_receipt,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "candidate-receipt.json"
    written = write_openmm_reference_constraint_stationarity_receipt(
        destination,
        candidate_receipt,
    )

    assert written == destination
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert (
        read_openmm_reference_constraint_stationarity_receipt(destination)
        == candidate_receipt
    )


def test_candidate_receipt_writer_rejects_symlink_transport(
    candidate_receipt,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "receipt.json"
    link.symlink_to(target)

    with pytest.raises(
        OpenMMReferenceConstraintStationarityError,
        match="symlink",
    ):
        write_openmm_reference_constraint_stationarity_receipt(
            link,
            candidate_receipt,
        )
    with pytest.raises(
        OpenMMReferenceConstraintStationarityError,
        match="non-symlink",
    ):
        read_openmm_reference_constraint_stationarity_receipt(link)
