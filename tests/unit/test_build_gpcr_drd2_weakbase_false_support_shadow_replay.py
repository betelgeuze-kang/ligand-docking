from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_drd2_weakbase_false_support_shadow_replay as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_fixture(scores: Path, smiles: Path) -> None:
    _write_csv(
        scores,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_CHEMBL217_DRD2_HUMAN_07800",
                "score": -8.0,
                "basic_amine_count": 2,
                "cationic_center_contact_fraction_2p8_4p2A": 1.0,
                "valid_anchor_support": 0.64,
                "weak_base_rescue_support_pressure": 0.64,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "score": -7.0,
                "basic_amine_count": 2,
                "cationic_center_contact_fraction_2p8_4p2A": 1.0,
                "valid_anchor_support": 0.65,
                "weak_base_rescue_support_pressure": 0.65,
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "score": -6.0,
                "basic_amine_count": 2,
                "cationic_center_contact_fraction_2p8_4p2A": 1.0,
                "valid_anchor_support": 0.7,
                "weak_base_rescue_support_pressure": 0.7,
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "CHEMBL331883",
                "score": -5.0,
                "basic_amine_count": 1,
                "cationic_center_contact_fraction_2p8_4p2A": 1.0,
                "valid_anchor_support": 0.7,
                "weak_base_rescue_support_pressure": 0.7,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_no_support",
                "score": -4.0,
                "basic_amine_count": 0,
                "cationic_center_contact_fraction_2p8_4p2A": 0.0,
                "valid_anchor_support": 0.0,
                "weak_base_rescue_support_pressure": 0.0,
            },
        ],
    )
    _write_csv(
        smiles,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_CHEMBL217_DRD2_HUMAN_07800",
                "ligand_smiles": "CCc1cccc(N)c1C(N)=O",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "ligand_smiles": "O=S1(=O)c2cccc3cccc(c23)N1CCCN1CCN(c2ccc(F)cc2)CC1",
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "CHEMBL331883",
                "ligand_smiles": "CCC(=O)N(c1ccccc1)[C@H]1CCN(C[C@H](O)c2ccccc2)C[C@H]1C",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_no_support",
                "ligand_smiles": "CCCC",
            },
        ],
    )


def test_nitrogen_features_separate_anilide_from_aliphatic_amine() -> None:
    decoy = mod._nitrogen_features("CCc1cccc(N)c1C(N)=O")
    positive = mod._nitrogen_features("CCCN[C@H]1CCc2nc(N)sc2C1")
    assert decoy["protonatable_aliphatic_amine_count"] == 0
    assert decoy["weak_nonprotonatable_n_count"] == 2
    assert positive["protonatable_aliphatic_amine_count"] >= 1


def test_build_replay_selects_minimal_weight_to_clear_drd2_decoy(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    smiles = tmp_path / "smiles.csv"
    _write_fixture(scores, smiles)

    payload, grid_rows, selected_rows = mod.build_replay(
        scores_csv=scores,
        smiles_csv=smiles,
        score_col="score",
        out_score_col="score_weakbase",
        grid="0,1,2",
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "drd2_weakbase_false_support_shadow_replay_selected_slice_green_claim_locked"
    assert summary["selected_weight"] == 1.0
    assert summary["before_drd2_target_rank"] == 2
    assert summary["selected_drd2_target_rank"] == 1
    assert summary["selected_drd2_decoys_above_positive"] == 0
    assert summary["selected_non_drd2_positive_regression_count"] == 0
    assert summary["top_decoy_protonatable_aliphatic_amine_count"] == 0
    assert summary["top_decoy_weak_nonprotonatable_n_count"] == 2
    assert {row["weight"] for row in grid_rows} == {0.0, 1.0, 2.0}
    top_decoy = next(row for row in selected_rows if row["ligand_id"] == "decoy_CHEMBL217_DRD2_HUMAN_07800")
    assert top_decoy["drd2_weakbase_false_support_probe"] == 1.0
    assert top_decoy["score_weakbase"] == -7.0
    assert summary["claim_promotion_allowed"] is False


def test_cli_writes_replay_artifacts(tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    smiles = tmp_path / "smiles.csv"
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"
    out_grid = tmp_path / "grid.csv"
    out_scores = tmp_path / "scores_out.csv"
    _write_fixture(scores, smiles)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_weakbase_false_support_shadow_replay.py"),
            "--scores-csv",
            str(scores),
            "--smiles-csv",
            str(smiles),
            "--score-col",
            "score",
            "--out-score-col",
            "score_weakbase",
            "--grid",
            "0,1,2",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-grid-csv",
            str(out_grid),
            "--out-scores-csv",
            str(out_scores),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_drd2_weakbase_false_support_shadow_replay"
    assert "Weak-Base False-Support" in out_md.read_text(encoding="utf-8")
    assert "score_weakbase" in out_scores.read_text(encoding="utf-8")
