from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from betelgeuze_engine_v2.offline.openmm_reference_native_minimization import (
    FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1,
    FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1_1,
    FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1_2,
    FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256,
    openmm_reference_native_minimization_configuration_document,
)


def test_native_minimization_configuration_is_frozen_and_claim_closed() -> None:
    configuration = openmm_reference_native_minimization_configuration_document()

    assert (
        configuration["configuration_sha256"]
        == FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
        == "9189afe3a01a7eb8ee2c26e8b233db6c2250a14317f8498e34303c1c2b4fdf51"
    )
    assert (
        configuration["superseded_configuration_sha256"]
        == FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1_2
        == "75aaf26a338699df1e9a398b74e9f065e60717d310a3b23c00875a3a5e3e7e34"
    )
    assert configuration["legacy_configuration_chain_sha256s"] == [
        FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1_1,
        FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1,
    ]
    assert (
        FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1_1
        == "0b48b892dcbf9fdb5937a487a2ff5d222e31e98050e2c05afa473c1eddaf3368"
    )
    assert (
        FROZEN_LEGACY_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256_V1
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
        configuration["acceptance"]["final_context_constraint_projection_required"]
        is True
    )
    assert configuration["claim_boundary"] == {
        "engine_trace_equivalence_claimed": False,
        "cross_algorithm_endpoint_equivalence_claimed": False,
        "openmm_checkpoint_restart_equality_claimed": False,
        "production_protocol_execution": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def test_native_minimization_contract_import_does_not_load_openmm() -> None:
    source = (
        "import sys;"
        "import betelgeuze_engine_v2.offline.openmm_reference_native_minimization;"
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


def test_native_minimization_source_keeps_endpoint_equivalence_ungated() -> None:
    source = Path(
        "betelgeuze_engine_v2/offline/openmm_reference_native_minimization.py"
    ).read_text(encoding="utf-8")

    assert "native_minimize_endpoint" in source
    assert "engine_at_openmm_endpoint_evaluation" in source
    assert "all_failure_rows_retained" in source
    assert '"cross_algorithm_endpoint_equivalence_claimed": False' in source
    assert '"s0_accepted": False' in source
    assert "post_observation_tuning_allowed" in source
