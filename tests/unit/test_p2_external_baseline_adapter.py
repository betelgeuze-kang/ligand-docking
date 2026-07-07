from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.product.build_external_docking_baseline_adapter import build_external_docking_baseline_adapter


def test_baseline_adapter_builds_work_order(tmp_path: Path) -> None:
    targets = tmp_path / "targets.csv"
    ligands = tmp_path / "ligands.csv"
    pd.DataFrame([{"target": "T1", "receptor_path": "receptor.file"}]).to_csv(targets, index=False)
    pd.DataFrame([{"ligand_id": "L1", "ligand_path": "ligand.file"}]).to_csv(ligands, index=False)
    payload = build_external_docking_baseline_adapter(
        targets_csv=str(targets), ligands_csv=str(ligands), engine="vina", out_json=str(tmp_path / "adapter.json")
    )
    assert payload["summary"]["status"] == "external_baseline_work_order_ready"
    assert payload["summary"]["work_order_row_count"] == 1
    assert payload["work_order_rows"][0]["target"] == "T1"


def test_baseline_adapter_validates_results(tmp_path: Path) -> None:
    targets = tmp_path / "targets.csv"
    ligands = tmp_path / "ligands.csv"
    results = tmp_path / "results.csv"
    pd.DataFrame([{"target": "T1", "receptor_path": "receptor.file"}]).to_csv(targets, index=False)
    pd.DataFrame([{"ligand_id": "L1", "ligand_path": "ligand.file"}]).to_csv(ligands, index=False)
    pd.DataFrame([{"target": "T1", "ligand_id": "L1", "baseline_engine": "vina", "baseline_score": -7.2, "pose_path": "pose.file"}]).to_csv(results, index=False)
    payload = build_external_docking_baseline_adapter(
        targets_csv=str(targets), ligands_csv=str(ligands), engine="vina", results_csv=str(results), out_json=str(tmp_path / "adapter.json")
    )
    assert payload["summary"]["status"] == "external_baseline_results_ready"
    assert payload["result_validation"]["complete_rows"] == 1
