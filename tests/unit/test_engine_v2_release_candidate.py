from __future__ import annotations

import json
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

from betelgeuze_engine_v2.contracts import (
    ALL_ATOM_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    DISTRIBUTION_VERSION,
    ENGINE_API_VERSION,
    ENGINE_RESULT_SCHEMA_VERSION,
    RUNTIME_INPUT_SCHEMA_VERSION,
    VERSION_TAXONOMY,
)
from tools.build_engine_v2_sbom import SPDX_VERSION


def test_release_candidate_versions_and_typed_package_metadata_match() -> None:
    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert DISTRIBUTION_VERSION == "0.3.0a1"
    assert VERSION_TAXONOMY.distribution_version == DISTRIBUTION_VERSION
    assert ENGINE_API_VERSION == "2.0.0"
    assert ALL_ATOM_SCHEMA_VERSION == "2.0.0"
    assert ENGINE_RESULT_SCHEMA_VERSION == "2.0.0"
    assert CHECKPOINT_SCHEMA_VERSION == "2.0.0"
    assert RUNTIME_INPUT_SCHEMA_VERSION == "2.1.0"
    assert VERSION_TAXONOMY.engine_api_version != DISTRIBUTION_VERSION
    assert metadata["project"]["version"] == DISTRIBUTION_VERSION
    assert metadata["project"]["requires-python"] == ">=3.10,<3.13"
    assert metadata["project"]["scripts"] == {
        "betelgeuze-engine-v2-prepare-ligand": (
            "betelgeuze_engine_v2.molecular.rdkit_openff_preparation:main"
        ),
        "betelgeuze-engine-v2-redock-diagnostic": (
            "betelgeuze_engine_v2.benchmark.redocking_cli:main"
        ),
        "betelgeuze-engine-v2-openmm-materialize": (
            "betelgeuze_engine_v2.offline.openmm_reference_materialization:main"
        ),
        "betelgeuze-engine-v2-openmm-native-minimization": (
            "betelgeuze_engine_v2.offline."
            "openmm_reference_native_minimization:main"
        ),
        "betelgeuze-engine-v2-openmm-fixed-born-disposition": (
            "betelgeuze_engine_v2.offline."
            "openmm_reference_fixed_born_disposition:main"
        ),
        "betelgeuze-engine-v2-openmm-constraint-stationarity": (
            "betelgeuze_engine_v2.offline."
            "openmm_reference_constraint_stationarity:main"
        ),
        "betelgeuze-engine-v2-minimization-stationarity-successor": (
            "betelgeuze_engine_v2.offline."
            "reference_minimization_stationarity_successor:main"
        ),
        "betelgeuze-engine-v2-openmm-nve-trajectory": (
            "betelgeuze_engine_v2.offline."
            "openmm_reference_nve_trajectory:main"
        ),
        "betelgeuze-engine-v2-openmm-explicit-solvent-trajectory": (
            "betelgeuze_engine_v2.offline."
            "openmm_reference_explicit_solvent_trajectory:main"
        ),
        "betelgeuze-engine-v2-openmm-force-double-rattle-trajectory": (
            "betelgeuze_engine_v2.offline."
            "openmm_force_double_rattle_trajectory:main"
        ),
        "betelgeuze-engine-v2-posebusters-intake": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_intake:main"
        ),
        "betelgeuze-engine-v2-posebusters-corpus-audit": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-prepare": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_preparation:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-execute": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_execution:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-rmsd": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_rmsd_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-oracle": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-oracle-runtime": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_runtime_observation:main"
        ),
        "betelgeuze-engine-v2-posebusters-external-prepare": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation:main"
        ),
        "betelgeuze-engine-v2-posebusters-external-execute": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_external_binary_execution:main"
        ),
        "betelgeuze-engine-v2-posebusters-external-evaluate-generated": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_external_generated_pose_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-vina-execute": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution:main"
        ),
        "betelgeuze-engine-v2-posebusters-evaluate-generated": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_generated_pose_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-target-clusters": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_target_cluster_binding:main"
        ),
        "betelgeuze-engine-v2-posebusters-rcsb-target-families": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_rcsb_target_family_binding:main"
        ),
        "betelgeuze-engine-v2-posebusters-ranking-intake": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake:main"
        ),
        "betelgeuze-engine-v2-posebusters-ranking-test-partitions": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_pose_ranking_test_partition:main"
        ),
        "betelgeuze-engine-v2-posebusters-external-ranking-evaluate": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_external_ranking_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-external-ranking-reproduce": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_external_ranking_reproduction:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_diagnostic_ranking_evaluation:main"
        ),
        "betelgeuze-engine-v2-public-ranking-corpus-intake": (
            "betelgeuze_engine_v2.benchmark."
            "public_pose_ranking_corpus_intake:main"
        ),
        "betelgeuze-engine-v2-public-ranking-calibration-partition-intake": (
            "betelgeuze_engine_v2.benchmark."
            "public_pose_ranking_calibration_partition_intake:main"
        ),
        "betelgeuze-engine-v2-public-ranking-calibration-training-view": (
            "betelgeuze_engine_v2.benchmark."
            "public_pose_ranking_calibration_training_view:main"
        ),
        "betelgeuze-engine-v2-public-ranking-fit-validation": (
            "betelgeuze_engine_v2.benchmark."
            "public_pose_ranking_fit_validation_selection:main"
        ),
        "betelgeuze-engine-v2-posebusters-pose-scaffold-identity": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_pose_scaffold_identity:main"
        ),
        "betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_prepared_ligand_diagnostic:main"
        ),
        "betelgeuze-engine-v2-posebusters-openbabel-compare": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_openbabel_charge_type_comparison:main"
        ),
        "betelgeuze-engine-v2-posebusters-sulfur-qm-esp": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_qm_esp:main"
        ),
        "betelgeuze-engine-v2-posebusters-sulfur-interaction": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_sulfur_interaction_energy:main"
        ),
        "betelgeuze-engine-v2-posebusters-sulfur-reproduce": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_sulfur_interaction_external_reproduction:main"
        ),
        "betelgeuze-engine-v2-posebusters-vina-sulfur-invariance": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_vina_sulfur_type_invariance:main"
        ),
        "betelgeuze-engine-v2-posebusters-native-geometry": (
            "betelgeuze_engine_v2.benchmark.public_posebusters_native_geometry:main"
        ),
        "betelgeuze-engine-v2-public-materialize": (
            "betelgeuze_engine_v2.benchmark.public_suite_materialization:main"
        ),
        "betelgeuze-engine-v2-s0-review": (
            "betelgeuze_engine_v2.offline.s0_production_evidence_bundle:main"
        ),
    }
    assert set(metadata["project"]["dependencies"]) == {
        "cryptography==46.0.5",
        "numpy>=1.26,<3",
        "torch==2.6.0",
    }
    assert metadata["project"]["optional-dependencies"] == {
        "chemistry": ["rdkit==2025.9.6"]
    }
    assert metadata["build-system"]["requires"] == [
        "setuptools==75.8.2",
        "wheel==0.45.1",
    ]
    assert "Typing :: Typed" in metadata["project"]["classifiers"]
    assert metadata["tool"]["setuptools"]["package-data"]["betelgeuze_engine_v2"] == [
        "py.typed"
    ]
    assert metadata["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "betelgeuze_engine_v2*"
    ]
    assert Path("betelgeuze_engine_v2/py.typed").is_file()


