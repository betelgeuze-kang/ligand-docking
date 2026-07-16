from __future__ import annotations

import numpy as np
import pytest

from betelgeuze_engine.biodiscovery import TierBetaScreening
from betelgeuze_engine.biodiscovery import pose as biodiscovery_pose
from betelgeuze_engine.biodiscovery import screening as biodiscovery_screening
from betelgeuze_engine.biodiscovery.strict_pose_contracts import (
    STRICT_POSE_RMSD_CONTRACT_VERSION,
    state_scoped_pose_rmsd_diagnostics,
)


def test_public_import_paths_install_one_strict_contract() -> None:
    assert (
        getattr(TierBetaScreening, "__strict_pose_contract__", "")
        == STRICT_POSE_RMSD_CONTRACT_VERSION
    )
    assert TierBetaScreening is biodiscovery_screening.TierBetaScreening
    assert biodiscovery_pose.pose_rmsd.__module__.endswith("strict_pose_contracts")
    assert biodiscovery_pose.symmetry_aware_pose_rmsd.__module__.endswith(
        "strict_pose_contracts"
    )


def test_pose_rmsd_rejects_truncation_nonfinite_and_bad_bijections() -> None:
    two_atoms = np.zeros((2, 3), dtype=np.float64)
    three_atoms = np.zeros((3, 3), dtype=np.float64)
    with pytest.raises(ValueError, match="shapes must match exactly"):
        biodiscovery_pose.pose_rmsd(two_atoms, three_atoms)
    with pytest.raises(ValueError, match=r"shape \[N, 3\]"):
        biodiscovery_pose.pose_rmsd(np.zeros((2, 4)), np.zeros((2, 4)))

    nonfinite = two_atoms.copy()
    nonfinite[0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        biodiscovery_pose.pose_rmsd(two_atoms, nonfinite)

    with pytest.raises(ValueError, match="complete atom-index bijection"):
        biodiscovery_pose.symmetry_aware_pose_rmsd(
            three_atoms,
            three_atoms,
            [(0, 0, 2)],
        )
    with pytest.raises(ValueError, match="exactly 3 indices"):
        biodiscovery_pose.symmetry_aware_pose_rmsd(
            three_atoms,
            three_atoms,
            [(0, 1)],
        )


def test_conformer_alignment_removes_rigid_motion_but_not_internal_change() -> None:
    reference = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 1.0, 0.5]],
        dtype=np.float64,
    )
    rotation = np.asarray(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    moved = reference @ rotation.T + np.asarray([8.0, -3.0, 2.5])
    distorted = moved.copy()
    distorted[2] += np.asarray([0.0, 1.25, 0.0])

    assert biodiscovery_pose.pose_rmsd(reference, moved) > 1.0
    assert biodiscovery_pose.aligned_symmetry_aware_pose_rmsd(
        reference,
        moved,
    ) == pytest.approx(0.0, abs=1e-10)
    assert (
        biodiscovery_pose.aligned_symmetry_aware_pose_rmsd(reference, distorted)
        > 0.1
    )


def test_conformer_diversity_preserves_v1_reader_fields_and_reports_effective_method() -> None:
    reference = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 1.0, 0.5]],
        dtype=np.float64,
    )
    rotation = np.asarray(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    moved = reference @ rotation.T + np.asarray([8.0, -3.0, 2.5])
    distorted = moved.copy()
    distorted[2] += np.asarray([0.0, 1.25, 0.0])

    diagnostics = biodiscovery_pose.conformer_diversity_diagnostics(
        np.stack([reference, moved, distorted]),
        smiles="CCO",
        diversity_threshold_a=0.1,
    )

    assert diagnostics["schema_version"] == "tier_beta_conformer_diversity_v1"
    assert diagnostics["method"] == "atom_order_pairwise_heavy_atom_rmsd"
    assert diagnostics["method_compatibility_alias"] is True
    assert diagnostics["strict_contract_version"] == STRICT_POSE_RMSD_CONTRACT_VERSION
    assert diagnostics["effective_method"] == (
        "kabsch_aligned_symmetry_aware_heavy_atom_rmsd"
    )
    assert diagnostics["alignment"] == (
        "centroid_translation_removed_proper_rotation_kabsch"
    )
    assert diagnostics["pairwise_rmsd_min_a"] == pytest.approx(0.0, abs=1e-10)
    assert diagnostics["pairwise_rmsd_max_a"] > 0.1


def test_state_scoped_diagnostics_never_compare_different_atom_count_states() -> None:
    rows = [
        {
            "pose_index": 0,
            "pose_rank": 1,
            "ligand_state": {"state_id": "state-cc", "smiles": "CC"},
            "pose_search": {},
        },
        {
            "pose_index": 1,
            "pose_rank": 2,
            "ligand_state": {"state_id": "state-cc", "smiles": "CC"},
            "pose_search": {},
        },
        {
            "pose_index": 2,
            "pose_rank": 3,
            "ligand_state": {"state_id": "state-ccc", "smiles": "CCC"},
            "pose_search": {},
        },
        {
            "pose_index": 3,
            "pose_rank": 4,
            "ligand_state": {"state_id": "state-ccc", "smiles": "CCC"},
            "pose_search": {},
        },
    ]
    coords = {
        0: np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64),
        1: np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64),
        2: np.asarray(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            dtype=np.float64,
        ),
        3: np.asarray(
            [[0.0, 0.0, 0.0], [1.1, 0.2, 0.0], [2.0, 0.0, 0.0]],
            dtype=np.float64,
        ),
    }

    diagnostics = state_scoped_pose_rmsd_diagnostics(
        biodiscovery_pose,
        rows,
        coords,
        fallback_ligand_smiles="CC",
        threshold_a=0.25,
    )

    assert diagnostics["coordinate_scope"] == "same_ligand_state_receptor_frame"
    assert diagnostics["state_cluster_count"] == 2
    assert rows[0]["pose_rmsd_reference_state_id"] == "state-cc"
    assert rows[1]["pose_rmsd_reference_state_id"] == "state-cc"
    assert rows[2]["pose_rmsd_reference_state_id"] == "state-ccc"
    assert rows[3]["pose_rmsd_reference_state_id"] == "state-ccc"
    assert rows[0]["pose_rmsd_reference_pose_index"] == 0
    assert rows[2]["pose_rmsd_reference_pose_index"] == 2
    assert rows[1]["symmetry_aware_pose_rmsd_to_top1_a"] == pytest.approx(0.0)
    assert rows[2]["symmetry_aware_pose_rmsd_to_top1_a"] == pytest.approx(0.0)
    assert all(
        row["pose_rmsd_scope"] == "same_ligand_state_receptor_frame"
        for row in rows
    )
    assert all(
        row["strict_pose_rmsd_contract_version"]
        == STRICT_POSE_RMSD_CONTRACT_VERSION
        for row in rows
    )


def test_cluster_contract_keeps_reader_schema_but_exposes_receptor_frame_semantics() -> None:
    rows = [{"pose_index": 0}, {"pose_index": 1}]
    coords = {
        0: np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64),
        1: np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64),
    }

    summary = biodiscovery_pose.cluster_poses_by_symmetry(
        rows,
        coords,
        [(1, 0)],
        threshold_a=0.1,
    )

    assert summary["status"] == "symmetry_aware_rmsd_clustered"
    assert summary["method"] == "rdkit_automorphism_min_rmsd"
    assert summary["effective_method"] == (
        "rdkit_automorphism_min_receptor_frame_rmsd"
    )
    assert summary["coordinate_scope"] == "receptor_frame_same_ligand_state"
    assert summary["cluster_count"] == 1
    assert rows[1]["symmetry_aware_pose_rmsd_to_cluster_representative_a"] == 0.0
    assert rows[1]["pose_rmsd_clustering"]["schema_version"] == (
        "tier_beta_pose_rmsd_clustering_v1"
    )
