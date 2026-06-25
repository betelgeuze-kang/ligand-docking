from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from betelgeuze_engine.biodiscovery import ligand_prep
from betelgeuze_engine.biodiscovery import manifest as biodiscovery_manifest
from betelgeuze_engine.biodiscovery import pose as biodiscovery_pose
from betelgeuze_engine.biodiscovery import protein_prep
from betelgeuze_engine.biodiscovery import scoring as biodiscovery_scoring
from betelgeuze_engine.biodiscovery.screening import (
    TierBetaScreening,
    TierBetaScreeningResult,
    _LOCAL_MANIFEST_KEY,
    _SCHEMA_VERSION,
    _aa3_to_aa1,
    _atom_count_from_smiles,
    _parse_pdb_text,
    _resolve_ligand_input,
    _resolve_pocket_indices,
    _run_stability_simulation,
    _single_pose_score,
    _validate_ligand,
    _validate_protein,
)

MINI_PDB = """
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.009   1.421   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.225   2.374   0.000  1.00  0.00           O
ATOM      5  CB  ALA A   1       1.986  -0.754   1.212  1.00  0.00           C
ATOM      6  N   GLY A   2       3.304   1.560   0.000  1.00  0.00           N
ATOM      7  CA  GLY A   2       3.988   2.847   0.000  1.00  0.00           C
ATOM      8  C   GLY A   2       5.498   2.674   0.000  1.00  0.00           C
ATOM      9  O   GLY A   2       6.070   1.579   0.000  1.00  0.00           O
ATOM     10  N   SER A   3       6.162   3.833   0.000  1.00  0.00           N
ATOM     11  CA  SER A   3       7.615   3.822   0.000  1.00  0.00           C
ATOM     12  C   SER A   3       8.214   5.220   0.000  1.00  0.00           C
ATOM     13  O   SER A   3       7.466   6.203   0.000  1.00  0.00           O
ATOM     14  CB  SER A   3       8.131   3.059  -1.213  1.00  0.00           C
ATOM     15  OG  SER A   3       7.730   1.699  -1.162  1.00  0.00           O
ATOM     16  N   LEU A   4       9.535   5.259   0.000  1.00  0.00           N
ATOM     17  CA  LEU A   4      10.330   6.481   0.000  1.00  0.00           C
ATOM     18  C   LEU A   4      11.779   6.021   0.000  1.00  0.00           C
ATOM     19  O   LEU A   4      12.049   4.817   0.000  1.00  0.00           O
ATOM     20  CB  LEU A   4      10.036   7.300   1.254  1.00  0.00           C
ATOM     21  CG  LEU A   4       8.578   7.729   1.400  1.00  0.00           C
ATOM     22  CD1 LEU A   4       8.435   8.548   2.675  1.00  0.00           C
ATOM     23  CD2 LEU A   4       8.050   8.500   0.199  1.00  0.00           C
ATOM     24  N   VAL A   5      12.715   6.974   0.000  1.00  0.00           N
ATOM     25  CA  VAL A   5      14.150   6.697   0.000  1.00  0.00           C
ATOM     26  C   VAL A   5      14.802   8.074   0.000  1.00  0.00           C
ATOM     27  O   VAL A   5      14.217   9.159   0.000  1.00  0.00           O
ATOM     28  CB  VAL A   5      14.619   5.884   1.208  1.00  0.00           C
ATOM     29  CG1 VAL A   5      16.122   5.646   1.141  1.00  0.00           C
ATOM     30  CG2 VAL A   5      13.893   4.543   1.248  1.00  0.00           C
ATOM     31  N   PHE A   6      16.133   8.073   0.000  1.00  0.00           N
ATOM     32  CA  PHE A   6      16.871   9.331   0.000  1.00  0.00           C
ATOM     33  C   PHE A   6      18.363   9.018   0.000  1.00  0.00           C
ATOM     34  O   PHE A   6      18.771   7.853   0.000  1.00  0.00           O
ATOM     35  CB  PHE A   6      16.496  10.144   1.240  1.00  0.00           C
ATOM     36  CG  PHE A   6      15.042  10.543   1.308  1.00  0.00           C
ATOM     37  CD1 PHE A   6      14.592  11.781   0.847  1.00  0.00           C
ATOM     38  CD2 PHE A   6      14.121   9.666   1.888  1.00  0.00           C
ATOM     39  CE1 PHE A   6      13.247  12.136   0.965  1.00  0.00           C
ATOM     40  CE2 PHE A   6      12.775  10.014   2.009  1.00  0.00           C
ATOM     41  CZ  PHE A   6      12.338  11.250   1.547  1.00  0.00           C
ATOM     42  N   GLN A   7      19.214  10.042   0.000  1.00  0.00           N
ATOM     43  CA  GLN A   7      20.658   9.831   0.000  1.00  0.00           C
ATOM     44  C   GLN A   7      21.263  11.229   0.000  1.00  0.00           C
ATOM     45  O   GLN A   7      20.570  12.252   0.000  1.00  0.00           O
ATOM     46  CB  GLN A   7      21.149   9.021  -1.202  1.00  0.00           C
ATOM     47  CG  GLN A   7      20.704   7.564  -1.159  1.00  0.00           C
ATOM     48  CD  GLN A   7      21.218   6.730  -2.329  1.00  0.00           C
ATOM     49  OE1 GLN A   7      22.099   7.168  -3.080  1.00  0.00           O
ATOM     50  NE2 GLN A   7      20.653   5.526  -2.472  1.00  0.00           N
ATOM     51  N   TRP A   8      22.588  11.229   0.000  1.00  0.00           N
ATOM     52  CA  TRP A   8      23.374  12.461   0.000  1.00  0.00           C
ATOM     53  C   TRP A   8      24.859  12.104   0.000  1.00  0.00           C
ATOM     54  O   TRP A   8      25.283  10.942   0.000  1.00  0.00           O
ATOM     55  CB  TRP A   8      23.020  13.282   1.236  1.00  0.00           C
ATOM     56  CG  TRP A   8      21.584  13.687   1.304  1.00  0.00           C
ATOM     57  CD1 TRP A   8      20.924  14.433   0.371  1.00  0.00           C
ATOM     58  CD2 TRP A   8      20.655  13.310   2.330  1.00  0.00           C
ATOM     59  NE1 TRP A   8      19.574  14.544   0.674  1.00  0.00           N
ATOM     60  CE2 TRP A   8      19.390  13.879   1.905  1.00  0.00           C
ATOM     61  CE3 TRP A   8      20.777  12.512   3.471  1.00  0.00           C
ATOM     62  CZ2 TRP A   8      18.252  13.673   2.671  1.00  0.00           C
ATOM     63  CZ3 TRP A   8      19.643  12.303   4.244  1.00  0.00           C
ATOM     64  CH2 TRP A   8      18.399  12.884   3.836  1.00  0.00           C
ATOM     65  N   HIS A   9      25.703  13.128   0.000  1.00  0.00           N
ATOM     66  CA  HIS A   9      27.145  12.918   0.000  1.00  0.00           C
ATOM     67  C   HIS A   9      28.030  14.030   0.000  1.00  0.00           C
ATOM     68  O   HIS A   9      27.530  15.160   0.000  1.00  0.00           O
ATOM     69  CB  HIS A   9      27.600  11.900   1.030  1.00  0.00           C
ATOM     70  N   THR A  10      29.340  13.830   0.000  1.00  0.00           N
ATOM     71  CA  THR A  10      30.200  14.900   0.000  1.00  0.00           C
ATOM     72  C   THR A  10      31.580  14.500   0.000  1.00  0.00           C
ATOM     73  O   THR A  10      31.850  13.300   0.000  1.00  0.00           O
ATOM     74  CB  THR A  10      29.950  15.750   1.250  1.00  0.00           C
"""

