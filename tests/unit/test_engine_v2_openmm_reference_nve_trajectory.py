from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.openmm_reference_nve_trajectory import (
    FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256,
    OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL,
    OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL,
    OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
    OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
    OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM,
    OPENMM_REFERENCE_NVE_TRAJECTORY_SCIENTIFIC_BLOCKERS,
    OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS,
    OpenMMReferenceNVETrajectoryError,
    build_openmm_reference_nve_trajectory_observation,
    openmm_reference_nve_trajectory_configuration_document,
    read_openmm_reference_nve_trajectory_observation,
    require_openmm_reference_nve_trajectory_observation,
    write_openmm_reference_nve_trajectory_observation,
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


def _number(row: dict[str, object], field: str) -> float:
    value = row[field]
    assert isinstance(value, str)
    return float.fromhex(value)


@pytest.fixture(scope="module")
def observation():
    return build_openmm_reference_nve_trajectory_observation()


def test_configuration_is_frozen_result_free_and_claim_closed() -> None:
    document = openmm_reference_nve_trajectory_configuration_document()

    assert (
        document["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_NVE_TRAJECTORY_CONFIG_SHA256
        == "2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e"
    )
    assert document["case_order"] == [
        "neutral_ion_pair_unconstrained",
        "neutral_water_coupled_oh_constraints",
    ]
    assert len(document["cases"]) == 2
    assert len(document["failure_rows"]) == 3
    assert document["oracle"]["platform"] == "Reference"
    assert "velocity-Verlet/RATTLE" in document["oracle"]["integrator"]
    assert document["claim_gates"] == {
        "single_host_can_validate": False,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
    }
    serialized = json.dumps(document, sort_keys=True)
    assert "observation_sha256" not in serialized
    assert "case_sha256" not in serialized


def test_configuration_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "from betelgeuze_engine_v2.offline import "
        "openmm_reference_nve_trajectory as module;"
        "module.openmm_reference_nve_trajectory_configuration_document();"
        "print(int('openmm' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "0"


def test_observation_reexecutes_every_trace_and_preregistered_metric(
    observation,
) -> None:
    verified = require_openmm_reference_nve_trajectory_observation(
        observation
    )

    assert verified == observation
    assert verified["summary"] == {
        "pass_case_count": 2,
        "pass_case_metric_count": 2,
        "failure_case_count": 3,
        "failure_case_metric_count": 3,
        "all_preregistered_metrics_pass": True,
        "host_count": 1,
        "independent_reviewer_approved": False,
        "production_eligible": False,
    }
    assert verified["scientifically_validated"] is False
    assert verified["claim_safe"] is False
    assert verified["scientific_blockers"] == list(
        OPENMM_REFERENCE_NVE_TRAJECTORY_SCIENTIFIC_BLOCKERS
    )
    assert len(verified["observation_sha256"]) == 64


def test_case_rows_record_energy_force_trajectory_constraint_and_restart(
    observation,
) -> None:
    rows = {row["case_id"]: row for row in observation["case_rows"]}
    assert set(rows) == {
        "neutral_ion_pair_unconstrained",
        "neutral_water_coupled_oh_constraints",
    }

    for row in rows.values():
        assert row["status"] == "completed"
        assert row["metric_pass"] is True
        assert len(row["engine_trace"]) == 17
        assert len(row["openmm_trace"]) == 17
        assert len(row["same_step_comparisons"]) == 17
        assert row["engine_restart"]["metric_pass"] is True
        assert row["openmm_restart"]["metric_pass"] is True
        assert (
            row["openmm_restart"]["checkpoint_transport"][
                "portable_across_runtime_or_hardware"
            ]
            is False
        )
        assert (
            row["openmm_restart"]["checkpoint_transport"][
                "raw_bytes_persisted"
            ]
            is False
        )
        maxima = row["maxima"]
        assert (
            _number(
                maxima,
                "same_coordinate_energy_max_abs_kcal_per_mol_hex",
            )
            <= OPENMM_REFERENCE_NVE_ENERGY_ERROR_THRESHOLD_KCAL_PER_MOL
        )
        assert (
            _number(
                maxima,
                "same_coordinate_force_max_abs_kcal_per_mol_angstrom_hex",
            )
            <= OPENMM_REFERENCE_NVE_FORCE_MAX_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        )
        assert (
            _number(
                maxima,
                "same_coordinate_force_rms_kcal_per_mol_angstrom_hex",
            )
            <= OPENMM_REFERENCE_NVE_FORCE_RMS_ERROR_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        )
        assert (
            _number(
                maxima,
                "position_constraint_max_abs_angstrom_hex",
            )
            <= OPENMM_REFERENCE_NVE_POSITION_CONSTRAINT_THRESHOLD_ANGSTROM
        )
        assert (
            _number(
                maxima,
                "velocity_constraint_max_abs_angstrom_per_ps_hex",
            )
            <= OPENMM_REFERENCE_NVE_VELOCITY_CONSTRAINT_THRESHOLD_ANGSTROM_PER_PS
        )
        assert (
            _number(
                maxima,
                "engine_energy_drift_max_abs_kcal_per_mol_hex",
            )
            <= OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL
        )
        assert (
            _number(
                maxima,
                "openmm_energy_drift_max_abs_kcal_per_mol_hex",
            )
            <= OPENMM_REFERENCE_NVE_DRIFT_THRESHOLD_KCAL_PER_MOL
        )
        assert all(row["metric_checks"].values())
        assert all(
            len(state["state_sha256"]) == 64
            for state in (*row["engine_trace"], *row["openmm_trace"])
        )
        assert all(
            len(comparison["comparison_sha256"]) == 64
            for comparison in row["same_step_comparisons"]
        )

    ion = rows["neutral_ion_pair_unconstrained"]
    assert ion["engine_constraint_iteration_counts"] == {
        "cumulative_shake": 0,
        "cumulative_rattle": 0,
    }
    water = rows["neutral_water_coupled_oh_constraints"]
    assert water["engine_constraint_iteration_counts"]["cumulative_shake"] > 0
    assert water["engine_constraint_iteration_counts"]["cumulative_rattle"] > 0
    assert water["openmm_constraint_iteration_counts"] == {
        "status": "not_exposed_by_openmm",
        "count": None,
    }


def test_all_failure_rows_are_exact_and_in_denominator(observation) -> None:
    rows = {row["case_id"]: row for row in observation["failure_rows"]}

    assert set(rows) == {
        "nonperiodic_direct_ewald",
        "net_charged_direct_ewald",
        "triclinic_direct_ewald",
    }
    assert rows["nonperiodic_direct_ewald"]["observed_engine_code"] == (
        "fully_periodic_required"
    )
    assert rows["nonperiodic_direct_ewald"]["observed_oracle_code"] == (
        "fully_periodic_required"
    )
    assert rows["net_charged_direct_ewald"]["observed_engine_code"] == (
        "neutrality_required"
    )
    assert rows["net_charged_direct_ewald"]["observed_oracle_code"] == (
        "neutrality_required"
    )
    assert rows["triclinic_direct_ewald"]["observed_engine_code"] == (
        "orthorhombic_required"
    )
    assert rows["triclinic_direct_ewald"]["observed_oracle_code"] == (
        "orthorhombic_required"
    )
    assert all(row["metric_pass"] for row in rows.values())
    assert all(row["status"] == "expected_fail_closed" for row in rows.values())


def test_observation_binds_source_binary_environment_and_dependencies(
    observation,
) -> None:
    source = observation["source_identity"]
    runtime = observation["runtime_identity"]

    assert source["absolute_paths_disclosed"] is False
    assert len(source["source_files"]) == 6
    assert len(source["source_manifest_sha256"]) == 64
    assert len(source["dependency_identity_sha256"]) == 64
    assert source["dependencies"]["torch_version"]
    assert runtime["platform"]["selected_name"] == "Reference"
    assert runtime["platform"]["cpu_substitution_allowed"] is False
    assert runtime["path_values_disclosed"] is False
    assert len(runtime["runtime_identity_sha256"]) == 64


def test_digest_and_rehashed_numeric_tampering_fail_closed(observation) -> None:
    digest_tamper = deepcopy(observation)
    digest_tamper["summary"]["pass_case_metric_count"] = 1
    with pytest.raises(
        OpenMMReferenceNVETrajectoryError,
        match="digest mismatch",
    ):
        require_openmm_reference_nve_trajectory_observation(digest_tamper)

    numeric_tamper = deepcopy(observation)
    case = numeric_tamper["case_rows"][0]
    case["maxima"][
        "same_coordinate_energy_max_abs_kcal_per_mol_hex"
    ] = "0x0.0p+0"
    case_projection = {
        key: value for key, value in case.items() if key != "case_sha256"
    }
    case["case_sha256"] = _sha256(case_projection)
    observation_projection = {
        key: value
        for key, value in numeric_tamper.items()
        if key != "observation_sha256"
    }
    numeric_tamper["observation_sha256"] = _sha256(
        observation_projection
    )
    with pytest.raises(
        OpenMMReferenceNVETrajectoryError,
        match="does not reproduce",
    ):
        require_openmm_reference_nve_trajectory_observation(numeric_tamper)


def test_private_no_overwrite_transport_round_trip(
    tmp_path: Path,
    observation,
) -> None:
    destination = tmp_path / "nve-trajectory.json"
    written = write_openmm_reference_nve_trajectory_observation(
        destination,
        observation,
    )

    assert written == destination
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert read_openmm_reference_nve_trajectory_observation(destination) == (
        observation
    )
    assert (
        write_openmm_reference_nve_trajectory_observation(
            destination,
            observation,
        )
        == destination
    )

    symlink = tmp_path / "receipt-link.json"
    symlink.symlink_to(destination)
    with pytest.raises(
        OpenMMReferenceNVETrajectoryError,
        match="regular non-symlink",
    ):
        read_openmm_reference_nve_trajectory_observation(symlink)
