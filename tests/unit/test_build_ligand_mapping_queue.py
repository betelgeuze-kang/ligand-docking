from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import build_ligand_mapping_queue as mod


def test_load_ligands_from_csv_skips_nan_smiles_without_beads(tmp_path: Path) -> None:
    csv_path = tmp_path / "ligands.csv"
    pd.DataFrame(
        [
            {"ligand_id": "bad_a", "smiles": float("nan")},
            {"ligand_id": "bad_b", "smiles": "nan"},
            {"ligand_id": "good", "smiles": "CCO"},
        ]
    ).to_csv(csv_path, index=False)

    rows = mod._load_ligands_from_csv(  # noqa: SLF001 - unit test on helper
        str(csv_path),
        csv_relax_3d=False,
        csv_relax_max_iters=200,
        csv_relax_embed_seed=13,
    )

    assert [row.ligand_id for row in rows] == ["good"]
    assert [row.smiles for row in rows] == ["CCO"]


def test_write_smiles_bead_cache_writes_destination_with_unique_tmp(tmp_path: Path) -> None:
    dst = tmp_path / "ligand_smiles_bead_cache.json"
    payload = {"CCO": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]}

    mod._write_smiles_bead_cache(str(dst), payload)  # noqa: SLF001 - unit test on helper

    assert dst.exists()
    assert dst.read_text(encoding="utf-8")
    assert not any(path.name == f"{dst.name}.tmp" for path in tmp_path.iterdir())
