import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools import run_ligand_backmapping_scoring as mod
from tools.run_ligand_backmapping_scoring import _inline_score_from_row, _ligand_props


def test_ligand_props_accepts_legacy_ligand_columns():
    row = {
        "ligand_mw": 310.5,
        "ligand_logp": 2.4,
        "ligand_rot_bonds": 7,
        "ligand_h_donors": 2,
        "ligand_h_acceptors": 5,
    }
    props = _ligand_props(row)
    assert props["mw"] == 310.5
    assert props["logp"] == 2.4
    assert props["rot_bonds"] == 7.0
    assert props["h_donors"] == 2.0
    assert props["h_acceptors"] == 5.0


def test_ligand_props_accepts_hard_decoy_metadata_columns():
    row = {
        "molecular_weight": 298.4,
        "logp": 3.6,
        "rot_bonds": 6,
        "h_donors": 3,
        "h_acceptors": 3,
    }
    props = _ligand_props(row)
    assert props["mw"] == 298.4
    assert props["logp"] == 3.6
    assert props["rot_bonds"] == 6.0
    assert props["h_donors"] == 3.0
    assert props["h_acceptors"] == 3.0


def test_inline_score_from_row_carries_ligand_priors_from_queue_row():
    row = {
        "inline_aux_available": True,
        "trajectory_frame_count": 120,
        "binding_energy_proxy": -5.0,
        "binding_energy_mmpbsa_kcal_mol_proxy": -5.0,
        "binding_energy_mmpbsa_std": 0.2,
        "stability_score": 0.8,
        "contact_fraction": 0.6,
        "mean_min_distance_A": 3.5,
        "ligand_mw": 298.4,
        "ligand_logp": 3.6,
        "ligand_rot_bonds": 6,
        "ligand_h_donors": 3,
        "ligand_h_acceptors": 3,
    }
    score = _inline_score_from_row(row, ligand_model="bead2")
    assert score is not None
    assert score["ligand_mw"] == 298.4
    assert score["ligand_logp"] == 3.6
    assert score["ligand_rot_bonds"] == 6.0
    assert score["ligand_h_donors"] == 3.0
    assert score["ligand_h_acceptors"] == 3.0


def test_load_native_target_coords_prefers_explicit_pdb_and_marks_provenance(tmp_path):
    native_pdb = tmp_path / "native_target.pdb"
    native_pdb.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       4.000   0.000   0.000  1.00 20.00           C",
                "HETATM    3  C1  LIG L   1       1.500   1.000   0.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    info = mod._load_native_target_coords("Toy Target", native_path=str(native_pdb))

    assert info["source_kind"] == "explicit_native_pdb"
    assert info["source_available"] is True
    assert info["source_used_explicit_native_path"] is True
    assert info["source_residue_anchor_mode"] == "ca_only"
    assert info["protein_ca_count"] == 2
    assert info["ligand_atom_count"] == 1
    assert info["coords"].shape == (2, 3)


def test_load_native_target_coords_supports_explicit_mmcif(tmp_path):
    native_cif = tmp_path / "native_target.cif"
    native_cif.write_text(
        "\n".join(
            [
                "data_native_target",
                "#",
                "loop_",
                "_atom_site.group_PDB",
                "_atom_site.id",
                "_atom_site.type_symbol",
                "_atom_site.label_atom_id",
                "_atom_site.label_comp_id",
                "_atom_site.label_asym_id",
                "_atom_site.Cartn_x",
                "_atom_site.Cartn_y",
                "_atom_site.Cartn_z",
                "ATOM 1 C CA GLY A 0.000 0.000 0.000",
                "ATOM 2 C CA ALA A 4.000 0.000 0.000",
                "HETATM 3 C C1 LIG L 1.500 1.000 0.000",
                "#",
                "",
            ]
        ),
        encoding="utf-8",
    )

    info = mod._load_native_target_coords("Toy Target", native_path=str(native_cif))

    assert info["source_kind"] == "explicit_native_mmcif"
    assert info["source_available"] is True
    assert info["source_format"] == "mmcif"
    assert info["protein_ca_count"] == 2
    assert info["coords"].shape == (2, 3)