VALID_SMILES = "c1ccccc1"
CHIRAL_SMILES = "C[C@H](O)C(=O)O"
INVALID_SMILES = "XxYyZz"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"


class TestHelperFunctions:
    def test_aa3_to_aa1_standard(self):
        assert _aa3_to_aa1("ALA") == "A"
        assert _aa3_to_aa1("GLY") == "G"
        assert _aa3_to_aa1("SER") == "S"
        assert _aa3_to_aa1("  his  ") == "H"

    def test_aa3_to_aa1_unknown(self):
        assert _aa3_to_aa1("XYZ") == "X"

    def test_parse_pdb_text_returns_coords_and_sequence(self):
        coords, seq = _parse_pdb_text(MINI_PDB)
        assert coords.shape[0] >= 9
        assert coords.shape[1] == 3
        assert "A" in seq

    def test_parse_mmcif_atom_site_loop_returns_coords_and_sequence(self):
        coords, seq = _parse_pdb_text((FIXTURE_DIR / "mini_protein.cif").read_text(encoding="utf-8"))
        assert coords.shape == (10, 3)
        assert seq == "AGSLVFQWHT"

    def test_parse_pdb_text_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_pdb_text("")

    def test_screening_uses_canonical_protein_preparation_helpers(self):
        assert _aa3_to_aa1 is protein_prep.aa3_to_aa1
        assert _parse_pdb_text is protein_prep.parse_pdb_text
        assert _validate_protein is protein_prep.validate_protein
        coords, seq = protein_prep.resolve_protein_input(MINI_PDB)
        validation = protein_prep.validate_protein(coords, seq)
        assert seq == "AGSLVFQWHT"
        assert validation["valid"] is True
        assert validation["fidelity"] == "sequence_mapped"

    def test_validate_ligand_valid(self):
        result = _validate_ligand(VALID_SMILES)
        assert result["valid"] is True
        assert result["blocked"] is False

    def test_validate_ligand_empty(self):
        result = _validate_ligand("")
        assert result["valid"] is False
        assert "empty_smiles" in result["blockers"]

    def test_validate_ligand_invalid(self):
        result = _validate_ligand(INVALID_SMILES)
        assert result["valid"] is False
        if result["valid"] is False:
            assert result["blocked"] is True

    def test_validate_ligand_chiral_unassigned(self):
        result = _validate_ligand(CHIRAL_SMILES)
        if result["unassigned_chiral_center_count"] > 0:
            assert "unassigned_ligand_chirality" in result["blockers"]

    def test_screening_uses_canonical_ligand_preparation_helpers(self):
        assert _validate_ligand is ligand_prep.validate_ligand
        assert _resolve_ligand_input is ligand_prep.resolve_ligand_input
        resolved = ligand_prep.resolve_ligand_input(VALID_SMILES)
        result = ligand_prep.validate_ligand(resolved.smiles, resolved)
        topology = ligand_prep.ligand_topology_payload(result)
        assert resolved.source_kind == "smiles_text"
        assert topology["atom_elements"] == ["C", "C", "C", "C", "C", "C"]
        assert topology["bond_count"] == 6
        assert topology["input_provenance"]["format"] == "smiles"

    def test_validate_protein_valid(self):
        coords = np.zeros((20, 3), dtype=np.float32)
        result = _validate_protein(coords, "AGSLV")
        assert result["valid"] is True
        assert not result["blocked"]

    def test_validate_protein_empty(self):
        coords = np.zeros((0, 3), dtype=np.float32)
        result = _validate_protein(coords, "")
        assert result["valid"] is False

    def test_validate_protein_too_few(self):
        coords = np.zeros((5, 3), dtype=np.float32)
        result = _validate_protein(coords, "")
        assert result["valid"] is False

    def test_validate_protein_too_many(self):
        coords = np.zeros((6000, 3), dtype=np.float32)
        result = _validate_protein(coords, "")
        assert result["valid"] is False

    def test_resolve_pocket_indices_with_center(self):
        coords = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]], dtype=np.float32)
        center = np.array([0.0, 0.0, 0.0])
        indices = _resolve_pocket_indices(coords, center, cutoff_a=6.0)
        assert 0 in indices
        assert 1 in indices
        assert 2 not in indices

    def test_resolve_pocket_indices_no_center(self):
        coords = np.zeros((10, 3), dtype=np.float32)
        indices = _resolve_pocket_indices(coords, None, cutoff_a=8.0)
        assert len(indices) == 10

    def test_screening_uses_canonical_pose_domain_helpers(self):
        assert _resolve_pocket_indices is biodiscovery_pose.resolve_pocket_indices
        protein_ca = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]], dtype=np.float32)
        ligand = np.array([[0.2, 0.0, 0.0], [10.0, 0.0, 0.0]], dtype=np.float32)
        protein_beads = biodiscovery_pose.virtual_protein_coords(protein_ca)
        assert protein_beads.shape == (8, 3)
        assert biodiscovery_pose.clash_count(protein_beads, ligand) >= 1
        assert biodiscovery_pose.pose_rmsd(ligand, ligand) == 0.0

    def test_conformer_diversity_diagnostics_measure_rotatable_heavy_atom_rmsd(self):
        conformers = np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0], [4.5, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.8, 0.0], [4.5, 1.2, 0.0]],
                [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, -0.8, 0.0], [4.5, -1.2, 0.0]],
            ],
            dtype=np.float32,
        )

        diagnostics = biodiscovery_pose.conformer_diversity_diagnostics(conformers, smiles="CCCC")

        assert diagnostics["schema_version"] == "tier_beta_conformer_diversity_v1"
        assert diagnostics["status"] == "rotatable_conformer_diversity_measured"
        assert diagnostics["method"] == "atom_order_pairwise_heavy_atom_rmsd"
        assert diagnostics["rotatable_bond_count"] >= 1
        assert diagnostics["conformer_count"] == 3
        assert diagnostics["pairwise_rmsd_count"] == 3
        assert diagnostics["pairwise_rmsd_max_a"] >= 0.5
        assert diagnostics["diverse_pair_count"] >= 1

    def test_so3_rotation_sampling_is_deterministic_orthonormal_and_nontrivial(self):
        rotations = biodiscovery_pose.so3_rotation_matrices(5, seed=23)
        replay = biodiscovery_pose.so3_rotation_matrices(5, seed=23)
        diagnostics = biodiscovery_pose.rotation_sampling_diagnostics(rotations)

        assert len(rotations) == 5
        assert np.allclose(rotations[0], np.eye(3))
        assert all(np.allclose(left, right) for left, right in zip(rotations, replay))
        assert diagnostics["schema_version"] == "tier_beta_so3_rotation_sampling_v1"
        assert diagnostics["method"] == "deterministic_uniform_quaternion_so3_identity_first"
        assert diagnostics["sample_count"] == 5
        assert diagnostics["identity_first"] is True
        assert diagnostics["non_identity_sample_count"] == 4
        assert diagnostics["determinant_min"] == pytest.approx(1.0, abs=1e-10)
        assert diagnostics["determinant_max"] == pytest.approx(1.0, abs=1e-10)
        assert diagnostics["orthogonality_error_max"] < 1e-12

    def test_local_rigid_body_minimizer_uses_rotation_and_preserves_internal_distances(self):
        ligand = np.asarray([[-2.0, 0.2, 0.0], [2.0, -0.2, 0.0]], dtype=np.float32)
        protein_beads = np.asarray([[0.0, 2.0, 0.0], [0.0, -2.0, 0.0]], dtype=np.float32)
        initial_distance = float(np.linalg.norm(ligand[0] - ligand[1]))
        initial_score = biodiscovery_pose.coarse_pose_score(protein_beads, ligand)["score"]

        minimized, diagnostics = biodiscovery_pose.local_rigid_body_minimize_pose(
            protein_beads,
            ligand,
            max_steps=8,
            initial_step_a=0.05,
            initial_rotation_step_rad=0.2,
        )

        assert diagnostics["status"] == "finite_difference_rigid_body_gradient_minimized"
        assert diagnostics["method"] == "finite_difference_gradient_descent_translation_rotation"
        assert diagnostics["degrees_of_freedom"] == ["translation", "rotation"]
        assert diagnostics["gradient_parameter_count"] == 6
        assert diagnostics["final_coarse_score"] < initial_score
        assert diagnostics["final_coarse_score"] == pytest.approx(
            biodiscovery_pose.coarse_pose_score(protein_beads, minimized)["score"]
        )
        assert np.linalg.norm(np.asarray(diagnostics["rotation_delta_rad"], dtype=np.float64)) > 0.1
        assert np.linalg.norm(np.asarray(diagnostics["translation_delta_a"], dtype=np.float64)) < 1e-3
        assert float(np.linalg.norm(minimized[0] - minimized[1])) == pytest.approx(initial_distance)

    def test_local_rigid_body_minimizer_reports_no_improvement_when_no_steps_are_allowed(self):
        ligand = np.asarray([[-2.0, 0.2, 0.0], [2.0, -0.2, 0.0]], dtype=np.float32)
        protein_beads = np.asarray([[0.0, 2.0, 0.0], [0.0, -2.0, 0.0]], dtype=np.float32)
        initial_score = biodiscovery_pose.coarse_pose_score(protein_beads, ligand)["score"]

        minimized, diagnostics = biodiscovery_pose.local_rigid_body_minimize_pose(
            protein_beads,
            ligand,
            max_steps=0,
        )

        assert diagnostics["status"] == "finite_difference_rigid_body_gradient_no_improvement"
        assert diagnostics["steps_taken"] == 0
        assert diagnostics["final_coarse_score"] == pytest.approx(initial_score)
        assert diagnostics["improved"] is False
        assert diagnostics["translation_delta_a"] == [0.0, 0.0, 0.0]
        assert diagnostics["rotation_delta_rad"] == [0.0, 0.0, 0.0]
        assert np.allclose(minimized, ligand)

    def test_pose_search_candidates_use_so3_translation_grid_and_clash_beam(self):
        conformers = np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            ],
            dtype=np.float32,
        )
        protein_beads = np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32)
        candidates, diagnostics = biodiscovery_pose.pose_search_candidates(
            conformers,
            np.asarray([4.0, 0.0, 0.0], dtype=np.float32),
            protein_beads,
            seed=11,
            max_candidates=5,
            ligand_smiles="CCCC",
            rotations_per_conformer=4,
            translation_spacing_a=1.5,
        )

        assert diagnostics["search_strategy"] == "etkdg_conformer_so3_translation_grid_coarse_score_local_min_beam_v1"
        assert diagnostics["conformer_count"] == 2
        assert diagnostics["conformer_diversity"]["schema_version"] == "tier_beta_conformer_diversity_v1"
        assert diagnostics["conformer_diversity"]["pairwise_rmsd_count"] == 1
        assert diagnostics["conformer_diversity"]["pairwise_rmsd_max_a"] == pytest.approx(1.0)
        assert diagnostics["rotatable_bond_count"] == biodiscovery_pose.rotatable_bond_count("CCCC")
        assert diagnostics["retained_conformer_count"] == len(
            {candidate["conformer_index"] for candidate in candidates}
        )
        assert diagnostics["retained_conformer_fraction"] == pytest.approx(
            diagnostics["retained_conformer_count"] / diagnostics["conformer_count"]
        )
        assert diagnostics["rotations_per_conformer"] == 4
        assert diagnostics["rotation_sampling"]["schema_version"] == "tier_beta_so3_rotation_sampling_v1"
        assert diagnostics["rotation_sampling"]["sample_count"] == 4
        assert diagnostics["rotation_sampling"]["non_identity_sample_count"] == 3
        assert diagnostics["rotation_sampling"]["orthogonality_error_max"] < 1e-12
        assert diagnostics["translation_grid_point_count"] >= 7
        assert diagnostics["translation_grid"]["schema_version"] == "tier_beta_pocket_translation_grid_v1"
        assert diagnostics["translation_grid"]["status"].startswith("protein_bead_envelope_grid")
        assert diagnostics["translation_grid"]["envelope_source"] == "search_envelope_beads"
        assert diagnostics["translation_grid"]["inside_envelope_count"] == diagnostics["translation_grid_point_count"]
        assert diagnostics["raw_candidate_count"] == (
            diagnostics["conformer_count"]
            * diagnostics["rotations_per_conformer"]
            * diagnostics["translation_grid_point_count"]
        )
        assert diagnostics["coarse_beam_candidate_count"] >= diagnostics["retained_candidate_count"]
        assert diagnostics["retained_candidate_count"] == 5
        assert diagnostics["coarse_score_beam_status"] == "pass"
        assert diagnostics["local_minimization_status"].startswith("finite_difference_rigid_body_gradient_")
        assert diagnostics["local_minimization_method"] == "finite_difference_gradient_descent_translation_rotation"
        assert diagnostics["local_minimization_degrees_of_freedom"] == ["translation", "rotation"]
        assert diagnostics["local_minimization_candidate_count"] == 10
        assert len(candidates) == 5
        assert all(candidate["coords"].shape == (2, 3) for candidate in candidates)
        assert [candidate["clash_count"] for candidate in candidates] == sorted(
            candidate["clash_count"] for candidate in candidates
        )
        assert all(
            candidate["coarse_score"] <= candidate["coarse_score_before_local"] + 1e-8
            for candidate in candidates
        )
        assert all("local_minimization" in candidate for candidate in candidates)
        assert all(candidate["local_minimization"]["gradient_parameter_count"] == 6 for candidate in candidates)
        assert all(
            candidate["local_minimization"]["degrees_of_freedom"] == ["translation", "rotation"]
            for candidate in candidates
        )
        assert all(len(candidate["local_minimization"]["rotation_delta_rad"]) == 3 for candidate in candidates)
        again, again_diag = biodiscovery_pose.pose_search_candidates(
            conformers,
            np.asarray([4.0, 0.0, 0.0], dtype=np.float32),
            protein_beads,
            seed=11,
            max_candidates=5,
            ligand_smiles="CCCC",
            rotations_per_conformer=4,
            translation_spacing_a=1.5,
        )
        assert diagnostics == again_diag
        assert [candidate["translation_vector_a"] for candidate in candidates] == [
            candidate["translation_vector_a"] for candidate in again
        ]
        assert [candidate["coarse_score"] for candidate in candidates] == [
            candidate["coarse_score"] for candidate in again
        ]
        assert np.allclose(candidates[0]["coords"], again[0]["coords"])

    def test_rotatable_conformer_diversity_reports_claim_blocker_when_low(self):
        low_diversity = np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.1, 0.0, 0.0], [1.1, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )

        diagnostics = biodiscovery_pose.conformer_diversity_diagnostics(
            low_diversity,
            smiles="CCCC",
            diversity_threshold_a=0.5,
        )

        assert diagnostics["status"] == "low_conformer_diversity_measured"
        assert diagnostics["rotatable_bond_count"] > 0
        assert diagnostics["claim_safe"] is False
        assert "rotatable_conformer_diversity_not_demonstrated" in diagnostics["claim_safe_blockers"]

    def test_pocket_translation_grid_uses_protein_bead_envelope(self):
        protein_beads = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.5, 0.0, 0.0],
                [0.0, 1.5, 0.0],
                [0.0, 0.0, 1.5],
                [-1.5, 0.0, 0.0],
                [0.0, -1.5, 0.0],
                [0.0, 0.0, -1.5],
            ],
            dtype=np.float32,
        )

        translations, diagnostics = biodiscovery_pose.pocket_translation_grid_for_beads(
            protein_beads,
            np.asarray([0.0, 0.0, 0.0], dtype=np.float32),
            spacing_a=1.5,
            envelope_radius_a=3.0,
            max_points=27,
        )

        assert diagnostics["schema_version"] == "tier_beta_pocket_translation_grid_v1"
        assert diagnostics["status"] == "protein_bead_envelope_grid"
        assert diagnostics["method"] == "protein_bead_envelope_lattice"
        assert diagnostics["envelope_source"] == "search_envelope_beads"
        assert diagnostics["grid_point_count"] == len(translations)
        assert diagnostics["inside_envelope_count"] == len(translations)
        assert len(translations) > len(biodiscovery_pose.pocket_translation_grid(1.5))
        assert all(np.linalg.norm(offset) <= diagnostics["envelope_radius_a"] + 1e-8 for offset in translations)

        again, again_diagnostics = biodiscovery_pose.pocket_translation_grid_for_beads(
            protein_beads,
            np.asarray([0.0, 0.0, 0.0], dtype=np.float32),
            spacing_a=1.5,
            envelope_radius_a=3.0,
            max_points=27,
        )
        assert diagnostics == again_diagnostics
        assert [offset.tolist() for offset in translations] == [offset.tolist() for offset in again]

    def test_pocket_translation_grid_falls_back_to_axial_grid_without_beads(self):
        translations, diagnostics = biodiscovery_pose.pocket_translation_grid_for_beads(
            np.zeros((0, 3), dtype=np.float32),
            np.asarray([0.0, 0.0, 0.0], dtype=np.float32),
            spacing_a=1.5,
        )

        assert diagnostics["status"] == "fallback_center_axial_grid_no_protein_beads"
        assert diagnostics["method"] == "center_plus_axial_offsets"
        assert diagnostics["envelope_source"] == "fallback_no_beads"
        assert diagnostics["fallback_used"] is True
        assert len(translations) == 7
        assert [offset.tolist() for offset in translations] == [
            offset.tolist() for offset in biodiscovery_pose.pocket_translation_grid(1.5)
        ]

    def test_pose_search_clash_prefilter_excludes_clashing_candidates_when_clean_beam_exists(self):
        conformers = np.asarray(
            [
                [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )
        protein_beads = np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32)

        candidates, diagnostics = biodiscovery_pose.pose_search_candidates(
            conformers,
            np.asarray([0.0, 0.0, 0.0], dtype=np.float32),
            protein_beads,
            seed=11,
            max_candidates=2,
            ligand_smiles="CC",
            rotations_per_conformer=1,
            translation_spacing_a=2.0,
        )

        assert diagnostics["raw_candidate_count"] == diagnostics["translation_grid_point_count"]
        assert diagnostics["translation_grid_point_count"] >= 7
        assert diagnostics["clash_free_candidate_count"] >= 2
        assert diagnostics["clash_prefilter_status"] == "excluded_clashing_candidates"
        assert diagnostics["clash_prefiltered_candidate_count"] == diagnostics["clash_free_candidate_count"]
        assert diagnostics["clashing_candidate_excluded_count"] > 0
        assert diagnostics["coarse_beam_candidate_count"] == min(
            diagnostics["clash_free_candidate_count"],
            diagnostics["beam_size"] * 2,
        )
        assert candidates
        assert all(candidate["clash_count"] == 0 for candidate in candidates)

    def test_symmetry_aware_rmsd_clusters_atom_automorphisms(self):
        mappings = biodiscovery_pose.ligand_symmetry_mappings("CC")
        assert (1, 0) in mappings
        pose_a = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
        pose_b = np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float32)

        assert biodiscovery_pose.pose_rmsd(pose_a, pose_b) > 0.0
        assert biodiscovery_pose.symmetry_aware_pose_rmsd(pose_a, pose_b, mappings) == 0.0

        rows = [
            {"pose_index": 0, "composite_score": 0.0},
            {"pose_index": 1, "composite_score": 1.0},
        ]
        summary = biodiscovery_pose.cluster_poses_by_symmetry(
            rows,
            {0: pose_a, 1: pose_b},
            mappings,
            threshold_a=0.1,
        )
        assert summary["status"] == "symmetry_aware_rmsd_clustered"
        assert summary["method"] == "rdkit_automorphism_min_rmsd"
        assert summary["cluster_count"] == 1
        assert rows[0]["pose_cluster_id"] == rows[1]["pose_cluster_id"]
        assert rows[1]["symmetry_aware_pose_rmsd_to_cluster_representative_a"] == 0.0

    def test_chemical_anchor_mapping_uses_feature_charge_ring_graph_atoms(self):
        mapping = biodiscovery_pose.chemical_anchor_mapping("CC(=O)N", {"atom_count": 4})

        assert mapping["schema_version"] == "tier_beta_ligand_anchor_mapping_v1"
        assert mapping["status"] == "rdkit_feature_charge_ring_graph_anchor_mapping"
        assert mapping["method"] == "rdkit_feature_charge_ring_graph"
        assert len(mapping["two_bead_anchor_atom_indices"]) == 2
        assert len(mapping["four_bead_anchor_atom_indices"]) == 4
        rows_by_element = {}
        for row in mapping["anchor_rows"]:
            rows_by_element.setdefault(row["element"], []).append(row)
        assert any("acceptor" in row["roles"] for row in rows_by_element["O"])
        assert any("donor" in row["roles"] for row in rows_by_element["N"])
        assert mapping["graph_distance_source"] == "rdkit_topological_distance_matrix"

    def test_chemical_anchor_bead_mapping_projects_selected_atoms_to_pose_coordinates(self):
        mapping = biodiscovery_pose.chemical_anchor_mapping("CC(=O)N", {"atom_count": 4})
        coords = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.5, 0.0, 0.0],
                [2.5, 0.8, 0.0],
                [2.5, -0.8, 0.0],
            ],
            dtype=np.float32,
        )

        bead_mapping = biodiscovery_pose.chemical_anchor_bead_coordinates(coords, mapping)

        assert bead_mapping["schema_version"] == "tier_beta_ligand_anchor_bead_mapping_v1"
        assert bead_mapping["status"] == "chemical_anchor_bead_coordinates_ready"
        assert bead_mapping["method"] == "rdkit_feature_charge_ring_graph_anchor_atom_coordinates"
        assert bead_mapping["claim_safe"] is True
        assert bead_mapping["two_bead_count"] == 2
        assert bead_mapping["four_bead_count"] == 4
        assert bead_mapping["two_bead_anchor_atom_indices"] == mapping["two_bead_anchor_atom_indices"]
        assert bead_mapping["four_bead_anchor_atom_indices"] == mapping["four_bead_anchor_atom_indices"]
        for atom_idx, bead_coord in zip(
            bead_mapping["two_bead_anchor_atom_indices"],
            bead_mapping["two_bead_coords_a"],
        ):
            assert bead_coord == pytest.approx(coords[int(atom_idx)].tolist())

    def test_screening_uses_canonical_scoring_helpers(self):
        assert _single_pose_score is biodiscovery_scoring.single_pose_score
        assert _run_stability_simulation is biodiscovery_scoring.run_stability_simulation
        protein_ca = np.array([[float(i), 0.0, 0.0] for i in range(10)], dtype=np.float32)
        protein_beads = biodiscovery_pose.virtual_protein_coords(protein_ca)
        ligand = np.array([[4.0, 0.2, 0.0], [4.5, 0.2, 0.0]], dtype=np.float32)
        score, diagnostics = biodiscovery_scoring.single_pose_score(protein_beads, ligand, device="cpu")
        assert math.isfinite(score)
        assert diagnostics["neighbor_diagnostics"]["nxn_allocation_observed"] is False
        drift, stability = biodiscovery_scoring.run_stability_simulation(
            protein_beads,
            ligand,
            steps=1,
            seed=3,
        )
        assert math.isfinite(drift)
        assert stability["steps_run"] == 1
        assert stability["restart_reproducible"] is True

    def test_screening_uses_canonical_manifest_signing_contract(self):
        assert _LOCAL_MANIFEST_KEY == biodiscovery_manifest.LOCAL_MANIFEST_KEY
        result = TierBetaScreening(device="cpu", pose_count=2, top_k=1, stability_steps=0).screen(
            protein_input=MINI_PDB,
            ligand_input=VALID_SMILES,
        )
        assert result.ok is True
        assert result.result_manifest["signature_key_id"] == "local-tier-beta"
        assert result.result_manifest["claim_metadata"]["claim_safe"] is False
        assert result.result_manifest["claim_boundary"] == biodiscovery_manifest.CLAIM_BOUNDARY
        assert result.result_manifest["blocked_claims"] == biodiscovery_manifest.BLOCKED_CLAIMS

    def test_atom_count_from_smiles_benzene(self):
        count = _atom_count_from_smiles("c1ccccc1")
        assert count == 6