def test_static_analysis_configuration_is_scoped_to_independent_contracts() -> None:
    pyright = json.loads(
        Path("packaging/engine-v2/pyrightconfig.json").read_text(encoding="utf-8")
    )
    assert pyright["typeCheckingMode"] == "basic"
    assert any("betelgeuze_engine_v2/contracts" in path for path in pyright["include"])
    assert "../../betelgeuze_engine_v2/molecular/legacy.py" in pyright["exclude"]
    assert pyright["extraPaths"] == ["../.."]

    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert set(metadata["tool"]["ruff"]["lint"]["select"]) == {"E4", "E7", "E9", "F"}


def test_release_candidate_documents_preserve_non_promotion_boundary() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/engine_v2_0_3_0a1.md").read_text(encoding="utf-8")
    assert "0.3.0a1" in changelog
    assert "does not establish" in changelog
    for flag in (
        "claim_safe",
        "scientifically_validated",
        "benchmark_validated",
        "customer_execution_enabled",
    ):
        assert f"{flag}=false" in release
        assert f"{flag}=true" not in release
    assert "byte-identical wheel SHA-256" in release


def test_sbom_contract_uses_spdx_23() -> None:
    assert SPDX_VERSION == "SPDX-2.3"
    source = Path("tools/build_engine_v2_sbom.py").read_text(encoding="utf-8")
    assert "DEPENDS_ON" in source
    assert "wheel_sha256" in source


