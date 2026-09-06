"""Strict pose-summary integrity and diagnostic-consumer regression tests."""
from __future__ import annotations

import numpy as np
import pytest

from betelgeuze_engine.biodiscovery import pose as biodiscovery_pose
from betelgeuze_engine.biodiscovery import screening as biodiscovery_screening
from betelgeuze_engine.biodiscovery.screening import TierBetaScreening
from tests.unit.test_biodiscovery_screening import MINI_PDB, VALID_SMILES


class TestChemistryValiditySummary:
    @staticmethod
    def ligand_metadata(**overrides):
        metadata = {
            "valid": True, "blockers": [], "atom_count": 6, "bond_count": 6,
            "formal_charges": [0, 0, 0, 0, 0, 0],
            "chirality_status": "not_assessed",
            "protonation_status": "not_assessed",
            "tautomer_status": "not_assessed",
        }
        metadata.update(overrides)
        return metadata

    @pytest.mark.parametrize("coords,reason", [
        (np.zeros((0, 3)), "empty_pose_coordinates"),
        (np.zeros((6, 2)), "invalid_pose_coordinate_shape"),
        (np.zeros((6, 4)), "invalid_pose_coordinate_shape"),
        (np.zeros(18), "invalid_pose_coordinate_shape"),
        (np.zeros((1, 6, 3)), "invalid_pose_coordinate_shape"),
        (np.array(0), "invalid_pose_coordinate_shape"),
        (None, "invalid_pose_coordinate_shape"),
        ([], "invalid_pose_coordinate_shape"),
        ([[0, 0, 0], [1, 2]], "invalid_pose_coordinates"),
        (np.zeros((5, 3)), "pose_atom_count_mismatch"),
        (np.zeros((7, 3)), "pose_atom_count_mismatch"),
    ])
    def test_rejects_empty_malformed_or_mismatched_pose(self, coords, reason):
        result = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert result["valid"] is False
        assert result["status"] == "blocked_chemical_validity"
        assert reason in result["claim_blockers"]

    @pytest.mark.parametrize("dtype", [bool, complex, str, object, "S3", "datetime64[D]"])
    def test_unsupported_dtypes_are_not_silently_coerced(self, dtype):
        coords = np.zeros((6, 3)).astype(dtype)
        result = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert result["valid"] is False
        assert result["coordinate_finite"] is False
        assert "invalid_pose_coordinate_dtype" in result["claim_blockers"]

    @pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
    def test_nonfinite_coordinates_remain_blocked(self, value):
        coords = np.zeros((6, 3))
        coords[1, 2] = value
        result = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert result["valid"] is False
        assert result["coordinate_finite"] is False
        assert result["claim_blockers"] == ["nonfinite_pose_coordinates"]

    @pytest.mark.parametrize("mask", [False, True])
    def test_masked_arrays_are_not_stripped_to_ordinary_coordinates(self, mask):
        coords = np.ma.array(np.zeros((6, 3)), mask=mask)
        result = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert result["valid"] is False
        assert "masked_pose_coordinates" in result["claim_blockers"]

    @pytest.mark.parametrize("count", [
        None, 0, -1, True, False, np.bool_(True), 6.0, 6.9, np.float64(6.0),
        "6", "bad", float("nan"), float("inf"), [6], np.array(6), np.array([6]),
    ])
    def test_atom_count_requires_a_positive_integer_without_coercion(self, count):
        result = biodiscovery_pose.chemistry_validity_summary(
            self.ligand_metadata(atom_count=count), np.zeros((6, 3)),
        )
        assert result["valid"] is False
        assert result["atom_count"] == 0
        assert "invalid_ligand_atom_count" in result["claim_blockers"]
        assert "pose_atom_count_mismatch" not in result["claim_blockers"]

    def test_missing_atom_count_is_not_inferred_from_coordinates(self):
        metadata = self.ligand_metadata()
        del metadata["atom_count"]
        result = biodiscovery_pose.chemistry_validity_summary(metadata, np.zeros((6, 3)))
        assert result["valid"] is False
        assert "invalid_ligand_atom_count" in result["claim_blockers"]

    @pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.uint64])
    @pytest.mark.parametrize("count", [6, np.int64(6), np.uint64(6)])
    def test_normal_result_schema_and_values_are_unchanged(self, dtype, count):
        result = biodiscovery_pose.chemistry_validity_summary(
            self.ligand_metadata(atom_count=count), np.zeros((6, 3), dtype=dtype),
        )
        assert result == {
            "status": "chemical_validity_pass", "valid": True, "claim_blockers": [],
            "atom_count": 6, "bond_count": 6, "formal_charge_sum": 0,
            "chirality_status": "not_assessed", "protonation_status": "not_assessed",
            "tautomer_status": "not_assessed", "coordinate_finite": True,
        }
        assert type(result["atom_count"]) is int

    def test_nested_numeric_lists_and_noncontiguous_readonly_arrays_are_supported(self):
        coords = np.arange(36, dtype=np.float64).reshape(6, 6)[:, ::2]
        coords.setflags(write=False)
        expected = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert expected["valid"] is True
        assert biodiscovery_pose.chemistry_validity_summary(
            self.ligand_metadata(), coords.tolist(),
        ) == expected

    @pytest.mark.parametrize("count", [1, 2, 10])
    def test_validity_is_not_special_cased_to_the_six_atom_fixture(self, count):
        result = biodiscovery_pose.chemistry_validity_summary(
            self.ligand_metadata(atom_count=count), np.zeros((count, 3)),
        )
        assert result["valid"] is True
        assert result["atom_count"] == count

    @pytest.mark.parametrize("upstream_valid", [False, None, 1, "true"])
    def test_coordinates_cannot_override_upstream_invalidity(self, upstream_valid):
        result = biodiscovery_pose.chemistry_validity_summary(
            self.ligand_metadata(valid=upstream_valid), np.zeros((6, 3)),
        )
        assert result["valid"] is False

    def test_prior_blockers_are_preserved_without_mutating_metadata_or_coordinates(self):
        metadata = self.ligand_metadata(blockers=["unassigned_ligand_chirality"])
        coords = np.zeros((5, 3), dtype=np.float32)
        coords_before = coords.copy()
        result = biodiscovery_pose.chemistry_validity_summary(metadata, coords)
        assert result["claim_blockers"] == ["unassigned_ligand_chirality", "pose_atom_count_mismatch"]
        assert metadata["blockers"] == ["unassigned_ligand_chirality"]
        np.testing.assert_array_equal(coords, coords_before)
        assert result["valid"] is False

    def test_repeated_blocker_is_not_appended_again(self):
        metadata = self.ligand_metadata(blockers=["pose_atom_count_mismatch"])
        result = biodiscovery_pose.chemistry_validity_summary(metadata, np.zeros((5, 3)))
        assert result["claim_blockers"] == ["pose_atom_count_mismatch"]

    def test_finite_values_outside_float64_range_remain_blocked(self):
        if np.finfo(np.longdouble).max <= np.finfo(np.float64).max:
            pytest.skip("longdouble has no additional exponent range on this platform")
        coords = np.zeros((6, 3), dtype=np.longdouble)
        coords[0, 0] = np.finfo(np.longdouble).max
        result = biodiscovery_pose.chemistry_validity_summary(self.ligand_metadata(), coords)
        assert result["valid"] is False
        assert "nonfinite_pose_coordinates" in result["claim_blockers"]

    def test_existing_charge_and_preparation_metadata_are_preserved(self):
        metadata = self.ligand_metadata(
            formal_charges=[-1, 0, 0, 0, 0, 0], chirality_status="assigned",
            protonation_status="input_state", tautomer_status="input_tautomer",
        )
        result = biodiscovery_pose.chemistry_validity_summary(metadata, np.zeros((6, 3)))
        assert result["formal_charge_sum"] == -1
        assert result["chirality_status"] == "assigned"
        assert result["protonation_status"] == "input_state"
        assert result["tautomer_status"] == "input_tautomer"
        assert result["valid"] is True


