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
