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
    openmm_force_double_rattle_trajectory as module,
)
from betelgeuze_engine_v2.offline.openmm_force_double_rattle_oracle import (
    OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
)
from betelgeuze_engine_v2.offline.openmm_force_double_rattle_trajectory import (
    FROZEN_OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SHA256,
    OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM,
    OPENMM_FORCE_DOUBLE_RATTLE_SCIENTIFIC_BLOCKERS,
    OpenMMForceDoubleRattleTrajectoryError,
    build_openmm_force_double_rattle_observation,
    openmm_force_double_rattle_configuration_document,
    read_openmm_force_double_rattle_observation,
    require_openmm_force_double_rattle_observation,
    write_openmm_force_double_rattle_observation,
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
    return build_openmm_force_double_rattle_observation()


def test_configuration_is_frozen_claim_closed_and_binds_v1() -> None:
    document = openmm_force_double_rattle_configuration_document()

    assert (
        document["configuration_sha256"]
        == FROZEN_OPENMM_FORCE_DOUBLE_RATTLE_TRAJECTORY_CONFIG_SHA256
        == "ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007"
    )
    assert document["case_order"] == [
        "neutral_solute_four_waters",
        "neutral_solute_four_waters_na_cl",
        "positive_solute_four_waters_cl",
    ]
    assert [
        row["preparation_receipt"]["solvated_atom_count"]
        for row in document["cases"]
    ] == [13, 15, 14]
    assert document["operational_algorithms"]["oracle_integrator"] == (
        OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID
    )
    assert OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID == (
        "stdlib_binary64_sequential_previous_vector_shake_rattle/1.1.0"
    )
    assert document["trajectory"] == {
        "timestep_ps_hex": (1.0e-4).hex(),
        "steps": 16,
        "restart_step": 7,
        "initial_velocity_policy": "index_derived_nonzero_binary64_v1",
        "reciprocal_max_indices": [2, 2, 2],
    }
    assert all(
        float.fromhex(row["initial_minimum_cutoff_margin_angstrom_hex"])
        >= OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM
        for row in document["cases"]
    )
    assert document["superseded_development_result"] == {
        "configuration_sha256": (
            "332e675b2c45a6fffca102559ddd4bca2a11e24e592d0daaca6807417af36682"
        ),
        "observation_sha256": (
            "478745074eb22318fad3cdd7427c0cdb77511bb299cd7413770eaee5ec71fab8"
        ),
        "receipt_file_sha256": (
            "c1cadc22ffe8b55e8ac810097868d617ba4517bfc7ab8df26474b69181009ede"
        ),
        "reason": (
            "current-vector nonlinear position projection exceeded the "
            "unchanged energy-drift gate for the +1 solute/Cl case"
        ),
    }
    assert document["claim_gates"] == {
        "scientifically_validated": False,
        "production_eligible": False,
        "p2_complete": False,
        "claim_safe": False,
    }
    serialized = json.dumps(document, sort_keys=True)
    assert "all_development_metrics_pass" not in serialized
    assert "case_sha256" not in serialized
    assert "observed_code" not in serialized


def test_configuration_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "from betelgeuze_engine_v2.offline import "
        "openmm_force_double_rattle_trajectory as module;"
        "module.openmm_force_double_rattle_configuration_document();"
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
    verified = require_openmm_force_double_rattle_observation(observation)

    assert verified == observation
    assert verified["observation_sha256"] == (
        "cd0b849e206124e11996581c81dcc13da9d11ee3caa1c8176b5525dfead271a6"
    )
    assert verified["summary"] == {
        "physical_case_count": 3,
        "physical_case_metric_pass_count": 3,
        "failure_case_count": 6,
        "failure_case_metric_pass_count": 6,
        "all_development_metrics_pass": True,
        "confirmatory_scientific_protocol": False,
        "host_count": 1,
        "independent_reviewer_approved": False,
        "production_eligible": False,
        "p2_complete": False,
    }
    assert verified["scientifically_validated"] is False
    assert verified["claim_safe"] is False
    assert verified["scientific_blockers"] == list(
        OPENMM_FORCE_DOUBLE_RATTLE_SCIENTIFIC_BLOCKERS
    )


def test_case_rows_retain_all_metrics_traces_and_restarts(observation) -> None:
    rows = {row["case_id"]: row for row in observation["case_rows"]}

    assert set(rows) == {
        "neutral_solute_four_waters",
        "neutral_solute_four_waters_na_cl",
        "positive_solute_four_waters_cl",
    }
    for row in rows.values():
        assert row["status"] == "completed"
        assert row["metric_pass"] is True
        assert all(row["metric_checks"].values())
        assert row["preparation_replay_pass"] is True
        assert len(row["engine_trace"]) == 17
        assert len(row["oracle_trace"]) == 17
        assert len(row["same_step_comparisons"]) == 17
        assert row["engine_restart"]["metric_pass"] is True
        assert row["oracle_restart"]["metric_pass"] is True
        assert float.fromhex(
            row["maxima"][
                "minimum_trajectory_cutoff_margin_angstrom_hex"
            ]
        ) >= OPENMM_FORCE_DOUBLE_RATTLE_CUTOFF_MARGIN_THRESHOLD_ANGSTROM

    charged = rows["positive_solute_four_waters_cl"]
    assert float.fromhex(
        charged["maxima"]["oracle_energy_drift_max_abs_kcal_per_mol_hex"]
    ) <= 1.0e-6


def test_all_failure_rows_are_exact_and_in_denominator(observation) -> None:
    rows = {row["case_id"]: row for row in observation["failure_rows"]}

    assert {
        case_id: row["observed_code"]
        for case_id, row in rows.items()
    } == {
        "cutoff_margin_violation": "cutoff_margin_required",
        "non_neutral_direct_ewald": "neutrality_required",
        "missing_explicit_mass": "explicit_mass_required",
        "oracle_atom_capacity": "oracle_atom_capacity_exceeded",
        "position_projection_budget": (
            "position_projection_budget_exhausted"
        ),
        "tampered_oracle_checkpoint": "checkpoint_digest_mismatch",
    }
    assert all(row["metric_pass"] for row in rows.values())
    assert all(row["status"] == "expected_fail_closed" for row in rows.values())


def test_receipt_binds_source_runtime_and_import_boundary(observation) -> None:
    source = observation["source_identity"]
    runtime = observation["runtime_identity"]

    assert source["absolute_paths_disclosed"] is False
    assert len(source["source_files"]) == 8
    assert len(source["source_manifest_sha256"]) == 64
    assert len(source["runtime_dependency_identity_sha256"]) == 64
    assert source["oracle_import_boundary"] == {
        "stdlib_only_source": True,
        "engine_nve_imported": False,
        "engine_shake_rattle_imported": False,
        "torch_imported": False,
        "openmm_imported": False,
    }
    assert runtime["platform"]["selected_name"] == "Reference"
    assert runtime["platform"]["cpu_substitution_allowed"] is False
    assert runtime["path_values_disclosed"] is False


def test_digest_tampering_fails_before_reexecution(observation) -> None:
    tampered = deepcopy(observation)
    tampered["summary"]["physical_case_metric_pass_count"] = 2

    with pytest.raises(
        OpenMMForceDoubleRattleTrajectoryError,
        match="digest mismatch",
    ):
        require_openmm_force_double_rattle_observation(tampered)


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
    destination = tmp_path / "double-rattle.json"
    written = write_openmm_force_double_rattle_observation(
        destination,
        observation,
    )

    assert written == destination
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert read_openmm_force_double_rattle_observation(destination) == (
        observation
    )
    assert (
        write_openmm_force_double_rattle_observation(
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
        OpenMMForceDoubleRattleTrajectoryError,
        match="refusing to overwrite",
    ):
        write_openmm_force_double_rattle_observation(
            destination,
            different,
        )

    symlink = tmp_path / "receipt-link.json"
    symlink.symlink_to(destination)
    with pytest.raises(
        OpenMMForceDoubleRattleTrajectoryError,
        match="regular non-symlink",
    ):
        read_openmm_force_double_rattle_observation(symlink)