def test_release_workflow_splits_pinned_static_and_matrix_jobs() -> None:
    workflow = Path(".github/workflows/ci-engine-v2-release-candidate.yml").read_text(
        encoding="utf-8"
    )
    assert "\n  static-analysis:\n" in workflow
    assert "\n  release-matrix:\n" in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'python-version: ["3.10", "3.11", "3.12"]' in workflow
    assert "Upload static-analysis diagnostics\n        if: always()" in workflow
    assert "persist-credentials: false" in workflow
    assert "clean: true" in workflow
    assert workflow.count("python -m pip install pip==25.0.1") >= 2
    assert '"$venv/bin/python" -m pip install pip==25.0.1' in workflow
    assert "docs/engine_v2_pr_overlap_matrix.md" in workflow
    assert ".github/workflows/ci-engine-v2-release-candidate.yml" in workflow
    assert (
        "tests/unit/test_engine_v2_public_pose_ranking_calibration_partition_intake.py"
        in workflow
    )
    assert workflow.count("betelgeuze-engine-v2-s0-review") >= 2
    assert "betelgeuze-engine-v2-redock-diagnostic" in workflow
    assert "betelgeuze-engine-v2-prepare-ligand" in workflow
    assert "betelgeuze-engine-v2-openmm-materialize" in workflow
    assert "betelgeuze-engine-v2-openmm-native-minimization" in workflow
    assert "betelgeuze-engine-v2-openmm-fixed-born-disposition" in workflow
    assert "betelgeuze-engine-v2-openmm-constraint-stationarity" in workflow
    assert "betelgeuze-engine-v2-minimization-stationarity-successor" in workflow
    assert "betelgeuze-engine-v2-openmm-nve-trajectory" in workflow
    assert (
        "betelgeuze-engine-v2-openmm-force-double-rattle-trajectory"
        in workflow
    )
    assert "betelgeuze-engine-v2-posebusters-intake" in workflow
    assert "betelgeuze-engine-v2-posebusters-corpus-audit" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-prepare" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-execute" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-rmsd" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-oracle" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-oracle-runtime" in workflow
    assert "betelgeuze-engine-v2-posebusters-external-prepare" in workflow
    assert "betelgeuze-engine-v2-posebusters-external-execute" in workflow
    assert "betelgeuze-engine-v2-posebusters-external-evaluate-generated" in workflow
    assert "betelgeuze-engine-v2-posebusters-vina-execute" in workflow
    assert "betelgeuze-engine-v2-posebusters-evaluate-generated" in workflow
    assert "betelgeuze-engine-v2-posebusters-target-clusters" in workflow
    assert "betelgeuze-engine-v2-posebusters-rcsb-target-families" in workflow
    assert "betelgeuze-engine-v2-posebusters-ranking-intake" in workflow
    assert "betelgeuze-engine-v2-posebusters-ranking-test-partitions" in workflow
    assert "betelgeuze-engine-v2-posebusters-external-ranking-evaluate" in workflow
    assert "betelgeuze-engine-v2-posebusters-external-ranking-reproduce" in workflow
    assert "betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking" in workflow
    assert "betelgeuze-engine-v2-public-ranking-corpus-intake" in workflow
    assert (
        "betelgeuze-engine-v2-public-ranking-calibration-partition-intake"
        in workflow
    )
    assert (
        "betelgeuze-engine-v2-public-ranking-calibration-training-view"
        in workflow
    )
    assert (
        "betelgeuze-engine-v2-public-ranking-fit-validation"
        in workflow
    )
    assert "betelgeuze-engine-v2-posebusters-pose-scaffold-identity" in workflow
    assert "betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic" in workflow
    assert "betelgeuze-engine-v2-posebusters-openbabel-compare" in workflow
    assert "betelgeuze-engine-v2-posebusters-sulfur-qm-esp" in workflow
    assert "betelgeuze-engine-v2-posebusters-sulfur-interaction" in workflow
    assert "betelgeuze-engine-v2-posebusters-sulfur-reproduce" in workflow
    assert "betelgeuze-engine-v2-posebusters-vina-sulfur-invariance" in workflow
    assert "betelgeuze-engine-v2-posebusters-native-geometry" in workflow
    assert "FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256" in workflow
    action_refs = re.findall(r"uses: [^@\s]+@([^\s]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)


def test_all_wheel_build_lanes_install_the_exact_backend_contract() -> None:
    required = (
        "build==1.2.2.post1",
        "setuptools==75.8.2",
        "wheel==0.45.1",
    )
    for path in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-package.yml",
        ".github/workflows/ci-engine-v2-release-candidate.yml",
    ):
        workflow = Path(path).read_text(encoding="utf-8")
        for requirement in required:
            assert requirement in workflow, f"{path} does not install {requirement}"
