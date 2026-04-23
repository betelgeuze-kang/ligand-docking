import math
from pathlib import Path

import pandas as pd

from tools import calibrate_ligand_mmpbsa_proxy as mod


def test_calibration_linear_fit(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    ref_csv = tmp_path / "ref.csv"
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    scores = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1", "binding_energy_mmpbsa_kcal_mol_proxy": -1.0},
            {"target": "T1", "ligand_id": "L2", "binding_energy_mmpbsa_kcal_mol_proxy": -2.0},
            {"target": "T2", "ligand_id": "L3", "binding_energy_mmpbsa_kcal_mol_proxy": -3.0},
        ]
    )
    # y = 2x + 1
    refs = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1", "reference_binding_kcal_mol": -1.0},
            {"target": "T1", "ligand_id": "L2", "reference_binding_kcal_mol": -3.0},
            {"target": "T2", "ligand_id": "L3", "reference_binding_kcal_mol": -5.0},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    refs.to_csv(ref_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--reference-csv",
            str(ref_csv),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--min-pairs-to-fit",
            "3",
        ]
    )
    payload = mod.run_calibration(args)
    assert payload["calibration_mode"] == "linear_fit"
    assert math.isclose(float(payload["slope"]), 2.0, rel_tol=1e-6)
    assert math.isclose(float(payload["intercept"]), 1.0, rel_tol=1e-6)
    out_df = pd.read_csv(out_csv)
    assert "binding_energy_mmpbsa_kcal_mol_calibrated" in out_df.columns
    assert out_df.shape[0] == 3


def test_calibration_uses_fit_roles_only(tmp_path: Path):
    scores_csv = tmp_path / "scores.csv"
    ref_csv = tmp_path / "ref.csv"
    split_csv = tmp_path / "split.csv"
    out_csv = tmp_path / "out.csv"
    out_json = tmp_path / "out.json"

    # Intended fit relation: y = 1*x + 0 on fit rows only.
    scores = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1", "binding_energy_mmpbsa_kcal_mol_proxy": -1.0},
            {"target": "T1", "ligand_id": "L2", "binding_energy_mmpbsa_kcal_mol_proxy": -2.0},
            # Eval row with incompatible mapping (would skew if leaked).
            {"target": "T2", "ligand_id": "L3", "binding_energy_mmpbsa_kcal_mol_proxy": -3.0},
        ]
    )
    refs = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1", "reference_binding_kcal_mol": -1.0},
            {"target": "T1", "ligand_id": "L2", "reference_binding_kcal_mol": -2.0},
            {"target": "T2", "ligand_id": "L3", "reference_binding_kcal_mol": -10.0},
        ]
    )
    split = pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1", "role": "fit"},
            {"target": "T1", "ligand_id": "L2", "role": "fit"},
            {"target": "T2", "ligand_id": "L3", "role": "eval"},
        ]
    )
    scores.to_csv(scores_csv, index=False)
    refs.to_csv(ref_csv, index=False)
    split.to_csv(split_csv, index=False)

    args = mod.build_parser().parse_args(
        [
            "--scores-csv",
            str(scores_csv),
            "--reference-csv",
            str(ref_csv),
            "--split-csv",
            str(split_csv),
            "--fit-roles",
            "fit",
            "--require-split-for-fit",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--min-pairs-to-fit",
            "2",
        ]
    )
    payload = mod.run_calibration(args)
    assert payload["calibration_mode"] == "linear_fit"
    assert math.isclose(float(payload["slope"]), 1.0, rel_tol=1e-6)
    assert math.isclose(float(payload["intercept"]), 0.0, abs_tol=1e-6)