def test_load_native_target_coords_uses_repo_registry_fallback(tmp_path, monkeypatch):
    native_pdb = tmp_path / "registry_native.pdb"
    native_pdb.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       4.000   0.000   0.000  1.00 20.00           C",
                "HETATM    3  C1  LIG L   1       1.500   1.000   0.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        mod,
        "resolve_repo_native_entry",
        lambda target: {
            "target": target,
            "native_pdb_path": str(native_pdb),
            "native_pdb_ready": True,
            "native_format": "pdb",
            "pdb_id": "6LU7",
        },
    )

    info = mod._load_native_target_coords("sars_cov_2_mpro", native_path="")

    assert info["source_kind"] == "repo_registry_native_pdb"
    assert info["source_available"] is True
    assert info["source_path"] == str(native_pdb)
    assert info["source_used_explicit_native_path"] is False
    assert info["protein_ca_count"] == 2
    assert info["ligand_atom_count"] == 1


def test_process_queue_row_emits_native_provenance_and_backmap_metadata(tmp_path, monkeypatch):
    native_pdb = tmp_path / "native_target.pdb"
    native_pdb.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       4.000   0.000   0.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    def _fake_score_frames(**kwargs):
        del kwargs
        return {
            "binding_energy_proxy": -0.12,
            "binding_energy_mmpbsa_kcal_mol_proxy": -0.12,
            "binding_energy_mmpbsa_std": 0.04,
            "stability_score": 0.51,
            "contact_fraction": 0.62,
            "mean_min_distance_A": 2.75,
            "frame_count": 64,
            "ligand_affinity_hint": 0.31,
            "ligand_onsps_norm": 0.22,
            "ligand_mw": 250.0,
            "ligand_logp": 2.5,
            "ligand_rot_bonds": 4.0,
            "ligand_h_donors": 1.0,
            "ligand_h_acceptors": 3.0,
            "ligand_model": "bead2",
        }

    def _fake_backmap(*, protein_ca, ligand_xyz, out_pdb):
        assert protein_ca.shape == (2, 3)
        assert ligand_xyz.shape[0] >= 2
        Path(out_pdb).write_text("MODEL\nENDMDL\n", encoding="utf-8")
        return {"protein_residues": 2, "protein_atoms": 10, "ligand_atoms": int(ligand_xyz.shape[0])}

    monkeypatch.setattr(mod, "_score_frames", _fake_score_frames)
    monkeypatch.setattr(mod, "_pseudo_backmap", _fake_backmap)

    row = {
        "queue_id": "toy_queue",
        "target": "Toy Target",
        "ligand_id": "toy_ligand",
        "native_pdb_path": str(native_pdb),
        "pocket_x": 1.0,
        "pocket_y": 2.0,
        "pocket_z": 3.0,
    }
    cfg = {
        "score_only": False,
        "jobs_root": str(tmp_path / "jobs"),
        "trajectory_root": str(tmp_path / "traj"),
        "trajectory_glob": "",
        "allow_missing_trajectory": True,
        "contact_cutoff_A": 4.5,
        "min_frames": 8,
        "ligand_model": "bead2",
        "hbond_onsps_weight": 0.0,
    }

    result = mod._process_queue_row(row, cfg)

    assert result["protein_structure_source_kind"] == "explicit_native_pdb"
    assert result["protein_structure_source_available"] is True
    assert result["backmapped_contains_protein"] is True
    assert result["backmapped_structure_kind"] == "pseudo_backmapped_protein_ligand_pdb"
    assert result["backmapped_protein_atoms"] == 10

    score_payload = json.loads(Path(result["score_json"]).read_text(encoding="utf-8"))
    assert score_payload["protein_structure_provenance"]["source_kind"] == "explicit_native_pdb"
    assert score_payload["backmapped_contains_protein"] is True
    assert score_payload["backmapped_structure_kind"] == "pseudo_backmapped_protein_ligand_pdb"


