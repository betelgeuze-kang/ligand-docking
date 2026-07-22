from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.openmm_reference_oracle import (
    FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256,
    OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL,
    OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM,
    OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
    OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
    OPENMM_REFERENCE_REQUIRED_PLATFORM,
    OpenMMReferenceOfflineOracleError,
    openmm_reference_mapping_contract_document,
    require_openmm_reference_mapping_contract_document,
)


def test_offline_module_import_does_not_import_optional_openmm_runtime() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                "import betelgeuze_engine_v2.offline.openmm_reference_oracle;"
                "assert 'openmm' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mapping_contract_freezes_all_energy_force_and_minimization_rows() -> None:
    document = openmm_reference_mapping_contract_document()

    assert (
        document["contract_sha256"] == FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256
    )
    assert FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256 == (
        "0bfc077eded6637ac4cec41fa863ead9bec16ad6665758e1642d12abfb958b43"
    )
    assert document["required_runtime"] == {
        "distribution_name": "OpenMM",
        "distribution_version": OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
        "full_version": OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
        "git_revision": "47684368dbbe4185d068be77d32a962059cfc37c",
        "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
        "cpu_fallback_allowed": False,
        "customer_runtime_dependency": False,
    }
    assert document["coverage"] == {
        "case_count": 27,
        "variant_count": 59,
        "mapped_variant_count": 47,
        "not_applicable_engine_contract_variant_count": 12,
        "skipped_variant_count": 0,
        "all_failure_rows_retained": True,
        "minimization_case_count": 14,
        "mapped_minimization_case_count": 8,
        "not_applicable_minimization_case_count": 6,
    }
    assert len(document["cases"]) == 27
    assert len(document["minimization_cases"]) == 14
    assert document["predefined_acceptance"] == {
        "energy_error_max_kcal_per_mol": (
            OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        ),
        "energy_error_rms_kcal_per_mol": (
            OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
        ),
        "force_error_max_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "force_error_rms_kcal_per_mol_angstrom": (
            OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
        ),
        "thresholds_predefined_before_observation": True,
        "post_observation_tuning_allowed": False,
    }
    assert document["native_minimization_boundary"] == {
        "endpoint_benchmark_is_separate": True,
        "algorithm": "OpenMM LocalEnergyMinimizer L-BFGS",
        "engine_armijo_jacobi_trace_equivalence_claimed": False,
        "checkpoint_restart_equality_claimed": False,
    }
    assert document["production_execution_authorized"] is False
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False


@pytest.mark.parametrize(
    "mutation",
    ("atom_order", "unit", "failure_disposition", "platform", "digest"),
)
def test_mapping_contract_rejects_semantic_and_digest_tampering(
    mutation: str,
) -> None:
    document = deepcopy(openmm_reference_mapping_contract_document())
    if mutation == "atom_order":
        document["cases"][0]["variants"][0]["atom_order_sha256"] = "0" * 64
    elif mutation == "unit":
        document["unit_mapping"]["input_coordinates"] = "nanometer"
    elif mutation == "failure_disposition":
        failure = next(
            variant
            for case in document["cases"]
            for variant in case["variants"]
            if variant["disposition"] == "not_applicable_engine_contract"
        )
        failure["disposition"] = "mapped_openmm_reference"
    elif mutation == "platform":
        document["required_runtime"]["platform"] = "CPU"
    else:
        document["contract_sha256"] = "f" * 64

    with pytest.raises(OpenMMReferenceOfflineOracleError):
        require_openmm_reference_mapping_contract_document(document)


def test_dedicated_workflow_pins_openmm_and_main_ci_owns_contract() -> None:
    dedicated_path = Path(".github/workflows/ci-engine-v2-openmm-reference.yml")
    main_path = Path(".github/workflows/ci-engine-v2-main.yml")
    dedicated = dedicated_path.read_text(encoding="utf-8")
    main = main_path.read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in dedicated
    assert "permissions:\n  contents: read" in dedicated
    assert (
        "uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0" in dedicated
    )
    assert (
        "uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
        in dedicated
    )
    assert "persist-credentials: false" in dedicated
    assert "clean: true" in dedicated
    assert "fetch-depth: 1" in dedicated
    assert "openmm==8.4.0.post2" in dedicated
    assert "cryptography==46.0.5" in dedicated
    assert "torch==2.6.0" in dedicated
    assert "--index-url https://download.pytorch.org/whl/cpu" in dedicated
    assert "ci-engine-v2-openmm-reference.yml" in main
    assert main.count("test_engine_v2_openmm_reference_contract.py") >= 2
    assert (
        dedicated.count("test_engine_v2_openmm_reference_result_review_contract.py")
        >= 2
    )
    assert (
        dedicated.count("test_engine_v2_openmm_reference_result_review_runtime.py") >= 2
    )
    assert (
        dedicated.count("test_engine_v2_s0_production_evidence_bundle_contract.py") >= 2
    )
    assert dedicated.count("test_engine_v2_s0_production_evidence_bundle.py") >= 2
    assert main.count("test_engine_v2_openmm_reference_result_review_contract.py") >= 2
    assert main.count("test_engine_v2_s0_production_evidence_bundle_contract.py") >= 2
    assert main.count("test_engine_v2_s0_production_evidence_bundle.py") >= 2
