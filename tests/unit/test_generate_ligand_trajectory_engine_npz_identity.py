from __future__ import annotations

from pathlib import Path

import numpy as np

from tools import generate_ligand_trajectory_engine as mod


def test_write_npz_bundle_embeds_queue_identity_metadata(tmp_path: Path) -> None:
    out = tmp_path / "traj.npz"

    mod._write_npz_bundle(
        str(out),
        protein_ca=np.zeros((2, 3), dtype=np.float32),
        ligand_frames=np.zeros((3, 4, 3), dtype=np.float32),
        frame_indices=np.asarray([0, 1, 2], dtype=np.int32),
        identity_metadata={
            "queue_id": "q1",
            "target": "kinase",
            "ligand_id": "lig1",
            "simulation_seed": 123,
        },
    )

    with np.load(out, allow_pickle=False) as data:
        assert str(np.asarray(data["queue_id"]).item()) == "q1"
        assert str(np.asarray(data["target"]).item()) == "kinase"
        assert str(np.asarray(data["ligand_id"]).item()) == "lig1"
        assert int(np.asarray(data["simulation_seed"]).item()) == 123


def test_summary_return_contract_fields_include_manifest_binding_paths() -> None:
    fields = mod._summary_return_contract_fields(
        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "runs/residual_force_trajectory_regeneration_current_summary.json",
    )

    assert fields == {
        "out_manifest_csv": "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "out_summary_json": "runs/residual_force_trajectory_regeneration_current_summary.json",
    }