class TestChemistryValidityConsumer:
    def test_screening_alias_uses_canonical_validity_function(self):
        assert biodiscovery_screening._chemistry_validity_summary is biodiscovery_pose.chemistry_validity_summary

    @pytest.mark.parametrize("coords,reason", [
        (np.zeros((0, 3)), "empty_pose_coordinates"),
        (np.zeros((6, 2)), "invalid_pose_coordinate_shape"),
        (np.zeros((5, 3)), "pose_atom_count_mismatch"),
    ])
    def test_invalid_summary_reaches_diagnostic_rows_and_abstention(self, monkeypatch, coords, reason):
        # Inject only at the summary boundary, after normal scoring. This tests
        # diagnostic propagation, not reachability of corrupt search candidates.
        def summarize_invalid_pose(metadata, actual_coords):
            return biodiscovery_pose.chemistry_validity_summary(metadata, coords)

        monkeypatch.setattr(biodiscovery_screening, "_chemistry_validity_summary", summarize_invalid_pose)
        result = TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
            protein_input=MINI_PDB, ligand_input=VALID_SMILES,
        )
        assert result.pose_scores
        for row in result.pose_scores:
            assert row["chemistry_validity"]["valid"] is False
            assert reason in row["chemistry_validity"]["claim_blockers"]
            assert row["abstention"] is True
            assert "chemistry_validity_blocked" in row["abstention_reasons"]
        assert result.result_manifest["claim_metadata"]["claim_safe"] is False


