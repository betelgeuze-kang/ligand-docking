from pathlib import Path

import pandas as pd

from tools import build_hard_decoy_benchmark as mod


def test_build_hard_decoy_outputs_split_roles(tmp_path: Path):
    ref = pd.DataFrame(
        [
            {"target": "EGFR_KINASE", "ligand_id": "bind1", "reference_binding_kcal_mol": -8.0, "is_binder": 1},
            {"target": "EGFR_KINASE", "ligand_id": "bind2", "reference_binding_kcal_mol": -7.5, "is_binder": 1},
            {"target": "EGFR_KINASE", "ligand_id": "dec1", "reference_binding_kcal_mol": -3.0, "is_binder": 0},
            {"target": "EGFR_KINASE", "ligand_id": "dec2", "reference_binding_kcal_mol": -1.0, "is_binder": 0},
            {"target": "KRAS_G12D", "ligand_id": "bind1", "reference_binding_kcal_mol": -5.5, "is_binder": 1},
            {"target": "KRAS_G12D", "ligand_id": "dec1", "reference_binding_kcal_mol": -1.2, "is_binder": 0},
        ]
    )
    lmeta = pd.DataFrame(
        [
            {"ligand_id": "bind1", "molecular_weight": 400, "logp": 2.5, "h_donors": 1, "h_acceptors": 6, "rot_bonds": 7, "scaffold": "S_A"},
            {"ligand_id": "bind2", "molecular_weight": 410, "logp": 2.7, "h_donors": 1, "h_acceptors": 6, "rot_bonds": 8, "scaffold": "S_A"},
            {"ligand_id": "dec1", "molecular_weight": 395, "logp": 2.3, "h_donors": 1, "h_acceptors": 6, "rot_bonds": 7, "scaffold": "S_A"},
            {"ligand_id": "dec2", "molecular_weight": 180, "logp": 1.0, "h_donors": 1, "h_acceptors": 2, "rot_bonds": 3, "scaffold": "S_B"},
        ]
    )
    tmeta = pd.DataFrame(
        [
            {"target": "EGFR_KINASE", "target_family": "KINASE"},
            {"target": "KRAS_G12D", "target_family": "RAS"},
        ]
    )

    ref_csv = tmp_path / "ref.csv"
    lmeta_csv = tmp_path / "lmeta.csv"
    tmeta_csv = tmp_path / "tmeta.csv"
    out_labels = tmp_path / "labels.csv"
    out_split = tmp_path / "split.csv"
    out_json = tmp_path / "sum.json"
    out_md = tmp_path / "sum.md"
    ref.to_csv(ref_csv, index=False)
    lmeta.to_csv(lmeta_csv, index=False)
    tmeta.to_csv(tmeta_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--reference-csv",
            str(ref_csv),
            "--ligand-meta-csv",
            str(lmeta_csv),
            "--target-meta-csv",
            str(tmeta_csv),
            "--fit-targets",
            "EGFR_KINASE",
            "--hard-decoy-quantile",
            "0.5",
            "--out-labels-csv",
            str(out_labels),
            "--out-split-csv",
            str(out_split),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    payload = mod.run_build(args)
    assert bool(payload["pass"]) is True
    split = pd.read_csv(out_split)
    roles = set(split["role"].astype(str).tolist())
    assert "fit" in roles
    assert ("id_eval" in roles) or ("near_ood_eval" in roles) or ("far_ood_eval" in roles)
