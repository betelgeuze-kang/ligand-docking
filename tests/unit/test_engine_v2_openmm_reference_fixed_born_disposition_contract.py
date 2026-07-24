from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from betelgeuze_engine_v2.offline.openmm_reference_fixed_born_disposition import (
    FIXED_BORN_FAILURE_CASE_IDS,
    FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1,
    FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2,
    FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3,
    FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V4,
    FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256,
    openmm_reference_fixed_born_disposition_configuration_document,
)


def test_fixed_born_disposition_configuration_is_frozen_and_claim_closed() -> None:
    configuration = (
        openmm_reference_fixed_born_disposition_configuration_document()
    )

    assert (
        configuration["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
        == "6182cecaa21d5d191baacda1bc9cf7ae7d3cb9eb8b2ca0217757cb23af37c281"
    )
    assert (
        configuration["protocol_revision"]["predecessor_configuration_sha256"]
        == FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V4
        == "2ca9ca3db259eecd94df5a553f934740764bdca3f7d50e2d9d31d4b2695d209e"
    )
    assert (
        configuration["protocol_revision"]["legacy_configuration_chain_sha256s"]
        == [
            FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3,
            FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2,
            FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1,
        ]
    )
    assert (
        FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V3
        == "8cbcf0f7872fdd83bdf5339e230094309000af49ca39d79fcaaaa0bf49bd6a48"
    )
    assert (
        FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V2
        == "ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045"
    )
    assert (
        FROZEN_LEGACY_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256_V1
        == "67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1"
    )
    assert configuration["expected_failed_case_ids"] == list(
        FIXED_BORN_FAILURE_CASE_IDS
    )
    assert len(configuration["case_rows"]) == 2
    assert len(configuration["probe_rows"]) == 8
    assert [row["maximum_iterations"] for row in configuration["probe_rows"][:5]] == [
        64,
        128,
        256,
        512,
        1024,
    ]
    assert configuration["protocol_revision"]["probe_matrix_changed"] is False
    assert (
        configuration["protocol_revision"]["endpoint_health_thresholds_changed"]
        is False
    )
    assert (
        configuration["acceptance"][
            "no_reporter_control_exact_native_endpoint_reproduction_required"
        ]
        is True
    )
    assert (
        configuration["acceptance"][
            "instrumented_baseline_bitwise_endpoint_equality_required"
        ]
        is False
    )
    assert configuration["acceptance"]["post_observation_tuning_allowed"] is False
    assert (
        configuration["reporter_contract"][
            "optimizer_rejection_count_available"
        ]
        is False
    )
    assert all(
        row["frozen_tangent_force_max_threshold_kcal_per_mol_angstrom"]
        == 1.0e-8
        and row["frozen_constraint_max_abs_residual_threshold_angstrom"]
        == 1.0e-10
        for row in configuration["case_rows"]
    )
    assert not any(configuration["claim_boundary"].values())


def test_fixed_born_disposition_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "import betelgeuze_engine_v2.offline."
        "openmm_reference_fixed_born_disposition;"
        "assert 'openmm' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_fixed_born_disposition_source_preserves_failure_boundary() -> None:
    source = Path(
        "betelgeuze_engine_v2/offline/"
        "openmm_reference_fixed_born_disposition.py"
    ).read_text(encoding="utf-8")

    assert "final_constraint_projection_tradeoff_observed" in source
    assert '"frozen_native_endpoint_health_failure_resolved": False' in source
    assert '"optimizer_rejection_count_available": False' in source
    assert '"s0_accepted": False' in source
    assert "post_observation_tuning_allowed" in source
