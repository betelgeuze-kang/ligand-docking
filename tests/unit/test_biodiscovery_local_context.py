"""Rigid geometry and local diagnostic scope, not molecular accuracy claims."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
import torch

from betelgeuze_engine.biodiscovery import local_geometry as geom, pose, scoring, screening
from tests.unit.test_biodiscovery_screening import MINI_PDB


def _rotation(seed):
    matrix, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    matrix[:, 0] *= np.linalg.det(matrix)
    return matrix


def _cloud(n=16):
    i = np.arange(n, dtype=np.float64)
    return np.column_stack((3.8 * i, np.sin(i), np.cos(i)))


def _pdb(coords):
    return "".join(
        f"ATOM  {i:5d}  CA  ALA A{i:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C\n"
        for i, (x, y, z) in enumerate(coords, 1)
    )


@pytest.mark.parametrize("seed", range(12))
def test_proxy_and_fixed_pose_score_are_rigid_transform_covariant(seed):
    protein = _cloud(12)
    ligand = np.array([[4.0, 2.0, .7], [5.0, 2.4, 1.0]])
    rng = np.random.default_rng(seed)
    rotation = _rotation(seed)
    translation = rng.uniform(-20., 20., 3)
    beads = pose.virtual_protein_coords(protein)
    moved = pose.virtual_protein_coords(protein @ rotation.T + translation)
    np.testing.assert_allclose(moved, beads @ rotation.T + translation, atol=8e-6, rtol=1e-6)
    before = pose.coarse_pose_score(beads, ligand)
    after = pose.coarse_pose_score(moved, ligand @ rotation.T + translation)
    assert after["score"] == pytest.approx(before["score"], rel=2e-5, abs=2e-4)
    assert after["clash_count"] == before["clash_count"]


def test_symmetric_distance_ties_preserve_input_index_rule():
    protein = np.array([[0., 0., 0.], [1., 0., 0.], [-1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    rotation = _rotation(99)
    expected = pose.virtual_protein_coords(protein) @ rotation.T
    np.testing.assert_allclose(pose.virtual_protein_coords(protein @ rotation.T), expected, atol=2e-6)


def test_selected_proxy_keeps_global_atom_order_and_uses_same_frame():
    protein = _cloud()
    indices = [10, 2, 7]
    full = pose.virtual_protein_coords(protein).reshape(-1, 4, 3)
    selected = pose.virtual_protein_coords(protein, residue_indices=indices).reshape(-1, 4, 3)
    np.testing.assert_array_equal(selected, full[indices])


@pytest.mark.parametrize("protein", [np.zeros((3, 3)), np.array([[0., 0., 0.], [1., 0., 0.]]),
                                     np.column_stack((np.arange(10), np.zeros((10, 2))))])
def test_degenerate_clouds_do_not_get_fabricated_global_axes(protein):
    with pytest.raises(ValueError, match="degenerate_protein_geometry"):
        pose.virtual_protein_coords(protein)


@pytest.mark.parametrize("protein", [np.empty((0, 3)), np.zeros((3, 2)), np.full((3, 3), np.nan),
                                     np.full((3, 3), 1j), np.full((3, 3), "0"),
                                     np.ma.array(_cloud(), mask=True), np.full((3, 3), 1e39)])
def test_invalid_geometry_never_becomes_proxy_atoms(protein):
    with pytest.raises(ValueError):
        pose.virtual_protein_coords(protein)


@pytest.mark.parametrize("indices", [[1.1], [True], [-1], [100], [0, 0]])
def test_bad_indices_are_not_coerced_or_silently_deduplicated(indices):
    with pytest.raises(ValueError):
        pose.virtual_protein_coords(_cloud(), residue_indices=indices)


def test_context_is_seeded_globally_and_explicitly_not_full_system_energy():
    protein = _cloud(127)
    selected, meta = geom.pocket_context(protein, list(range(10)), [np.zeros((1, 6, 3))], cutoff_a=8.)
    assert set(range(10)) <= set(selected)
    assert 10 < len(selected) < 127
    assert meta["input_residue_count"] == 127
    assert meta["context_residue_count"] + meta["excluded_residue_count"] == 127
    assert meta["context_residue_indices"] == selected
    assert meta["full_system_energy_equivalent"] is False
    assert meta["physical_boundary_validated"] is False
    assert meta["representation"] == "ca_point_cloud_frame_v2"


def test_search_neighborhood_includes_ligand_radius_and_motion_bounds():
    protein = _cloud(80)
    small, a = geom.pocket_context(protein, [5, 6, 7], [np.zeros((1, 2, 3))], cutoff_a=8.)
    large, b = geom.pocket_context(protein, [5, 6, 7], [np.array([[[-15., 0., 0.], [15., 0., 0.]]])], cutoff_a=8.)
    assert b["radius_a"] - a["radius_a"] == pytest.approx(15.)
    assert set(small) <= set(large)
    assert b["local_translation_bound_a"] == 6 * .25
    assert b["search_translation_bound_a"] == 1.5


@pytest.mark.parametrize("cutoff", [0., -1., float("inf"), float("nan")])
def test_invalid_context_cutoff_is_rejected(cutoff):
    with pytest.raises(ValueError):
        geom.pocket_context(_cloud(), [0, 1, 2], [np.zeros((1, 2, 3))], cutoff_a=cutoff)


def test_missing_conformers_cannot_create_an_underestimated_context():
    with pytest.raises(ValueError, match="missing_context_conformer"):
        geom.pocket_context(_cloud(), [0, 1, 2], [], cutoff_a=8.)


def test_real_screening_small_pocket_on_127_residue_input_no_longer_hits_global_514_cap():
    result = screening.TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=_pdb(_cloud(127)), ligand_input="c1ccccc1", pocket_residue_indices=list(range(10)),
    )
    assert result.ok is True, result.blocked_reason
    assert result.protein_residue_count == 127
    assert result.pocket_residue_indices == list(range(10))
    context = next(s for s in result.stage_records if s["stage_id"] == "protein_calculation_context")["diagnostics"]
    assert 4 * context["context_residue_count"] + 6 <= 512
    assert context["excluded_residue_count"] > 0
    assert result.pose_scores[0]["ranking_metric"]["name"] == "restricted_local_composite_score_v2_ca_geometry_context"
    assert result.diagnostics["benchmark_metric_summary"]["score_metric"] == result.pose_scores[0]["ranking_metric"]["name"]


def test_oversized_local_context_is_blocked_before_search(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("oversized local context reached expensive search")

    monkeypatch.setattr(screening, "_pose_search_candidates", forbidden)
    result = screening.TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=_pdb(_cloud(127)), ligand_input="c1ccccc1", pocket_residue_indices=list(range(127)),
    )
    assert result.ok is False
    assert "dense_diagnostic_blocked" in result.blocked_reason


@pytest.mark.parametrize("indices", [[], [0, 0], [True], [1.9], [-1], [10000]])
def test_service_rejects_invalid_explicit_pocket_without_reinterpreting_it(indices):
    result = screening.TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB, ligand_input="c1ccccc1", pocket_residue_indices=indices,
    )
    assert result.ok is False
    assert "pocket" in result.blocked_reason


def test_wrapper_passes_exact_typing_and_paired_partial_charges(monkeypatch):
    observed = {}

    def capture(**kwargs):
        observed.update(kwargs)
        return {"binding_energy_kcal_mol": -1., "is_free_energy": False}

    monkeypatch.setattr(scoring, "mm_gbsa_binding_energy", capture)
    protein = np.array([[0., 0., 0.], [2., 0., 0.], [0., 3., 0.]])
    ligand = np.array([[1., 2., 1.], [2., 3., 1.]])
    result = scoring.mm_gbsa_binding_score(
        protein, ligand, protein_elements=["C", "N", "O"], ligand_elements=["N", "O"],
        protein_charges=np.array([.2, -.1, -.1]), ligand_charges=np.array([.1, -.1]),
    )
    assert observed["protein_elements"] == ["C", "N", "O"]
    assert observed["ligand_elements"] == ["N", "O"]
    np.testing.assert_array_equal(observed["ligand_charges"], [.1, -.1])
    assert result["chemistry_input_scope"]["partial_charges_supplied"] is True
    assert result["chemistry_input_scope"]["physical_parameterization_validated"] is False


@pytest.mark.parametrize("kwargs", [dict(ligand_elements=["N"]), dict(ligand_elements=["Bad", "C"]),
                                    dict(protein_charges=np.zeros(3)),
                                    dict(protein_charges=np.zeros(3), ligand_charges=np.ones(3)),
                                    dict(protein_charges=np.zeros(3), ligand_charges=[np.nan, 0.]),
                                    dict(protein_charges=np.zeros(3), ligand_charges=[True, False])])
def test_invalid_chemistry_is_rejected_instead_of_falling_back(monkeypatch, kwargs):
    def forbidden(**kwargs):
        pytest.fail("invalid typing reached lower-level score")

    monkeypatch.setattr(scoring, "mm_gbsa_binding_energy", forbidden)
    result = scoring.mm_gbsa_binding_score(_cloud(3), np.ones((2, 3)), **kwargs)
    assert result["error"] == "mm_gbsa_failed"
    assert result["blocked_reason"] == "invalid_mm_gbsa_inputs_or_evaluation"


def test_supplied_heteroatom_types_change_actual_interaction_proxy():
    protein = np.array([[0., 0., 0.], [3., 0., 0.], [0., 3., 0.]])
    ligand = np.array([[1., 1., 2.], [2., 1., 2.]])
    carbon = scoring.mm_gbsa_binding_score(protein, ligand, ligand_elements=["C", "C"])
    typed = scoring.mm_gbsa_binding_score(protein, ligand, ligand_elements=["N", "O"])
    assert "error" not in carbon and "error" not in typed
    assert typed["chemistry_input_scope"]["ligand_elements_supplied"] is True
    assert typed["chemistry_input_scope"]["protein_elements_supplied"] is False
    assert typed["chemistry_input_scope"]["partial_charges_supplied"] is False
    assert typed["is_free_energy"] is False
    assert typed["deltaG_mm_gbsa_kcal_mol"] != carbon["deltaG_mm_gbsa_kcal_mol"]


def test_service_forwards_heteroatom_pose_order_without_fabricating_protein_charges(monkeypatch):
    actual = scoring.mm_gbsa_binding_score
    observed = []

    def record(protein, ligand, **kwargs):
        observed.append(kwargs)
        return actual(protein, ligand, **kwargs)

    monkeypatch.setattr(screening, "_mm_gbsa_binding_score", record)
    result = screening.TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB, ligand_input="CCO",
    )
    assert result.pose_scores
    assert observed
    assert observed[0]["ligand_elements"] == ["C", "C", "O"]
    assert "protein_charges" not in observed[0]
    assert "ligand_charges" not in observed[0]


@pytest.mark.parametrize("translation", [[50., 0., 0.], [-500., 200., 100.], [10., -20., 30.]])
def test_proxy_dynamics_shared_translation_keeps_relative_motion(translation, monkeypatch):
    def evaluate(state, pairs, **kwargs):
        return SimpleNamespace(forces=torch.zeros_like(state.coords), energy=torch.zeros(1))

    monkeypatch.setattr(scoring.ProductForceField, "from_registry", lambda *args: SimpleNamespace(energy_forces=evaluate))
    protein = np.array([[0., 0., 0.], [3., 0., 0.], [0., 3., 0.], [0., 0., 3.]])
    ligand = np.array([[1., 1., 1.], [2., 1., 1.]])
    a, left = scoring.run_stability_simulation(protein, ligand, steps=2, seed=17)
    b, right = scoring.run_stability_simulation(protein + translation, ligand + translation, steps=2, seed=17)
    assert left["status"] == right["status"] == "observed"
    assert a == b
    assert left["pose_observations"] == right["pose_observations"]
    assert right["coordinate_preparation"] == "shared_box_center_translation_v1"
    assert right["scientific_claim_validated"] is False
    assert right["boundary_consistency_validated"] is False


def test_chemical_mapping_failure_cannot_silently_fall_back_to_field_score(monkeypatch):
    monkeypatch.setattr(screening, "_mm_gbsa_binding_score", lambda *args, **kwargs: {
        "binding_energy_kcal_mol": float("inf"), "error": "mm_gbsa_failed",
        "detail": "invalid_ligand_element_mapping",
    })
    result = screening.TierBetaScreening(device="cpu", pose_count=1, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB, ligand_input="CCO",
    )
    assert result.ok is False
    assert "invalid_ligand_element_mapping" in result.blocked_reason
