from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline import (
    openmm_reference_explicit_solvent_trajectory as module,
)
from betelgeuze_engine_v2.offline.openmm_reference_explicit_solvent_trajectory import (
    FROZEN_OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SHA256,
    OPENMM_REFERENCE_CONSTRAINTS_SOURCE_SHA256,
    OPENMM_REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS,
    OpenMMReferenceExplicitSolventError,
    build_openmm_reference_explicit_solvent_observation,
    openmm_reference_explicit_solvent_configuration_document,
    read_openmm_reference_explicit_solvent_observation,
    require_openmm_reference_explicit_solvent_observation,
    write_openmm_reference_explicit_solvent_observation,
)


def _sha256(value: object) -> str:
    payload = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture(scope="module")
def observation():
    return build_openmm_reference_explicit_solvent_observation()


def test_configuration_is_exact_frozen_result_free_and_claim_closed() -> None:
    document = openmm_reference_explicit_solvent_configuration_document()

    assert (
        document["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_EXPLICIT_SOLVENT_CONFIG_SHA256
        == "e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5"
    )
    assert document["case_order"] == [
        "neutral_solute_two_waters",
        "neutral_solute_two_waters_na_cl",
        "positive_solute_two_waters_cl",
    ]
    assert [
        row["preparation_receipt"]["solvated_atom_count"]
        for row in document["cases"]
    ] == [7, 9, 8]
    assert document["nominal_trajectory"] == {
        "timestep_ps_hex": (1.0e-6).hex(),
        "steps": 4,
        "restart_step": 2,
        "reciprocal_max_indices": [2, 2, 2],
        "initial_velocity_policy": "all_zero_binary64",
    }
    assert len(document["failure_rows"]) == 4
    assert document["openmm_constraint_source_audit"][
        "reference_constraints_source_sha256"
    ] == OPENMM_REFERENCE_CONSTRAINTS_SOURCE_SHA256
    assert document["failure_disposition_policy"][
        "threshold_relaxation_allowed"
    ] is False
    assert document["failure_disposition_policy"][
        "physical_input_modification_allowed"
    ] is False
    assert document["claim_gates"] == {
        "single_host_can_validate": False,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
    }
    serialized = json.dumps(document, sort_keys=True)
    assert "observation_sha256" not in serialized
    assert "case_sha256" not in serialized
    assert "all_preregistered_metrics_pass" not in serialized
    assert "observed_code" not in serialized


def test_configuration_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "from betelgeuze_engine_v2.offline import "
        "openmm_reference_explicit_solvent_trajectory as module;"
        "module.openmm_reference_explicit_solvent_configuration_document();"
        "print(int('openmm' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "0"


def test_observation_reexecutes_complete_receipt(observation) -> None:
    verified = require_openmm_reference_explicit_solvent_observation(
        observation
    )

    assert verified == observation
    assert verified["summary"] == {
        "physical_case_count": 3,
        "physical_case_metric_pass_count": 0,
        "physical_case_disposition_count": 3,
        "timestep_convergence_metric_pass": False,
        "ewald_convergence_metric_pass": True,
        "failure_case_count": 4,
        "failure_case_metric_pass_count": 4,
        "all_preregistered_metrics_pass": False,
        "all_failure_dispositions_complete": True,
        "host_count": 1,
        "independent_reviewer_approved": False,
        "production_eligible": False,
    }
    assert verified["scientifically_validated"] is False
    assert verified["claim_safe"] is False
    assert verified["scientific_blockers"] == list(
        OPENMM_REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS
    )


def test_case_rows_retain_failed_metrics_and_complete_dispositions(
    observation,
) -> None:
    rows = {row["case_id"]: row for row in observation["case_rows"]}

    assert set(rows) == {
        "neutral_solute_two_waters",
        "neutral_solute_two_waters_na_cl",
        "positive_solute_two_waters_cl",
    }
    for row in rows.values():
        assert row["status"] == "completed_failed_disposition"
        assert row["metric_pass"] is False
        assert row["failure_disposition_complete"] is True
        assert row["unexpected_failed_metrics"] == []
        assert row["preparation_replay_pass"] is True
        parent = row["parent_trajectory_row"]
        assert len(parent["engine_trace"]) == 5
        assert len(parent["openmm_trace"]) == 5
        assert len(parent["same_step_comparisons"]) == 5
        assert parent["engine_restart"]["metric_pass"] is True
        assert parent["openmm_restart"]["metric_pass"] is True
        assert (
            parent["metric_checks"]["position_constraint_metric_pass"]
            is False
        )
        codes = {
            disposition["code"]
            for disposition in row["failed_metric_dispositions"]
        }
        assert (
            "openmm_reference_settle_float_distance_precision_limit"
            in codes
        )
        assert all(
            disposition["threshold_relaxed"] is False
            and disposition["accepted_as_metric_pass"] is False
            for disposition in row["failed_metric_dispositions"]
        )

    salted = rows["neutral_solute_two_waters_na_cl"]
    assert salted["parent_trajectory_row"]["metric_checks"] == {
        "same_coordinate_energy_metric_pass": True,
        "same_coordinate_force_max_metric_pass": True,
        "same_coordinate_force_rms_metric_pass": True,
        "trajectory_coordinate_metric_pass": True,
        "trajectory_velocity_metric_pass": True,
        "position_constraint_metric_pass": False,
        "velocity_constraint_metric_pass": True,
        "engine_energy_drift_metric_pass": True,
        "openmm_energy_drift_metric_pass": True,
        "engine_restart_metric_pass": True,
        "openmm_restart_metric_pass": True,
    }
    for case_id in (
        "neutral_solute_two_waters",
        "positive_solute_two_waters_cl",
    ):
        codes = {
            disposition["code"]
            for disposition in rows[case_id]["failed_metric_dispositions"]
        }
        assert "exact_cutoff_boundary_inclusion_divergence" in codes


def test_timestep_failure_and_ewald_success_remain_in_denominator(
    observation,
) -> None:
    timestep = observation["timestep_convergence"]
    assert timestep["metric_pass"] is False
    assert timestep["failure_disposition_complete"] is True
    rows = {
        row["implementation"]: row
        for row in timestep["implementation_rows"]
    }
    engine = rows["engine_reference"]
    oracle = rows["openmm_reference"]
    assert engine["metric_checks"][
        "medium_coordinate_absolute_metric_pass"
    ] is True
    assert engine["metric_checks"][
        "coordinate_monotonic_metric_pass"
    ] is False
    assert engine["failed_metric_dispositions"][0]["code"] == (
        "engine_constraint_roundoff_nonmonotone_below_absolute_threshold"
    )
    assert engine["metric_pass"] is False
    assert all(oracle["metric_checks"].values())
    assert oracle["metric_pass"] is True

    ewald = observation["ewald_convergence"]
    assert ewald["metric_pass"] is True
    assert all(
        row["metric_pass"] for row in ewald["implementation_rows"]
    )
    for row in ewald["implementation_rows"]:
        bound2 = row["gaps"]["bound2_to_bound4"]
        bound3 = row["gaps"]["bound3_to_bound4"]
        assert float.fromhex(
            bound3["energy_max_abs_kcal_per_mol_hex"]
        ) <= float.fromhex(bound2["energy_max_abs_kcal_per_mol_hex"])
        assert float.fromhex(
            bound3["force_max_abs_kcal_per_mol_angstrom_hex"]
        ) <= float.fromhex(
            bound2["force_max_abs_kcal_per_mol_angstrom_hex"]
        )


def test_all_failure_rows_are_exact_and_in_denominator(observation) -> None:
    rows = {row["case_id"]: row for row in observation["failure_rows"]}

    assert {
        case_id: row["observed_code"]
        for case_id, row in rows.items()
    } == {
        "non_neutral_materialization": "neutrality_required",
        "boxed_source_materialization": "unboxed_source_required",
        "missing_mass_materialization": "explicit_mass_required",
        "oracle_atom_capacity": "oracle_atom_capacity_exceeded",
    }
    assert all(row["metric_pass"] for row in rows.values())
    assert all(row["status"] == "expected_fail_closed" for row in rows.values())
    assert rows["oracle_atom_capacity"]["atom_count"] == 17
    assert rows["oracle_atom_capacity"]["maximum_atom_count"] == 16


def test_receipt_binds_source_runtime_and_dependency_identity(
    observation,
) -> None:
    source = observation["source_identity"]
    runtime = observation["runtime_identity"]

    assert source["absolute_paths_disclosed"] is False
    assert len(source["source_files"]) == 7
    assert len(source["source_manifest_sha256"]) == 64
    assert len(source["parent_runtime_dependency_identity_sha256"]) == 64
    assert runtime["platform"]["selected_name"] == "Reference"
    assert runtime["platform"]["cpu_substitution_allowed"] is False
    assert runtime["path_values_disclosed"] is False


def test_digest_tampering_fails_before_reexecution(observation) -> None:
    tampered = deepcopy(observation)
    tampered["summary"]["physical_case_metric_pass_count"] = 1

    with pytest.raises(
        OpenMMReferenceExplicitSolventError,
        match="digest mismatch",
    ):
        require_openmm_reference_explicit_solvent_observation(tampered)


def test_private_no_overwrite_transport_round_trip(
    tmp_path: Path,
    observation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = {
        key: value
        for key, value in observation.items()
        if key != "observation_sha256"
    }
    monkeypatch.setattr(module, "_observation_projection", lambda: projection)
    destination = tmp_path / "explicit-solvent.json"
    written = write_openmm_reference_explicit_solvent_observation(
        destination,
        observation,
    )

    assert written == destination
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert read_openmm_reference_explicit_solvent_observation(destination) == (
        observation
    )
    assert (
        write_openmm_reference_explicit_solvent_observation(
            destination,
            observation,
        )
        == destination
    )

    different = deepcopy(observation)
    different["summary"]["host_count"] = 2
    different_projection = {
        key: value
        for key, value in different.items()
        if key != "observation_sha256"
    }
    different["observation_sha256"] = _sha256(different_projection)
    monkeypatch.setattr(
        module,
        "_observation_projection",
        lambda: different_projection,
    )
    with pytest.raises(
        OpenMMReferenceExplicitSolventError,
        match="refusing to overwrite",
    ):
        write_openmm_reference_explicit_solvent_observation(
            destination,
            different,
        )

    symlink = tmp_path / "receipt-link.json"
    symlink.symlink_to(destination)
    with pytest.raises(
        OpenMMReferenceExplicitSolventError,
        match="regular non-symlink",
    ):
        read_openmm_reference_explicit_solvent_observation(symlink)
