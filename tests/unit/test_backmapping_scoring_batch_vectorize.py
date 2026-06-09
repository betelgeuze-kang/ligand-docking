from __future__ import annotations

import numpy as np

from tools.run_ligand_backmapping_scoring import _frame_mmpbsa_proxy, _frame_mmpbsa_proxy_batch, _score_frames


def test_frame_mmpbsa_proxy_batch_matches_single_frame_loop() -> None:
    rng = np.random.default_rng(0)
    prot = rng.normal(size=(40, 3)).astype(np.float32)
    frames = rng.normal(size=(8, 2, 3)).astype(np.float32)
    props = {"affinity_hint": 0.6, "polar_norm": 0.4, "logp_norm": 0.3, "onsps_norm": 0.2}
    batch = _frame_mmpbsa_proxy_batch(
        protein_xyz=prot,
        ligand_frames_xyz=frames,
        props=props,
        contact_cutoff_A=8.0,
        ligand_model="2bead",
    )
    singles = [
        _frame_mmpbsa_proxy(
            protein_xyz=prot,
            ligand_xyz=frame,
            props=props,
            contact_cutoff_A=8.0,
            ligand_model="2bead",
        )
        for frame in frames
    ]
    assert batch["min_distance_A"].shape[0] == len(singles)
    for idx, single in enumerate(singles):
        assert np.isclose(batch["deltaG_mmpbsa_proxy_kcal_mol"][idx], single["deltaG_mmpbsa_proxy_kcal_mol"], rtol=1e-5)
        assert np.isclose(batch["min_distance_A"][idx], single["min_distance_A"], rtol=1e-5)
        assert np.isclose(batch["contact_count"][idx], single["contact_count"], rtol=1e-5)


def test_score_frames_clash_relief_uses_batch_path_for_multi_frame_npz(tmp_path) -> None:
    rng = np.random.default_rng(1)
    protein = rng.normal(size=(36, 3)).astype(np.float32)
    frames = rng.normal(size=(6, 2, 3)).astype(np.float32)
    npz_path = tmp_path / "trajectory.npz"
    np.savez(npz_path, protein_ca=protein, ligand_frames=frames)
    row = {"ligand_smiles": "CCO", "affinity_hint": 0.5, "polar_norm": 0.4, "logp_norm": 0.3, "onsps_norm": 0.2}
    result = _score_frames(
        frame_paths=[],
        trajectory_npz_path=str(npz_path),
        protein_default=protein,
        ligand_default=frames[0],
        contact_cutoff_A=8.0,
        row=row,
        min_frames=1,
        ligand_model="2bead",
        hbond_onsps_weight=0.1,
        clash_relief_mode="on",
    )
    assert int(result["frame_count"]) == 6
    assert result.get("clash_relief_enabled") is True