class TestStrictRMSDInputs:
    @pytest.mark.parametrize("entrypoint", [
        "pose_rmsd", "aligned_pose_rmsd", "symmetry_aware_pose_rmsd",
        "aligned_symmetry_aware_pose_rmsd",
    ])
    @pytest.mark.parametrize("side", ["left", "right"])
    @pytest.mark.parametrize("coords", [
        np.full((2, 3), 1j), np.full((2, 3), "0"),
        np.zeros((2, 3), dtype=bool), np.zeros((2, 3), dtype=object),
        np.ma.array(np.zeros((2, 3)), mask=True),
        np.ma.array(np.zeros((2, 3)), mask=False),
    ])
    def test_invalid_representations_are_rejected_on_both_sides(self, entrypoint, side, coords):
        left, right = (coords, np.zeros((2, 3))) if side == "left" else (np.zeros((2, 3)), coords)
        with pytest.raises(ValueError, match="real numeric|masked coordinates"):
            getattr(biodiscovery_pose, entrypoint)(left, right)

    @pytest.mark.parametrize("align", [False, True])
    def test_best_mapping_does_not_hide_invalid_representation(self, align):
        with pytest.raises(ValueError, match="real numeric"):
            biodiscovery_pose.best_symmetry_mapped_pose(
                np.zeros((2, 3)), np.full((2, 3), 1j), [(1, 0)], align=align,
            )

    @pytest.mark.parametrize("coords,reason", [
        (np.zeros((0, 3)), "at least one atom"),
        (np.zeros((2, 2)), "shape"),
        (np.zeros((1, 2, 3)), "shape"),
        (np.zeros((3, 3)), "shapes must match exactly"),
        ([[0, 0, 0], [1, 2]], "real numeric"),
        (np.full((2, 3), np.nan), "non-finite"),
        (np.full((2, 3), np.inf), "non-finite"),
        (np.zeros((2, 3), dtype="datetime64[D]"), "real numeric"),
        (np.full((2, 3), b"0"), "real numeric"),
    ])
    def test_existing_shape_and_finiteness_contracts_remain_strict(self, coords, reason):
        with pytest.raises(ValueError, match=reason):
            biodiscovery_pose.pose_rmsd(np.zeros((2, 3)), coords)

    @pytest.mark.parametrize("entrypoint", [
        "pose_rmsd", "aligned_pose_rmsd", "symmetry_aware_pose_rmsd",
        "aligned_symmetry_aware_pose_rmsd",
    ])
    @pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.uint64])
    def test_supported_real_dtypes_keep_zero_self_distance(self, entrypoint, dtype):
        coords = np.array([[0, 0, 0], [1, 2, 3], [4, 1, 2], [1, 5, 2]], dtype=dtype)
        before = coords.copy()
        assert getattr(biodiscovery_pose, entrypoint)(coords, coords) == pytest.approx(0.0, abs=1e-12)
        np.testing.assert_array_equal(coords, before)

    def test_numeric_lists_and_readonly_noncontiguous_arrays_are_supported(self):
        coords = np.arange(48, dtype=np.float64).reshape(8, 6)[:, ::2]
        coords.setflags(write=False)
        assert biodiscovery_pose.pose_rmsd(coords, coords.tolist()) == 0.0
        assert biodiscovery_pose.aligned_pose_rmsd(coords, coords.tolist()) == pytest.approx(0.0, abs=1e-12)

    def test_direct_distance_preserves_receptor_frame_while_alignment_removes_rigid_motion(self):
        reference = np.array([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.], [0., 0., 3.]])
        translation = np.array([3., 4., 0.])
        rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        assert biodiscovery_pose.pose_rmsd(reference, reference + translation) == pytest.approx(5.)
        moved = reference @ rotation.T + translation
        assert biodiscovery_pose.aligned_pose_rmsd(reference, moved) == pytest.approx(0., abs=1e-12)
        assert biodiscovery_pose.pose_rmsd(reference, moved) > 1.

    def test_alignment_does_not_treat_reflection_as_proper_rotation(self):
        reference = np.array([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.], [0., 0., 3.]])
        reflected = reference * [-1., 1., 1.]
        assert biodiscovery_pose.aligned_pose_rmsd(reference, reflected) > 0.1

    def test_symmetry_mapping_preserves_full_atom_bijection(self):
        reference = np.array([[0., 0., 0.], [2., 0., 0.]])
        candidate = reference[::-1].copy()
        mapped, distance, mapping = biodiscovery_pose.best_symmetry_mapped_pose(
            reference, candidate, [(1, 0)],
        )
        assert distance == 0.0 and mapping == (1, 0)
        np.testing.assert_array_equal(mapped, reference)
        assert biodiscovery_pose.pose_rmsd(reference, candidate) == 2.0
        with pytest.raises(ValueError, match="bijection"):
            biodiscovery_pose.symmetry_aware_pose_rmsd(reference, candidate, [(0, 0)])

    def test_float64_conversion_overflow_is_a_value_error_without_a_warning(self):
        if np.finfo(np.longdouble).max <= np.finfo(np.float64).max:
            pytest.skip("longdouble has no additional exponent range")
        coords = np.full((2, 3), np.finfo(np.longdouble).max, dtype=np.longdouble)
        with pytest.raises(ValueError, match="non-finite"):
            biodiscovery_pose.pose_rmsd(np.zeros((2, 3)), coords)


