from __future__ import annotations

from pathlib import Path
import re

from betelgeuze_engine_v2 import DISTRIBUTION_NAME, DISTRIBUTION_VERSION
from tools.check_engine_v2_architecture import inspect_package


def test_independent_package_metadata_matches_version_taxonomy() -> None:
    text = Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    python_range = re.search(
        r'^requires-python\s*=\s*"([^"]+)"', text, flags=re.MULTILINE
    )
    assert name and name.group(1) == DISTRIBUTION_NAME
    assert version and version.group(1) == DISTRIBUTION_VERSION
    assert python_range and python_range.group(1) == ">=3.10,<3.13"
    assert '"cryptography==46.0.5"' in text
    assert '"torch==2.6.0"' in text
    assert '"numpy>=1.26,<3"' in text
    assert '"rdkit==2025.9.6"' in text
    assert 'include = ["betelgeuze_engine_v2*"]' in text
    assert (
        'betelgeuze-engine-v2-prepare-ligand = "betelgeuze_engine_v2.molecular.rdkit_openff_preparation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-redock-diagnostic = "betelgeuze_engine_v2.benchmark.redocking_cli:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-s0-review = "betelgeuze_engine_v2.offline.s0_production_evidence_bundle:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-public-materialize = "betelgeuze_engine_v2.benchmark.public_suite_materialization:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-materialize = "betelgeuze_engine_v2.offline.openmm_reference_materialization:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-native-minimization = "betelgeuze_engine_v2.offline.openmm_reference_native_minimization:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-fixed-born-disposition = "betelgeuze_engine_v2.offline.openmm_reference_fixed_born_disposition:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-constraint-stationarity = "betelgeuze_engine_v2.offline.openmm_reference_constraint_stationarity:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-minimization-stationarity-successor = "betelgeuze_engine_v2.offline.reference_minimization_stationarity_successor:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-nve-trajectory = "betelgeuze_engine_v2.offline.openmm_reference_nve_trajectory:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-explicit-solvent-trajectory = "betelgeuze_engine_v2.offline.openmm_reference_explicit_solvent_trajectory:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-openmm-force-double-rattle-trajectory = "betelgeuze_engine_v2.offline.openmm_force_double_rattle_trajectory:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-intake = "betelgeuze_engine_v2.benchmark.public_posebusters_intake:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-corpus-audit = "betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-prepare = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_preparation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-execute = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_execution:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-rmsd = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_rmsd_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-oracle = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-oracle-runtime = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_runtime_observation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-native-geometry = "betelgeuze_engine_v2.benchmark.public_posebusters_native_geometry:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-external-prepare = "betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-external-execute = "betelgeuze_engine_v2.benchmark.public_posebusters_external_binary_execution:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-external-evaluate-generated = "betelgeuze_engine_v2.benchmark.public_posebusters_external_generated_pose_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-vina-execute = "betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-evaluate-generated = "betelgeuze_engine_v2.benchmark.public_posebusters_generated_pose_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-target-clusters = "betelgeuze_engine_v2.benchmark.public_posebusters_target_cluster_binding:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-rcsb-target-families = "betelgeuze_engine_v2.benchmark.public_posebusters_rcsb_target_family_binding:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-ranking-intake = "betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-ranking-test-partitions = "betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_test_partition:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-external-ranking-evaluate = "betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-external-ranking-reproduce = "betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_reproduction:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking = "betelgeuze_engine_v2.benchmark.public_posebusters_internal_diagnostic_ranking_evaluation:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-public-ranking-corpus-intake = "betelgeuze_engine_v2.benchmark.public_pose_ranking_corpus_intake:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-public-ranking-calibration-partition-intake = "betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_partition_intake:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-public-ranking-calibration-training-view = "betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_training_view:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-public-ranking-fit-validation = "betelgeuze_engine_v2.benchmark.public_pose_ranking_fit_validation_selection:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-pose-scaffold-identity = "betelgeuze_engine_v2.benchmark.public_posebusters_pose_scaffold_identity:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic = "betelgeuze_engine_v2.benchmark.public_posebusters_prepared_ligand_diagnostic:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-openbabel-compare = "betelgeuze_engine_v2.benchmark.public_posebusters_openbabel_charge_type_comparison:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-sulfur-qm-esp = "betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_qm_esp:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-sulfur-interaction = "betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_interaction_energy:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-sulfur-reproduce = "betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_interaction_external_reproduction:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2-posebusters-vina-sulfur-invariance = "betelgeuze_engine_v2.benchmark.public_posebusters_vina_sulfur_type_invariance:main"'
        in text
    )


def test_ast_architecture_guard_accepts_canonical_engine_package() -> None:
    violations = inspect_package(Path("betelgeuze_engine_v2").resolve())
    assert violations == []


def test_overlap_matrix_records_both_independent_merge_lanes() -> None:
    text = Path("docs/engine_v2_pr_overlap_matrix.md").read_text(encoding="utf-8")
    for marker in ("#43", "#44", "#45", "#46", "#47", "#48", "#49"):
        assert marker in text
    assert "#50 -> #51 -> #52 -> #53 -> #54 -> V2-F" in text
    assert "#44 -> #45 -> #46 -> #47 -> #48" in text
    assert "통째 병합 금지" in text