class TestTierBetaScreeningFailClosed:
    def test_empty_protein_fails(self):
        svc = TierBetaScreening()
        result = svc.screen(protein_input="", ligand_input=VALID_SMILES)
        assert result.ok is False
        assert "empty_protein_input" in result.blocked_reason

    def test_empty_ligand_fails(self):
        svc = TierBetaScreening()
        result = svc.screen(protein_input=MINI_PDB, ligand_input="")
        assert result.ok is False
        assert "empty" in result.blocked_reason.lower()

    def test_invalid_ligand_fails(self):
        svc = TierBetaScreening()
        result = svc.screen(protein_input=MINI_PDB, ligand_input=INVALID_SMILES)
        assert result.ok is False

    def test_protein_text_without_atoms_fails(self):
        svc = TierBetaScreening()
        result = svc.screen(protein_input="JUST SOME TEXT\nNO ATOM RECORDS\n", ligand_input=VALID_SMILES)
        assert result.ok is False


class TestTierBetaScreeningSuccess:
    def test_benzene_on_mini_pdb_disabled_stability(self):
        svc = TierBetaScreening(
            device="cpu",
            pose_count=8,
            top_k=3,
            stability_steps=0,
        )
        result = svc.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
        assert isinstance(result, TierBetaScreeningResult)
        assert result.schema_version == _SCHEMA_VERSION
        assert result.protein_residue_count >= 9
        assert result.ligand_smiles == VALID_SMILES
        assert result.ligand_valid is True
        assert result.pocket_residue_count > 0
        assert result.poses_generated > 0
        assert result.poses_scored > 0
        assert result.top_k == 3
        assert len(result.pose_scores) <= result.top_k
        assert result.best_score != float("inf")
        assert result.manifest_hash != ""
        assert "ligand_valid" in result.diagnostics
        assert "protein_valid" in result.diagnostics
        assert result.stability_steps_run == 0
        assert len(result.claim_metadata) > 0
        aggregation = result.diagnostics["pose_search_aggregation"]
        assert aggregation["rotation_sampling"]["schema_version"] == "tier_beta_so3_rotation_sampling_v1"
        assert aggregation["rotation_sampling"]["non_identity_sample_count"] >= 1
        assert aggregation["local_minimization_status"].startswith("finite_difference_rigid_body_gradient_")
        assert aggregation["local_minimization_method"] == "finite_difference_gradient_descent_translation_rotation"
        assert aggregation["local_minimization_degrees_of_freedom"] == ["translation", "rotation"]
        assert aggregation["local_minimization_candidate_count"] >= result.poses_scored
        assert aggregation["local_minimization_improved_count"] >= 0
        assert aggregation["symmetry_rmsd_clustering_status"] == "symmetry_aware_rmsd_clustered"
        assert aggregation["chemical_anchor_mapping_status"] == "rdkit_feature_charge_ring_graph_anchor_mapping"
        assert all(
            row["pose_search"]["rotation_sampling"]["schema_version"] == "tier_beta_so3_rotation_sampling_v1"
            for row in result.pose_scores
        )
        assert all(
            row["pose_search"]["symmetry_rmsd_clustering_status"] == "symmetry_aware_rmsd_clustered"
            for row in result.pose_scores
        )
        assert all(
            row["pose_search"]["chemical_anchor_bead_mapping_status"] == "chemical_anchor_bead_coordinates_ready"
            for row in result.pose_scores
        )
        assert all(
            row["chemical_anchor_bead_mapping"]["two_bead_count"] >= 1
            and row["chemical_anchor_bead_mapping"]["four_bead_count"] >= 1
            for row in result.pose_scores
        )

    def test_benzene_with_stability_simulation(self):
        svc = TierBetaScreening(
            device="cpu",
            pose_count=8,
            top_k=3,
            stability_steps=20,
            stability_dt=0.001,
        )
        result = svc.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
        assert result.stability_steps_run == 20
        assert "blocked_reason" in result.claim_metadata

    def test_benzene_with_custom_pocket(self):
        svc = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0)
        result = svc.screen(
            protein_input=MINI_PDB,
            ligand_input=VALID_SMILES,
            pocket_residue_indices=[0, 1, 2, 3],
        )
        assert result.pocket_residue_indices == [0, 1, 2, 3]
        assert result.pocket_residue_count == 4
        assert result.poses_scored > 0

    def test_result_contains_pose_scores_sorted(self):
        svc = TierBetaScreening(device="cpu", pose_count=8, top_k=4, stability_steps=0)
        result = svc.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
        scores = [p["composite_score"] for p in result.pose_scores]
        assert scores == sorted(scores)
        assert math.isfinite(result.best_score)

    def test_fail_result_has_empty_pose_scores(self):
        svc = TierBetaScreening()
        result = svc.screen(protein_input="", ligand_input=VALID_SMILES)
        assert result.pose_scores == []

    def test_seed_determinism(self):
        svc1 = TierBetaScreening(device="cpu", seed=42, pose_count=4, top_k=2, stability_steps=0)
        svc2 = TierBetaScreening(device="cpu", seed=42, pose_count=4, top_k=2, stability_steps=0)
        r1 = svc1.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
        r2 = svc2.screen(protein_input=MINI_PDB, ligand_input=VALID_SMILES)
        assert r1.pose_scores == r2.pose_scores
        assert r1.best_score == r2.best_score
        assert r1.poses_generated == r2.poses_generated

    def test_salt_ligand_scores_fragment_parent_state_without_counterion_pose(self):
        svc = TierBetaScreening(device="cpu", seed=7, pose_count=2, top_k=4, stability_steps=0)
        result = svc.screen(protein_input=MINI_PDB, ligand_input="CC(=O)[O-].[Na+]")
        replay = svc.screen(protein_input=MINI_PDB, ligand_input="CC(=O)[O-].[Na+]")

        assert result.ok is False
        assert "unsupported_ligand_metal_or_counterion" in result.blocked_reason
        assert "fragment_parent_projection_not_product_safe" in result.blocked_reason
        pose_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "pose_ensemble")
        ensemble = pose_stage["diagnostics"]["ligand_state_ensemble"]
        assert ensemble["status"] == "restricted_rdkit_standardized_state_ensemble_ph_range_no_pka_calibration"
        assert ensemble["state_count"] == 2
        assert ensemble["claim_safe"] is False
        assert "unsupported_ligand_metal_or_counterion" in ensemble["claim_safe_blockers"]
        skipped = next(state for state in ensemble["states"] if state["state_kind"] == "input_canonical")
        scored = next(state for state in ensemble["states"] if state["state_kind"] == "salt_parent")
        assert skipped["scoring_status"] == "not_scored_unsupported_ligand_element"
        assert skipped["unsupported_elements"] == ["Na"]
        assert scored["scoring_status"] == "pose_conformers_generated"
        assert {row["ligand_state"]["state_kind"] for row in result.pose_scores} == {"salt_parent"}
        assert all("Na" not in row["ligand_topology"]["atom_elements"] for row in result.pose_scores)
        scoring_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "scoring_ranking")
        assert scoring_stage["diagnostics"]["pose_search"]["scored_state_count"] == 1
        assert result.result_manifest["claim_metadata"]["ligand_topology"]["claim_safe"] is False
        assert "fragment_parent_projection_not_product_safe" in result.result_manifest["claim_metadata"]["ligand_topology"]["blockers"]
        assert result.typed_output["ok"] is False
        assert result.typed_output["failure_code"] == "screening_claim_not_safe"
        assert result.pose_scores == replay.pose_scores
        assert result.result_manifest["replay_hash"] == replay.result_manifest["replay_hash"]

    def test_projected_tautomer_states_remain_claim_blocked_after_scoring(self):
        svc = TierBetaScreening(device="cpu", seed=9, pose_count=4, top_k=4, stability_steps=0)
        result = svc.screen(protein_input=MINI_PDB, ligand_input="CC(=O)CC(=O)C")

        assert result.ok is False
        assert "tautomer_projection_not_product_safe" in result.blocked_reason
        pose_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "pose_ensemble")
        ensemble = pose_stage["diagnostics"]["ligand_state_ensemble"]
        assert ensemble["claim_safe"] is False
        assert "tautomer_projection_not_product_safe" in ensemble["claim_safe_blockers"]
        assert any(state["state_kind"].startswith("tautomer_") for state in ensemble["states"])
        assert any(row["ligand_state"]["state_kind"].startswith("tautomer_") for row in result.pose_scores)
        for row in result.pose_scores:
            assert row["pose_search"]["symmetry_ligand_smiles"] == row["ligand_state"]["smiles"]
        assert result.typed_output["ok"] is False

    def test_projected_ph_protomer_states_are_independently_scored_and_aggregated(self):
        svc = TierBetaScreening(device="cpu", seed=13, pose_count=4, top_k=4, stability_steps=0)
        result = svc.screen(protein_input=MINI_PDB, ligand_input="CN")

        assert result.ok is False
        assert "protonation_projection_not_product_safe" in result.blocked_reason
        assert "ph_range_protomer_heuristic_not_product_safe" in result.blocked_reason
        pose_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "pose_ensemble")
        ensemble = pose_stage["diagnostics"]["ligand_state_ensemble"]
        assert ensemble["claim_safe"] is False
        assert "ph_range_protomer_heuristic_not_product_safe" in ensemble["claim_safe_blockers"]
        assert {state["state_kind"] for state in ensemble["states"]} >= {
            "input_canonical",
            "protomer_ph_5_0_basic_amine_protonated",
        }
        scored_states = {
            state["state_kind"]: state
            for state in ensemble["states"]
            if state.get("scoring_status") == "pose_conformers_generated"
        }
        assert scored_states["input_canonical"]["poses_generated"] >= 1
        assert scored_states["protomer_ph_5_0_basic_amine_protonated"]["poses_generated"] >= 1
        assert scored_states["input_canonical"]["atom_elements"] == ["C", "N"]
        assert scored_states["protomer_ph_5_0_basic_amine_protonated"]["formal_charge_sum"] == 1
        assert scored_states["protomer_ph_5_0_basic_amine_protonated"]["formal_charges"] == [0, 1]
        assert scored_states["protomer_ph_5_0_basic_amine_protonated"]["feature_source"] == (
            "rdkit_chemical_features_base_fdef"
        )

        scoring_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "scoring_ranking")
        state_ranking = scoring_stage["diagnostics"]["state_ranking_aggregation"]
        assert state_ranking["schema_version"] == "tier_beta_ligand_state_ranking_aggregation_v1"
        assert state_ranking["status"] == "ranked_state_aggregation_complete"
        assert state_ranking == result.diagnostics["state_ranking_aggregation"]
        assert state_ranking == scoring_stage["diagnostics"]["pose_search"]["state_ranking_aggregation"]
        assert {state["state_kind"] for state in state_ranking["states"]} >= {
            "input_canonical",
            "protomer_ph_5_0_basic_amine_protonated",
        }
        assert all(state["pose_count"] >= 1 for state in state_ranking["states"])
        protomer_row = next(
            state
            for state in state_ranking["states"]
            if state["state_kind"] == "protomer_ph_5_0_basic_amine_protonated"
        )
        assert "ph_range_protomer_heuristic_not_product_safe" in protomer_row["claim_safe_blockers"]
        pose_protomer_rows = [
            row
            for row in result.pose_scores
            if row["ligand_state"]["state_kind"] == "protomer_ph_5_0_basic_amine_protonated"
        ]
        assert pose_protomer_rows
        assert all(row["ligand_state"]["formal_charge_sum"] == 1 for row in pose_protomer_rows)
        assert all(row["ligand_topology"]["formal_charges"] == [0, 1] for row in pose_protomer_rows)
        manifest_scoring_stage = next(
            stage for stage in result.result_manifest["stage_records"] if stage["stage_id"] == "scoring_ranking"
        )
        assert manifest_scoring_stage["diagnostics"]["state_ranking_aggregation"] == state_ranking
        assert result.typed_output["ok"] is False