def test_score_frames_clash_relief_recomputes_proxy_after_translation(tmp_path):
    protein = np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32)
    ligand = np.asarray([[0.55, 0.0, 0.0], [0.95, 0.0, 0.0]], dtype=np.float32)

    score = mod._score_frames(
        frame_paths=[],
        trajectory_npz_path="",
        protein_default=protein,
        ligand_default=ligand,
        contact_cutoff_A=6.0,
        row={"smiles": "CCO"},
        min_frames=1,
        ligand_model="2bead",
        hbond_onsps_weight=1.0,
        clash_relief_mode="translate",
        clash_relief_target_min_distance_A=2.12,
        clash_relief_max_translation_A=2.0,
        clash_relief_max_steps=12,
    )

    assert score["clash_relief_enabled"] is True
    assert score["clash_relief_applied_frame_count"] == 1
    assert score["pre_repair_clash_frame_fraction"] == 1.0
    assert score["pre_repair_mean_min_distance_A"] < 1.0
    assert score["mean_min_distance_A"] >= 2.1
    assert score["clash_frame_fraction"] == 0.0
    assert score["binding_energy_proxy"] < score["pre_repair_binding_energy_proxy"]


def test_process_queue_row_clash_relief_bypasses_inline_metrics_and_records_provenance(tmp_path):
    native_pdb = tmp_path / "native_target.pdb"
    native_pdb.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    npz = tmp_path / "trajectory.npz"
    np.savez(
        npz,
        protein_ca=np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32),
        ligand_frames=np.asarray(
            [
                [[0.55, 0.0, 0.0], [0.95, 0.0, 0.0]],
                [[0.60, 0.0, 0.0], [1.00, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    row = {
        "queue_id": "toy_clash",
        "target": "Toy Target",
        "ligand_id": "toy_ligand",
        "native_pdb_path": str(native_pdb),
        "trajectory_npz": str(npz),
        "inline_aux_available": True,
        "binding_energy_proxy": 9.9,
        "binding_energy_mmpbsa_kcal_mol_proxy": 9.9,
        "binding_energy_mmpbsa_std": 0.0,
        "stability_score": 0.0,
        "contact_fraction": 0.0,
        "mean_min_distance_A": 0.5,
        "smiles": "CCO",
    }
    cfg = {
        "score_only": False,
        "jobs_root": str(tmp_path / "jobs"),
        "trajectory_root": str(tmp_path),
        "trajectory_glob": "",
        "allow_missing_trajectory": False,
        "contact_cutoff_A": 6.0,
        "min_frames": 2,
        "ligand_model": "2bead",
        "hbond_onsps_weight": 1.0,
        "clash_relief_mode": "translate",
        "clash_relief_target_min_distance_A": 2.12,
        "clash_relief_max_translation_A": 2.0,
        "clash_relief_max_steps": 12,
    }

    result = mod._process_queue_row(row, cfg)

    assert result["clash_relief_enabled"] is True
    assert result["clash_relief_applied_frame_count"] == 2
    assert result["pre_repair_binding_energy_proxy"] != 9.9
    assert result["binding_energy_proxy"] < result["pre_repair_binding_energy_proxy"]
    assert result["mean_min_distance_A"] >= 2.1
    score_payload = json.loads(Path(result["score_json"]).read_text(encoding="utf-8"))
    assert score_payload["score"]["clash_relief_mode"] == "translate"
    assert score_payload["score"]["pre_repair_clash_frame_fraction"] == 1.0


def test_residual_intrusion_variant_penalizes_compact_hydrophobic_contact_decoy(tmp_path):
    spec = tmp_path / "residual_intrusion.json"
    zero_base_weights = {
        "prior_weight_h_donors": 0.0,
        "prior_weight_h_acceptors": 0.0,
        "prior_weight_rot_bonds": 0.0,
        "prior_weight_neg_logp": 0.0,
        "weakness_weight_distance": 0.0,
        "weakness_weight_neg_contact": 0.0,
        "weakness_weight_neg_stability": 0.0,
        "weakness_weight_energy": 0.0,
        "support_weight_neg_energy": 0.0,
        "support_weight_contact": 0.0,
        "support_weight_stability": 0.0,
        "support_weight_neg_distance": 0.0,
        "affinity_mismatch_weight": 0.0,
        "support_penalty_weight": 0.0,
    }
    spec.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "max_abs_delta_score": 1.0,
                        "yellow_band_abs_delta_score": 0.5,
                    },
                    "tuning": {
                        **zero_base_weights,
                        "variant": "gpcr_core_decoy_intrusion_v1",
                        "intrusion_weight_low_h_donors": 0.8,
                        "intrusion_weight_low_h_acceptors": 0.8,
                        "intrusion_weight_low_rot_bonds": 0.5,
                        "intrusion_weight_high_logp": 0.7,
                        "intrusion_weight_low_affinity": 0.5,
                        "intrusion_contact_bias": 0.25,
                        "intrusion_weight_contact": 0.9,
                        "intrusion_weight_stability": 0.4,
                        "intrusion_weight_neg_distance": 0.3,
                        "min_intrusion_prior_pressure_for_delta": 1.0,
                        "min_intrusion_contact_support_for_delta": 1.0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    df = pd.DataFrame(
        {
            "ligand_id": ["compact_hydrophobic_decoy", "beta_blocker_like_active"],
            "binding_score_composite_v7": [-2.0, -1.9],
        }
    )
    args = argparse.Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode="apply",
        residual_prototype_family="gpcr",
        residual_prototype_spec_json=str(spec),
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=None,
        residual_prototype_yellow_band_abs_delta_score=None,
    )

    out, summary = mod._apply_residual_prototype_shadow(
        df,
        args,
        z_e=pd.Series([-0.5, -0.8]),
        z_d=pd.Series([-0.7, -0.5]),
        z_s=pd.Series([0.8, 0.9]),
        z_c=pd.Series([1.2, 0.9]),
        z_aff=pd.Series([-1.0, 1.0]),
        z_logp=pd.Series([1.4, -0.5]),
        z_rot=pd.Series([-1.1, 1.0]),
        z_hd=pd.Series([-1.2, 1.0]),
        z_ha=pd.Series([-1.0, 1.0]),
    )

    assert summary["tuning_variant"] == "gpcr_core_decoy_intrusion_v1"
    assert summary["positive_delta_count"] == 1
    assert summary["active_score_col"] == "binding_score_composite_v7_residual_active"
    assert out.loc[0, "residual_shadow_intrusion_pressure"] > 1.0
    assert out.loc[0, "residual_shadow_delta"] > 0.0
    assert out.loc[1, "residual_shadow_delta"] == 0.0
    assert out.loc[0, "binding_score_composite_v7_residual_active"] > out.loc[0, "binding_score_composite_v7"]


def test_residual_intrusion_variant_does_not_apply_ungated_intrusion_raw_delta(tmp_path):
    spec = tmp_path / "residual_intrusion_gated.json"
    spec.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "max_abs_delta_score": 1.0,
                        "yellow_band_abs_delta_score": 0.5,
                    },
                    "tuning": {
                        "variant": "gpcr_core_decoy_intrusion_v1",
                        "intrusion_weight_low_h_donors": 1.0,
                        "intrusion_weight_low_h_acceptors": 1.0,
                        "intrusion_weight_low_rot_bonds": 1.0,
                        "intrusion_weight_high_logp": 1.0,
                        "intrusion_weight_low_affinity": 1.0,
                        "intrusion_contact_bias": 0.25,
                        "intrusion_weight_contact": 1.0,
                        "min_intrusion_prior_pressure_for_delta": 100.0,
                        "min_intrusion_contact_support_for_delta": 100.0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    df = pd.DataFrame(
        {
            "ligand_id": ["ungated_decoy"],
            "binding_score_composite_v7": [-2.0],
        }
    )
    args = argparse.Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode="apply",
        residual_prototype_family="gpcr",
        residual_prototype_spec_json=str(spec),
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=None,
        residual_prototype_yellow_band_abs_delta_score=None,
    )
    one = pd.Series([1.0], dtype=float)
    neg = pd.Series([-1.0], dtype=float)

    out, summary = mod._apply_residual_prototype_shadow(
        df,
        args,
        z_e=neg,
        z_d=neg,
        z_s=one,
        z_c=one,
        z_aff=neg,
        z_logp=one,
        z_rot=neg,
        z_hd=neg,
        z_ha=neg,
    )

    assert summary["intrusion_positive_delta_count"] == 0
    assert summary["positive_delta_count"] == 0
    assert out.loc[0, "residual_shadow_intrusion_delta_raw"] > 0.0
    assert out.loc[0, "residual_shadow_delta"] == 0.0
    assert out.loc[0, "binding_score_composite_v7_residual_active"] == out.loc[0, "binding_score_composite_v7"]


def test_fixed_family_reference_scaling_uses_frozen_feature_stats(tmp_path):
    stats_json = tmp_path / "gpcr_reference_stats.json"
    stats_json.write_text(
        json.dumps(
            {
                "schema_version": "score_reference_stats_v1",
                "reference_scope": {
                    "family": "gpcr",
                    "source_roles": ["fit", "calibration"],
                    "eval_roles_used": [],
                },
                "features": {
                    "ligand_h_donors": {"mean": 2.0, "std": 2.0, "n": 50},
                },
            }
        ),
        encoding="utf-8",
    )
    scaling = mod._load_score_reference_scaling(
        mode="fixed_family_reference",
        stats_json=str(stats_json),
    )
    df = pd.DataFrame({"ligand_h_donors": [2.0, 6.0]})

    z = mod._zscore_with_reference(df, "ligand_h_donors", scaling)

    assert z.tolist() == [0.0, 2.0]
    assert scaling["status"] == "loaded"
    assert scaling["applied_columns"] == ["ligand_h_donors"]
    assert scaling["missing_columns"] == []
    assert scaling["stats_hash"]
    assert scaling["reference_scope"]["eval_roles_used"] == []


def test_fixed_family_reference_scaling_falls_back_to_run_local_when_feature_missing(tmp_path):
    stats_json = tmp_path / "gpcr_reference_stats.json"
    stats_json.write_text(
        json.dumps(
            {
                "schema_version": "score_reference_stats_v1",
                "features": {
                    "ligand_h_donors": {"mean": 2.0, "std": 2.0, "n": 50},
                },
            }
        ),
        encoding="utf-8",
    )
    scaling = mod._load_score_reference_scaling(
        mode="fixed_family_reference",
        stats_json=str(stats_json),
    )
    df = pd.DataFrame({"ligand_h_acceptors": [10.0, 12.0, 14.0]})

    z = mod._zscore_with_reference(df, "ligand_h_acceptors", scaling)

    assert z.round(6).tolist() == [-1.0, 0.0, 1.0]
    assert scaling["applied_columns"] == []
    assert scaling["missing_columns"] == ["ligand_h_acceptors"]
    assert scaling["fallback_columns"] == ["ligand_h_acceptors"]


def test_residual_pharmacophore_variant_rewards_aryloxypropanolamine_shadow_only(tmp_path):
    spec = tmp_path / "residual_pharmacophore.json"
    spec.write_text(
        json.dumps(
            {
                "prototype": {
                    "constraints": {
                        "max_abs_delta_score": 0.0,
                        "yellow_band_abs_delta_score": 0.0,
                    },
                    "tuning": {
                        "variant": "gpcr_adrb2_beta_blocker_pharmacophore_v1",
                        "pharmacophore_reward_score": 8.0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    df = pd.DataFrame(
        {
            "ligand_id": ["propranolol_like", "plain_decoy"],
            "ligand_smiles": [
                "CC(C)NCC(COC1=CC=CC2=CC=CC=C21)O",
                "CCOC1=CC=CC=C1",
            ],
            "binding_score_composite_v7": [-2.0, -2.1],
        }
    )
    args = argparse.Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode="shadow_only",
        residual_prototype_family="gpcr",
        residual_prototype_spec_json=str(spec),
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=None,
        residual_prototype_yellow_band_abs_delta_score=None,
    )
    zero = pd.Series([0.0, 0.0], dtype=float)

    out, summary = mod._apply_residual_prototype_shadow(
        df,
        args,
        z_e=zero,
        z_d=zero,
        z_s=zero,
        z_c=zero,
        z_aff=zero,
        z_logp=zero,
        z_rot=zero,
        z_hd=zero,
        z_ha=zero,
    )

    assert summary["tuning_variant"] == "gpcr_adrb2_beta_blocker_pharmacophore_v1"
    assert summary["pharmacophore_positive_match_count"] == 1
    assert out.loc[0, "gpcr_adrb2_beta_blocker_pharmacophore_match"] == 1
    assert out.loc[1, "gpcr_adrb2_beta_blocker_pharmacophore_match"] == 0
    assert out.loc[0, "binding_score_composite_v7_residual_shadow"] == -10.0
    assert out.loc[1, "binding_score_composite_v7_residual_shadow"] == -2.1
    assert out.loc[0, "binding_score_composite_v7_residual_active"] == -2.0