class TestRMSDConsumerBoundaries:
    @pytest.mark.parametrize("coords", [
        np.full((1, 2, 3), 1j), np.full((1, 2, 3), "0"),
        np.zeros((1, 2, 3), dtype=bool), np.zeros((1, 2, 3), dtype=object),
        np.ma.array(np.zeros((1, 2, 3)), mask=True),
        np.ma.array(np.zeros((1, 2, 3)), mask=False),
    ])
    @pytest.mark.parametrize("consumer", ["diversity", "search"])
    def test_ensemble_cast_cannot_erase_invalid_representation(self, monkeypatch, coords, consumer):
        def must_not_score(*args, **kwargs):
            pytest.fail("invalid ensemble reached scoring")

        monkeypatch.setattr(biodiscovery_pose, "coarse_pose_score", must_not_score)
        with pytest.raises(ValueError, match="real numeric|masked coordinates"):
            if consumer == "diversity":
                biodiscovery_pose.conformer_diversity_diagnostics(coords)
            else:
                biodiscovery_pose.pose_search_candidates(
                    coords, np.zeros(3), np.zeros((1, 3)), seed=1, max_candidates=1,
                )

    def test_search_rejects_float32_overflow_before_scoring(self, monkeypatch):
        def must_not_score(*args, **kwargs):
            pytest.fail("unrepresentable ensemble reached scoring")

        monkeypatch.setattr(biodiscovery_pose, "coarse_pose_score", must_not_score)
        with pytest.raises(ValueError, match="non-finite"):
            biodiscovery_pose.pose_search_candidates(
                np.full((1, 2, 3), 1e39), np.zeros(3), np.zeros((1, 3)),
                seed=1, max_candidates=1,
            )

    @pytest.mark.parametrize("coords", [
        np.zeros((0, 3)), np.zeros((2, 2)), np.full((2, 3), np.nan),
        np.full((2, 3), 1j), np.full((2, 3), "0"),
        np.zeros((2, 3), dtype=bool), np.ma.array(np.zeros((2, 3)), mask=True),
    ])
    def test_singleton_cluster_must_validate_its_only_pose(self, coords):
        row = {"pose_index": 0, "composite_score": 0.0}
        before = row.copy()
        with pytest.raises(ValueError):
            biodiscovery_pose.cluster_poses_by_symmetry([row], {0: coords}, [])
        assert row == before

    @pytest.mark.parametrize("bad_coords", [np.full((2, 3), np.nan), np.zeros((3, 3))])
    def test_later_bad_pose_does_not_partially_write_cluster_diagnostics(self, bad_coords):
        rows = [{"pose_index": 0, "composite_score": 0.0}, {"pose_index": 1, "composite_score": 1.0}]
        before = [row.copy() for row in rows]
        with pytest.raises(ValueError):
            biodiscovery_pose.cluster_poses_by_symmetry(rows, {0: np.zeros((2, 3)), 1: bad_coords}, [])
        assert rows == before

    @pytest.mark.parametrize("mapping", [[(0, 0)], [(0,)], [(0, True)]])
    def test_singleton_cluster_does_not_skip_atom_mapping_validation(self, mapping):
        row = {"pose_index": 0, "composite_score": 0.0}
        with pytest.raises(ValueError, match="symmetry mapping"):
            biodiscovery_pose.cluster_poses_by_symmetry([row], {0: np.zeros((2, 3))}, mapping)
        assert "pose_cluster_id" not in row

    def test_normal_singleton_and_empty_cluster_outputs_remain_supported(self):
        row = {"pose_index": 0, "composite_score": 0.0}
        result = biodiscovery_pose.cluster_poses_by_symmetry([row], {0: np.zeros((2, 3))}, [])
        assert result["cluster_count"] == 1
        assert row["symmetry_aware_pose_rmsd_to_cluster_representative_a"] == 0.0
        assert biodiscovery_pose.cluster_poses_by_symmetry([], {}, [])["cluster_count"] == 0

    def test_normal_conformer_diversity_remains_rigid_motion_invariant(self):
        pose = np.array([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.]])
        conformers = np.stack([pose, pose + [4., 5., 6.]])
        result = biodiscovery_pose.conformer_diversity_diagnostics(conformers)
        assert result["pairwise_rmsd_count"] == 1
        assert result["pairwise_rmsd_max_a"] == pytest.approx(0., abs=1e-12)
        assert result["coordinate_frame_invariant"] is True
