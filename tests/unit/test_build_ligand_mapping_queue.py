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


def test_load_ligands_from_csv_joins_ligand_meta_when_reference_has_no_smiles(tmp_path: Path) -> None:
    reference_csv = tmp_path / "reference.csv"
    meta_csv = tmp_path / "ligand_meta.csv"
    pd.DataFrame(
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "carazolol", "is_binder": 1},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "missing_meta", "is_binder": 0},
        ]
    ).to_csv(reference_csv, index=False)
    pd.DataFrame(
        [
            {
                "ligand_id": "carazolol",
                "smiles": "CC(C)NCCO",
                "molecular_weight": 298.4,
                "logp": 3.6,
                "h_donors": 3,
                "h_acceptors": 3,
                "rot_bonds": 6,
            }
        ]
    ).to_csv(meta_csv, index=False)

    rows = mod._load_ligands_from_csv(  # noqa: SLF001 - unit test on helper
        str(reference_csv),
        csv_relax_3d=False,
        csv_relax_max_iters=200,
        csv_relax_embed_seed=13,
        ligand_meta_csv=str(meta_csv),
    )

    assert [row.ligand_id for row in rows] == ["carazolol"]
    assert rows[0].smiles == "CC(C)NCCO"
    assert rows[0].molecular_weight == 298.4


def test_write_smiles_bead_cache_writes_destination_with_unique_tmp(tmp_path: Path) -> None:
    dst = tmp_path / "ligand_smiles_bead_cache.json"
    payload = {"CCO": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]}

    mod._write_smiles_bead_cache(str(dst), payload)  # noqa: SLF001 - unit test on helper

    assert dst.exists()
    assert dst.read_text(encoding="utf-8")
    assert not any(path.name == f"{dst.name}.tmp" for path in tmp_path.iterdir())


def test_resolve_ligands_limits_required_ids_to_active_targets(tmp_path: Path) -> None:
    csv_path = tmp_path / "ligands.csv"
    meta_csv = tmp_path / "meta.csv"
    split_csv = tmp_path / "split.csv"
    pd.DataFrame(
        [
            {"target": "T_OTHER", "ligand_id": "other_a", "is_binder": 1},
            {"target": "T_OTHER", "ligand_id": "other_b", "is_binder": 0},
            {"target": "T_FOCUS", "ligand_id": "focus_a", "is_binder": 1},
            {"target": "T_FOCUS", "ligand_id": "focus_b", "is_binder": 1},
            {"target": "T_FOCUS", "ligand_id": "focus_c", "is_binder": 0},
        ]
    ).to_csv(csv_path, index=False)
    pd.DataFrame(
        [
            {"ligand_id": "other_a", "smiles": "CCO", "molecular_weight": 46.0, "logp": 0.0, "h_donors": 1, "h_acceptors": 1, "rot_bonds": 0},
            {"ligand_id": "other_b", "smiles": "CCN", "molecular_weight": 45.0, "logp": 0.1, "h_donors": 1, "h_acceptors": 1, "rot_bonds": 0},
            {"ligand_id": "focus_a", "smiles": "CCC", "molecular_weight": 44.0, "logp": 1.0, "h_donors": 0, "h_acceptors": 0, "rot_bonds": 0},
            {"ligand_id": "focus_b", "smiles": "CCCC", "molecular_weight": 58.0, "logp": 1.5, "h_donors": 0, "h_acceptors": 0, "rot_bonds": 1},
            {"ligand_id": "focus_c", "smiles": "CCCCC", "molecular_weight": 72.0, "logp": 2.0, "h_donors": 0, "h_acceptors": 0, "rot_bonds": 2},
        ]
    ).to_csv(meta_csv, index=False)
    pd.DataFrame(
        [
            {"target": "T_OTHER", "ligand_id": "other_a", "role": "fit"},
            {"target": "T_OTHER", "ligand_id": "other_b", "role": "fit"},
            {"target": "T_FOCUS", "ligand_id": "focus_a", "role": "eval"},
            {"target": "T_FOCUS", "ligand_id": "focus_b", "role": "eval"},
            {"target": "T_FOCUS", "ligand_id": "focus_c", "role": "eval"},
        ]
    ).to_csv(split_csv, index=False)

    overrides = mod._load_target_ligand_overrides(  # noqa: SLF001
        path=str(split_csv),
        roles="eval",
        role_col="role",
        target_col="target",
        ligand_col="ligand_id",
    )
    required = []
    target_set = {"T_FOCUS"}
    for target_name, ids in overrides.items():
        if target_name not in target_set:
            continue
        required.extend([str(x).strip() for x in ids if str(x).strip()])
    rows, _ = mod._resolve_ligands(  # noqa: SLF001
        ligand_sdf="",
        ligand_csv=str(csv_path),
        max_ligands=3,
        csv_relax_3d=False,
        csv_relax_max_iters=200,
        csv_relax_embed_seed=13,
        ligand_meta_csv=str(meta_csv),
        required_ligand_ids=required,
    )

    assert [row.ligand_id for row in rows] == ["focus_a", "focus_b", "focus_c"]


def test_default_pocket_center_uses_geometric_detection_not_global_centroid(tmp_path: Path) -> None:
    pdb_path = tmp_path / "target.pdb"
    lines = []
    # Dense shell around origin with a low-density cavity near (10, 10, 10).
    for x in range(0, 12, 3):
        for y in range(0, 12, 3):
            for z in range(0, 12, 3):
                if 6 <= x <= 9 and 6 <= y <= 9 and 6 <= z <= 9:
                    continue
                lines.append(f"ATOM  {len(lines)+1:5d}  CA  ALA A{len(lines)+1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C")
    pdb_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    pocket = mod._default_pocket_center("TEST_TARGET", native_path=str(pdb_path))  # noqa: SLF001

    centroid = mod._pdb_centroid(str(pdb_path))  # noqa: SLF001
    assert centroid is not None
    assert pocket != centroid
    assert max(abs(pocket[i] - centroid[i]) for i in range(3)) > 1.0
